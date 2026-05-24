"""
Runtime Contract - 统一的运行时契约

所有 runtime 必须继承 BaseRuntime 并实现：
- initialize(): 初始化
- run(): 主循环
- shutdown(): 关闭清理
- health_check(): 健康检查
"""

import asyncio
import os
import signal
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.kernel.state.runtime_state import RuntimeState


class LoggerProtocol(Protocol):
    """Logger protocol for dependency injection"""
    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def debug(self, msg: str) -> None: ...


class ClockProtocol(Protocol):
    """Clock protocol for dependency injection"""
    def now_ms(self) -> int: ...


class ConfigProtocol(Protocol):
    """Config protocol for dependency injection"""
    kafka_bootstrap_servers: str


@dataclass
class RuntimeConfig:
    """Runtime 配置基类"""
    name: str = "unknown"
    version: str = "1.0.0"
    environment: str = "dev"
    
    kafka_bootstrap_servers: str = None
    redis_url: str = None
    
    log_level: str = "INFO"
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    
    shutdown_timeout: int = 30
    health_check_interval: int = 10

    def _resolve_kafka_servers(self) -> str:
        if self.kafka_bootstrap_servers is not None:
            return self.kafka_bootstrap_servers
        try:
            from infrastructure.config.startup.settings import get_startup_settings
            return get_startup_settings().kafka.bootstrap_servers
        except Exception:
            return os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    def _resolve_redis_url(self) -> str:
        if self.redis_url is not None:
            return self.redis_url
        try:
            from infrastructure.config.startup.settings import get_startup_settings
            settings = get_startup_settings()
            return settings.redis.url
        except Exception:
            return os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    def __post_init__(self):
        if self.kafka_bootstrap_servers is None:
            object.__setattr__(self, 'kafka_bootstrap_servers', self._resolve_kafka_servers())
        if self.redis_url is None:
            object.__setattr__(self, 'redis_url', self._resolve_redis_url())
    
    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """从环境变量加载配置"""
        return cls(
            name=os.environ.get("RUNTIME_NAME", "unknown"),
            version=os.environ.get("RUNTIME_VERSION", "1.0.0"),
            environment=os.environ.get("ENVIRONMENT", "dev"),
            kafka_bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS") or None,
            redis_url=os.environ.get("REDIS_URL") or None,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            metrics_enabled=os.environ.get("METRICS_ENABLED", "true").lower() == "true",
            tracing_enabled=os.environ.get("TRACING_ENABLED", "true").lower() == "true",
            shutdown_timeout=int(os.environ.get("SHUTDOWN_TIMEOUT", "30")),
            health_check_interval=int(os.environ.get("HEALTH_CHECK_INTERVAL", "10")),
        )


def _default_now_ms() -> int:
    """Default clock implementation - can be overridden via injection"""
    import time
    return int(time.time() * 1000)


@dataclass
class RuntimeContext:
    """Runtime 上下文"""
    config: RuntimeConfig
    state: RuntimeState = RuntimeState.CREATED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    _now_ms: Callable[[], int] = field(default_factory=lambda: _default_now_ms)
    
    def record_stat(self, key: str, value: Any) -> None:
        """记录统计信息"""
        self.stats[key] = value
    
    def increment_stat(self, key: str, delta: int = 1) -> None:
        """增加计数"""
        self.stats[key] = self.stats.get(key, 0) + delta
    
    def record_error(self, error: str) -> None:
        """记录错误"""
        self.errors.append(error)
    
    @property
    def uptime_seconds(self) -> float:
        """运行时长（秒）"""
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.fromtimestamp(self._now_ms() / 1000)
        return (end - self.start_time).total_seconds()
    
    def request_shutdown(self) -> None:
        """请求关闭"""
        self._shutdown_event.set()
    
    def is_shutdown_requested(self) -> bool:
        """是否请求关闭"""
        return self._shutdown_event.is_set()
    
    async def wait_for_shutdown(self, timeout: float = None) -> bool:
        """等待关闭信号"""
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            return False


_runtime_context: Optional[RuntimeContext] = None


def get_runtime_context() -> RuntimeContext:
    """获取当前 Runtime 上下文"""
    global _runtime_context
    if _runtime_context is None:
        raise RuntimeError("Runtime context not initialized")
    return _runtime_context


def set_runtime_context(ctx: RuntimeContext) -> None:
    """设置 Runtime 上下文"""
    global _runtime_context
    _runtime_context = ctx


class BaseRuntime(ABC):
    """
    Runtime 基类
    
    所有 runtime 必须继承此类并实现：
    - initialize(): 初始化资源
    - run(): 主运行循环
    - shutdown(): 清理资源
    - health_check(): 健康检查
    
    生命周期：
    CREATED → INITIALIZING → RUNNING → STOPPING → STOPPED
                         ↘ ERROR
    
    Dependencies are injected via constructor:
    - logger: LoggerProtocol (optional, defaults to stdlib logging)
    - now_ms: Callable[[], int] (optional, defaults to time.time * 1000)
    """
    
    def __init__(
        self,
        config: RuntimeConfig = None,
        logger: Optional[LoggerProtocol] = None,
        now_ms: Optional[Callable[[], int]] = None,
    ):
        self.config = config or RuntimeConfig.from_env()
        self.context = RuntimeContext(
            config=self.config,
            _now_ms=now_ms or _default_now_ms,
        )
        self.logger = logger or self._create_default_logger()
        
        self._tasks: List[asyncio.Task] = []
        self._shutdown_handlers: List[Callable] = []
    
    def _create_default_logger(self) -> LoggerProtocol:
        """Create a default logger using stdlib logging"""
        import logging
        log = logging.getLogger(self.config.name)
        log.setLevel(getattr(logging, self.config.log_level, logging.INFO))
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
            log.addHandler(handler)
        return log
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def state(self) -> RuntimeState:
        return self.context.state
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化资源（子类实现）"""
        pass
    
    @abstractmethod
    async def run(self) -> None:
        """主运行循环（子类实现）"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """清理资源（子类实现）"""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "name": self.name,
            "state": self.state.value,
            "uptime_seconds": self.context.uptime_seconds,
            "stats": self.context.stats,
            "errors_count": len(self.context.errors),
            "healthy": self.state == RuntimeState.RUNNING,
        }

    async def on_event(self, event: Any) -> None:
        """RuntimeProtocol event entrypoint.

        Stateful runtimes should override this when they consume events directly.
        Runtimes with their own run loop can keep using run().
        """
        raise NotImplementedError(f"{self.name} does not implement on_event()")

    async def get_state(self) -> Dict[str, Any]:
        """RuntimeProtocol get_state entrypoint."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": dict(self.context.stats),
        }

    async def snapshot(self) -> Dict[str, Any]:
        """RuntimeProtocol snapshot entrypoint."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": dict(self.context.stats),
            "errors": list(self.context.errors),
        }

    async def recover(self, checkpoint: Any = None) -> None:
        """RuntimeProtocol recovery entrypoint."""
        if checkpoint is not None:
            self.logger.info(f"Recover called with checkpoint: {checkpoint}")

    async def health(self) -> Dict[str, Any]:
        """RuntimeProtocol health entrypoint."""
        return await self.health_check()
    
    def on_shutdown(self, handler: Callable) -> None:
        """注册关闭处理器"""
        self._shutdown_handlers.append(handler)
    
    async def _set_state(self, state: RuntimeState) -> None:
        """设置状态"""
        self.context.state = state
        self.logger.info(f"Runtime state changed: {state.value}")
    
    async def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        loop = asyncio.get_running_loop()
        
        def handle_signal(sig):
            self.logger.info(f"Received signal {sig}, requesting shutdown...")
            self.context.request_shutdown()
        
        import sys
        if sys.platform == "win32":
            self.logger.info("Windows platform detected, skipping signal handlers")
            return
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
    
    async def _run_shutdown_handlers(self) -> None:
        """运行关闭处理器"""
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                self.logger.error(f"Shutdown handler error: {e}")
    
    async def start(self) -> None:
        """启动 Runtime"""
        set_runtime_context(self.context)
        
        try:
            await self._set_state(RuntimeState.INITIALIZING)
            self.context.start_time = datetime.fromtimestamp(self.context._now_ms() / 1000)
            
            await self._setup_signal_handlers()
            await self.initialize()
            
            await self._set_state(RuntimeState.RUNNING)
            self.logger.info(f"Runtime {self.name} started")
            
            await self.run()
            
        except Exception as e:
            self.logger.error(f"Runtime error: {e}")
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.context.record_error(str(e))
            await self._set_state(RuntimeState.ERROR)
            raise
            
        finally:
            await self._set_state(RuntimeState.STOPPING)
            await self._run_shutdown_handlers()
            await self.shutdown()
            self.context.end_time = datetime.fromtimestamp(self.context._now_ms() / 1000)
            await self._set_state(RuntimeState.STOPPED)
            self.logger.info(f"Runtime {self.name} stopped. Uptime: {self.context.uptime_seconds:.1f}s")
    
    async def stop(self) -> None:
        """停止 Runtime"""
        self.context.request_shutdown()
    
    async def run_forever(self) -> None:
        """运行直到收到关闭信号"""
        await self.context.wait_for_shutdown()
    
    def create_task(self, coro, name: str = None) -> asyncio.Task:
        """创建并跟踪任务"""
        task = asyncio.create_task(coro)
        if name:
            task.set_name(name)
        self._tasks.append(task)
        return task
    
    async def wait_for_tasks(self, timeout: float = None) -> None:
        """等待所有任务完成"""
        if not self._tasks:
            return
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Tasks did not complete within {timeout}s")
            for task in self._tasks:
                if not task.done():
                    task.cancel()
