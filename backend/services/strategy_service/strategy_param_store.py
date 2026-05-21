"""
Strategy Parameter Store - 策略参数持久化存储

支持：
1. Redis 缓存 + 数据库持久化（双重持久化）
2. 每个币种独立的策略参数
3. 历史数据特征范围配置
4. 参数版本管理

存储策略：
- Redis: 热数据缓存，快速读取
- 数据库: 持久化存储，历史版本，审计
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from enum import Enum

from infrastructure.cache.redis_client import get_redis_client, RedisClient
from infrastructure.logging import get_logger

logger = get_logger("strategy_param_store")


class ParamSource(Enum):
    """参数来源"""
    DEFAULT = "default"
    USER_DEFINED = "user_defined"
    OPTIMIZED = "optimized"
    IMPORTED = "imported"


@dataclass
class FeatureRange:
    """历史数据特征范围"""
    start_date: str = ""
    end_date: str = ""
    volatility_range: str = "all"
    trend_range: str = "all"
    volume_profile: str = "all"
    funding_range: str = "all"
    custom_filters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureRange':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StrategyParameters:
    """策略参数"""
    strategy_id: str
    symbol: str
    
    enabled: bool = True
    weight: float = 1.0
    
    entry_params: Dict[str, Any] = field(default_factory=dict)
    exit_params: Dict[str, Any] = field(default_factory=dict)
    risk_params: Dict[str, Any] = field(default_factory=dict)
    
    feature_range: FeatureRange = field(default_factory=FeatureRange)
    
    source: str = ParamSource.DEFAULT.value
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if isinstance(self.feature_range, dict):
            self.feature_range = FeatureRange.from_dict(self.feature_range)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['feature_range'] = self.feature_range.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyParameters':
        if 'feature_range' in data and isinstance(data['feature_range'], dict):
            data['feature_range'] = FeatureRange.from_dict(data['feature_range'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_db_model(cls, model) -> 'StrategyParameters':
        """从数据库模型创建"""
        return cls(
            strategy_id=model.strategy_id,
            symbol=model.symbol,
            enabled=model.enabled,
            weight=float(model.weight) if model.weight else 1.0,
            entry_params=model.entry_params or {},
            exit_params=model.exit_params or {},
            risk_params=model.risk_params or {},
            feature_range=FeatureRange.from_dict(model.feature_range or {}),
            source=model.source,
            version=model.version,
            created_at=model.created_at.isoformat() if model.created_at else "",
            updated_at=model.updated_at.isoformat() if model.updated_at else "",
            updated_by=model.updated_by or "",
            metadata=model.metadata or {},
        )


class StrategyParamStore:
    """
    策略参数存储
    
    双重持久化策略：
    1. Redis: 热数据缓存，快速读取
    2. 数据库: 持久化存储，历史版本
    
    读取顺序：Redis -> 数据库 -> 返回默认值
    写入顺序：数据库 -> Redis
    """
    
    KEY_PREFIX = "strategy:param"
    SYMBOL_KEY_PREFIX = "strategy:symbol"
    VERSION_KEY_PREFIX = "strategy:version"
    
    CACHE_TTL = 86400
    
    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        use_database: bool = True
    ):
        self._redis = redis_client
        self._local_cache: Dict[str, StrategyParameters] = {}
        self._use_database = use_database
        self._repository = None
    
    async def _get_redis(self) -> RedisClient:
        if self._redis is None:
            self._redis = get_redis_client()
            if not self._redis.is_connected:
                await self._redis.connect()
        return self._redis
    
    def _get_repository(self):
        """获取数据库存储层"""
        if self._repository is None and self._use_database:
            from services.strategy_service.strategy_param_repository import get_strategy_param_repository
            self._repository = get_strategy_param_repository()
        return self._repository
    
    def _make_param_key(self, symbol: str, strategy_id: str) -> str:
        return f"{self.KEY_PREFIX}:{symbol.upper()}:{strategy_id}"
    
    def _make_symbol_key(self, symbol: str) -> str:
        return f"{self.SYMBOL_KEY_PREFIX}:{symbol.upper()}"
    
    def _make_version_key(self, symbol: str, strategy_id: str, version: int) -> str:
        return f"{self.VERSION_KEY_PREFIX}:{symbol.upper()}:{strategy_id}:{version}"
    
    async def get_param(
        self,
        symbol: str,
        strategy_id: str,
        use_cache: bool = True
    ) -> Optional[StrategyParameters]:
        """
        获取策略参数
        
        读取顺序：本地缓存 -> Redis -> 数据库
        """
        cache_key = f"{symbol}_{strategy_id}"
        
        if use_cache and cache_key in self._local_cache:
            return self._local_cache[cache_key]
        
        redis_key = self._make_param_key(symbol, strategy_id)
        
        try:
            redis = await self._get_redis()
            data = await redis.get_json(redis_key)
            
            if data:
                params = StrategyParameters.from_dict(data)
                if use_cache:
                    self._local_cache[cache_key] = params
                return params
            
            if self._use_database:
                repo = self._get_repository()
                if repo:
                    db_param = await repo.get_param(symbol, strategy_id)
                    if db_param:
                        params = StrategyParameters.from_db_model(db_param)
                        await redis.set_json(redis_key, params.to_dict(), ex=self.CACHE_TTL)
                        if use_cache:
                            self._local_cache[cache_key] = params
                        return params
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get param: {e}")
            if self._use_database:
                repo = self._get_repository()
                if repo:
                    try:
                        db_param = await repo.get_param(symbol, strategy_id)
                        if db_param:
                            return StrategyParameters.from_db_model(db_param)
                    except Exception as db_e:
                        logger.error(f"Database fallback failed: {db_e}")
            return self._local_cache.get(cache_key)
    
    async def set_param(
        self,
        params: StrategyParameters,
        persist_version: bool = True,
        change_reason: str = None
    ) -> bool:
        """
        保存策略参数
        
        写入顺序：数据库 -> Redis
        """
        params.updated_at = datetime.now().isoformat()
        
        cache_key = f"{params.symbol}_{params.strategy_id}"
        self._local_cache[cache_key] = params
        
        success = True
        
        if self._use_database:
            repo = self._get_repository()
            if repo:
                try:
                    data = params.to_dict()
                    data["change_reason"] = change_reason
                    db_param = await repo.set_param(
                        params.symbol,
                        params.strategy_id,
                        data,
                        save_history=persist_version
                    )
                    params.version = db_param.version
                except Exception as e:
                    logger.error(f"Failed to save to database: {e}")
                    success = False
        
        redis_key = self._make_param_key(params.symbol, params.strategy_id)
        
        try:
            redis = await self._get_redis()
            await redis.set_json(redis_key, params.to_dict(), ex=self.CACHE_TTL)
            
            logger.info(f"Saved strategy param: {params.symbol}/{params.strategy_id} v{params.version}")
            
        except Exception as e:
            logger.error(f"Failed to save to Redis: {e}")
            if success:
                success = False
        
        return success
    
    async def delete_param(self, symbol: str, strategy_id: str) -> bool:
        """删除策略参数"""
        cache_key = f"{symbol}_{strategy_id}"
        if cache_key in self._local_cache:
            del self._local_cache[cache_key]
        
        success = True
        
        if self._use_database:
            repo = self._get_repository()
            if repo:
                try:
                    await repo.delete_param(symbol, strategy_id)
                except Exception as e:
                    logger.error(f"Failed to delete from database: {e}")
                    success = False
        
        redis_key = self._make_param_key(symbol, strategy_id)
        
        try:
            redis = await self._get_redis()
            await redis.delete(redis_key)
        except Exception as e:
            logger.error(f"Failed to delete from Redis: {e}")
            if success:
                success = False
        
        return success
    
    async def get_symbol_params(self, symbol: str) -> List[StrategyParameters]:
        """获取币种的所有策略参数"""
        if self._use_database:
            repo = self._get_repository()
            if repo:
                try:
                    db_params = await repo.get_symbol_params(symbol)
                    return [StrategyParameters.from_db_model(p) for p in db_params]
                except Exception as e:
                    logger.error(f"Failed to get symbol params from database: {e}")
        
        try:
            redis = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:{symbol.upper()}:*"
            
            keys = []
            cursor = 0
            while True:
                cursor, batch = await redis.client.scan(
                    cursor, match=pattern, count=100
                )
                keys.extend(batch)
                if cursor == 0:
                    break
            
            params_list = []
            for key in keys:
                data = await redis.get_json(key)
                if data:
                    params_list.append(StrategyParameters.from_dict(data))
            
            return params_list
            
        except Exception as e:
            logger.error(f"Failed to get symbol params: {e}")
            return [
                p for k, p in self._local_cache.items()
                if k.startswith(f"{symbol}_")
            ]
    
    async def get_all_params(self) -> List[StrategyParameters]:
        """获取所有策略参数"""
        if self._use_database:
            repo = self._get_repository()
            if repo:
                try:
                    db_params = await repo.get_all_params()
                    return [StrategyParameters.from_db_model(p) for p in db_params]
                except Exception as e:
                    logger.error(f"Failed to get all params from database: {e}")
        
        try:
            redis = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:*"
            
            keys = []
            cursor = 0
            while True:
                cursor, batch = await redis.client.scan(
                    cursor, match=pattern, count=100
                )
                keys.extend(batch)
                if cursor == 0:
                    break
            
            params_list = []
            for key in keys:
                data = await redis.get_json(key)
                if data:
                    params_list.append(StrategyParameters.from_dict(data))
            
            return params_list
            
        except Exception as e:
            logger.error(f"Failed to get all params: {e}")
            return list(self._local_cache.values())
    
    async def update_feature_range(
        self,
        symbol: str,
        strategy_id: str,
        feature_range: FeatureRange
    ) -> Optional[StrategyParameters]:
        """更新历史数据特征范围"""
        params = await self.get_param(symbol, strategy_id)
        
        if params is None:
            params = StrategyParameters(
                strategy_id=strategy_id,
                symbol=symbol,
                feature_range=feature_range,
                source=ParamSource.USER_DEFINED.value
            )
        else:
            params.feature_range = feature_range
            params.version += 1
        
        success = await self.set_param(params, change_reason="Update feature range")
        return params if success else None
    
    async def batch_update_params(
        self,
        updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量更新参数"""
        if self._use_database:
            repo = self._get_repository()
            if repo:
                return await repo.batch_update(updates)
        
        results = {"success": 0, "failed": 0, "errors": []}
        
        for update in updates:
            try:
                symbol = update.get("symbol")
                strategy_id = update.get("strategy_id")
                param_updates = update.get("params", {})
                
                params = await self.get_param(symbol, strategy_id)
                
                if params is None:
                    params = StrategyParameters(
                        strategy_id=strategy_id,
                        symbol=symbol
                    )
                
                for key, value in param_updates.items():
                    if hasattr(params, key):
                        setattr(params, key, value)
                
                params.version += 1
                params.source = ParamSource.USER_DEFINED.value
                
                success = await self.set_param(params)
                
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "symbol": update.get("symbol"),
                    "strategy_id": update.get("strategy_id"),
                    "error": str(e)
                })
        
        return results
    
    async def get_param_history(
        self,
        symbol: str,
        strategy_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取参数历史版本"""
        if self._use_database:
            repo = self._get_repository()
            if repo:
                try:
                    history = await repo.get_param_history(symbol, strategy_id, limit)
                    return [h.to_dict() for h in history]
                except Exception as e:
                    logger.error(f"Failed to get param history from database: {e}")
        
        try:
            redis = await self._get_redis()
            pattern = f"{self.VERSION_KEY_PREFIX}:{symbol.upper()}:{strategy_id}:*"
            
            keys = []
            cursor = 0
            while True:
                cursor, batch = await redis.client.scan(
                    cursor, match=pattern, count=100
                )
                keys.extend(batch)
                if cursor == 0:
                    break
            
            versions = []
            for key in keys:
                data = await redis.get_json(key)
                if data:
                    versions.append(data)
            
            versions.sort(key=lambda x: x.get("version", 0), reverse=True)
            return versions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get param history: {e}")
            return []
    
    async def restore_version(
        self,
        symbol: str,
        strategy_id: str,
        version: int
    ) -> Optional[StrategyParameters]:
        """恢复到指定版本"""
        if self._use_database:
            repo = self._get_repository()
            if repo:
                try:
                    db_param = await repo.restore_version(symbol, strategy_id, version)
                    if db_param:
                        params = StrategyParameters.from_db_model(db_param)
                        cache_key = f"{symbol}_{strategy_id}"
                        self._local_cache[cache_key] = params
                        
                        redis = await self._get_redis()
                        redis_key = self._make_param_key(symbol, strategy_id)
                        await redis.set_json(redis_key, params.to_dict(), ex=self.CACHE_TTL)
                        
                        return params
                except Exception as e:
                    logger.error(f"Failed to restore version from database: {e}")
        
        version_key = self._make_version_key(symbol, strategy_id, version)
        
        try:
            redis = await self._get_redis()
            data = await redis.get_json(version_key)
            
            if not data:
                logger.error(f"Version {version} not found")
                return None
            
            params = StrategyParameters.from_dict(data)
            params.version += 1
            params.source = ParamSource.USER_DEFINED.value
            
            success = await self.set_param(params)
            return params if success else None
            
        except Exception as e:
            logger.error(f"Failed to restore version: {e}")
            return None
    
    def invalidate_cache(self, symbol: Optional[str] = None):
        """清除缓存"""
        if symbol:
            keys_to_remove = [
                k for k in self._local_cache.keys()
                if k.startswith(f"{symbol}_")
            ]
            for k in keys_to_remove:
                del self._local_cache[k]
        else:
            self._local_cache.clear()


_param_store: Optional[StrategyParamStore] = None


def get_strategy_param_store(use_database: bool = True) -> StrategyParamStore:
    """获取策略参数存储单例"""
    global _param_store
    if _param_store is None:
        _param_store = StrategyParamStore(use_database=use_database)
    return _param_store
