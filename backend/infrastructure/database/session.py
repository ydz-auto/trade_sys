"""
Database Session Manager

数据库会话管理
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from infrastructure.database.configs import DatabaseConfig
from infrastructure.database.sqlalchemy_base import Base

logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config
        self._engine = None
        self._session_factory = None

    async def initialize(self) -> None:
        """初始化数据库连接"""
        if self._engine is not None:
            return

        config = self.config or DatabaseConfig()
        url = f"postgresql+asyncpg://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"

        self._engine = create_async_engine(
            url,
            pool_size=config.min_connections,
            max_overflow=config.max_connections - config.min_connections,
            poolclass=NullPool if config.min_connections == 0 else None,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info(f"Database engine initialized: {config.host}:{config.port}/{config.database}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database engine closed")

    async def create_tables(self) -> None:
        """创建所有表"""
        if self._engine is None:
            await self.initialize()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    @asynccontextmanager
    async def session(self):
        """获取数据库会话上下文管理器"""
        if self._session_factory is None:
            await self.initialize()

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_session(self) -> AsyncSession:
        """获取数据库会话（需手动关闭）"""
        if self._session_factory is None:
            await self.initialize()
        return self._session_factory()


_db_manager: Optional[DatabaseSessionManager] = None


def get_db_manager(config: Optional[DatabaseConfig] = None) -> DatabaseSessionManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseSessionManager(config)
    return _db_manager


async def init_db(config: Optional[DatabaseConfig] = None) -> DatabaseSessionManager:
    manager = get_db_manager(config)
    await manager.initialize()
    return manager


async def close_db() -> None:
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None
