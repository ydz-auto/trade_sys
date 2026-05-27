"""
V2 Core Strategies - 重构后的核心策略（Top 5）

基于 Event + MarketContext 架构实现，区别于传统 "特征堆 if 判断"

策略列表（按优先级）：
1. OpenInterestBehaviorV2 - 仓位行为策略
2. TradePressureExhaustionV2 - 交易压力耗尽策略
3. FundingExtremeReversalV2 - 资金费率极端反转策略
4. LiquidationCascadeV2 - 爆仓连锁策略
5. MomentumIgnitionV2 - 动量点火策略

核心设计原则（按照用户定义）：
- 策略只读 MarketContext，不直接读 features
- StrategyInfo 定义周期依赖和上下文需求
- 周期设计：4h/1h 过滤，15m 出信号，5m 确认，1m 执行
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from .v2_base import (
    StateAwareStrategy,
    StrategySignalV2,
    SignalDirection,
    SignalStrength,
    StrategyInfo,
)
from domain.config.strategy_config import (
    StrategyConfigV2,
    EntryParams,
    ExitParams,
    RiskParams,
    StrategyType,
)
from domain.market_state import MarketContext
from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from infrastructure.logging import get_logger

logger = get_logger("strategy_v2_core")


# ============== 配置工厂 ==============

def create_v2_configs() -> Dict[str, StrategyConfigV2]:
    """创建 V2 策略配置"""
    return {
        "open_interest_behavior_v2": StrategyConfigV2(
            strategy_id="open_interest_behavior_v2",
            strategy_name="Open Interest Behavior V2",
            strategy_type=StrategyType.DERIVATIVES,
            is_active=True,
            entry_params=EntryParams(
                lookback_period=24,
                confirmation_threshold=0.6,
                min_confidence=0.7,
            ),
            exit_params=ExitParams(
                profit_take_pct=2.0,
                stop_loss_pct=1.5,
                trailing_stop_pct=0.5,
            ),
            risk_params=RiskParams(
                max_position_size=0.1,
                position_size_pct=0.05,
                max_drawdown_pct=5.0,
            ),
        ),
        "trade_pressure_exhaustion_v2": StrategyConfigV2(
            strategy_id="trade_pressure_exhaustion_v2",
            strategy_name="Trade Pressure Exhaustion V2",
            strategy_type=StrategyType.BEHAVIORAL,
            is_active=True,
            entry_params=EntryParams(
                lookback_period=12,
                confirmation_threshold=0.7,
                min_confidence=0.65,
            ),
            exit_params=ExitParams(
                profit_take_pct=1.5,
                stop_loss_pct=1.0,
                trailing_stop_pct=0.3,
            ),
            risk_params=RiskParams(
                max_position_size=0.08,
                position_size_pct=0.04,
                max_drawdown_pct=4.0,
            ),
        ),
        "funding_extreme_reversal_v2": StrategyConfigV2(
            strategy_id="funding_extreme_reversal_v2",
            strategy_name="Funding Extreme Reversal V2",
            strategy_type=StrategyType.DERIVATIVES,
            is_active=True,
            entry_params=EntryParams(
                lookback_period=8,
                confirmation_threshold=0.65,
                min_confidence=0.7,
            ),
            exit_params=ExitParams(
                profit_take_pct=1.8,
                stop_loss_pct=1.2,
                trailing_stop_pct=0.4,
            ),
            risk_params=RiskParams(
                max_position_size=0.07,
                position_size_pct=0.035,
                max_drawdown_pct=4.5,
            ),
        ),
        "liquidation_cascade_v2": StrategyConfigV2(
            strategy_id="liquidation_cascade_v2",
            strategy_name="Liquidation Cascade V2",
            strategy_type=StrategyType.EVENT,
            is_active=True,
            entry_params=EntryParams(
                lookback_period=6,
                confirmation_threshold=0.6,
                min_confidence=0.65,
            ),
            exit_params=ExitParams(
                profit_take_pct=1.2,
                stop_loss_pct=0.8,
                trailing_stop_pct=0.2,
            ),
            risk_params=RiskParams(
                max_position_size=0.06,
                position_size_pct=0.03,
                max_drawdown_pct=3.5,
            ),
        ),
        "momentum_ignition_v2": StrategyConfigV2(
            strategy_id="momentum_ignition_v2",
            strategy_name="Momentum Ignition V2",
            strategy_type=StrategyType.TECHNICAL,
            is_active=True,
            entry_params=EntryParams(
                lookback_period=12,
                confirmation_threshold=0.7,
                min_confidence=0.75,
            ),
            exit_params=ExitParams(
                profit_take_pct=2.5,
                stop_loss_pct=1.8,
                trailing_stop_pct=0.6,
            ),
            risk_params=RiskParams(
                max_position_size=0.09,
                position_size_pct=0.045,
                max_drawdown_pct=5.0,
            ),
        ),
    }


# ============== 策略实现 ==============

class OpenInterestBehaviorV2(StateAwareStrategy):
    """
    Open Interest 仓位行为策略（重构版）
    
    核心逻辑（语义化）：
    - 主周期 15m 评估 OI 行为
    - 1h 过滤趋势方向
    - 5m 确认资金流
    - 衍生品上下文提供 OI 和资金费率数据
    
    策略只读：
    - ctx.tfs["15m"].*
    - ctx.tfs["1h"].trend_state
    - ctx.derivatives.oi
    - ctx.derivatives.funding_rate
    """
    
    def _define_strategy_info(self) -> StrategyInfo:
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=[
                "oi", "oi_delta", "oi_zscore",
                "funding_rate", "funding_zscore",
                "oi_funding_divergence",
            ],
            required_context=[
                "tfs.15m.flow",
                "tfs.1h.trend_state",
                "derivatives.oi",
                "derivatives.funding_rate",
            ],
            primary_timeframe="15m",
            confirm_timeframes=["5m", "1h"],
            execution_timeframe="1m",
            tags={"derivatives", "oi_behavior", "regime_aware"},
        )
    
    def _generate_signal_impl(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """核心逻辑 - 基于 MarketContext 的语义化判断"""
        
        symbol = market_context.symbol
        info = self.strategy_info
        
        # 读取上下文
        tf_15m = market_context.tf(info.primary_timeframe)
        tf_1h = market_context.tf("1h")
        tf_5m = market_context.tf("5m")
        derivatives = market_context.derivatives
        
        # ==== 大周期过滤 ====
        if tf_1h.trend_state.name == "DOWN":
            # 1h 下跌时，限制多头
            if derivatives.oi_zscore > 2.0:
                # OI 极端高，可能反转
                base_conf = 0.7
            else:
                return None
        elif tf_1h.trend_state.name == "UP":
            base_conf = 0.75
        else:  # RANGE
            base_conf = 0.6
        
        # ==== 主周期信号 ====
        signal_confidence = market_context.calculate_signal_confidence(
            base_confidence=base_conf,
            primary_timeframe=info.primary_timeframe,
        )
        
        if signal_confidence < 0.6:
            return None
        
        # ==== 多头入场 ====
        if (
            tf_15m.trend_state.name == "UP"
            and derivatives.oi_zscore > 1.0
            and tf_5m.flow_pressure.name == "BUY"
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.LONG,
                strength=SignalStrength.STRONG if signal_confidence > 0.8 else SignalStrength.MODERATE,
                confidence=signal_confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                key_context_paths=[
                    "tfs.15m.trend_state",
                    "tfs.1h.trend_state",
                    "derivatives.oi_zscore",
                ],
                reason=f"OI rising with trend, confidence={signal_confidence:.2f}",
            )
        
        # ==== 空头入场 ====
        if (
            tf_15m.trend_state.name == "DOWN"
            and derivatives.oi_zscore < -1.0
            and tf_5m.flow_pressure.name == "SELL"
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.SHORT,
                strength=SignalStrength.STRONG if signal_confidence > 0.8 else SignalStrength.MODERATE,
                confidence=signal_confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                key_context_paths=[
                    "tfs.15m.trend_state",
                    "tfs.1h.trend_state",
                    "derivatives.oi_zscore",
                ],
                reason=f"OI falling with trend, confidence={signal_confidence:.2f}",
            )
        
        return None


class TradePressureExhaustionV2(StateAwareStrategy):
    """
    交易压力耗尽策略（重构版）
    
    核心逻辑：
    - 15m 检测压力耗尽
    - 5m 确认资金流方向
    - 1m 检查流动性质量
    
    策略只读：
    - ctx.tfs["15m"].flow
    - ctx.tfs["15m"].volume_state
    - ctx.tfs["5m"].flow_pressure
    - ctx.tfs["1m"].liquidity_state
    """
    
    def _define_strategy_info(self) -> StrategyInfo:
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=[
                "trade_delta", "cumulative_delta",
                "pressure_zscore", "volume_ratio",
                "cvd", "sweep_score",
            ],
            required_context=[
                "tfs.15m.flow",
                "tfs.15m.volume_state",
                "tfs.5m.flow_pressure",
                "tfs.1m.liquidity_state",
            ],
            primary_timeframe="15m",
            confirm_timeframes=["5m", "1m"],
            execution_timeframe="1m",
            tags={"behavioral", "flow_analysis", "momentum"},
        )
    
    def _generate_signal_impl(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        
        symbol = market_context.symbol
        info = self.strategy_info
        
        # 读取上下文
        tf_15m = market_context.tf(info.primary_timeframe)
        tf_5m = market_context.tf("5m")
        tf_1m = market_context.tf("1m")
        
        # ==== 检查压力耗尽 ====
        if not market_context.is_exhausted():
            return None
        
        # ==== 计算置信度 ====
        base_conf = 0.7
        signal_confidence = market_context.calculate_signal_confidence(
            base_confidence=base_conf,
            primary_timeframe=info.primary_timeframe,
        )
        
        if signal_confidence < 0.65:
            return None
        
        # ==== 多头入场（卖出压力耗尽）====
        if (
            tf_15m.volume_state.name == "CLIMAX"
            and tf_5m.flow_pressure.name == "BUY"
            and tf_1m.liquidity_state.name != "VACUUM"
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.LONG,
                strength=SignalStrength.EXTREME if signal_confidence > 0.9 else SignalStrength.STRONG,
                confidence=signal_confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                key_context_paths=[
                    "tfs.15m.volume_state",
                    "tfs.5m.flow_pressure",
                    "tfs.1m.liquidity_state",
                ],
                reason=f"Buy pressure exhaustion, confidence={signal_confidence:.2f}",
            )
        
        # ==== 空头入场（买入压力耗尽）====
        if (
            tf_15m.volume_state.name == "CLIMAX"
            and tf_5m.flow_pressure.name == "SELL"
            and tf_1m.liquidity_state.name != "VACUUM"
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.SHORT,
                strength=SignalStrength.EXTREME if signal_confidence > 0.9 else SignalStrength.STRONG,
                confidence=signal_confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                key_context_paths=[
                    "tfs.15m.volume_state",
                    "tfs.5m.flow_pressure",
                    "tfs.1m.liquidity_state",
                ],
                reason=f"Sell pressure exhaustion, confidence={signal_confidence:.2f}",
            )
        
        return None


class FundingExtremeReversalV2(StateAwareStrategy):
    """
    资金费率极端反转策略（重构版）
    
    核心逻辑：
    - 资金费率极端值 + 价格背离 = 反转信号
    - 4h 过滤大方向
    - 1h 确认趋势
    
    策略只读：
    - ctx.derivatives.funding_zscore
    - ctx.derivatives.funding_extreme_reversal
    - ctx.tfs["4h"].trend_state
    - ctx.tfs["1h"].trend_state
    """
    
    def _define_strategy_info(self) -> StrategyInfo:
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=[
                "funding_rate", "funding_zscore",
                "funding_extreme_reversal", "funding_extreme_side",
                "oi_funding_divergence",
            ],
            required_context=[
                "derivatives.funding_zscore",
                "derivatives.funding_extreme_reversal",
                "tfs.4h.trend_state",
                "tfs.1h.trend_state",
            ],
            primary_timeframe="1h",
            confirm_timeframes=["15m", "4h"],
            execution_timeframe="5m",
            tags={"derivatives", "funding", "mean_reversion"},
        )
    
    def _generate_signal_impl(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        
        symbol = market_context.symbol
        info = self.strategy_info
        
        # 读取上下文
        derivatives = market_context.derivatives
        tf_4h = market_context.tf("4h")
        tf_1h = market_context.tf(info.primary_timeframe)
        
        # ==== 检查资金费率极端 ====
        if not derivatives.funding_extreme_reversal:
            return None
        
        # ==== 大周期过滤 ====
        if tf_4h.trend_state.name == "DOWN":
            if derivatives.funding_extreme_side == "short":
                # 4h 下跌 + 资金费率极端空头 -> 可能反弹
                base_conf = 0.75
            else:
                return None  # 不做逆势
        elif tf_4h.trend_state.name == "UP":
            if derivatives.funding_extreme_side == "long":
                base_conf = 0.75
            else:
                return None
        else:  # RANGE
            base_conf = 0.65
        
        # ==== 计算置信度 ====
        signal_confidence = market_context.calculate_signal_confidence(
            base_confidence=base_conf,
            primary_timeframe=info.primary_timeframe,
        )
        
        if signal_confidence < 0.65:
            return None
        
        # ==== 生成信号 ====
        direction = SignalDirection.LONG if derivatives.funding_extreme_side == "short" else SignalDirection.SHORT
        
        return StrategySignalV2(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            symbol=symbol,
            direction=direction,
            strength=SignalStrength.STRONG if signal_confidence > 0.8 else SignalStrength.MODERATE,
            confidence=signal_confidence,
            triggering_event_type=triggering_event.type if triggering_event else None,
            key_context_paths=[
                "derivatives.funding_extreme_side",
                "tfs.4h.trend_state",
                "tfs.1h.trend_state",
            ],
            reason=f"Funding extreme {derivatives.funding_extreme_side}, confidence={signal_confidence:.2f}",
        )


class LiquidationCascadeV2(StateAwareStrategy):
    """
    爆仓连锁策略（重构版）
    
    核心逻辑：
    - 检测强平后的反转机会
    - 5m 确认资金流
    - 1m 检查入场条件
    
    策略只读：
    - ctx.derivatives.liquidation_total
    - ctx.derivatives.liquidation_reversal_signal
    - ctx.tfs["5m"].flow_pressure
    - ctx.tfs["1m"].liquidity_state
    """
    
    def _define_strategy_info(self) -> StrategyInfo:
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=[
                "liquidation_long", "liquidation_short",
                "liquidation_total", "liquidation_reversal_signal",
            ],
            required_context=[
                "derivatives.liquidation_total",
                "derivatives.liquidation_reversal_signal",
                "tfs.5m.flow_pressure",
                "tfs.1m.liquidity_state",
            ],
            primary_timeframe="5m",
            confirm_timeframes=["1m", "15m"],
            execution_timeframe="1m",
            tags={"event_driven", "liquidation", "reversal"},
        )
    
    def _generate_signal_impl(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        
        symbol = market_context.symbol
        info = self.strategy_info
        
        # 读取上下文
        derivatives = market_context.derivatives
        tf_5m = market_context.tf(info.primary_timeframe)
        tf_1m = market_context.tf("1m")
        tf_15m = market_context.tf("15m")
        
        # ==== 检查强平反转信号 ====
        if not derivatives.liquidation_reversal_signal:
            return None
        
        # ==== 检查流动性 ====
        if tf_1m.liquidity_state.name == "VACUUM":
            return None  # 流动性真空，不入场
        
        # ==== 判断方向 ====
        if derivatives.liquidation_long > derivatives.liquidation_short:
            # 多单被强平，可能反弹做多
            if tf_5m.flow_pressure.name != "SELL":  # 资金流不再卖出
                direction = SignalDirection.LONG
                base_conf = 0.7
            else:
                return None
        else:
            # 空单被强平，可能反弹做空
            if tf_5m.flow_pressure.name != "BUY":
                direction = SignalDirection.SHORT
                base_conf = 0.7
            else:
                return None
        
        # ==== 计算置信度 ====
        signal_confidence = market_context.calculate_signal_confidence(
            base_confidence=base_conf,
            primary_timeframe=info.primary_timeframe,
        )
        
        if signal_confidence < 0.6:
            return None
        
        return StrategySignalV2(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            symbol=symbol,
            direction=direction,
            strength=SignalStrength.STRONG if signal_confidence > 0.8 else SignalStrength.MODERATE,
            confidence=signal_confidence,
            triggering_event_type=triggering_event.type if triggering_event else None,
            key_context_paths=[
                "derivatives.liquidation_reversal_signal",
                "tfs.5m.flow_pressure",
                "tfs.1m.liquidity_state",
            ],
            reason=f"Liquidation cascade reversal, confidence={signal_confidence:.2f}",
        )


class MomentumIgnitionV2(StateAwareStrategy):
    """
    动量点火策略（重构版）
    
    核心逻辑：
    - 高置信度趋势 + 动量突破
    - 15m 主周期判断
    - 1h 趋势过滤
    - 5m 动量确认
    
    策略只读：
    - ctx.tfs["15m"].momentum_score
    - ctx.tfs["1h"].trend_state
    - ctx.tfs["5m"].momentum_direction
    - ctx.tfs["15m"].volatility_state
    """
    
    def _define_strategy_info(self) -> StrategyInfo:
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=[
                "momentum_score", "momentum_direction",
                "volatility", "volume_ratio",
            ],
            required_context=[
                "tfs.15m.momentum_score",
                "tfs.1h.trend_state",
                "tfs.5m.momentum_direction",
                "tfs.15m.volatility_state",
            ],
            primary_timeframe="15m",
            confirm_timeframes=["5m", "1h"],
            execution_timeframe="1m",
            tags={"technical", "momentum", "trend_following"},
        )
    
    def _generate_signal_impl(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        
        symbol = market_context.symbol
        info = self.strategy_info
        
        # 读取上下文
        tf_15m = market_context.tf(info.primary_timeframe)
        tf_1h = market_context.tf("1h")
        tf_5m = market_context.tf("5m")
        
        # ==== 检查动量 ====
        momentum_score = tf_15m.momentum_score
        if abs(momentum_score) < 0.7:
            return None
        
        # ==== 趋势对齐 ====
        if tf_1h.trend_state.name == "UP" and momentum_score > 0:
            direction = SignalDirection.LONG
        elif tf_1h.trend_state.name == "DOWN" and momentum_score < 0:
            direction = SignalDirection.SHORT
        elif tf_1h.trend_state.name == "RANGE":
            # 区间内按动量方向
            direction = SignalDirection.LONG if momentum_score > 0 else SignalDirection.SHORT
        else:
            return None  # 逆势
        
        # ==== 确认周期 ====
        if tf_5m.momentum_direction.name == "NEUTRAL":
            return None  # 5m 没有确认
        
        # ==== 波动率检查 ====
        if tf_15m.volatility_state.name == "EXTREME":
            return None  # 极端波动不入场
        
        # ==== 计算置信度 ====
        base_conf = 0.75
        signal_confidence = market_context.calculate_signal_confidence(
            base_confidence=base_conf,
            primary_timeframe=info.primary_timeframe,
        )
        
        if signal_confidence < 0.7:
            return None
        
        return StrategySignalV2(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            symbol=symbol,
            direction=direction,
            strength=SignalStrength.STRONG if signal_confidence > 0.85 else SignalStrength.MODERATE,
            confidence=signal_confidence,
            triggering_event_type=triggering_event.type if triggering_event else None,
            key_context_paths=[
                "tfs.15m.momentum_score",
                "tfs.1h.trend_state",
                "tfs.5m.momentum_direction",
            ],
            reason=f"Momentum ignition {direction.value}, confidence={signal_confidence:.2f}",
        )


# ============== 导出接口 ==============

__all__ = [
    "create_v2_configs",
    "OpenInterestBehaviorV2",
    "TradePressureExhaustionV2",
    "FundingExtremeReversalV2",
    "LiquidationCascadeV2",
    "MomentumIgnitionV2",
]
