"""
完整交易流程模拟脚本

模拟从信号产生到订单执行的完整流程
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("simulate_pipeline")

from infrastructure.messaging.schema.signal import Signal
from infrastructure.messaging.schema.decision import Decision, RiskCheckedDecision
from services.strategy_service.strategies import create_default_strategies
from services.strategy_service.main_kafka import generate_simple_decision
from services.risk_service.risk_engine import RiskService, RiskConfig, RiskCheckResult


class SimulatedExecutionEngine:
    """模拟执行引擎"""
    
    def __init__(self):
        self.orders = []
        self.current_price = 50000.0  # BTCUSDT
        logger.info("模拟执行引擎已创建")
    
    def update_price(self, new_price: float):
        """更新价格"""
        self.current_price = new_price
        logger.info(f"价格更新: {new_price:.2f}")
    
    def execute_order(self, decision: Decision) -> dict:
        """模拟订单执行"""
        print(f"\n执行订单: {decision.action} {decision.symbol}")
        print(f"  数量: {decision.quantity:.4f}")
        print(f"  价格: {decision.price or '市价'}")
        
        # 模拟执行
        price = decision.price or self.current_price
        value = decision.quantity * price
        
        order = {
            "order_id": f"sim_order_{len(self.orders) + 1}",
            "symbol": decision.symbol,
            "action": decision.action,
            "quantity": decision.quantity,
            "price": price,
            "value": value,
            "status": "filled",
            "timestamp": datetime.now().isoformat(),
        }
        
        self.orders.append(order)
        
        print(f"  ✅ 订单执行成功!")
        print(f"  订单 ID: {order['order_id']}")
        print(f"  成交价值: ${value:.2f}")
        
        return order


class PipelineSimulator:
    """流程模拟器"""
    
    def __init__(self):
        # 初始化组件
        self.orchestrator = create_default_strategies()
        self.risk_service = RiskService(RiskConfig())
        self.execution_engine = SimulatedExecutionEngine()
        
        # 历史数据
        self.signals = []
        self.decisions = []
        self.checked_decisions = []
    
    def generate_signal(self, bullish=True) -> Signal:
        """生成模拟信号"""
        confidence = 0.5 + random.random() * 0.5  # 0.5 - 1.0
        
        signal = Signal(
            timestamp=int(datetime.now().timestamp() * 1000),
            signal="BTC_BULLISH" if bullish else "BTC_BEARISH",
            direction="bullish" if bullish else "bearish",
            confidence=confidence,
            consensus=0.7 + random.random() * 0.3,
            event_types=["news", "social", "market"],
            assets=["BTCUSDT"],
            strength=0.6 + random.random() * 0.4,
            event_count=2 + random.randint(0, 2),
        )
        
        self.signals.append(signal)
        return signal
    
    def run_strategy(self, signal: Signal) -> Decision:
        """运行策略决策"""
        print(f"\n[2] 策略决策...")
        
        # 使用简单决策（因为我们没有历史价格数据）
        decision = generate_simple_decision(signal)
        
        self.decisions.append(decision)
        
        print(f"  ✅ 决策: {decision.action} {decision.symbol}")
        print(f"  数量: {decision.quantity:.4f}")
        print(f"  置信度: {decision.confidence:.2f}")
        print(f"  原因: {decision.reason}")
        
        return decision
    
    def check_risk(self, decision: Decision) -> RiskCheckedDecision:
        """执行风控检查"""
        print(f"\n[3] 风控检查...")
        
        # 简单检查
        approved = True
        reason = None
        risk_level = "low"
        
        if decision.quantity > 0.5:  # 提高阈值
            risk_level = "high"
            approved = False
            reason = "单笔订单数量过大"
        elif decision.confidence < 0.5:  # 降低阈值
            risk_level = "medium"
            approved = False
            reason = "置信度不足"
        
        # 模拟持仓检查
        total_exposure = sum(
            o["value"]
            for o in self.execution_engine.orders
            if o["status"] == "filled"
        )
        
        print(f"  当前持仓价值: ${total_exposure:.2f}")
        
        if total_exposure > 50000:
            risk_level = "high"
            approved = False
            reason = "持仓价值过高"
        
        checked_decision = RiskCheckedDecision(
            decision_id=decision.decision_id,
            approved=approved,
            reason=reason,
            risk_level=risk_level,
            original_decision=decision,
            check_results={
                "position_size": "ok" if decision.quantity <= 0.1 else "exceeded",
                "confidence": "ok" if decision.confidence >= 0.6 else "low",
                "exposure": "ok" if total_exposure <= 50000 else "exceeded",
            },
        )
        
        self.checked_decisions.append(checked_decision)
        
        status = "✅ 批准" if approved else "❌ 拒绝"
        print(f"  风控结果: {status} ({risk_level.upper()})")
        if reason:
            print(f"  原因: {reason}")
        
        return checked_decision
    
    def execute_decision(self, checked_decision: RiskCheckedDecision) -> dict:
        """执行决策"""
        print(f"\n[4] 订单执行...")
        
        if not checked_decision.can_execute:
            print("  ❌ 决策未通过风控，跳过执行")
            return {"status": "skipped"}
        
        order = self.execution_engine.execute_order(checked_decision.original_decision)
        return order
    
    def run_complete_pipeline(self, num_steps=3):
        """运行完整流程"""
        print("=" * 70)
        print("完整交易流程模拟")
        print("=" * 70)
        
        # 设置初始价格
        self.execution_engine.update_price(50000.0)
        
        for i in range(num_steps):
            step_num = i + 1
            print(f"\n\n{'=' * 70}")
            print(f"第 {step_num} 轮")
            print('=' * 70)
            
            # 1. 产生信号
            print(f"\n[1] 产生信号...")
            bullish = random.random() > 0.3  # 70% 看涨
            signal = self.generate_signal(bullish)
            
            print(f"  ✅ 信号: {signal.signal}")
            print(f"  方向: {signal.direction}")
            print(f"  置信度: {signal.confidence:.2f}")
            print(f"  事件数量: {signal.event_count}")
            
            # 2. 策略决策
            decision = self.run_strategy(signal)
            
            # 3. 风控检查
            checked_decision = self.check_risk(decision)
            
            # 4. 执行
            order = self.execute_decision(checked_decision)
            
            # 更新价格（模拟波动）
            price_change = (random.random() - 0.5) * 200
            self.execution_engine.update_price(
                self.execution_engine.current_price + price_change
            )
        
        # 总结
        self.print_summary()
    
    def print_summary(self):
        """打印总结"""
        print(f"\n\n{'=' * 70}")
        print("模拟总结")
        print('=' * 70)
        
        # 信号统计
        bullish_count = sum(1 for s in self.signals if s.direction == "bullish")
        bearish_count = len(self.signals) - bullish_count
        
        # 决策统计
        long_count = sum(1 for d in self.decisions if d.action == "LONG")
        short_count = sum(1 for d in self.decisions if d.action == "SHORT")
        hold_count = len(self.decisions) - long_count - short_count
        
        # 风控统计
        approved_count = sum(1 for c in self.checked_decisions if c.approved)
        rejected_count = len(self.checked_decisions) - approved_count
        
        # 订单统计
        filled_count = len(self.execution_engine.orders)
        total_value = sum(o["value"] for o in self.execution_engine.orders)
        
        print(f"\n信号统计:")
        print(f"  总信号: {len(self.signals)}")
        print(f"  看涨: {bullish_count}")
        print(f"  看跌: {bearish_count}")
        
        print(f"\n决策统计:")
        print(f"  LONG: {long_count}")
        print(f"  SHORT: {short_count}")
        print(f"  HOLD: {hold_count}")
        
        print(f"\n风控统计:")
        print(f"  批准: {approved_count}")
        print(f"  拒绝: {rejected_count}")
        print(f"  通过率: {approved_count/len(self.checked_decisions)*100:.1f}%")
        
        print(f"\n订单统计:")
        print(f"  成交: {filled_count}")
        print(f"  总成交额: ${total_value:.2f}")
        
        if self.execution_engine.orders:
            last_price = self.execution_engine.current_price
            print(f"\n最终价格: ${last_price:.2f}")
        
        print("\n" + "=" * 70)
        print("模拟完成!")
        print("=" * 70)


async def main():
    """主函数"""
    simulator = PipelineSimulator()
    
    # 运行 3 轮模拟
    simulator.run_complete_pipeline(num_steps=3)


if __name__ == "__main__":
    asyncio.run(main())
