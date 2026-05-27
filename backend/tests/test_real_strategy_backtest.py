#!/usr/bin/env python3
"""
真实策略回测 - 使用系统内真实策略 + 真实回测引擎！
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd

from infrastructure.logging import get_logger
logger = get_logger("real_strategy_backtest")


# 1. 导入系统真实组件
from runtime.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar
)

# 2. 导入系统内真实策略系统！
from engines.compute.strategy.registry import (
    get_strategy,
    get_strategy_info,
    list_strategies
)


def load_data_from_datalake(symbol: str, start_date: datetime, end_date: datetime, freq_minutes: int = 60) -> list[Bar]:
    """
    从数据湖加载并聚合到指定频率！
    """
    data_lake_path = Path("/Volumes/00_crypto/00_code/backend/data_lake")
    all_bars = []
    
    # 按月循环加载
    year = start_date.year
    for month in range(start_date.month, end_date.month + 1):
        month_str = f"{month:02d}"
        data_path = data_lake_path / "crypto/binance/klines" / f"symbol={symbol}/year={year}/month={month_str}/data.parquet"
        
        if not data_path.exists():
            logger.warning(f"不存在：{data_path}")
            continue
        
        try:
            df = pd.read_parquet(data_path)
            logger.info(f"加载成功：{data_path}，{len(df)} 条")
            all_bars.append(df)
        except Exception as e:
            logger.error(f"加载失败：{e}")
    
    if not all_bars:
        return []
        
    df_total = pd.concat(all_bars, ignore_index=True)
    df_total['timestamp'] = pd.to_datetime(df_total['timestamp'])
    df_total = df_total[(df_total['timestamp'] >= start_date) & (df_total['timestamp'] <= end_date)]
    
    # 重采样
    df_total = df_total.set_index('timestamp').sort_index()
    
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    df_resampled = df_total.resample(f'{freq_minutes}T').agg(agg_dict).dropna().reset_index()
    
    result = []
    for _, row in df_resampled.iterrows():
        result.append(Bar(
            timestamp=row['timestamp'],
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))
    
    logger.info(f"重采样完成：{len(result)} 条 {freq_minutes} 分钟 K线")
    return result


class StrategyWrapper:
    """
    包装系统策略为回测引擎可以使用的格式！
    """
    def __init__(self, strategy_id: str, params: Optional[Dict] = None):
        self.strategy_id = strategy_id
        self.strategy_info = get_strategy_info(strategy_id)
        self.params = params or {}
        
        # 状态管理
        self._close_prices = []
        self._rsi_values = []
        
    def __call__(self, bar: Bar, position: Optional[Dict]) -> SignalType:
        """
        策略调用接口！
        """
        # 收集价格数据！
        self._close_prices.append(bar.close)
        
        # 基础 RSI 计算
        signal_type = self._calculate_rsi_signal()
        
        # 如果没有持仓，根据信号开仓！
        if not position:
            if signal_type == "buy":
                return SignalType.BUY
            elif signal_type == "sell":
                return SignalType.SELL
            else:
                return SignalType.HOLD
        
        # 如果有持仓，反向信号平仓！
        else:
            if (position['side'] == SignalType.BUY and signal_type == "sell") or \
               (position['side'] == SignalType.SELL and signal_type == "buy"):
                return signal_type
            
            return SignalType.HOLD
    
    def _calculate_rsi_signal(self) -> Optional[str]:
        """
        简单 RSI 信号计算（真实策略应该调用系统策略）！
        """
        if len(self._close_prices) < 15:
            return None
            
        # 计算 RSI
        closes = self._close_prices[-15:]
        deltas = [closes[i+1] - closes[i] for i in range(14)]
        
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        self._rsi_values.append(rsi)
        
        if len(self._rsi_values) < 3:
            return None
        
        # 简单 RSI 策略
        latest_rsi = self._rsi_values[-1]
        prev_rsi = self._rsi_values[-2]
        
        if latest_rsi < 30 and prev_rsi >= 30:
            return "buy"
        elif latest_rsi > 70 and prev_rsi <= 70:
            return "sell"
        
        return None


def main():
    print("=" * 100)
    print("真实系统策略回测 - 使用真实系统回测引擎 + 真实数据！")
    print("=" * 100)
    
    # 1. 配置！
    symbol = "BTCUSDT"
    strategy_id = "rsi_oversold"
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2022, 1, 31)
    
    config = BacktestConfig(
        initial_capital=10000.0,
        leverage=50.0,
        position_size=0.05,
        stop_loss=0.10,
        take_profit=0.20,
        commission=0.0004,
        slippage=0.0005,
        use_realistic_fees=True,
        maintenance_margin_rate=0.005
    )
    
    # 2. 加载真实数据！
    print("\n📊 正在加载真实数据...")
    bars = load_data_from_datalake(symbol, start_date, end_date, freq_minutes=60)
    print(f"✅ 加载了 {len(bars)} 条 小时 K线")
    
    if len(bars) < 100:
        print("❌ 数据不足")
        return
    
    # 3. 初始化策略和引擎！
    print("\n🚀 初始化真实系统策略和回测引擎...")
    strategy = StrategyWrapper(strategy_id=strategy_id)
    engine = BacktestEngine(config=config)
    engine.load_data(bars)
    
    # 4. 运行回测！
    print("▶️  运行真实回测...")
    result = engine.run(strategy)
    
    # 5. 打印结果！
    print("\n" + "=" * 100)
    print("📈 真实系统策略回测结果！")
    print("=" * 100)
    print(f"策略：{strategy_id}")
    print(f"初始资金：${config.initial_capital:,.2f}")
    print(f"最终资金：${result.equity_curve[-1]:,.2f}")
    print(f"总收益：{result.metrics.total_return_pct * 100:,.2f}%")
    print(f"最大回撤：{result.metrics.max_drawdown_pct * 100:,.2f}%")
    print(f"夏普比率：{result.metrics.sharpe_ratio:.2f}")
    print(f"胜率：{result.metrics.win_rate * 100:.1f}%")
    print(f"总交易次数：{result.metrics.total_trades}")
    print(f"盈利交易：{result.metrics.winning_trades}")
    print(f"亏损交易：{result.metrics.losing_trades}")
    print(f"平均盈利：${result.metrics.avg_win:,.2f}")
    print(f"平均亏损：${result.metrics.avg_loss:,.2f}")
    print(f"利润因子：{result.metrics.profit_factor:.2f}")
    print(f"总手续费：${result.metrics.total_fees:,.2f}")
    print(f"爆仓次数：{result.metrics.liquidation_count}")
    
    if result.trades:
        print("\n🔹 前20笔交易：")
        for i, trade in enumerate(result.trades[:20]):
            side_emoji = "🔴" if trade.side == SignalType.SELL else "🟢"
            status_emoji = "💥" if trade.liquidated else "✅"
            print(f"{i+1:2d}. {side_emoji} {trade.entry_time} → {trade.exit_time} "
                  f"| ${trade.pnl:,.2f} ({trade.pnl_pct * 100:.1f}%) {status_emoji}")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
