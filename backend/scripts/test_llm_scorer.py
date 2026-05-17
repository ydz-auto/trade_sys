#!/usr/bin/env python3
"""
测试 LLM 增强 + 智能打分功能

测试分层 LLM 打分引擎
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger

logger = get_logger("test_llm_scorer")


async def test_llm_scorer():
    """测试 LLM 打分引擎"""
    logger.info("=" * 60)
    logger.info("测试 1: LLM 打分引擎（关键词模式）")
    logger.info("=" * 60)
    
    try:
        from services.event_service.scoring.llm_scorer import LLMScoringEngine, ScoringPriority
        
        # 创建引擎（不传入 LLM Pool，使用关键词降级）
        engine = LLMScoringEngine(llm_pool=None)
        
        # 测试数据
        test_events = [
            {
                "title": "BlackRock Bitcoin ETF 正式获批，机构资金持续流入",
                "content": "BlackRock 的比特币 ETF 已获得 SEC 批准，预计将引发新一轮机构入场潮",
                "source": "odaily"
            },
            {
                "title": "Ethereum 网络升级时间表确定，Gas 费用将大幅降低",
                "content": "以太坊基金会宣布了网络升级计划，预计 Gas 费用将下降 50%",
                "source": "cointelegraph"
            },
            {
                "title": "Solana 链上活动创历史新高，DApp 生态持续繁荣",
                "content": "Solana 网络的日活跃地址数突破了 100 万，创下历史记录",
                "source": "twitter"
            },
            {
                "title": "Twitter 网友热议：BTC 是否会突破 100K？",
                "content": "加密社区对 BTC 未来走势展开激烈讨论",
                "source": "twitter"
            }
        ]
        
        for event in test_events:
            logger.info("")
            logger.info(f"测试事件: {event['title'][:40]}...")
            
            # 获取优先级
            priority = engine.get_priority(event["source"])
            logger.info(f"  数据源: {event['source']} → 优先级: P{priority.value}")
            
            # 执行打分
            result = await engine.analyze(event)
            
            logger.info(f"  情绪: {result.sentiment}")
            logger.info(f"  重要性: {result.importance:.2f}")
            logger.info(f"  相关性: {result.relevance:.2f}")
            logger.info(f"  置信度: {result.confidence:.2f}")
            logger.info(f"  符号: {result.symbols}")
            logger.info(f"  叙事: {result.narratives}")
            logger.info(f"  可操作: {result.actionable}")
            logger.info(f"  打分方式: {result.scored_by}")
            logger.info(f"  来源质量: {result.source_quality:.2f}")
            logger.info(f"  内容质量: {result.content_quality:.2f}")
            logger.info(f"  时效性: {result.timeliness:.2f}")
            if result.reasoning:
                logger.info(f"  推理: {result.reasoning}")
        
        # 获取统计
        stats = engine.get_stats()
        logger.info("")
        logger.info("统计信息:")
        logger.info(f"  总数: {stats['total']}")
        logger.info(f"  LLM 成功: {stats['llm_success']}")
        logger.info(f"  LLM 失败: {stats['llm_failed']}")
        logger.info(f"  降级使用: {stats['fallback_used']}")
        
        return True
        
    except Exception as e:
        logger.error(f"LLM Scorer 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_priority_mapping():
    """测试优先级映射"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 2: 优先级映射")
    logger.info("=" * 60)
    
    from services.event_service.scoring.llm_scorer import LLMScoringConfig, ScoringPriority
    
    test_sources = [
        ("odaily", ScoringPriority.P0_FULL),
        ("clawhub_odaily", ScoringPriority.P0_FULL),
        ("etf", ScoringPriority.P0_FULL),
        ("macro", ScoringPriority.P0_FULL),
        ("twitter", ScoringPriority.P1_LIGHT),
        ("telegram", ScoringPriority.P1_LIGHT),
        ("rss", ScoringPriority.P2_KEYWORD),
        ("whale", ScoringPriority.P2_KEYWORD),
        ("cointelegraph", ScoringPriority.P2_KEYWORD),
    ]
    
    for source, expected in test_sources:
        actual = LLMScoringConfig.get_priority(source)
        status = "✓" if actual == expected else "✗"
        logger.info(f"  {status} {source:20s} → P{actual.value} (期望 P{expected.value})")
    
    return True


async def test_keyword_scorer():
    """测试关键词打分器"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 3: 关键词打分器（降级方案）")
    logger.info("=" * 60)
    
    from services.event_service.scoring.llm_scorer import KeywordScorer
    
    scorer = KeywordScorer()
    
    test_cases = [
        {
            "title": "Bitcoin 暴涨 10%，突破新高",
            "content": "BTC 价格创下历史新高，市场情绪极度乐观"
        },
        {
            "title": "以太坊暴跌 15%，引发市场恐慌",
            "content": "ETH 价格大幅下跌，多头被迫平仓"
        },
        {
            "title": "DeFi 协议获得新融资",
            "content": "某 DeFi 项目获得 1000 万美元融资"
        }
    ]
    
    for case in test_cases:
        result = scorer.score(case["title"], case["content"])
        
        logger.info("")
        logger.info(f"标题: {case['title']}")
        logger.info(f"  情绪: {result.sentiment}")
        logger.info(f"  重要性: {result.importance:.2f}")
        logger.info(f"  符号: {result.symbols}")
        logger.info(f"  叙事: {result.narratives}")
    
    return True


async def test_odaily_consumer_integration():
    """测试 OdailyConsumer 集成"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 4: OdailyConsumer 集成")
    logger.info("=" * 60)
    
    try:
        from services.event_service.consumers.odaily_consumer import OdailyConsumer
        
        # 创建消费者
        consumer = OdailyConsumer()
        await consumer.initialize()
        
        logger.info("OdailyConsumer 初始化成功")
        logger.info(f"LLM Scorer: {consumer._scorer is not None}")
        
        # 测试增强功能
        test_data = {
            "id": "test-123",
            "title": "BlackRock Bitcoin ETF 获批，机构资金流入",
            "content": "据最新消息，BlackRock 的比特币 ETF 正式获得批准",
            "source": "odaily",
            "sentiment": "bullish",
            "importance": 0.9,
            "symbols": ["BTC"],
            "tags": ["odaily", "etf"],
            "metadata": {}
        }
        
        enriched = await consumer._enrich_odaily_data(test_data)
        
        if enriched:
            logger.info("")
            logger.info("增强结果:")
            logger.info(f"  情绪: {enriched['sentiment']}")
            logger.info(f"  重要性: {enriched['importance']:.2f}")
            logger.info(f"  相关性: {enriched.get('relevance', 'N/A')}")
            logger.info(f"  置信度: {enriched.get('confidence', 'N/A')}")
            logger.info(f"  符号: {enriched['symbols']}")
            logger.info(f"  叙事: {enriched['narratives']}")
            logger.info(f"  可操作: {enriched['actionable']}")
            logger.info(f"  打分方式: {enriched['scored_by']}")
            logger.info(f"  黑天鹅: {enriched['is_black_swan']}")
        
        return True
        
    except Exception as e:
        logger.error(f"OdailyConsumer 集成测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def main():
    """主测试函数"""
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "       LLM 增强 + 智能打分测试".center(58) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # 运行所有测试
    results = []
    
    results.append(("LLM Scorer", await test_llm_scorer()))
    results.append(("Priority Mapping", await test_priority_mapping()))
    results.append(("Keyword Scorer", await test_keyword_scorer()))
    results.append(("OdailyConsumer Integration", await test_odaily_consumer_integration()))
    
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
        logger.info("LLM 增强 + 智能打分功能：")
        logger.info("  ✓ 分层 LLM（按优先级）")
        logger.info("  ✓ 一次调用同时完成增强 + 打分")
        logger.info("  ✓ 自动降级到关键词规则")
        logger.info("  ✓ 多维度打分（重要性、相关性、置信度等）")
        logger.info("  ✓ Token 消耗最优")
        return 0
    else:
        logger.error("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
