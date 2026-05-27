#!/usr/bin/env python3
"""
使用系统真实能力的回测 - 调用 system internal Runtime & Engine
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from infrastructure.logging import get_logger
logger = get_logger("real_backtest")


# 1. 导入系统内真实组件
from runtime.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar
)


def load_data_from_datalake(symbol: str, start_date: datetime, end_date: datetime) -> list[Bar]:
    """
    从数据湖加载真实数据
    """
    import pandas as pd
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
            
            # 转换为 Bar 对象
            for _, row in df.iterrows():
                ts = pd.to_datetime(row['timestamp'])
                if ts < start_date or ts > end_date:
                    continue
                    
                all_bars.append(Bar(
                    timestamp=ts,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                ))
                
        except Exception as e:
            logger.error(f"加载失败：{e}")
            
    # 按时间排序
    all_bars.sort(key=lambda x: x.timestamp)
    return all_bars


def simple_rsi_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """
    简单 RSI 策略（测试用）
    这个只是一个示例，真正的策略在 engines/compute/strategy/registry.py 中
    """
    # 真实策略需要完整特征计算
    # 这里只是简单测试回测引擎
    # 实际应该调用系统内策略
    return SignalType.HOLD


def main():
    print("=" * 100)
    print("真实系统回测 - 使用 system internal BacktestEngine")
    print("=" * 100)
    
    # 配置
    symbol = "BTCUSDT"
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
    
    # 1. 加载数据
    print("\n📊 正在加载数据...")
    bars = load_data_from_datalake(symbol, start_date, end_date)
    print(f"✅ 加载了 {len(bars)} 条 K线")
    
    if len(bars) < 100:
        print("❌ 数据不足")
        return
    
    # 2. 初始化回测引擎
    print("\n🚀 初始化真实系统回测引擎...")
    engine = BacktestEngine(config=config)
    engine.load_data(bars)
    
    # 3. 运行回测
    print("▶️  运行回测...")
    result = engine.run(simple_rsi_strategy)
    
    # 4. 打印结果
    print("\n" + "=" * 100)
    print("📈 真实系统回测结果")
    print("=" * 100)
    print(f"初始资金：${config.initial_capital:,.2f}")
    print(f"最终资金：${result.equity_curve[-1]:,.2f}")
    print(f"总收益：{result.metrics.total_return_pct * 100:,.2f}%")
    print(f"最大回撤：{result.metrics.max_drawdown_pct * 100:,.2f}%")
    print(f"夏普比率：{result.metrics.sharpe_ratio:.2f}")
    print(f"胜率：{result.metrics.win_rate * 100:.1f}%")
    print(f"总交易次数：{result.metrics.total_trades}")
    print(f"盈利交易：{result.metrics.winning_trades}")
    print(f"亏损交易：{result.metrics.losing_trades}")
    print(f"利润因子：{result.metrics.profit_factor:.2f}")
    print(f"总手续费：${result.metrics.total_fees:,.2f}")
    print(f"爆仓次数：{result.metrics.liquidation_count}")
    
    if result.trades:
        print("\n🔹 前10笔交易：")
        for i, trade in enumerate(result.trades[:10]):
            side_emoji = "🔴" if trade.side == SignalType.SELL else "🟢"
            status_emoji = "💥" if trade.liquidated else "✅"
            print(f"{i+1:2d}. {side_emoji} {trade.entry_time} → {trade.exit_time} "
                  f"| ${trade.pnl:,.2f} ({trade.pnl_pct * 100:.1f}%) {status_emoji}")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
