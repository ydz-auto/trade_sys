"""
Common Types - 通用类型定义

定义研究工具使用的基础数据类型和常量。
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceData:
    """价格数据"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class SignalRecord:
    """信号记录"""
    timestamp: int
    symbol: str
    strategy: str
    signal_type: str  # 'long', 'short', 'none'
    confidence: float
    reason: str
    additional_info: Dict[str, Any] = None


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: int
    symbol: str
    strategy: str
    direction: str  # 'long', 'short'
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    holding_bars: int


@dataclass
class BacktestConfig:
    """回测配置"""
    maker_fee: float = 0.0002
    taker_fee: float = 0.0005
    slippage_bps: float = 2.0
    max_holding_bars: int = 10


@dataclass
class WalkForwardConfig:
    """滚动验证配置"""
    train_period_days: int = 30
    test_period_days: int = 7
    gap_days: int = 0
    max_workers: Optional[int] = None


@dataclass
class EventStudyConfig:
    """事件研究配置"""
    forward_windows: List[int] = None
    
    def __post_init__(self):
        if self.forward_windows is None:
            self.forward_windows = [1, 3, 5, 10]


@dataclass
class ValidationResult:
    """验证结果基类"""
    strategy: str
    symbol: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy': self.strategy,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
        }


class StrategyName:
    """策略名称常量"""
    SHORT_SQUEEZE = 'short_squeeze'
    OI_BEHAVIOR = 'oi_behavior'
    FUNDING_EXTREME_REVERSAL = 'funding_extreme_reversal'
    LIQUIDATION_CASCADE = 'liquidation_cascade'
    TRADE_PRESSURE_BOUNCE = 'trade_pressure_bounce'
    
    ALL = [
        SHORT_SQUEEZE,
        OI_BEHAVIOR,
        FUNDING_EXTREME_REVERSAL,
        LIQUIDATION_CASCADE,
        TRADE_PRESSURE_BOUNCE,
    ]


__all__ = [
    'PriceData',
    'SignalRecord',
    'TradeRecord',
    'BacktestConfig',
    'WalkForwardConfig',
    'EventStudyConfig',
    'ValidationResult',
    'StrategyName',
]
