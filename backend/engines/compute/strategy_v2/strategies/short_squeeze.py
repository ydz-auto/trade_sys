"""
Short Squeeze Strategy - 空头挤压策略

基于资金费率和持仓量数据判断空头挤压机会。

核心逻辑：
1. 高持仓量 + 负资金费率 → 潜在空头挤压
2. 价格上涨 + 资金流买入压力 → 确认挤压开始
3. 强平数据验证挤压强度
"""

from engines.compute.context import (
    MarketContext,
    TrendState,
    FlowPressure,
    LiquidityState,
    FundingBias,
)

from ..base import StrategyV2, Signal
from ..metadata import StrategyMeta
from ..registry import register_strategy


@register_strategy
class ShortSqueezeStrategy(StrategyV2):
    """
    空头挤压策略
    
    策略逻辑：
    - 当市场存在大量空头头寸（高持仓量 + 负资金费率）时，价格快速上涨可能引发空头挤压
    - 结合多周期资金流确认挤压信号
    """
    
    meta = StrategyMeta(
        name="Short Squeeze",
        primary_tf="15m",
        confirm_tfs=["5m", "1h"],
        execution_tf="1m",
        required_context=[
            "tf.15m.price",
            "tf.15m.flow",
            "tf.1h.trend",
            "tf.5m.flow",
            "tf.1m.liquidity",
            "derivatives.oi",
            "derivatives.funding",
            "derivatives.liquidation",
        ],
        tags={"derivatives", "short_squeeze", "momentum", "real_time", "multi_timeframe"},
    )
    
    def generate_signal(self, ctx: MarketContext) -> Signal:
        # 获取上下文
        m15 = ctx.tf["15m"]
        h1 = ctx.tf["1h"]
        m5 = ctx.tf["5m"]
        m1 = ctx.tf["1m"]
        oi = ctx.derivatives.oi
        funding = ctx.derivatives.funding
        liquidation = ctx.derivatives.liquidation
        
        # 大周期趋势过滤（1h）
        if h1.trend.state == TrendState.STRONG_DOWN:
            # 强下跌趋势中，不允许做空挤压策略
            return Signal.none(reason="strong_downtrend_filter")
        
        # 执行层检查（1m 流动性）
        if m1.liquidity.state == LiquidityState.VACUUM:
            return Signal.none(reason="liquidity_vacuum")
        
        # 空头挤压条件：高持仓量 + 负资金费率
        has_short_squeeze_setup = (
            oi.zscore > 1.5 and 
            funding.bias in [FundingBias.NEGATIVE, FundingBias.EXTREME_NEGATIVE]
        )
        
        if not has_short_squeeze_setup:
            return Signal.none(reason="no_squeeze_setup")
        
        # 确认信号：价格上涨 + 资金流买入压力
        if m15.price.change_percent > 0.5:
            # 15m 买入压力确认
            if m15.flow.pressure == FlowPressure.BUY:
                # 5m 二次确认
                if m5.flow.pressure == FlowPressure.BUY:
                    final_conf = ctx.calculate_signal_confidence(0.75, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="short_squeeze_confirmed"
                    )
                
                # 5m 中性也可以接受
                if m5.flow.pressure == FlowPressure.NEUTRAL:
                    final_conf = ctx.calculate_signal_confidence(0.65, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="short_squeeze_with_neutral_confirmation"
                    )
        
        # 强平辅助确认：空头强平增加 → 挤压正在发生
        if liquidation.short_zscore > 1.5:
            if m15.flow.pressure == FlowPressure.BUY:
                final_conf = ctx.calculate_signal_confidence(0.72, "15m")
                return Signal.long(
                    confidence=final_conf,
                    reason="short_squeeze_with_liquidation"
                )
        
        # 挤压延续：持续买入压力 + 价格上涨
        if has_short_squeeze_setup:
            if m15.flow.pressure == FlowPressure.BUY and m5.flow.pressure == FlowPressure.BUY:
                if m15.price.close > m15.price.open:
                    final_conf = ctx.calculate_signal_confidence(0.60, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="short_squeeze_continuation"
                    )
        
        return Signal.none()
