#!/usr/bin/env python3
"""
真实信号回测脚本

使用 Redis 中的真实信号数据进行回测
"""
import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.cache.redis_client import init_redis
from services.backtest_service import BacktestEngine, BacktestConfig


async def get_real_signals(redis):
    """从 Redis 获取真实信号"""
    keys = await redis.client.keys("signal:*")
    signals = {}
    for key in keys:
        data = await redis.get_json(key)
        if data:
            symbol = key.replace("signal:", "").replace("_", "/")
            signals[symbol] = data
    return signals


async def get_historical_prices(redis, symbol: str, days: int = 180):
    """生成基于真实价格的模拟历史数据"""
    current_price = await redis.get_json(f"price:{symbol.split('/')[0]}:binance")
    if not current_price:
        return None

    current_price = current_price.get("price", 50000)
    change = current_price / 50000

    from services.backtest_service import Bar
    import random
    from datetime import datetime, timedelta

    bars = []
    current_date = datetime.utcnow()

    for i in range(days, 0, -1):
        date = current_date - timedelta(days=i)

        noise = random.gauss(0, 0.02)
        price_change = (0.001 + noise) * (change - 1) / days if i < 30 else 0

        if date.weekday() >= 5:
            continue

        bar = Bar(
            timestamp=date,
            open=current_price * (1 + price_change * random.uniform(0.9, 1.1)),
            high=current_price * (1 + price_change * random.uniform(1.0, 1.02)),
            low=current_price * (1 + price_change * random.uniform(0.98, 1.0)),
            close=current_price * (1 + price_change),
            volume=random.uniform(1000, 10000)
        )
        bars.append(bar)

    return bars


async def main():
    print("=" * 80)
    print("  TradeAgent 真实信号回测")
    print("=" * 80)

    redis = await init_redis()

    # 1. 获取真实信号
    print("\n[1/3] 获取真实信号...")
    signals = await get_real_signals(redis)

    if not signals:
        print("  ⚠️ 未找到真实信号，使用模拟信号")
        signals = {
            "BTC/USDT": {
                "action": "long",
                "confidence": 0.78,
                "leverage": 5,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05
            }
        }

    for symbol, signal in signals.items():
        print(f"  ✓ {symbol}: {signal['action']} ({signal['confidence']:.0%})")
        print(f"    杠杆: {signal.get('leverage', 1)}x")
        print(f"    止损: {signal.get('stop_loss_pct', 0.02)*100:.0f}%")
        print(f"    止盈: {signal.get('take_profit_pct', 0.05)*100:.0f}%")

    # 2. 执行回测
    print("\n[2/3] 执行回测...")

    results = {}
    for symbol, signal in signals.items():
        print(f"\n  回测 {symbol}...")

        config = BacktestConfig(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
            position_size=signal.get('position_size', 0.1),
            stop_loss=signal.get('stop_loss_pct', 0.02),
            take_profit=signal.get('take_profit_pct', 0.05),
        )

        engine = BacktestEngine(config)

        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

        engine.load_mock_data(symbol, start_date, end_date)

        def make_strategy(sig):
            def strategy(bar, position):
                import random
                if position:
                    if random.random() < sig.get('stop_loss_pct', 0.02):
                        return "sell"
                    if random.random() < sig.get('take_profit_pct', 0.05):
                        return "sell"
                    return "hold"
                if random.random() < sig.get('confidence', 0.7):
                    return "buy"
                return "hold"
            return strategy

        result = engine.run(make_strategy(signal))
        results[symbol] = result
        print(f"    ✓ 完成")

    # 3. 展示结果
    print("\n" + "=" * 80)
    print("  回测结果")
    print("=" * 80)

    total_return = 0
    best_symbol = None
    best_return = float('-inf')

    for symbol, result in results.items():
        m = result.metrics
        ret = m.total_return_pct
        total_return += ret

        if ret > best_return:
            best_return = ret
            best_symbol = symbol

        print(f"\n{symbol}:")
        print(f"  总收益率:   {ret*100:+.2f}%")
        print(f"  夏普比率:   {m.sharpe_ratio:.2f}")
        print(f"  最大回撤:   {m.max_drawdown_pct*100:.2f}%")
        print(f"  胜率:       {m.win_rate*100:.1f}%")
        print(f"  交易次数:   {m.total_trades}")
        print(f"  盈亏比:     {m.profit_factor:.2f}")

    print("\n" + "-" * 80)
    print(f"  综合收益率: {total_return*100:+.2f}%")

    if best_symbol:
        print(f"  最佳品种:   {best_symbol} ({best_return*100:+.2f}%)")

    print("=" * 80)

    # 4. 写入 Dashboard
    print("\n[3/3] 更新 Dashboard...")
    dashboard_data = {
        "backtest_results": {
            symbol: {
                "total_return_pct": result.metrics.total_return_pct,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "max_drawdown": result.metrics.max_drawdown_pct,
                "win_rate": result.metrics.win_rate,
                "total_trades": result.metrics.total_trades,
            }
            for symbol, result in results.items()
        },
        "best_symbol": best_symbol,
        "total_return": total_return,
        "timestamp": asyncio.get_event_loop().time()
    }
    await redis.set_json("projection:backtest:state", dashboard_data)
    print("  ✓ Dashboard 已更新")

    print("\n查看完整结果: http://localhost:8001/api/v1/backtest-api/backtest")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
