"""
Execution Runtime - 订单执行运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集

业务逻辑：调用 services/execution_service/ 和 services/risk_service/
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig
from runtime.shared import (
    RuntimeLifecycle,
    RuntimeMetrics,
    RuntimeConsumer,
    ConsumerConfig,
    RuntimePublisher,
    PublisherConfig,
    RuntimeHealthCheck,
)
from infrastructure.messaging import Topics
from infrastructure.messaging.kafka_config import ConsumerGroup


class ExecutionConfig(RuntimeConfig):
    """Execution Runtime 配置"""
    name: str = "execution_runtime"
    max_position_size: float = 0.1
    max_leverage: int = 5
    enable_mock: bool = True


class ExecutionRuntime(BaseRuntime):
    """
    Execution Runtime - 订单执行运行时
    
    只负责运行时编排，业务逻辑在：
    - services/execution_service/ - 订单执行
    - services/risk_service/ - 风控检查
    """
    
    def __init__(self, config: ExecutionConfig = None):
        config = config or ExecutionConfig.from_env()
        super().__init__(config)
        self.config: ExecutionConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        
        self.execution_engine = None
        self.risk_engine = None
        self.order_manager = None
    
    async def initialize(self) -> None:
        """初始化运行时组件"""
        self.logger.info("Initializing Execution Runtime...")
        
        self.lifecycle = RuntimeLifecycle("execution")
        self.metrics = RuntimeMetrics("execution")
        self.health_check = RuntimeHealthCheck("execution")
        
        self.consumer = RuntimeConsumer(ConsumerConfig(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            topics=[Topics.DECISIONS],
            group_id=ConsumerGroup.EXECUTION_RUNTIME,
        ))
        
        self.publisher = RuntimePublisher(PublisherConfig(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            topic=Topics.ORDERS,
        ))
        
        await self.consumer.start()
        await self.publisher.start()
        
        try:
            from services.execution_service.engine.execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine()
            self.logger.info("Execution engine initialized")
        except Exception as e:
            self.logger.warning(f"Execution engine init failed: {e}")
        
        try:
            from services.execution_service.engine.order_manager import OrderManager
            self.order_manager = OrderManager()
            self.logger.info("Order manager initialized")
        except Exception as e:
            self.logger.warning(f"Order manager init failed: {e}")
        
        try:
            from services.execution_service.risk.risk_engine import RiskEngine
            self.risk_engine = RiskEngine()
            self.logger.info("Risk engine initialized")
        except Exception as e:
            self.logger.warning(f"Risk engine init failed: {e}")
        
        self.health_check.register_check("execution_engine", self._check_execution_engine)
        self.health_check.register_check("risk_engine", self._check_risk_engine)
        self.health_check.register_check("consumer", self.consumer.is_healthy)
        self.health_check.register_check("publisher", self.publisher.is_healthy)
        
        self.logger.info("Execution Runtime initialized successfully")
    
    async def _check_execution_engine(self) -> bool:
        return self.execution_engine is not None
    
    async def _check_risk_engine(self) -> bool:
        return self.risk_engine is not None
    
    async def shutdown(self) -> None:
        """关闭运行时组件"""
        self.logger.info("Shutting down Execution Runtime...")
        
        if self.consumer:
            await self.consumer.stop()
        if self.publisher:
            await self.publisher.stop()
        
        self.logger.info(f"Execution Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Execution Runtime main loop...")
        
        await self.lifecycle.transition_to_running()
        
        while not self.context.is_shutdown_requested():
            try:
                message = await self.consumer.consume(timeout=1.0)
                if message:
                    await self._process_decision(message)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)
    
    async def _process_decision(self, decision: Dict[str, Any]) -> None:
        """处理决策（运行时编排）"""
        trace_id = decision.get("trace_id", "unknown")
        
        self.metrics.increment("decisions_received")
        
        with self.metrics.timing("decision_processing"):
            risk_result = await self._check_risk(decision)
            
            if not risk_result.get("approved", False):
                self.logger.warning(f"[{trace_id}] Risk check failed: {risk_result.get('reason')}")
                self.metrics.increment("risk_rejected")
                return
            
            order = await self._execute_decision(decision)
            
            if order:
                self.metrics.increment("orders_executed")
                self.logger.info(f"[{trace_id}] Order executed: {order}")
                
                await self.publisher.publish(order)
    
    async def _check_risk(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """风控检查（调用 services/risk_service/）"""
        if self.risk_engine:
            return await self.risk_engine.check(decision)
        return {"approved": True, "reason": "Risk engine not available"}
    
    async def _execute_decision(self, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行决策（调用 services/execution_service/）"""
        if decision.get("action") == "HOLD":
            return None
        
        if self.execution_engine:
            return await self.execution_engine.execute(decision)
        
        if self.order_manager:
            return await self.order_manager.create_order(decision)
        
        return self._create_mock_order(decision)
    
    def _create_mock_order(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """创建模拟订单"""
        return {
            "order_id": f"ord_{datetime.now().timestamp()}",
            "trace_id": decision.get("trace_id", ""),
            "symbol": decision.get("symbol", "BTCUSDT"),
            "side": "buy" if decision.get("action") == "LONG" else "sell",
            "type": "market",
            "quantity": decision.get("quantity", 0.01),
            "status": "filled",
            "timestamp": datetime.now().isoformat(),
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "health_check": await self.health_check.to_dict() if self.health_check else {},
        })
        return health


_execution_runtime: Optional[ExecutionRuntime] = None


def get_execution_runtime() -> ExecutionRuntime:
    """获取 Execution Runtime 单例"""
    global _execution_runtime
    if _execution_runtime is None:
        _execution_runtime = ExecutionRuntime()
    return _execution_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Execution Runtime - Risk Check + Order Execution")
    print("=" * 60)
    
    runtime = get_execution_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
