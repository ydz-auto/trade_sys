#!/usr/bin/env python3
"""
数据源测试 - 最终版
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

        # 检查 Telethon 是否安装
        try:
            import telethon
        except ImportError:
            print("⚠️  Telethon 未安装")
            print("   安装: pip install telethon")
            print("   获取 API: https://my.telegram.org/apps")
            return False

        # 连接
        connected = await adapter.connect()

        if not connected:
            print("⚠️  连接失败 (需要 API credentials)")
            print("   配置环境变量:")
            print("     TELEGRAM_API_ID=your_api_id")
            print("     TELEGRAM_API_HASH=your_api_hash")
            return False

        # 监听 5 秒
        print("⏱️  监听 5 秒...")
        await adapter.listen()
        await asyncio.sleep(5)
        await adapter.disconnect()

        stats = adapter.get_stats()
        print(f"\n✅ 获取到 {stats['total_messages']} 条消息")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 70)
    print("🔍 数据源测试")
    print("=" * 70)

    results = {}

    # 1. Twitter
    print("\n✅ 1. Twitter (模拟)")
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

    # 5. CryptoPanic
    print("\n✅ 5. CryptoPanic (模拟)")
    try:
        adapter = CryptoPanicAdapter(api_key=None)
        events = await adapter.collect()
        print(f"   获取到 {len(events)} 条新闻")
        await adapter.close()
        results["CryptoPanic"] = True
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        results["CryptoPanic"] = False

    # 总结
    print("\n" + "=" * 70)
    print("📊 结果")
    print("=" * 70)
    for name, status in results.items():
        print(f"{'✅' if status else '❌'} {name}")

    print(f"\n通过: {sum(results.values())}/{len(results)}")

    print("\n" + "=" * 70)
    print("💡 说明")
    print("=" * 70)
    print("模拟模式的数据源可以在没有 API key 时正常工作")
    print("要启用真实数据，配置相应的环境变量即可")


if __name__ == "__main__":
    asyncio.run(main())
