"""
State 管理器实现
"""

import time
import json
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
from enum import Enum

from .types import (
    StateType,
    SystemState,
    SystemMode,
    SystemStatus,
    MarketState,
    Position,
    Order,
    TradingState,
    RiskState,
    StrategyState,
    PortfolioState,
    STATE_DEFAULTS,
)


class StateManager:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._memory_state: Dict[StateType, Dict[str, Any]] = {}
        self._state_history: Dict[StateType, List[Dict]] = defaultdict(list)
        self._subscribers: Dict[StateType, List[Callable]] = defaultdict(list)
        self._last_snapshot: Dict[StateType, float] = {}

    def set_redis(self, redis_client):
        self._redis = redis_client

    def get_state(self, state_type: StateType, key: Optional[str] = None) -> Any:
        if state_type in self._memory_state:
            if key is None:
                return self._memory_state[state_type]
            return self._memory_state[state_type].get(key)
        return None

    def set_state(
        self,
        state_type: StateType,
        value: Any,
        key: Optional[str] = None,
        persist: bool = True,
    ):
        if key is None:
            self._memory_state[state_type] = value
        else:
            if state_type not in self._memory_state:
                self._memory_state[state_type] = {}
            self._memory_state[state_type][key] = value

        self._record_history(state_type, key, value)

        if persist and self._redis:
            self._persist_state(state_type, key, value)

        self._notify_subscribers(state_type, key, value)

    def update_state(
        self,
        state_type: StateType,
        updates: Dict[str, Any],
        persist: bool = True,
    ):
        current = self.get_state(state_type) or {}

        if isinstance(current, dict):
            current.update(updates)
            self.set_state(state_type, current, persist=persist)
        elif hasattr(current, "to_dict"):
            state_dict = current.to_dict()
            state_dict.update(updates)
            self.set_state(state_type, state_dict, persist=persist)

    def delete_state(self, state_type: StateType, key: Optional[str] = None):
        if key is None:
            if state_type in self._memory_state:
                del self._memory_state[state_type]
            if self._redis:
                self._redis.delete(f"state:{state_type.value}")
        else:
            if state_type in self._memory_state and key in self._memory_state[state_type]:
                del self._memory_state[state_type][key]
            if self._redis:
                self._redis.hdel(f"state:{state_type.value}", key)

    def _record_history(
        self,
        state_type: StateType,
        key: Optional[str],
        value: Any,
    ):
        history_entry = {
            "timestamp": int(time.time()),
            "key": key,
            "value": value if not hasattr(value, "to_dict") else value.to_dict(),
        }

        self._state_history[state_type].append(history_entry)

        if len(self._state_history[state_type]) > 100:
            self._state_history[state_type] = self._state_history[state_type][-100:]

    def get_history(
        self,
        state_type: StateType,
        key: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        history = self._state_history.get(state_type, [])

        if key is not None:
            history = [h for h in history if h.get("key") == key]

        return history[-limit:]

    def _persist_state(
        self,
        state_type: StateType,
        key: Optional[str],
        value: Any,
    ):
        if not self._redis:
            return

        state_key = f"state:{state_type.value}"

        if key is None:
            if hasattr(value, "to_dict"):
                value = value.to_dict()
            self._redis.set_json(state_key, value)
        else:
            if hasattr(value, "to_dict"):
                value = value.to_dict()
            self._redis.hset(state_key, key, json.dumps(value))

    async def load_from_redis(self, state_type: StateType):
        if not self._redis:
            return

        state_key = f"state:{state_type.value}"
        data = await self._redis.get_json(state_key)

        if data:
            self._memory_state[state_type] = data

    async def snapshot(self, state_type: StateType):
        if state_type not in self._memory_state:
            return

        snapshot_key = f"state:snapshot:{state_type.value}:{int(time.time())}"

        value = self._memory_state[state_type]
        if hasattr(value, "to_dict"):
            value = value.to_dict()

        if self._redis:
            await self._redis.set_json(snapshot_key, value, ex=86400 * 7)

        self._last_snapshot[state_type] = time.time()

    def subscribe(
        self,
        state_type: StateType,
        callback: Callable[[StateType, Optional[str], Any], None],
    ):
        self._subscribers[state_type].append(callback)

    def unsubscribe(
        self,
        state_type: StateType,
        callback: Callable,
    ):
        if callback in self._subscribers[state_type]:
            self._subscribers[state_type].remove(callback)

    def _notify_subscribers(
        self,
        state_type: StateType,
        key: Optional[str],
        value: Any,
    ):
        for callback in self._subscribers[state_type]:
            try:
                callback(state_type, key, value)
            except Exception:
                pass


class SystemStateManager(StateManager):
    def __init__(self, redis_client=None):
        super().__init__(redis_client)
        self.set_state(StateType.SYSTEM, SystemState().to_dict(), persist=False)

    def get_system_state(self) -> SystemState:
        state = self.get_state(StateType.SYSTEM)
        if state is None:
            return SystemState()
        return SystemState(**state) if isinstance(state, dict) else state

    def set_mode(self, mode: SystemMode):
        self.update_state(StateType.SYSTEM, {"mode": mode.value if isinstance(mode, Enum) else mode})

    def set_status(self, status: SystemStatus):
        self.update_state(StateType.SYSTEM, {"status": status.value if isinstance(status, Enum) else status})

    def set_trading_allowed(self, allowed: bool):
        self.update_state(StateType.SYSTEM, {"allow_trading": allowed})

    def add_strategy(self, strategy_id: str):
        state = self.get_system_state()
        if strategy_id not in state.active_strategies:
            state.active_strategies.append(strategy_id)
            self.set_state(StateType.SYSTEM, state.to_dict())

    def remove_strategy(self, strategy_id: str):
        state = self.get_system_state()
        if strategy_id in state.active_strategies:
            state.active_strategies.remove(strategy_id)
            self.set_state(StateType.SYSTEM, state.to_dict())

    def update_service_status(self, service_name: str, status: str):
        state = self.get_system_state()
        state.services[service_name] = status
        self.set_state(StateType.SYSTEM, state.to_dict())


class MarketStateManager(StateManager):
    def get_market_state(self, symbol: str) -> Optional[MarketState]:
        state = self.get_state(StateType.MARKET, symbol)
        if state is None:
            return None
        return MarketState(**state) if isinstance(state, dict) else state

    def update_market_state(self, symbol: str, updates: Dict[str, Any]):
        updates["last_update"] = int(time.time())
        self.update_state(StateType.MARKET, {symbol: MarketState(symbol=symbol, **updates).to_dict()})

    def get_all_market_states(self) -> Dict[str, MarketState]:
        market_data = self.get_state(StateType.MARKET) or {}
        return {
            symbol: MarketState(**data) if isinstance(data, dict) else data
            for symbol, data in market_data.items()
        }


class PositionStateManager(StateManager):
    def get_position(self, symbol: str) -> Optional[Position]:
        state = self.get_state(StateType.POSITION, symbol)
        if state is None:
            return None
        return Position(**state) if isinstance(state, dict) else state

    def update_position(self, symbol: str, updates: Dict[str, Any]):
        updates["last_update"] = int(time.time())
        current = self.get_position(symbol)
        if current:
            current_dict = current.to_dict() if hasattr(current, "to_dict") else current
            current_dict.update(updates)
            self.set_state(StateType.POSITION, current_dict, key=symbol)
        else:
            self.set_state(StateType.POSITION, Position(symbol=symbol, **updates).to_dict(), key=symbol)

    def get_all_positions(self) -> List[Position]:
        positions = self.get_state(StateType.POSITION) or {}
        return [
            Position(**data) if isinstance(data, dict) else data
            for data in positions.values()
        ]

    def close_position(self, symbol: str):
        self.delete_state(StateType.POSITION, symbol)


class RiskStateManager(StateManager):
    def __init__(self, redis_client=None):
        super().__init__(redis_client)
        self.set_state(StateType.RISK, RiskState().to_dict(), persist=False)

    def get_risk_state(self) -> RiskState:
        state = self.get_state(StateType.RISK)
        if state is None:
            return RiskState()
        return RiskState(**state) if isinstance(state, dict) else state

    def update_risk_state(self, updates: Dict[str, Any]):
        updates["last_update"] = int(time.time())
        self.update_state(StateType.RISK, updates)

    def increment_consecutive_losses(self):
        state = self.get_risk_state()
        state.consecutive_losses += 1
        self.set_state(StateType.RISK, state.to_dict())

    def reset_consecutive_losses(self):
        state = self.get_risk_state()
        state.consecutive_losses = 0
        self.set_state(StateType.RISK, state.to_dict())


_state_manager: Optional[StateManager] = None
_system_state_manager: Optional[SystemStateManager] = None
_market_state_manager: Optional[MarketStateManager] = None
_position_state_manager: Optional[PositionStateManager] = None
_risk_state_manager: Optional[RiskStateManager] = None


def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def get_system_state_manager() -> SystemStateManager:
    global _system_state_manager
    if _system_state_manager is None:
        _system_state_manager = SystemStateManager()
    return _system_state_manager


def get_market_state_manager() -> MarketStateManager:
    global _market_state_manager
    if _market_state_manager is None:
        _market_state_manager = MarketStateManager()
    return _market_state_manager


def get_position_state_manager() -> PositionStateManager:
    global _position_state_manager
    if _position_state_manager is None:
        _position_state_manager = PositionStateManager()
    return _position_state_manager


def get_risk_state_manager() -> RiskStateManager:
    global _risk_state_manager
    if _risk_state_manager is None:
        _risk_state_manager = RiskStateManager()
    return _risk_state_manager
