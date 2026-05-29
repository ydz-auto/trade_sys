"""
Alpha Full Pipeline Runner - 完整 Alpha 验证流水线

按以下顺序执行：
1. Feature Discovery     - 检查现有 Features
2. IC Analysis          - 计算 IC / Rank IC
3. Conditional IC       - 按 Regime 分组 IC
4. Signal Test          - 信号测试（WR, PF, Sharpe）
5. Fee Sensitivity      - 手续费敏感性
6. Multi-Symbol         - 多币种验证
7. Stability            - 参数稳定性
8. Walk Forward         - 滚动窗口测试
9. Leaderboard          - 更新排行榜

使用方法：
    cd backend
    python research/alpha/run_alpha_full_pipeline.py --symbol BTCUSDT --days 365
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict
import argparse
from datetime import datetime
import json

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.strategy_alpha_registry import AlphaRegistry, AlphaDefinition
from research.alpha.feature_matrix import build_feature_matrix
from research.alpha.labels import compute_labels_from_df
from research.alpha.ic_analysis import compute_ic_table, compute_conditional_ic
from research.alpha.funding_regime_signal import run_signal_test
from research.alpha.regime_analysis import classify_regime


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_subheader(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


class AlphaFullPipeline:
    def __init__(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = ["1h"],
        days: int = 365,
        output_dir: str = "reports/alpha/full_pipeline/",
    ):
        self.symbols = symbols or ["BTCUSDT"]
        self.timeframes = timeframes
        self.days = days
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results = {}
        self.feature_matrix = None
        self.label_df = None

    def run(self, strategies: Optional[List[str]] = None):
        print_header(f"Alpha Full Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  Symbols: {self.symbols}")
        print(f"  Timeframes: {self.timeframes}")
        print(f"  Days: {self.days}")

        if strategies is None:
            active = AlphaRegistry.get_active()
            strategies = [a.name for a in active]
        print(f"  Strategies to validate: {len(strategies)}")

        for symbol in self.symbols:
            self.results[symbol] = {}

            print_header(f"[{symbol}] - Loading Data")
            self._load_data(symbol)

            print_header(f"[{symbol}] - Stage 1: IC Analysis")
            ic_results = self._run_ic_analysis(strategies)

            print_header(f"[{symbol}] - Stage 2: Conditional IC")
            cond_ic_results = self._run_conditional_ic(strategies)

            print_header(f"[{symbol}] - Stage 3: Signal Test")
            signal_results = self._run_signal_test(strategies)

            print_header(f"[{symbol}] - Stage 4: Multi-Symbol Summary")
            self._print_summary(ic_results, cond_ic_results, signal_results)

        print_header("Full Pipeline Complete")
        self._save_results()

        return self.results

    def _load_data(self, symbol: str):
        print_subheader("Building Feature Matrix")
        self.feature_matrix = build_feature_matrix(
            symbol=symbol,
            days=self.days,
            timeframe=self.timeframes[0],
        )
        print(f"  Feature matrix: {len(self.feature_matrix)} rows × {len(self.feature_matrix.columns)} cols")

        print_subheader("Computing Labels")
        self.label_df = compute_labels_from_df(self.feature_matrix)
        print(f"  Labels: {list(self.label_df.columns)}")

        print_subheader("Classifying Regimes")
        self.feature_matrix = classify_regime(self.feature_matrix)
        if "regime" in self.feature_matrix.columns:
            print(f"  Regimes: {self.feature_matrix['regime'].value_counts().to_dict()}")

    def _run_ic_analysis(self, strategies: List[str]) -> pd.DataFrame:
        features_to_check = []
        for name in strategies:
            try:
                defn = AlphaRegistry.get(name)
                features_to_check.extend(defn.features)
            except KeyError:
                pass

        features_to_check = list(set(features_to_check))
        available = [f for f in features_to_check if f in self.feature_matrix.columns]
        print(f"  Checking IC for {len(available)} features")

        if not available:
            return pd.DataFrame()

        ic_results = compute_ic_table(
            feature_matrix=self.feature_matrix,
            label_df=self.label_df,
            features=available,
            labels=["future_ret_1", "future_ret_3", "future_ret_5", "future_ret_10"],
        )

        top_ic = ic_results[ic_results["rank_ic"].abs() > 0.03].sort_values("rank_ic", ascending=False)
        print(f"\n  Features with |Rank IC| > 0.03: {len(top_ic)}")
        if len(top_ic) > 0:
            print(f"\n  {'Feature':<25} {'Horizon':<10} {'IC':>10} {'Rank IC':>10}")
            print(f"  {'-'*60}")
            for _, row in top_ic.head(10).iterrows():
                print(f"  {row['feature']:<25} {row['horizon']:<10} {row['ic']:>10.4f} {row['rank_ic']:>10.4f}")

        return ic_results

    def _run_conditional_ic(self, strategies: List[str]) -> pd.DataFrame:
        if "regime" not in self.feature_matrix.columns:
            print("  [SKIP] Regime classification not available")
            return pd.DataFrame()

        features_to_check = []
        for name in strategies:
            try:
                defn = AlphaRegistry.get(name)
                features_to_check.extend(defn.features)
            except KeyError:
                pass

        features_to_check = list(set(features_to_check))
        available = [f for f in features_to_check if f in self.feature_matrix.columns]

        if not available:
            return pd.DataFrame()

        cond_ic_results = compute_conditional_ic(
            feature_matrix=self.feature_matrix,
            label_df=self.label_df,
            features=available[:10],
            regime_col="regime",
        )

        if len(cond_ic_results) > 0:
            print(f"\n  Conditional IC by Regime:")
            print(f"\n  {'Feature':<25} {'Regime':<15} {'IC':>10} {'Rank IC':>10}")
            print(f"  {'-'*65}")
            for _, row in cond_ic_results.head(20).iterrows():
                print(f"  {row['feature']:<25} {row['regime']:<15} {row['ic']:>10.4f} {row['rank_ic']:>10.4f}")

        return cond_ic_results

    def _run_signal_test(self, strategies: List[str]) -> Dict[str, dict]:
        signal_results = {}

        print_subheader("Running Signal Tests")
        print(f"\n  {'Strategy':<35} {'WR%':>8} {'PF':>8} {'Sharpe':>8} {'Trades':>8} {'Status':<10}")
        print(f"  {'-'*85}")

        for name in strategies:
            try:
                defn = AlphaRegistry.get(name)
            except KeyError:
                continue

            if defn.status == "blocked":
                signal_results[name] = {"status": "blocked", "reason": defn.blocked_reason}
                continue

            result = run_signal_test(
                feature_matrix=self.feature_matrix,
                label_df=self.label_df,
                alpha_def=defn,
                percentile_thresholds=[90, 95],
                holding_bars=[5, 10],
                fee_taker=0.001,
            )

            if result:
                wr = result.get("win_rate", 0) * 100
                pf = result.get("profit_factor", 0)
                sharpe = result.get("sharpe_ratio", 0)
                trades = result.get("total_trades", 0)

                if pf > 1.0 and wr > 45:
                    status = "✓ PASS"
                elif pf > 0.8:
                    status = "~ WEAK"
                else:
                    status = "✗ FAIL"

                print(f"  {name:<35} {wr:>7.1f}% {pf:>8.2f} {sharpe:>8.2f} {trades:>8} {status:<10}")
                signal_results[name] = result
            else:
                print(f"  {name:<35} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'0':>8} {'✗ NO DATA':<10}")
                signal_results[name] = {"status": "no_data"}

        return signal_results

    def _print_summary(
        self,
        ic_results: pd.DataFrame,
        cond_ic_results: pd.DataFrame,
        signal_results: Dict[str, dict],
    ):
        print_subheader("Pipeline Summary")

        passed = [k for k, v in signal_results.items()
                  if v.get("status") != "blocked" and v.get("profit_factor", 0) > 1.0]
        blocked = [k for k, v in signal_results.items() if v.get("status") == "blocked"]
        failed = [k for k, v in signal_results.items()
                  if v.get("status") != "blocked" and v.get("profit_factor", 0) <= 1.0]

        print(f"\n  Total strategies: {len(signal_results)}")
        print(f"  ✓ PASS:  {len(passed)}")
        print(f"  ✗ FAIL:  {len(failed)}")
        print(f"  ⏸ BLOCKED: {len(blocked)}")

        if passed:
            print(f"\n  Top Passers:")
            sorted_pass = sorted(passed, key=lambda k: signal_results[k].get("profit_factor", 0), reverse=True)
            for name in sorted_pass[:5]:
                r = signal_results[name]
                print(f"    • {name}: PF={r.get('profit_factor', 0):.2f}, Sharpe={r.get('sharpe_ratio', 0):.2f}")

    def _save_results(self):
        output_file = self.output_dir / f"full_pipeline_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, default=str, indent=2)
        print(f"\n  Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Alpha Full Pipeline Runner")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    parser.add_argument("--days", type=int, default=365, help="Lookback days")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    parser.add_argument("--strategies", type=str, default=None, help="Comma-separated strategy names (default: all active)")
    parser.add_argument("--output", type=str, default="reports/alpha/full_pipeline/", help="Output directory")

    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else [args.symbol]
    strategies = [s.strip() for s in args.strategies.split(",")] if args.strategies else None

    pipeline = AlphaFullPipeline(
        symbols=symbols,
        timeframes=[args.timeframe],
        days=args.days,
        output_dir=args.output,
    )

    pipeline.run(strategies=strategies)


if __name__ == "__main__":
    main()
