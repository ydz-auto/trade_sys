#!/usr/bin/env python3
"""
多数据源集成测试

测试所有适配器的数据采集能力
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from services.data_service.adapters import (
    get_adapter_registry,
    OdailySkillAdapter,
    CryptoPanicAdapter,
    WhaleAlertAdapter,
    TwitterAdapter,
    QQAdapter
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
    print("-" * 70)
    cryptopanic = CryptoPanicAdapter(api_key=None)  # 无 API Key 时使用模拟数据
    try:
        events = await cryptopanic.collect()
        print(f"✅ 成功获取 {len(events)} 条事件")
        for i, e in enumerate(events[:3], 1):
            print(f"   {i}. [{e.sentiment}] {e.title[:50]}...")
    except Exception as e:
        print(f"❌ 失败: {e}")
    finally:
        await cryptopanic.close()
    
    # 3. 测试 Whale Alert (模拟数据)
    print("\n🐋 3. Whale Alert (链上监控)")
    print("-" * 70)
    whale = WhaleAlertAdapter(api_key=None)  # 无 API Key 时使用模拟数据
    try:
        events = await whale.collect()
        print(f"✅ 成功获取 {len(events)} 条事件")
        for i, e in enumerate(events[:3], 1):
            print(f"   {i}. [{e.sentiment}] {e.title[:50]}...")
    except Exception as e:
        print(f"❌ 失败: {e}")
    finally:
        await whale.close()
    
    # 4. 测试 Twitter (支持真实 API)
    print("\n🐦 4. Twitter (社交监控)")
    print("-" * 70)
    # 检查是否配置了 API Key
    has_api_key = os.getenv("TWITTER_API_KEY") is not None
    twitter = TwitterAdapter()
    try:
        events = await twitter.collect()
        print(f"✅ 成功获取 {len(events)} 条事件")
        if has_api_key:
            print("   (使用真实 API)")
        else:
            print("   (使用模拟数据 - 设置 TWITTER_API_KEY 启用真实数据)")
        for i, e in enumerate(events[:3], 1):
            author = e.metadata.get("author", "unknown")
            print(f"   {i}. [{author}] {e.title[:50]}...")
    except Exception as e:
        print(f"❌ 失败: {e}")
    
    # 5. 测试 QQ (中文社区监控)
    print("\n💬 5. QQ (中文社区监控)")
    print("-" * 70)
    qq = QQAdapter()
    try:
        events = await qq.collect()
        print(f"✅ 成功获取 {len(events)} 条事件")
        print("   (使用模拟数据 - 设置 QQ_USE_MOCK=false 启用 go-cqhttp)")
        for i, e in enumerate(events[:3], 1):
            sender = e.metadata.get("sender", "unknown")
            print(f"   {i}. [{sender}] {e.content[:50]}...")
            print(f"      情绪: {e.sentiment}, 币种: {e.symbols}, 重要性: {e.importance}")
    except Exception as e:
        print(f"❌ 失败: {e}")
    
    # 6. 汇总
    print("\n" + "=" * 70)
    print("数据源汇总")
    print("=" * 70)
    
    registry = get_adapter_registry()
    all_events = await registry.collect_all()
    
    print(f"\n总计获取 {len(all_events)} 条事件")
    
    # 按来源分组
    by_source = {}
    for e in all_events:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    
    print("\n按来源分布:")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  - {source}: {count} 条")
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
    
    # 输出使用说明
    print("\n📖 启用真实数据:")
    print("-" * 70)
    print("设置环境变量:")
    print("  export TWITTER_API_KEY='your_key'")
    print("  export TWITTER_API_SECRET='your_secret'")
    print("  export TWITTER_ACCESS_TOKEN='your_token'")
    print("  export TWITTER_ACCESS_TOKEN_SECRET='your_token_secret'")
    print("")
    print("获取 API: https://developer.twitter.com/en/docs/twitter-api")


if __name__ == "__main__":
    asyncio.run(test_all_adapters())
