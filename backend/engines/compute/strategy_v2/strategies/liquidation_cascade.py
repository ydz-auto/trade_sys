"""
Liquidation Cascade Strategy - 强平瀑布策略

基于强平数据判断市场反转和延续信号。

核心逻辑：
1. 大量多头强平 + 价格下跌 → 可能反弹
2. 大量空头强平 + 价格上涨 → 可能回调
3. 强平后资金流反转 → 确认信号
"""

from engines.compute.context import (
    MarketContext,
    TrendState,
    FlowPressure,
    LiquidityState,
)

from ..base import StrategyV2, Signal
from ..metadata import StrategyMeta
from ..registry import register_strategy


@register_strategy
class LiquidationCascadeStrategy(StrategyV2):
    """
    强平瀑布策略
    
    策略逻辑：
    - 当大量强平发生时，市场可能出现过度反应
    - 强平后的资金流反转是重要确认信号
    - 结合流动性状态判断入场时机
    """
    
    meta = StrategyMeta(
        name="Liquidation Cascade",
        primary_tf="5m",
        confirm_tfs=["1m", "15m"],
        execution_tf="1m",
        required_context=[
            "tf.5m.price",
            "tf.5m.flow",
            "tf.1m.liquidity",
            "tf.1m.flow",
            "tf.15m.trend",
            "derivatives.liquidation",
        ],
        tags={"derivatives", "liquidation", "mean_reversion", "real_time"},
    )
    
    def generate_signal(self, ctx: MarketContext) -> Signal:
        # 获取上下文
        m5 = ctx.tf["5m"]
        m1 = ctx.tf["1m"]
        m15 = ctx.tf["15m"]
        liquidation = ctx.derivatives.liquidation
        
        # 检查是否有强平信号
        if liquidation.total == 0:
            return Signal.none(reason="no_liquidation")
        
        # 1m 流动性检查（执行层过滤）
        if m1.liquidity.state == LiquidityState.VACUUM:
            return Signal.none(reason="liquidity_vacuum")
        
        # 多头强平瀑布 → 可能反弹
        if liquidation.long_zscore > 2.0:
            # 条件：大量多头强平 + 价格下跌
            if m5.price.change_percent < -1.0:
                # 检查资金流是否反转
                if m1.flow.pressure == FlowPressure.BUY:
                    # 强平后出现买入压力 → 反弹信号
                    final_conf = ctx.calculate_signal_confidence(0.70, "5m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="long_liquidation_bounce"
                    )
                
                # 如果 15m 是下跌趋势，反弹信号更强
                if m15.trend.state == TrendState.WEAK_DOWN:
                    if m1.flow.pressure == FlowPressure.NEUTRAL:
                        final_conf = ctx.calculate_signal_confidence(0.60, "5m")
                        return Signal.long(
                            confidence=final_conf,
                            reason="long_liquidation_bounce_in_downtrend"
                        )
        
        # 空头强平瀑布 → 可能回调
        if liquidation.short_zscore > 2.0:
            # 条件：大量空头强平 + 价格上涨
            if m5.price.change_percent > 1.0:
                # 检查资金流是否反转
                if m1.flow.pressure == FlowPressure.SELL:
                    # 强平后出现卖出压力 → 回调信号
                    final_conf = ctx.calculate_signal_confidence(0.70, "5m")
                    return Signal.short(
                        confidence=final_conf,
                        reason="short_liquidation_pullback"
                    )
                
                # 如果 15m 是上涨趋势，回调信号更强
                if m15.trend.state == TrendState.WEAK_UP:
                    if m1.flow.pressure == FlowPressure.NEUTRAL:
                        final_conf = ctx.calculate_signal_confidence(0.60, "5m")
                        return Signal.short(
                            confidence=final_conf,
                            reason="short_liquidation_pullback_in_uptrend"
                        )
        
        # 强平反转信号（来自 feature）
        if liquidation.reversal_signal:
            if m5.flow.pressure == FlowPressure.BUY:
                final_conf = ctx.calculate_signal_confidence(0.65, "5m")
                return Signal.long(
                    confidence=final_conf,
                    reason="liquidation_reversal_signal_long"
                )
            elif m5.flow.pressure == FlowPressure.SELL:
                final_conf = ctx.calculate_signal_confidence(0.65, "5m")
                return Signal.short(
                    confidence=final_conf,
                    reason="liquidation_reversal_signal_short"
                )
        
        # 强平延续信号
        # 多头强平 + 持续卖出压力 → 继续下跌
        if liquidation.long_zscore > 1.5 and m5.flow.pressure == FlowPressure.SELL:
            if m15.trend.state == TrendState.WEAK_DOWN:
                final_conf = ctx.calculate_signal_confidence(0.55, "5m")
                return Signal.short(
                    confidence=final_conf,
                    reason="liquidation_cascade_continuation_short"
                )
        
        # 空头强平 + 持续买入压力 → 继续上涨
        if liquidation.short_zscore > 1.5 and m5.flow.pressure == FlowPressure.BUY:
            if m15.trend.state == TrendState.WEAK_UP:
                final_conf = ctx.calculate_signal_confidence(0.55, "5m")
                return Signal.long(
                    confidence=final_conf,
                    reason="liquidation_cascade_continuation_long"
                )
        
        return Signal.none()
