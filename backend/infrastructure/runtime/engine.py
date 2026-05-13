"""
Unified Runtime - 统一运行时系统

统一 live/paper/replay/backtest 四种运行模式：
- 共用 execution
- 共用 risk
- 共用 portfolio state
- 共用 clock
- 共用 event source

这是系统一致性的核心。
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger
from infrastructure.runtime.clock import Clock, ClockMode, ClockConfig

logger = get_logger("infrastructure.runtime.engine")


class RuntimeMode(str, Enum):
    """运行模式"""
    LIVE = "live"
    PAPER = "paper"
    REPLAY = "replay"
    BACKTEST = "backtest"


@dataclass
class RuntimeConfig:
    """运行时配置"""
    mode: RuntimeMode = RuntimeMode.LIVE
    
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    speed: float = 1.0
    
    enable_risk: bool = True
    enable_portfolio: bool = True
    
    checkpoint_interval: int = 1000
    snapshot_interval: int = 5000
    
    initial_capital: float = 100000.0
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_clock_mode(self) -> ClockMode:
        """转换为时钟模式"""
        mapping = {
            RuntimeMode.LIVE: ClockMode.LIVE,
            RuntimeMode.PAPER: ClockMode.PAPER,
            RuntimeMode.REPLAY: ClockMode.REPLAY,
            RuntimeMode.BACKTEST: ClockMode.BACKTEST,
        }
        return mapping[self.mode]


@dataclass
class RuntimeState:
    """运行时状态"""
    runtime_id: str
    mode: RuntimeMode
    
    is_running: bool = False
    is_paused: bool = False
    
    start_time: Optional[datetime] = None
    current_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    events_processed: int = 0
    orders_created: int = 0
    orders_filled: int = 0
    trades_count: int = 0
    
    capital: float = 0.0
    pnl: float = 0.0
    
    errors_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "mode": self.mode.value,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "current_time": self.current_time.isoformat() if self.current_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "events_processed": self.events_processed,
            "orders_created": self.orders_created,
            "orders_filled": self.orders_filled,
            "trades_count": self.trades_count,
            "capital": self.capital,
            "pnl": self.pnl,
            "errors_count": self.errors_count,
            "last_error": self.last_error,
        }


class RuntimeEngine:
    """统一运行时引擎
    
    所有运行模式共用的核心引擎
    """
    
    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig()
        
        self.runtime_id = f"runtime_{uuid.uuid4().hex[:12]}"
        
        self.clock = Clock(ClockConfig(
            mode=self.config.to_clock_mode(),
            start_time=self.config.start_time,
            end_time=self.config.end_time,
            speed=self.config.speed,
        ))
        
        self._state = RuntimeState(
            runtime_id=self.runtime_id,
            mode=self.config.mode,
            capital=self.config.initial_capital,
        )
        
        self._execution_engine = None
        self._risk_engine = None
        self._portfolio_engine = None
        self._strategy_engine = None
        
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._lifecycle_hooks: Dict[str, List[Callable]] = {}
        
        self._snapshots: List[Dict[str, Any]] = []
        self._checkpoints: List[Dict[str, Any]] = []
        
        self._running = False
        self._paused = False
    
    def set_execution_engine(self, engine: Any) -> None:
        """设置执行引擎"""
        self._execution_engine = engine
        logger.info(f"Execution engine set: {type(engine).__name__}")
    
    def set_risk_engine(self, engine: Any) -> None:
        """设置风控引擎"""
        self._risk_engine = engine
        logger.info(f"Risk engine set: {type(engine).__name__}")
    
    def set_portfolio_engine(self, engine: Any) -> None:
        """设置组合引擎"""
        self._portfolio_engine = engine
        logger.info(f"Portfolio engine set: {type(engine).__name__}")
    
    def set_strategy_engine(self, engine: Any) -> None:
        """设置策略引擎"""
        self._strategy_engine = engine
        logger.info(f"Strategy engine set: {type(engine).__name__}")
    
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def register_lifecycle_hook(
        self,
        hook_name: str,
        hook: Callable[[], Awaitable[None]],
    ) -> None:
        """注册生命周期钩子"""
        if hook_name not in self._lifecycle_hooks:
            self._lifecycle_hooks[hook_name] = []
        self._lifecycle_hooks[hook_name].append(hook)
    
    async def initialize(self) -> None:
        """初始化运行时"""
        logger.info(f"Initializing runtime: {self.runtime_id} (mode={self.config.mode.value})")
        
        await self._run_hooks("on_initialize")
        
        if self._execution_engine and hasattr(self._execution_engine, 'initialize'):
            await self._execution_engine.initialize()
        
        if self._risk_engine and hasattr(self._risk_engine, 'initialize'):
            await self._risk_engine.initialize()
        
        if self._portfolio_engine and hasattr(self._portfolio_engine, 'initialize'):
            await self._portfolio_engine.initialize()
        
        if self._strategy_engine and hasattr(self._strategy_engine, 'initialize'):
            await self._strategy_engine.initialize()
        
        self._state.start_time = self.clock.now()
        self._state.current_time = self._state.start_time
        
        logger.info(f"Runtime initialized: {self.runtime_id}")
    
    async def start(self) -> None:
        """启动运行时"""
        if self._running:
            logger.warning(f"Runtime already running: {self.runtime_id}")
            return
        
        self._running = True
        self._paused = False
        self._state.is_running = True
        self._state.is_paused = False
        
        logger.info(f"Starting runtime: {self.runtime_id}")
        
        await self._run_hooks("on_start")
    
    async def stop(self) -> None:
        """停止运行时"""
        if not self._running:
            return
        
        self._running = False
        self._state.is_running = False
        
        logger.info(f"Stopping runtime: {self.runtime_id}")
        
        await self._run_hooks("on_stop")
        
        if self._execution_engine and hasattr(self._execution_engine, 'stop'):
            await self._execution_engine.stop()
    
    async def pause(self) -> None:
        """暂停运行时"""
        self._paused = True
        self._state.is_paused = True
        logger.info(f"Runtime paused: {self.runtime_id}")
    
    async def resume(self) -> None:
        """恢复运行时"""
        self._paused = False
        self._state.is_paused = False
        logger.info(f"Runtime resumed: {self.runtime_id}")
    
    async def process_event(
        self,
        event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """处理事件"""
        if not self._running or self._paused:
            return None
        
        event_type = event.get("event_type", "unknown")
        
        try:
            if self.clock.is_simulated():
                event_time = event.get("timestamp")
                if event_time:
                    if isinstance(event_time, str):
                        event_time = datetime.fromisoformat(event_time)
                    self.clock.advance_to(event_time)
            
            handlers = self._event_handlers.get(event_type, [])
            handlers.extend(self._event_handlers.get("*", []))
            
            result = None
            for handler in handlers:
                handler_result = await handler(event)
                if handler_result:
                    result = handler_result
            
            self._state.events_processed += 1
            self._state.current_time = self.clock.now()
            
            if self._state.events_processed % self.config.snapshot_interval == 0:
                await self.save_snapshot()
            
            return result
            
        except Exception as e:
            self._state.errors_count += 1
            self._state.last_error = str(e)
            logger.error(f"Event processing error: {e}")
            return None
    
    async def process_events(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Optional[Dict[str, Any]]]:
        """批量处理事件"""
        results = []
        for event in events:
            result = await self.process_event(event)
            results.append(result)
        return results
    
    async def create_order(
        self,
        order_request: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """创建订单"""
        if self.config.enable_risk and self._risk_engine:
            risk_check = await self._risk_engine.evaluate(order_request)
            if not risk_check.get("approved", True):
                logger.warning(f"Order rejected by risk engine: {risk_check.get('reason')}")
                return None
        
        if self._execution_engine:
            order = await self._execution_engine.create_order(order_request)
            self._state.orders_created += 1
            return order
        
        return None
    
    async def on_fill(
        self,
        fill: Dict[str, Any],
    ) -> None:
        """成交回调"""
        self._state.orders_filled += 1
        self._state.trades_count += 1
        
        if self._portfolio_engine and hasattr(self._portfolio_engine, 'on_fill'):
            await self._portfolio_engine.on_fill(fill)
    
    async def save_snapshot(self) -> Dict[str, Any]:
        """保存快照"""
        snapshot = {
            "runtime_id": self.runtime_id,
            "timestamp": self.clock.now().isoformat(),
            "state": self._state.to_dict(),
            "clock_state": {
                "current_time": self.clock.now().isoformat(),
                "step_count": self.clock.get_step_count(),
            },
            "portfolio_state": None,
            "strategy_state": None,
        }
        
        if self._portfolio_engine and hasattr(self._portfolio_engine, 'get_state'):
            snapshot["portfolio_state"] = self._portfolio_engine.get_state()
        
        if self._strategy_engine and hasattr(self._strategy_engine, 'get_state'):
            snapshot["strategy_state"] = self._strategy_engine.get_state()
        
        self._snapshots.append(snapshot)
        
        logger.debug(f"Snapshot saved at {snapshot['timestamp']}")
        return snapshot
    
    async def restore_snapshot(
        self,
        snapshot: Dict[str, Any],
    ) -> bool:
        """恢复快照"""
        try:
            snapshot_time = datetime.fromisoformat(snapshot["timestamp"])
            self.clock.advance_to(snapshot_time)
            
            state_data = snapshot.get("state", {})
            self._state.events_processed = state_data.get("events_processed", 0)
            self._state.orders_created = state_data.get("orders_created", 0)
            self._state.orders_filled = state_data.get("orders_filled", 0)
            self._state.trades_count = state_data.get("trades_count", 0)
            self._state.capital = state_data.get("capital", 0)
            self._state.pnl = state_data.get("pnl", 0)
            
            if self._portfolio_engine and hasattr(self._portfolio_engine, 'restore_state'):
                portfolio_state = snapshot.get("portfolio_state")
                if portfolio_state:
                    await self._portfolio_engine.restore_state(portfolio_state)
            
            if self._strategy_engine and hasattr(self._strategy_engine, 'restore_state'):
                strategy_state = snapshot.get("strategy_state")
                if strategy_state:
                    await self._strategy_engine.restore_state(strategy_state)
            
            logger.info(f"Snapshot restored from {snapshot['timestamp']}")
            return True
            
        except Exception as e:
            logger.error(f"Snapshot restore failed: {e}")
            return False
    
    async def save_checkpoint(self) -> Dict[str, Any]:
        """保存检查点"""
        checkpoint = await self.save_snapshot()
        self._checkpoints.append(checkpoint)
        return checkpoint
    
    def get_state(self) -> RuntimeState:
        """获取运行时状态"""
        self._state.current_time = self.clock.now()
        return self._state
    
    def get_mode(self) -> RuntimeMode:
        """获取运行模式"""
        return self.config.mode
    
    def is_live(self) -> bool:
        """是否实时模式"""
        return self.config.mode in [RuntimeMode.LIVE, RuntimeMode.PAPER]
    
    def is_simulated(self) -> bool:
        """是否模拟模式"""
        return self.config.mode in [RuntimeMode.REPLAY, RuntimeMode.BACKTEST]
    
    def get_snapshots(self) -> List[Dict[str, Any]]:
        """获取所有快照"""
        return self._snapshots.copy()
    
    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """获取所有检查点"""
        return self._checkpoints.copy()
    
    async def _run_hooks(self, hook_name: str) -> None:
        """运行生命周期钩子"""
        hooks = self._lifecycle_hooks.get(hook_name, [])
        for hook in hooks:
            try:
                await hook()
            except Exception as e:
                logger.error(f"Lifecycle hook error ({hook_name}): {e}")


def create_live_runtime(
    strategy_id: Optional[str] = None,
    initial_capital: float = 100000.0,
) -> RuntimeEngine:
    """创建实时运行时"""
    config = RuntimeConfig(
        mode=RuntimeMode.LIVE,
        strategy_id=strategy_id,
        initial_capital=initial_capital,
    )
    return RuntimeEngine(config)


def create_paper_runtime(
    strategy_id: Optional[str] = None,
    initial_capital: float = 100000.0,
) -> RuntimeEngine:
    """创建模拟运行时"""
    config = RuntimeConfig(
        mode=RuntimeMode.PAPER,
        strategy_id=strategy_id,
        initial_capital=initial_capital,
    )
    return RuntimeEngine(config)


def create_replay_runtime(
    start_time: datetime,
    end_time: datetime,
    strategy_id: Optional[str] = None,
    speed: float = 1.0,
) -> RuntimeEngine:
    """创建回放运行时"""
    config = RuntimeConfig(
        mode=RuntimeMode.REPLAY,
        strategy_id=strategy_id,
        start_time=start_time,
        end_time=end_time,
        speed=speed,
    )
    return RuntimeEngine(config)


def create_backtest_runtime(
    start_time: datetime,
    end_time: datetime,
    strategy_id: Optional[str] = None,
    initial_capital: float = 100000.0,
) -> RuntimeEngine:
    """创建回测运行时"""
    config = RuntimeConfig(
        mode=RuntimeMode.BACKTEST,
        strategy_id=strategy_id,
        start_time=start_time,
        end_time=end_time,
        initial_capital=initial_capital,
    )
    return RuntimeEngine(config)
