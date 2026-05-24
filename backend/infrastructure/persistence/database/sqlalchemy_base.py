"""
SQLAlchemy Base - 关系型数据库 ORM 支持
使用 SQLAlchemy 2.0 异步引擎
"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from infrastructure.persistence.database.configs import DatabaseConfig


class Base(DeclarativeBase):
    pass


class SQLAlchemyManager:
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def create_engine(self) -> AsyncEngine:
        url = (
            f"postgresql+asyncpg://"
            f"{self.config.username}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{self.config.database}"
        )
        
        return create_async_engine(
            url,
            echo=self.config.echo,
            pool_size=self.config.min_connections,
            max_overflow=self.config.max_connections - self.config.min_connections,
            poolclass=NullPool if self.config.pool_size == 0 else None,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    async def initialize(self) -> None:
        if self._engine is not None:
            return

        self._engine = self.create_engine()
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        from domain.models import user, api_key, trading, strategy_params

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session_factory is None:
            await self.initialize()

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session() as session:
            yield session


_sqlalchemy_manager: Optional[SQLAlchemyManager] = None


def get_sqlalchemy_manager(config: Optional[DatabaseConfig] = None) -> SQLAlchemyManager:
    global _sqlalchemy_manager
    if _sqlalchemy_manager is None:
        _sqlalchemy_manager = SQLAlchemyManager(config)
    return _sqlalchemy_manager


async def init_sqlalchemy(config: Optional[DatabaseConfig] = None) -> SQLAlchemyManager:
    manager = get_sqlalchemy_manager(config)
    await manager.initialize()
    return manager


async def close_sqlalchemy() -> None:
    global _sqlalchemy_manager
    if _sqlalchemy_manager:
        await _sqlalchemy_manager.close()
        _sqlalchemy_manager = None
