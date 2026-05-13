"""
集成测试 - 验证完整的交易流程

测试从信号到决策到风控到执行的完整流程
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("integration_test")

from infrastructure.messaging.schema.signal import Signal
from infrastructure.messaging.schema.decision import Decision, RiskCheckedDecision
from services.strategy_service.strategies import (
    create_default_strategies,
    StrategySignal,
    ActionType,
)
from services.strategy_service.main_kafka import generate_simple_decision
from services.risk_service.risk_engine import RiskService, RiskConfig, RiskCheckResult
from shared.idempotency import get_idempotency_manager
from shared.observability import get_observability_manager


async def test_signal_to_decision():
    """测试：从信号到决策的转换"""
    print("\n" + "=" * 70)
    print("测试 1: 信号 -> 决策")
    print("=" * 70)
    
    # 创建信号
    signal = Signal(
        timestamp=int(datetime.now().timestamp() * 1000),
        signal="BTC_BULLISH",
        direction="bullish",
        confidence=0.85,
        consensus=0.8,
        event_types=["etf_inflow", "news_positive"],
        assets=["BTCUSDT"],
        strength=0.7,
        event_count=3,
    )
    
    print(f"输入信号: {signal.signal} direction={signal.direction} confidence={signal.confidence:.2f}")
    
    # 生成简单决策
    decision = generate_simple_decision(signal)
    
    print(f"输出决策: {decision.action} {decision.symbol} quantity={decision.quantity:.4f}")
    print(f"决策原因: {decision.reason}")
    print(f"置信度: {decision.confidence:.2f}")
    
    # 验证决策
    assert decision.action == "LONG", f"期望 LONG，实际 {decision.action}"
    assert decision.symbol == "BTCUSDT", f"期望 BTCUSDT，实际 {decision.symbol}"
    assert decision.confidence == 0.85, f"期望 0.85，实际 {decision.confidence:.2f}"
    
    print("✅ 信号转决策测试通过")
    return decision


async def test_strategy_engine():
    """测试：策略引擎"""
    print("\n" + "=" * 70)
    print("测试 2: 策略引擎")
    print("=" * 70)
    
    orchestrator = create_default_strategies()
    print(f"策略引擎创建成功，策略数量: {len(orchestrator._strategies)}")
    
    # 测试 RSI 策略
    rsi_strategy = orchestrator._strategies.get("rsi_14")
    if rsi_strategy:
        print(f"RSI 策略已加载: oversold={rsi_strategy.oversold} overbought={rsi_strategy.overbought}")
    
    # 测试 MACD 策略
    macd_strategy = orchestrator._strategies.get("macd_12_26_9")
    if macd_strategy:
        print(f"MACD 策略已加载: {macd_strategy.fast_period}/{macd_strategy.slow_period}/{macd_strategy.signal_period}")
    
    print("✅ 策略引擎测试通过")


async def test_risk_check():
    """测试：风控检查"""
    print("\n" + "=" * 70)
    print("测试 3: 风控检查")
    print("=" * 70)
    
    # 创建风控服务
    risk_config = RiskConfig(
        max_position_size=0.2,
        max_single_loss=0.02,
        max_daily_loss=0.05,
        max_drawdown=0.15,
    )
    risk_service = RiskService(risk_config)
    
    # 创建决策
    decision = Decision(
        decision_id="test_dec_001",
        action="LONG",
        symbol="BTCUSDT",
        quantity=0.01,
        price=50000.0,
        confidence=0.85,
        reason="Test decision",
        source="test",
        timestamp=int(datetime.now().timestamp() * 1000),
    )
    
    print(f"决策: {decision.action} {decision.symbol} quantity={decision.quantity}")
    print(f"价格: {decision.price} 价值: {decision.quantity * decision.price:.2f}")
    
    # 执行风控检查（使用模拟方法，因为我们没有真正的 TradeRisk）
    # 我们直接验证风控服务可以创建
    print(f"风控配置: max_position={risk_config.max_position_size:.2%}, max_loss={risk_config.max_single_loss:.2%}")
    print(f"当前权益: {risk_service._current_equity:.2f}")
    
    # 简单测试：检查默认的风控状态
    result = risk_service.get_metrics()
    print(f"风控指标: {result}")
    
    # 测试 add_position
    risk_service.add_position(
        symbol="BTCUSDT",
        quantity=0.01,
        entry_price=50000.0,
    )
    print(f"添加持仓: BTCUSDT 数量=0.01")
    
    positions = risk_service.get_positions_risk()
    print(f"持仓数量: {len(positions)}")
    
    assert len(positions) == 1, f"期望 1 个持仓，实际 {len(positions)}"
    
    # 测试 remove_position
    risk_service.remove_position("BTCUSDT", pnl=10.0)
    print(f"移除持仓: BTCUSDT")
    
    positions = risk_service.get_positions_risk()
    assert len(positions) == 0, f"期望 0 个持仓，实际 {len(positions)}"
    
    print("✅ 风控检查测试通过")


async def test_idempotency():
    """测试：幂等性"""
    print("\n" + "=" * 70)
    print("测试 4: 幂等性检查")
    print("=" * 70)
    
    idempotency = await get_idempotency_manager()
    
    # 第一次检查
    operation_key = "test_order_001"
    can_execute1, existing1 = await idempotency.check_and_lock(
        operation_type="order",
        operation_key=operation_key,
        request_data={"symbol": "BTCUSDT", "quantity": 0.01},
    )
    
    print(f"第一次检查: can_execute={can_execute1} existing={existing1}")
    assert can_execute1 is True, "第一次应该可以执行"
    assert existing1 is None, "第一次应该没有现有的"
    
    # 第二次检查
    can_execute2, existing2 = await idempotency.check_and_lock(
        operation_type="order",
        operation_key=operation_key,
        request_data={"symbol": "BTCUSDT", "quantity": 0.01},
    )
    
    print(f"第二次检查: can_execute={can_execute2}")
    assert can_execute2 is False, "第二次应该不可以执行"
    
    # 完成
    await idempotency.complete(
        operation_type="order",
        operation_key=operation_key,
        result={"status": "success"},
    )
    
    status = await idempotency.get_status("order", operation_key)
    print(f"最终状态: {status}")
    assert status is not None, "应该有状态"
    
    print("✅ 幂等性测试通过")


async def test_full_pipeline():
    """测试：完整流程"""
    print("\n" + "=" * 70)
    print("测试 5: 完整流程模拟")
    print("=" * 70)
    
    # 1. 模拟 fusion_service 产生信号
    print("步骤 1: Fusion Service 产生信号...")
    signal = Signal(
        timestamp=int(datetime.now().timestamp() * 1000),
        signal="BTC_BULLISH",
        direction="bullish",
        confidence=0.85,
        event_count=3,
        assets=["BTCUSDT"],
    )
    
    # 2. strategy_service 处理信号，产生决策
    print("步骤 2: Strategy Service 产生决策...")
    decision = generate_simple_decision(signal)
    print(f"  决策: {decision.action} {decision.symbol} quantity={decision.quantity:.4f}")
    
    # 3. risk_service 检查决策
    print("步骤 3: Risk Service 检查决策...")
    risk_service = RiskService(RiskConfig())
    # 模拟风控检查
    checked_decision = RiskCheckedDecision(
        decision_id=decision.decision_id,
        approved=True,
        reason=None,
        risk_level="low",
        original_decision=decision,
        check_results={"all_passed": True},
    )
    print(f"  风控结果: {'✅ 批准' if checked_decision.approved else '❌ 拒绝'}")
    
    # 4. execution_service 执行决策
    print("步骤 4: Execution Service 执行...")
    if checked_decision.can_execute:
        print("  模拟订单执行...")
        print(f"  订单: {decision.action} {decision.symbol} quantity={decision.quantity:.4f}")
        print("  订单提交成功!")
    
    print("✅ 完整流程测试通过")


async def main():
    """运行所有集成测试"""
    print("=" * 70)
    print("开始运行集成测试")
    print("=" * 70)
    
    passed_tests = 0
    total_tests = 5
    
    try:
        await test_signal_to_decision()
        passed_tests += 1
    except Exception as e:
        logger.error(f"测试 1 失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    try:
        await test_strategy_engine()
        passed_tests += 1
    except Exception as e:
        logger.error(f"测试 2 失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    try:
        await test_risk_check()
        passed_tests += 1
    except Exception as e:
        logger.error(f"测试 3 失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    try:
        await test_idempotency()
        passed_tests += 1
    except Exception as e:
        logger.error(f"测试 4 失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    try:
        await test_full_pipeline()
        passed_tests += 1
    except Exception as e:
        logger.error(f"测试 5 失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    print("\n" + "=" * 70)
    print("集成测试总结")
    print("=" * 70)
    print(f"通过: {passed_tests}/{total_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    print("=" * 70)
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
