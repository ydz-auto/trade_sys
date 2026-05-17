"""
News Storage - 新闻存储（支持 LLM 增强 + 中文摘要）

存储增强后的新闻数据：
- 原始数据（英文）
- LLM 翻译（中文摘要）
- LLM 增强分析
- 智能打分
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from infrastructure.logging import get_logger
logger = get_logger("news_storage")

from infrastructure.database import get_clickhouse_manager


class NewsStorage:
    """
    新闻存储器
    
    存储增强后的新闻数据：
    - 原始数据
    - LLM 翻译（中文）
    - LLM 增强（情绪、叙事、符号）
    - 智能打分（多维度）
    """
    
    def __init__(self):
        self._manager = None
        self._initialized = False
    
    async def initialize(self):
        """初始化"""
        if self._initialized:
            return
        
        try:
            self._manager = get_clickhouse_manager()
            await self._manager.init_tables()
            self._initialized = True
            logger.info("News storage initialized")
        except Exception as e:
            logger.warning(f"ClickHouse not available, news storage disabled: {e}")
            self._initialized = False
    
    async def store_news(self, news: Dict[str, Any]) -> bool:
        """
        存储单条新闻
        
        Args:
            news: {
                "id": str,
                "timestamp": datetime,
                "source": str,
                
                # 原始数据
                "title": str,
                "content": str,
                "url": str,
                
                # LLM 翻译
                "title_zh": str,
                "content_zh": str,
                
                # LLM 增强
                "sentiment": str,
                "sentiment_score": float,
                "importance": float,
                "relevance": float,
                "confidence": float,
                
                # 提取信息
                "symbols": List[str],
                "narratives": List[str],
                "actionable": bool,
                
                # 质量打分
                "source_quality": float,
                "content_quality": float,
                "timeliness": float,
                
                # 特殊标记
                "is_black_swan": bool,
                "reasoning": str,
                "scored_by": str
            }
            
        Returns:
            bool: 是否存储成功
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._manager:
            logger.warning("Storage not available, skipping")
            return False
        
        try:
            # 序列化和存储
            record = self._prepare_record(news)
            await self._manager.insert("news", [record])
            
            logger.info(f"Stored news: {news.get('title', '')[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store news: {e}")
            return False
    
    async def store_batch(self, news_list: List[Dict[str, Any]]) -> int:
        """
        批量存储新闻
        
        Args:
            news_list: 新闻列表
            
        Returns:
            int: 成功存储的数量
        """
        if not news_list:
            return 0
        
        if not self._initialized:
            await self.initialize()
        
        if not self._manager:
            logger.warning("Storage not available, skipping batch")
            return 0
        
        try:
            records = [self._prepare_record(news) for news in news_list]
            await self._manager.insert("news", records)
            
            success_count = len(records)
            logger.info(f"Batch stored {success_count} news items")
            return success_count
            
        except Exception as e:
            logger.error(f"Failed to batch store news: {e}")
            return 0
    
    def _prepare_record(self, news: Dict[str, Any]) -> Dict[str, Any]:
        """准备存储记录"""
        # 序列化和格式化
        symbols = news.get("symbols", [])
        if isinstance(symbols, list):
            symbols_str = ",".join(symbols)
        else:
            symbols_str = str(symbols)
        
        narratives = news.get("narratives", [])
        if isinstance(narratives, list):
            narratives_str = ",".join(narratives)
        else:
            narratives_str = str(narratives)
        
        return {
            "id": news.get("id", ""),
            "timestamp": news.get("timestamp") or datetime.now(),
            "source": news.get("source", ""),
            
            # 原始数据
            "title": news.get("title", "")[:500],
            "title_zh": news.get("title_zh", "")[:200],
            "content": news.get("content", "")[:2000],
            "content_zh": news.get("content_zh", "")[:500],  # 中文摘要（限制长度）
            "url": news.get("url", ""),
            
            # LLM 增强
            "sentiment": news.get("sentiment", "neutral"),
            "sentiment_score": float(news.get("sentiment_score", 0.5)),
            "importance": float(news.get("importance", 0.5)),
            "relevance": float(news.get("relevance", 0.5)),
            "confidence": float(news.get("confidence", 0.5)),
            
            # 提取信息
            "symbols": symbols_str,
            "narratives": narratives_str,
            "actionable": bool(news.get("actionable", False)),
            
            # 质量打分
            "source_quality": float(news.get("source_quality", 0.5)),
            "content_quality": float(news.get("content_quality", 0.5)),
            "timeliness": float(news.get("timeliness", 0.5)),
            
            # 特殊标记
            "is_black_swan": bool(news.get("is_black_swan", False)),
            "reasoning": news.get("reasoning", "")[:500],
            "scored_by": news.get("scored_by", "unknown"),
            
            # 元数据
            "ingest_time": datetime.now()
        }
    
    async def query_news(
        self,
        source: Optional[str] = None,
        sentiment: Optional[str] = None,
        min_importance: float = 0.0,
        symbols: Optional[List[str]] = None,
        narratives: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询新闻
        
        Args:
            source: 数据源过滤
            sentiment: 情绪过滤
            min_importance: 最小重要性
            symbols: 相关币种过滤
            narratives: 叙事过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 新闻列表
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._manager:
            logger.warning("Storage not available")
            return []
        
        try:
            # 构建 WHERE 条件
            conditions = []
            
            if source:
                conditions.append(f"source = '{source}'")
            
            if sentiment:
                conditions.append(f"sentiment = '{sentiment}'")
            
            if min_importance > 0:
                conditions.append(f"importance >= {min_importance}")
            
            if symbols:
                symbols_filter = " OR ".join([f"symbols LIKE '%{s}%'" for s in symbols])
                conditions.append(f"({symbols_filter})")
            
            if narratives:
                narratives_filter = " OR ".join([f"narratives LIKE '%{n}%'" for n in narratives])
                conditions.append(f"({narratives_filter})")
            
            if start_time:
                conditions.append(f"timestamp >= '{start_time.isoformat()}'")
            
            if end_time:
                conditions.append(f"timestamp <= '{end_time.isoformat()}'")
            
            # 构建查询
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT * FROM news
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """
            
            result = await self._manager.query(query)
            
            # 解析结果
            news_list = []
            for row in result:
                news = {
                    "id": row.get("id"),
                    "timestamp": row.get("timestamp"),
                    "source": row.get("source"),
                    "title": row.get("title"),
                    "title_zh": row.get("title_zh"),
                    "content": row.get("content"),
                    "content_zh": row.get("content_zh"),
                    "url": row.get("url"),
                    "sentiment": row.get("sentiment"),
                    "sentiment_score": row.get("sentiment_score"),
                    "importance": row.get("importance"),
                    "relevance": row.get("relevance"),
                    "confidence": row.get("confidence"),
                    "symbols": row.get("symbols", "").split(",") if row.get("symbols") else [],
                    "narratives": row.get("narratives", "").split(",") if row.get("narratives") else [],
                    "actionable": row.get("actionable"),
                    "source_quality": row.get("source_quality"),
                    "content_quality": row.get("content_quality"),
                    "timeliness": row.get("timeliness"),
                    "is_black_swan": row.get("is_black_swan"),
                    "reasoning": row.get("reasoning"),
                    "scored_by": row.get("scored_by"),
                    "ingest_time": row.get("ingest_time")
                }
                news_list.append(news)
            
            return news_list
            
        except Exception as e:
            logger.error(f"Failed to query news: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            await self.initialize()
        
        if not self._manager:
            return {}
        
        try:
            queries = {
                "total": "SELECT count() as count FROM news",
                "by_source": "SELECT source, count() as count FROM news GROUP BY source ORDER BY count DESC",
                "by_sentiment": "SELECT sentiment, count() as count FROM news GROUP BY sentiment",
                "avg_importance": "SELECT avg(importance) as avg FROM news",
                "actionable_count": "SELECT count() as count FROM news WHERE actionable = 1",
                "black_swan_count": "SELECT count() as count FROM news WHERE is_black_swan = 1",
                "llm_vs_keyword": "SELECT scored_by, count() as count FROM news GROUP BY scored_by"
            }
            
            stats = {}
            for key, query in queries.items():
                result = await self._manager.query(query)
                stats[key] = result
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}


# 全局实例
_news_storage: Optional[NewsStorage] = None


def get_news_storage() -> NewsStorage:
    """获取新闻存储器单例"""
    global _news_storage
    if _news_storage is None:
        _news_storage = NewsStorage()
    return _news_storage
