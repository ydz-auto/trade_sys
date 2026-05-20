"""
Execution Router - 执行路由器

核心职责:
1. 统一所有下单入口
2. 根据模式路由到正确的 Execution Adapter
3. 阻止危险 execution (Replay 禁止真实下单)
4. Runtime namespace 隔离

架构:
    Strategy/Runtime
           ↓
    ExecutionRouter  ← 本模块
           ↓
    ┌──────┴──────┐
    ↓             ↓
PaperAdapter   LiveAdapter
"""
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import asyncio

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderType,
    OrderStatus,
    Exchange,
)
from domain.trading_mode import TradingMode, get_trading_mode_manager
from infrastructure.logging import get_logger

logger = get_logger("execution.router")


class ExecutionRoute(str, Enum):
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"
    BLOCKED = "blocked"


class ExecutionBlockedError(Exception):
    """执行被阻止的错误"""
    def __init__(self, reason: str, details: Dict[str, Any] = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(f"Execution blocked: {reason}")


class ExecutionRouter:
    _instance: Optional['ExecutionRouter'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._mode_manager = get_trading_mode_manager()
        
        self._adapters: Dict[TradingMode, Any] = {}
        
        self._execution_log: list[Dict[str, Any]] = []
        
        self._safety_rules: Dict[str, Callable[[], bool]] = {
            "replay_mode": self._check_not_in_replay,
            "mode_active": self._check_mode_active,
            "risk_passed": self._check_risk_limits,
        }
        
        self._stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "paper_executions": 0,
            "live_executions": 0,
            "backtest_executions": 0,
        }
        
        logger.info("ExecutionRouter initialized")

    def _check_not_in_replay(self) -> bool:
        return not getattr(self._mode_manager, '_in_replay', False)

    def _check_mode_active(self) -> bool:
        from domain.trading_mode.manager import ModeState
        return self._mode_manager.state == ModeState.ACTIVE

    def _check_risk_limits(self) -> bool:
        return True

    def register_adapter(self, mode: TradingMode, adapter: Any) -> None:
        self._adapters[mode] = adapter
        logger.info(f"Registered adapter for mode: {mode.value}")

    def get_route(self) -> ExecutionRoute:
        mode = self._mode_manager.mode
        
        if mode == TradingMode.BACKTEST:
            return ExecutionRoute.BACKTEST
        elif mode == TradingMode.PAPER:
            return ExecutionRoute.PAPER
        elif mode == TradingMode.LIVE:
            return ExecutionRoute.LIVE
        
        return ExecutionRoute.BLOCKED

    def get_namespace(self) -> str:
        mode = self._mode_manager.mode
        return f"runtime.{mode.value}"

    def get_event_topic(self, event_type: str) -> str:
        namespace = self.get_namespace()
        return f"{namespace}.{event_type}"

    async def validate_execution(self, request: OrderRequest) -> tuple[bool, str]:
        for rule_name, rule_check in self._safety_rules.items():
            if not rule_check():
                return False, f"Safety rule '{rule_name}' failed"
        
        if self._mode_manager.mode == TradingMode.LIVE:
            is_safe, message = self._mode_manager.is_safe_to_trade()
            if not is_safe:
                return False, message
        
        return True, "OK"

    async def execute(self, request: OrderRequest) -> OrderResult:
        self._stats["total_requests"] += 1
        
        route = self.get_route()
        namespace = self.get_namespace()
        
        is_valid, message = await self.validate_execution(request)
        if not is_valid:
            self._stats["blocked_requests"] += 1
            logger.warning(f"Execution blocked: {message}")
            return OrderResult(
                success=False,
                error=f"Execution blocked: {message}",
            )
        
        adapter = self._adapters.get(self._mode_manager.mode)
        if adapter is None:
            logger.error(f"No adapter registered for mode: {self._mode_manager.mode.value}")
            return OrderResult(
                success=False,
                error=f"No adapter for mode: {self._mode_manager.mode.value}",
            )
        
        try:
            logger.info(
                f"[{namespace}] Executing order: {request.side.value} "
                f"{request.quantity} {request.symbol} via {route.value}"
            )
            
            result = await adapter.create_order(request)
            
            if result.success:
                self._log_execution(request, result, route, namespace)
                
                if route == ExecutionRoute.PAPER:
                    self._stats["paper_executions"] += 1
                elif route == ExecutionRoute.LIVE:
                    self._stats["live_executions"] += 1
                elif route == ExecutionRoute.BACKTEST:
                    self._stats["backtest_executions"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return OrderResult(success=False, error=str(e))

    async def execute_batch(self, requests: list[OrderRequest]) -> list[OrderResult]:
        results = []
        for request in requests:
            result = await self.execute(request)
            results.append(result)
        return results

    def _log_execution(
        self,
        request: OrderRequest,
        result: OrderResult,
        route: ExecutionRoute,
        namespace: str,
    ) -> None:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "namespace": namespace,
            "route": route.value,
            "symbol": request.symbol,
            "side": request.side.value,
            "quantity": request.quantity,
            "order_type": request.order_type.value,
            "success": result.success,
            "order_id": result.order.order_id if result.order else None,
        }
        self._execution_log.append(log_entry)
        
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-500:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self._mode_manager.mode.value,
            "route": self.get_route().value,
            "namespace": self.get_namespace(),
            "stats": self._stats.copy(),
            "recent_executions": self._execution_log[-10:],
        }

    def get_execution_log(self, limit: int = 100) -> list[Dict[str, Any]]:
        return self._execution_log[-limit:]

    def set_replay_mode(self, in_replay: bool) -> None:
        self._mode_manager._in_replay = in_replay
        logger.info(f"Replay mode set to: {in_replay}")

    def add_safety_rule(self, name: str, check: Callable[[], bool]) -> None:
        self._safety_rules[name] = check
        logger.info(f"Added safety rule: {name}")

    def remove_safety_rule(self, name: str) -> None:
        self._safety_rules.pop(name, None)
        logger.info(f"Removed safety rule: {name}")


def get_execution_router() -> ExecutionRouter:
    return ExecutionRouter()


async def safe_execute(request: OrderRequest) -> OrderResult:
    router = get_execution_router()
    return await router.execute(request)
