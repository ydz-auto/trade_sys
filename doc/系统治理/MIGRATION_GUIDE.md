# 架构迁移指南

**创建日期**: 2026-05-14  
**目标**: 将 services/ 中的运行时职责迁移到 runtime/ 层

---

## 迁移策略

### 总体原则

1. **渐进式迁移**：不一次性重构所有代码，按优先级逐步迁移
2. **保持兼容**：迁移过程中保持系统可用
3. **充分测试**：每个阶段都要有充分的测试覆盖
4. **文档同步**：及时更新文档和注释

### 迁移顺序

```
阶段 1: 创建 runtime 基础设施 (1-2 周)
    ↓
阶段 2: 迁移核心 runtime (2-3 周)
    - ingestion_runtime
    - signal_runtime
    - execution_runtime
    ↓
阶段 3: 迁移辅助 runtime (1-2 周)
    - projection_runtime
    - correlation_runtime
    ↓
阶段 4: 清理 services 层 (1 周)
    ↓
阶段 5: 清理遗留代码 (1 周)
```

---

## 阶段 1: 创建 runtime 基础设施

### 1.1 创建 runtime/base.py

```python
# runtime/base.py
"""
Runtime 基础抽象类

所有 runtime 都应该继承 BaseRuntime
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from infrastructure.logging import get_logger
from runtime.shared import RuntimeContext, RuntimeLifecycle


class BaseRuntime(ABC):
    """
    Runtime 基类
    
    职责：
    - 生命周期管理
    - 健康检查
    - 优雅关闭
    - 错误处理
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"runtime.{name}")
        self.context = RuntimeContext(name)
        self.lifecycle = RuntimeLifecycle(name)
        self._running = False
        self._stats: Dict[str, Any] = {}
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        初始化 runtime
        
        子类必须实现此方法，用于：
        - 初始化运行时组件（consumer, publisher, metrics）
        - 初始化业务逻辑（调用 services/）
        """
        pass
    
    @abstractmethod
    async def run(self) -> None:
        """
        运行 runtime
        
        子类必须实现此方法，用于：
        - 主循环
        - 消费消息
        - 调用业务逻辑
        - 发布结果
        """
        pass
    
    async def shutdown(self) -> None:
        """
        关闭 runtime
        
        子类可以重写此方法，添加自定义关闭逻辑
        """
        self.logger.info(f"Shutting down {self.name} runtime...")
        self._running = False
        await self.lifecycle.shutdown()
        self.logger.info(f"{self.name} runtime stopped")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态字典
        """
        return {
            "name": self.name,
            "running": self._running,
            "stats": self._stats,
            "lifecycle": await self.lifecycle.get_status(),
        }
    
    @asynccontextmanager
    async def lifespan(self):
        """
        生命周期上下文管理器
        
        用法:
            async with runtime.lifespan():
                await runtime.run()
        """
        try:
            await self.initialize()
            self._running = True
            yield
        finally:
            await self.shutdown()


class RuntimeContext:
    """
    Runtime 上下文
    
    管理 runtime 的全局状态
    """
    
    def __init__(self, name: str):
        self.name = name
        self._shutdown_requested = False
        self._shutdown_reason: Optional[str] = None
    
    def request_shutdown(self, reason: str = "") -> None:
        """请求关闭"""
        self._shutdown_requested = True
        self._shutdown_reason = reason
    
    def is_shutdown_requested(self) -> bool:
        """检查是否请求关闭"""
        return self._shutdown_requested
    
    def get_shutdown_reason(self) -> Optional[str]:
        """获取关闭原因"""
        return self._shutdown_reason
```

### 1.2 创建 runtime/shared/ 目录

```python
# runtime/shared/__init__.py
"""
Runtime 共享组件

提供运行时通用功能：
- 生命周期管理
- 指标收集
- Kafka 消费者/发布者
- 健康检查
"""

from .lifecycle import RuntimeLifecycle
from .metrics import RuntimeMetrics
from .consumer import RuntimeConsumer
from .publisher import RuntimePublisher
from .healthcheck import RuntimeHealthCheck

__all__ = [
    "RuntimeLifecycle",
    "RuntimeMetrics",
    "RuntimeConsumer",
    "RuntimePublisher",
    "RuntimeHealthCheck",
]
```

```python
# runtime/shared/lifecycle.py
"""
生命周期管理
"""

from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger


class RuntimeState(Enum):
    """Runtime 状态"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class RuntimeLifecycle:
    """
    Runtime 生命周期管理
    
    功能：
    - 状态管理
    - 启动/停止钩子
    - 错误处理
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"runtime.{name}.lifecycle")
        self.state = RuntimeState.INITIALIZING
        self.start_time: Optional[datetime] = None
        self.stop_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self._hooks = {
            "pre_start": [],
            "post_start": [],
            "pre_stop": [],
            "post_stop": [],
        }
    
    def register_hook(self, hook_type: str, callback) -> None:
        """注册钩子函数"""
        if hook_type in self._hooks:
            self._hooks[hook_type].append(callback)
    
    async def start(self) -> None:
        """启动"""
        self.logger.info(f"Starting {self.name} lifecycle...")
        
        # 执行 pre_start 钩子
        for hook in self._hooks["pre_start"]:
            await hook()
        
        self.state = RuntimeState.RUNNING
        self.start_time = datetime.utcnow()
        
        # 执行 post_start 钩子
        for hook in self._hooks["post_start"]:
            await hook()
        
        self.logger.info(f"{self.name} lifecycle started")
    
    async def shutdown(self) -> None:
        """关闭"""
        self.logger.info(f"Shutting down {self.name} lifecycle...")
        
        # 执行 pre_stop 钩子
        for hook in self._hooks["pre_stop"]:
            await hook()
        
        self.state = RuntimeState.STOPPING
        self.stop_time = datetime.utcnow()
        
        # 执行 post_stop 钩子
        for hook in self._hooks["post_stop"]:
            await hook()
        
        self.state = RuntimeState.STOPPED
        self.logger.info(f"{self.name} lifecycle stopped")
    
    def set_error(self, error: str) -> None:
        """设置错误状态"""
        self.state = RuntimeState.ERROR
        self.error = error
        self.logger.error(f"{self.name} lifecycle error: {error}")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        uptime = None
        if self.start_time:
            if self.stop_time:
                uptime = (self.stop_time - self.start_time).total_seconds()
            else:
                uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        return {
            "name": self.name,
            "state": self.state.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "stop_time": self.stop_time.isoformat() if self.stop_time else None,
            "uptime_seconds": uptime,
            "error": self.error,
        }
```

```python
# runtime/shared/metrics.py
"""
指标收集
"""

from typing import Dict, Any
from datetime import datetime
from collections import defaultdict

from infrastructure.logging import get_logger
from shared.observability import get_observability_manager


class RuntimeMetrics:
    """
    Runtime 指标收集
    
    功能：
    - 请求计数
    - 延迟统计
    - 错误统计
    - 业务指标
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"runtime.{name}.metrics")
        self.observability = get_observability_manager(name)
        
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = defaultdict(list)
    
    def increment(self, metric: str, value: int = 1) -> None:
        """增加计数器"""
        self._counters[metric] += value
        self.observability.record_request(
            metric, "COUNTER", 200, value / 1000.0
        )
    
    def gauge(self, metric: str, value: float) -> None:
        """设置仪表值"""
        self._gauges[metric] = value
        self.observability.record_request(
            metric, "GAUGE", 200, value
        )
    
    def histogram(self, metric: str, value: float) -> None:
        """记录直方图值"""
        self._histograms[metric].append({
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def record_latency(self, operation: str, latency_ms: float) -> None:
        """记录延迟"""
        self.histogram(f"{operation}_latency_ms", latency_ms)
        self.observability.record_request(
            operation, "LATENCY", 200, latency_ms / 1000.0
        )
    
    def record_error(self, operation: str, error: str) -> None:
        """记录错误"""
        self.increment(f"{operation}_errors")
        self.observability.record_request(
            operation, "ERROR", 500, 0.0
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: len(v) for k, v in self._histograms.items()
            },
        }
```

```python
# runtime/shared/consumer.py
"""
Kafka 消费者
"""

from typing import Optional, Callable, Any
import asyncio

from infrastructure.logging import get_logger
from infrastructure.messaging import get_broker, Topics


class RuntimeConsumer:
    """
    Runtime Kafka 消费者
    
    功能：
    - 订阅 Kafka topic
    - 消费消息
    - 错误处理
    - 重试机制
    """
    
    def __init__(
        self,
        name: str,
        topics: list[str],
        bootstrap_servers: str = "localhost:9092",
        group_id: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.name = name
        self.topics = topics
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id or f"{name}-group"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.logger = get_logger(f"runtime.{name}.consumer")
        self._broker = None
        self._running = False
        self._message_handlers: dict[str, Callable] = {}
    
    async def initialize(self) -> None:
        """初始化消费者"""
        self.logger.info(f"Initializing consumer for {self.name}...")
        
        for attempt in range(self.max_retries):
            try:
                self._broker = get_broker(self.bootstrap_servers)
                self.logger.info(f"Consumer initialized: {self.topics}")
                return
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize consumer (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        raise RuntimeError(f"Failed to initialize consumer after {self.max_retries} attempts")
    
    def register_handler(self, topic: str, handler: Callable) -> None:
        """注册消息处理器"""
        self._message_handlers[topic] = handler
        self.logger.info(f"Registered handler for topic: {topic}")
    
    async def consume(self) -> Optional[Any]:
        """消费消息"""
        if not self._broker:
            raise RuntimeError("Consumer not initialized")
        
        # 这里需要根据实际的 broker 实现来消费消息
        # 简化示例
        pass
    
    async def start(self) -> None:
        """启动消费者"""
        self._running = True
        self.logger.info(f"Consumer started: {self.topics}")
    
    async def stop(self) -> None:
        """停止消费者"""
        self._running = False
        if self._broker:
            await self._broker.stop()
        self.logger.info(f"Consumer stopped: {self.topics}")
```

```python
# runtime/shared/publisher.py
"""
Kafka 发布者
"""

from typing import Optional, Any
import asyncio

from infrastructure.logging import get_logger
from infrastructure.messaging import get_broker


class RuntimePublisher:
    """
    Runtime Kafka 发布者
    
    功能：
    - 发布消息到 Kafka
    - 错误处理
    - 重试机制
    """
    
    def __init__(
        self,
        name: str,
        bootstrap_servers: str = "localhost:9092",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.name = name
        self.bootstrap_servers = bootstrap_servers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.logger = get_logger(f"runtime.{name}.publisher")
        self._broker = None
    
    async def initialize(self) -> None:
        """初始化发布者"""
        self.logger.info(f"Initializing publisher for {self.name}...")
        
        for attempt in range(self.max_retries):
            try:
                self._broker = get_broker(self.bootstrap_servers)
                self.logger.info(f"Publisher initialized")
                return
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize publisher (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        raise RuntimeError(f"Failed to initialize publisher after {self.max_retries} attempts")
    
    async def publish(
        self,
        topic: str,
        message: Any,
        key: Optional[str] = None,
    ) -> bool:
        """
        发布消息
        
        Args:
            topic: Kafka topic
            message: 消息内容
            key: 消息键（可选）
            
        Returns:
            是否发布成功
        """
        if not self._broker:
            raise RuntimeError("Publisher not initialized")
        
        for attempt in range(self.max_retries):
            try:
                await self._broker.publish(
                    message=message,
                    topic=topic,
                    key=key,
                )
                self.logger.debug(f"Published message to {topic}")
                return True
            except Exception as e:
                self.logger.warning(
                    f"Failed to publish message (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        self.logger.error(f"Failed to publish message after {self.max_retries} attempts")
        return False
    
    async def shutdown(self) -> None:
        """关闭发布者"""
        if self._broker:
            await self._broker.stop()
        self.logger.info(f"Publisher shutdown")
```

```python
# runtime/shared/healthcheck.py
"""
健康检查
"""

from typing import Dict, Any
from datetime import datetime

from infrastructure.logging import get_logger


class RuntimeHealthCheck:
    """
    Runtime 健康检查
    
    功能：
    - HTTP 健康检查端点
    - 就绪检查
    - 存活检查
    """
    
    def __init__(self, name: str, port: int = 8080):
        self.name = name
        self.port = port
        self.logger = get_logger(f"runtime.{name}.healthcheck")
        self._checks: Dict[str, callable] = {}
    
    def register_check(self, name: str, check: callable) -> None:
        """注册健康检查"""
        self._checks[name] = check
        self.logger.info(f"Registered health check: {name}")
    
    async def check_health(self) -> Dict[str, Any]:
        """执行健康检查"""
        results = {}
        all_healthy = True
        
        for name, check in self._checks.items():
            try:
                healthy = await check()
                results[name] = {
                    "healthy": healthy,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                if not healthy:
                    all_healthy = False
            except Exception as e:
                results[name] = {
                    "healthy": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                all_healthy = False
        
        return {
            "name": self.name,
            "healthy": all_healthy,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def check_ready(self) -> bool:
        """检查是否就绪"""
        health = await self.check_health()
        return health["healthy"]
    
    async def check_live(self) -> bool:
        """检查是否存活"""
        return True
```

---

## 阶段 2: 迁移核心 runtime

### 2.1 创建 runtime/ingestion_runtime/

```python
# runtime/ingestion_runtime/__init__.py
"""
Ingestion Runtime - 数据采集运行时

职责：
- Kafka 消费/发布
- 数据采集编排
- 数据聚合编排
"""

from .runtime import IngestionRuntime, get_ingestion_runtime

__all__ = ["IngestionRuntime", "get_ingestion_runtime"]
```

```python
# runtime/ingestion_runtime/runtime.py
"""
Ingestion Runtime 实现
"""

import asyncio
from typing import Optional

from runtime.base import BaseRuntime
from runtime.shared import (
    RuntimeConsumer,
    RuntimePublisher,
    RuntimeMetrics,
    RuntimeHealthCheck,
)

from services.data_service.collectors import NewsCollector
from services.aggregation_service.aggregators import (
    get_timeframe_aggregator,
    get_trade_aggregator,
)

from infrastructure.logging import get_logger
from infrastructure.messaging import Topics

logger = get_logger("ingestion_runtime")


class IngestionRuntime(BaseRuntime):
    """
    Ingestion Runtime - 数据采集运行时
    
    职责：
    1. 消费原始数据（运行时职责）
    2. 调用数据采集逻辑（services/data_service/）
    3. 调用数据聚合逻辑（services/aggregation_service/）
    4. 发布聚合结果（运行时职责）
    """
    
    def __init__(self):
        super().__init__("ingestion")
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.healthcheck: Optional[RuntimeHealthCheck] = None
        
        self.news_collector: Optional[NewsCollector] = None
        self.timeframe_aggregator = None
        self.trade_aggregator = None
    
    async def initialize(self) -> None:
        """初始化运行时"""
        logger.info("Initializing Ingestion Runtime...")
        
        self.consumer = RuntimeConsumer(
            name="ingestion",
            topics=[Topics.RAW_DATA],
        )
        await self.consumer.initialize()
        
        self.publisher = RuntimePublisher(name="ingestion")
        await self.publisher.initialize()
        
        self.metrics = RuntimeMetrics("ingestion")
        
        self.healthcheck = RuntimeHealthCheck("ingestion")
        self.healthcheck.register_check("kafka", self._check_kafka)
        
        self.news_collector = NewsCollector()
        self.timeframe_aggregator = get_timeframe_aggregator()
        self.trade_aggregator = get_trade_aggregator()
        
        logger.info("Ingestion Runtime initialized")
    
    async def run(self) -> None:
        """运行主循环"""
        logger.info("Starting Ingestion Runtime main loop...")
        
        await self.consumer.start()
        
        try:
            while not self.context.is_shutdown_requested():
                try:
                    message = await self.consumer.consume()
                    
                    if message:
                        await self._process_message(message)
                        self.metrics.increment("messages_processed")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.metrics.record_error("message_processing", str(e))
                    await asyncio.sleep(1)
                    
        finally:
            await self.consumer.stop()
    
    async def _process_message(self, message: dict) -> None:
        """处理消息"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            news_items = await self.news_collector.collect()
            
            for news in news_items:
                await self.publisher.publish(
                    topic=Topics.RAW_DATA,
                    message=news.to_dict(),
                    key=news.symbol,
                )
            
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            self.metrics.record_latency("message_processing", latency)
            
        except Exception as e:
            logger.error(f"Error in _process_message: {e}")
            raise
    
    async def _check_kafka(self) -> bool:
        """检查 Kafka 连接"""
        try:
            return self.consumer._broker is not None
        except:
            return False


_ingestion_runtime: Optional[IngestionRuntime] = None


async def get_ingestion_runtime() -> IngestionRuntime:
    """获取 Ingestion Runtime 单例"""
    global _ingestion_runtime
    if _ingestion_runtime is None:
        _ingestion_runtime = IngestionRuntime()
        await _ingestion_runtime.initialize()
    return _ingestion_runtime
```

### 2.2 创建 runtime/signal_runtime/

```python
# runtime/signal_runtime/__init__.py
"""
Signal Runtime - 信号生成运行时

职责：
- 消费 events
- 调用融合逻辑
- 调用策略逻辑
- 发布 signals 和 decisions
"""

from .runtime import SignalRuntime, get_signal_runtime

__all__ = ["SignalRuntime", "get_signal_runtime"]
```

```python
# runtime/signal_runtime/runtime.py
"""
Signal Runtime 实现
"""

import asyncio
from typing import Optional

from runtime.base import BaseRuntime
from runtime.shared import (
    RuntimeConsumer,
    RuntimePublisher,
    RuntimeMetrics,
)

from services.fusion_service import FusionEngine
from services.strategy_service.strategies import create_default_strategies
from services.event_service.understanding import EventUnderstandingEngine

from infrastructure.logging import get_logger
from infrastructure.messaging import Topics

logger = get_logger("signal_runtime")


class SignalRuntime(BaseRuntime):
    """
    Signal Runtime - 信号生成运行时
    
    职责：
    1. 消费 events（运行时职责）
    2. 调用事件理解逻辑（services/event_service/）
    3. 调用融合逻辑（services/fusion_service/）
    4. 调用策略逻辑（services/strategy_service/）
    5. 发布 signals 和 decisions（运行时职责）
    """
    
    def __init__(self):
        super().__init__("signal")
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        self.metrics: Optional[RuntimeMetrics] = None
        
        self.fusion_engine: Optional[FusionEngine] = None
        self.strategy_orchestrator = None
        self.event_understanding: Optional[EventUnderstandingEngine] = None
    
    async def initialize(self) -> None:
        """初始化运行时"""
        logger.info("Initializing Signal Runtime...")
        
        self.consumer = RuntimeConsumer(
            name="signal",
            topics=[Topics.EVENTS, Topics.RAW_DATA],
        )
        await self.consumer.initialize()
        
        self.publisher = RuntimePublisher(name="signal")
        await self.publisher.initialize()
        
        self.metrics = RuntimeMetrics("signal")
        
        self.fusion_engine = FusionEngine()
        self.strategy_orchestrator = create_default_strategies()
        self.event_understanding = EventUnderstandingEngine()
        
        logger.info("Signal Runtime initialized")
    
    async def run(self) -> None:
        """运行主循环"""
        logger.info("Starting Signal Runtime main loop...")
        
        await self.consumer.start()
        
        try:
            while not self.context.is_shutdown_requested():
                try:
                    message = await self.consumer.consume()
                    
                    if message:
                        await self._process_message(message)
                        self.metrics.increment("messages_processed")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.metrics.record_error("message_processing", str(e))
                    await asyncio.sleep(1)
                    
        finally:
            await self.consumer.stop()
    
    async def _process_message(self, message: dict) -> None:
        """处理消息"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            event = await self.event_understanding.process(message)
            
            if event:
                signals = self.fusion_engine.process(event)
                
                for signal in signals:
                    await self.publisher.publish(
                        topic=Topics.SIGNALS,
                        message=signal.model_dump(),
                        key=signal.assets[0] if signal.assets else "CRYPTO",
                    )
                
                decisions = self.strategy_orchestrator.process(signals)
                
                for decision in decisions:
                    await self.publisher.publish(
                        topic=Topics.DECISIONS,
                        message=decision.model_dump(),
                        key=decision.symbol,
                    )
            
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            self.metrics.record_latency("message_processing", latency)
            
        except Exception as e:
            logger.error(f"Error in _process_message: {e}")
            raise


_signal_runtime: Optional[SignalRuntime] = None


async def get_signal_runtime() -> SignalRuntime:
    """获取 Signal Runtime 单例"""
    global _signal_runtime
    if _signal_runtime is None:
        _signal_runtime = SignalRuntime()
        await _signal_runtime.initialize()
    return _signal_runtime
```

### 2.3 创建 runtime/execution_runtime/

```python
# runtime/execution_runtime/__init__.py
"""
Execution Runtime - 订单执行运行时

职责：
- 消费 decisions
- 调用风控逻辑
- 调用执行逻辑
- 发布订单结果
"""

from .runtime import ExecutionRuntime, get_execution_runtime

__all__ = ["ExecutionRuntime", "get_execution_runtime"]
```

```python
# runtime/execution_runtime/runtime.py
"""
Execution Runtime 实现
"""

import asyncio
from typing import Optional

from runtime.base import BaseRuntime
from runtime.shared import (
    RuntimeConsumer,
    RuntimePublisher,
    RuntimeMetrics,
)

from services.execution_service.engine import ExecutionEngine
from services.risk_service.risk_engine import RiskEngine
from services.approval_service.decision_gate import ApprovalGate

from infrastructure.logging import get_logger
from infrastructure.messaging import Topics

logger = get_logger("execution_runtime")


class ExecutionRuntime(BaseRuntime):
    """
    Execution Runtime - 订单执行运行时
    
    职责：
    1. 消费 decisions（运行时职责）
    2. 调用风控逻辑（services/risk_service/）
    3. 调用审批逻辑（services/approval_service/）
    4. 调用执行逻辑（services/execution_service/）
    5. 发布订单结果（运行时职责）
    """
    
    def __init__(self):
        super().__init__("execution")
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        self.metrics: Optional[RuntimeMetrics] = None
        
        self.execution_engine: Optional[ExecutionEngine] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.approval_gate: Optional[ApprovalGate] = None
    
    async def initialize(self) -> None:
        """初始化运行时"""
        logger.info("Initializing Execution Runtime...")
        
        self.consumer = RuntimeConsumer(
            name="execution",
            topics=[Topics.decisions_risk_checked(), Topics.decisions_approved()],
        )
        await self.consumer.initialize()
        
        self.publisher = RuntimePublisher(name="execution")
        await self.publisher.initialize()
        
        self.metrics = RuntimeMetrics("execution")
        
        self.execution_engine = ExecutionEngine()
        self.risk_engine = RiskEngine()
        self.approval_gate = ApprovalGate()
        
        logger.info("Execution Runtime initialized")
    
    async def run(self) -> None:
        """运行主循环"""
        logger.info("Starting Execution Runtime main loop...")
        
        await self.consumer.start()
        
        try:
            while not self.context.is_shutdown_requested():
                try:
                    message = await self.consumer.consume()
                    
                    if message:
                        await self._process_message(message)
                        self.metrics.increment("messages_processed")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.metrics.record_error("message_processing", str(e))
                    await asyncio.sleep(1)
                    
        finally:
            await self.consumer.stop()
    
    async def _process_message(self, message: dict) -> None:
        """处理消息"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            decision = message.get("original_decision", message)
            
            risk_result = self.risk_engine.check(decision)
            
            if risk_result.approved:
                approval_result = await self.approval_gate.process(decision)
                
                if approval_result.approved:
                    execution_result = await self.execution_engine.execute(decision)
                    
                    await self.publisher.publish(
                        topic=Topics.ORDERS,
                        message=execution_result.model_dump(),
                        key=decision.symbol,
                    )
            
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            self.metrics.record_latency("message_processing", latency)
            
        except Exception as e:
            logger.error(f"Error in _process_message: {e}")
            raise


_execution_runtime: Optional[ExecutionRuntime] = None


async def get_execution_runtime() -> ExecutionRuntime:
    """获取 Execution Runtime 单例"""
    global _execution_runtime
    if _execution_runtime is None:
        _execution_runtime = ExecutionRuntime()
        await _execution_runtime.initialize()
    return _execution_runtime
```

---

## 阶段 3: 清理 services 层

### 3.1 删除运行时文件

迁移完成后，删除以下文件：

```bash
# 删除 Kafka 相关文件
rm services/*/main_kafka.py
rm -rf services/*/consumers/
rm -rf services/*/publishers/
rm -rf services/*/producers/

# 删除遗留 Worker
rm -rf services/workers/

# 删除 HTTP 服务器（如果已迁移到 api/）
rm services/*/http_server.py
```

### 3.2 更新导入路径

更新所有导入路径，从 `services.*.main_kafka` 改为 `runtime.*.runtime`。

### 3.3 更新文档

更新所有文档，反映新的架构。

---

## 测试策略

### 单元测试

```python
# tests/unit/services/test_fusion_engine.py
"""
测试融合引擎（纯业务逻辑）
"""

import pytest
from services.fusion_service.engine import FusionEngine


def test_fusion_engine_process():
    """测试融合引擎处理逻辑"""
    engine = FusionEngine()
    
    event = {
        "event_type": "etf_inflow",
        "asset": "BTC",
        "direction": "bullish",
        "strength": 0.8,
    }
    
    signals = engine.process(event)
    
    assert len(signals) > 0
    assert signals[0].direction == "bullish"
```

### 集成测试

```python
# tests/integration/runtime/test_signal_runtime.py
"""
测试 Signal Runtime（运行时编排）
"""

import pytest
from runtime.signal_runtime import SignalRuntime


@pytest.mark.asyncio
async def test_signal_runtime_process():
    """测试 Signal Runtime 处理流程"""
    runtime = SignalRuntime()
    await runtime.initialize()
    
    message = {
        "event_type": "etf_inflow",
        "asset": "BTC",
        "direction": "bullish",
        "strength": 0.8,
    }
    
    await runtime._process_message(message)
    
    stats = runtime.metrics.get_stats()
    assert stats["counters"]["messages_processed"] == 1
```

---

## 回滚计划

如果迁移出现问题，可以快速回滚：

1. 恢复 `services/*/main_kafka.py` 文件
2. 恢复 `services/*/consumers/` 目录
3. 恢复 `services/*/publishers/` 目录
4. 重启所有服务

---

## 检查清单

### 迁移前

- [ ] 创建 runtime 基础设施
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 准备回滚计划

### 迁移中

- [ ] 创建 runtime 层
- [ ] 迁移运行时逻辑
- [ ] 更新导入路径
- [ ] 运行测试

### 迁移后

- [ ] 删除 services 中的运行时文件
- [ ] 更新文档
- [ ] 监控系统运行状态
- [ ] 收集性能指标

---

*文档版本: v1.0*
