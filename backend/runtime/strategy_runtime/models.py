"""
Strategy Models - 策略运行时数据模型
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, List, Optional
from datetime import datetime


class StrategyType(str, Enum):
    """策略类型"""
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    MICROSTRUCTURE = "microstructure"
    REGIME = "regime"
    MULTI_FACTOR = "multi_factor"
    ML_BASED = "ml_based"


class StrategyStatus(str, Enum):
    """策略状态"""
    INACTIVE = "inactive"
    WARMING_UP = "warming_up"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class StrategyAction(str, Enum):
    """策略动作"""
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    DO_NOTHING = "do_nothing"


@dataclass
class StrategySignal:
    """策略信号"""
    strategy_id: str
    strategy_name: str
    strategy_type: StrategyType
    symbol: str
    action: StrategyAction
    confidence: float
    reason: str
    timestamp_ms: int
    price: Optional[float] = None
    quantity: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        return 0.0 <= self.confidence <= 1.0


@dataclass
class StrategyDefinition:
    """策略定义 - 描述策略的元数据"""
    strategy_id: str
    name: str
    description: str
    strategy_type: StrategyType
    priority: int = 0
    required_features: List[str] = field(default_factory=list)
    supported_symbols: List[str] = field(default_factory=list)
    default_params: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    tier: int = 1  # 1 = 第一梯队, 2 = 第二梯队
    
    # 回测/评估指标
    backtest_sharpe: Optional[float] = None
    backtest_win_rate: Optional[float] = None


@dataclass
class StrategyState:
    """策略运行时状态"""
    strategy_id: str
    status: StrategyStatus
    symbol: str
    last_signal: Optional[StrategySignal] = None
    signals_count: int = 0
    warmup_complete: bool = False
    warmup_progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at_ms: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
