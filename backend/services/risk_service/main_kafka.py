"""
Risk Service - Kafka Consumer + Producer

消费决策，进行风控检查，输出风控后决策到 execution_service

用法:
    python -m services.risk_service.main_kafka
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("risk_service.kafka")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema.decision import Decision, RiskCheckedDecision
from services.risk_service.risk_engine import (
    RiskService,
    RiskCheckResult,
    RiskConfig,
    TradeRisk,
)
from shared.observability import get_observability_manager
from shared.service_registry import get_service_registry, ServiceEndpoint
from shared.idempotency import get_idempotency_manager


# 全局变量
broker = None
risk_service = None
observability = None
service_registry = None
idempotency = None


def perform_risk_check(decision: Decision) -> RiskCheckedDecision:
    """
    执行风控检查
    
    Args:
        decision: 原始决策
        
    Returns:
        风控检查后的决策
    """
    if not risk_service:
        return RiskCheckedDecision(
            decision_id=decision.decision_id,
            approved=True,
            reason="Risk service not initialized",
            risk_level="medium",
            original_decision=decision,
            check_results={"status": "bypassed"},
        )
    
    # 构建 TradeRisk
    estimated_value = decision.quantity * (decision.price or 1.0)
    trade_risk = TradeRisk(
        symbol=decision.symbol,
        side="buy" if decision.is_buy else "sell" if decision.is_sell else "hold",
        quantity=decision.quantity,
        price=decision.price or 0.0,
        estimated_value=estimated_value,
        estimated_loss=estimated_value * 0.02,  # 假设 2% 止损
        risk_level="low",
        stop_loss=decision.price * 0.98 if decision.price else 0,
        take_profit=decision.price * 1.02 if decision.price else 0,
    )
    
    # 执行风控检查
    result = risk_service.check_trade(trade_risk)
    
    # 转换结果
    approved = result.check_result == RiskCheckResult.PASSED
    
    return RiskCheckedDecision(
        decision_id=decision.decision_id,
        approved=approved,
        reason=result.rejected_reason,
        risk_level=result.risk_level,
        original_decision=decision,
        check_results={
            "check_result": result.check_result.value,
            "risk_level": result.risk_level,
            "warnings": result.warnings,
            "metrics": result.metrics,
        },
        metadata={
            "position_risks": [
                {
                    "symbol": pr.symbol,
                    "unrealized_pnl": pr.unrealized_pnl,
                }
                for pr in result.position_risks
            ],
        },
    )


async def handle_decision(msg: dict):
    """
    处理策略决策，执行风控检查
    """
    try:
        # 解析决策
        decision = Decision(**msg) if isinstance(msg, dict) else msg
        
        logger.info(f"Received decision: {decision.action} on {decision.symbol} confidence={decision.confidence:.3f}")
        
        # 记录指标
        if observability:
            observability.record_request(
                "decision_received",
                "GET",
                200,
                0.001,
            )
        
        # 幂等性检查
        if idempotency:
            can_execute, existing = await idempotency.check_and_lock(
                operation_type="risk_check",
                operation_key=decision.decision_id,
                request_data=decision.model_dump(),
            )
            if not can_execute:
                logger.info(f"Decision already checked: {decision.decision_id}")
                return
        
        # 执行风控检查
        checked_decision = perform_risk_check(decision)
        
        # 打印风控结果
        print("\n" + "=" * 70)
        print("⚠️ RISK CHECK RESULT")
        print("=" * 70)
        print(f"  Decision:   {decision.action} {decision.symbol}")
        print(f"  Approved:   {'✅ YES' if checked_decision.approved else '❌ NO'}")
        print(f"  Risk:       {checked_decision.risk_level.upper()}")
        print(f"  Reason:     {checked_decision.reason or 'Passed'}")
        if checked_decision.check_results:
            print(f"  Details:    {checked_decision.check_results}")
        print("=" * 70 + "\n")
        
        # 发布风控后决策到 Kafka
        if broker:
            await broker.publish(
                message=checked_decision.model_dump(),
                topic=Topics.decisions_risk_checked(),
                key=decision.symbol,
            )
            logger.info(f"Published checked decision: {checked_decision.approved}")
            
            # 如果通过，同时发布到 approved topic
            if checked_decision.can_execute:
                await broker.publish(
                    message=checked_decision.model_dump(),
                    topic=Topics.decisions_approved(),
                    key=decision.symbol,
                )
                logger.info(f"Published approved decision")
        
        # 记录指标
        if observability:
            observability.record_business_event(
                "risk_checked",
                {
                    "symbol": decision.symbol,
                    "approved": checked_decision.approved,
                    "risk_level": checked_decision.risk_level,
                },
            )
        
        # 更新幂等性状态
        if idempotency:
            await idempotency.complete(
                operation_type="risk_check",
                operation_key=decision.decision_id,
                result={"approved": checked_decision.approved},
            )
        
    except Exception as e:
        logger.error(f"Error handling decision: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def main():
    """主函数"""
    global broker, risk_service, observability, service_registry, idempotency
    
    print("=" * 70)
    print("Risk Service - Kafka Consumer + Producer")
    print("=" * 70)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.decisions()}")
    print(f"Publish: {Topics.decisions_risk_checked()}, {Topics.decisions_approved()}")
    print("=" * 70)
    
    # 初始化 observability
    observability = get_observability_manager("risk_service")
    
    # 初始化 service registry
    service_registry = get_service_registry()
    await service_registry.register(
        service_name="risk_service",
        version="2.0.0",
        endpoints=[ServiceEndpoint(host="localhost", port=8004)],
        capabilities=["risk_checking", "position_limits", "loss_limits"],
    )
    
    # 初始化 idempotency
    idempotency = await get_idempotency_manager()
    
    # 创建风控服务
    risk_config = RiskConfig(
        max_position_size=0.2,
        max_single_loss=0.02,
        max_daily_loss=0.05,
        max_drawdown=0.15,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
    )
    risk_service = RiskService(risk_config)
    print("\n✅ Risk service initialized with default config")
    
    # 初始化 broker
    broker = get_broker(bootstrap_servers)
    
    print("\n[risk_service] Waiting for decisions...\n")
    
    # 订阅决策
    @broker.subscriber(Topics.decisions())
    async def on_decision(msg: dict):
        await handle_decision(msg)
    
    # 运行
    await broker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Risk service stopped by user")
