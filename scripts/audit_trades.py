#!/usr/bin/env python3
"""
交易级审计脚本
分析回测结果的问题
"""
import sys
import os
import json
from pathlib import Path

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from runtime.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, Bar
from datetime import datetime
import pandas as pd

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe

logger = get_logger("audit_trades")

# 复制策略类（从之前的脚本）
class BaseStrategyImpl:
    def __init__(self, strategy_id: str, params: dict):
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
    
    def calculate(self, bar: Bar):
        raise NotImplementedError
    
    def __call__(self, bar: Bar, position=None):
        self.on_bar(bar)
        return self.calculate(bar)
    
    def calculate_ema(self, prices: list, period: int) -> float:
        if len(prices) < period:
            return 0.0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        return ema
    
    def calculate_rsi(self, prices: list, period: int = 14) -> float:
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


class GenericTrendStrategy(BaseStrategyImpl):
    def calculate(self, bar: Bar):
        from runtime.replay_runtime.backtest_engine import SignalType
        lookback = self.params.get("lookback", 24)
        threshold = self.params.get("threshold", 0.01)
        
        if len(self._closes) < lookback:
            return SignalType.HOLD
        
        lookback_return = (bar.close - self._closes[-lookback]) / self._closes[-lookback]
        signal = SignalType.HOLD
        
        if self._position is None:
            if lookback_return > threshold:
                self._position = "long"
                signal = SignalType.BUY
            elif lookback_return < -threshold:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if lookback_return < -threshold/2:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if lookback_return > threshold/2:
                self._position = None
                signal = SignalType.BUY
        return signal


class MomentumStrategy(BaseStrategyImpl):
    def calculate(self, bar: Bar):
        from runtime.replay_runtime.backtest_engine import SignalType
        period = self.params.get("period", 10)
        threshold = self.params.get("threshold", 0.02)
        
        if len(self._closes) < period:
            return SignalType.HOLD
        
        momentum = (bar.close - self._closes[-period]) / self._closes[-period]
        signal = SignalType.HOLD
        
        if self._position is None:
            if momentum > threshold:
                self._position = "long"
                signal = SignalType.BUY
            elif momentum < -threshold:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if momentum < -threshold/2:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if momentum > threshold/2:
                self._position = None
                signal = SignalType.BUY
        return signal


STRATEGY_IMPLEMENTATIONS = {
    "long_liquidation_bounce": {
        "class": GenericTrendStrategy,
        "param_grid": {"lookback": [12], "threshold": [0.02]}
    },
    "short_squeeze": {
        "class": GenericTrendStrategy,
        "param_grid": {"lookback": [12], "threshold": [0.02]}
    },
    "volatility_expansion": {
        "class": GenericTrendStrategy,
        "param_grid": {"lookback": [12], "threshold": [0.02]}
    },
    "momentum": {
        "class": MomentumStrategy,
        "param_grid": {"period": [10], "threshold": [0.02]}
    },
}


DATA_LAKE_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"


def load_year_data(year: int) -> list[Bar]:
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


def audit_strategy(strategy_id: str, params: dict, bars: list):
    from runtime.replay_runtime.backtest_engine import SignalType
    
    print(f"\n{'='*80}")
    print(f"审计策略: {strategy_id}")
    print(f"参数: {params}")
    print(f"{'='*80}")
    
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
    
    strategy_config = STRATEGY_IMPLEMENTATIONS.get(strategy_id)
    strategy_impl = strategy_config["class"](strategy_id, params)
    
    result = engine.run(strategy_impl)
    
    print(f"\n回测结果:")
    print(f"  总收益: ${result.metrics.total_return:.2f}")
    print(f"  夏普比率: {result.metrics.sharpe_ratio:.4f}")
    print(f"  最大回撤: {result.metrics.max_drawdown_pct:.2%}")
    print(f"  总交易数: {result.metrics.total_trades}")
    print(f"  胜率: {result.metrics.win_rate:.2%}")
    print(f"  盈亏比: {result.metrics.profit_factor:.4f}")
    
    print(f"\n前30笔交易详情:")
    print("-"*160)
    print(f"{'#':4s} {'进场时间':<20s} {'出场时间':<20s} {'方向':6s} {'进场价':>10s} {'出场价':>10s} {'数量':>10s} {'名义价值':>12s} {'杠杆':>5s} {'进场费':>8s} {'出场费':>8s} {'资金费':>8s} {'PNL':>12s} {'PNL%':>8s} {'强平':4s}")
    print("-"*160)
    
    for i, trade in enumerate(result.trades[:30]):
        side = "LONG" if trade.side == SignalType.BUY else "SHORT"
        notional = trade.entry_price * trade.quantity
        print(f"{i+1:4d} {trade.entry_time.strftime('%Y-%m-%d %H:%M'):<20s} {trade.exit_time.strftime('%Y-%m-%d %H:%M'):<20s} {side:6s} {trade.entry_price:10.2f} {trade.exit_price:10.2f} {trade.quantity:10.3f} {notional:12.2f} {trade.leverage:5.1f} {trade.entry_fee:8.2f} {trade.exit_fee:8.2f} {trade.funding_fee:8.2f} {trade.pnl:12.2f} {trade.pnl_pct:8.2%} {'是' if trade.liquidated else '否':4s}")
    
    if len(result.trades) > 30:
        print(f"... 还有 {len(result.trades) - 30} 笔交易")
    
    return result


def main():
    print("="*80)
    print("交易级审计")
    print("="*80)
    
    # 加载2024年数据
    bars = load_year_data(2024)
    if not bars:
        print("无法加载数据")
        return
    
    # 测试几个策略
    strategies_to_test = [
        "long_liquidation_bounce",
        "short_squeeze", 
        "volatility_expansion",
        "momentum"
    ]
    
    results = {}
    for strategy_id in strategies_to_test:
        params = STRATEGY_IMPLEMENTATIONS[strategy_id]["param_grid"]
        # 取第一组参数
        param_values = {k: v[0] for k, v in params.items()}
        results[strategy_id] = audit_strategy(strategy_id, param_values, bars)
    
    # 比较结果
    print(f"\n{'='*80}")
    print("策略对比总结")
    print(f"{'='*80}")
    
    print(f"\n{'策略ID':<30s} {'交易数':>8s} {'夏普':>10s} {'收益':>12s} {'最大回撤':>12s}")
    print("-"*80)
    
    for strategy_id, result in results.items():
        print(f"{strategy_id:<30s} {result.metrics.total_trades:8d} {result.metrics.sharpe_ratio:10.4f} ${result.metrics.total_return:11.2f} {result.metrics.max_drawdown_pct:12.2%}")
    
    # 检查前几笔交易是否完全相同
    print(f"\n{'='*80}")
    print("检查交易是否重复")
    print(f"{'='*80}")
    
    strategy_trades = {}
    for strategy_id, result in results.items():
        strategy_trades[strategy_id] = [
            (t.entry_time, t.exit_time, t.entry_price, t.exit_price, t.quantity, t.pnl)
            for t in result.trades[:10]
        ]
    
    # 比较 long_liquidation_bounce vs short_squeeze
    if "long_liquidation_bounce" in strategy_trades and "short_squeeze" in strategy_trades:
        trades1 = strategy_trades["long_liquidation_bounce"]
        trades2 = strategy_trades["short_squeeze"]
        
        all_same = True
        for i, (t1, t2) in enumerate(zip(trades1, trades2)):
            if t1 != t2:
                all_same = False
                print(f"❌ 交易 #{i+1} 不同")
                print(f"   long_liquidation_bounce: {t1}")
                print(f"   short_squeeze: {t2}")
                break
        
        if all_same and len(trades1) == len(trades2):
            print("✅ 前10笔交易完全相同！这证实了问题：多个策略使用相同的逻辑！")
    
    print(f"\n审计完成！")


if __name__ == "__main__":
    main()
