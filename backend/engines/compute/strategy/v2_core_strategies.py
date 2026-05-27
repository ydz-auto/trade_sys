"""
V2 Core Strategies - 重构后的核心策略（Top 6）

基于 Event + State 架构实现，区别于传统 "特征堆 if 判断"

策略列表（按优先级）：
1. OpenInterestBehaviorV2 - 仓位行为策略
2. TradePressureExhaustionV2 - 交易压力耗尽策略
3. FundingExtremeReversalV2 - 资金费率极端反转策略
4. LiquidationCascadeV2 - 爆仓连锁策略
5. CVDDivergenceV2 - CVD 背离策略（待定）
6. PanicReversalV2 - 恐慌反转策略（待定）
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from .v2_base import (
    StateAwareStrategy,
    EventDrivenStrategy,
    RegimeAwareStrategy,
    StrategySignalV2,
    SignalDirection,
    SignalStrength,
)
from domain.config.strategy_config import (
    StrategyConfigV2,
    EntryParams,
    ExitParams,
    RiskParams,
    StrategyType,
)
from domain.market_state.state import MarketState
from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from infrastructure.logging import get_logger

logger = get_logger("strategy_v2_core")


class OpenInterestBehaviorV2(StateAwareStrategy):
    """
    Open Interest 仓位行为策略（重构版）
    
    核心逻辑（语义化，不再是原始值比较）：
    - 趋势上涨 + OI上升 + 状态有确认 -> 做多
    - 趋势上涨 + OI下降 + 压力耗尽 -> 做空
    - 趋势下跌 + OI上升 + 压力积累 -> 做空
    - 趋势下跌 + OI下降 + 压力耗尽 -> 做多
    
    旧代码的问题：
    ```
    if price_change > 0 and oi_change > 0:  # 原始值比较
        return LONG
    ```
    
    新代码的方式：
    ```
    if market_state.is_trending_up() and market_state.oi_regime == 'rising':
        return LONG
    ```
    """
    
    def __init__(self, config: StrategyConfigV2):
        super().__init__(config)
        self.min_confidence = 0.6
    
    def _generate_signal_impl(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent],
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """核心逻辑 - 基于 State 的语义化判断"""
        
        symbol = market_state.symbol
        confidence = market_state.confidence
        
        if confidence < self.min_confidence:
            return None
        
        # ==== 多头入场场景 ====
        if (
            market_state.is_trending_up()
            and market_state.oi_regime == 'rising'
            and market_state.confidence > 0.7
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.LONG,
                strength=SignalStrength.STRONG if confidence > 0.8 else SignalStrength.MODERATE,
                confidence=confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                triggering_market_state=market_state,
                key_features={
                    'oi_regime': market_state.oi_regime,
                    'confidence': confidence,
                },
                reason=f"OI行为做多: 趋势上涨+仓位增加 [conf={confidence:.2f}]",
                timestamp=market_state.timestamp,
            )
        
        if (
            market_state.is_exhausted()
            and market_state.oi_regime == 'falling'
            and market_state.is_trending_down()
            and confidence > 0.65
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.LONG,
                strength=SignalStrength.STRONG,
                confidence=confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                triggering_market_state=market_state,
                key_features={
                    'pressure_state': market_state.pressure,
                    'oi_regime': market_state.oi_regime,
                },
                reason=f"OI行为做多: 价格下跌+压力耗尽+仓位减少 [conf={confidence:.2f}]",
                timestamp=market_state.timestamp,
            )
        
        # ==== 空头入场场景 ====
        if (
            market_state.is_trending_down()
            and market_state.oi_regime == 'rising'
            and market_state.confidence > 0.7
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.SHORT,
                strength=SignalStrength.STRONG if confidence > 0.8 else SignalStrength.MODERATE,
                confidence=confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                triggering_market_state=market_state,
                key_features={
                    'oi_regime': market_state.oi_regime,
                    'confidence': confidence,
                },
                reason=f"OI行为做空: 趋势下跌+仓位增加 [conf={confidence:.2f}]",
                timestamp=market_state.timestamp,
            )
        
        if (
            market_state.is_trending_up()
            and market_state.oi_regime == 'falling'
            and (market_state.has_pressure_divergence() or market_state.is_exhausted())
            and confidence > 0.65
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.SHORT,
                strength=SignalStrength.MODERATE,
                confidence=confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                triggering_market_state=market_state,
                key_features={
                    'pressure_state': market_state.pressure,
                    'oi_regime': market_state.oi_regime,
                },
                reason=f"OI行为做空: 价格上涨+压力耗尽+仓位减少 [conf={confidence:.2f}]",
                timestamp=market_state.timestamp,
            )
        
        return None


class TradePressureExhaustionV2(EventDrivenStrategy):
    """
    交易压力耗尽策略（重构版）
    
    完全事件驱动：
    - 只关注 TRADE_PRESSURE_EXHAUSTION 和 TRADE_PRESSURE_FLUSH 事件
    - 结合当前 State 确认入场时机
    
    旧代码模式（特征堆）：
    ```
    if zscore_pressure < -3 and volume > 2*avg:  # 魔法数字
        return Signal
    ```
    
    新代码模式（事件 + 状态）：
    ```
    if (event.type == EventType.TRADE_PRESSURE_FLUSH 
        and market_state.is_exhausted()
        and market_state.is_high_confidence()):
        return Signal
    ```
    """
    
    def __init__(self, config: StrategyConfigV2):
        # 定义感兴趣的事件
        interested_events = [
            EventType.TRADE_PRESSURE_EXHAUSTION,
            EventType.TRADE_PRESSURE_FLUSH,
        ]
        super().__init__(config, interested_event_types=interested_events)
    
    def _handle_event(
        self,
        event: BaseEvent,
        market_state: MarketState,
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """处理特定事件"""
        symbol = market_state.symbol
        
        # ==== 做多场景：压力释放/耗尽在下跌趋势中 ====
        if (
            (event.type == EventType.TRADE_PRESSURE_FLUSH or event.type == EventType.TRADE_PRESSURE_EXHAUSTION)
            and market_state.is_trending_down()
            and market_state.confidence > 0.65
        ):
            # 确认是"底部"行为
            if (
                market_state.is_exhausted()
                or market_state.has_pressure_divergence()
                or market_state.is_liquid_vacuum()
            ):
                strength = SignalStrength.STRONG if market_state.confidence > 0.8 else SignalStrength.MODERATE
                return StrategySignalV2(
                    strategy_id=self.strategy_id,
                    strategy_name=self.strategy_name,
                    symbol=symbol,
                    direction=SignalDirection.LONG,
                    strength=strength,
                    confidence=market_state.confidence,
                    triggering_event_type=event.type,
                    triggering_market_state=market_state,
                    key_features={
                        'pressure_state': market_state.pressure,
                        'liquidity_state': market_state.liquidity,
                        'event_type': event.type.value,
                    },
                    reason=f"压力耗尽做多: {event.type.value} 在下跌趋势中触发 [conf={market_state.confidence:.2f}]",
                    timestamp=event.timestamp if hasattr(event, 'timestamp') else datetime.utcnow(),
                )
        
        # ==== 做空场景：压力释放/耗尽在上涨趋势中 ====
        if (
            (event.type == EventType.TRADE_PRESSURE_FLUSH or event.type == EventType.TRADE_PRESSURE_EXHAUSTION)
            and market_state.is_trending_up()
            and market_state.confidence > 0.65
        ):
            if (
                market_state.is_exhausted()
                or market_state.has_pressure_divergence()
            ):
                strength = SignalStrength.STRONG if market_state.confidence > 0.8 else SignalStrength.MODERATE
                return StrategySignalV2(
                    strategy_id=self.strategy_id,
                    strategy_name=self.strategy_name,
                    symbol=symbol,
                    direction=SignalDirection.SHORT,
                    strength=strength,
                    confidence=market_state.confidence,
                    triggering_event_type=event.type,
                    triggering_market_state=market_state,
                    key_features={
                        'pressure_state': market_state.pressure,
                        'event_type': event.type.value,
                    },
                    reason=f"压力耗尽做空: {event.type.value} 在上涨趋势中触发 [conf={market_state.confidence:.2f}]",
                    timestamp=event.timestamp if hasattr(event, 'timestamp') else datetime.utcnow(),
                )
        
        return None


class FundingExtremeReversalV2(StateAwareStrategy):
    """
    资金费率极端反转策略（重构版）
    
    核心逻辑：
    - 极端正费率 + 趋势疲态 + 压力背离 -> 做空
    - 极端负费率 + 趋势疲态 + 压力背离 -> 做多
    
    利用 State 的 funding_regime 字段判断，而非原始值
    """
    
    def __init__(self, config: StrategyConfigV2):
        super().__init__(config)
    
    def _generate_signal_impl(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent],
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        symbol = market_state.symbol
        
        # ==== 做空场景：极端正费率 + 上涨趋势疲态 ====
        if (
            market_state.funding_regime == 'extreme_positive'
            and market_state.is_trending_up()
            and (market_state.has_pressure_divergence() or market_state.is_exhausted())
            and market_state.confidence > 0.6
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.SHORT,
                strength=SignalStrength.MODERATE,
                confidence=market_state.confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                triggering_market_state=market_state,
                key_features={
                    'funding_regime': market_state.funding_regime,
                    'pressure_state': market_state.pressure,
                },
                reason=f"资金费率反转做空: 极端正费率+上涨疲态 [conf={market_state.confidence:.2f}]",
                timestamp=market_state.timestamp,
            )
        
        # ==== 做多场景：极端负费率 + 下跌趋势疲态 ====
        if (
            market_state.funding_regime == 'extreme_negative'
            and market_state.is_trending_down()
            and (market_state.is_exhausted() or market_state.has_pressure_divergence())
            and market_state.confidence > 0.6
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.LONG,
                strength=SignalStrength.MODERATE,
                confidence=market_state.confidence,
                triggering_event_type=triggering_event.type if triggering_event else None,
                triggering_market_state=market_state,
                key_features={
                    'funding_regime': market_state.funding_regime,
                    'pressure_state': market_state.pressure,
                },
                reason=f"资金费率反转做多: 极端负费率+下跌疲态 [conf={market_state.confidence:.2f}]",
                timestamp=market_state.timestamp,
            )
        
        return None


class LiquidationCascadeV2(EventDrivenStrategy):
    """
    爆仓连锁策略（重构版）
    
    完全事件驱动，结合 Market State 确认
    """
    
    def __init__(self, config: StrategyConfigV2):
        interested_events = [
            EventType.MARKET_STRUCTURE_LIQUIDATION,
        ]
        super().__init__(config, interested_event_types=interested_events)
    
    def _handle_event(
        self,
        event: BaseEvent,
        market_state: MarketState,
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        symbol = market_state.symbol
        
        # ==== 做多场景：大量多头爆仓 + 压力耗尽 + Crash/Squeeze Regime ====
        if (
            market_state.is_crash()
            and market_state.is_exhausted()
            and market_state.oi_regime == 'falling'
            and market_state.confidence > 0.7
        ):
            return StrategySignalV2(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                symbol=symbol,
                direction=SignalDirection.LONG,
                strength=SignalStrength.EXTREME,
                confidence=market_state.confidence,
                triggering_event_type=event.type,
                triggering_market_state=market_state,
                key_features={
                    'regime': market_state.regime,
                    'pressure_state': market_state.pressure,
                    'oi_regime': market_state.oi_regime,
                },
                reason=f"爆仓连锁做多: Crash状态+压力耗尽+仓位减少 [conf={market_state.confidence:.2f}]",
                timestamp=event.timestamp if hasattr(event, 'timestamp') else datetime.utcnow(),
            )
        
        return None


class MomentumIgnitionV2(StateAwareStrategy):
    """
    动量点火策略（重构版）
    
    核心逻辑（State 驱动）：
        - 在 TRENDING 状态下，成交量急放 + 价格大幅移动 → 跟随动量方向
        
    符合您对“高质量低频”策略的期望
    """
    
    def __init__(self, config: StrategyConfigV2):
        super().__init__(config)
        self.min_volume_spike = 3.0  # 成交量急放阈值
        self.min_return = 0.01  # 1h 涨跌幅阈值
    
    def _generate_signal_impl(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent],
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """核心逻辑 - 基于当前 Regime 决定是否点火"""
        
        # 只在 TRENDING 或 BREAKOUT 状态下工作
        if not (market_state.regime in [RegimeType.TRENDING_UP, RegimeType.TRENDING_DOWN] 
                or market_state.regime == RegimeType.BREAKOUT):
            return None
        
        symbol = market_state.symbol
        volume_ratio = current_features.get('volume_ratio', 0.0)
        return_1h = current_features.get('return_1h', 0.0)
        
        # 确认成交量急放
        if volume_ratio < self.min_volume_spike:
            return None
        
        # 确认价格大幅移动
        if abs(return_1h) < self.min_return:
            return None
        
        # 方向判断
        direction = SignalDirection.LONG if return_1h > 0 else SignalDirection.SHORT
        
        # 确认方向与当前 Regime 一致（避免逆势）
        if direction == SignalDirection.LONG and market_state.is_trending_down():
            return None
        if direction == SignalDirection.SHORT and market_state.is_trending_up():
            return None
        
        # 计算信心度
        confidence = min(0.9, (
            min(1.0, volume_ratio / 5.0) * 0.5 +
            min(1.0, abs(return_1h) / 0.03) * 0.4 +
            0.1
        ))
        
        return StrategySignalV2(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            symbol=symbol,
            direction=direction,
            strength=SignalStrength.STRONG if confidence > 0.7 else SignalStrength.MODERATE,
            confidence=confidence,
            triggering_event_type=triggering_event.type if triggering_event else None,
            triggering_market_state=market_state,
            key_features={
                'volume_ratio': volume_ratio,
                'return_1h': return_1h,
                'regime': market_state.regime,
            },
            reason=f"动量点火{direction}: 成交量急放={volume_ratio:.2f}x, 1h涨跌={return_1h*100:.2f}%",
            timestamp=market_state.timestamp,
        )


def create_v2_configs() -> Dict[str, StrategyConfigV2]:
    """
    创建所有 V2 策略的默认配置（Top 5 策略）
    
    这样所有策略都使用类型化的配置，不再有散参数
    """
    return {
        'open_interest_behavior_v2': StrategyConfigV2(
            strategy_id='open_interest_behavior_v2',
            strategy_name='Open Interest 仓位行为策略 V2',
            strategy_type=StrategyType.BEHAVIORAL,
            is_active=True,
            entry_params=EntryParams(
                signal_threshold=0.6,
                max_entries_per_symbol=1,
            ),
            exit_params=ExitParams(
                stop_loss_pct=0.02,
                take_profit_pct=0.05,
            ),
            risk_params=RiskParams(
                position_size_pct=0.1,
                max_positions=3,
            ),
            supported_symbols=['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
            description='基于仓位变化的事件驱动策略 V2',
        ),
        'trade_pressure_exhaustion_v2': StrategyConfigV2(
            strategy_id='trade_pressure_exhaustion_v2',
            strategy_name='交易压力耗尽策略 V2',
            strategy_type=StrategyType.BEHAVIORAL,
            is_active=True,
            entry_params=EntryParams(
                signal_threshold=0.65,
                max_entries_per_symbol=2,
            ),
            exit_params=ExitParams(
                stop_loss_pct=0.015,
                take_profit_pct=0.04,
            ),
            risk_params=RiskParams(
                position_size_pct=0.08,
                max_positions=2,
            ),
            supported_symbols=['BTCUSDT', 'ETHUSDT'],
            description='基于交易压力事件的反转策略 V2',
        ),
        'funding_extreme_reversal_v2': StrategyConfigV2(
            strategy_id='funding_extreme_reversal_v2',
            strategy_name='资金费率极端反转策略 V2',
            strategy_type=StrategyType.BEHAVIORAL,
            is_active=True,
            entry_params=EntryParams(
                signal_threshold=0.6,
                max_entries_per_symbol=1,
            ),
            exit_params=ExitParams(
                stop_loss_pct=0.02,
                take_profit_pct=0.06,
            ),
            risk_params=RiskParams(
                position_size_pct=0.07,
                max_positions=2,
            ),
            supported_symbols=['BTCUSDT', 'ETHUSDT'],
            description='基于资金费率极端值的反转策略 V2',
        ),
        'liquidation_cascade_v2': StrategyConfigV2(
            strategy_id='liquidation_cascade_v2',
            strategy_name='爆仓连锁策略 V2',
            strategy_type=StrategyType.EVENT_DRIVEN,
            is_active=True,
            entry_params=EntryParams(
                signal_threshold=0.7,
                max_entries_per_symbol=1,
            ),
            exit_params=ExitParams(
                stop_loss_pct=0.025,
                take_profit_pct=0.08,
            ),
            risk_params=RiskParams(
                position_size_pct=0.12,
                max_positions=1,
            ),
            supported_symbols=['BTCUSDT', 'ETHUSDT'],
            description='基于爆仓事件的连锁策略 V2',
        ),
        'momentum_ignition_v2': StrategyConfigV2(
            strategy_id='momentum_ignition_v2',
            strategy_name='动量点火策略 V2',
            strategy_type=StrategyType.TREND,
            is_active=True,
            entry_params=EntryParams(
                signal_threshold=0.65,
                max_entries_per_symbol=1,
            ),
            exit_params=ExitParams(
                stop_loss_pct=0.015,
                take_profit_pct=0.06,
            ),
            risk_params=RiskParams(
                position_size_pct=0.08,
                max_positions=2,
            ),
            supported_symbols=['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
            description='高质量低频：成交量急放 + 趋势确认 V2',
        ),
    }


# 导出
__all__ = [
    'OpenInterestBehaviorV2',
    'TradePressureExhaustionV2',
    'FundingExtremeReversalV2',
    'LiquidationCascadeV2',
    'MomentumIgnitionV2',
    'create_v2_configs',
]
