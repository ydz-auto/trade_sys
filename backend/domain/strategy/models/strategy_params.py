"""
Strategy Parameter Models - 策略参数数据库模型

支持：
1. 每个币种独立的策略参数
2. 参数版本历史
3. 特征范围配置
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Boolean, Index, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.persistence.database.sqlalchemy_base import Base


class ParamSource(str, Enum):
    """参数来源"""
    DEFAULT = "default"
    USER_DEFINED = "user_defined"
    OPTIMIZED = "optimized"
    IMPORTED = "imported"


class StrategyParam(Base):
    """
    策略参数表
    
    存储每个币种的策略参数配置
    """
    __tablename__ = "strategy_params"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)
    
    entry_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    exit_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    feature_range: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    source: Mapped[str] = mapped_column(String(20), default=ParamSource.DEFAULT.value)
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    param_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_strategy_params_symbol_strategy", "symbol", "strategy_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<StrategyParam(strategy_id='{self.strategy_id}', symbol='{self.symbol}', version={self.version})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "enabled": self.enabled,
            "weight": float(self.weight) if self.weight else 1.0,
            "entry_params": self.entry_params or {},
            "exit_params": self.exit_params or {},
            "risk_params": self.risk_params or {},
            "feature_range": self.feature_range or {},
            "source": self.source,
            "version": self.version,
            "metadata": self.metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }


class StrategyParamHistory(Base):
    """
    策略参数历史表
    
    存储参数修改历史，用于审计和回滚
    """
    __tablename__ = "strategy_param_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    param_id: Mapped[int] = mapped_column(ForeignKey("strategy_params.id", ondelete="CASCADE"))
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)
    
    entry_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    exit_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    feature_range: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    source: Mapped[str] = mapped_column(String(20), default=ParamSource.DEFAULT.value)
    
    param_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_strategy_param_history_symbol_strategy_version", "symbol", "strategy_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<StrategyParamHistory(strategy_id='{self.strategy_id}', symbol='{self.symbol}', version={self.version})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "param_id": self.param_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "version": self.version,
            "enabled": self.enabled,
            "weight": float(self.weight) if self.weight else 1.0,
            "entry_params": self.entry_params or {},
            "exit_params": self.exit_params or {},
            "risk_params": self.risk_params or {},
            "feature_range": self.feature_range or {},
            "source": self.source,
            "metadata": self.metadata or {},
            "change_reason": self.change_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


class StrategyConfig(Base):
    """
    策略配置表
    
    存储策略的全局配置和元数据
    """
    __tablename__ = "strategy_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    strategy_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    default_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    supported_symbols: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    supported_timeframes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    min_capital: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    max_leverage: Mapped[int] = mapped_column(Integer, default=20)
    
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<StrategyConfig(strategy_id='{self.strategy_id}', name='{self.strategy_name}')>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "description": self.description,
            "default_params": self.default_params or {},
            "supported_symbols": self.supported_symbols or [],
            "supported_timeframes": self.supported_timeframes or [],
            "min_capital": float(self.min_capital) if self.min_capital else None,
            "max_leverage": self.max_leverage,
            "risk_level": self.risk_level,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
