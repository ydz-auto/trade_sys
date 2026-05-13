"""
Strategy Worker - 事件处理 + 信号融合 + 策略决策

合并 event_service + fusion_service + strategy_service

职责：
1. 消费 RAW_DATA，提取事件
2. 融合多个事件，生成信号
3. 运行策略，生成决策

用法:
    python -m services.workers.strategy_worker
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("workers.strategy_worker")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import (
    RawDataEvent,
    AnalysisEvent,
    SignalEvent,
    DecisionEvent,
    EventType,
    EventSource,
    parse_event,
)
from domain.event import EventType as DomainEventType, Direction, get_direction

from services.fusion_service import FusionEngine, FusionEvent
from services.strategy_service.strategies import (
    create_default_strategies,
    StrategySignal,
    ActionType,
)


class SimpleEventDetector:
    """简化版事件检测器"""

    EVENT_PATTERNS = {
        "inflow": DomainEventType.FLOW_ETF_INFLOW,
        "outflow": DomainEventType.FLOW_ETF_OUTFLOW,
        "etf": DomainEventType.POLICY_ETF_APPROVAL,
        "hack": DomainEventType.PROTOCOL_HACK,
        "exploit": DomainEventType.PROTOCOL_HACK,
        "depeg": DomainEventType.RISK_STABLECOIN_DEPEG,
        "institutional": DomainEventType.POLICY_REGULATION_POSITIVE,
        "adoption": DomainEventType.POLICY_REGULATION_POSITIVE,
    }

    def detect(self, title: str, content: str, trace_id: str = None) -> Optional[AnalysisEvent]:
        text = (title + " " + content).lower()

        for keyword, event_type in self.EVENT_PATTERNS.items():
            if keyword in text:
                direction = get_direction(event_type)
                strength = 0.7 + (0.3 * hash(title) % 100 / 100)

                asset = "BTC"
                if "eth" in text or "ethereum" in text:
                    asset = "ETH"
                elif "sol" in text or "solana" in text:
                    asset = "SOL"
                
                symbol = self._normalize_symbol(asset)

                return AnalysisEvent(
                    trace_id=trace_id,
                    source=EventSource.STRATEGY_WORKER,
                    symbol=symbol,
                    event_category=event_type.category.value,
                    direction=direction.value,
                    strength=min(strength, 1.0),
                    raw_event_type=event_type.value,
                    affected_symbols=[asset],
                    metadata={"title": title, "source": "coindesk"},
                )

        return None
    
    def _normalize_symbol(self, asset: str) -> str:
        """标准化交易对格式"""
        asset = asset.upper()
        return f"{asset}USDT"


class StrategyWorker:
    """
    策略 Worker
    
    合并 event_service + fusion_service + strategy_service
    """
    
    def __init__(self):
        self.broker = None
        self.event_detector = SimpleEventDetector()
        self.fusion_engine = FusionEngine(
            window_seconds=300,
            min_events=1,
            min_confidence=0.3,
        )
        self.strategy_orchestrator = None
        
        self._running = False
        self._stats = {
            "raw_data_received": 0,
            "events_detected": 0,
            "signals_generated": 0,
            "decisions_made": 0,
            "errors": 0,
        }
    
    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Strategy Worker...")
        
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.broker = get_broker(bootstrap_servers)
        
        self.strategy_orchestrator = create_default_strategies()
        logger.info("Strategy orchestrator initialized")
        
        self._running = True
        logger.info("Strategy Worker initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Strategy Worker...")
        self._running = False
        
        if self.broker:
            await self.broker.stop()
        
        logger.info(f"Strategy Worker stopped. Stats: {self._stats}")
    
    async def process_raw_data(self, msg: dict) -> Optional[AnalysisEvent]:
        """
        处理原始数据 -> 提取事件
        
        原 event_service 逻辑
        """
        try:
            raw_event = RawDataEvent(**msg) if isinstance(msg, dict) else msg
            self._stats["raw_data_received"] += 1
            
            trace_id = raw_event.trace_id
            logger.debug(f"[{trace_id}] Processing raw data")
            
            data = raw_event.data
            title = data.get("title", "") if isinstance(data, dict) else ""
            content = data.get("content", "") if isinstance(data, dict) else ""
            
            event = self.event_detector.detect(title, content, trace_id=trace_id)
            
            if event:
                self._stats["events_detected"] += 1
                logger.info(f"[{trace_id}] Detected event: {event.raw_event_type} -> {event.symbol}")
                return event
            else:
                logger.debug(f"[{trace_id}] No event detected")
                return None
                
        except Exception as e:
            logger.error(f"Error processing raw data: {e}")
            self._stats["errors"] += 1
            return None
    
    def resolve_signal_conflicts(self, signals: list, trace_id: str = None) -> list[SignalEvent]:
        """冲突解决：多个信号 → 每个资产一个最终信号"""
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
            
            symbol = self._normalize_symbol(asset)

            signal = SignalEvent(
                trace_id=trace_id,
                source=EventSource.STRATEGY_WORKER,
                symbol=symbol,
                signal_name=f"{asset}_{direction.upper()}",
                direction=direction,
                confidence=confidence,
                event_count=v["events"],
            )
            final_signals.append(signal)

        return final_signals
    
    async def process_event(self, event: AnalysisEvent) -> list[SignalEvent]:
        """
        处理事件 -> 融合 -> 生成信号
        
        原 fusion_service 逻辑
        """
        try:
            trace_id = event.trace_id
            
            fusion_event = FusionEvent(
                id=event.event_id,
                timestamp=event.timestamp if isinstance(event.timestamp, datetime) else datetime.now(),
                source="strategy_worker",
                event_type=event.raw_event_type,
                category=event.event_category,
                asset=event.symbol,
                direction=event.direction,
                strength=event.strength,
                sources=[],
            )

            self.fusion_engine.add_event(fusion_event)
            logger.debug(f"[{trace_id}] Buffer size: {self.fusion_engine.get_buffer_size()}")

            signals = self.fusion_engine.process(price_change=0.02)

            if not signals:
                return []

            self._stats["signals_generated"] += len(signals)
            
            final_signals = self.resolve_signal_conflicts(signals, trace_id=trace_id)
            
            return final_signals
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            self._stats["errors"] += 1
            return []
    
    def _normalize_symbol(self, asset: str) -> str:
        """标准化交易对格式"""
        asset = asset.upper()
        if "USDT" not in asset:
            return f"{asset}USDT"
        return asset
    
    def generate_decision(self, signal: SignalEvent) -> DecisionEvent:
        """生成决策"""
        confidence = signal.confidence
        
        if confidence < 0.1:
            action = "HOLD"
            quantity = 0.0
            reason = "信号模糊"
        elif signal.direction == "bullish":
            action = "LONG"
            quantity = min(confidence * 0.08, 0.1)
            reason = f"信号看涨，置信度 {confidence:.3f}"
        elif signal.direction == "bearish":
            action = "SHORT"
            quantity = min(confidence * 0.08, 0.1)
            reason = f"信号看跌，置信度 {confidence:.3f}"
        else:
            action = "HOLD"
            quantity = 0.0
            reason = "中性信号"
        
        return DecisionEvent(
            trace_id=signal.trace_id,
            parent_event_id=signal.event_id,
            source=EventSource.STRATEGY_WORKER,
            symbol=signal.symbol,
            action=action,
            quantity=quantity,
            confidence=confidence,
            reason=reason,
        )
    
    async def handle_raw_data(self, msg: dict) -> None:
        """
        完整处理链：RAW_DATA -> Event -> Signal -> Decision
        """
        try:
            event = await self.process_raw_data(msg)
            if not event:
                return
            
            signals = await self.process_event(event)
            if not signals:
                return
            
            for signal in signals:
                decision = self.generate_decision(signal)
                
                self._stats["decisions_made"] += 1
                
                print("\n" + "=" * 70)
                print("🎯 STRATEGY WORKER DECISION")
                print("=" * 70)
                print(f"  Trace ID:   {decision.trace_id}")
                print(f"  Symbol:     {decision.symbol}")
                print(f"  Action:     {decision.action}")
                print(f"  Quantity:   {decision.quantity:.4f}")
                print(f"  Confidence: {decision.confidence:.3f}")
                print(f"  Reason:     {decision.reason}")
                print("=" * 70 + "\n")
                
                if self.broker:
                    await self.broker.publish(
                        message=decision.model_dump(),
                        topic=Topics.DECISIONS,
                        key=decision.symbol,
                    )
                    logger.info(f"[{decision.trace_id}] Published decision: {decision.action} on {decision.symbol}")
                    
        except Exception as e:
            logger.error(f"Error in processing chain: {e}")
            self._stats["errors"] += 1
    
    async def run(self) -> None:
        """运行 Worker"""
        await self.initialize()
        
        try:
            logger.info("Subscribing to RAW_DATA topic...")
            
            @self.broker.subscriber(Topics.RAW_DATA)
            async def on_raw_data(msg: dict):
                await self.handle_raw_data(msg)
            
            await self.broker.run()
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.shutdown()
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            **self._stats
        }


async def main():
    """主入口"""
    print("=" * 60)
    print("Strategy Worker - Event + Fusion + Strategy")
    print("=" * 60)
    print(f"Subscribe: {Topics.RAW_DATA}")
    print(f"Publish: {Topics.DECISIONS}")
    print("=" * 60)
    
    worker = StrategyWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
