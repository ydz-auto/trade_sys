"""
Strategy State Management - 策略状态管理模块

管理策略实例的运行时状态，包括：
- 策略启用/禁用状态
- 策略特定的历史状态（如RSI、MACD等的前值）
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class StrategyInstanceState:
    """单个策略实例的完整状态"""
    strategy_id: str
    symbol: str
    
    # 基础状态
    enabled: bool = True
    
    # 策略特定状态（针对不同策略类型）
    # RSI 策略
    prev_rsi: Optional[float] = None
    
    # MACD 策略
    prev_macd: Optional[float] = None
    prev_signal: Optional[float] = None
    
    # Trend 策略
    prev_ema_fast: Optional[float] = None
    prev_ema_slow: Optional[float] = None
    
    # Bollinger 策略
    prev_above_middle: Optional[bool] = None
    
    # 流动性真空策略
    avg_spread: Optional[float] = None
    prev_top5_depth: Optional[float] = None
    
    # SMA交叉策略
    sma_fast_prev: Optional[float] = None
    sma_slow_prev: Optional[float] = None
    
    # 布林带普通策略
    price_prev: Optional[float] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at_ms: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    
    def touch(self):
        """更新最后修改时间"""
        self.updated_at_ms = int(datetime.now().timestamp() * 1000)
    
    def update_from_dict(self, state_dict: Dict[str, Any]):
        """从字典更新状态"""
        for key, value in state_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)


class StrategyStateManager:
    """策略状态管理器 - 集中管理所有策略的状态"""
    
    def __init__(self):
        self._states: Dict[str, StrategyInstanceState] = {}
    
    def get_or_create_state(self, strategy_id: str, symbol: str) -> StrategyInstanceState:
        """获取或创建策略状态"""
        key = self._make_key(strategy_id, symbol)
        if key not in self._states:
            self._states[key] = StrategyInstanceState(
                strategy_id=strategy_id,
                symbol=symbol
            )
        return self._states[key]
    
    def get_state(self, strategy_id: str, symbol: str) -> Optional[StrategyInstanceState]:
        """获取策略状态，不存在则返回 None"""
        key = self._make_key(strategy_id, symbol)
        return self._states.get(key)
    
    def update_state(self, strategy_id: str, symbol: str, **kwargs):
        """更新策略状态"""
        state = self.get_or_create_state(strategy_id, symbol)
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.touch()
    
    def list_all_states(self) -> list[StrategyInstanceState]:
        """列出所有策略状态"""
        return list(self._states.values())
    
    def clear_all_states(self):
        """清除所有状态"""
        self._states.clear()
    
    @staticmethod
    def _make_key(strategy_id: str, symbol: str) -> str:
        """生成状态键"""
        return f"{strategy_id}:{symbol}"
