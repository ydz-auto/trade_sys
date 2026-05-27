"""
Alpha Pipeline - 核心编排器

7 阶段验证流水线：
  1. Feature IC
  2. Conditional IC
  3. Signal Profitability
  4. Fee Sensitivity
  5. Multi-Symbol
  6. Parameter Stability
  7. Walk-Forward

CLI:
  python -m research.alpha.pipeline --strategy ret_5_reversal --symbols BTCUSDT,ETHUSDT --days 365
"""

import sys
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.strategy_alpha_registry import AlphaDefinition, AlphaRegistry
from research.alpha.alpha_signal_strategy import run_feature_walk_forward
from research.alpha.ic_analysis import compute_ic_table, compute_conditional_ic
from research.alpha.funding_regime_signal import run_signal_test, run_signal_matrix
from research.alpha.feature_matrix import build_feature_matrix
from research.alpha.labels import compute_labels_from_df
from research.alpha.regime_analysis import classify_regime
from research.stability.analyzer import StabilityAnalyzer


@dataclass
class StageResult:
    stage_name: str
    passed: bool
    data: Dict[str, Any]
    message: str
    skipped: bool = False


@dataclass
class AlphaValidationResult:
    strategy: str
    symbol: str
    timeframe: str
    stages: List[StageResult]
    final_status: str
    best_params: Optional[Dict[str, Any]] = None
    best_metrics: Optional[Dict[str, Any]] = None
    blocked_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "stages": [
                {
                    "stage_name": s.stage_name,
                    "passed": s.passed,
                    "message": s.message,
                    "skipped": s.skipped,
                }
                for s in self.stages
            ],
            "final_status": self.final_status,
            "best_params": self.best_params,
            "best_metrics": self.best_metrics,
            "blocked_reason": self.blocked_reason,
        }


@dataclass
class AlphaPipelineResult:
    results: List[AlphaValidationResult]
    config: Dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "config": self.config,
            "timestamp": self.timestamp,
        }


class AlphaPipeline:
    def __init__(
        self,
        symbols: List[str],
        timeframes: List[str],
        days: int,
        fee_mode: str = "both",
        holding_bars_list: Optional[List[int]] = None,
        percentile_thresholds: Optional[List[int]] = None,
        skip_walk_forward: bool = False,
        skip_stability: bool = False,
        output_dir: str = "reports/alpha/",
        exchange: str = "binance",
        ic_threshold: float = 0.02,
        ic_p_value_threshold: float = 0.05,
        pf_threshold: float = 1.0,
        win_rate_threshold: float = 0.50,
        min_trades: int = 30,
        multi_symbol_min: int = 2,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
    ):
        self.symbols = symbols
        self.timeframes = timeframes
        self.days = days
        self.fee_mode = fee_mode
        self.holding_bars_list = holding_bars_list or [5, 10, 20]
        self.percentile_thresholds = percentile_thresholds or [90, 95, 97]
        self.skip_walk_forward = skip_walk_forward
        self.skip_stability = skip_stability
        self.output_dir = output_dir
        self.exchange = exchange
        self.ic_threshold = ic_threshold
        self.ic_p_value_threshold = ic_p_value_threshold
        self.pf_threshold = pf_threshold
        self.win_rate_threshold = win_rate_threshold
        self.min_trades = min_trades
        self.multi_symbol_min = multi_symbol_min
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def run(self, strategy_names: List[str]) -> AlphaPipelineResult:
        results = []
        config = {
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "days": self.days,
            "fee_mode": self.fee_mode,
            "holding_bars_list": self.holding_bars_list,
            "percentile_thresholds": self.percentile_thresholds,
            "skip_walk_forward": self.skip_walk_forward,
            "skip_stability": self.skip_stability,
        }

        for name in strategy_names:
            try:
                defn = AlphaRegistry.get(name)
            except KeyError:
                results.append(AlphaValidationResult(
                    strategy=name,
                    symbol="",
                    timeframe="",
                    stages=[],
                    final_status="unknown",
                    blocked_reason=f"Strategy {name} not found in registry",
                ))
                continue

            if defn.status == "blocked":
                results.append(AlphaValidationResult(
                    strategy=name,
                    symbol="",
                    timeframe="",
                    stages=[],
                    final_status="blocked",
                    blocked_reason=defn.blocked_reason,
                ))
                continue

            for tf in self.timeframes:
                symbol_results = self._run_for_strategy(defn, tf)
                results.extend(symbol_results)

        return AlphaPipelineResult(
            results=results,
            config=config,
            timestamp=datetime.now().isoformat(),
        )

    def _run_for_strategy(
        self, defn: AlphaDefinition, timeframe: str
    ) -> List[AlphaValidationResult]:
        all_results = []
        multi_symbol_data = {}

        for symbol in self.symbols:
            print(f"\n{'='*60}")
            print(f"Alpha Pipeline: {defn.name} | {symbol} | {timeframe} | {self.days}d")
            print(f"{'='*60}")

            result = self._run_single(defn, symbol, timeframe)
            all_results.append(result)

            if result.best_params is not None:
                multi_symbol_data[symbol] = {
                    "best_params": result.best_params,
                    "best_metrics": result.best_metrics,
                }

        if len(self.symbols) > 1 and multi_symbol_data:
            profitable_count = sum(
                1 for v in multi_symbol_data.values()
                if v["best_metrics"] and v["best_metrics"].get("profit_factor", 0) > self.pf_threshold
            )
            for r in all_results:
                if r.final_status not in ("blocked", "unknown"):
                    if profitable_count >= self.multi_symbol_min:
                        if r.final_status == "fail":
                            r.final_status = "warning"
                    else:
                        if r.final_status == "pass":
                            r.final_status = "warning"

        return all_results

    def _run_single(
        self, defn: AlphaDefinition, symbol: str, timeframe: str
    ) -> AlphaValidationResult:
        stages = []
        best_params = None
        best_metrics = None

        try:
            fm = build_feature_matrix(
                symbol=symbol,
                exchange=self.exchange,
                days=self.days,
                timeframe=timeframe,
            )
        except Exception as e:
            return AlphaValidationResult(
                strategy=defn.name,
                symbol=symbol,
                timeframe=timeframe,
                stages=[],
                final_status="error",
                blocked_reason=str(e),
            )

        fm = classify_regime(fm)
        labels = compute_labels_from_df(fm)
        close = fm["close"].values.astype(float)

        if defn.combo_logic == "all_must_trigger" and len(defn.features) > 1:
            fm = self._build_combo_feature(fm, defn)

        missing = [f for f in defn.features if f not in fm.columns]
        combo_col = "_combo_feature"
        if defn.combo_logic and combo_col in fm.columns:
            effective_primary = combo_col
        else:
            effective_primary = defn.primary_feature
            missing = [f for f in defn.features if f not in fm.columns]
        if missing:
            return AlphaValidationResult(
                strategy=defn.name,
                symbol=symbol,
                timeframe=timeframe,
                stages=[StageResult(
                    stage_name="data_quality",
                    passed=False,
                    data={},
                    message=f"Missing features: {missing}",
                )],
                final_status="blocked",
                blocked_reason=f"Missing features: {missing}",
            )

        s1 = self._stage_feature_ic(fm, labels, defn, effective_primary)
        stages.append(s1)
        if not s1.passed:
            return self._build_result(defn, symbol, timeframe, stages, "fail")

        s2 = self._stage_conditional_ic(fm, labels, defn, effective_primary)
        stages.append(s2)
        if not s2.passed:
            return self._build_result(defn, symbol, timeframe, stages, "fail")

        s3 = self._stage_signal_profitability(fm, close, defn, effective_primary)
        stages.append(s3)
        if not s3.passed:
            return self._build_result(defn, symbol, timeframe, stages, "fail")

        best_params = s3.data.get("best_params")
        best_metrics = s3.data.get("best_metrics")

        s4 = self._stage_fee_sensitivity(fm, close, best_params, defn, effective_primary)
        stages.append(s4)
        if not s4.passed:
            return self._build_result(
                defn, symbol, timeframe, stages,
                "warning" if s4.data.get("profitable_maker") else "fail",
                best_params=best_params,
                best_metrics=best_metrics,
            )

        if not self.skip_stability and best_params:
            s6 = self._stage_parameter_stability(fm, close, best_params, defn, effective_primary)
            stages.append(s6)

        if not self.skip_walk_forward and best_params:
            s7 = self._stage_walk_forward(fm, close, best_params, defn, effective_primary)
            stages.append(s7)

        final_status = "pass"
        for s in stages:
            if not s.passed and not s.skipped:
                final_status = "warning"
                break

        return AlphaValidationResult(
            strategy=defn.name,
            symbol=symbol,
            timeframe=timeframe,
            stages=stages,
            final_status=final_status,
            best_params=best_params,
            best_metrics=best_metrics,
        )

    def _build_combo_feature(
        self, fm: pd.DataFrame, defn: AlphaDefinition
    ) -> pd.DataFrame:
        mask = pd.Series(True, index=fm.index)
        for feat_name, direction in defn.signal_direction_map.items():
            if feat_name not in fm.columns:
                continue
            if feat_name == defn.primary_feature:
                continue
            feat_vals = fm[feat_name]
            if direction == "negative_means_long":
                threshold = feat_vals.quantile(0.05)
                mask &= (feat_vals < threshold)
            elif direction == "positive_means_long":
                threshold = feat_vals.quantile(0.95)
                mask &= (feat_vals > threshold)

        combo_feature = fm[defn.primary_feature].copy()
        combo_feature[~mask] = np.nan
        fm = fm.copy()
        fm["_combo_feature"] = combo_feature
        return fm

    def _stage_feature_ic(
        self, fm: pd.DataFrame, labels: pd.DataFrame, defn: AlphaDefinition,
        effective_primary: str,
    ) -> StageResult:
        ic_features = defn.features if defn.combo_logic else [effective_primary]
        ic_df = compute_ic_table(fm, labels, features=ic_features)

        primary_rows = ic_df[ic_df["feature"] == defn.primary_feature]
        significant = primary_rows[
            (
                (primary_rows["rank_ic"].abs() > self.ic_threshold)
                & (primary_rows["rank_p_value"] < self.ic_p_value_threshold)
            )
            | (
                (primary_rows["ic"].abs() > self.ic_threshold)
                & (primary_rows["p_value"] < self.ic_p_value_threshold)
            )
        ]

        if len(significant) > 0:
            best_row = significant.loc[significant["rank_ic"].abs().idxmax()]
            return StageResult(
                stage_name="feature_ic",
                passed=True,
                data={"ic_table": ic_df.to_dict("records")},
                message=(
                    f"Primary feature {defn.primary_feature}: "
                    f"rank_ic={best_row['rank_ic']:.4f}, "
                    f"rank_p={best_row['rank_p_value']:.4f} "
                    f"at horizon={best_row['horizon']}"
                ),
            )

        return StageResult(
            stage_name="feature_ic",
            passed=False,
            data={"ic_table": ic_df.to_dict("records")},
            message=(
                f"Primary feature {defn.primary_feature} has no significant IC "
                f"(|IC| > {self.ic_threshold}, p < {self.ic_p_value_threshold})"
            ),
        )

    def _stage_conditional_ic(
        self, fm: pd.DataFrame, labels: pd.DataFrame, defn: AlphaDefinition,
        effective_primary: str,
    ) -> StageResult:
        if "trend_regime" not in fm.columns:
            return StageResult(
                stage_name="conditional_ic",
                passed=True,
                data={},
                message="No trend_regime column, skipping conditional IC",
                skipped=True,
            )

        try:
            cond_trend = compute_conditional_ic(
                fm, labels, defn.primary_feature, "future_ret_5",
                regime_col="trend_regime",
            )
        except Exception:
            return StageResult(
                stage_name="conditional_ic",
                passed=True,
                data={},
                message="Conditional IC computation failed, skipping",
                skipped=True,
            )

        valid_ic = cond_trend.dropna(subset=["ic"])
        if len(valid_ic) < 2:
            return StageResult(
                stage_name="conditional_ic",
                passed=True,
                data={"conditional_ic": cond_trend.to_dict("records")},
                message="Insufficient regime data for conditional IC",
                skipped=True,
            )

        overall_ic = valid_ic["ic"].mean()
        consistent_count = 0
        for _, row in valid_ic.iterrows():
            if overall_ic < 0 and row["ic"] < 0:
                consistent_count += 1
            elif overall_ic > 0 and row["ic"] > 0:
                consistent_count += 1

        if consistent_count >= 2:
            return StageResult(
                stage_name="conditional_ic",
                passed=True,
                data={"conditional_ic": cond_trend.to_dict("records")},
                message=(
                    f"IC consistent in {consistent_count}/{len(valid_ic)} regimes "
                    f"(overall IC direction: {'negative' if overall_ic < 0 else 'positive'})"
                ),
            )

        return StageResult(
            stage_name="conditional_ic",
            passed=False,
            data={"conditional_ic": cond_trend.to_dict("records")},
            message=(
                f"IC inconsistent across regimes: "
                f"only {consistent_count}/{len(valid_ic)} consistent"
            ),
        )

    def _stage_signal_profitability(
        self, fm: pd.DataFrame, close: np.ndarray, defn: AlphaDefinition,
        effective_primary: str,
    ) -> StageResult:
        feature_name = effective_primary
        feature_vals = fm[feature_name].dropna()

        if len(feature_vals) == 0:
            return StageResult(
                stage_name="signal_profitability",
                passed=False,
                data={},
                message=f"No valid data for feature {feature_name}",
            )

        if defn.combo_logic == "all_must_trigger" and feature_name == "_combo_feature":
            feature_thresholds = [0.0]
        else:
            feature_thresholds = []
            for p in self.percentile_thresholds:
                if defn.direction in ("long", "both"):
                    val = feature_vals.quantile((100 - p) / 100)
                    feature_thresholds.append(round(abs(val), 8))
                else:
                    val = feature_vals.quantile(p / 100)
                    feature_thresholds.append(round(abs(val), 8))

        directions = [defn.direction] if defn.direction != "both" else ["long", "short"]

        result_df = run_signal_matrix(
            fm, close,
            feature_name=feature_name,
            feature_thresholds=feature_thresholds,
            holding_bars_list=self.holding_bars_list,
            directions=directions,
            taker_fee=self.taker_fee,
        )

        viable = result_df[
            (result_df["trades"] >= self.min_trades)
            & (result_df["win_rate"] > self.win_rate_threshold)
            & (result_df["profit_factor"] > self.pf_threshold)
        ]

        if len(viable) > 0:
            best = viable.loc[viable["avg_ret"].idxmax()]
            return StageResult(
                stage_name="signal_profitability",
                passed=True,
                data={
                    "signal_matrix": result_df.to_dict("records"),
                    "best_params": {
                        "threshold": float(best["threshold"]),
                        "holding_bars": int(best["holding_bars"]),
                        "direction": str(best["direction"]),
                    },
                    "best_metrics": {
                        "profit_factor": float(best["profit_factor"]),
                        "sharpe": float(best["sharpe"]),
                        "win_rate": float(best["win_rate"]),
                        "trades": int(best["trades"]),
                        "avg_ret": float(best["avg_ret"]),
                        "total_ret": float(best["total_ret"]),
                    },
                },
                message=(
                    f"Viable: PF={best['profit_factor']:.3f}, "
                    f"WR={best['win_rate']:.3f}, "
                    f"trades={int(best['trades'])}, "
                    f"thresh={best['threshold']:.5f}, "
                    f"hold={int(best['holding_bars'])}"
                ),
            )

        return StageResult(
            stage_name="signal_profitability",
            passed=False,
            data={"signal_matrix": result_df.to_dict("records")},
            message=(
                f"No viable combinations: "
                f"need PF>{self.pf_threshold}, WR>{self.win_rate_threshold}, "
                f"trades>={self.min_trades}"
            ),
        )

    def _stage_fee_sensitivity(
        self,
        fm: pd.DataFrame,
        close: np.ndarray,
        best_params: Optional[Dict[str, Any]],
        defn: AlphaDefinition,
        effective_primary: str,
    ) -> StageResult:
        if best_params is None:
            return StageResult(
                stage_name="fee_sensitivity",
                passed=False,
                data={},
                message="No best params from signal profitability stage",
            )

        threshold = best_params["threshold"]
        holding_bars = best_params["holding_bars"]
        direction = best_params["direction"]

        feature_vals = fm[effective_primary].values.astype(float)
        regime_labels = fm["trend_regime"].values

        result_maker = run_signal_test(
            close, feature_vals, regime_labels,
            feature_threshold=threshold,
            holding_bars=holding_bars,
            direction=direction,
            taker_fee=self.maker_fee,
        )
        result_taker = run_signal_test(
            close, feature_vals, regime_labels,
            feature_threshold=threshold,
            holding_bars=holding_bars,
            direction=direction,
            taker_fee=self.taker_fee,
        )

        profitable_maker = result_maker.get("profit_factor", 0) > 1.0 and result_maker.get("avg_ret", 0) > 0
        profitable_taker = result_taker.get("profit_factor", 0) > 1.0 and result_taker.get("avg_ret", 0) > 0

        data = {
            "maker_result": result_maker,
            "taker_result": result_taker,
            "profitable_maker": profitable_maker,
            "profitable_taker": profitable_taker,
        }

        if profitable_taker:
            return StageResult(
                stage_name="fee_sensitivity",
                passed=True,
                data=data,
                message=(
                    f"Profitable with taker fee: "
                    f"PF={result_taker['profit_factor']:.3f}, "
                    f"avg_ret={result_taker['avg_ret']:.5f}"
                ),
            )

        if profitable_maker:
            return StageResult(
                stage_name="fee_sensitivity",
                passed=False,
                data=data,
                message=(
                    f"Profitable with maker but not taker fee: "
                    f"maker PF={result_maker['profit_factor']:.3f}, "
                    f"taker PF={result_taker['profit_factor']:.3f}"
                ),
            )

        return StageResult(
            stage_name="fee_sensitivity",
            passed=False,
            data=data,
            message="Not profitable with either fee level",
        )

    def _stage_parameter_stability(
        self,
        fm: pd.DataFrame,
        close: np.ndarray,
        best_params: Dict[str, Any],
        defn: AlphaDefinition,
        effective_primary: str,
    ) -> StageResult:
        base_threshold = best_params["threshold"]
        holding_bars = best_params["holding_bars"]
        direction = best_params["direction"]

        feature_vals = fm[effective_primary].values.astype(float)
        regime_labels = fm["trend_regime"].values

        threshold_range = np.linspace(
            base_threshold * 0.5, base_threshold * 1.5, 11
        ).tolist()

        analyzer = StabilityAnalyzer()

        def metric_fn(thresh: float) -> float:
            result = run_signal_test(
                close, feature_vals, regime_labels,
                feature_threshold=thresh,
                holding_bars=holding_bars,
                direction=direction,
                taker_fee=self.taker_fee,
            )
            return result.get("sharpe", 0.0) if not np.isnan(result.get("sharpe", 0.0)) else 0.0

        sweep = analyzer.analyze_1d("threshold", threshold_range, metric_fn)

        if sweep.is_flat:
            return StageResult(
                stage_name="parameter_stability",
                passed=True,
                data={"sweep": sweep.to_dict()},
                message=f"Stable: std={sweep.std_metric:.4f}, is_flat=True",
            )

        return StageResult(
            stage_name="parameter_stability",
            passed=False,
            data={"sweep": sweep.to_dict()},
            message=f"Unstable: std={sweep.std_metric:.4f}, is_flat=False",
        )

    def _stage_walk_forward(
        self,
        fm: pd.DataFrame,
        close: np.ndarray,
        best_params: Dict[str, Any],
        defn: AlphaDefinition,
        effective_primary: str,
    ) -> StageResult:
        threshold = best_params["threshold"]
        holding_bars = best_params["holding_bars"]
        direction = best_params["direction"]

        feature_vals = fm[effective_primary].values.astype(float)
        regime_labels = fm["trend_regime"].values

        bars_per_day_map = {"1m": 1440, "5m": 288, "15m": 96, "1h": 24, "4h": 6}
        bars_per_day = bars_per_day_map.get(self.timeframes[0] if self.timeframes else "1h", 24)

        train_bars = 30 * bars_per_day
        test_bars = 7 * bars_per_day

        wf_result = run_feature_walk_forward(
            close=close,
            feature_vals=feature_vals,
            regime_labels=regime_labels,
            threshold=threshold,
            holding_bars=holding_bars,
            direction=direction,
            taker_fee=self.taker_fee,
            train_bars=train_bars,
            test_bars=test_bars,
        )

        if wf_result.total_windows == 0:
            return StageResult(
                stage_name="walk_forward",
                passed=False,
                data={"total_windows": 0},
                message="No valid walk-forward windows",
            )

        passed = (
            wf_result.avg_return > 0
            and wf_result.win_rate_consistency > 0.5
        )

        return StageResult(
            stage_name="walk_forward",
            passed=passed,
            data={
                "total_windows": wf_result.total_windows,
                "avg_return": wf_result.avg_return,
                "avg_sharpe": wf_result.avg_sharpe,
                "win_rate_consistency": wf_result.win_rate_consistency,
                "profit_factor": wf_result.profit_factor,
            },
            message=(
                f"WF: {wf_result.total_windows} windows, "
                f"avg_ret={wf_result.avg_return:.5f}, "
                f"avg_sharpe={wf_result.avg_sharpe:.3f}, "
                f"wr_consistency={wf_result.win_rate_consistency:.3f}"
            ),
        )

    def _build_result(
        self,
        defn: AlphaDefinition,
        symbol: str,
        timeframe: str,
        stages: List[StageResult],
        final_status: str,
        best_params: Optional[Dict] = None,
        best_metrics: Optional[Dict] = None,
    ) -> AlphaValidationResult:
        return AlphaValidationResult(
            strategy=defn.name,
            symbol=symbol,
            timeframe=timeframe,
            stages=stages,
            final_status=final_status,
            best_params=best_params,
            best_metrics=best_metrics,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Alpha Research Factory - Unified Validation Pipeline"
    )
    parser.add_argument("--strategy", type=str, required=True,
                        help="Strategy name or 'all'")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT,SOLUSDT,ETCUSDT,ZECUSDT",
                        help="Comma-separated symbol list")
    parser.add_argument("--timeframes", type=str, default="1h",
                        help="Comma-separated timeframe list")
    parser.add_argument("--days", type=int, default=365,
                        help="Lookback days")
    parser.add_argument("--fee-mode", type=str, default="both",
                        choices=["taker", "maker", "both"],
                        help="Fee mode for validation")
    parser.add_argument("--holding-bars", type=str, default="5,10,20",
                        help="Comma-separated holding bars list")
    parser.add_argument("--thresholds", type=str, default="90,95,97",
                        help="Comma-separated percentile thresholds")
    parser.add_argument("--skip-walk-forward", action="store_true",
                        help="Skip walk-forward stage")
    parser.add_argument("--skip-stability", action="store_true",
                        help="Skip parameter stability stage")
    parser.add_argument("--output-dir", type=str, default="reports/alpha/",
                        help="Output directory for leaderboard files")
    parser.add_argument("--exchange", type=str, default="binance",
                        help="Exchange name")

    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    timeframes = [t.strip() for t in args.timeframes.split(",")]
    holding_bars_list = [int(x) for x in args.holding_bars.split(",")]
    percentile_thresholds = [int(x) for x in args.thresholds.split(",")]

    if args.strategy == "all":
        strategy_names = [d.name for d in AlphaRegistry.get_active()]
    else:
        strategy_names = [s.strip() for s in args.strategy.split(",")]

    pipeline = AlphaPipeline(
        symbols=symbols,
        timeframes=timeframes,
        days=args.days,
        fee_mode=args.fee_mode,
        holding_bars_list=holding_bars_list,
        percentile_thresholds=percentile_thresholds,
        skip_walk_forward=args.skip_walk_forward,
        skip_stability=args.skip_stability,
        output_dir=args.output_dir,
        exchange=args.exchange,
    )

    result = pipeline.run(strategy_names)

    from research.alpha.leaderboard import Leaderboard
    lb = Leaderboard(result)
    lb.print_summary()
    lb.print_table()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    lb.save_csv(str(output_path / "leaderboard.csv"))
    lb.save_json(str(output_path / "leaderboard.json"))

    print(f"\nLeaderboard saved to {output_path}")


if __name__ == "__main__":
    main()
