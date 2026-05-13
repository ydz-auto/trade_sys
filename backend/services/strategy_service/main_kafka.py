"""
Strategy Service - 增强版 Kafka Consumer + Producer

消费 signals，运行策略，输出决策到 execution_service

用法:
    python -m services.strategy_service.main_kafka
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import os
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("strategy_service.kafka")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import Signal, Decision
from services.strategy_service.strategies import (
    create_default_strategies,
    StrategySignal,
    ActionType,
)
from shared.observability import get_observability_manager
from shared.service_registry import get_service_registry, ServiceEndpoint


# 全局变量
broker = None
strategy_orchestrator = None
observability = None
service_registry = None


def convert_strategy_signals(signals: list, fusion_signal: Signal) -> Decision:
    """
    将策略信号转换为决策
    
    Args:
        signals: 策略信号列表
        fusion_signal: 原始融合信号
        
    Returns:
        Decision
    """
    if not signals:
        return Decision(
            decision_id=f"dec_{int(datetime.now().timestamp() * 1000)}",
            action="HOLD",
            symbol=fusion_signal.assets[0] if fusion_signal.assets else "BTCUSDT",
            quantity=0.0,
            price=None,
            confidence=0.0,
            reason="无策略信号",
            source="strategy_service",
            timestamp=int(datetime.now().timestamp() * 1000),
            metadata={},
        )
    
    # 统计信号方向
    direction_votes = defaultdict(float)
    total_confidence = 0.0
    
    for sig in signals:
        weight = sig.confidence
        direction_votes[sig.action] += weight
        total_confidence += weight
    
    # 找出占优方向
    if not direction_votes:
        action = "HOLD"
    else:
        sorted_directions = sorted(
            direction_votes.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        dominant_action = sorted_directions[0][0]
        confidence = sorted_directions[0][1] / max(total_confidence, 0.001)
        
        if dominant_action == ActionType.LONG:
            action = "LONG"
        elif dominant_action == ActionType.SHORT:
            action = "SHORT"
        else:
            action = "HOLD"
    
    # 获取第一个信号的信息
    first_sig = signals[0]
    
    return Decision(
        decision_id=f"dec_{int(datetime.now().timestamp() * 1000)}",
        action=action,
        symbol=first_sig.symbol,
        quantity=first_sig.quantity,
        price=first_sig.price,
        confidence=min(1.0, confidence),
        reason=f"策略一致: {', '.join([s.reason for s in signals])}",
        source="strategy_service",
        timestamp=int(datetime.now().timestamp() * 1000),
        metadata={
            "signal_count": len(signals),
            "strategies": [s.strategy_id for s in signals],
            "fusion_signal": {
                "direction": fusion_signal.direction,
                "confidence": fusion_signal.confidence,
                "event_count": fusion_signal.event_count,
            },
        },
    )


def generate_simple_decision(signal: Signal) -> Decision:
    """
    生成简单决策（基于融合信号）
    
    当策略引擎没有可用数据时使用
    """
    confidence = signal.confidence
    
    if confidence < 0.1:
        action = "HOLD"
        quantity = 0.0
        reason = "信号模糊"
    elif signal.direction == "bullish":
        action = "LONG"
        quantity = min(confidence * 0.08, 0.1)  # 降低数量
        reason = f"信号看涨，置信度 {confidence:.3f}"
    elif signal.direction == "bearish":
        action = "SHORT"
        quantity = min(confidence * 0.08, 0.1)  # 降低数量
        reason = f"信号看跌，置信度 {confidence:.3f}"
    else:
        action = "HOLD"
        quantity = 0.0
        reason = "中性信号"
    
    return Decision(
        decision_id=f"dec_{int(datetime.now().timestamp() * 1000)}",
        action=action,
        symbol=signal.assets[0] if signal.assets else "BTCUSDT",
        quantity=quantity,
        price=None,
        confidence=confidence,
        reason=reason,
        source="strategy_service",
        timestamp=int(datetime.now().timestamp() * 1000),
        metadata={"fusion_signal": signal.model_dump()},
    )


async def handle_signal(msg: dict):
    """
    处理融合信号，运行策略，输出决策
    """
    try:
        # 解析信号
        signal = Signal(**msg) if isinstance(msg, dict) else msg
        symbol = signal.assets[0] if signal.assets else "BTCUSDT"
        
        logger.info(f"Received signal: {signal.signal} confidence={signal.confidence:.3f}")
        
        # 记录指标
        if observability:
            observability.record_request(
                "signal_received",
                "GET",
                200,
                0.001,
            )
            observability.record_business_event(
                "signal_processed",
                {"symbol": symbol, "confidence": signal.confidence},
            )
        
        # 运行策略（如果有策略）
        strategy_signals = []
        if strategy_orchestrator:
            # 注：这里需要从 aggregation_service 或市场数据接口获取价格
            # 暂时只使用简单决策逻辑
            strategy_signals = strategy_orchestrator.process()
        
        # 生成决策
        if strategy_signals:
            decision = convert_strategy_signals(strategy_signals, signal)
        else:
            decision = generate_simple_decision(signal)
        
        # 打印决策
        print("\n" + "=" * 70)
        print("🎯 STRATEGY DECISION")
        print("=" * 70)
        print(f"  Symbol:     {decision.symbol}")
        print(f"  Action:     {decision.action}")
        print(f"  Quantity:   {decision.quantity:.4f}")
        print(f"  Price:      {decision.price or 'Market'}")
        print(f"  Confidence: {decision.confidence:.3f}")
        print(f"  Reason:     {decision.reason}")
        print("=" * 70 + "\n")
        
        # 发布决策到 Kafka
        if broker:
            await broker.publish(
                message=decision.model_dump(),
                topic=Topics.DECISIONS,
                key=decision.symbol,
            )
            logger.info(f"Published decision to {Topics.DECISIONS}: {decision.action}")
        
        # 记录指标
        if observability:
            observability.record_business_event(
                "decision_published",
                {"symbol": symbol, "action": decision.action},
            )
        
    except Exception as e:
        logger.error(f"Error handling signal: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def main():
    """主函数"""
    global broker, strategy_orchestrator, observability, service_registry
    
    print("=" * 70)
    print("Strategy Service - Enhanced Kafka Consumer + Producer")
    print("=" * 70)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.SIGNALS}")
    print(f"Publish: {Topics.DECISIONS}")
    print("=" * 70)
    
    # 初始化 observability
    observability = get_observability_manager("strategy_service")
    
    # 初始化 service registry
    service_registry = get_service_registry()
    await service_registry.register(
        service_name="strategy_service",
        version="2.0.0",
        endpoints=[ServiceEndpoint(host="localhost", port=8003)],
        capabilities=["strategy_generation", "decision_making"],
    )
    
    # 创建策略编排器
    strategy_orchestrator = create_default_strategies()
    print("\n✅ Strategy engine initialized: RSI and MACD strategies")
    
    # 初始化 broker
    broker = get_broker(bootstrap_servers)
    
    print("\n[strategy_service] Waiting for signals...\n")
    
    # 订阅信号
    @broker.subscriber(Topics.SIGNALS)
    async def on_signal(msg: dict):
        await handle_signal(msg)
    
    # 运行
    await broker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Strategy service stopped by user")
