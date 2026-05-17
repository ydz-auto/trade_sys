"""
Execution Service - 订单执行业务服务

职责：
- 风控检查逻辑
- 订单生成逻辑
- 执行策略逻辑

注意：这是纯业务逻辑，不包含交易所 API 调用等基础设施代码。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    approved: bool
    reason: str
    risk_level: str
    checks: Dict[str, bool]


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: str
    timestamp: datetime


class RiskChecker:
    """风控检查器 - 纯业务逻辑"""
    
    def __init__(
        self,
        max_position_size: float = 0.1,
        max_leverage: int = 5,
        daily_loss_limit: float = 0.05,
    ):
        self.max_position_size = max_position_size
        self.max_leverage = max_leverage
        self.daily_loss_limit = daily_loss_limit
    
    def check_position_size(self, quantity: float) -> bool:
        """检查仓位大小"""
        return quantity <= self.max_position_size
    
    def check_leverage(self, leverage: int) -> bool:
        """检查杠杆"""
        return leverage <= self.max_leverage
    
    def check_daily_loss(self, current_loss: float) -> bool:
        """检查日亏损"""
        return abs(current_loss) <= self.daily_loss_limit
    
    def check(self, decision: Dict[str, Any], context: Dict[str, Any] = None) -> RiskCheckResult:
        """执行风控检查"""
        context = context or {}
        
        checks = {}
        reasons = []
        
        quantity = decision.get("quantity", 0)
        if quantity > 0:
            checks["position_size"] = self.check_position_size(quantity)
            if not checks["position_size"]:
                reasons.append(f"仓位超限: {quantity} > {self.max_position_size}")
        
        leverage = context.get("leverage", 1)
        checks["leverage"] = self.check_leverage(leverage)
        if not checks["leverage"]:
            reasons.append(f"杠杆超限: {leverage} > {self.max_leverage}")
        
        daily_loss = context.get("daily_loss", 0)
        checks["daily_loss"] = self.check_daily_loss(daily_loss)
        if not checks["daily_loss"]:
            reasons.append(f"日亏损超限: {daily_loss} > {self.daily_loss_limit}")
        
        approved = all(checks.values())
        
        if approved:
            risk_level = "low"
            reason = "风控检查通过"
        elif len(reasons) == 1:
            risk_level = "medium"
            reason = reasons[0]
        else:
            risk_level = "high"
            reason = "; ".join(reasons)
        
        return RiskCheckResult(
            approved=approved,
            reason=reason,
            risk_level=risk_level,
            checks=checks,
        )


class OrderGenerator:
    """订单生成器 - 纯业务逻辑"""
    
    def generate(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
    ) -> Order:
        """生成订单"""
        side = OrderSide.BUY if action.upper() in ("LONG", "BUY") else OrderSide.SELL
        
        return Order(
            order_id=f"ord_{symbol}_{datetime.now().timestamp()}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="pending",
            timestamp=datetime.now(),
        )


class ExecutionService:
    """
    Execution Service - 订单执行业务服务
    
    编排风控检查和订单生成的完整流程。
    这是纯业务逻辑层，不包含任何基础设施代码。
    """
    
    def __init__(
        self,
        max_position_size: float = 0.1,
        max_leverage: int = 5,
        daily_loss_limit: float = 0.05,
    ):
        self.risk_checker = RiskChecker(
            max_position_size=max_position_size,
            max_leverage=max_leverage,
            daily_loss_limit=daily_loss_limit,
        )
        self.order_generator = OrderGenerator()
    
    def check_risk(
        self,
        decision: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> RiskCheckResult:
        """执行风控检查（纯业务逻辑）"""
        return self.risk_checker.check(decision, context)
    
    def generate_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
    ) -> Order:
        """生成订单（纯业务逻辑）"""
        ot = OrderType.MARKET if order_type == "market" else OrderType.LIMIT
        return self.order_generator.generate(symbol, action, quantity, ot, price)
    
    def execute_decision(
        self,
        decision: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Optional[Order]:
        """
        执行决策的完整流程（纯业务逻辑）
        
        这是业务用例的入口点，编排整个业务流程。
        """
        if decision.get("action") == "HOLD":
            return None
        
        risk_result = self.check_risk(decision, context)
        if not risk_result.approved:
            return None
        
        order = self.generate_order(
            symbol=decision["symbol"],
            action=decision["action"],
            quantity=decision["quantity"],
        )
        
        return order
