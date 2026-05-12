"""
QQ 实时监控 MVP - 最简方案

目标：
QQ 群 → 实时打印 → 关键词过滤

这个脚本展示了最简单的使用方式。

运行：
    cd backend
    python3 examples/qq_mvp.py

需要：
1. 安装 NapCatQQ: https://github.com/NapNeko/NapCatQQ
2. 开启 WebSocket (默认 ws://127.0.0.1:3001)
3. 设置监控的群号
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_service.sources.qq_realtime import QQRealtimeSource


async def main():
    print("=" * 70)
    print("QQ 实时监控 MVP")
    print("=" * 70)

    use_mock = os.getenv("QQ_USE_MOCK", "true").lower() == "true"

    if use_mock:
        print("\n⚠️  当前在模拟模式！")
        print("-" * 70)
        print("要使用真实 NapCatQQ，设置环境变量：")
        print("  export QQ_USE_MOCK=false")
        print()
        input("按回车继续模拟模式演示...")
    else:
        print("\n✅ 真实模式")
        print("-" * 70)
        print("请确保：")
        print("  1. NapCatQQ 已启动")
        print("  2. WebSocket 服务已开启 (端口 3001)")
        print("  3. 已配置 QQ_WATCH_GROUPS")
        print()
        input("按回车继续...")

    print()
    print("=" * 70)
    print("配置信息")
    print("=" * 70)

    ws_url = os.getenv("QQ_WS_URL", "ws://127.0.0.1:3001")
    watch_groups = os.getenv("QQ_WATCH_GROUPS", "")

    print(f"WebSocket: {ws_url}")
    print(f"模拟模式: {'是' if use_mock else '否'}")

    groups = [int(g.strip()) for g in watch_groups.split(",") if g.strip()] if watch_groups else []

    if groups:
        print(f"监控群: {groups}")
    else:
        print("监控群: 未配置 (全部群)")

    print()

    source = QQRealtimeSource(
        ws_url=ws_url,
        watch_groups=groups if groups else None,
        use_mock=use_mock
    )

    print("\n" + "=" * 70)
    print("开始监听... (Ctrl+C 停止)")
    print("=" * 70)
    print()

    async def on_event(event):
        priority = event.metadata.get("priority", "P2")
        emoji = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(priority, "⚪")

        print(f"{emoji} [{priority}] {event.metadata['sender']}")
        print(f"   {event.content[:100]}")
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
        print(f"P0 重要: {stats['priority_p0']}")
        print(f"P1 关注: {stats['priority_p1']}")
        print(f"P2 过滤: {stats['priority_p2']}")
        print(f"重复: {stats['duplicates']}")
        print(f"错误: {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
