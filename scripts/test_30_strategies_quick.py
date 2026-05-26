#!/usr/bin/env python3
"""
Quick test - run first 5 strategies with simplified params
"""
import sys
import os

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from itertools import product
import json
import numpy as np

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from runtimes.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
)

logger = get_logger("walk_forward_test")


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


class BaseStrategyImpl:
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.params = params
        self._closes = []
        self._highs = []
        self._lows = []
        self._volumes = []
        self._position = None
        self._entry_price = 0.0
    
    def on_bar(self, bar: Bar):
        self._closes.append(bar.close)
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._volumes.append(bar.volume)
        
        if len(self._closes) > 600:
            self._closes = self._closes[-600:]
            self._highs = self._highs[-600:]
            self._lows = self._lows[-600:]
            self._volumes = self._volumes[-600:]
    
    def calculate(self, bar: Bar) -> SignalType:
        raise NotImplementedError
    
    def __call__(self, bar: Bar, position=None) -> SignalType:
        self.on_bar(bar)
        return self.calculate(bar)
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return 0.0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        return ema
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        
        avg_gain = sum(gains[-period:]) / period if gains else 0.0
        avg_loss = sum(losses[-period:]) / period if losses else 0.0
        
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


class RSIOversoldStrategy(BaseStrategyImpl):
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
        self._rsi_prev = None
    
    def calculate(self, bar: Bar) -> SignalType:
        period = self.params.get("period", 14)
        oversold = self.params.get("oversold", 30)
        rsi = self.calculate_rsi(self._closes, period)
        signal = SignalType.HOLD
        
        if self._rsi_prev is not None:
            if self._position is None:
                if rsi <= oversold and self._rsi_prev > oversold:
                    self._position = "long"
                    signal = SignalType.BUY
            elif self._position == "long":
                if rsi >= 70 and self._rsi_prev < 70:
                    self._position = None
                    signal = SignalType.SELL
        self._rsi_prev = rsi
        return signal


class RSIOverboughtStrategy(BaseStrategyImpl):
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
        self._rsi_prev = None
    
    def calculate(self, bar: Bar) -> SignalType:
        period = self.params.get("period", 14)
        overbought = self.params.get("overbought", 70)
        rsi = self.calculate_rsi(self._closes, period)
        signal = SignalType.HOLD
        
        if self._rsi_prev is not None:
            if self._position is None:
                if rsi >= overbought and self._rsi_prev < overbought:
                    self._position = "short"
                    signal = SignalType.SELL
            elif self._position == "short":
                if rsi <= 30 and self._rsi_prev > 30:
                    self._position = None
                    signal = SignalType.BUY
        self._rsi_prev = rsi
        return signal


class MACDCrossStrategy(BaseStrategyImpl):
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
        self._macd_line = []
        self._signal_line = []
    
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 12)
        slow_period = self.params.get("slow_period", 26)
        signal_period = self.params.get("signal_period", 9)
        
        if len(self._closes) < slow_period + signal_period:
            return SignalType.HOLD
        
        ema_fast = self.calculate_ema(self._closes, fast_period)
        ema_slow = self.calculate_ema(self._closes, slow_period)
        macd_line = ema_fast - ema_slow
        
        self._macd_line.append(macd_line)
        if len(self._macd_line) >= signal_period:
            signal_line = self.calculate_ema(self._macd_line[-signal_period:], signal_period)
        else:
            signal_line = 0.0
        
        self._signal_line.append(signal_line)
        signal = SignalType.HOLD
        
        if len(self._signal_line) >= 2:
            prev_macd = self._macd_line[-2]
            prev_signal = self._signal_line[-2]
            
            if self._position is None:
                if prev_macd <= prev_signal and macd_line > signal_line:
                    self._position = "long"
                    signal = SignalType.BUY
                elif prev_macd >= prev_signal and macd_line < signal_line:
                    self._position = "short"
                    signal = SignalType.SELL
            elif self._position == "long":
                if prev_macd >= prev_signal and macd_line < signal_line:
                    self._position = None
                    signal = SignalType.SELL
            elif self._position == "short":
                if prev_macd <= prev_signal and macd_line > signal_line:
                    self._position = None
                    signal = SignalType.BUY
        return signal


class SMACrossStrategy(BaseStrategyImpl):
    def calculate_sma(self, period: int) -> float:
        if len(self._closes) < period:
            return 0.0
        return sum(self._closes[-period:]) / period
    
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 10)
        slow_period = self.params.get("slow_period", 50)
        
        sma_fast = self.calculate_sma(fast_period)
        sma_slow = self.calculate_sma(slow_period)
        
        if sma_fast == 0 or sma_slow == 0:
            return SignalType.HOLD
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if sma_fast > sma_slow:
                self._position = "long"
                signal = SignalType.BUY
            elif sma_fast < sma_slow:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if sma_fast < sma_slow:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if sma_fast > sma_slow:
                self._position = None
                signal = SignalType.BUY
        return signal


class EMACrossStrategy(BaseStrategyImpl):
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 10)
        slow_period = self.params.get("slow_period", 50)
        
        ema_fast = self.calculate_ema(self._closes, fast_period)
        ema_slow = self.calculate_ema(self._closes, slow_period)
        
        if ema_fast == 0 or ema_slow == 0:
            return SignalType.HOLD
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if ema_fast > ema_slow:
                self._position = "long"
                signal = SignalType.BUY
            elif ema_fast < ema_slow:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if ema_fast < ema_slow:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if ema_fast > ema_slow:
                self._position = None
                signal = SignalType.BUY
        return signal


STRATEGY_IMPLEMENTATIONS = {
    "rsi_oversold": {
        "class": RSIOversoldStrategy,
        "param_grid": {"period": [14], "oversold": [30]}
    },
    "rsi_overbought": {
        "class": RSIOverboughtStrategy,
        "param_grid": {"period": [14], "overbought": [70]}
    },
    "macd_cross": {
        "class": MACDCrossStrategy,
        "param_grid": {"fast_period": [12], "slow_period": [26], "signal_period": [9]}
    },
    "sma_cross": {
        "class": SMACrossStrategy,
        "param_grid": {"fast_period": [10], "slow_period": [50]}
    },
    "ema_cross": {
        "class": EMACrossStrategy,
        "param_grid": {"fast_period": [10], "slow_period": [50]}
    }
}

ALL_STRATEGIES = list(STRATEGY_IMPLEMENTATIONS.keys())


class WalkForwardRunner:
    DATA_LAKE_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"

    def __init__(self, enable_gpu: bool = True):
        self._results: List[WalkForwardResult] = []
        self._all_data: Dict[int, List[Bar]] = {}
        self._enable_gpu = enable_gpu

    def load_year_data(self, year: int) -> List[Bar]:
        if year in self._all_data:
            return self._all_data[year]

        year_path = self.DATA_LAKE_PATH / f"year={year}"
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
        self._all_data[year] = bars
        logger.info(f"Loaded {year} data: {len(bars)} bars")
        return bars

    def run_single_backtest(
        self,
        strategy_id: str,
        params: Dict[str, Any],
        year: int,
        initial_capital: float = 10000.0,
    ):
        strategy_config = STRATEGY_IMPLEMENTATIONS.get(strategy_id)
        if not strategy_config:
            return None
        
        bars = self.load_year_data(year)
        if not bars:
            return None
        
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
        
        strategy_impl = strategy_config["class"](strategy_id, params)
        result = engine.run(strategy_impl)
        
        return result

    def generate_param_grid(self, strategy_id: str) -> List[Dict[str, Any]]:
        strategy_config = STRATEGY_IMPLEMENTATIONS.get(strategy_id)
        if not strategy_config:
            return []
        
        param_grid = strategy_config["param_grid"]
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in product(*values)]

    def optimize_params(
        self,
        strategy_id: str,
        optimize_year: int,
    ):
        param_combinations = self.generate_param_grid(strategy_id)
        
        logger.info(
            f"Optimizing {strategy_id} on {optimize_year} "
            f"({len(param_combinations)} combinations)"
        )

        best_params = None
        best_sharpe = -float('inf')
        best_result = None

        for i, params in enumerate(param_combinations):
            result = self.run_single_backtest(strategy_id, params, optimize_year)
            if result is not None:
                sharpe = result.metrics.sharpe_ratio
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
                    best_result = result

        logger.info(
            f"Optimization complete: best_params={best_params}, "
            f"sharpe={best_sharpe:.4f}"
        )

        return best_params, best_result

    def run_walk_forward(
        self,
        strategy_id: str,
        optimize_year: int = 2022,
        validation_year: int = 2023,
        test_year: int = 2024,
    ) -> WalkForwardResult:
        logger.info(
            f"\n{'='*60}\n"
            f"Walk-Forward: {strategy_id}\n"
            f"{'='*60}"
        )

        best_params, optimize_result = self.optimize_params(
            strategy_id=strategy_id,
            optimize_year=optimize_year,
        )
        
        if best_params is None:
            logger.error(f"Failed to find good params for {strategy_id}")
            return None

        logger.info(f"Validating on {validation_year}...")
        validation_result = self.run_single_backtest(
            strategy_id=strategy_id,
            params=best_params,
            year=validation_year,
        )

        logger.info(f"Testing on {test_year}...")
        test_result = self.run_single_backtest(
            strategy_id=strategy_id,
            params=best_params,
            year=test_year,
        )

        if optimize_result is None or validation_result is None or test_result is None:
            logger.error("One of the backtests failed")
            return None

        decay_opt_to_test = 0.0
        if optimize_result.metrics.sharpe_ratio > 0:
            decay_opt_to_test = (optimize_result.metrics.sharpe_ratio - test_result.metrics.sharpe_ratio) / optimize_result.metrics.sharpe_ratio
        
        overfitting_score = decay_opt_to_test

        result = WalkForwardResult(
            strategy_id=strategy_id,
            optimize_year=optimize_year,
            validation_year=validation_year,
            test_year=test_year,
            best_params=best_params,
            optimize_sharpe=optimize_result.metrics.sharpe_ratio,
            validation_sharpe=validation_result.metrics.sharpe_ratio,
            test_sharpe=test_result.metrics.sharpe_ratio,
            optimize_trades=optimize_result.metrics.total_trades,
            validation_trades=validation_result.metrics.total_trades,
            test_trades=test_result.metrics.total_trades,
            optimize_return=optimize_result.metrics.total_return,
            validation_return=validation_result.metrics.total_return,
            test_return=test_result.metrics.total_return,
            max_drawdown=test_result.metrics.max_drawdown_pct,
            win_rate=test_result.metrics.win_rate,
            profit_factor=test_result.metrics.profit_factor,
            overfitting_score=overfitting_score,
        )

        self._results.append(result)
        return result

    def generate_report(self) -> str:
        report = []
        report.append("\n" + "="*80)
        report.append("快速测试报告 - 前5种策略")
        report.append("="*80)
        
        for result in self._results:
            report.append(f"\n策略: {result.strategy_id}")
            report.append(f"  最佳参数: {result.best_params}")
            report.append(f"  测试集 Sharpe: {result.test_sharpe:.4f} | Return: ${result.test_return:.2f} | Drawdown: {result.max_drawdown:.2%}")
            status = "✅ 过拟合风险低" if result.overfitting_score <= 0.3 else "⚠️  中度过拟合风险" if result.overfitting_score <= 0.5 else "❌ 严重过拟合风险"
            report.append(f"  过拟合指标: {result.overfitting_score:.2%} - {status}")
        
        report.append("\n" + "="*80)
        report.append("✅ 快速测试完成!")
        report.append("="*80)
        return "\n".join(report)


def main():
    print("="*80)
    print("快速测试 - 前5种策略")
    print("="*80)
    
    runner = WalkForwardRunner(enable_gpu=True)

    for strategy_id in ALL_STRATEGIES:
        try:
            result = runner.run_walk_forward(
                strategy_id=strategy_id,
                optimize_year=2022,
                validation_year=2023,
                test_year=2024,
            )
        except Exception as e:
            logger.error(f"Failed to run walk-forward for {strategy_id}: {e}")
            import traceback
            traceback.print_exc()

    report = runner.generate_report()
    print(report)


if __name__ == "__main__":
    main()
