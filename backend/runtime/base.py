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
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger
from infrastructure.logging.logger import LoggerFactory
from infrastructure.runtime_clock import now_ms
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS


class RuntimeState(Enum):
    """Runtime 状态"""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RuntimeConfig:
    """Runtime 配置基类"""
    name: str = "unknown"
    version: str = "1.0.0"
    environment: str = "dev"
    
    kafka_bootstrap_servers: str = field(default_factory=lambda: KAFKA_BOOTSTRAP_SERVERS)
    redis_url: str = "redis://localhost:6379/0"
    
    log_level: str = "INFO"
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    
    shutdown_timeout: int = 30
    health_check_interval: int = 10
    
    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """从环境变量加载配置"""
        return cls(
            name=os.environ.get("RUNTIME_NAME", "unknown"),
            version=os.environ.get("RUNTIME_VERSION", "1.0.0"),
            environment=os.environ.get("ENVIRONMENT", "dev"),
            kafka_bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", KAFKA_BOOTSTRAP_SERVERS),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            metrics_enabled=os.environ.get("METRICS_ENABLED", "true").lower() == "true",
            tracing_enabled=os.environ.get("TRACING_ENABLED", "true").lower() == "true",
            shutdown_timeout=int(os.environ.get("SHUTDOWN_TIMEOUT", "30")),
            health_check_interval=int(os.environ.get("HEALTH_CHECK_INTERVAL", "10")),
        )


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
        end = self.end_time or datetime.fromtimestamp(now_ms() / 1000)
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
    """
    
    def __init__(self, config: RuntimeConfig = None):
        self.config = config or RuntimeConfig.from_env()
        self.context = RuntimeContext(config=self.config)
        self.logger = get_logger(self.config.name)
        
        self._tasks: List[asyncio.Task] = []
        self._shutdown_handlers: List[Callable] = []
    
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
        LoggerFactory.initialize(
            log_dir=os.environ.get("LOG_DIR", "logs"),
            log_level=self.config.log_level
        )
        
        set_runtime_context(self.context)
        
        try:
            await self._set_state(RuntimeState.INITIALIZING)
            self.context.start_time = datetime.fromtimestamp(now_ms() / 1000)
            
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
            self.context.end_time = datetime.fromtimestamp(now_ms() / 1000)
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
