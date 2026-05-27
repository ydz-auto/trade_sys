"""
Open Interest Behavior Strategy - 持仓量行为策略

基于持仓量变化判断市场情绪和潜在价格走势。

核心逻辑：
1. 高持仓量 + 资金费率极端 → 反转信号
2. 持仓量急剧增加 + 价格下跌 → 空头挤压
3. 持仓量下降 + 价格上涨 → 趋势延续
"""

from engines.compute.context import (
    MarketContext,
    TrendState,
    FlowPressure,
)

from ..base import StrategyV2, Signal
from ..metadata import StrategyMeta
from ..registry import register_strategy


@register_strategy
class OpenInterestBehaviorStrategy(StrategyV2):
    """
    持仓量行为策略
    
    策略逻辑：
    - 当持仓量处于高位且资金费率极端时，可能出现反转
    - 结合趋势状态和资金流压力确认信号
    """
    
    meta = StrategyMeta(
        name="Open Interest Behavior",
        primary_tf="15m",
        confirm_tfs=["5m", "1h"],
        execution_tf="1m",
        required_context=[
            "tf.15m.price",
            "tf.15m.trend",
            "tf.15m.flow",
            "tf.1h.trend",
            "derivatives.oi",
            "derivatives.funding",
        ],
        tags={"derivatives", "oi_behavior", "regime_aware", "multi_timeframe"},
    )
    
    def generate_signal(self, ctx: MarketContext) -> Signal:
        # 获取上下文
        m15 = ctx.tf["15m"]
        h1 = ctx.tf["1h"]
        oi = ctx.derivatives.oi
        funding = ctx.derivatives.funding
        
        # 大周期趋势过滤（1h）
        if h1.trend.state == TrendState.STRONG_DOWN:
            # 强下跌趋势中，只允许做空或小仓反弹
            if oi.zscore > 2.0 and funding.bias.name == "NEGATIVE":
                return Signal.short(
                    confidence=0.65,
                    reason="high_oi_negative_funding_in_downtrend"
                )
            return Signal.none(reason="strong_downtrend_filter")
        
        if h1.trend.state == TrendState.STRONG_UP:
            # 强上涨趋势中，只允许做多
            if oi.zscore > 2.0 and funding.bias.name == "POSITIVE":
                return Signal.short(
                    confidence=0.55,
                    reason="extreme_funding_overbought"
                )
        
        # 主信号逻辑（15m）
        # 高持仓量 + 资金费率极端 → 反转信号
        if abs(oi.zscore) > 2.0:
            # 多头挤压条件：高持仓 + 负资金费率 + 买入压力
            if oi.zscore > 2.0 and funding.bias.name in ["NEGATIVE", "EXTREME_NEGATIVE"]:
                if m15.flow.pressure == FlowPressure.BUY:
                    final_conf = ctx.calculate_signal_confidence(0.75, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="long_squeeze_setup"
                    )
            
            # 空头挤压条件：高持仓 + 正资金费率 + 卖出压力
            if oi.zscore < -2.0 and funding.bias.name in ["POSITIVE", "EXTREME_POSITIVE"]:
                if m15.flow.pressure == FlowPressure.SELL:
                    final_conf = ctx.calculate_signal_confidence(0.70, "15m")
                    return Signal.short(
                        confidence=final_conf,
                        reason="short_squeeze_setup"
                    )
        
        # 持仓量急剧变化 + 价格趋势确认
        if abs(oi.delta) > 0.1 * oi.value:  # 持仓量变化超过 10%
            # 持仓量激增 + 价格上涨 → 多头延续
            if oi.delta > 0 and m15.price.change_percent > 0:
                if m15.trend.state == TrendState.WEAK_UP:
                    final_conf = ctx.calculate_signal_confidence(0.60, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="oi_surge_with_price_rise"
                    )
            
            # 持仓量骤降 + 价格下跌 → 空头延续
            if oi.delta < 0 and m15.price.change_percent < 0:
                if m15.trend.state == TrendState.WEAK_DOWN:
                    final_conf = ctx.calculate_signal_confidence(0.55, "15m")
                    return Signal.short(
                        confidence=final_conf,
                        reason="oi_collapse_with_price_drop"
                    )
        
        return Signal.none()
