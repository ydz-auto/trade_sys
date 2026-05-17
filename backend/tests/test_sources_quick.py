#!/usr/bin/env python3
"""
数据源测试 - 修复版
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.data_service.adapters import (
    OdailySkillAdapter,
    CryptoPanicAdapter,
    WhaleAlertAdapter,
    TwitterAdapter,
    QQAdapter
)


async def test_telegram():
    """测试 Telegram"""
    print("\n" + "=" * 70)
    print("3️⃣  Telegram")
    print("=" * 70)

    try:
        from services.data_service.collectors.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter()

        print("📡 正在连接 Telegram...")
        events = await adapter.collect()

        print(f"✅ 获取到 {len(events)} 条消息")

        if events:
            print("\n示例:")
            for event in events[:3]:
                sender = event.metadata.get("sender_name", "unknown")
                print(f"  - {sender}: {event.content[:60]}...")
                print(f"    情绪: {event.sentiment}, 重要性: {event.importance}")

        return True

    except ImportError as e:
        print(f"⚠️  Telegram 适配器导入失败: {e}")
        print("需要安装: pip install telethon")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_all():
    print("=" * 70)
    print("🔍 数据源测试")
    print("=" * 70)

    results = {}

    # 1. Twitter
    print("\n✅ 1. Twitter")
    try:
        twitter = TwitterAdapter()
        events = await twitter.collect()
        print(f"   获取到 {len(events)} 条推文")
        results["Twitter"] = True
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        results["Twitter"] = False

    # 2. QQ
    print("\n✅ 2. QQ (模拟)")
    try:
        qq = QQAdapter()
        events = await qq.collect()
        print(f"   获取到 {len(events)} 条消息")
        results["QQ"] = True
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        results["QQ"] = False

    # 3. Odaily
    print("\n✅ 3. Odaily (ClawHub)")
    try:
        odaily = OdailySkillAdapter(modules=["M1"])
        events = await odaily.collect()
        print(f"   获取到 {len(events)} 条新闻")
        results["Odaily"] = True
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        results["Odaily"] = False

    # 4. Telegram
    print("\n📱 4. Telegram")
    results["Telegram"] = await test_telegram()

    # 总结
    print("\n" + "=" * 70)
    print("📊 结果")
    print("=" * 70)
    for name, status in results.items():
        print(f"{'✅' if status else '❌'} {name}")

    print(f"\n通过: {sum(results.values())}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(test_all())
