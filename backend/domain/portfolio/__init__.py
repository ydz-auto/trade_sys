"""
Portfolio Domain - 投资组合领域

核心职责：
1. 管理多策略持仓
2. 敞口管理和风险控制
3. 资金分配
4. 跨策略相关性控制
"""

from .portfolio import Portfolio, PortfolioState, PortfolioMetrics
from .position import Position, PositionSide, PositionStatus
from .exposure_manager import ExposureManager, Exposure, ExposureConfig
from .capital_allocator import CapitalAllocator, CapitalAllocatorConfig, AllocationResult

__all__ = [
    "Portfolio",
    "PortfolioState",
    "PortfolioMetrics",
    "Position",
    "PositionSide",
    "PositionStatus",
    "ExposureManager",
    "Exposure",
    "ExposureConfig",
    "CapitalAllocator",
    "CapitalAllocatorConfig",
    "AllocationResult",
]
