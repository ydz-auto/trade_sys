"""
Cross-Symbol Event Semantics - 跨品种事件语义

核心问题：
当计算 correlation、lead-lag、basis 等跨品种特征时，
不同品种的事件时间可能不同步，导致数据泄漏。

例如：
- BTC 10:15:00 的数据已到达
- ETH 10:15:00 的数据可能还未到达
- 此时计算 BTC-ETH correlation 会泄漏 BTC 的未来信息到 ETH

解决方案：
1. 跟踪每个品种的事件可用时间
2. 跨品种特征必须等待所有品种数据就绪
3. 提供跨品种可用性检查
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from infrastructure.logging import get_logger
from infrastructure.event.event_time import (
    EventTimeManager,
    EventTimeRecord,
    EventSource,
    get_event_time_manager,
)

logger = get_logger("infrastructure.cross_symbol")


@dataclass
class SymbolAvailability:
    """品种可用性状态"""
    symbol: str
    last_exchange_time: int
    last_receive_time: int
    last_available_at: int
    is_ready: bool
    
    pending_events: int = 0
    latency_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "last_exchange_time": self.last_exchange_time,
            "last_receive_time": self.last_receive_time,
            "last_available_at": self.last_available_at,
            "is_ready": self.is_ready,
            "pending_events": self.pending_events,
            "latency_ms": self.latency_ms,
        }


@dataclass
class CrossSymbolAvailability:
    """跨品种可用性状态"""
    query_time: int
    symbols: Dict[str, SymbolAvailability]
    
    all_ready: bool
    ready_symbols: List[str]
    pending_symbols: List[str]
    
    min_available_time: int
    max_latency_ms: int
    
    def get_safe_query_time(self) -> int:
        """获取安全的查询时间（所有品种都可用）"""
        if not self.symbols:
            return self.query_time
        
        return min(s.last_available_at for s in self.symbols.values())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_time": self.query_time,
            "all_ready": self.all_ready,
            "ready_symbols": self.ready_symbols,
            "pending_symbols": self.pending_symbols,
            "min_available_time": self.min_available_time,
            "max_latency_ms": self.max_latency_ms,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
        }


class CrossSymbolEventSemantics:
    """
    跨品种事件语义管理器
    
    核心功能：
    1. 跟踪每个品种的事件可用性
    2. 计算跨品种特征的安全查询时间
    3. 检测跨品种数据泄漏
    """
    
    def __init__(self, symbols: List[str]):
        self.symbols = set(symbols)
        
        self._symbol_availability: Dict[str, SymbolAvailability] = {}
        self._event_time_managers: Dict[str, EventTimeManager] = {}
        
        for symbol in symbols:
            self._symbol_availability[symbol] = SymbolAvailability(
                symbol=symbol,
                last_exchange_time=0,
                last_receive_time=0,
                last_available_at=0,
                is_ready=False,
            )
            self._event_time_managers[symbol] = EventTimeManager()
        
        self._cross_symbol_features: Dict[str, Set[str]] = {}
        
        self._leakage_log: List[Dict[str, Any]] = []
    
    def register_cross_symbol_feature(
        self,
        feature_name: str,
        required_symbols: List[str],
    ):
        """
        注册跨品种特征
        
        Args:
            feature_name: 特征名称
            required_symbols: 所需品种列表
        """
        self._cross_symbol_features[feature_name] = set(required_symbols)
        logger.info(f"Registered cross-symbol feature: {feature_name} requires {required_symbols}")
    
    def update_symbol_availability(
        self,
        symbol: str,
        exchange_time: int,
        receive_time: Optional[int] = None,
        network_delay_ms: int = 100,
        processing_delay_ms: int = 50,
    ):
        """
        更新品种可用性
        
        Args:
            symbol: 品种
            exchange_time: 交易所时间
            receive_time: 接收时间
            network_delay_ms: 网络延迟
            processing_delay_ms: 处理延迟
        """
        if symbol not in self.symbols:
            logger.warning(f"Unknown symbol: {symbol}")
            return
        
        if receive_time is None:
            receive_time = int(datetime.utcnow().timestamp() * 1000)
        
        available_at = receive_time + processing_delay_ms
        
        current = self._symbol_availability[symbol]
        
        self._symbol_availability[symbol] = SymbolAvailability(
            symbol=symbol,
            last_exchange_time=max(current.last_exchange_time, exchange_time),
            last_receive_time=max(current.last_receive_time, receive_time),
            last_available_at=max(current.last_available_at, available_at),
            is_ready=True,
            latency_ms=receive_time - exchange_time + processing_delay_ms,
        )
    
    def check_cross_symbol_availability(
        self,
        query_time: int,
        required_symbols: Optional[List[str]] = None,
    ) -> CrossSymbolAvailability:
        """
        检查跨品种可用性
        
        Args:
            query_time: 查询时间
            required_symbols: 所需品种列表（None表示所有）
        
        Returns:
            CrossSymbolAvailability: 跨品种可用性状态
        """
        symbols_to_check = set(required_symbols) if required_symbols else self.symbols
        
        symbol_states: Dict[str, SymbolAvailability] = {}
        ready_symbols = []
        pending_symbols = []
        
        for symbol in symbols_to_check:
            if symbol not in self._symbol_availability:
                pending_symbols.append(symbol)
                continue
            
            state = self._symbol_availability[symbol]
            symbol_states[symbol] = state
            
            if state.last_available_at <= query_time:
                ready_symbols.append(symbol)
            else:
                pending_symbols.append(symbol)
        
        all_ready = len(pending_symbols) == 0
        
        min_available_time = 0
        max_latency_ms = 0
        
        if symbol_states:
            min_available_time = min(s.last_available_at for s in symbol_states.values())
            max_latency_ms = max(s.latency_ms for s in symbol_states.values())
        
        return CrossSymbolAvailability(
            query_time=query_time,
            symbols=symbol_states,
            all_ready=all_ready,
            ready_symbols=ready_symbols,
            pending_symbols=pending_symbols,
            min_available_time=min_available_time,
            max_latency_ms=max_latency_ms,
        )
    
    def check_feature_availability(
        self,
        feature_name: str,
        query_time: int,
    ) -> Tuple[bool, CrossSymbolAvailability]:
        """
        检查跨品种特征可用性
        
        Args:
            feature_name: 特征名称
            query_time: 查询时间
        
        Returns:
            Tuple[bool, CrossSymbolAvailability]: (是否可用, 可用性状态)
        """
        required_symbols = self._cross_symbol_features.get(feature_name)
        
        if required_symbols is None:
            return True, self.check_cross_symbol_availability(query_time, [])
        
        availability = self.check_cross_symbol_availability(query_time, list(required_symbols))
        
        if not availability.all_ready:
            self._log_leakage_attempt(
                feature_name=feature_name,
                query_time=query_time,
                pending_symbols=availability.pending_symbols,
            )
        
        return availability.all_ready, availability
    
    def get_safe_query_time(
        self,
        required_symbols: Optional[List[str]] = None,
        query_time: Optional[int] = None,
    ) -> int:
        """
        获取安全的查询时间
        
        Args:
            required_symbols: 所需品种列表
            query_time: 期望查询时间
        
        Returns:
            int: 所有品种都可用的安全时间
        """
        availability = self.check_cross_symbol_availability(query_time or 0, required_symbols)
        return availability.get_safe_query_time()
    
    def compute_cross_symbol_feature(
        self,
        feature_name: str,
        compute_fn: Any,
        query_time: int,
        strict: bool = True,
    ) -> Tuple[Optional[Any], CrossSymbolAvailability]:
        """
        计算跨品种特征（带可用性检查）
        
        Args:
            feature_name: 特征名称
            compute_fn: 计算函数
            query_time: 查询时间
            strict: 严格模式（未就绪时抛异常）
        
        Returns:
            Tuple[Optional[Any], CrossSymbolAvailability]: (特征值, 可用性状态)
        """
        is_available, availability = self.check_feature_availability(feature_name, query_time)
        
        if not is_available:
            msg = (
                f"Cross-symbol feature {feature_name} not available at {query_time}. "
                f"Pending symbols: {availability.pending_symbols}"
            )
            
            if strict:
                raise ValueError(msg)
            
            logger.warning(msg)
            return None, availability
        
        try:
            result = compute_fn()
            return result, availability
        except Exception as e:
            logger.error(f"Error computing cross-symbol feature {feature_name}: {e}")
            return None, availability
    
    def _log_leakage_attempt(
        self,
        feature_name: str,
        query_time: int,
        pending_symbols: List[str],
    ):
        """记录泄漏尝试"""
        self._leakage_log.append({
            "feature_name": feature_name,
            "query_time": query_time,
            "pending_symbols": pending_symbols,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_leakage_report(self) -> Dict[str, Any]:
        """获取泄漏报告"""
        feature_counts: Dict[str, int] = {}
        for log in self._leakage_log:
            feature = log["feature_name"]
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
        
        return {
            "total_attempts": len(self._leakage_log),
            "feature_counts": feature_counts,
            "recent_attempts": self._leakage_log[-10:],
        }
    
    def get_symbol_status(self) -> Dict[str, Any]:
        """获取所有品种状态"""
        return {
            symbol: state.to_dict()
            for symbol, state in self._symbol_availability.items()
        }


_semantics_instances: Dict[str, CrossSymbolEventSemantics] = {}


def get_cross_symbol_semantics(
    symbols: List[str],
    instance_id: str = "default",
) -> CrossSymbolEventSemantics:
    """获取跨品种事件语义实例"""
    key = f"{instance_id}_{'_'.join(sorted(symbols))}"
    if key not in _semantics_instances:
        _semantics_instances[key] = CrossSymbolEventSemantics(symbols)
    return _semantics_instances[key]
