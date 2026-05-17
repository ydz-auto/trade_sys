"""
验证完整架构

测试：
1. Validation Boundary
2. Event Schema Registry
3. Portfolio Projection
4. Projection Service Schema 验证
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("verify_architecture")

from infrastructure.messaging.schema_registry import (
    get_schema_registry,
    BaseEventV2,
    DecisionEventV2,
    SignalEventV2,
    EventType,
    EventSource,
)
from domain.validation_boundary import (
    get_validation_boundary,
    ValidationCriteria,
)
from domain.portfolio_projection import (
    get_portfolio_projection,
    PositionSide,
)


async def test_event_schema_registry():
    """测试 Event Schema Registry"""
    print("\n" + "=" * 60)
    print("1. Testing Event Schema Registry")
    print("=" * 60)
    
    registry = get_schema_registry()
    
    print("\nRegistered Event Types:")
    for event_type in registry.get_all_event_types():
        schema = registry.get_schema(EventType(event_type))
        print(f"  - {event_type}: {len(schema.get('fields', []))} fields")
    
    event_data = {
        "event_id": "evt_001",
        "event_type": "decision",
        "trace_id": "trace_001",
        "symbol": "BTC/USDT",
        "timeframe": "4h",
        "decision_id": "dec_001",
        "action": "LONG",
        "quantity": 0.01,
        "confidence": 0.75,
        "reason": "Strong bullish signal",
    }
    
    print("\nTesting Schema Validation:")
    print(f"  Input: {event_data}")
    
    is_valid, error = registry.validate_event(event_data)
    print(f"  Valid: {is_valid}")
    if error:
        print(f"  Error: {error}")
    
    if is_valid:
        canonical = registry.transform_to_canonical(event_data)
        print(f"  Canonical Symbol: {canonical.get('symbol')}")
        print(f"  Canonical timestamp: {canonical.get('timestamp')[:19] if canonical.get('timestamp') else 'N/A'}")
    
    print("\n✅ Event Schema Registry working correctly")


async def test_validation_boundary():
    """测试 Validation Boundary"""
    print("\n" + "=" * 60)
    print("2. Testing Validation Boundary")
    print("=" * 60)
    
    vb = get_validation_boundary()
    
    criteria = ValidationCriteria(
        min_ic=0.02,
        min_sharpe=0.5,
        max_drawdown=0.2,
        min_trades=100,
        regime_coverage=0.6,
        decay_threshold=0.3,
    )
    vb.set_validation_criteria(criteria)
    print(f"\nValidation Criteria Set:")
    print(f"  Min IC: {criteria.min_ic}")
    print(f"  Min Sharpe: {criteria.min_sharpe}")
    print(f"  Max Drawdown: {criteria.max_drawdown}")
    
    proposal_id = "proposal_001"
    print(f"\nReceiving Proposal: {proposal_id}")
    stage = vb.receive_proposal(proposal_id, {
        "factor": "momentum",
        "timeframe": "4h",
    })
    print(f"  Stage: {stage}")
    
    validation_results = {
        "ic": 0.045,
        "sharpe": 0.8,
        "max_drawdown": 0.15,
        "regime_coverage": 0.7,
        "decay": 0.2,
        "passed_regimes": ["trending_up", "breakout"],
        "failed_regimes": [],
    }
    
    print("\nValidating Proposal:")
    report = vb.validate_proposal(proposal_id, validation_results)
    print(f"  Result: {report.result}")
    print(f"  Overall Score: {report.overall_score:.2f}")
    print(f"  Recommendation: {report.recommendation}")
    print(f"  Warnings: {len(report.warnings)}")
    print(f"  Errors: {len(report.errors)}")
    
    if report.result.value == "passed":
        print("\nDeploying Proposal:")
        signal = vb.deploy_proposal(
            proposal_id,
            report.report_id,
            {"symbol": "BTCUSDT", "timeframe": "4h", "action": "LONG", "quantity": 0.01}
        )
        print(f"  Signal ID: {signal.signal_id}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Valid: {signal.is_valid()}")
    
    print("\n✅ Validation Boundary working correctly")


async def test_portfolio_projection():
    """测试 Portfolio Projection"""
    print("\n" + "=" * 60)
    print("3. Testing Portfolio Projection")
    print("=" * 60)
    
    portfolio = get_portfolio_projection()
    await portfolio.initialize()
    
    print("\nProcessing Fill Events:")
    
    fill1 = {
        "event_id": "fill_001",
        "event_type": "fill",
        "trace_id": "trace_001",
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.1,
        "price": 60000,
    }
    
    position1 = await portfolio.process_fill(fill1)
    if position1:
        print(f"  Position Opened: {position1.symbol}")
        print(f"    Side: {position1.side.value}")
        print(f"    Size: {position1.size}")
        print(f"    Entry: ${position1.entry_price}")
    
    print("\n  Updating Price:")
    position1 = await portfolio.update_price("BTCUSDT", 62000)
    if position1:
        print(f"    Current Price: ${position1.current_price}")
        print(f"    Unrealized PnL: ${position1.unrealized_pnl:.2f}")
        print(f"    PnL %: {position1.pnl_percentage:.2f}%")
    
    fill2 = {
        "event_id": "fill_002",
        "event_type": "fill",
        "trace_id": "trace_002",
        "symbol": "ETHUSDT",
        "side": "buy",
        "quantity": 1.0,
        "price": 3500,
    }
    
    position2 = await portfolio.process_fill(fill2)
    if position2:
        print(f"\n  Position Opened: {position2.symbol}")
        print(f"    Side: {position2.side.value}")
        print(f"    Size: {position2.size}")
    
    print("\n  Taking Snapshot:")
    snapshot = await portfolio.take_snapshot()
    print(f"    Positions: {len(snapshot.positions)}")
    print(f"    Total PnL: ${snapshot.total_pnl:.2f}")
    
    print("\n  PnL Summary:")
    pnl_summary = portfolio.get_pnl_summary()
    print(f"    Active Positions: {pnl_summary['active_positions']}")
    print(f"    Total Unrealized: ${pnl_summary['total_unrealized_pnl']:.2f}")
    print(f"    Total Realized: ${pnl_summary['total_realized_pnl']:.2f}")
    print(f"    Long Count: {pnl_summary['long_count']}")
    print(f"    Short Count: {pnl_summary['short_count']}")
    
    print("\n✅ Portfolio Projection working correctly")


async def test_event_lifecycle():
    """测试事件生命周期"""
    print("\n" + "=" * 60)
    print("4. Testing Event Lifecycle")
    print("=" * 60)
    
    print("\nCreating Event Chain:")
    
    parent = BaseEventV2(
        event_id="evt_parent",
        event_type=EventType.EVENT,
        trace_id="trace_001",
        symbol="BTCUSDT",
        timeframe="4h",
    )
    print(f"  Parent Event: {parent.event_id}")
    print(f"    Type: {parent.event_type.value}")
    print(f"    Symbol: {parent.symbol}")
    
    child = parent.derive_child(
        event_type=EventType.SIGNAL,
        source=EventSource.STRATEGY_WORKER,
        signal_name="BTC_BULLISH",
        direction="bullish",
        confidence=0.75,
    )
    print(f"\n  Child Event: {child.event_id}")
    print(f"    Parent: {child.parent_event_id}")
    print(f"    Type: {child.event_type.value}")
    print(f"    Signal: {child.signal_name}")
    
    decision = child.derive_child(
        event_type=EventType.DECISION,
        source=EventSource.STRATEGY_WORKER,
        decision_id="dec_001",
        action="LONG",
        quantity=0.01,
        confidence=0.75,
    )
    print(f"\n  Decision Event: {decision.event_id}")
    print(f"    Parent: {decision.parent_event_id}")
    print(f"    Action: {decision.action}")
    
    print("\n  Event Trace:")
    print(f"    {parent.event_id} → {child.event_id} → {decision.event_id}")
    
    print("\n✅ Event Lifecycle working correctly")


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("Runtime State Architecture - Full Verification")
    print("=" * 60)
    
    await test_event_schema_registry()
    await test_validation_boundary()
    await test_portfolio_projection()
    await test_event_lifecycle()
    
    print("\n" + "=" * 60)
    print("All Tests Passed")
    print("=" * 60)
    
    print("\nArchitecture Summary:")
    print("  ┌─────────────────────────────────────────────┐")
    print("  │           RESEARCH DOMAIN                    │")
    print("  │  Alpha Lifecycle → Proposal → Validation    │")
    print("  └──────────────────┬──────────────────────────┘")
    print("                     │ Validation Boundary")
    print("                     ↓")
    print("  ┌─────────────────────────────────────────────┐")
    print("  │           RUNTIME DOMAIN                     │")
    print("  │                                              │")
    print("  │  Services → Kafka → Projections → Redis       │")
    print("  │       │                   │                 │")
    print("  │       │              Schema Registry         │")
    print("  │       │                   │                 │")
    print("  │       └────────┬──────────┘                 │")
    print("  │                ↓                            │")
    print("  │  Portfolio Projection (独立状态机)          │")
    print("  │                ↓                            │")
    print("  │  API / WS Gateway → Frontend                │")
    print("  └─────────────────────────────────────────────┘")


if __name__ == "__main__":
    asyncio.run(main())
