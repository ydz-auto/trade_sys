"""
Feature Matrix Runtime - 特征矩阵运行时

核心功能：
- 实时特征矩阵管理
- 多交易对支持
- 与replay runtime集成
"""

from typing import Dict, Optional
from pathlib import Path
import asyncio

from infrastructure.logging import get_logger
from domain.feature.materializer import (
    RealtimeFeatureMaterializer,
    UnifiedFeatureMatrix
)

logger = get_logger("runtime.feature_matrix")

DATA_LAKE_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake")


class FeatureMatrixRuntime:
    """特征矩阵运行时"""
    
    def __init__(self):
        self._materializers: Dict[str, RealtimeFeatureMaterializer] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def get_or_create_materializer(
        self,
        symbol: str,
        interval_ms: int = 60000,
        window_size: int = 60
    ) -> RealtimeFeatureMaterializer:
        """获取或创建实时物化器"""
        if symbol not in self._materializers:
            self._materializers[symbol] = RealtimeFeatureMaterializer(
                symbol=symbol,
                interval_ms=interval_ms,
                window_size=window_size
            )
        return self._materializers[symbol]
    
    def get_realtime_matrix(self, symbol: str) -> Optional[UnifiedFeatureMatrix]:
        """获取实时特征矩阵"""
        if symbol not in self._materializers:
            return None
        return self._materializers[symbol].get_current_matrix()
    
    def update_trades(self, symbol: str, trades_df):
        """更新交易数据"""
        mat = self.get_or_create_materializer(symbol)
        mat.update_trades(trades_df)
    
    def update_oi(self, symbol: str, oi_df):
        """更新持仓数据"""
        mat = self.get_or_create_materializer(symbol)
        mat.update_oi(oi_df)
    
    def update_funding(self, symbol: str, funding_df):
        """更新资金费率"""
        mat = self.get_or_create_materializer(symbol)
        mat.update_funding(funding_df)
    
    def update_liquidation(self, symbol: str, liq_df):
        """更新清算数据"""
        mat = self.get_or_create_materializer(symbol)
        mat.update_liquidation(liq_df)
    
    async def start(self):
        """启动运行时"""
        if self._running:
            return
        
        self._running = True
        logger.info("Feature Matrix Runtime started")
    
    async def stop(self):
        """停止运行时"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Feature Matrix Runtime stopped")


# 全局实例
_feature_matrix_runtime: Optional[FeatureMatrixRuntime] = None


def get_feature_matrix_runtime() -> FeatureMatrixRuntime:
    """获取特征矩阵运行时"""
    global _feature_matrix_runtime
    if _feature_matrix_runtime is None:
        _feature_matrix_runtime = FeatureMatrixRuntime()
    return _feature_matrix_runtime

