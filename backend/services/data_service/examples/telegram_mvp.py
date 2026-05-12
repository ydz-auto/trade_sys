#!/usr/bin/env python3
"""
Telegram 实时监控 MVP

监控优质新闻频道：
- WuBlockchain (币世界)
- 金十数据
- PANews
- Odaily
- TreeNews

运行：
    cd backend
    python3 services/data_service/examples/telegram_mvp.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.data_service.sources.telegram_realtime import TelegramRealtimeSource


async def main():
    print("=" * 70)
    print("Telegram 实时监控 MVP")
    print("=" * 70)

    use_mock = os.getenv("TELEGRAM_USE_MOCK", "true").lower() == "true"

    if use_mock:
        print("\n⚠️  当前在模拟模式！")
        print("-" * 70)
        print("要使用真实 Telegram，设置环境变量：")
        print("  export TELEGRAM_API_ID=your_api_id")
        print("  export TELEGRAM_API_HASH=your_api_hash")
        print("  export TELEGRAM_PHONE=your_phone")
        print()
        print("获取 API: https://my.telegram.org/apps")
        print()
        input("按回车继续模拟模式演示...")
    else:
        print("\n✅ 真实模式")
        print("-" * 70)
        print("请确保：")
        print("  1. 已安装 Telethon: pip install telethon")
        print("  2. 已配置 API credentials")
        print("  3. 手机号已验证")
        print()
        input("按回车继续...")

    print()
    print("=" * 70)
    print("配置信息")
    print("=" * 70)

    print(f"模拟模式: {'是' if use_mock else '否'}")

    channels = os.getenv("TELEGRAM_CHANNELS", "")
    if channels:
        print(f"监控频道: {channels}")
    else:
        print("监控频道: (默认列表)")

    print()

    source = TelegramRealtimeSource(use_mock=use_mock)

    print("\n" + "=" * 70)
    print("开始监听... (Ctrl+C 停止)")
    print("=" * 70)
    print()

    async def on_event(event):
        priority = event.metadata.get("priority", "P2")
        emoji = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(priority, "⚪")

        print(f"{emoji} [{priority}] {event.metadata['channel']}")
        print(f"   {event.content[:80]}")
        print(f"   币种: {', '.join(event.symbols) if event.symbols else '无'}")
        print(f"   情绪: {event.sentiment}")
        print()

    source.on_event = on_event

    try:
        await source.listen()
    except KeyboardInterrupt:
        print("\n\n停止中...")
        await source.stop()

        print("\n" + "=" * 70)
        print("统计")
        print("=" * 70)
        stats = source.get_stats()
        print(f"总消息: {stats['total']}")
        print(f"P0 重要: {stats['p0']}")
        print(f"P1 关注: {stats['p1']}")
        print(f"P2 过滤: {stats['p2']}")
        print(f"重复: {stats['duplicates']}")
        print(f"错误: {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
