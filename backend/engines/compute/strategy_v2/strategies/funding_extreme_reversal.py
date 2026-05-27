"""
Funding Extreme Reversal Strategy - 资金费率极端反转策略

基于资金费率极端值判断市场反转时机。

核心逻辑：
1. 资金费率极端正值 → 市场过热，可能下跌
2. 资金费率极端负值 → 市场恐慌，可能上涨
3. 结合趋势状态和资金流确认反转信号
"""

from engines.compute.context import (
    MarketContext,
    TrendState,
    FlowPressure,
    FundingBias,
)

from ..base import StrategyV2, Signal
from ..metadata import StrategyMeta
from ..registry import register_strategy


@register_strategy
class FundingExtremeReversalStrategy(StrategyV2):
    """
    资金费率极端反转策略
    
    策略逻辑：
    - 当资金费率达到极端水平时，市场情绪可能过度，预示反转
    - 结合大周期趋势过滤和小周期资金流确认
    """
    
    meta = StrategyMeta(
        name="Funding Extreme Reversal",
        primary_tf="1h",
        confirm_tfs=["15m", "4h"],
        execution_tf="5m",
        required_context=[
            "tf.1h.price",
            "tf.1h.trend",
            "tf.15m.flow",
            "tf.4h.trend",
            "derivatives.funding",
            "derivatives.oi",
        ],
        tags={"derivatives", "funding", "mean_reversion", "regime_aware", "multi_timeframe"},
    )
    
    def generate_signal(self, ctx: MarketContext) -> Signal:
        # 获取上下文
        h1 = ctx.tf["1h"]
        m15 = ctx.tf["15m"]
        h4 = ctx.tf["4h"]
        funding = ctx.derivatives.funding
        oi = ctx.derivatives.oi
        
        # 大周期趋势过滤（4h）
        if h4.trend.state == TrendState.STRONG_DOWN:
            # 4h 强下跌趋势中，只允许做空或小仓反弹
            if funding.bias == FundingBias.EXTREME_POSITIVE:
                # 极端正资金费率 + 下跌趋势 → 继续下跌
                return Signal.short(
                    confidence=0.65,
                    reason="extreme_funding_in_downtrend"
                )
            # 极端负资金费率可以考虑反弹，但仓位打折
            if funding.bias == FundingBias.EXTREME_NEGATIVE:
                final_conf = ctx.calculate_signal_confidence(0.50, "1h")
                return Signal.long(
                    confidence=final_conf,
                    reason="extreme_negative_funding_bounce_in_downtrend"
                )
        
        if h4.trend.state == TrendState.STRONG_UP:
            # 4h 强上涨趋势中，只允许做多
            if funding.bias == FundingBias.EXTREME_NEGATIVE:
                # 极端负资金费率 + 上涨趋势 → 继续上涨
                return Signal.long(
                    confidence=0.65,
                    reason="extreme_negative_funding_in_uptrend"
                )
            # 极端正资金费率可以考虑做空，但仓位打折
            if funding.bias == FundingBias.EXTREME_POSITIVE:
                final_conf = ctx.calculate_signal_confidence(0.50, "1h")
                return Signal.short(
                    confidence=final_conf,
                    reason="extreme_positive_funding_reversal_in_uptrend"
                )
        
        # 主信号逻辑：资金费率极端反转
        if funding.bias == FundingBias.EXTREME_POSITIVE:
            # 极端正资金费率 → 看空反转
            # 条件：高资金费率 + 资金流疲软
            if m15.flow.pressure in [FlowPressure.SELL, FlowPressure.NEUTRAL]:
                final_conf = ctx.calculate_signal_confidence(0.72, "1h")
                return Signal.short(
                    confidence=final_conf,
                    reason="extreme_positive_funding_reversal"
                )
        
        if funding.bias == FundingBias.EXTREME_NEGATIVE:
            # 极端负资金费率 → 看多反转
            # 条件：低资金费率 + 资金流强劲
            if m15.flow.pressure in [FlowPressure.BUY, FlowPressure.NEUTRAL]:
                final_conf = ctx.calculate_signal_confidence(0.75, "1h")
                return Signal.long(
                    confidence=final_conf,
                    reason="extreme_negative_funding_reversal"
                )
        
        # 资金费率背离信号
        # 资金费率上涨但价格不涨 → 潜在反转
        if funding.zscore > 1.0 and h1.price.change_percent < 0:
            if m15.flow.pressure == FlowPressure.SELL:
                final_conf = ctx.calculate_signal_confidence(0.55, "1h")
                return Signal.short(
                    confidence=final_conf,
                    reason="funding_price_divergence_short"
                )
        
        # 资金费率下跌但价格不跌 → 潜在反转
        if funding.zscore < -1.0 and h1.price.change_percent > 0:
            if m15.flow.pressure == FlowPressure.BUY:
                final_conf = ctx.calculate_signal_confidence(0.55, "1h")
                return Signal.long(
                    confidence=final_conf,
                    reason="funding_price_divergence_long"
                )
        
        return Signal.none()
