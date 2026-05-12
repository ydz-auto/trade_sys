"""
Risk Domain 配置

风控领域的配置定义
包括风控参数、阈值、限制等
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class RiskRuntimeConfig(BaseModel):
    """
    风控运行时配置
    支持热更新和版本化
    """
    max_risk_index: int = Field(default=80, ge=0, le=100, description="最大风险指数")
    max_drawdown_pct: float = Field(default=0.08, ge=0.0, le=1.0, description="最大回撤比例")
    max_consecutive_losses: int = Field(default=3, ge=1, le=10, description="最大连续亏损次数")
    auto_pause_on_high_risk: bool = Field(default=True, description="高风险自动暂停")

    position_size_limit: float = Field(default=10000.0, description="单笔仓位限制")
    daily_loss_limit: float = Field(default=50000.0, description="日亏损限制")
    single_trade_max_loss: float = Field(default=1000.0, description="单笔最大亏损")

    leverage_limit: int = Field(default=3, ge=1, le=10, description="最大杠杆")
    margin_call_threshold: float = Field(default=0.3, description="强平阈值")

    min_trade_interval_seconds: int = Field(default=60, description="最小交易间隔(秒)")
    max_trades_per_day: int = Field(default=50, description="日最大交易次数")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def validate_for_trading(self) -> List[str]:
        """验证配置是否允许交易"""
        errors = []
        if self.max_risk_index >= 90:
            errors.append("风险指数过高")
        if self.max_drawdown_pct < 0.02:
            errors.append("回撤限制过于严格")
        return errors


RISK_DEFAULTS: Dict[str, Any] = {
    "risk.max_risk_index": 80,
    "risk.max_drawdown_pct": 0.08,
    "risk.max_consecutive_losses": 3,
    "risk.auto_pause_on_high_risk": True,
    "risk.position_size_limit": 10000.0,
    "risk.daily_loss_limit": 50000.0,
    "risk.single_trade_max_loss": 1000.0,
    "risk.leverage_limit": 3,
    "risk.margin_call_threshold": 0.3,
    "risk.min_trade_interval_seconds": 60,
    "risk.max_trades_per_day": 50,
}


RISK_SCHEMA: Dict[str, Dict[str, Any]] = {
    "risk.max_risk_index": {
        "value_type": "int",
        "default": 80,
        "description": "Maximum risk index before pausing trading",
        "min_value": 0,
        "max_value": 100,
        "required": True,
    },
    "risk.max_drawdown_pct": {
        "value_type": "float",
        "default": 0.08,
        "description": "Maximum drawdown percentage",
        "min_value": 0.0,
        "max_value": 1.0,
        "required": True,
    },
    "risk.max_consecutive_losses": {
        "value_type": "int",
        "default": 3,
        "description": "Maximum consecutive losses before pause",
        "min_value": 1,
        "max_value": 10,
    },
    "risk.auto_pause_on_high_risk": {
        "value_type": "bool",
        "default": True,
        "description": "Auto pause trading on high risk",
    },
}
