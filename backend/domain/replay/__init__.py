"""
Replay Realism - 回测真实性

确保回测结果可信:
1. Slippage Model - 滑点模型
2. Latency Model - 延迟模型
3. Partial Fill - 部分成交
4. Fee Model - 手续费模型
5. Funding Model - 资金费率
6. Liquidation Model - 爆仓模拟
"""
from .slippage import SlippageModel, calculate_slippage
from .latency import LatencyModel, simulate_latency
from .partial_fill import PartialFillModel, simulate_partial_fill
from .fee_model import FeeModel, calculate_fees
from .funding import FundingModel, calculate_funding
from .liquidation import LiquidationModel, check_liquidation
from .realism_engine import ReplayRealismEngine

__all__ = [
    "SlippageModel",
    "calculate_slippage",
    "LatencyModel",
    "simulate_latency",
    "PartialFillModel",
    "simulate_partial_fill",
    "FeeModel",
    "calculate_fees",
    "FundingModel",
    "calculate_funding",
    "LiquidationModel",
    "check_liquidation",
    "ReplayRealismEngine",
]
