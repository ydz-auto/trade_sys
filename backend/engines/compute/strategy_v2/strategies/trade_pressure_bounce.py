"""
Trade Pressure Bounce Strategy - 交易压力反弹策略

基于资金流数据判断短期反转机会。

核心逻辑：
1. 极端买入/卖出压力后可能出现反转
2. CVD 背离 + 价格反转 → 确认信号
3. 结合波动率和成交量验证
"""

from engines.compute.context import (
    MarketContext,
    TrendState,
    FlowPressure,
    VolatilityState,
    VolumeState,
)

from ..base import StrategyV2, Signal
from ..metadata import StrategyMeta
from ..registry import register_strategy


@register_strategy
class TradePressureBounceStrategy(StrategyV2):
    """
    交易压力反弹策略
    
    策略逻辑：
    - 当资金流出现极端压力后，市场可能出现反转
    - CVD（累积成交量delta）背离是重要的反转信号
    - 结合波动率和成交量确认反弹强度
    """
    
    meta = StrategyMeta(
        name="Trade Pressure Bounce",
        primary_tf="15m",
        confirm_tfs=["5m", "1m"],
        execution_tf="1m",
        required_context=[
            "tf.15m.price",
            "tf.15m.flow",
            "tf.15m.volatility",
            "tf.15m.volume",
            "tf.5m.flow",
            "tf.1m.liquidity",
        ],
        tags={"orderflow", "trade_pressure", "mean_reversion", "real_time", "multi_timeframe"},
    )
    
    def generate_signal(self, ctx: MarketContext) -> Signal:
        # 获取上下文
        m15 = ctx.tf["15m"]
        m5 = ctx.tf["5m"]
        m1 = ctx.tf["1m"]
        
        # 执行层检查（1m 流动性）
        if m1.liquidity.state.name == "VACUUM":
            return Signal.none(reason="liquidity_vacuum")
        
        # 卖出压力极端 → 可能反弹
        if m15.flow.pressure == FlowPressure.SELL and m15.flow.score < -0.7:
            # CVD 背离：卖出压力但 CVD 上升
            if m15.flow.cvd_slope > 0:
                # 确认信号：5m 出现买入压力
                if m5.flow.pressure == FlowPressure.BUY:
                    final_conf = ctx.calculate_signal_confidence(0.70, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="sell_pressure_bounce_cvd_divergence"
                    )
            
            # 成交量高潮 + 卖出压力 → 可能反转
            if m15.volume.state == VolumeState.CLIMAX:
                if m5.flow.pressure in [FlowPressure.BUY, FlowPressure.NEUTRAL]:
                    final_conf = ctx.calculate_signal_confidence(0.65, "15m")
                    return Signal.long(
                        confidence=final_conf,
                        reason="sell_pressure_bounce_volume_climax"
                    )
        
        # 买入压力极端 → 可能回调
        if m15.flow.pressure == FlowPressure.BUY and m15.flow.score > 0.7:
            # CVD 背离：买入压力但 CVD 下降
            if m15.flow.cvd_slope < 0:
                # 确认信号：5m 出现卖出压力
                if m5.flow.pressure == FlowPressure.SELL:
                    final_conf = ctx.calculate_signal_confidence(0.70, "15m")
                    return Signal.short(
                        confidence=final_conf,
                        reason="buy_pressure_pullback_cvd_divergence"
                    )
            
            # 成交量高潮 + 买入压力 → 可能反转
            if m15.volume.state == VolumeState.CLIMAX:
                if m5.flow.pressure in [FlowPressure.SELL, FlowPressure.NEUTRAL]:
                    final_conf = ctx.calculate_signal_confidence(0.65, "15m")
                    return Signal.short(
                        confidence=final_conf,
                        reason="buy_pressure_pullback_volume_climax"
                    )
        
        # 波动率压缩后的突破
        if m15.volatility.state == VolatilityState.LOW:
            # 波动率压缩后出现资金流突破
            if m15.flow.pressure != FlowPressure.NEUTRAL:
                # 确认方向
                if m15.flow.pressure == FlowPressure.BUY:
                    if m5.flow.pressure == FlowPressure.BUY:
                        final_conf = ctx.calculate_signal_confidence(0.65, "15m")
                        return Signal.long(
                            confidence=final_conf,
                            reason="vol_compression_breakout_long"
                        )
                else:
                    if m5.flow.pressure == FlowPressure.SELL:
                        final_conf = ctx.calculate_signal_confidence(0.65, "15m")
                        return Signal.short(
                            confidence=final_conf,
                            reason="vol_compression_breakout_short"
                        )
        
        # 主动交易比率反转
        if m15.flow.aggressive_ratio < 0.4:  # 大量主动卖出
            if m5.flow.aggressive_ratio > 0.6:  # 5m 反转
                final_conf = ctx.calculate_signal_confidence(0.60, "15m")
                return Signal.long(
                    confidence=final_conf,
                    reason="aggressive_ratio_reversal_long"
                )
        
        if m15.flow.aggressive_ratio > 0.6:  # 大量主动买入
            if m5.flow.aggressive_ratio < 0.4:  # 5m 反转
                final_conf = ctx.calculate_signal_confidence(0.60, "15m")
                return Signal.short(
                    confidence=final_conf,
                    reason="aggressive_ratio_reversal_short"
                )
        
        return Signal.none()
