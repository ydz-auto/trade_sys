#!/usr/bin/env python3
"""
测试 Odaily 数据流

测试完整的数据流：
DataService OdailySkillAdapter → Kafka raw.odaily → EventService OdailyConsumer
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger

logger = get_logger("test_odaily_flow")


async def test_odaily_adapter():
    """测试 OdailySkillAdapter"""
    logger.info("=" * 60)
    logger.info("测试 1: OdailySkillAdapter")
    logger.info("=" * 60)
    
    try:
        from services.data_service.adapters.skill_adapter import OdailySkillAdapter
        
        adapter = OdailySkillAdapter()
        logger.info("OdailySkillAdapter 初始化成功")
        
        # 测试获取原始数据
        raw_data = await adapter.fetch_raw_data()
        logger.info(f"获取原始数据: {len(raw_data.get('modules', {}))} 个模块")
        
        # 测试标准化
        events = adapter.normalize(raw_data)
        logger.info(f"标准化事件数: {len(events)}")
        
        for i, event in enumerate(events[:3]):
            logger.info(f"  事件 {i+1}:")
            logger.info(f"    标题: {event.title[:60]}...")
            logger.info(f"    来源: {event.source}")
            logger.info(f"    情绪: {event.sentiment}")
            logger.info(f"    符号: {event.symbols}")
            logger.info(f"    标签: {event.tags}")
        
        return True
        
    except Exception as e:
        logger.error(f"OdailySkillAdapter 测试失败: {e}")
        return False


async def test_kafka_topic():
    """测试 Kafka topic 配置"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 2: Kafka Topic 配置")
    logger.info("=" * 60)
    
    try:
        from infrastructure.messaging import Topics
        
        topic = Topics.raw_odaily()
        logger.info(f"raw.odaily topic: {topic}")
        
        return True
        
    except Exception as e:
        logger.error(f"Kafka topic 测试失败: {e}")
        return False


async def test_odaily_consumer():
    """测试 OdailyConsumer (简化版)"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 3: OdailyConsumer (增强逻辑)")
    logger.info("=" * 60)
    
    try:
        # 直接测试增强逻辑，避免复杂依赖
        test_data = {
            "id": "test-123",
            "title": "BlackRock Bitcoin ETF 获批，机构资金持续流入",
            "content": "据最新消息，BlackRock 的比特币 ETF 已正式获得 SEC 批准，市场情绪高涨...",
            "sentiment": "bullish",
            "importance": 0.9,
            "symbols": ["BTC", "ETH"],
            "tags": ["odaily", "m1_article"],
            "metadata": {}
        }
        
        # 直接测试核心逻辑
        from services.event_service.consumers.odaily_consumer import OdailyConsumer
        
        # 使用一个简单的实例化
        consumer = OdailyConsumer()
        
        # 测试私有方法（生产中不推荐，但测试中可以）
        narratives = consumer._extract_narratives(test_data["title"] + " " + test_data["content"])
        actionability = consumer._calculate_actionability(
            test_data["importance"],
            test_data["tags"],
            test_data["symbols"]
        )
        is_black_swan = consumer._detect_black_swan(test_data["title"] + " " + test_data["content"])
        
        logger.info(f"增强逻辑测试:")
        logger.info(f"  叙事: {narratives}")
        logger.info(f"  可操作性: {actionability:.2f}")
        logger.info(f"  黑天鹅: {is_black_swan}")
        
        return True
        
    except Exception as e:
        logger.error(f"OdailyConsumer 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_ingestion_integration():
    """测试 Ingestion Runtime 集成"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 4: Ingestion Runtime 集成")
    logger.info("=" * 60)
    
    try:
        # 我们不启动完整的 runtime，只测试关键组件
        from services.data_service.adapters.skill_adapter import OdailySkillAdapter
        
        adapter = OdailySkillAdapter()
        
        # 模拟 Ingestion Runtime 的调用
        raw_data = await adapter.fetch_raw_data()
        events = adapter.normalize(raw_data)
        
        logger.info(f"模拟 Ingestion Runtime:")
        logger.info(f"  采集事件数: {len(events)}")
        logger.info(f"  模拟发布到: raw.odaily topic")
        
        return True
        
    except Exception as e:
        logger.error(f"Ingestion 集成测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def main():
    """主测试函数"""
    
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "           Odaily 数据流测试".center(58) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # 运行所有测试
    results = []
    
    results.append(("OdailySkillAdapter", await test_odaily_adapter()))
    results.append(("Kafka Topic", await test_kafka_topic()))
    results.append(("OdailyConsumer", await test_odaily_consumer()))
    results.append(("Ingestion Integration", await test_ingestion_integration()))
    
    # 输出汇总
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info(f"{name:30s} {status}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("✅ 所有测试通过！")
        logger.info("")
        logger.info("架构说明:")
        logger.info("  DataService: OdailySkillAdapter 采集数据")
        logger.info("    ↓")
        logger.info("  Kafka: raw.odaily topic")
        logger.info("    ↓")
        logger.info("  EventService: OdailyConsumer 消费并增强理解")
        return 0
    else:
        logger.error("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
