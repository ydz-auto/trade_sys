#!/usr/bin/env python3
"""
Walk-Forward 参数优化脚本 - 使用 BacktestEngine

使用真实 BTCUSDT 历史数据运行 Walk-Forward 参数优化：
- 2022 优化 → 2023 验证 → 2024 测试

策略：
- RSI
- MACD
- RSI+MA

生成标准回测报告：
- Sharpe Ratio
- Profit Factor
- Win Rate
- Max Drawdown
- Overfitting 指标
"""
import sys
import os

# 添加后端路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from itertools import product
import json

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from runtimes.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
)

logger = get_logger("walk_forward")


@dataclass
class WalkForwardResult:
    """Walk-Forward 结果"""
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


class StrategyWrapper:
    """策略包装器 - 统一不同策略"""

    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.params = params
        self._closes = []
        self._rsi_values = []
        self._macd_line = []
        self._signal_line = []
        self._histogram = []
        self._position = None  # 'long', 'short', None
        self._entry_price = 0.0

    def calculate_rsi(self, prices: List[float], period: int = 14):
        """计算 RSI"""
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

    def calculate_ema(self, prices: List[float], period: int):
        """计算 EMA"""
        if len(prices) < period:
            return 0.0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def calculate_macd(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        """计算 MACD"""
        if len(prices) < slow_period + signal_period:
            return 0.0, 0.0, 0.0

        ema_fast = self.calculate_ema(prices, fast_period)
        ema_slow = self.calculate_ema(prices, slow_period)
        macd_line = ema_fast - ema_slow

        self._macd_line.append(macd_line)
        if len(self._macd_line) >= signal_period:
            signal_line = self.calculate_ema(self._macd_line[-signal_period:], signal_period)
        else:
            signal_line = 0.0
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def __call__(self, bar: Bar, position=None) -> SignalType:
        """生成交易信号"""
        self._closes.append(bar.close)
        if len(self._closes) > 200:
            self._closes = self._closes[-200:]

        if self.strategy_id == "rsi":
            period = self.params.get("period", 14)
            oversold = self.params.get("oversold", 30)
            overbought = self.params.get("overbought", 70)

            rsi = self.calculate_rsi(self._closes, period)
            self._rsi_values.append(rsi)
            if len(self._rsi_values) < 2:
                return SignalType.HOLD

            prev_rsi = self._rsi_values[-2]

            if self._position is None:
                if rsi <= oversold and prev_rsi > oversold:
                    self._position = "long"
                    self._entry_price = bar.close
                    return SignalType.BUY
                elif rsi >= overbought and prev_rsi < overbought:
                    self._position = "short"
                    self._entry_price = bar.close
                    return SignalType.SELL
            elif self._position == "long":
                if rsi >= overbought and prev_rsi < overbought:
                    self._position = None
                    return SignalType.SELL
            elif self._position == "short":
                if rsi <= oversold and prev_rsi > oversold:
                    self._position = None
                    return SignalType.BUY

        elif self.strategy_id == "macd":
            fast_period = self.params.get("fast_period", 12)
            slow_period = self.params.get("slow_period", 26)
            signal_period = self.params.get("signal_period", 9)

            macd_line, signal_line, histogram = self.calculate_macd(
                self._closes,
                fast_period, slow_period, signal_period
            )

            self._signal_line.append(signal_line)
            if len(self._signal_line) < 2:
                return SignalType.HOLD

            prev_macd = self._macd_line[-2] if len(self._macd_line) >= 2 else 0
            prev_signal = self._signal_line[-2]

            if self._position is None:
                if prev_macd <= prev_signal and macd_line > signal_line:
                    self._position = "long"
                    self._entry_price = bar.close
                    return SignalType.BUY
                elif prev_macd >= prev_signal and macd_line < signal_line:
                    self._position = "short"
                    self._entry_price = bar.close
                    return SignalType.SELL
            elif self._position == "long":
                if prev_macd >= prev_signal and macd_line < signal_line:
                    self._position = None
                    return SignalType.SELL
            elif self._position == "short":
                if prev_macd <= prev_signal and macd_line > signal_line:
                    self._position = None
                    return SignalType.BUY

        return SignalType.HOLD


class WalkForwardRunner:
    """Walk-Forward 参数优化运行器"""

    DATA_LAKE_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"

    def __init__(self, enable_gpu: bool = True):
        self._results: List[WalkForwardResult] = []
        self._all_data: Dict[int, List[Bar]] = {}
        self._enable_gpu = enable_gpu

    def load_year_data(self, year: int) -> List[Bar]:
        """加载指定年份的真实数据"""
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

    def get_year_time_range(self, year: int) -> Tuple[datetime, datetime]:
        """获取年份的时间范围"""
        tz = timezone.utc
        start_dt = datetime(year, 1, 1, tzinfo=tz)
        end_dt = datetime(year + 1, 1, 1, tzinfo=tz)
        return start_dt, end_dt

    def run_single_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        year: int,
        initial_capital: float = 10000.0,
        config_overrides: Optional[Dict[str, Any]] = None,
    ):
        """运行单次回测"""
        start_dt, end_dt = self.get_year_time_range(year)

        bars = self.load_year_data(year)
        if not bars:
            logger.warning(f"No data for year {year}")
            return None

        filtered_bars = [
            bar for bar in bars
            if start_dt <= bar.timestamp < end_dt
        ]
        if not filtered_bars:
            logger.warning(f"No data in range for year {year}")
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
        if config_overrides:
            for key, value in config_overrides.items():
                setattr(config, key, value)

        engine = BacktestEngine(config=config, enable_gpu=self._enable_gpu)
        engine.load_data(filtered_bars)

        wrapper = StrategyWrapper(strategy_id, params)
        result = engine.run(wrapper)

        return result

    def generate_param_grid(self, strategy_id: str) -> Dict[str, List[Any]]:
        """生成参数网格"""
        if strategy_id == "rsi":
            return {
                "period": [7, 14, 21],
                "oversold": [20, 25, 30, 35],
                "overbought": [65, 70, 75, 80],
            }
        elif strategy_id == "macd":
            return {
                "fast_period": [8, 12, 16],
                "slow_period": [20, 26, 32],
                "signal_period": [7, 9, 11],
            }
        else:
            return {}

    def expand_params(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """展开参数网格"""
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in product(*values)]

    def optimize_params(
        self,
        strategy_id: str,
        optimize_year: int,
        symbol: str = "BTCUSDT",
    ):
        """在优化年份搜索最佳参数"""
        param_grid = self.generate_param_grid(strategy_id)
        param_combinations = self.expand_params(param_grid)

        logger.info(
            f"Optimizing {strategy_id} on {optimize_year} "
            f"({len(param_combinations)} combinations)"
        )

        best_params = None
        best_sharpe = -float('inf')
        best_result = None

        for i, params in enumerate(param_combinations):
            logger.info(f"  Testing {i+1}/{len(param_combinations)}: params={params}")
            result = self.run_single_backtest(symbol, strategy_id, params, optimize_year)
            if result is not None:
                sharpe = result.metrics.sharpe_ratio
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
                    best_result = result
                    logger.info(
                        f"    New best: sharpe={sharpe:.4f}, return={result.metrics.total_return_pct:.2%}"
                    )

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
        symbol: str = "BTCUSDT",
    ) -> WalkForwardResult:
        """运行完整的 Walk-Forward"""
        logger.info(
            f"\n{'='*60}\n"
            f"Walk-Forward: {strategy_id}\n"
            f"  Optimize: {optimize_year}\n"
            f"  Validation: {validation_year}\n"
            f"  Test: {test_year}\n"
            f"{'='*60}"
        )

        best_params, optimize_result = self.optimize_params(
            strategy_id=strategy_id,
            optimize_year=optimize_year,
            symbol=symbol,
        )

        logger.info(f"\nValidating on {validation_year}...")
        validation_result = self.run_single_backtest(
            symbol=symbol,
            strategy_id=strategy_id,
            params=best_params,
            year=validation_year,
        )

        logger.info(f"\nTesting on {test_year}...")
        test_result = self.run_single_backtest(
            symbol=symbol,
            strategy_id=strategy_id,
            params=best_params,
            year=test_year,
        )

        if optimize_result is None or validation_result is None or test_result is None:
            logger.error("One of the backtests failed")
            return None

        overfitting_score = self._compute_overfitting(
            optimize_result.metrics,
            validation_result.metrics,
            test_result.metrics,
        )

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
            max_drawdown=test_result.metrics.max_drawdown,
            win_rate=test_result.metrics.win_rate,
            profit_factor=test_result.metrics.profit_factor,
            overfitting_score=overfitting_score,
        )

        self._results.append(result)
        return result

    def _compute_overfitting(
        self,
        optimize_metrics,
        validation_metrics,
        test_metrics,
    ) -> float:
        """计算过拟合分数"""
        if optimize_metrics.sharpe_ratio <= 0:
            return 0.0

        decay_opt_to_test = (optimize_metrics.sharpe_ratio - test_metrics.sharpe_ratio) / optimize_metrics.sharpe_ratio

        if validation_metrics.sharpe_ratio > 0:
            decay_val_to_test = (validation_metrics.sharpe_ratio - test_metrics.sharpe_ratio) / validation_metrics.sharpe_ratio
            return max(decay_opt_to_test, decay_val_to_test)

        return decay_opt_to_test

    def generate_report(self) -> str:
        """生成标准回测报告"""
        report = []
        report.append("\n" + "=" * 80)
        report.append("Walk-Forward 参数优化报告 (GPU加速)")
        report.append("=" * 80)
        report.append(f"\n数据: BTCUSDT 真实历史数据")
        report.append(f"优化集: 2022")
        report.append(f"验证集: 2023")
        report.append(f"测试集: 2024")
        report.append("\n" + "-" * 80)

        for result in self._results:
            report.append(f"\n策略: {result.strategy_id}")
            report.append(f"  最佳参数: {result.best_params}")
            report.append(f"\n  优化集 ({result.optimize_year}):")
            report.append(f"    Sharpe Ratio: {result.optimize_sharpe:.4f}")
            report.append(f"    Total Return: ${result.optimize_return:.2f}")
            report.append(f"    Trades: {result.optimize_trades}")
            report.append(f"\n  验证集 ({result.validation_year}):")
            report.append(f"    Sharpe Ratio: {result.validation_sharpe:.4f}")
            report.append(f"    Total Return: ${result.validation_return:.2f}")
            report.append(f"    Trades: {result.validation_trades}")
            report.append(f"\n  测试集 ({result.test_year}):")
            report.append(f"    Sharpe Ratio: {result.test_sharpe:.4f}")
            report.append(f"    Total Return: ${result.test_return:.2f}")
            report.append(f"    Max Drawdown: {result.max_drawdown:.2%}")
            report.append(f"    Win Rate: {result.win_rate:.2%}")
            report.append(f"    Profit Factor: {result.profit_factor:.4f}")
            report.append(f"    Trades: {result.test_trades}")
            report.append(f"\n  过拟合指标:")
            report.append(f"    Sharpe 衰减: {result.overfitting_score:.2%}")

            if result.overfitting_score > 0.5:
                report.append(f"    ⚠️  严重过拟合！不建议上 paper trading")
            elif result.overfitting_score > 0.3:
                report.append(f"    ⚠️  中度过拟合，需要谨慎")
            else:
                report.append(f"    ✅ 过拟合风险较低，可以考虑 paper trading")

            report.append("-" * 80)

        report.append("\n" + "=" * 80)
        report.append("总结")
        report.append("=" * 80)

        for result in self._results:
            status = "✅ PASS" if result.overfitting_score <= 0.3 else "⚠️ WARN"
            report.append(
                f"{result.strategy_id}: "
                f"Test Sharpe={result.test_sharpe:.4f}, "
                f"Overfitting={result.overfitting_score:.2%}, "
                f"{status}"
            )

        return "\n".join(report)

    def save_results(self, output_path: str = "walk_forward_results.json"):
        """保存结果到 JSON"""
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
                "max_drawdown": r.max_drawdown,
                "win_rate": r.win_rate,
                "profit_factor": r.profit_factor,
                "overfitting_score": r.overfitting_score,
            })

        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        logger.info(f"Results saved to {output_path}")


def main():
    """主函数"""
    print("=" * 80)
    print("Walk-Forward 参数优化 (GPU加速)")
    print("=" * 80)
    print("\n使用真实 BTCUSDT 历史数据")
    print("时间划分: 2022优化 → 2023验证 → 2024测试")
    print("策略: RSI, MACD")

    runner = WalkForwardRunner(enable_gpu=True)

    strategies = ["rsi", "macd"]

    for strategy_id in strategies:
        try:
            result = runner.run_walk_forward(
                strategy_id=strategy_id,
                optimize_year=2022,
                validation_year=2023,
                test_year=2024,
                symbol="BTCUSDT",
            )
        except Exception as e:
            logger.error(f"Failed to run walk-forward for {strategy_id}: {e}")
            import traceback
            traceback.print_exc()

    report = runner.generate_report()
    print(report)

    runner.save_results("walk_forward_results.json")

    print("\n" + "=" * 80)
    print("Walk-Forward 完成")
    print("=" * 80)


if __name__ == "__main__":
    main()