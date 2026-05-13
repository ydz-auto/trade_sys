"""
决策 Schema - Strategy Service 生成的决策
"""

from typing import List, Optional, Any

from pydantic import Field

from infrastructure.messaging.schema.base import BaseMessage


class Decision(BaseMessage):
    """
    策略决策
    
    Strategy Service 产生的最终决策
    """
    
    decision_id: str = Field(description="决策 ID")
    action: str = Field(description="动作类型: LONG/SHORT/HOLD/CLOSE")
    symbol: str = Field(description="交易品种")
    quantity: float = Field(ge=0.0, description="数量")
    price: Optional[float] = Field(default=None, description="价格（None 表示市价单）")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reason: str = Field(default="", description="决策原因")
    source: str = Field(default="strategy_service", description="决策来源")
    metadata: dict = Field(default_factory=dict, description="附加元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec_1234567890",
                "action": "LONG",
                "symbol": "BTCUSDT",
                "quantity": 0.01,
                "price": None,
                "confidence": 0.85,
                "reason": "RSI超卖，MACD金叉",
                "source": "strategy_service",
                "metadata": {
                    "rsi": 28.5,
                    "macd_histogram": 0.0012,
                    "strategies": ["rsi_14", "macd_12_26_9"],
                },
            }
        }
    
    @property
    def is_buy(self) -> bool:
        return self.action.upper() == "LONG" or self.action.upper() == "BUY"
    
    @property
    def is_sell(self) -> bool:
        return self.action.upper() == "SHORT" or self.action.upper() == "SELL"
    
    @property
    def is_hold(self) -> bool:
        return self.action.upper() == "HOLD"
    
    @property
    def is_actionable(self) -> bool:
        return not self.is_hold and self.confidence >= 0.5


class RiskCheckedDecision(BaseMessage):
    """
    风控检查后的决策
    
    Risk Service 产生的决策，包含风控检查结果
    """
    
    decision_id: str = Field(description="原始决策 ID")
    approved: bool = Field(description="是否通过风控")
    reason: Optional[str] = Field(default=None, description="原因（如拒绝原因）")
    risk_level: str = Field(default="low", description="风险等级: low/medium/high/extreme")
    original_decision: Decision = Field(description="原始决策")
    check_results: dict = Field(default_factory=dict, description="具体的风控检查结果")
    metadata: dict = Field(default_factory=dict, description="附加元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec_1234567890",
                "approved": True,
                "reason": None,
                "risk_level": "low",
                "check_results": {
                    "position_limit": "passed",
                    "daily_loss_limit": "passed",
                },
            }
        }
    
    @property
    def can_execute(self) -> bool:
        return self.approved
