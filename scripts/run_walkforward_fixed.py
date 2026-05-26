#!/usr/bin/env python3
"""
Walk-Forward 参数优化脚本 - 修复版
使用真实策略系统，提供交易明细输出，支持参数优化
"""
import sys
import os
import time
import json
import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from runtimes.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
    Trade
)
from engines.compute.strategy.strategies import (
    BaseStrategy,
    RSIStrategy,
    MACDStrategy,
    SMACrossoverStrategy,
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    MomentumStrategy,
    PanicReversalStrategy,
    LongLiquidationBounceStrategy,
    VolumeClimaxFadeStrategy,
    WeakBounceShortStrategy,
    OIFlushStrategy,
    ShortSqueezeStrategy,
    FundingExhaustionTrapStrategy,
    DeadCatEchoStrategy,
    ImbalancePressureStrategy,
    SweepDetectionStrategy,
    LiquidityVacuumStrategy,
    AggressiveFlowStrategy,
    BreakoutStrategy,
    TrendFollowingStrategy,
    VolatilityExpansionStrategy,
    BBCompressionBreakoutStrategy,
    MomentumIgnitionStrategy,
    LeadLagStrategy,
    PremiumDivergenceStrategy
)
from engines.compute.strategy.behavioral_strategies import (
    OpenInterestBehaviorStrategy,
    FundingExtremeReversalStrategy,
    LiquidationCascadeStrategy,
    CVDDivergenceStrategy,
    WhaleTradeStrategy,
    FundingSettlementStrategy
)

logger = get_logger("walkforward_fixed")

# ============= 策略配置 =============

STRATEGY_MAPPING = {
    "rsi_oversold": RSIStrategy,
    "rsi_overbought": RSIStrategy,
    "macd_cross": MACDStrategy,
    "sma_cross": SMACrossoverStrategy,
    "ema_cross": EMACrossoverStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "momentum": MomentumStrategy,
    "panic_reversal": PanicReversalStrategy,
    "long_liquidation_bounce": LongLiquidationBounceStrategy,
    "volume_climax_fade": VolumeClimaxFadeStrategy,
    "weak_bounce_short": WeakBounceShortStrategy,
    "oi_flush": OIFlushStrategy,
    "short_squeeze": ShortSqueezeStrategy,
    "funding_exhaustion_trap": FundingExhaustionTrapStrategy,
    "dead_cat_echo": DeadCatEchoStrategy,
    "imbalance_pressure": ImbalancePressureStrategy,
    "sweep_detection": SweepDetectionStrategy,
    "liquidity_vacuum": LiquidityVacuumStrategy,
    "aggressive_flow": AggressiveFlowStrategy,
    "breakout": BreakoutStrategy,
    "trend_following": TrendFollowingStrategy,
    "volatility_expansion": VolatilityExpansionStrategy,
    "bb_compression_breakout": BBCompressionBreakoutStrategy,
    "momentum_ignition": MomentumIgnitionStrategy,
    "lead_lag": LeadLagStrategy,
    "premium_divergence": PremiumDivergenceStrategy,
    "oi_behavior": OpenInterestBehaviorStrategy,
    "funding_extreme_reversal": FundingExtremeReversalStrategy,
    "liquidation_cascade": LiquidationCascadeStrategy,
    "cvd_divergence": CVDDivergenceStrategy,
    "whale_trade": WhaleTradeStrategy,
    "funding_settlement": FundingSettlementStrategy
}

PARAM_GRIDS = {
    "rsi_oversold": {
        "period": [7, 14, 21],
        "oversold": [20, 30, 40],
        "overbought": [70, 80, 90]
    },
    "rsi_overbought": {
        "period": [7, 14, 21],
        "oversold": [20, 30, 40],
        "overbought": [70, 80, 90]
    },
    "macd_cross": {
        "fast_period": [6, 12, 18],
        "slow_period": [13, 26, 39],
        "signal_period": [5, 9, 13]
    },
    "sma_cross": {
        "fast_period": [5, 10, 20],
        "slow_period": [20, 50, 100]
    },
    "ema_cross": {
        "fast_period": [5, 10, 20],
        "slow_period": [20, 50, 100]
    },
    "bollinger_bands": {
        "period": [10, 20, 30],
        "std_dev": [1.5, 2.0, 2.5]
    },
    "momentum": {
        "period": [5, 10, 20],
        "threshold": [0.01, 0.02, 0.03]
    },
    "panic_reversal": {
        "drop_threshold": [-0.01, -0.015, -0.02],
        "volume_ratio_threshold": [1.2, 1.5, 2.0]
    },
    "long_liquidation_bounce": {
        "drop_threshold": [-0.015, -0.02, -0.025],
        "rsi_threshold": [20, 25, 30],
        "volume_ratio_threshold": [1.5, 2.0, 2.5]
    },
    "volume_climax_fade": {
        "volume_ratio_threshold": [1.5, 2.0, 2.5],
        "upper_shadow_threshold": [0.2, 0.3, 0.4],
        "price_threshold": [0.002, 0.003, 0.005]
    },
    "weak_bounce_short": {
        "drop_threshold_4h": [-0.015, -0.02, -0.025],
        "bounce_max": [0.01, 0.015, 0.02],
        "volume_ratio_threshold": [1.2, 1.5, 2.0]
    },
    "oi_flush": {
        "oi_flush_threshold": [-0.05, -0.10, -0.15],
        "funding_normalization_threshold": [0.3, 0.5, 0.7]
    },
    "short_squeeze": {
        "funding_extreme_threshold": [-1.5, -2.0, -2.5],
        "oi_growth_threshold": [0.0, 0.02, 0.04],
        "price_momentum_threshold": [0.003, 0.005, 0.008]
    },
    "funding_exhaustion_trap": {
        "funding_extreme_threshold": [2.0, 2.5, 3.0]
    },
    "dead_cat_echo": {
        "drop_threshold_4h": [-0.015, -0.02, -0.025],
        "bounce_ratio_max": [0.2, 0.3, 0.4]
    },
    "imbalance_pressure": {
        "imbalance_threshold": [0.2, 0.3, 0.4]
    },
    "sweep_detection": {
        "sweep_threshold": [0.5, 0.7, 0.9]
    },
    "liquidity_vacuum": {
        "spread_expansion_factor": [1.5, 2.0, 2.5]
    },
    "aggressive_flow": {
        "flow_imbalance_threshold": [1.5, 2.0, 2.5]
    },
    "breakout": {
        "lookback": [24, 48, 72],
        "volume_ratio_threshold": [1.2, 1.5, 2.0]
    },
    "trend_following": {
        "fast_period": [5, 10, 20],
        "slow_period": [20, 50, 100]
    },
    "volatility_expansion": {
        "atr_period": [7, 14, 21],
        "atr_expansion_ratio": [1.3, 1.5, 1.7],
        "lookback": [24, 48, 72]
    },
    "bb_compression_breakout": {
        "compression_threshold": [0.015, 0.02, 0.025]
    },
    "momentum_ignition": {
        "volume_spike_ratio": [2.0, 3.0, 4.0],
        "return_threshold": [0.008, 0.01, 0.015]
    },
    "lead_lag": {
        "divergence_threshold": [0.003, 0.005, 0.008]
    },
    "premium_divergence": {
        "premium_threshold": [0.003, 0.005, 0.008]
    },
    "oi_behavior": {
        "lookback_periods": [6, 12, 24],
        "min_oi_change_threshold": [0.008, 0.01, 0.015],
        "min_price_change_threshold": [0.003, 0.005, 0.008]
    },
    "funding_extreme_reversal": {
        "funding_zscore_threshold": [2.0, 2.5, 3.0],
        "oi_new_high_threshold": [1.3, 1.5, 1.7]
    },
    "liquidation_cascade": {
        "long_liq_spike_threshold": [500000, 1000000, 2000000],
        "oi_drop_threshold": [-0.03, -0.05, -0.08],
        "price_drop_threshold": [-0.02, -0.03, -0.04]
    },
    "cvd_divergence": {
        "lookback_periods": [12, 24, 48],
        "divergence_threshold": [0.08, 0.1, 0.15]
    },
    "whale_trade": {
        "whale_threshold_btc": [50, 100, 200],
        "lookback_trades": [3, 5, 10],
        "oi_change_threshold": [0.008, 0.01, 0.015]
    },
    "funding_settlement": {
        "minutes_before_settlement": [15, 30, 60],
        "minutes_after_settlement": [30, 60, 120]
    }
}

# ============= 数据类 =============

@dataclass
class WalkForwardResult:
    strategy_id: str
    optimize_year: int
    validation_year: int
    test_year: int
    best_params: Dict[str, Any]
    optimize_sharpe: float
    validation_sharpe: float
    test_sharpe: float
    optimize_trades: int
    validation_trades: int
    test_trades: int
    optimize_return: float
    validation_return: float
    test_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    overfitting_score: float
    test_trades_list: List[Trade]

# ============= 策略适配器 =============

class StrategyAdapter:
    """适配旧策略接口到回测引擎的SignalType接口"""
    def __init__(self, strategy: BaseStrategy, data_getter=None):
        self.strategy = strategy
        self._closes = []
        self._highs = []
        self._lows = []
        self._volumes = []
        self._data_getter = data_getter

    def _build_data_dict(self, bar: Bar) -> Dict:
        basic_data = {
            "close_prices": self._closes.copy(),
            "high_prices": self._highs.copy(),
            "low_prices": self._lows.copy(),
            "volumes": self._volumes.copy(),
            "symbol": "BTCUSDT",
            "timestamp": bar.timestamp
        }

        if self._data_getter is not None:
            try:
                supplementary_data = self._data_getter(bar.timestamp, self._closes.copy())
                basic_data.update(supplementary_data)
            except Exception as e:
                pass

        return basic_data

    def __call__(self, bar: Bar, position=None) -> SignalType:
        self._closes.append(bar.close)
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._volumes.append(bar.volume)

        if len(self._closes) > 600:
            self._closes = self._closes[-600:]
            self._highs = self._highs[-600:]
            self._lows = self._lows[-600:]
            self._volumes = self._volumes[-600:]

        data = self._build_data_dict(bar)
        try:
            signal = self.strategy.calculate(data)
            if signal:
                from engines.compute.strategy.strategies import ActionType
                if signal.action == ActionType.LONG:
                    return SignalType.BUY
                elif signal.action == ActionType.SHORT:
                    return SignalType.SELL
        except Exception as e:
            pass

        return SignalType.HOLD

# ============= Walk-Forward 运行器 =============

class WalkForwardRunner:
    DATA_LAKE_KLINES_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"
    DATA_LAKE_FUNDING_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "funding" / "symbol=BTCUSDT" / "data.parquet"
    DATA_LAKE_OI_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "oi" / "symbol=BTCUSDT" / "data.parquet"

    def __init__(self, enable_gpu: bool = True, resample: str = "1h"):
        self._results: List[WalkForwardResult] = []
        self._all_data: Dict[int, List[Bar]] = {}
        self._enable_gpu = enable_gpu
        self._resample = resample
        self._funding_df: Optional[pd.DataFrame] = None
        self._oi_df: Optional[pd.DataFrame] = None
        self._load_supplementary_data()

    def _load_supplementary_data(self):
        """加载补充数据（funding和OI）"""
        try:
            if self.DATA_LAKE_FUNDING_PATH.exists():
                self._funding_df = read_parquet_safe(self.DATA_LAKE_FUNDING_PATH)
                if self._funding_df is not None:
                    logger.info(f"Loaded funding data: {len(self._funding_df)} rows")
            if self.DATA_LAKE_OI_PATH.exists():
                self._oi_df = read_parquet_safe(self.DATA_LAKE_OI_PATH)
                if self._oi_df is not None:
                    logger.info(f"Loaded OI data: {len(self._oi_df)} rows")
        except Exception as e:
            logger.warning(f"Failed to load supplementary data: {e}")

    @staticmethod
    def _resample_bars(bars: List[Bar], freq: str) -> List[Bar]:
        if not bars or freq == "raw":
            return bars
        records = [{"timestamp": b.timestamp, "open": b.open, "high": b.high,
                    "low": b.low, "close": b.close, "volume": b.volume} for b in bars]
        df = pd.DataFrame(records).set_index("timestamp")
        ohlcv_agg = {"open": "first", "high": "max", "low": "min",
                      "close": "last", "volume": "sum"}
        df_resampled = df.resample(freq).agg(ohlcv_agg).dropna()
        result = []
        for ts, row in df_resampled.iterrows():
            result.append(Bar(
                timestamp=ts.to_pydatetime().replace(tzinfo=None) if ts.tzinfo is None else ts.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            ))
        return result

    def _get_strategy_data(self, timestamp: datetime, closes: List[float]) -> Dict:
        """获取策略所需的完整数据"""
        data = {
            "close_prices": closes,
            "high_prices": [],
            "low_prices": [],
            "volumes": [],
            "symbol": "BTCUSDT",
            "timestamp": timestamp,
        }

        try:
            ts_naive = timestamp.replace(tzinfo=None) if timestamp.tzinfo is not None else timestamp

            if self._funding_df is not None:
                mask = self._funding_df["timestamp"] <= ts_naive
                if mask.any():
                    latest_funding = self._funding_df.loc[mask].iloc[-1]
                    data["funding_rate"] = float(latest_funding.get("fundingRate", 0.0))

                    mask_30d = self._funding_df["timestamp"] <= ts_naive
                    if mask_30d.sum() > 1:
                        funding_history = self._funding_df.loc[mask_30d]["fundingRate"].values.astype(float)
                        mean = np.mean(funding_history)
                        std = np.std(funding_history)
                        if std > 0:
                            data["funding_zscore"] = (data.get("funding_rate", 0.0) - mean) / std

            if self._oi_df is not None:
                mask = self._oi_df["timestamp"] <= ts_naive
                if mask.any():
                    latest_oi = self._oi_df.loc[mask].iloc[-1]
                    sum_oi = latest_oi.get("sumOpenInterest", 0.0)
                    sum_oi = float(sum_oi) if sum_oi != "" else 0.0

                    if mask.sum() > 24:
                        prev_oi = self._oi_df.loc[mask].iloc[-25].get("sumOpenInterest", 0.0)
                        prev_oi = float(prev_oi) if prev_oi != "" else 0.0
                        if prev_oi > 0:
                            data["oi_delta"] = (sum_oi - prev_oi) / prev_oi

        except Exception as e:
            pass

        return data

    def load_year_data(self, year: int) -> List[Bar]:
        if year in self._all_data:
            return self._all_data[year]

        year_path = self.DATA_LAKE_KLINES_PATH / f"year={year}"
        if not year_path.exists():
            logger.warning(f"Year {year} data not found at {year_path}")
            return []

        bars = []
        for month_dir in sorted(year_path.iterdir()):
            if month_dir.is_dir() and month_dir.name.startswith("month="):
                parquet_file = month_dir / "data.parquet"
                if parquet_file.exists():
                    df = read_parquet_safe(parquet_file)
                    if df is not None and len(df) > 0:
                        for _, row in df.iterrows():
                            try:
                                if 'timestamp' in df.columns:
                                    ts = pd.to_datetime(row['timestamp']).tz_localize('UTC')
                                elif 'open_time' in df.columns:
                                    ts = pd.to_datetime(row['open_time'], unit='ms').tz_localize('UTC')
                                else:
                                    continue
                                bar = Bar(
                                    timestamp=ts,
                                    open=float(row.get('open', 0)),
                                    high=float(row.get('high', 0)),
                                    low=float(row.get('low', 0)),
                                    close=float(row.get('close', 0)),
                                    volume=float(row.get('volume', 0)),
                                )
                                bars.append(bar)
                            except Exception as e:
                                continue

        bars = sorted(bars, key=lambda x: x.timestamp)
        if self._resample and self._resample != "raw":
            bars = self._resample_bars(bars, self._resample)
        self._all_data[year] = bars
        logger.info(f"Loaded {year} data: {len(bars)} bars (resample={self._resample})")
        return bars

    def generate_param_grid(self, strategy_id: str) -> List[Dict[str, Any]]:
        param_grid = PARAM_GRIDS.get(strategy_id, {})
        if not param_grid:
            return [{}]

        keys = list(param_grid.keys())
        values = list(param_grid.values())

        from itertools import product
        combinations = product(*values)
        return [dict(zip(keys, combo)) for combo in combinations]

    def run_single_backtest(
        self,
        strategy_id: str,
        params: Dict[str, Any],
        bars: List[Bar],
        initial_capital: float = 10000.0,
    ) -> Tuple[Optional[float], Optional[int], Optional[float], Optional[List[Trade]]]:
        strategy_class = STRATEGY_MAPPING.get(strategy_id)
        if not strategy_class:
            return None, None, None, None

        try:
            strategy = strategy_class(strategy_id=strategy_id, **params)
        except TypeError:
            strategy = strategy_class(strategy_id=strategy_id)
            for key, value in params.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)

        adapter = StrategyAdapter(strategy, self._get_strategy_data)

        config = BacktestConfig(
            initial_capital=initial_capital,
            commission=0.0004,
            slippage=0.0005,
            position_size=0.1,
            stop_loss=0.10,
            take_profit=0.20,
            leverage=5.0,
            use_realistic_fees=True,
        )

        engine = BacktestEngine(config=config, enable_gpu=self._enable_gpu)
        engine.load_data(bars)
        result = engine.run(adapter)

        if result:
            return (
                result.metrics.sharpe_ratio,
                result.metrics.total_trades,
                result.metrics.total_return,
                result.trades
            )
        return None, None, None, None

    def optimize_params(
        self,
        strategy_id: str,
        optimize_bars: List[Bar],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float], Optional[int], Optional[float]]:
        param_combinations = self.generate_param_grid(strategy_id)

        logger.info(
            f"Optimizing {strategy_id} with {len(param_combinations)} param combinations"
        )

        best_params = None
        best_sharpe = -float('inf')
        best_trades = 0
        best_return = 0.0

        for i, params in enumerate(param_combinations):
            sharpe, trades, ret, _ = self.run_single_backtest(strategy_id, params, optimize_bars)
            if sharpe is not None and sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params
                best_trades = trades if trades else 0
                best_return = ret if ret else 0.0

        logger.info(
            f"Optimization complete: best_params={best_params}, sharpe={best_sharpe:.4f}"
        )

        return best_params, best_sharpe, best_trades, best_return

    def run_walk_forward(
        self,
        strategy_id: str,
        optimize_year: int = 2022,
        validation_year: int = 2023,
        test_year: int = 2024,
    ) -> Optional[WalkForwardResult]:
        logger.info(
            f"\n{'='*80}\nWalk-Forward: {strategy_id}\n{'='*80}"
        )

        optimize_bars = self.load_year_data(optimize_year)
        validation_bars = self.load_year_data(validation_year)
        test_bars = self.load_year_data(test_year)

        if not optimize_bars or not validation_bars or not test_bars:
            logger.error(f"Missing data for strategy {strategy_id}")
            return None

        best_params, optimize_sharpe, optimize_trades, optimize_return = self.optimize_params(
            strategy_id, optimize_bars
        )

        if best_params is None:
            logger.error(f"Failed to find good params for {strategy_id}")
            return None

        validation_sharpe, validation_trades, validation_return, _ = self.run_single_backtest(
            strategy_id, best_params, validation_bars
        )

        test_sharpe, test_trades, test_return, test_trades_list = self.run_single_backtest(
            strategy_id, best_params, test_bars
        )

        if optimize_sharpe is None or validation_sharpe is None or test_sharpe is None:
            logger.error("One of the backtests failed")
            return None

        decay_opt_to_test = 0.0
        if optimize_sharpe > 0:
            decay_opt_to_test = (optimize_sharpe - test_sharpe) / optimize_sharpe

        overfitting_score = decay_opt_to_test

        result = WalkForwardResult(
            strategy_id=strategy_id,
            optimize_year=optimize_year,
            validation_year=validation_year,
            test_year=test_year,
            best_params=best_params,
            optimize_sharpe=optimize_sharpe,
            validation_sharpe=validation_sharpe,
            test_sharpe=test_sharpe,
            optimize_trades=optimize_trades,
            validation_trades=validation_trades,
            test_trades=test_trades,
            optimize_return=optimize_return,
            validation_return=validation_return,
            test_return=test_return,
            max_drawdown=0.1,
            win_rate=0.5,
            profit_factor=1.0,
            overfitting_score=overfitting_score,
            test_trades_list=test_trades_list if test_trades_list else []
        )

        self._results.append(result)
        return result

    def save_trades_to_csv(self, result: WalkForwardResult, output_dir: str):
        """保存交易明细到CSV"""
        csv_path = Path(output_dir) / f"trades_{result.strategy_id}.csv"
        csv_path.parent.mkdir(exist_ok=True)

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "trade_index", "entry_time", "exit_time", "side", "entry_price",
                "exit_price", "quantity", "pnl", "pnl_pct", "leverage",
                "entry_fee", "exit_fee", "funding_fee", "liquidated"
            ])

            for i, trade in enumerate(result.test_trades_list):
                writer.writerow([
                    i,
                    trade.entry_time,
                    trade.exit_time,
                    trade.side,
                    trade.entry_price,
                    trade.exit_price,
                    trade.quantity,
                    trade.pnl,
                    trade.pnl_pct,
                    trade.leverage,
                    trade.entry_fee,
                    trade.exit_fee,
                    trade.funding_fee,
                    trade.liquidated
                ])

        logger.info(f"Trades saved to {csv_path}")

    def generate_report(self) -> str:
        report = []
        report.append("\n" + "="*80)
        report.append("Walk-Forward 参数优化报告 - 修复版")
        report.append("="*80)
        report.append(f"\n数据: BTCUSDT 真实历史数据 (1小时K线)")
        report.append(f"优化集: 2022 | 验证集: 2023 | 测试集: 2024")
        report.append(f"策略数: {len(self._results)}")
        report.append("\n" + "-"*80)

        for result in self._results:
            report.append(f"\n策略: {result.strategy_id}")
            report.append(f"  最佳参数: {result.best_params}")
            report.append(f"\n  优化集 (2022): Sharpe={result.optimize_sharpe:.4f}, Return=${result.optimize_return:.2f}, Trades={result.optimize_trades}")
            report.append(f"  验证集 (2023): Sharpe={result.validation_sharpe:.4f}, Return=${result.validation_return:.2f}, Trades={result.validation_trades}")
            report.append(f"  测试集 (2024): Sharpe={result.test_sharpe:.4f}, Return=${result.test_return:.2f}, Trades={result.test_trades}, Overfit={result.overfitting_score:.2%}")

        report.append("\n" + "="*80)
        report.append("策略排行榜 (按测试集 Sharpe 排序)")
        report.append("="*80)

        sorted_results = sorted(self._results, key=lambda x: x.test_sharpe, reverse=True)
        for i, result in enumerate(sorted_results, 1):
            status = "✅ PASS" if result.overfitting_score <= 0.3 else "⚠️ WARN" if result.overfitting_score <= 0.5 else "❌ FAIL"
            report.append(
                f"{i:2d}. {result.strategy_id:<35s} "
                f"Sharpe: {result.test_sharpe:7.4f} | "
                f"Return: ${result.test_return:10.2f} | "
                f"Trades: {result.test_trades:4d} | "
                f"Overfit: {result.overfitting_score:6.2%} {status}"
            )

        return "\n".join(report)

    def save_results(self, output_path: str = "walkforward_results.json", output_trades_dir: str = "trades"):
        results_dict = []
        for r in self._results:
            results_dict.append({
                "strategy_id": r.strategy_id,
                "optimize_year": r.optimize_year,
                "validation_year": r.validation_year,
                "test_year": r.test_year,
                "best_params": r.best_params,
                "optimize_sharpe": r.optimize_sharpe,
                "validation_sharpe": r.validation_sharpe,
                "test_sharpe": r.test_sharpe,
                "optimize_trades": r.optimize_trades,
                "validation_trades": r.validation_trades,
                "test_trades": r.test_trades,
                "optimize_return": r.optimize_return,
                "validation_return": r.validation_return,
                "test_return": r.test_return,
                "overfitting_score": r.overfitting_score,
            })
            self.save_trades_to_csv(r, output_trades_dir)

        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    def check_strategy_differences(self, strategy_ids: List[str]) -> str:
        """检查多个策略的交易是否有差异"""
        report = []
        report.append("\n" + "="*80)
        report.append("策略交易差异检查")
        report.append("="*80)

        strategy_trades = {}
        for result in self._results:
            if result.strategy_id in strategy_ids:
                strategy_trades[result.strategy_id] = result.test_trades_list

        all_same = True
        for i in range(len(strategy_ids)):
            for j in range(i+1, len(strategy_ids)):
                s1 = strategy_ids[i]
                s2 = strategy_ids[j]
                if s1 not in strategy_trades or s2 not in strategy_trades:
                    continue

                trades1 = strategy_trades[s1]
                trades2 = strategy_trades[s2]

                if len(trades1) != len(trades2):
                    all_same = False
                    report.append(f"❌ {s1} 与 {s2} 交易数量不同: {len(trades1)} vs {len(trades2)}")
                else:
                    same = True
                    for k in range(min(10, len(trades1))):
                        t1 = trades1[k]
                        t2 = trades2[k]
                        if (t1.entry_time != t2.entry_time or
                            t1.exit_time != t2.exit_time or
                            abs(t1.entry_price - t2.entry_price) > 1e-6 or
                            abs(t1.exit_price - t2.exit_price) > 1e-6):
                            same = False
                            break

                    if same:
                        all_same = False
                        report.append(f"❌ {s1} 与 {s2} 前10笔交易完全相同！这是个问题！")
                    else:
                        report.append(f"✅ {s1} 与 {s2} 交易有差异，这是正常的")

        if all_same:
            report.append("\n✅ 所有策略交易都有差异，没有发现重复策略问题！")

        return "\n".join(report)

# ============= 主函数 =============

def main(strategies_to_run: List[str] = None):
    print("="*80)
    print("Walk-Forward 参数优化 - 修复版 (使用真实策略)")
    print("="*80)

    if strategies_to_run is None:
        strategies_to_run = list(STRATEGY_MAPPING.keys())

    print(f"\n策略列表 ({len(strategies_to_run)}):")
    for i, strategy in enumerate(strategies_to_run, 1):
        print(f"  {i:2d}. {strategy}")

    print(f"\n数据: BTCUSDT 真实历史数据 (1小时K线)")
    print(f"时间划分: 2022优化 → 2023验证 → 2024测试")

    runner = WalkForwardRunner(enable_gpu=False, resample="1h")

    start_time = time.time()
    completed = 0

    for strategy_id in strategies_to_run:
        try:
            strategy_start = time.time()
            print(f"\n[{completed+1}/{len(strategies_to_run)}] 正在运行: {strategy_id}...")
            result = runner.run_walk_forward(
                strategy_id=strategy_id,
                optimize_year=2022,
                validation_year=2023,
                test_year=2024,
            )
            strategy_elapsed = time.time() - strategy_start
            if result:
                print(f"  完成: {strategy_id} (Test Sharpe: {result.test_sharpe:.4f}, {strategy_elapsed:.1f}秒)")
            else:
                print(f"  失败: {strategy_id}")
            completed += 1
        except Exception as e:
            logger.error(f"Failed to run walk-forward for {strategy_id}: {e}")
            import traceback
            traceback.print_exc()

    report = runner.generate_report()
    print(report)

    critical_strategies = ["long_liquidation_bounce", "short_squeeze", "volatility_expansion"]
    diff_report = runner.check_strategy_differences(critical_strategies)
    print(diff_report)

    runner.save_results("walkforward_results_fixed.json", "trades")

    total_elapsed = time.time() - start_time
    print("\n" + "="*80)
    print(f"Walk-Forward 完成! 总用时: {total_elapsed:.1f}秒")
    print("="*80)

if __name__ == "__main__":
    # 默认只运行3个关键策略进行验证
    main(["long_liquidation_bounce", "short_squeeze", "volatility_expansion"])
