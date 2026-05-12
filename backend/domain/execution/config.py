"""
Execution Domain 配置

执行领域的配置定义
包括订单执行参数、滑点控制、手续费等
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class OrderTypeConfig(BaseModel):
    """订单类型配置"""
    use_market_order: bool = Field(default=True, description="是否使用市价单")
    use_limit_order: bool = Field(default=False, description="是否使用限价单")
    use_stop_order: bool = Field(default=False, description="是否使用止损单")

    limit_order_offset_pct: float = Field(default=0.001, description="限价单偏移百分比")
    stop_order_offset_pct: float = Field(default=0.005, description="止损单偏移百分比")


class SlippageConfig(BaseModel):
    """滑点配置"""
    max_slippage_pct: float = Field(default=0.002, ge=0.0, le=0.1, description="最大滑点百分比")
    target_slippage_pct: float = Field(default=0.001, ge=0.0, le=0.1, description="目标滑点百分比")
    aggressive_slippage_pct: float = Field(default=0.005, ge=0.0, le=0.1, description="激进滑点百分比")


class FeeConfig(BaseModel):
    """手续费配置"""
    maker_fee_pct: float = Field(default=0.001, description="Maker费率")
    taker_fee_pct: float = Field(default=0.001, description="Taker费率")
    estimated_fee_pct: float = Field(default=0.002, description="预估费率")


class ExecutionRuntimeConfig(BaseModel):
    """
    执行运行时配置
    支持热更新和版本化
    """
    order_type: OrderTypeConfig = Field(default_factory=OrderTypeConfig)
    slippage: SlippageConfig = Field(default_factory=SlippageConfig)
    fee: FeeConfig = Field(default_factory=FeeConfig)

    max_order_size: float = Field(default=10000.0, description="最大订单金额")
    min_order_size: float = Field(default=10.0, description="最小订单金额")

    max_retry_attempts: int = Field(default=3, description="最大重试次数")
    retry_interval_seconds: int = Field(default=5, description="重试间隔(秒)")

    order_timeout_seconds: int = Field(default=60, description="订单超时时间(秒)")

    enable_partial_fill: bool = Field(default=True, description="是否允许部分成交")
    partial_fill_threshold: float = Field(default=0.5, description="部分成交阈值")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def validate_for_trading(self) -> List[str]:
        """验证配置"""
        errors = []
        if self.min_order_size > self.max_order_size:
            errors.append("最小订单金额不应大于最大订单金额")
        if self.slippage.target_slippage_pct > self.slippage.max_slippage_pct:
            errors.append("目标滑点不应大于最大滑点")
        return errors


EXECUTION_DEFAULTS: Dict[str, Any] = {
    "execution.max_order_size": 10000.0,
    "execution.min_order_size": 10.0,
    "execution.max_retry_attempts": 3,
    "execution.retry_interval_seconds": 5,
    "execution.order_timeout_seconds": 60,
    "execution.enable_partial_fill": True,
    "execution.partial_fill_threshold": 0.5,
}


EXECUTION_SCHEMA: Dict[str, Dict[str, Any]] = {
    "execution.max_order_size": {
        "value_type": "float",
        "default": 10000.0,
        "description": "Maximum order size",
        "min_value": 0,
    },
    "execution.min_order_size": {
        "value_type": "float",
        "default": 10.0,
        "description": "Minimum order size",
        "min_value": 0,
    },
}
