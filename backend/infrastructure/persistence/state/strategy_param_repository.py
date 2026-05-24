"""
Strategy Parameter Repository - 策略参数数据库存储层

提供策略参数的数据库 CRUD 操作
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.strategy_params import (
    StrategyParam,
    StrategyParamHistory,
    StrategyConfig,
)
from infrastructure.persistence.database.session import get_db_manager
from infrastructure.logging import get_logger

logger = get_logger("strategy_param_repository")


class StrategyParamRepository:
    """策略参数数据库存储层"""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session
    
    async def get_param(
        self,
        symbol: str,
        strategy_id: str
    ) -> Optional[StrategyParam]:
        """获取策略参数"""
        if self._session:
            stmt = select(StrategyParam).where(
                and_(
                    StrategyParam.symbol == symbol.upper(),
                    StrategyParam.strategy_id == strategy_id
                )
            )
            result = await self._session.execute(stmt)
            return result.scalar_one_or_none()
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                stmt = select(StrategyParam).where(
                    and_(
                        StrategyParam.symbol == symbol.upper(),
                        StrategyParam.strategy_id == strategy_id
                    )
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
    
    async def get_param_dict(
        self,
        symbol: str,
        strategy_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取策略参数（字典格式）"""
        param = await self.get_param(symbol, strategy_id)
        return param.to_dict() if param else None
    
    async def set_param(
        self,
        symbol: str,
        strategy_id: str,
        data: Dict[str, Any],
        save_history: bool = True
    ) -> StrategyParam:
        """保存策略参数"""
        if self._session:
            return await self._set_param_with_session(
                self._session, symbol, strategy_id, data, save_history
            )
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                return await self._set_param_with_session(
                    session, symbol, strategy_id, data, save_history
                )
    
    async def _set_param_with_session(
        self,
        session: AsyncSession,
        symbol: str,
        strategy_id: str,
        data: Dict[str, Any],
        save_history: bool
    ) -> StrategyParam:
        """使用指定 session 保存参数"""
        stmt = select(StrategyParam).where(
            and_(
                StrategyParam.symbol == symbol.upper(),
                StrategyParam.strategy_id == strategy_id
            )
        )
        result = await session.execute(stmt)
        param = result.scalar_one_or_none()
        
        if param:
            if save_history:
                history = StrategyParamHistory(
                    param_id=param.id,
                    strategy_id=param.strategy_id,
                    symbol=param.symbol,
                    version=param.version,
                    enabled=param.enabled,
                    weight=param.weight,
                    entry_params=param.entry_params,
                    exit_params=param.exit_params,
                    risk_params=param.risk_params,
                    feature_range=param.feature_range,
                    source=param.source,
                    metadata=param.metadata,
                    change_reason=data.get("change_reason"),
                    created_by=data.get("updated_by"),
                )
                session.add(history)
            
            param.enabled = data.get("enabled", param.enabled)
            param.weight = data.get("weight", param.weight)
            param.entry_params = data.get("entry_params", param.entry_params)
            param.exit_params = data.get("exit_params", param.exit_params)
            param.risk_params = data.get("risk_params", param.risk_params)
            param.feature_range = data.get("feature_range", param.feature_range)
            param.source = data.get("source", param.source)
            param.metadata = data.get("metadata", param.metadata)
            param.updated_by = data.get("updated_by")
            param.version = param.version + 1
            param.updated_at = datetime.utcnow()
        else:
            param = StrategyParam(
                strategy_id=strategy_id,
                symbol=symbol.upper(),
                enabled=data.get("enabled", True),
                weight=data.get("weight", 1.0),
                entry_params=data.get("entry_params"),
                exit_params=data.get("exit_params"),
                risk_params=data.get("risk_params"),
                feature_range=data.get("feature_range"),
                source=data.get("source", "default"),
                version=1,
                metadata=data.get("metadata"),
                updated_by=data.get("updated_by"),
            )
            session.add(param)
        
        await session.commit()
        await session.refresh(param)
        
        logger.info(f"Saved strategy param: {symbol}/{strategy_id} v{param.version}")
        return param
    
    async def delete_param(self, symbol: str, strategy_id: str) -> bool:
        """删除策略参数"""
        if self._session:
            return await self._delete_param_with_session(
                self._session, symbol, strategy_id
            )
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                return await self._delete_param_with_session(
                    session, symbol, strategy_id
                )
    
    async def _delete_param_with_session(
        self,
        session: AsyncSession,
        symbol: str,
        strategy_id: str
    ) -> bool:
        """使用指定 session 删除参数"""
        stmt = select(StrategyParam).where(
            and_(
                StrategyParam.symbol == symbol.upper(),
                StrategyParam.strategy_id == strategy_id
            )
        )
        result = await session.execute(stmt)
        param = result.scalar_one_or_none()
        
        if param:
            await session.delete(param)
            await session.commit()
            return True
        return False
    
    async def get_symbol_params(self, symbol: str) -> List[StrategyParam]:
        """获取币种的所有策略参数"""
        if self._session:
            stmt = select(StrategyParam).where(
                StrategyParam.symbol == symbol.upper()
            )
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                stmt = select(StrategyParam).where(
                    StrategyParam.symbol == symbol.upper()
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
    
    async def get_all_params(self) -> List[StrategyParam]:
        """获取所有策略参数"""
        if self._session:
            stmt = select(StrategyParam)
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                stmt = select(StrategyParam)
                result = await session.execute(stmt)
                return list(result.scalars().all())
    
    async def get_param_history(
        self,
        symbol: str,
        strategy_id: str,
        limit: int = 10
    ) -> List[StrategyParamHistory]:
        """获取参数历史版本"""
        if self._session:
            stmt = select(StrategyParamHistory).where(
                and_(
                    StrategyParamHistory.symbol == symbol.upper(),
                    StrategyParamHistory.strategy_id == strategy_id
                )
            ).order_by(desc(StrategyParamHistory.version)).limit(limit)
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                stmt = select(StrategyParamHistory).where(
                    and_(
                        StrategyParamHistory.symbol == symbol.upper(),
                        StrategyParamHistory.strategy_id == strategy_id
                    )
                ).order_by(desc(StrategyParamHistory.version)).limit(limit)
                result = await session.execute(stmt)
                return list(result.scalars().all())
    
    async def restore_version(
        self,
        symbol: str,
        strategy_id: str,
        version: int
    ) -> Optional[StrategyParam]:
        """恢复到指定版本"""
        if self._session:
            history = await self._get_history_by_version(
                self._session, symbol, strategy_id, version
            )
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                history = await self._get_history_by_version(
                    session, symbol, strategy_id, version
                )
        
        if not history:
            return None
        
        data = {
            "enabled": history.enabled,
            "weight": float(history.weight) if history.weight else 1.0,
            "entry_params": history.entry_params,
            "exit_params": history.exit_params,
            "risk_params": history.risk_params,
            "feature_range": history.feature_range,
            "source": history.source,
            "metadata": history.metadata,
            "change_reason": f"Restored from version {version}",
        }
        
        return await self.set_param(symbol, strategy_id, data, save_history=True)
    
    async def _get_history_by_version(
        self,
        session: AsyncSession,
        symbol: str,
        strategy_id: str,
        version: int
    ) -> Optional[StrategyParamHistory]:
        """获取指定版本的历史记录"""
        stmt = select(StrategyParamHistory).where(
            and_(
                StrategyParamHistory.symbol == symbol.upper(),
                StrategyParamHistory.strategy_id == strategy_id,
                StrategyParamHistory.version == version
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def batch_update(
        self,
        updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量更新参数"""
        results = {"success": 0, "failed": 0, "errors": []}
        
        for update in updates:
            try:
                symbol = update.get("symbol")
                strategy_id = update.get("strategy_id")
                params = update.get("params", {})
                
                await self.set_param(symbol, strategy_id, params)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "symbol": update.get("symbol"),
                    "strategy_id": update.get("strategy_id"),
                    "error": str(e)
                })
        
        return results
    
    async def get_strategy_config(self, strategy_id: str) -> Optional[StrategyConfig]:
        """获取策略配置"""
        if self._session:
            stmt = select(StrategyConfig).where(
                StrategyConfig.strategy_id == strategy_id
            )
            result = await self._session.execute(stmt)
            return result.scalar_one_or_none()
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                stmt = select(StrategyConfig).where(
                    StrategyConfig.strategy_id == strategy_id
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
    
    async def get_all_strategy_configs(self) -> List[StrategyConfig]:
        """获取所有策略配置"""
        if self._session:
            stmt = select(StrategyConfig).where(
                StrategyConfig.is_active == True
            )
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        else:
            db_manager = get_db_manager()
            async with db_manager.session() as session:
                stmt = select(StrategyConfig).where(
                    StrategyConfig.is_active == True
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())


_repository: Optional[StrategyParamRepository] = None


def get_strategy_param_repository(session: Optional[AsyncSession] = None) -> StrategyParamRepository:
    """获取策略参数存储层单例"""
    global _repository
    if _repository is None:
        _repository = StrategyParamRepository(session)
    return _repository
