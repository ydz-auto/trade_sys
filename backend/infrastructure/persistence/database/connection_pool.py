"""
数据库连接池配置
"""

from typing import Optional, Dict, Any

from infrastructure.persistence.database.enums import PoolType
from infrastructure.persistence.database.configs import PoolConfig


class ConnectionPool:
    def __init__(self, config: PoolConfig):
        self.config = config
        self._pools: Dict[str, Any] = {}

    async def init_pool(self, name: str, pool: Any):
        self._pools[name] = pool

    async def close_pool(self, name: str):
        if name in self._pools:
            await self._pools[name].close()
            del self._pools[name]

    async def close_all(self):
        for name in list(self._pools.keys()):
            await self.close_pool(name)

    def get_pool(self, name: str) -> Optional[Any]:
        return self._pools.get(name)

    @property
    def pools(self) -> Dict[str, Any]:
        return self._pools


_pool_instance: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    global _pool_instance
    if _pool_instance is None:
        from infrastructure.persistence.database.configs import DatabaseConfig
        db_config = DatabaseConfig()
        _pool_instance = ConnectionPool(PoolConfig(
            pool_type="default",
            host=db_config.host,
            port=db_config.port,
            database=db_config.database,
        ))
    return _pool_instance