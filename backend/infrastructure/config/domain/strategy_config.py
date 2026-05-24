"""
Strategy Domain 配置

策略领域的配置定义
包括因子权重、策略参数、阈值等
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator


class FactorWeights(BaseModel):
    """因子权重配置"""
    momentum: float = Field(default=0.3, ge=0.0, le=1.0)
    trend: float = Field(default=0.3, ge=0.0, le=1.0)
    flow: float = Field(default=0.2, ge=0.0, le=1.0)
    sentiment: float = Field(default=0.2, ge=0.0, le=1.0)

    @field_validator("momentum", "trend", "flow", "sentiment")
    @classmethod
    def validate_weights(cls, v):
        if v < 0:
            raise ValueError("权重不能为负数")
        return v

    def total(self) -> float:
        return self.momentum + self.trend + self.flow + self.sentiment

    def validate_sum(self) -> bool:
        return abs(self.total() - 1.0) < 0.001


class StrategyRuntimeConfig(BaseModel):
    """
    策略运行时配置
    支持热更新和版本化
    """
    momentum_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="动量因子权重")
    trend_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="趋势因子权重")
    flow_weight: float = Field(default=0.2, ge=0.0, le=1.0, description="资金流因子权重")
    sentiment_weight: float = Field(default=0.2, ge=0.0, le=1.0, description="情绪因子权重")

    min_signal_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="最小信号阈值")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="置信度阈值")

    rebalance_interval_hours: int = Field(default=24, ge=1, description="调仓间隔(小时)")
    min_holding_period_minutes: int = Field(default=30, ge=1, description="最小持仓时间(分钟)")

    symbols: List[str] = Field(default=["BTCUSDT", "ETHUSDT"], description="交易标的")
    exchanges: List[str] = Field(default=["binance"], description="交易所")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def validate_for_trading(self) -> List[str]:
        """验证配置"""
        errors = []
        total_weight = self.momentum_weight + self.trend_weight + self.flow_weight + self.sentiment_weight
        if abs(total_weight - 1.0) > 0.001:
            errors.append(f"因子权重之和必须为1.0，当前为{total_weight}")
        if self.min_signal_threshold > self.confidence_threshold:
            errors.append("信号阈值不应大于置信度阈值")
        return errors


STRATEGY_DEFAULTS: Dict[str, Any] = {
    "strategy.momentum_weight": 0.3,
    "strategy.trend_weight": 0.3,
    "strategy.flow_weight": 0.2,
    "strategy.sentiment_weight": 0.2,
    "strategy.min_signal_threshold": 0.6,
    "strategy.confidence_threshold": 0.7,
    "strategy.rebalance_interval_hours": 24,
    "strategy.min_holding_period_minutes": 30,
}


STRATEGY_SCHEMA: Dict[str, Dict[str, Any]] = {
    "strategy.momentum_weight": {
        "value_type": "float",
        "default": 0.3,
        "description": "Momentum factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "strategy.trend_weight": {
        "value_type": "float",
        "default": 0.3,
        "description": "Trend factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "strategy.flow_weight": {
        "value_type": "float",
        "default": 0.2,
        "description": "Flow factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "strategy.sentiment_weight": {
        "value_type": "float",
        "default": 0.2,
        "description": "Sentiment factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
}
