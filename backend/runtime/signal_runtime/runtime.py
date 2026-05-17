"""
Signal Runtime - 信号生成运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集

业务逻辑：调用 services/fusion_service/ 和 services/strategy_service/
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class SignalConfig(RuntimeConfig):
    """Signal Runtime 配置"""
    name: str = "signal_runtime"
    fusion_window_seconds: int = 300
    fusion_min_events: int = 1
    fusion_min_confidence: float = 0.3


class SignalRuntime(BaseRuntime):
    """
    Signal Runtime - 信号生成运行时
    
    只负责运行时编排，业务逻辑在：
    - services/fusion_service/ - 信号融合
    - services/strategy_service/ - 策略决策
    """
    
    def __init__(self, config: SignalConfig = None):
        config = config or SignalConfig.from_env()
        super().__init__(config)
        self.config: SignalConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        
        self.fusion_engine = None
        self.strategy_orchestrator = None
    
    async def initialize(self) -> None:
        """初始化运行时组件"""
        self.logger.info("Initializing Signal Runtime...")
        
        self.lifecycle = RuntimeLifecycle("signal")
        self.metrics = RuntimeMetrics("signal")
        self.health_check = RuntimeHealthCheck("signal")
        
        self.consumer = RuntimeConsumer(ConsumerConfig(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            topics=[Topics.EVENTS],
            group_id=ConsumerGroup.SIGNAL_RUNTIME,
        ))
        
        self.publisher = RuntimePublisher(PublisherConfig(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            topic=Topics.DECISIONS,
        ))
        
        await self.consumer.start()
        await self.publisher.start()
        
        try:
            from services.fusion_service import FusionEngine
            self.fusion_engine = FusionEngine(
                window_seconds=self.config.fusion_window_seconds,
                min_events=self.config.fusion_min_events,
                min_confidence=self.config.fusion_min_confidence,
            )
            self.logger.info("Fusion engine initialized")
        except Exception as e:
            self.logger.warning(f"Fusion engine init failed: {e}")
        
        try:
            from services.strategy_service.strategies import create_default_strategies
            self.strategy_orchestrator = create_default_strategies()
            self.logger.info("Strategy orchestrator initialized")
        except Exception as e:
            self.logger.warning(f"Strategy orchestrator init failed: {e}")
        
        self.health_check.register_check("fusion_engine", self._check_fusion_engine)
        self.health_check.register_check("strategy_orchestrator", self._check_strategy)
        self.health_check.register_check("consumer", self.consumer.is_healthy)
        self.health_check.register_check("publisher", self.publisher.is_healthy)
        
        self.logger.info("Signal Runtime initialized successfully")
    
    async def _check_fusion_engine(self) -> bool:
        return self.fusion_engine is not None
    
    async def _check_strategy(self) -> bool:
        return self.strategy_orchestrator is not None
    
    async def shutdown(self) -> None:
        """关闭运行时组件"""
        self.logger.info("Shutting down Signal Runtime...")
        
        if self.consumer:
            await self.consumer.stop()
        if self.publisher:
            await self.publisher.stop()
        
        self.logger.info(f"Signal Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Signal Runtime main loop...")
        
        await self.lifecycle.transition_to_running()
        
        while not self.context.is_shutdown_requested():
            try:
                message = await self.consumer.consume(timeout=1.0)
                if message:
                    await self._process_event(message)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)
    
    async def _process_event(self, message: Dict[str, Any]) -> None:
        """处理事件（运行时编排）"""
        trace_id = message.get("trace_id", "unknown")
        
        self.metrics.increment("events_received")
        
        with self.metrics.timing("event_processing"):
            signals = await self._fuse_events(message)
            
            if signals:
                decisions = await self._run_strategies(signals)
                
                for decision in decisions:
                    await self.publisher.publish(decision)
                    self.metrics.increment("decisions_made")
    
    async def _fuse_events(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """融合事件（调用 services/fusion_service/）"""
        if not self.fusion_engine:
            return []
        
        try:
            from services.fusion_service import FusionEvent
            
            fusion_event = FusionEvent(
                id=message.get("event_id", ""),
                timestamp=datetime.now(),
                source=message.get("source", "unknown"),
                event_type=message.get("event_type", ""),
                category=message.get("category", ""),
                asset=message.get("asset"),
                direction=message.get("direction", "neutral"),
                strength=message.get("strength", 0.5),
            )
            
            self.fusion_engine.add_event(fusion_event)
            
            signals = self.fusion_engine.process(price_change=0.02)
            
            if signals:
                self.metrics.increment("signals_generated", len(signals))
                return self._resolve_conflicts(signals)
            
            return []
            
        except Exception as e:
            self.logger.error(f"Fusion error: {e}")
            return []
    
    def _resolve_conflicts(self, signals: List[Any]) -> List[Dict[str, Any]]:
        """冲突解决（业务逻辑）"""
        if not signals:
            return []
        
        asset_map = defaultdict(lambda: {"bullish": 0.0, "bearish": 0.0, "events": 0})
        
        for s in signals:
            asset = s.assets[0] if s.assets else "CRYPTO"
            direction = s.direction
            
            if direction == "bullish":
                asset_map[asset]["bullish"] += s.confidence
            elif direction == "bearish":
                asset_map[asset]["bearish"] += s.confidence
            
            asset_map[asset]["events"] += 1
        
        final_signals = []
        
        for asset, v in asset_map.items():
            net = v["bullish"] - v["bearish"]
            
            if abs(net) < 0.05:
                continue
            
            direction = "bullish" if net > 0 else "bearish"
            confidence = abs(net)
            
            final_signals.append({
                "asset": asset,
                "signal": f"{asset}_{direction.upper()}",
                "direction": direction,
                "confidence": confidence,
                "event_count": v["events"],
            })
        
        return final_signals
    
    async def _run_strategies(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """运行策略（调用 services/strategy_service/）"""
        if not self.strategy_orchestrator or not signals:
            return []
        
        decisions = []
        
        for signal in signals:
            try:
                strategy_signals = self.strategy_orchestrator.process(signal)
                
                if strategy_signals:
                    decision = self._convert_to_decision(strategy_signals, signal)
                    decisions.append(decision)
                    
            except Exception as e:
                self.logger.error(f"Strategy error: {e}")
        
        return decisions
    
    def _convert_to_decision(self, strategy_signals: List[Any], signal: Dict[str, Any]) -> Dict[str, Any]:
        """转换策略信号为决策"""
        if not strategy_signals:
            return {
                "action": "HOLD",
                "symbol": f"{signal.get('asset', 'BTC')}USDT",
                "quantity": 0.0,
                "confidence": 0.0,
                "reason": "无策略信号",
            }
        
        direction_votes = defaultdict(float)
        total_confidence = 0.0
        
        for sig in strategy_signals:
            weight = sig.confidence
            direction_votes[sig.action] += weight
            total_confidence += weight
        
        if not direction_votes:
            action = "HOLD"
            confidence = 0.0
        else:
            sorted_directions = sorted(
                direction_votes.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            action = sorted_directions[0][0]
            confidence = sorted_directions[0][1] / max(total_confidence, 0.001)
        
        return {
            "trace_id": signal.get("trace_id", ""),
            "action": action,
            "symbol": f"{signal.get('asset', 'BTC')}USDT",
            "quantity": min(confidence * 0.08, 0.1),
            "confidence": confidence,
            "reason": f"信号{signal.get('signal', '')}，置信度 {confidence:.3f}",
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


_signal_runtime: Optional[SignalRuntime] = None


def get_signal_runtime() -> SignalRuntime:
    """获取 Signal Runtime 单例"""
    global _signal_runtime
    if _signal_runtime is None:
        _signal_runtime = SignalRuntime()
    return _signal_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Signal Runtime - Event Fusion + Strategy")
    print("=" * 60)
    
    runtime = get_signal_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
