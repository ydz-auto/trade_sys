"""
Market State Machine
市场状态机

提供事件驱动的市场状态转换引擎。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from domain.market_state.state import (
    RegimeType,
    LiquidityState,
    PressureState,
    VolatilityState,
    TrendState,
    MarketState,
)
from domain.event.event_type import EventType

logger = logging.getLogger(__name__)


@dataclass
class MarketStateMachine:
    """
    市场状态机
    
    核心职责：
    - 维护当前市场状态
    - 通过事件驱动状态转换
    - 保持状态历史用于回放
    - 提供状态查询接口
    """
    symbol: str
    
    # 当前状态
    current_state: MarketState = field(init=False)
    
    # 状态历史（用于回放和验证）
    history: List[MarketState] = field(default_factory=list, init=False)
    
    # 配置
    max_history: int = 1000
    
    # 内部计数器
    _state_version: int = field(default=1, init=False)
    
    def __post_init__(self):
        # 初始化状态
        self.current_state = self._initial_state()
        self.history.append(self.current_state)
    
    def _initial_state(self) -> MarketState:
        """创建初始状态"""
        now = datetime.utcnow()
        return MarketState(
            timestamp=now,
            symbol=self.symbol,
            regime=RegimeType.QUIET,
            liquidity=LiquidityState.NORMAL,
            pressure=PressureState.NEUTRAL,
            volatility=VolatilityState.NORMAL,
            trend=TrendState.SIDEWAYS,
            confidence=0.5,
            version=1,
        )
    
    def update(
        self,
        event_type: EventType,
        features: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> MarketState:
        """
        基于事件和特征更新市场状态
        
        Args:
            event_type: 触发状态更新的事件类型
            features: 当前特征快照
            timestamp: 时间戳（默认当前时间）
        
        Returns:
            更新后的 MarketState
        """
        timestamp = timestamp or datetime.utcnow()
        
        # 计算新状态
        new_state = self._compute_new_state(
            old_state=self.current_state,
            event_type=event_type,
            features=features,
            timestamp=timestamp,
        )
        
        # 更新当前状态
        self.current_state = new_state
        self._state_version += 1
        
        # 添加到历史
        self.history.append(new_state)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        logger.debug(
            f"Market state updated for {self.symbol}: "
            f"regime={new_state.regime.value}, "
            f"pressure={new_state.pressure.value}, "
            f"confidence={new_state.confidence:.2f}"
        )
        
        return new_state
    
    def _compute_new_state(
        self,
        old_state: MarketState,
        event_type: EventType,
        features: Dict[str, float],
        timestamp: datetime,
    ) -> MarketState:
        """
        计算新的市场状态
        
        根据当前事件和特征，决定每个维度的新状态。
        """
        # 1. 更新压力状态（基于 Trade Pressure 事件）
        pressure = self._update_pressure(old_state.pressure, event_type, features)
        
        # 2. 更新流动性状态
        liquidity = self._update_liquidity(old_state.liquidity, event_type, features)
        
        # 3. 更新波动率状态
        volatility = self._update_volatility(old_state.volatility, features)
        
        # 4. 更新趋势状态
        trend = self._update_trend(old_state.trend, features)
        
        # 5. 确定整体市场状态（基于多个维度）
        regime = self._determine_regime(pressure, liquidity, volatility, trend, features)
        
        # 6. 计算信心度
        confidence = self._calculate_confidence(event_type, features)
        
        # 7. 确定 OI 和资金费率状态
        oi_regime = self._determine_oi_regime(features)
        funding_regime = self._determine_funding_regime(features)
        
        return MarketState(
            timestamp=timestamp,
            symbol=self.symbol,
            regime=regime,
            liquidity=liquidity,
            pressure=pressure,
            volatility=volatility,
            trend=trend,
            confidence=confidence,
            last_major_event=event_type.value,
            feature_snapshot=features.copy(),
            oi_regime=oi_regime,
            funding_regime=funding_regime,
            version=self._state_version,
        )
    
    def _update_pressure(
        self,
        current: PressureState,
        event_type: EventType,
        features: Dict[str, float],
    ) -> PressureState:
        """更新压力状态"""
        # 基于事件类型快速转换
        if event_type == EventType.TRADE_PRESSURE_FLUSH:
            return PressureState.FLUSHED
        elif event_type == EventType.TRADE_PRESSURE_EXHAUSTION:
            return PressureState.EXHAUSTED
        elif event_type == EventType.TRADE_PRESSURE_ABSORPTION:
            return PressureState.ABSORBED
        elif event_type == EventType.TRADE_PRESSURE_DIVERGENCE:
            return PressureState.DIVERGENCE
        elif event_type == EventType.TRADE_PRESSURE_SQUEEZE:
            return PressureState.BUILDUP
        elif event_type == EventType.TRADE_PRESSURE_BUILDUP:
            return PressureState.BUILDUP
        
        # 基于特征的平滑过渡
        pressure_zscore = features.get("pressure_zscore", 0.0)
        
        if pressure_zscore > 2.0:
            return PressureState.BUILDUP
        elif pressure_zscore < -2.0:
            return PressureState.FLUSHED
        elif abs(pressure_zscore) < 0.5:
            return PressureState.NEUTRAL
        
        return current
    
    def _update_liquidity(
        self,
        current: LiquidityState,
        event_type: EventType,
        features: Dict[str, float],
    ) -> LiquidityState:
        """更新流动性状态"""
        if event_type == EventType.LIQUIDITY_VACUUM:
            return LiquidityState.VACUUM
        elif event_type == EventType.LIQUIDITY_FLOOD:
            return LiquidityState.FLOODED
        
        # 基于特征
        liquidity_ratio = features.get("liquidity_ratio", 1.0)
        spread_zscore = features.get("spread_zscore", 0.0)
        
        if liquidity_ratio < 0.3:
            return LiquidityState.VACUUM
        elif liquidity_ratio < 0.5:
            return LiquidityState.THIN
        elif liquidity_ratio > 2.0:
            return LiquidityState.FLOODED
        
        return current
    
    def _update_volatility(
        self,
        current: VolatilityState,
        features: Dict[str, float],
    ) -> VolatilityState:
        """更新波动率状态"""
        vol_zscore = features.get("volatility_zscore", 0.0)
        
        if vol_zscore > 3.0:
            return VolatilityState.EXTREME
        elif vol_zscore > 1.5:
            return VolatilityState.ELEVATED
        elif vol_zscore < -1.0:
            return VolatilityState.LOW
        
        return VolatilityState.NORMAL
    
    def _update_trend(
        self,
        current: TrendState,
        features: Dict[str, float],
    ) -> TrendState:
        """更新趋势状态"""
        trend_strength = features.get("trend_strength", 0.0)
        
        if trend_strength > 0.6:
            return TrendState.STRONG_UP
        elif trend_strength > 0.2:
            return TrendState.WEAK_UP
        elif trend_strength < -0.6:
            return TrendState.STRONG_DOWN
        elif trend_strength < -0.2:
            return TrendState.WEAK_DOWN
        
        return TrendState.SIDEWAYS
    
    def _determine_regime(
        self,
        pressure: PressureState,
        liquidity: LiquidityState,
        volatility: VolatilityState,
        trend: TrendState,
        features: Dict[str, float],
    ) -> RegimeType:
        """确定整体市场状态"""
        # 基于多维度组合的规则
        
        # Squeeze 状态特征：压力积聚 + 流动性真空 + 高波动率
        if (
            pressure == PressureState.BUILDUP
            and liquidity == LiquidityState.VACUUM
            and volatility != VolatilityState.LOW
        ):
            return RegimeType.SQUEEZE
        
        # Crash 状态：极端波动率 + 压力释放 + 强下跌趋势
        if (
            volatility == VolatilityState.EXTREME
            and pressure == PressureState.FLUSHED
            and trend in [TrendState.STRONG_DOWN, TrendState.WEAK_DOWN]
        ):
            return RegimeType.CRASH
        
        # 趋势状态
        if trend in [TrendState.STRONG_UP, TrendState.WEAK_UP]:
            return RegimeType.TRENDING_UP
        if trend in [TrendState.STRONG_DOWN, TrendState.WEAK_DOWN]:
            return RegimeType.TRENDING_DOWN
        
        # 均值回归状态
        if (
            pressure in [PressureState.EXHAUSTED, PressureState.ABSORBED]
            and volatility != VolatilityState.EXTREME
        ):
            return RegimeType.MEAN_REVERTING
        
        # 安静状态
        if volatility == VolatilityState.LOW and trend == TrendState.SIDEWAYS:
            return RegimeType.QUIET
        
        return RegimeType.MEAN_REVERTING
    
    def _calculate_confidence(
        self,
        event_type: EventType,
        features: Dict[str, float],
    ) -> float:
        """计算状态转换的信心度"""
        base_confidence = 0.5
        
        # 事件类型提升信心
        high_confidence_events = [
            EventType.TRADE_PRESSURE_FLUSH,
            EventType.TRADE_PRESSURE_EXHAUSTION,
            EventType.LIQUIDITY_VACUUM,
            EventType.MARKET_STRUCTURE_LIQUIDATION,
        ]
        if event_type in high_confidence_events:
            base_confidence += 0.3
        
        # 特征强度提升信心
        for feat_name, feat_val in features.items():
            if "zscore" in feat_name:
                base_confidence += min(0.2, abs(feat_val) * 0.1)
        
        return min(1.0, base_confidence)
    
    def _determine_oi_regime(self, features: Dict[str, float]) -> str:
        """确定持仓量状态"""
        oi_zscore = features.get("oi_zscore", 0.0)
        if oi_zscore > 2.0:
            return "rising"
        elif oi_zscore < -2.0:
            return "falling"
        return "neutral"
    
    def _determine_funding_regime(self, features: Dict[str, float]) -> str:
        """确定资金费率状态"""
        funding_rate = features.get("funding_rate", 0.0)
        if funding_rate > 0.001:
            return "extreme_positive"
        elif funding_rate < -0.001:
            return "extreme_negative"
        return "normal"
    
    def get_state_at(self, index: int = -1) -> Optional[MarketState]:
        """
        获取历史状态
        
        Args:
            index: 索引，-1 表示最新状态
        
        Returns:
            MarketState 或 None
        """
        if not self.history:
            return None
        try:
            return self.history[index]
        except IndexError:
            return None
    
    def get_history(
        self,
        limit: Optional[int] = None,
    ) -> List[MarketState]:
        """
        获取状态历史
        
        Args:
            limit: 返回的最大数量
        
        Returns:
            MarketState 列表
        """
        if limit is None:
            return self.history.copy()
        return self.history[-limit:]
    
    def reset(self) -> None:
        """重置状态机到初始状态"""
        self.current_state = self._initial_state()
        self.history = [self.current_state]
        self._state_version = 1
        logger.info(f"MarketStateMachine reset for {self.symbol}")
