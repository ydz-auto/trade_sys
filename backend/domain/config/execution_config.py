"""
执行配置类型
Execution Configuration Types

定义订单执行和交易执行的配置，确保执行的一致性。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTX = "gtx"


class SlippageModel(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    VOLUME_BASED = "volume_based"
    REALISTIC = "realistic"


@dataclass
class SlippageConfig:
    """滑点配置"""
    model: SlippageModel = SlippageModel.FIXED
    fixed_bps: float = 5.0
    max_bps: float = 50.0
    volume_sensitivity: float = 0.5


@dataclass
class FeeConfig:
    """手续费配置"""
    maker_bps: float = 1.0
    taker_bps: float = 2.0
    min_fee: float = 0.0
    max_fee: Optional[float] = None
    use_volume_tier: bool = True


@dataclass
class ExecutionProtectionConfig:
    """执行保护配置"""
    max_order_size_pct: float = 0.1
    max_positions: int = 10
    max_daily_trades: int = 100
    min_order_interval_ms: int = 100
    enable_circuit_breaker: bool = True
    circuit_breaker_drawdown_pct: float = 0.1


@dataclass(frozen=True)
class ExecutionConfig:
    """
    执行配置
    
    核心特性：
    - 订单类型配置
    - 滑点模型配置
    - 手续费配置
    - 执行保护配置
    """
    execution_id: str
    execution_name: str
    
    version: str = "1.0.0"
    
    # 订单配置
    default_order_type: OrderType = OrderType.LIMIT
    default_time_in_force: TimeInForce = TimeInForce.GTC
    default_position_size_pct: float = 0.05
    
    # 滑点和手续费
    slippage_config: SlippageConfig = field(default_factory=SlippageConfig)
    fee_config: FeeConfig = field(default_factory=FeeConfig)
    
    # 执行保护
    protection_config: ExecutionProtectionConfig = field(default_factory=ExecutionProtectionConfig)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    
    # 扩展配置
    extra_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "execution_name": self.execution_name,
            "version": self.version,
            "default_order_type": self.default_order_type.value,
            "default_time_in_force": self.default_time_in_force.value,
            "default_position_size_pct": self.default_position_size_pct,
            "slippage_config": {
                "model": self.slippage_config.model.value,
                "fixed_bps": self.slippage_config.fixed_bps,
                "max_bps": self.slippage_config.max_bps,
                "volume_sensitivity": self.slippage_config.volume_sensitivity,
            },
            "fee_config": {
                "maker_bps": self.fee_config.maker_bps,
                "taker_bps": self.fee_config.taker_bps,
                "min_fee": self.fee_config.min_fee,
                "max_fee": self.fee_config.max_fee,
                "use_volume_tier": self.fee_config.use_volume_tier,
            },
            "protection_config": {
                "max_order_size_pct": self.protection_config.max_order_size_pct,
                "max_positions": self.protection_config.max_positions,
                "max_daily_trades": self.protection_config.max_daily_trades,
                "min_order_interval_ms": self.protection_config.min_order_interval_ms,
                "enable_circuit_breaker": self.protection_config.enable_circuit_breaker,
                "circuit_breaker_drawdown_pct": self.protection_config.circuit_breaker_drawdown_pct,
            },
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "extra_config": self.extra_config,
        }


@dataclass(frozen=True)
class OrderExecutionConfig:
    """单个订单的执行配置"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    
    client_order_id: Optional[str] = None
    reduce_only: bool = False
    close_on_trigger: bool = False
    
    # 执行策略
    iceberg_enabled: bool = False
    iceberg_visible_qty: Optional[float] = None
    twap_enabled: bool = False
    twap_duration_seconds: int = 60
    
    # 验证标志
    validate_risk: bool = True
    validate_liquidity: bool = True
