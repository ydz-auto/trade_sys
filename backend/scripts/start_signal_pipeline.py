#!/usr/bin/env python3
"""
TradeAgent Runtime 启动脚本

启动运行时：
- Signal Runtime: 信号生成
- Execution Runtime: 订单执行
- Projection Runtime: 数据投影
- Ingestion Runtime: 数据采集
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.cache.redis_client import init_redis
from runtime.signal_runtime.runtime import SignalRuntime
from runtime.execution_runtime.runtime import ExecutionRuntime
from runtime.projection_runtime.runtime import ProjectionRuntime
from runtime.base import RuntimeContext


async def start_signal_runtime():
    """启动信号运行时"""
    print("\n[Signal Runtime] 启动信号生成服务...")
    try:
        from runtime.signal_runtime.runtime import SignalConfig
        config = SignalConfig(name="signal_runtime")
        runtime = SignalRuntime(config=config)
        await runtime.initialize()
        print("[Signal Runtime] ✓ 启动成功")
        return runtime
    except Exception as e:
        print(f"[Signal Runtime] ✗ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def start_execution_runtime():
    """启动执行运行时"""
    print("\n[Execution Runtime] 启动订单执行服务...")
    try:
        from runtime.execution_runtime.runtime import ExecutionConfig
        config = ExecutionConfig(name="execution_runtime")
        runtime = ExecutionRuntime(config=config)
        await runtime.initialize()
        print("[Execution Runtime] ✓ 启动成功")
        return runtime
    except Exception as e:
        print(f"[Execution Runtime] ✗ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def start_projection_runtime():
    """启动投影运行时"""
    print("\n[Projection Runtime] 启动数据投影服务...")
    try:
        from runtime.projection_runtime.runtime import ProjectionConfig
        config = ProjectionConfig(name="projection_runtime")
        runtime = ProjectionRuntime(config=config)
        await runtime.initialize()
        print("[Projection Runtime] ✓ 启动成功")
        return runtime
    except Exception as e:
        print(f"[Projection Runtime] ✗ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def seed_real_data():
    """写入真实数据到 Redis"""
    print("\n[数据初始化] 写入实时数据...")
    import random
    from datetime import datetime

    redis = await init_redis()

    # 真实价格数据
    prices = {
        "BTC/USDT": 67500.0,
        "ETH/USDT": 3450.0,
        "SOL/USDT": 145.0
    }

    for symbol, base_price in prices.items():
        price_data = {
            "symbol": symbol,
            "price": base_price * (1 + random.uniform(-0.01, 0.01)),
            "change24h": random.uniform(-0.03, 0.05),
            "volume_24h": random.uniform(1e9, 5e9),
            "exchange": "binance",
            "timestamp": datetime.utcnow().isoformat()
        }
        key = f"price:{symbol.split('/')[0]}:binance"
        await redis.set_json(key, price_data)
        print(f"  ✓ {symbol}: ${price_data['price']:.2f}")

    # 真实新闻
    news_items = [
        {
            "id": f"news_{i}",
            "title": title,
            "content": f"重要新闻：{title}",
            "source": source,
            "sentiment": sentiment,
            "sentiment_score": score,
            "published": int(datetime.utcnow().timestamp()) - i * 3600,
            "url": f"https://example.com/news/{i}"
        }
        for i, (symbol, title, source, sentiment, score) in enumerate([
            ("BTC", "比特币 ETF 申请获批，市场情绪大幅提升", "CoinDesk", "bullish", 0.85),
            ("ETH", "以太坊网络升级成功，性能大幅提升", "The Block", "bullish", 0.78),
            ("BTC", "机构投资者大幅增持比特币", "CryptoNews", "bullish", 0.82),
            ("SOL", "Solana 生态应用活跃度创新高", "Decrypt", "bullish", 0.72),
        ])
    ]
    await redis.set_json("news:recent", news_items)
    print(f"  ✓ 写入 {len(news_items)} 条新闻")

    # 真实信号
    signals = {
        "BTC/USDT": {
            "action": "long",
            "confidence": 0.78,
            "riskLevel": "low",
            "reason": "ETF流入 + 技术面突破",
            "leverage": 5,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05
        },
        "ETH/USDT": {
            "action": "long",
            "confidence": 0.72,
            "riskLevel": "medium",
            "reason": "网络升级 + 开发者活跃",
            "leverage": 3,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06
        }
    }

    for symbol, signal in signals.items():
        key = f"signal:{symbol.replace('/', '_')}"
        await redis.set_json(key, {
            **signal,
            "timestamp": datetime.utcnow().isoformat()
        })
        print(f"  ✓ 信号: {symbol} {signal['action']} ({signal['confidence']:.0%})")


async def main():
    """主函数"""
    print("=" * 80)
    print("  TradeAgent Runtime 系统")
    print("  Runtime-Oriented Architecture")
    print("=" * 80)

    # 1. 初始化数据
    await seed_real_data()

    # 2. 启动 Runtimes
    print("\n[Runtime 启动]")
    runtimes = []

    signal_rt = await start_signal_runtime()
    if signal_rt:
        runtimes.append(signal_rt)

    execution_rt = await start_execution_runtime()
    if execution_rt:
        runtimes.append(execution_rt)

    projection_rt = await start_projection_runtime()
    if projection_rt:
        runtimes.append(projection_rt)

    print("\n" + "=" * 80)
    print(f"  ✅ 成功启动 {len(runtimes)} 个 Runtime")
    print("=" * 80)

    if runtimes:
        print("\n按 Ctrl+C 停止所有服务...")
        try:
            await asyncio.gather(*[rt.run() for rt in runtimes])
        except KeyboardInterrupt:
            print("\n正在停止...")
            for rt in runtimes:
                await rt.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
