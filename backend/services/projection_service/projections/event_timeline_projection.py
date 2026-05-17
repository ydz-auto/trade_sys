"""
Event Timeline Projection - 事件时间线投影

消费：
- 所有事件类型

输出：
- projection:timeline:events       → 全局事件时间线
- projection:timeline:symbol:{sym} → 按品种的时间线
- projection:timeline:type:{type}  → 按类型的时间线

这是 Runtime 可视化的核心：
    09:31 ETF inflow detected
    09:32 4H bullish regime confirmed
    09:33 Funding normalized
    09:34 LONG signal generated
    09:35 Risk approved
    09:35 Order executed
"""

import json
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict

from .base import BaseProjection
from ..state_keys import ProjectionKeys, ProjectionChannels
from infrastructure.messaging import Topics
from infrastructure.messaging.schema import EventType


class EventTimelineProjection(BaseProjection):
    """
    事件时间线投影
    
    这是前端 Event Timeline 页面的数据源
    """
    
    def __init__(self):
        super().__init__("timeline")
        
        self._global_timeline: List[Dict[str, Any]] = []
        self._symbol_timelines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._type_timelines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        self._event_counts = defaultdict(int)
        self._last_24h_events = 0
    
    @property
    def topics(self) -> List[str]:
        return [
            Topics.RAW_DATA,
            Topics.EVENTS,
            Topics.SIGNALS,
            Topics.DECISIONS,
            Topics.decisions_risk_checked(),
            Topics.ORDERS,
        ]
    
    async def initialize(self) -> None:
        await super().initialize()
        self.logger.info("Event timeline projection initialized")
    
    async def process_event(self, event: Dict[str, Any]) -> None:
        """处理所有事件"""
        self.record_event()
        
        try:
            timeline_entry = self._create_timeline_entry(event)
            
            self._global_timeline.insert(0, timeline_entry)
            self._global_timeline = self._global_timeline[:500]
            
            symbol = event.get("symbol", "GLOBAL")
            self._symbol_timelines[symbol].insert(0, timeline_entry)
            self._symbol_timelines[symbol] = self._symbol_timelines[symbol][:100]
            
            event_type = event.get("event_type", "unknown")
            self._type_timelines[event_type].insert(0, timeline_entry)
            self._type_timelines[event_type] = self._type_timelines[event_type][:100]
            
            self._event_counts[event_type] += 1
            
            await self._update_redis()
            
            await self.push_websocket(ProjectionChannels.timeline(), {
                "type": "new_event",
                "event": timeline_entry,
            })
            
        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self._stats.errors += 1
    
    def _create_timeline_entry(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """创建时间线条目"""
        event_type = event.get("event_type", "unknown")
        timestamp = event.get("timestamp", datetime.utcnow().isoformat())
        symbol = event.get("symbol", "")
        trace_id = event.get("trace_id", "")
        
        entry = {
            "event_id": event.get("event_id", ""),
            "trace_id": trace_id,
            "event_type": event_type,
            "symbol": symbol,
            "timestamp": timestamp,
            "display_time": self._format_display_time(timestamp),
            "title": self._generate_title(event),
            "description": self._generate_description(event),
            "severity": self._determine_severity(event),
            "metadata": {},
        }
        
        if event_type == "raw_data":
            data = event.get("data", {})
            entry["title"] = f"📰 {data.get('title', 'News')[:50]}"
            entry["description"] = data.get("source", "unknown")
            entry["metadata"]["source"] = data.get("source", "")
        
        elif event_type == "event":
            entry["title"] = f"⚡ {event.get('raw_event_type', 'Event')}"
            entry["description"] = f"{event.get('direction', 'neutral')} - {event.get('strength', 0):.2f}"
            entry["metadata"]["direction"] = event.get("direction", "")
            entry["metadata"]["strength"] = event.get("strength", 0)
        
        elif event_type == "signal":
            direction = event.get("direction", "neutral")
            icon = "🟢" if direction == "bullish" else "🔴" if direction == "bearish" else "⚪"
            entry["title"] = f"{icon} Signal: {event.get('signal_name', 'Unknown')}"
            entry["description"] = f"Confidence: {event.get('confidence', 0):.2f}"
            entry["metadata"]["confidence"] = event.get("confidence", 0)
            entry["metadata"]["direction"] = direction
        
        elif event_type == "decision":
            action = event.get("action", "HOLD")
            icon = "📈" if action == "LONG" else "📉" if action == "SHORT" else "⏸️"
            entry["title"] = f"{icon} Decision: {action} {symbol}"
            entry["description"] = event.get("reason", "")[:100]
            entry["metadata"]["action"] = action
            entry["metadata"]["confidence"] = event.get("confidence", 0)
            entry["metadata"]["quantity"] = event.get("quantity", 0)
        
        elif event_type == "risk_checked":
            approved = event.get("approved", False)
            icon = "✅" if approved else "❌"
            risk_level = event.get("risk_level", "low")
            entry["title"] = f"{icon} Risk Check: {risk_level.upper()}"
            entry["description"] = event.get("rejection_reason", "Approved") if not approved else "Approved"
            entry["metadata"]["approved"] = approved
            entry["metadata"]["risk_level"] = risk_level
        
        elif event_type == "order":
            status = event.get("status", "new")
            side = event.get("side", "buy")
            icon = "📝" if status == "new" else "✅" if status == "filled" else "❌"
            entry["title"] = f"{icon} Order: {side.upper()} {symbol}"
            entry["description"] = f"Qty: {event.get('quantity', 0)} @ {event.get('price', 0)}"
            entry["metadata"]["order_id"] = event.get("order_id", "")
            entry["metadata"]["status"] = status
        
        elif event_type == "fill":
            entry["title"] = f"💰 Fill: {event.get('side', 'buy').upper()} {symbol}"
            entry["description"] = f"{event.get('quantity', 0)} @ {event.get('price', 0)}"
            entry["metadata"]["fill_id"] = event.get("fill_id", "")
            entry["metadata"]["realized_pnl"] = event.get("realized_pnl", 0)
        
        elif event_type == "pnl":
            entry["title"] = f"📊 PnL Update: {symbol}"
            entry["description"] = f"Unrealized: {event.get('unrealized_pnl', 0):.2f}"
            entry["metadata"]["unrealized_pnl"] = event.get("unrealized_pnl", 0)
        
        return entry
    
    def _format_display_time(self, timestamp: str) -> str:
        """格式化显示时间"""
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                dt = timestamp
            return dt.strftime("%H:%M:%S")
        except Exception:
            return timestamp
    
    def _generate_title(self, event: Dict[str, Any]) -> str:
        """生成事件标题"""
        event_type = event.get("event_type", "unknown")
        return f"{event_type.upper()}: {event.get('symbol', '')}"
    
    def _generate_description(self, event: Dict[str, Any]) -> str:
        """生成事件描述"""
        return str(event.get("reason", ""))[:100]
    
    def _determine_severity(self, event: Dict[str, Any]) -> str:
        """确定事件严重程度"""
        event_type = event.get("event_type", "")
        
        if event_type == "risk_checked":
            if not event.get("approved", True):
                return "error"
            risk_level = event.get("risk_level", "low")
            if risk_level in ("high", "extreme"):
                return "warning"
        
        if event_type == "decision":
            action = event.get("action", "")
            if action in ("LONG", "SHORT"):
                return "info"
        
        if event_type == "signal":
            confidence = event.get("confidence", 0)
            if confidence >= 0.7:
                return "success"
        
        return "info"
    
    async def _update_redis(self) -> None:
        """更新 Redis"""
        await self.update_redis(ProjectionKeys.timeline_events(), self._global_timeline[:100])
        
        if self.redis:
            for symbol, timeline in list(self._symbol_timelines.items())[:10]:
                await self.update_redis(
                    ProjectionKeys.timeline_by_symbol(symbol),
                    timeline[:50]
                )
    
    def get_timeline(self, symbol: str = None, event_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取时间线"""
        if symbol:
            return self._symbol_timelines.get(symbol, [])[:limit]
        if event_type:
            return self._type_timelines.get(event_type, [])[:limit]
        return self._global_timeline[:limit]
    
    def get_event_counts(self) -> Dict[str, int]:
        """获取事件计数"""
        return dict(self._event_counts)
