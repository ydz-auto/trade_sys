#!/usr/bin/env python3
"""
测试实时源管理器

测试所有实时数据源是否正常工作。
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.data_service.source_manager import get_source_manager, get_source_status, get_source_stats


async def test_source_manager():
    """测试数据源管理器"""
    print("=" * 70)
    print("测试数据源管理器")
    print("=" * 70)

    # 获取管理器
    manager = get_source_manager()

    # 获取注册的数据源
    status = manager.get_status()

    print(f"\n已注册的数据源: {len(status)}")
    for name, info in status.items():
        print(f"\n  📡 {name}")
        print(f"     类型: {info['type']}")
        print(f"     状态: {info['status']}")

    if not status:
        print("\n⚠️  没有注册的数据源")
        print("\n可能原因：")
        print("  1. 缺少依赖库")
        print("  2. 环境变量设置了禁用 (QQ_DISABLE=true 或 TELEGRAM_DISABLE=true)")
        return

    print("\n" + "=" * 70)
    print("启动所有数据源...")
    print("=" * 70)

    # 启动所有数据源
    results = await manager.start_all()

    print("\n启动结果:")
    for name, success in results.items():
        emoji = "✅" if success else "❌"
        print(f"  {emoji} {name}: {'成功' if success else '失败'}")

    # 获取状态
    print("\n" + "=" * 70)
    print("数据源状态")
    print("=" * 70)

    await asyncio.sleep(3)  # 等待一些事件

    status = manager.get_status()
    for name, info in status.items():
        print(f"\n  📡 {name}")
        print(f"     类型: {info['type']}")
        print(f"     状态: {info['status']}")
        print(f"     事件数: {info['events_count']}")
        print(f"     错误数: {info['errors_count']}")
        if info['last_event_time']:
            print(f"     最后事件: {info['last_event_time']}")

    # 获取统计
    stats = manager.get_stats()
    print("\n" + "=" * 70)
    print("统计信息")
    print("=" * 70)
    print(f"  数据源总数: {stats['total_sources']}")
    print(f"  运行中: {stats['running_sources']}")
    print(f"  总事件数: {stats['total_events']}")
    print(f"  总错误数: {stats['total_errors']}")
    print(f"  Kafka连接: {'是' if stats['kafka_connected'] else '否'}")

    # 停止
    print("\n" + "=" * 70)
    print("停止数据源...")
    print("=" * 70)

    await manager.stop_all()

    print("\n✅ 测试完成！")

    print("\n" + "=" * 70)
    print("使用说明")
    print("=" * 70)
    print("""
要使用真实数据源，配置环境变量：

QQ:
  export QQ_USE_MOCK=false
  export QQ_WS_URL=ws://127.0.0.1:3001
  export QQ_WATCH_GROUPS=123456789,987654321

Telegram:
  export TELEGRAM_USE_MOCK=false
  export TELEGRAM_API_ID=your_api_id
  export TELEGRAM_API_HASH=your_api_hash
  export TELEGRAM_PHONE=your_phone
""")


if __name__ == "__main__":
    asyncio.run(test_source_manager())
