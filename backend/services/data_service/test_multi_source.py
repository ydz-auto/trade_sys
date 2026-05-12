#!/usr/bin/env python3
"""
多数据源集成测试

测试所有适配器的数据采集能力
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.data_service.adapters import (
    get_adapter_registry,
    OdailySkillAdapter,
    CryptoPanicAdapter,
    WhaleAlertAdapter,
    TwitterAdapter
)


async def test_all_adapters():
    print("=" * 70)
    print("多数据源集成测试")
    print("=" * 70)
    
    # 1. 测试 Odaily Skill (已验证)
    print("\n📰 1. Odaily Skill (ClawHub)")
    print("-" * 70)
    odaily = OdailySkillAdapter(modules=["M1"])
    try:
        events = await odaily.collect()
        print(f"✅ 成功获取 {len(events)} 条事件")
        for i, e in enumerate(events[:3], 1):
            print(f"   {i}. [{e.sentiment}] {e.title[:50]}...")
    except Exception as e:
        print(f"❌ 失败: {e}")
    
    # 2. 测试 CryptoPanic (模拟数据)
    print("\n📰 2. CryptoPanic (新闻聚合)")
