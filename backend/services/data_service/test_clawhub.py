#!/usr/bin/env python3
"""
测试 ClawHub Odaily Skill 集成
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.data_service.adapters.skill_adapter import OdailySkillAdapter, ClawHubRunner


async def test_clawhub():
    print("=" * 60)
    print("ClawHub Odaily Skill 集成测试")
    print("=" * 60)

    print("\n1. 检查 Skill 路径...")
    skill_dir = ClawHubRunner.find_skill_dir()
    if skill_dir:
        print(f"   ✅ Skill 目录: {skill_dir}")
    else:
        print("   ❌ 未找到 Skill")
        return

    print("\n2. 测试模块调用...")
    
    print("\n   M1: 今日必关注")
    result = ClawHubRunner.call_module("get_today_watch", {"limit": 3})
    if result:
        print(f"   ✅ 返回 {len(result)} 条数据")
    else:
        print("   ❌ M1 调用失败")

    print("\n   M2: 市场分析")
    result = ClawHubRunner.call_module("get_crypto_market_analysis", {"focus": "overview"})
    if result:
        print(f"   ✅ 返回成功")
    else:
        print("   ❌ M2 调用失败")

    print("\n   M4: 巨鲸追踪")
    result = ClawHubRunner.call_module("scan_whale_tail_trades", {"min_size": 10000, "min_price": 0.95})
    if result:
        print(f"   ✅ 返回成功")
    else:
        print("   ❌ M4 调用失败")

    print("\n3. 测试 OdailySkillAdapter (仅 M1)...")
    adapter = OdailySkillAdapter(modules=["M1"])
    
    print("   采集数据中...")
    events = await adapter.collect()
    
    print(f"\n   ✅ 共获取 {len(events)} 个事件")
    
    for i, event in enumerate(events[:5], 1):
        print(f"\n   [{i}] {event.title[:50]}...")
        print(f"       Source: {event.source}")
        print(f"       Sentiment: {event.sentiment}")
        print(f"       Importance: {event.importance}")
        print(f"       Symbols: {event.symbols}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_clawhub())
