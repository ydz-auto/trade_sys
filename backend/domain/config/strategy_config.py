"""
策略配置类型
Strategy Configuration Types

定义策略执行所需的所有配置，支持类型安全和参数验证。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class StrategyType(str, Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    LIQUIDATION = "liquidation"
    MICROSTRUCTURE = "microstructure"
    CUSTOM = "custom"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class EntryParams:
    """入场参数配置"""
    signal_threshold: float = 0.5
    max_entries_per_symbol: int = 1
    entry_timeout_seconds: int = 60
    confirmation_required: bool = True


@dataclass
class ExitParams:
    """出场参数配置"""
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    trailing_stop_activation_pct: float = 0.03
    trailing_stop_distance_pct: float = 0.01
    max_hold_minutes: int = 1440


@dataclass
class RiskParams:
    """风险参数配置"""
    position_size_pct: float = 0.1
    max_risk_pct: float = 0.01
    max_drawdown_pct: float = 0.1
    max_positions: int = 5
    max_leverage: int = 5
    enable_stop_loss: bool = True
    enable_take_profit: bool = True


@dataclass(frozen=True)
class StrategyConfigV2:
    """
    策略配置（v2版本 - 类型安全）
    
    核心特性：
    - 强类型配置
    - 不可变（frozen），运行时不可修改
    - 支持完整的参数验证
    - 可序列化
    """
    strategy_id: str
    strategy_name: str
    strategy_type: StrategyType
    
    version: str = "1.0.0"
    is_active: bool = True
    
    # 核心参数
    entry_params: EntryParams = field(default_factory=EntryParams)
    exit_params: ExitParams = field(default_factory=ExitParams)
    risk_params: RiskParams = field(default_factory=RiskParams)
    
    # 支持的标的
    supported_symbols: List[str] = field(default_factory=list)
    supported_timeframes: List[str] = field(default_factory=lambda: ["1m", "5m", "15m"])
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    
    # 扩展参数（用于特定策略的额外配置）
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # 基本验证
        assert self.strategy_id, "strategy_id cannot be empty"
        assert self.strategy_name, "strategy_name cannot be empty"
        assert 0 < self.entry_params.signal_threshold <= 1.0, "signal_threshold must be between 0 and 1"
        assert 0 < self.risk_params.position_size_pct <= 1.0, "position_size_pct must be between 0 and 1"
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type.value,
            "version": self.version,
            "is_active": self.is_active,
            "entry_params": {
                "signal_threshold": self.entry_params.signal_threshold,
                "max_entries_per_symbol": self.entry_params.max_entries_per_symbol,
                "entry_timeout_seconds": self.entry_params.entry_timeout_seconds,
                "confirmation_required": self.entry_params.confirmation_required,
            },
            "exit_params": {
                "stop_loss_pct": self.exit_params.stop_loss_pct,
                "take_profit_pct": self.exit_params.take_profit_pct,
                "trailing_stop_activation_pct": self.exit_params.trailing_stop_activation_pct,
                "trailing_stop_distance_pct": self.exit_params.trailing_stop_distance_pct,
                "max_hold_minutes": self.exit_params.max_hold_minutes,
            },
            "risk_params": {
                "position_size_pct": self.risk_params.position_size_pct,
                "max_risk_pct": self.risk_params.max_risk_pct,
                "max_drawdown_pct": self.risk_params.max_drawdown_pct,
                "max_positions": self.risk_params.max_positions,
                "max_leverage": self.risk_params.max_leverage,
                "enable_stop_loss": self.risk_params.enable_stop_loss,
                "enable_take_profit": self.risk_params.enable_take_profit,
            },
            "supported_symbols": self.supported_symbols,
            "supported_timeframes": self.supported_timeframes,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "extra_params": self.extra_params,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfigV2":
        """从字典创建"""
        entry_params = EntryParams(**data.get("entry_params", {}))
        exit_params = ExitParams(**data.get("exit_params", {}))
        risk_params = RiskParams(**data.get("risk_params", {}))
        
        return cls(
            strategy_id=data["strategy_id"],
            strategy_name=data["strategy_name"],
            strategy_type=StrategyType(data.get("strategy_type", StrategyType.CUSTOM)),
            version=data.get("version", "1.0.0"),
            is_active=data.get("is_active", True),
            entry_params=entry_params,
            exit_params=exit_params,
            risk_params=risk_params,
            supported_symbols=data.get("supported_symbols", []),
            supported_timeframes=data.get("supported_timeframes", ["1m", "5m", "15m"]),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            extra_params=data.get("extra_params", {}),
        )


# 保持向后兼容的别名
StrategyConfig = StrategyConfigV2
