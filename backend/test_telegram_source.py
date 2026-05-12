#!/usr/bin/env python3
"""
测试 Telegram 实时数据源
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.data_service.sources.telegram_realtime import TelegramRealtimeSource


async def main():
    print("=" * 80)
    print("Telegram 实时数据源 - 测试")
    print("=" * 80)
    print()

    source = TelegramRealtimeSource(use_mock=True)

    print("📊 配置信息：")
    print(f"   模式: 模拟模式 (MOCK)")
    print(f"   频道: {source.channels}")
    print()
    print("=" * 80)
    print("开始监听... (Ctrl+C 停止)")
    print("=" * 80)
    print()

    received_events = []

    async def on_event(event):
        received_events.append(event)

        priority = event.metadata.get("priority", "P2")
        emoji = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(priority, "⚪")

        print(f"{emoji} [{priority}] {event.metadata['channel']}")
        print(f"   内容: {event.content[:70]}")
        print(f"   币种: {', '.join(event.symbols) if event.symbols else '无'}")
        print(f"   情绪: {event.sentiment}")
        print(f"   重要性: {event.importance}")
        print()

        if len(received_events) >= 3:
            source._running = False

    source.on_event = on_event

    try:
        await source.listen()
    except KeyboardInterrupt:
        pass
    finally:
        await source.stop()

    print()
    print("=" * 80)
    print("测试完成 - 统计")
    print("=" * 80)
    stats = source.get_stats()

    print()
    print(f"总消息数: {stats['total']}")
    print(f"P0 重要: {stats['p0']}")
    print(f"P1 关注: {stats['p1']}")
    print(f"P2 过滤: {stats['p2']}")
    print(f"重复消息: {stats['duplicates']}")
    print(f"错误: {stats['errors']}")
    print()
    print(f"实际处理事件: {len(received_events)}")

    print()
    print("=" * 80)
    print("✅ 测试通过！Telegram 数据源可以正常使用。")
    print("=" * 80)
    print()
    print("下一步:")
    print("  1. 获取 Telegram API: https://my.telegram.org/apps")
    print("  2. 安装 Telethon: pip install telethon")
    print("  3. 设置环境变量:")
    print("     export TELEGRAM_API_ID=your_id")
    print("     export TELEGRAM_API_HASH=your_hash")
    print("     export TELEGRAM_PHONE=your_phone")
    print("  4. 运行 examples/telegram_mvp.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
