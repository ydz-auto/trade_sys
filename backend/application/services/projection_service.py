"""
Projection Service - CQRS 投影业务服务

职责：
- 状态投影逻辑
- 数据聚合逻辑
- 视图生成逻辑

注意：这是纯业务逻辑，不包含 Redis、Kafka 等基础设施代码。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProjectionState:
    """投影状态"""
    projection_type: str
    key: str
    data: Dict[str, Any]
    version: int
    last_updated: datetime


class DashboardProjector:
    """Dashboard 投影器 - 纯业务逻辑"""
    
    def __init__(self):
        self._state: Dict[str, Any] = {}
    
    def project_price(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """投影价格事件"""
        symbol = event.get("symbol")
        price = event.get("price")
        
        if symbol and price:
            self._state[f"price:{symbol}"] = {
                "symbol": symbol,
                "price": price,
                "timestamp": datetime.now().isoformat(),
            }
        
        return self._state
    
    def project_signal(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """投影信号事件"""
        symbol = event.get("symbol")
        direction = event.get("direction")
        confidence = event.get("confidence")
        
        if symbol:
            self._state[f"signal:{symbol}"] = {
                "symbol": symbol,
                "direction": direction,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat(),
            }
        
        return self._state
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self._state


class DecisionProjector:
    """Decision 投影器 - 纯业务逻辑"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self._decisions: List[Dict[str, Any]] = []
        self._stats: Dict[str, int] = {
            "total": 0,
            "long": 0,
            "short": 0,
            "hold": 0,
        }
    
    def project(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """投影决策事件"""
        action = event.get("action", "HOLD").upper()
        
        self._decisions.append({
            **event,
            "timestamp": datetime.now().isoformat(),
        })
        
        if len(self._decisions) > self.history_size:
            self._decisions.pop(0)
        
        self._stats["total"] += 1
        if action in self._stats:
            self._stats[action.lower()] += 1
        
        return {
            "latest": self._decisions[-1] if self._decisions else None,
            "history": self._decisions[-10:],
            "stats": self._stats,
        }
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "latest": self._decisions[-1] if self._decisions else None,
            "history": self._decisions,
            "stats": self._stats,
        }


class ProjectionService:
    """
    Projection Service - CQRS 投影业务服务
    
    编排各种投影器的业务逻辑。
    这是纯业务逻辑层，不包含任何基础设施代码。
    """
    
    def __init__(self):
        self.dashboard_projector = DashboardProjector()
        self.decision_projector = DecisionProjector()
    
    def project(self, event_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        投影事件（纯业务逻辑）
        
        这是业务用例的入口点，根据事件类型分发到不同的投影器。
        """
        if event_type in ("raw_data", "market"):
            return self.dashboard_projector.project_price(event)
        elif event_type == "signal":
            return self.dashboard_projector.project_signal(event)
        elif event_type == "decision":
            return self.decision_projector.project(event)
        else:
            return {}
    
    def get_dashboard_state(self) -> Dict[str, Any]:
        """获取 Dashboard 状态"""
        return self.dashboard_projector.get_state()
    
    def get_decision_state(self) -> Dict[str, Any]:
        """获取 Decision 状态"""
        return self.decision_projector.get_state()
