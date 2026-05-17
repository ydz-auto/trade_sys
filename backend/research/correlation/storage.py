"""
相关性分析结果存储 - ClickHouse 存储适配器
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.database import get_clickhouse_manager

logger = get_logger("research.correlation.storage")


class CorrelationStorage:
    """相关性分析结果存储适配器"""
    
    def __init__(self):
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            manager = get_clickhouse_manager()
            self._client = manager.client
        return self._client
    
    async def save_result(self, result: Dict[str, Any]) -> bool:
        """
        保存相关性分析结果到 ClickHouse
        
        Args:
            result: CorrelationResult.to_dict() 的输出
        
        Returns:
            bool: 是否保存成功
        """
        try:
            client = await self._get_client()
            
            row = {
                "symbol": result["symbol"],
                "timeframe": result["timeframe"],
                "timestamp": result["timestamp"],
                "positive_count": result["summary"]["positive_count"],
                "negative_count": result["summary"]["negative_count"],
                "neutral_count": result["summary"]["neutral_count"],
                "total_signals": result["summary"]["total_signals"],
                "signal_assessments": json.dumps(result["signal_assessments"], ensure_ascii=False),
                "univariate_results": json.dumps(result.get("univariate_results", {}), ensure_ascii=False),
                "multivariate_results": json.dumps(result.get("multivariate_results", {}), ensure_ascii=False),
                "llm_results": json.dumps(result.get("llm_results", {}), ensure_ascii=False),
                "analysis_duration_ms": result.get("metadata", {}).get("analysis_duration_ms", 0.0),
            }
            
            await client.insert("correlation_results", [row])
            
            logger.info(
                f"Saved correlation result to ClickHouse: "
                f"{result['symbol']} {result['timeframe']} "
                f"(+{row['positive_count']}/-{row['negative_count']}/~{row['neutral_count']})"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save correlation result to ClickHouse: {e}")
            return False
    
    async def get_latest_result(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取最新的相关性分析结果
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
        
        Returns:
            最新的分析结果，如果没有则返回 None
        """
        try:
            client = await self._get_client()
            
            query = f"""
                SELECT *
                FROM correlation_results
                WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
                ORDER BY timestamp DESC
                LIMIT 1
            """
            
            results = await client.fetch(query)
            
            if not results:
                return None
            
            row = results[0]
            
            return {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "timestamp": row["timestamp"],
                "summary": {
                    "positive_count": row["positive_count"],
                    "negative_count": row["negative_count"],
                    "neutral_count": row["neutral_count"],
                    "total_signals": row["total_signals"],
                },
                "signal_assessments": json.loads(row["signal_assessments"]),
                "univariate_results": json.loads(row["univariate_results"]),
                "multivariate_results": json.loads(row["multivariate_results"]),
                "llm_results": json.loads(row["llm_results"]),
            }
            
        except Exception as e:
            logger.error(f"Failed to get latest correlation result: {e}")
            return None
    
    async def get_results_history(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 10,
    ) -> list[Dict[str, Any]]:
        """
        获取相关性分析结果历史
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            limit: 返回结果数量
        
        Returns:
            分析结果列表
        """
        try:
            client = await self._get_client()
            
            query = f"""
                SELECT *
                FROM correlation_results
                WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
                ORDER BY timestamp DESC
                LIMIT {limit}
            """
            
            results = await client.fetch(query)
            
            return [
                {
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "timestamp": row["timestamp"],
                    "summary": {
                        "positive_count": row["positive_count"],
                        "negative_count": row["negative_count"],
                        "neutral_count": row["neutral_count"],
                        "total_signals": row["total_signals"],
                    },
                    "signal_assessments": json.loads(row["signal_assessments"]),
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to get correlation results history: {e}")
            return []


_storage: Optional[CorrelationStorage] = None


def get_correlation_storage() -> CorrelationStorage:
    """获取存储适配器单例"""
    global _storage
    if _storage is None:
        _storage = CorrelationStorage()
    return _storage
