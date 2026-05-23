"""
Slippage Control - 滑点控制

实时控制滑点:
1. 滑点监控
2. 动态调整
3. 保护机制
4. 告警系统
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("execution.slippage_control")


class SlippageStatus(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SlippageMeasurement:
    timestamp: datetime
    symbol: str
    
    expected_price: float
    actual_price: float
    
    slippage_bps: float
    slippage_pct: float
    
    order_size: float
    market_conditions: Dict[str, Any]


@dataclass
class SlippageControlResult:
    status: SlippageStatus
    
    current_slippage_bps: float
    avg_slippage_bps: float
    max_slippage_bps: float
    
    should_pause: bool
    should_reduce_size: bool
    recommended_size_pct: float
    
    alert_message: Optional[str]


@dataclass
class SlippageController:
    warning_threshold_bps: float = 5.0
    high_threshold_bps: float = 15.0
    critical_threshold_bps: float = 30.0
    
    history_size: int = 100
    cooldown_seconds: float = 60.0
    
    size_reduction_factor: float = 0.5
    
    def __post_init__(self):
        self._history: Dict[str, List[SlippageMeasurement]] = {}
        self._pause_until: Dict[str, datetime] = {}
    
    def record(
        self,
        symbol: str,
        expected_price: float,
        actual_price: float,
        order_size: float,
        market_conditions: Dict[str, Any],
    ) -> SlippageMeasurement:
        timestamp = datetime.now()
        
        slippage_pct = (actual_price - expected_price) / expected_price
        slippage_bps = abs(slippage_pct) * 10000
        
        measurement = SlippageMeasurement(
            timestamp=timestamp,
            symbol=symbol,
            expected_price=expected_price,
            actual_price=actual_price,
            slippage_bps=slippage_bps,
            slippage_pct=slippage_pct,
            order_size=order_size,
            market_conditions=market_conditions,
        )
        
        if symbol not in self._history:
            self._history[symbol] = []
        
        self._history[symbol].append(measurement)
        
        if len(self._history[symbol]) > self.history_size:
            self._history[symbol] = self._history[symbol][-self.history_size:]
        
        return measurement
    
    def check(
        self,
        symbol: str,
        proposed_size: float,
    ) -> SlippageControlResult:
        history = self._history.get(symbol, [])
        
        if not history:
            return self._normal_result()
        
        recent = history[-20:]
        
        current_bps = recent[-1].slippage_bps if recent else 0.0
        avg_bps = np.mean([m.slippage_bps for m in recent])
        max_bps = max(m.slippage_bps for m in recent)
        
        status = self._determine_status(current_bps, avg_bps)
        
        should_pause = self._should_pause(symbol, status, current_bps)
        should_reduce = status in [SlippageStatus.HIGH, SlippageStatus.CRITICAL]
        
        recommended_pct = self._calculate_recommended_size(
            status, current_bps, avg_bps
        )
        
        alert = self._generate_alert(status, current_bps, avg_bps)
        
        return SlippageControlResult(
            status=status,
            current_slippage_bps=current_bps,
            avg_slippage_bps=avg_bps,
            max_slippage_bps=max_bps,
            should_pause=should_pause,
            should_reduce_size=should_reduce,
            recommended_size_pct=recommended_pct,
            alert_message=alert,
        )
    
    def _determine_status(
        self,
        current: float,
        avg: float,
    ) -> SlippageStatus:
        if current >= self.critical_threshold_bps:
            return SlippageStatus.CRITICAL
        
        if current >= self.high_threshold_bps or avg >= self.high_threshold_bps:
            return SlippageStatus.HIGH
        
        if current >= self.warning_threshold_bps or avg >= self.warning_threshold_bps:
            return SlippageStatus.ELEVATED
        
        return SlippageStatus.NORMAL
    
    def _should_pause(
        self,
        symbol: str,
        status: SlippageStatus,
        current_bps: float,
    ) -> bool:
        if status == SlippageStatus.CRITICAL:
            self._pause_until[symbol] = datetime.now() + timedelta(seconds=self.cooldown_seconds)
            return True
        
        if symbol in self._pause_until:
            if datetime.now() < self._pause_until[symbol]:
                return True
            else:
                del self._pause_until[symbol]
        
        return False
    
    def _calculate_recommended_size(
        self,
        status: SlippageStatus,
        current: float,
        avg: float,
    ) -> float:
        if status == SlippageStatus.NORMAL:
            return 1.0
        
        if status == SlippageStatus.ELEVATED:
            return 0.8
        
        if status == SlippageStatus.HIGH:
            return self.size_reduction_factor
        
        return self.size_reduction_factor * 0.5
    
    def _generate_alert(
        self,
        status: SlippageStatus,
        current: float,
        avg: float,
    ) -> Optional[str]:
        if status == SlippageStatus.NORMAL:
            return None
        
        if status == SlippageStatus.CRITICAL:
            return f"CRITICAL: Slippage {current:.1f} bps exceeds threshold. Trading paused."
        
        if status == SlippageStatus.HIGH:
            return f"HIGH: Slippage {current:.1f} bps (avg: {avg:.1f}). Consider reducing size."
        
        return f"ELEVATED: Slippage {current:.1f} bps. Monitor closely."
    
    def _normal_result(self) -> SlippageControlResult:
        return SlippageControlResult(
            status=SlippageStatus.NORMAL,
            current_slippage_bps=0.0,
            avg_slippage_bps=0.0,
            max_slippage_bps=0.0,
            should_pause=False,
            should_reduce_size=False,
            recommended_size_pct=1.0,
            alert_message=None,
        )
    
    def get_stats(self, symbol: str) -> Dict[str, Any]:
        history = self._history.get(symbol, [])
        
        if not history:
            return {"count": 0}
        
        slippages = [m.slippage_bps for m in history]
        
        return {
            "count": len(history),
            "current_bps": slippages[-1],
            "avg_bps": np.mean(slippages),
            "max_bps": max(slippages),
            "min_bps": min(slippages),
            "std_bps": np.std(slippages),
            "trend": slippages[-1] - slippages[0] if len(slippages) > 1 else 0.0,
        }


def control_slippage(
    symbol: str,
    expected_price: float,
    actual_price: float,
    order_size: float,
    market_conditions: Dict[str, Any],
    controller: Optional[SlippageController] = None,
) -> SlippageControlResult:
    controller = controller or SlippageController()
    controller.record(
        symbol, expected_price, actual_price,
        order_size, market_conditions
    )
    return controller.check(symbol, order_size)
