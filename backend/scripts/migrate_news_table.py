"""
数据库迁移脚本：扩展新闻表支持 LLM 增强

执行方式：
    python scripts/migrate_news_table.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger

logger = get_logger("migration")


async def migrate_news_table():
    """迁移新闻表"""
    logger.info("=" * 60)
    logger.info("开始迁移：扩展新闻表支持 LLM 增强 + 中文摘要")
    logger.info("=" * 60)
    
    try:
        from infrastructure.database import get_clickhouse_manager
        
        manager = get_clickhouse_manager()
        await manager.init_tables()
        
        # 检查表是否存在
        check_query = """
            SELECT name FROM system.tables 
            WHERE database = currentDatabase() AND name = 'news'
        """
        result = await manager.query(check_query)
        
        if result:
            logger.info("表 'news' 已存在")
            
            # 检查是否已有新字段
            desc_query = "DESCRIBE TABLE news"
            columns = await manager.query(desc_query)
            
            existing_columns = [col.get("name") for col in columns]
            logger.info(f"现有字段: {existing_columns}")
            
            # 需要添加的字段
            new_columns = {
                "title_zh": "ALTER TABLE news ADD COLUMN IF NOT EXISTS title_zh String DEFAULT ''",
                "content_zh": "ALTER TABLE news ADD COLUMN IF NOT EXISTS content_zh String DEFAULT ''",
                "importance": "ALTER TABLE news ADD COLUMN IF NOT EXISTS importance Float64 DEFAULT 0.5",
                "relevance": "ALTER TABLE news ADD COLUMN IF NOT EXISTS relevance Float64 DEFAULT 0.5",
                "confidence": "ALTER TABLE news ADD COLUMN IF NOT EXISTS confidence Float64 DEFAULT 0.5",
                "symbols": "ALTER TABLE news ADD COLUMN IF NOT EXISTS symbols String DEFAULT ''",
                "narratives": "ALTER TABLE news ADD COLUMN IF NOT EXISTS narratives String DEFAULT ''",
                "actionable": "ALTER TABLE news ADD COLUMN IF NOT EXISTS actionable UInt8 DEFAULT 0",
                "source_quality": "ALTER TABLE news ADD COLUMN IF NOT EXISTS source_quality Float64 DEFAULT 0.5",
                "content_quality": "ALTER TABLE news ADD COLUMN IF NOT EXISTS content_quality Float64 DEFAULT 0.5",
                "timeliness": "ALTER TABLE news ADD COLUMN IF NOT EXISTS timeliness Float64 DEFAULT 0.5",
                "is_black_swan": "ALTER TABLE news ADD COLUMN IF NOT EXISTS is_black_swan UInt8 DEFAULT 0",
                "reasoning": "ALTER TABLE news ADD COLUMN IF NOT EXISTS reasoning String DEFAULT ''",
                "scored_by": "ALTER TABLE news ADD COLUMN IF NOT EXISTS scored_by String DEFAULT 'unknown'"
            }
            
            # 添加缺失的字段
            for col_name, alter_sql in new_columns.items():
                if col_name not in existing_columns:
                    logger.info(f"添加字段: {col_name}")
                    try:
                        await manager.execute(alter_sql)
                        logger.info(f"✓ 成功添加字段: {col_name}")
                    except Exception as e:
                        logger.warning(f"添加字段失败 {col_name}: {e}")
                else:
                    logger.info(f"字段已存在: {col_name}")
            
            logger.info("迁移完成！")
            
        else:
            logger.info("表 'news' 不存在，将自动创建")
            
            # 创建新表
            create_sql = """
                CREATE TABLE IF NOT EXISTS news (
                    id String,
                    timestamp DateTime,
                    source String,
                    
                    -- 原始数据
                    title String,
                    title_zh String DEFAULT '',
                    content String,
                    content_zh String DEFAULT '',
                    url String,
                    
                    -- LLM 增强
                    sentiment String DEFAULT 'neutral',
                    sentiment_score Float64 DEFAULT 0.5,
                    importance Float64 DEFAULT 0.5,
                    relevance Float64 DEFAULT 0.5,
                    confidence Float64 DEFAULT 0.5,
                    
                    -- 提取信息
                    symbols String DEFAULT '',
                    narratives String DEFAULT '',
                    actionable UInt8 DEFAULT 0,
                    
                    -- 质量打分
                    source_quality Float64 DEFAULT 0.5,
                    content_quality Float64 DEFAULT 0.5,
                    timeliness Float64 DEFAULT 0.5,
                    
                    -- 特殊标记
                    is_black_swan UInt8 DEFAULT 0,
                    reasoning String DEFAULT '',
                    scored_by String DEFAULT 'unknown',
                    
                    -- 元数据
                    ingest_time DateTime DEFAULT now()
                ) ENGINE = MergeTree()
                PARTITION BY toYYYYMM(timestamp)
                ORDER BY (source, timestamp)
                TTL timestamp + INTERVAL 90 DAY
            """
            
            await manager.execute(create_sql)
            logger.info("✓ 成功创建表 'news'")
        
        return True
        
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def verify_migration():
    """验证迁移"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("验证迁移结果")
    logger.info("=" * 60)
    
    try:
        from infrastructure.database import get_clickhouse_manager
        
        manager = get_clickhouse_manager()
        
        # 查看表结构
        desc_query = "DESCRIBE TABLE news"
        columns = await manager.query(desc_query)
        
        logger.info("表结构:")
        for col in columns:
            logger.info(f"  {col.get('name'):20s} {col.get('type')}")
        
        # 统计记录数
        count_query = "SELECT count() as count FROM news"
        result = await manager.query(count_query)
        count = result[0].get("count", 0) if result else 0
        logger.info(f"\n总记录数: {count}")
        
        # 按 scored_by 统计
        scored_by_query = "SELECT scored_by, count() as count FROM news GROUP BY scored_by"
        result = await manager.query(scored_by_query)
        
        logger.info("\n打分方式统计:")
        for row in result:
            logger.info(f"  {row.get('scored_by'):15s} : {row.get('count')}")
        
        return True
        
    except Exception as e:
        logger.error(f"验证失败: {e}")
        return False


async def main():
    """主函数"""
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "         新闻表 LLM 增强迁移".center(58) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # 执行迁移
    success = await migrate_news_table()
    
    if success:
        # 验证
        await verify_migration()
        
        logger.info("")
        logger.info("✅ 迁移完成！")
        logger.info("")
        logger.info("新功能支持：")
        logger.info("  ✓ LLM 中文摘要（content_zh）")
        logger.info("  ✓ LLM 增强（importance, relevance, confidence）")
        logger.info("  ✓ 智能打分（source_quality, content_quality, timeliness）")
        logger.info("  ✓ 叙事提取（narratives）")
        logger.info("  ✓ 可操作性标记（actionable）")
        logger.info("  ✓ 黑天鹅检测（is_black_swan）")
        
        return 0
    else:
        logger.error("❌ 迁移失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
