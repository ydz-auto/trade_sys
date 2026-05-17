#!/usr/bin/env python3
"""
数据源完整测试

测试所有数据源的采集能力。
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.data_service.adapters import (
    get_adapter_registry,
    OdailySkillAdapter,
    CryptoPanicAdapter,
    WhaleAlertAdapter,
    TwitterAdapter
)


async def test_binance():
    """测试 Binance WebSocket"""
    print("\n" + "=" * 70)
    print("1️⃣  Binance WebSocket")
    print("=" * 70)

    try:
        from services.data_service.collectors.binance_websocket import BinanceWebSocketAdapter

        adapter = BinanceWebSocketAdapter()

        print("📡 正在连接 Binance WebSocket...")
        await adapter.connect()

        print("⏱️  等待 5 秒获取数据...")
        await asyncio.sleep(5)

        events = adapter.get_events()
        print(f"\n✅ 获取到 {len(events)} 个事件")

        if events:
            print("\n最新事件:")
            for event in events[:3]:
                print(f"  - {event.title}")
                print(f"    类型: {event.event_type}")
                print(f"    币种: {event.symbols}")
                print()

        await adapter.disconnect()
        return True

    except ImportError:
        print("⚠️  Binance WebSocket 适配器未找到")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_twitter():
    """测试 Twitter"""
    print("\n" + "=" * 70)
    print("2️⃣  Twitter/X")
    print("=" * 70)

    try:
        twitter = TwitterAdapter()
        events = await twitter.collect()

        print(f"✅ 获取到 {len(events)} 条推文")

        if events:
            print("\n示例:")
            for event in events[:3]:
                author = event.metadata.get("author", "unknown")
                print(f"  - @{author}: {event.content[:60]}...")
                print(f"    情绪: {event.sentiment}, 重要性: {event.importance}")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_telegram():
    """测试 Telegram"""
    print("\n" + "=" * 70)
    print("3️⃣  Telegram")
    print("=" * 70)

    try:
        from services.data_service.collectors.telegram_adapter import TelegramCollector

        adapter = TelegramCollector()

        print("📡 正在连接 Telegram...")
        events = await adapter.fetch()

        print(f"✅ 获取到 {len(events)} 条消息")

        if events:
            print("\n示例:")
            for event in events[:3]:
                sender = event.metadata.get("sender_name", "unknown")
                print(f"  - {sender}: {event.content[:60]}...")
                print(f"    情绪: {event.sentiment}, 重要性: {event.importance}")

        return True

    except ImportError:
        print("⚠️  Telegram 适配器未找到")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_news_sources():
    """测试新闻源"""
    print("\n" + "=" * 70)
    print("4️⃣  新闻源")
    print("=" * 70)

    try:
        # CryptoPanic
        print("\n📰 CryptoPanic:")
        adapter = CryptoPanicAdapter(api_key=None)
        events = await adapter.collect()
        print(f"  ✅ 获取到 {len(events)} 条新闻")
        await adapter.close()

        # Odaily Skill
        print("\n📰 Odaily (ClawHub):")
        adapter = OdailySkillAdapter(modules=["M1"])
        events = await adapter.collect()
        print(f"  ✅ 获取到 {len(events)} 条新闻")

        # Whale Alert
        print("\n🐋 Whale Alert:")
        adapter = WhaleAlertAdapter(api_key=None)
        events = await adapter.collect()
        print(f"  ✅ 获取到 {len(events)} 条警报")
        await adapter.close()

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_registry():
    """测试适配器注册表"""
    print("\n" + "=" * 70)
    print("5️⃣  适配器注册表")
    print("=" * 70)

    try:
        registry = get_adapter_registry()

        print(f"\n已注册的适配器: {len(registry._adapters)}")
        for name in registry._adapters.keys():
            print(f"  ✅ {name}")

        print("\n采集所有事件...")
        all_events = await registry.collect_all()
        print(f"\n✅ 总共获取 {len(all_events)} 个事件")

        # 按来源分组
        by_source = {}
        for e in all_events:
            by_source[e.source] = by_source.get(e.source, 0) + 1

        print("\n按来源分布:")
        for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {source}: {count} 条")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 70)
    print("🔍 数据源完整测试")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # 1. Binance
    results["Binance WebSocket"] = await test_binance()

    # 2. Twitter
    results["Twitter"] = await test_twitter()

    # 3. Telegram
    results["Telegram"] = await test_telegram()

    # 4. 新闻源
    results["新闻源"] = await test_news_sources()

    # 5. 注册表
    results["适配器注册表"] = await test_registry()

    # 总结
    print("\n" + "=" * 70)
    print("📊 测试总结")
    print("=" * 70)

    success = sum(1 for v in results.values() if v)
    total = len(results)

    for name, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {name}")

    print(f"\n通过: {success}/{total}")

    if success == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - success} 个测试失败")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
