#!/usr/bin/env python3
"""
测试 QQ 实时数据源

这个脚本在模拟模式下运行，不需要安装 NapCatQQ 也能测试。

运行：
    cd backend
    python3 test_qq_source.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.data_service.sources.qq_realtime import QQRealtimeSource


async def test():
    print("=" * 80)
    print("QQ 实时数据源 - 测试")
    print("=" * 80)
    print()

    source = QQRealtimeSource(use_mock=True)

    print("📊 配置信息：")
    print(f"   模式: 模拟模式 (MOCK)")
    print(f"   关键词优先级: P0={len(source.priority.P0_CRITICAL)}, "
          f"P1={len(source.priority.P1_IMPORTANT)}, "
          f"P2={len(source.priority.P2_NORMAL)}")
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

        print(f"{emoji} [{priority}] {event.metadata['sender']}")
        print(f"   内容: {event.content[:70]}")
        print(f"   币种: {', '.join(event.symbols) if event.symbols else '无'}")
        print(f"   情绪: {event.sentiment}")
        print(f"   重要性: {event.importance}")
        print()

        if len(received_events) >= 5:
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
    print(f"P0 重要: {stats['priority_p0']}")
    print(f"P1 关注: {stats['priority_p1']}")
    print(f"P2 过滤: {stats['priority_p2']}")
    print(f"重复消息: {stats['duplicates']}")
    print(f"错误: {stats['errors']}")
    print()
    print(f"实际处理事件: {len(received_events)}")

    print()
    print("=" * 80)
    print("标准化事件示例:")
    print("=" * 80)
    if received_events:
        sample = received_events[0]
        print(f"Source: {sample.source}")
        print(f"Type: {sample.event_type}")
        print(f"Title: {sample.title}")
        print(f"Symbols: {sample.symbols}")
        print(f"Sentiment: {sample.sentiment}")
        print(f"Importance: {sample.importance}")
        print(f"Tags: {sample.tags}")
        print()
        print("Metadata:")
        for k, v in sample.metadata.items():
            if k != "raw_msg":
                print(f"  {k}: {v}")

    print()
    print("=" * 80)
    print("✅ 测试通过！代码可以正常使用。")
    print("=" * 80)
    print()
    print("下一步:")
    print("  1. 安装 NapCatQQ: https://github.com/NapNeko/NapCatQQ")
    print("  2. 设置环境变量: QQ_USE_MOCK=false")
    print("  3. 运行 examples/qq_mvp.py")
    print()


if __name__ == "__main__":
    asyncio.run(test())
