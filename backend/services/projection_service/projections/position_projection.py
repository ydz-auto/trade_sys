"""
Position Projection - 持仓状态投影

消费：
- ORDERS: 订单事件
- FILLS: 成交事件
- PNL: 盈亏事件

输出：
- projection:position:current      → 当前持仓
- projection:position:history      → 持仓历史
- projection:position:pnl          → 持仓盈亏
"""

import json
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict

from .base import BaseProjection
from ..state_keys import ProjectionKeys, ProjectionChannels
from infrastructure.messaging import Topics


class PositionProjection(BaseProjection):
    """
    持仓状态投影
    
    跟踪持仓、盈亏、历史记录
    """
    
    def __init__(self):
        super().__init__("position")
        
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._position_history: List[Dict[str, Any]] = []
        self._pnl_summary = {
            "total_unrealized": 0.0,
            "total_realized": 0.0,
            "total_pnl": 0.0,
            "positions_count": 0,
            "long_count": 0,
            "short_count": 0,
            "last_update": None,
        }
    
    @property
    def topics(self) -> List[str]:
        return [
            Topics.ORDERS,
            Topics.EVENTS,
        ]
    
    async def initialize(self) -> None:
        await super().initialize()
        
        positions = await self.get_redis(ProjectionKeys.position_current())
        if positions:
            self._positions = positions
        
        pnl = await self.get_redis(ProjectionKeys.position_pnl())
        if pnl:
            self._pnl_summary = pnl
        
        self.logger.info("Position projection initialized")
    
    async def process_event(self, event: Dict[str, Any]) -> None:
        """处理事件"""
        self.record_event()
        
        event_type = event.get("event_type", "")
        
        try:
            if event_type == "order":
                await self._process_order(event)
            elif event_type == "fill":
                await self._process_fill(event)
            elif event_type == "pnl":
                await self._process_pnl(event)
            elif event_type == "decision":
                await self._process_decision(event)
            
        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self._stats.errors += 1
    
    async def _process_order(self, event: Dict[str, Any]) -> None:
        """处理订单事件"""
        status = event.get("status", "")
        symbol = event.get("symbol", "")
        
        if status in ("filled", "partial"):
            await self._update_position_from_order(event)
    
    async def _update_position_from_order(self, event: Dict[str, Any]) -> None:
        """从订单更新持仓"""
        symbol = event.get("symbol", "")
        side = event.get("side", "")
        quantity = event.get("filled_quantity", event.get("quantity", 0))
        price = event.get("price", 0) or event.get("avg_price", 0)
        
        if not symbol or not price:
            return
        
        if symbol not in self._positions:
            self._positions[symbol] = {
                "symbol": symbol,
                "side": "long" if side == "buy" else "short",
                "size": 0.0,
                "entry_price": 0.0,
                "current_price": price,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "leverage": 1,
                "opened_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        position = self._positions[symbol]
        
        if side == "buy":
            if position["size"] < 0:
                if abs(position["size"]) <= quantity:
                    position["realized_pnl"] += (position["entry_price"] - price) * abs(position["size"])
                    quantity -= abs(position["size"])
                    position["size"] = 0
                    position["side"] = "long"
                else:
                    position["realized_pnl"] += (position["entry_price"] - price) * quantity
                    position["size"] += quantity
                    quantity = 0
            
            if quantity > 0:
                if position["size"] == 0:
                    position["entry_price"] = price
                    position["size"] = quantity
                else:
                    total_cost = position["entry_price"] * position["size"] + price * quantity
                    position["size"] += quantity
                    position["entry_price"] = total_cost / position["size"]
                position["side"] = "long"
        
        elif side == "sell":
            if position["size"] > 0:
                if position["size"] <= quantity:
                    position["realized_pnl"] += (price - position["entry_price"]) * position["size"]
                    quantity -= position["size"]
                    position["size"] = 0
                    position["side"] = "short"
                else:
                    position["realized_pnl"] += (price - position["entry_price"]) * quantity
                    position["size"] -= quantity
                    quantity = 0
            
            if quantity > 0:
                if position["size"] == 0:
                    position["entry_price"] = price
                    position["size"] = -quantity
                else:
                    total_cost = abs(position["entry_price"] * position["size"]) + price * quantity
                    position["size"] -= quantity
                    position["entry_price"] = total_cost / abs(position["size"])
                position["side"] = "short"
        
        position["current_price"] = price
        position["updated_at"] = datetime.utcnow().isoformat()
        
        if position["size"] == 0:
            history_entry = {
                "symbol": symbol,
                "side": position["side"],
                "entry_price": position["entry_price"],
                "exit_price": price,
                "realized_pnl": position["realized_pnl"],
                "closed_at": datetime.utcnow().isoformat(),
            }
            self._position_history.insert(0, history_entry)
            self._position_history = self._position_history[:100]
            del self._positions[symbol]
        
        await self._update_state()
        
        await self.push_websocket(ProjectionChannels.position(), {
            "type": "position_update",
            "symbol": symbol,
            "position": self._positions.get(symbol),
        })
    
    async def _process_fill(self, event: Dict[str, Any]) -> None:
        """处理成交事件"""
        symbol = event.get("symbol", "")
        side = event.get("side", "")
        quantity = event.get("quantity", 0)
        price = event.get("price", 0)
        realized_pnl = event.get("realized_pnl")
        
        if symbol in self._positions:
            position = self._positions[symbol]
            position["current_price"] = price
            position["updated_at"] = datetime.utcnow().isoformat()
            
            if realized_pnl is not None:
                position["realized_pnl"] += realized_pnl
            
            await self._update_state()
    
    async def _process_pnl(self, event: Dict[str, Any]) -> None:
        """处理盈亏事件"""
        symbol = event.get("symbol", "")
        unrealized_pnl = event.get("unrealized_pnl", 0)
        current_price = event.get("current_price", 0)
        
        if symbol in self._positions:
            position = self._positions[symbol]
            position["unrealized_pnl"] = unrealized_pnl
            position["current_price"] = current_price
            position["updated_at"] = datetime.utcnow().isoformat()
            
            await self._update_state()
    
    async def _process_decision(self, event: Dict[str, Any]) -> None:
        """处理决策事件（用于创建预期持仓）"""
        action = event.get("action", "").upper()
        symbol = event.get("symbol", "")
        
        if action in ("CLOSE", "EXIT"):
            if symbol in self._positions:
                position = self._positions[symbol]
                history_entry = {
                    "symbol": symbol,
                    "side": position["side"],
                    "entry_price": position["entry_price"],
                    "exit_price": position["current_price"],
                    "realized_pnl": position["realized_pnl"],
                    "closed_at": datetime.utcnow().isoformat(),
                    "reason": "manual_close",
                }
                self._position_history.insert(0, history_entry)
                del self._positions[symbol]
                
                await self._update_state()
                
                await self.push_websocket(ProjectionChannels.position(), {
                    "type": "position_closed",
                    "symbol": symbol,
                    "realized_pnl": position["realized_pnl"],
                })
    
    async def _update_state(self) -> None:
        """更新状态到 Redis"""
        await self.update_redis(ProjectionKeys.position_current(), self._positions)
        
        total_unrealized = sum(p.get("unrealized_pnl", 0) for p in self._positions.values())
        total_realized = sum(p.get("realized_pnl", 0) for p in self._positions.values())
        long_count = sum(1 for p in self._positions.values() if p.get("size", 0) > 0)
        short_count = sum(1 for p in self._positions.values() if p.get("size", 0) < 0)
        
        self._pnl_summary = {
            "total_unrealized": total_unrealized,
            "total_realized": total_realized,
            "total_pnl": total_unrealized + total_realized,
            "positions_count": len(self._positions),
            "long_count": long_count,
            "short_count": short_count,
            "last_update": datetime.utcnow().isoformat(),
        }
        
        await self.update_redis(ProjectionKeys.position_pnl(), self._pnl_summary)
    
    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有持仓"""
        return self._positions
    
    def get_position(self, symbol: str) -> Dict[str, Any]:
        """获取单个持仓"""
        return self._positions.get(symbol, {})
    
    def get_pnl_summary(self) -> Dict[str, Any]:
        """获取盈亏摘要"""
        return self._pnl_summary
    
    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取持仓历史"""
        return self._position_history[:limit]
