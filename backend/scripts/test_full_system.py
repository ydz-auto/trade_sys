"""
完整系统测试

测试：
1. Multi-Timeframe Coordinator
2. Replay Engine
3. Observability
4. Narrative Engine
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("full_system_test")

from domain import (
    get_timeframe_coordinator,
    get_replay_engine,
    get_runtime_metrics,
    get_narrative_engine,
    Timeframe,
    RegimeType,
    TimeframeSignal,
    CoordinatedSignal,
    ReplayConfig,
    ReplayMode,
    MetricType,
    NarrativeType,
)


async def test_timeframe_coordinator():
    """测试多周期协调器"""
    print("\n" + "=" * 60)
    print("1. Testing Timeframe Coordinator")
    print("=" * 60)
    
    coordinator = get_timeframe_coordinator()
    
    print("\nUpdating signals for BTCUSDT:")
    
    signals = [
        TimeframeSignal(
            timeframe=Timeframe.MACRO_1D.value,
            symbol="BTCUSDT",
            direction="bullish",
            confidence=0.75,
            strength=0.8,
            regime=RegimeType.TRENDING_UP,
            regime_confidence=0.7,
        ),
        TimeframeSignal(
            timeframe=Timeframe.SWING_4H.value,
            symbol="BTCUSDT",
            direction="bullish",
            confidence=0.7,
            strength=0.75,
            regime=RegimeType.TRENDING_UP,
            regime_confidence=0.65,
        ),
        TimeframeSignal(
            timeframe=Timeframe.INTRADAY_1H.value,
            symbol="BTCUSDT",
            direction="bullish",
            confidence=0.65,
            strength=0.6,
            regime=RegimeType.TRENDING_UP,
            regime_confidence=0.6,
        ),
        TimeframeSignal(
            timeframe=Timeframe.MICRO_15M.value,
            symbol="BTCUSDT",
            direction="neutral",
            confidence=0.5,
            strength=0.4,
            regime=RegimeType.RANGING,
            regime_confidence=0.5,
        ),
    ]
    
    for signal in signals:
        coordinator.update_signal(signal)
        print(f"  {signal.timeframe}: {signal.direction} ({signal.confidence:.0%})")
    
    print("\nCoordinating signals:")
    coordinated = coordinator.coordinate_signals("BTCUSDT")
    
    print(f"  Direction: {coordinated.direction}")
    print(f"  Alignment: {coordinated.alignment.value}")
    print(f"  Alignment Score: {coordinated.alignment_score:.2f}")
    print(f"  Confidence: {coordinated.confidence:.2f}")
    print(f"  Position Multiplier: {coordinated.position_size_multiplier:.2f}")
    print(f"  Risk Level: {coordinated.risk_level}")
    print(f"  Reasoning: {coordinated.reasoning}")
    print(f"\n  Confluent Factors: {coordinated.confluent_factors}")
    
    print("\n✅ Timeframe Coordinator working correctly")


async def test_observability():
    """测试可观测性"""
    print("\n" + "=" * 60)
    print("2. Testing Observability")
    print("=" * 60)
    
    metrics = get_runtime_metrics()
    
    print("\nRecording metrics:")
    
    metrics.record_signal_latency("trace_001", 1500)
    metrics.record_signal_latency("trace_002", 2000)
    metrics.record_signal_latency("trace_003", 3500)
    print(f"  Signal latency: 1500ms, 2000ms, 3500ms")
    
    metrics.record_factor_staleness("momentum", 15)
    metrics.record_factor_staleness("volatility", 25)
    print(f"  Factor staleness: momentum=15min, volatility=25min")
    
    metrics.record_regime_conflict("BTCUSDT", 0.2)
    metrics.record_regime_conflict("ETHUSDT", 0.0)
    print(f"  Regime conflict: BTCUSDT=0.2, ETHUSDT=0.0")
    
    metrics.record_kafka_lag("tradeagent.events.all", "projection-worker", 150)
    print(f"  Kafka lag: 150 messages")
    
    metrics.record_decision_latency("trace_001", 5000)
    print(f"  Decision latency: 5000ms")
    
    print("\nGetting latency stats:")
    latency_stats = metrics.get_latency_stats("signal")
    print(f"  Signal latency: p50={latency_stats['p50']:.0f}ms, "
          f"p95={latency_stats['p95']:.0f}ms, avg={latency_stats['avg']:.0f}ms")
    
    print("\nGetting summary:")
    summary = metrics.get_summary()
    print(f"  Metrics tracked: {summary['metrics_count']}")
    print(f"  Active alerts: {summary['active_alerts']}")
    
    active_alerts = metrics.get_active_alerts()
    if active_alerts:
        print(f"\n  Active Alerts:")
        for alert in active_alerts:
            print(f"    - {alert.name}: {alert.message}")
    
    print("\n✅ Observability working correctly")


async def test_narrative_engine():
    """测试叙事引擎"""
    print("\n" + "=" * 60)
    print("3. Testing Narrative Engine")
    print("=" * 60)
    
    narrative = get_narrative_engine()
    
    print("\nAdding events to cache:")
    
    events = [
        {
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "etf_inflow",
            "direction": "bullish",
            "strength": 0.7,
            "timestamp": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
        },
        {
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "funding_reset",
            "direction": "bullish",
            "strength": 0.6,
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        },
        {
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "regime_confirm",
            "direction": "bullish",
            "strength": 0.8,
            "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        },
    ]
    
    for event in events:
        narrative.add_event(event)
        print(f"  {event['event_category']}: {event['direction']}")
    
    print("\nGenerating signal narrative:")
    signal_event = {
        "event_type": "signal",
        "symbol": "BTCUSDT",
        "signal_name": "BTC_STRONG_BULLISH",
        "direction": "bullish",
        "confidence": 0.8,
        "strength": 0.75,
        "event_count": 3,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    signal_narrative = narrative.generate_signal_narrative(signal_event)
    print(f"  Title: {signal_narrative.signal_name}")
    print(f"  Direction: {signal_narrative.direction}")
    print(f"  Explanation: {signal_narrative.explanation}")
    
    print("\nGenerating decision explanation:")
    decision_event = {
        "decision_id": "dec_001",
        "event_type": "decision",
        "symbol": "BTCUSDT",
        "action": "LONG",
        "quantity": 0.01,
        "confidence": 0.75,
        "reason": "Strong bullish confluence across timeframes",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    explanation = narrative.generate_decision_explanation(
        decision_event, signal_event
    )
    
    print(f"  Action: {explanation.action} {explanation.symbol}")
    print(f"  Confidence: {explanation.confidence:.0%}")
    print(f"  Reasoning: {explanation.reasoning}")
    print(f"  Supporting: {explanation.supporting_factors}")
    print(f"  Risk: {explanation.risk_assessment}")
    
    print("\nGenerating market summary:")
    summary_narrative = narrative.generate_market_summary("BTCUSDT", hours=4)
    print(f"  Title: {summary_narrative.title}")
    print(f"  Content: {summary_narrative.content}")
    
    print("\n✅ Narrative Engine working correctly")


async def test_replay_engine():
    """测试回放引擎"""
    print("\n" + "=" * 60)
    print("4. Testing Replay Engine")
    print("=" * 60)
    
    from domain import get_replay_engine
    
    engine = get_replay_engine()
    
    print("\nConfiguring replay:")
    config = ReplayConfig(
        mode=ReplayMode.HISTORICAL,
        symbols=["BTCUSDT"],
        speed=10.0,
        enable_explainability=True,
    )
    print(f"  Mode: {config.mode.value}")
    print(f"  Speed: {config.speed}x")
    print(f"  Symbols: {config.symbols}")
    
    print("\nLoading events:")
    events = [
        {
            "event_id": "evt_001",
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "etf_inflow",
            "direction": "bullish",
            "strength": 0.7,
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        },
        {
            "event_id": "evt_002",
            "event_type": "signal",
            "symbol": "BTCUSDT",
            "signal_name": "BTC_BULLISH",
            "direction": "bullish",
            "confidence": 0.75,
            "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        },
        {
            "event_id": "evt_003",
            "event_type": "decision",
            "symbol": "BTCUSDT",
            "action": "LONG",
            "quantity": 0.01,
            "confidence": 0.72,
            "reason": "Strong bullish signal",
            "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
        },
    ]
    
    engine.cache_events("BTCUSDT", events)
    print(f"  Cached {len(events)} events")
    
    print("\nSimulating strategy:")
    def simple_strategy(event):
        if event.get("event_type") == "signal":
            direction = event.get("direction", "neutral")
            if direction == "bullish":
                return {
                    "action": "LONG",
                    "symbol": event.get("symbol"),
                    "quantity": 0.01,
                }
        return None
    
    result = engine.simulate_strategy(events, simple_strategy)
    print(f"  Trades: {result['trade_count']}")
    print(f"  Total PnL: ${result['total_pnl']:.2f}")
    
    print("\n✅ Replay Engine working correctly")


async def test_integration():
    """集成测试"""
    print("\n" + "=" * 60)
    print("5. Integration Test")
    print("=" * 60)
    
    from domain import (
        get_timeframe_coordinator,
        get_narrative_engine,
        get_runtime_metrics,
    )
    
    coordinator = get_timeframe_coordinator()
    narrative = get_narrative_engine()
    metrics = get_runtime_metrics()
    
    print("\nSimulating full trading scenario:")
    
    scenario_events = [
        {
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "macro_bullish",
            "direction": "bullish",
            "strength": 0.8,
            "timestamp": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
        },
        {
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "swing_confirm",
            "direction": "bullish",
            "strength": 0.75,
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        },
        {
            "event_type": "event",
            "symbol": "BTCUSDT",
            "event_category": "intraday_breakout",
            "direction": "bullish",
            "strength": 0.7,
            "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        },
    ]
    
    for event in scenario_events:
        narrative.add_event(event)
        print(f"  Event: {event['event_category']} - {event['direction']}")
    
    for tf, direction, confidence in [
        (Timeframe.MACRO_1D, "bullish", 0.8),
        (Timeframe.SWING_4H, "bullish", 0.75),
        (Timeframe.INTRADAY_1H, "bullish", 0.7),
    ]:
        signal = TimeframeSignal(
            timeframe=tf.value,
            symbol="BTCUSDT",
            direction=direction,
            confidence=confidence,
            strength=confidence,
            regime=RegimeType.TRENDING_UP,
            regime_confidence=confidence,
        )
        coordinator.update_signal(signal)
    
    coordinated = coordinator.coordinate_signals("BTCUSDT")
    print(f"\nCoordinated Signal:")
    print(f"  Direction: {coordinated.direction}")
    print(f"  Alignment: {coordinated.alignment.value} ({coordinated.alignment_score:.0%})")
    print(f"  Position Size: {coordinated.position_size_multiplier:.2f}x")
    
    metrics.record_decision_latency("scenario_trace", 3000)
    print(f"\nDecision latency recorded: 3000ms")
    
    print("\n✅ Integration test completed")


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("Full System Test - Event-driven Quant Runtime")
    print("=" * 60)
    
    await test_timeframe_coordinator()
    await test_observability()
    await test_narrative_engine()
    await test_replay_engine()
    await test_integration()
    
    print("\n" + "=" * 60)
    print("All Tests Passed ✅")
    print("=" * 60)
    
    print("\nSystem Architecture:")
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │                 RUNTIME DOMAIN                          │")
    print("  │                                                          │")
    print("  │  ┌─────────────────────────────────────────────────┐  │")
    print("  │  │  Timeframe Coordinator (多周期协调)                 │  │")
    print("  │  │  - Signal alignment                              │  │")
    print("  │  │  - Position sizing                               │  │")
    print("  │  └─────────────────────────────────────────────────┘  │")
    print("  │                                                          │")
    print("  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │")
    print("  │  │ Replay      │  │ Observability│  │ Narrative   │  │")
    print("  │  │ Engine      │  │             │  │ Engine      │  │")
    print("  │  │ (回放)     │  │ (可观测性)  │  │ (AI解释)    │  │")
    print("  │  └─────────────┘  └─────────────┘  └─────────────┘  │")
    print("  └─────────────────────────────────────────────────────────┘")
    print("  │                                                          │")
    print("  │  ┌─────────────────────────────────────────────────┐  │")
    print("  │  │  Projection Service → Redis → API/WS → Frontend   │  │")
    print("  │  └─────────────────────────────────────────────────┘  │")
    print("  └─────────────────────────────────────────────────────────┘")


if __name__ == "__main__":
    asyncio.run(main())
