"""
State 基础设施类型定义

仅包含基础设施层的状态存储分类类型。
领域模型类型已迁移至 domain.state.types。
"""

from enum import Enum
from typing import Dict, Any

from domain.state.types import (
    SystemState,
    TradingState,
    RiskState,
    PortfolioState,
)


class StateType(str, Enum):
    SYSTEM = "system"
    TRADING = "trading"
    POSITION = "position"
    ORDER = "order"
    MARKET = "market"
    RISK = "risk"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"


STATE_DEFAULTS: Dict[StateType, Dict[str, Any]] = {
    StateType.SYSTEM: SystemState().to_dict(),
    StateType.TRADING: TradingState().to_dict(),
    StateType.RISK: RiskState().to_dict(),
    StateType.POSITION: {},
    StateType.ORDER: {},
    StateType.MARKET: {},
    StateType.STRATEGY: {},
    StateType.PORTFOLIO: PortfolioState().to_dict(),
}


STATE_HISTORY_SIZE = 100
STATE_SNAPSHOT_INTERVAL = 60
