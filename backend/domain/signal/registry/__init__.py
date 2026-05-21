"""
Signal Registry - 信号注册表

因为现在有统一的信号模型，需要一个注册表来管理所有信号。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from collections import defaultdict

from domain.signal.models import Signal, SignalDirection, SignalState, SignalType


@dataclass
class SignalQuery:
    """信号查询条件"""
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    direction: Optional[SignalDirection] = None
    state: Optional[SignalState] = None
    signal_type: Optional[SignalType] = None
    strategy_id: Optional[str] = None
    min_confidence: Optional[float] = None
    min_strength: Optional[float] = None
    only_active: bool = False


class SignalRegistry:
    """信号注册表 - 集中管理所有信号"""
    
    def __init__(self):
        self.signals: Dict[UUID, Signal] = {}
        self.signals_by_symbol: Dict[str, List[UUID]] = defaultdict(list)
        self.signals_by_strategy: Dict[str, List[UUID]] = defaultdict(list)
        self.signals_by_type: Dict[SignalType, List[UUID]] = defaultdict(list)
    
    def register(self, signal: Signal) -> None:
        """注册信号"""
        self.signals[signal.signal_id] = signal
        
        self.signals_by_symbol[signal.symbol].append(signal.signal_id)
        
        if signal.strategy_id:
            self.signals_by_strategy[signal.strategy_id].append(signal.signal_id)
        
        self.signals_by_type[signal.type].append(signal.signal_id)
    
    def get(self, signal_id: UUID) -> Optional[Signal]:
        """获取信号"""
        return self.signals.get(signal_id)
    
    def query(self, query: SignalQuery) -> List[Signal]:
        """查询信号"""
        results = []
        
        for signal in self.signals.values():
            if query.symbol and signal.symbol != query.symbol:
                continue
            if query.timeframe and signal.timeframe != query.timeframe:
                continue
            if query.direction and signal.direction != query.direction:
                continue
            if query.state and signal.state != query.state:
                continue
            if query.signal_type and signal.type != query.signal_type:
                continue
            if query.strategy_id and signal.strategy_id != query.strategy_id:
                continue
            if query.min_confidence and signal.confidence.value < query.min_confidence:
                continue
            if query.min_strength and signal.strength.magnitude < query.min_strength:
                continue
            if query.only_active and not signal.is_active():
                continue
            
            results.append(signal)
        
        return results
    
    def get_active_signals(self, symbol: Optional[str] = None) -> List[Signal]:
        """获取活跃信号"""
        query = SignalQuery(only_active=True, symbol=symbol)
        return self.query(query)
    
    def get_signals_by_strategy(self, strategy_id: str) -> List[Signal]:
        """获取策略的所有信号"""
        signal_ids = self.signals_by_strategy.get(strategy_id, [])
        return [self.signals[s_id] for s_id in signal_ids if s_id in self.signals]
    
    def get_signals_by_symbol(self, symbol: str) -> List[Signal]:
        """获取交易对的所有信号"""
        signal_ids = self.signals_by_symbol.get(symbol, [])
        return [self.signals[s_id] for s_id in signal_ids if s_id in self.signals]
    
    def update(self, signal: Signal) -> bool:
        """更新信号"""
        if signal.signal_id not in self.signals:
            return False
        self.signals[signal.signal_id] = signal
        return True
    
    def remove(self, signal_id: UUID) -> bool:
        """移除信号"""
        signal = self.signals.get(signal_id)
        if not signal:
            return False
        
        del self.signals[signal_id]
        
        if signal.symbol in self.signals_by_symbol:
            self.signals_by_symbol[signal.symbol] = [
                s_id for s_id in self.signals_by_symbol[signal.symbol]
                if s_id != signal_id
            ]
        
        if signal.strategy_id and signal.strategy_id in self.signals_by_strategy:
            self.signals_by_strategy[signal.strategy_id] = [
                s_id for s_id in self.signals_by_strategy[signal.strategy_id]
                if s_id != signal_id
            ]
        
        if signal.type in self.signals_by_type:
            self.signals_by_type[signal.type] = [
                s_id for s_id in self.signals_by_type[signal.type]
                if s_id != signal_id
            ]
        
        return True
    
    def cleanup_expired(self) -> int:
        """清理过期信号"""
        expired_ids = [
            s_id for s_id, signal in self.signals.items()
            if signal.is_expired()
        ]
        
        for s_id in expired_ids:
            self.remove(s_id)
        
        return len(expired_ids)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计"""
        active = 0
        pending = 0
        expired = 0
        by_type = defaultdict(int)
        by_direction = defaultdict(int)
        
        for signal in self.signals.values():
            if signal.state == SignalState.ACTIVE and signal.is_active():
                active += 1
            elif signal.state == SignalState.PENDING:
                pending += 1
            elif signal.state == SignalState.EXPIRED or signal.is_expired():
                expired += 1
            
            by_type[signal.type.value] += 1
            by_direction[signal.direction.value] += 1
        
        return {
            "total": len(self.signals),
            "active": active,
            "pending": pending,
            "expired": expired,
            "by_type": dict(by_type),
            "by_direction": dict(by_direction),
        }
    
    def clear(self) -> None:
        """清空注册表"""
        self.signals.clear()
        self.signals_by_symbol.clear()
        self.signals_by_strategy.clear()
        self.signals_by_type.clear()
