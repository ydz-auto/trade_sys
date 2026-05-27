#!/usr/bin/env python3
"""
快速验证三个关键策略的区别
"""
import sys
import os
import time
import csv
from pathlib import Path

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from runtime.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
    Trade
)
from engines.compute.strategy.strategies import (
    LongLiquidationBounceStrategy,
    ShortSqueezeStrategy,
    VolatilityExpansionStrategy,
)

logger = get_logger("test_critical")


class StrategyAdapter:
    """适配旧策略接口到回测引擎的SignalType接口"""
    def __init__(self, strategy):
        self.strategy = strategy
        self._closes = []
        self._highs = []
        self._lows = []
        self._volumes = []

    def _build_data_dict(self, bar: Bar):
        return {
            "close_prices": self._closes.copy(),
            "high_prices": self._highs.copy(),
            "low_prices": self._lows.copy(),
            "volumes": self._volumes.copy(),
            "symbol": "BTCUSDT",
            "timestamp": bar.timestamp
        }

    def __call__(self, bar: Bar, position=None):
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


def load_data(year: int):
    DATA_LAKE_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"
    year_path = DATA_LAKE_PATH / f"year={year}"
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
                    import pandas as pd
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
    logger.info(f"Loaded {year} data: {len(bars)} bars")
    return bars


def run_backtest(strategy_class, strategy_id, bars):
    strategy = strategy_class(strategy_id=strategy_id)
    adapter = StrategyAdapter(strategy)

    config = BacktestConfig(
        initial_capital=10000.0,
        commission=0.0004,
        slippage=0.0005,
        position_size=0.1,
        stop_loss=0.10,
        take_profit=0.20,
        leverage=5.0,
        use_realistic_fees=True,
    )

    engine = BacktestEngine(config=config, enable_gpu=False)
    engine.load_data(bars)
    result = engine.run(adapter)
    return result


def save_trades(result, strategy_id):
    csv_path = Path("trades_" + strategy_id + ".csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "trade_index", "entry_time", "exit_time", "side", "entry_price",
            "exit_price", "quantity", "pnl", "pnl_pct"
        ])

        for i, trade in enumerate(result.trades):
            writer.writerow([
                i,
                trade.entry_time,
                trade.exit_time,
                trade.side,
                trade.entry_price,
                trade.exit_price,
                trade.quantity,
                trade.pnl,
                trade.pnl_pct
            ])

    print(f"✅ Trades saved to {csv_path}")
    return result.trades


def compare_strategies():
    print("="*80)
    print("三个关键策略验证")
    print("="*80)

    bars = load_data(2024)
    if not bars:
        print("❌ 无法加载数据")
        return

    strategies = {
        "long_liquidation_bounce": LongLiquidationBounceStrategy,
        "short_squeeze": ShortSqueezeStrategy,
        "volatility_expansion": VolatilityExpansionStrategy,
    }

    results = {}

    print("\n运行策略回测...")
    for strategy_name, strategy_class in strategies.items():
        print(f"\n正在运行: {strategy_name}...")
        result = run_backtest(strategy_class, strategy_name, bars[:1000])
        if result:
            results[strategy_name] = result
            print(f"  ✅ {strategy_name}:")
            print(f"    总交易: {result.metrics.total_trades}")
            print(f"    总收益: ${result.metrics.total_return:.2f}")
            print(f"    夏普比率: {result.metrics.sharpe_ratio:.4f}")
            print(f"    最大回撤: {result.metrics.max_drawdown_pct:.2%}")
            save_trades(result, strategy_name)

    print("\n" + "="*80)
    print("比较策略交易差异")
    print("="*80)

    strategy_names = list(strategies.keys())
    all_same = True
    for i in range(len(strategy_names)):
        for j in range(i+1, len(strategy_names)):
            s1 = strategy_names[i]
            s2 = strategy_names[j]
            if s1 not in results or s2 not in results:
                continue

            trades1 = results[s1].trades
            trades2 = results[s2].trades

            if len(trades1) != len(trades2):
                all_same = False
                print(f"❌ {s1} 与 {s2} 交易数量不同: {len(trades1)} vs {len(trades2)}")
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
                    print(f"❌ {s1} 与 {s2} 前10笔交易完全相同！")
                else:
                    print(f"✅ {s1} 与 {s2} 交易有差异，正常！")

    if all_same:
        print("\n✅ 所有策略交易都有差异，没有重复策略问题！")

    print("\n" + "="*80)
    print("验证完成")
    print("="*80)


if __name__ == "__main__":
    compare_strategies()
