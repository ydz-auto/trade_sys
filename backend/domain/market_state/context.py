"""
MarketContext - 统一市场上下文（固定 schema）

按照用户定义的固定结构：
- symbol + timestamp
- tfs: 时间周期上下文（1m/5m/15m/1h/4h）
- 各域上下文：regime, price, volatility, liquidity, flow, derivatives, cross_market
- risk_flags: 风险标志

核心原则：
1. 固定 schema，不是大 dict
2. 策略只读，不能修改
3. features 作为生产原料，Context 作为消费产品
4. 周期设计：4h/1h 过滤，15m 出信号，5m 确认，1m 执行
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from domain.market_state.layers import (
    TimeframeContext,
    RegimeContext,
    PriceContext,
    VolatilityContext,
    LiquidityContext,
    FlowContext,
    DerivativesContext,
    CrossMarketContext,
    RiskFlags,
)

import logging

logger = logging.getLogger(__name__)


# ============== 固定周期定义 ==============

STANDARD_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"]


@dataclass(frozen=True)
class MarketContext:
    """
    统一市场上下文（固定 schema）
    
    策略只能读这个，不能自己解释市场
    """
    # 基础信息
    symbol: str
    timestamp: int  # 毫秒时间戳
    
    # 时间周期上下文（核心）
    tfs: Dict[str, TimeframeContext] = field(default_factory=dict)
    
    # 各域上下文
    regime: RegimeContext = field(default_factory=RegimeContext)
    price: PriceContext = field(default_factory=PriceContext)
    volatility: VolatilityContext = field(default_factory=VolatilityContext)
    liquidity: LiquidityContext = field(default_factory=LiquidityContext)
    flow: FlowContext = field(default_factory=FlowContext)
    derivatives: DerivativesContext = field(default_factory=DerivativesContext)
    cross_market: CrossMarketContext = field(default_factory=CrossMarketContext)
    
    # 风险标志
    risk_flags: RiskFlags = field(default_factory=RiskFlags)
    
    # ============== 周期访问快捷方法 ==============
    
    def tf(self, timeframe: str) -> TimeframeContext:
        """快捷访问时间周期上下文"""
        return self.tfs.get(timeframe, TimeframeContext(timeframe=timeframe))
    
    def tf_1m(self) -> TimeframeContext:
        return self.tf("1m")
    
    def tf_5m(self) -> TimeframeContext:
        return self.tf("5m")
    
    def tf_15m(self) -> TimeframeContext:
        return self.tf("15m")
    
    def tf_1h(self) -> TimeframeContext:
        return self.tf("1h")
    
    def tf_4h(self) -> TimeframeContext:
        return self.tf("4h")
    
    # ============== 语义化快捷方法 ==============
    
    def is_exhausted(self) -> bool:
        """是否处于压力耗尽状态（基于各周期综合判断）"""
        tf_15m = self.tf_15m()
        tf_5m = self.tf_5m()
        return (tf_15m.volume_state.name == "CLIMAX" and 
                tf_5m.flow_pressure.name in ["BUY", "SELL"] and 
                abs(tf_5m.flow_score) > 0.8)
    
    def is_liquid_vacuum(self) -> bool:
        """是否处于流动性真空"""
        return self.tf_1m().liquidity_vacuum or self.liquidity.is_vacuum
    
    def is_high_confidence_trend(self) -> bool:
        """是否有高置信度趋势"""
        return self.regime.confidence > 0.75 and self.regime.state in ("trending_up", "trending_down")
    
    def is_flush(self) -> bool:
        """是否刚经历流动性 flush"""
        tf_1m = self.tf_1m()
        return tf_1m.liquidity_state.name == "VACUUM" and tf_1m.sweep_score > 0.8
    
    def is_squeeze(self) -> bool:
        """是否处于挤压状态"""
        return self.regime.state == "squeeze"
    
    def is_quiet(self) -> bool:
        """是否处于低波动安静状态"""
        return self.regime.state == "quiet"
    
    def get_trend_strength(self) -> float:
        """获取趋势强度（0-1）"""
        tf_1h = self.tf_1h()
        tf_4h = self.tf_4h()
        return (tf_1h.momentum_score + tf_4h.momentum_score) / 2
    
    def get_liquidity_quality(self) -> float:
        """获取流动性质量（0-1）"""
        liquidity_score = {
            "NORMAL": 1.0,
            "THIN": 0.6,
            "VACUUM": 0.3,
        }
        return liquidity_score.get(self.liquidity.state.name, 0.5)
    
    # ============== 置信度计算（按照用户定义的周期规则）==============
    
    def calculate_signal_confidence(
        self,
        base_confidence: float,
        primary_timeframe: str = "15m",
    ) -> float:
        """
        计算最终信号置信度
        
        规则：大周期定方向，中周期给信号，小周期找入场
        final_confidence = base * regime_multiplier_4h * trend_filter_1h * trigger_confirmation_5m * execution_quality_1m
        """
        # 4h 大方向过滤
        tf_4h = self.tf_4h()
        regime_multiplier = 1.0
        if tf_4h.trend_state.name == "DOWN":
            regime_multiplier = 0.5  # 4h bearish 时打折
        
        # 1h 趋势过滤
        tf_1h = self.tf_1h()
        trend_filter = 1.0
        if tf_1h.trend_state.name == "RANGE":
            trend_filter = 0.8  # 1h range 时稍微降低
        
        # 5m 确认
        tf_5m = self.tf_5m()
        trigger_confirmation = 1.0
        if primary_timeframe == "15m":
            if tf_5m.flow_pressure.name == "NEUTRAL":
                trigger_confirmation = 0.7  # 没有 5m 确认，降低置信度
            else:
                trigger_confirmation = 1.2  # 有 5m 确认，提升置信度
        
        # 1m 执行质量
        tf_1m = self.tf_1m()
        execution_quality = 1.0
        if tf_1m.liquidity_state.name == "VACUUM":
            execution_quality = 0.6  # 流动性真空，执行质量低
        
        # 综合计算
        final_confidence = base_confidence * regime_multiplier * trend_filter * trigger_confirmation * execution_quality
        
        # 限制在 0-1 范围内
        return max(0.0, min(1.0, final_confidence))
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化（用于回放/存储）"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "tfs": {k: v.__dict__ for k, v in self.tfs.items()},
            "regime": self.regime.__dict__,
            "price": self.price.__dict__,
            "volatility": self.volatility.__dict__,
            "liquidity": self.liquidity.__dict__,
            "flow": self.flow.__dict__,
            "derivatives": self.derivatives.__dict__,
            "cross_market": self.cross_market.__dict__,
            "risk_flags": self.risk_flags.__dict__,
        }


class MarketContextAuthority:
    """
    市场上下文权威层
    
    职责：
    1. 唯一负责更新 MarketContext
    2. 从 features 生成结构化 Context
    3. 确保所有 runtime 对齐
    4. 禁止绕过该层直接访问状态
    """
    
    def __init__(self, symbol: str):
        self._symbol = symbol
        self._current_context: Optional[MarketContext] = None
        self._context_history: list[MarketContext] = []
        self._max_history = 1000
    
    def update(
        self,
        features: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> MarketContext:
        """
        更新市场上下文（唯一入口）
        
        从 features 生成结构化的 MarketContext
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # 创建时间周期上下文
        tfs = self._build_timeframe_contexts(features)
        
        # 创建各域上下文
        regime = self._build_regime_context(features)
        price = self._build_price_context(features)
        volatility = self._build_volatility_context(features)
        liquidity = self._build_liquidity_context(features)
        flow = self._build_flow_context(features)
        derivatives = self._build_derivatives_context(features)
        cross_market = self._build_cross_market_context(features)
        risk_flags = self._build_risk_flags(features)
        
        # 构建完整上下文
        context = MarketContext(
            symbol=self._symbol,
            timestamp=int(timestamp.timestamp() * 1000),
            tfs=tfs,
            regime=regime,
            price=price,
            volatility=volatility,
            liquidity=liquidity,
            flow=flow,
            derivatives=derivatives,
            cross_market=cross_market,
            risk_flags=risk_flags,
        )
        
        # 保存历史
        self._current_context = context
        self._context_history.append(context)
        if len(self._context_history) > self._max_history:
            self._context_history.pop(0)
        
        logger.debug(f"MarketContext updated at {timestamp}")
        return context
    
    def _build_timeframe_contexts(self, features: Dict[str, Any]) -> Dict[str, TimeframeContext]:
        """从 features 构建各时间周期上下文"""
        tfs = {}
        
        for tf in STANDARD_TIMEFRAMES:
            tf_prefix = f"{tf}_"
            tf_features = {k.replace(tf_prefix, ""): v for k, v in features.items() if k.startswith(tf_prefix)}
            
            tfs[tf] = TimeframeContext(
                timeframe=tf,
                # 从 features 映射，这里简化处理
                momentum_score=tf_features.get("momentum_score", 0.0),
                volatility_value=tf_features.get("volatility", 0.0),
                volume_ratio=tf_features.get("volume_ratio", 1.0),
                flow_score=tf_features.get("flow_score", 0.0),
                spread=tf_features.get("spread", 0.0),
                microprice=tf_features.get("microprice", 0.0),
                sweep_score=tf_features.get("sweep_score", 0.0),
                liquidity_vacuum=tf_features.get("liquidity_vacuum", False),
                cvd_value=tf_features.get("cvd", 0.0),
                technical={k: v for k, v in tf_features.items() if k.startswith("rsi") or k.startswith("macd") or k.startswith("sma") or k.startswith("ema") or k.startswith("bb_")},
            )
        
        return tfs
    
    def _build_regime_context(self, features: Dict[str, Any]) -> RegimeContext:
        return RegimeContext(
            state=features.get("regime", "unknown"),
            confidence=features.get("regime_confidence", 0.0),
            duration=features.get("regime_duration", 0),
            strength=features.get("regime_strength", 0.0),
        )
    
    def _build_price_context(self, features: Dict[str, Any]) -> PriceContext:
        return PriceContext(
            close=features.get("close", 0.0),
            high=features.get("high", 0.0),
            low=features.get("low", 0.0),
            open=features.get("open", 0.0),
            return_1h=features.get("return_1h", 0.0),
            return_4h=features.get("return_4h", 0.0),
            return_24h=features.get("return_24h", 0.0),
            price_change=features.get("price_change", 0.0),
            price_change_percent=features.get("price_change_percent", 0.0),
        )
    
    def _build_volatility_context(self, features: Dict[str, Any]) -> VolatilityContext:
        return VolatilityContext(
            current=features.get("volatility", 0.0),
            historical=features.get("historical_volatility", 0.0),
            implied=features.get("implied_volatility", None),
            realized_vol_ratio=features.get("realized_vol_ratio", 1.0),
            implied_vol_ratio=features.get("implied_vol_ratio", 1.0),
        )
    
    def _build_liquidity_context(self, features: Dict[str, Any]) -> LiquidityContext:
        return LiquidityContext(
            top_bid=features.get("top_bid", 0.0),
            top_ask=features.get("top_ask", 0.0),
            spread=features.get("spread", 0.0),
            spread_ratio=features.get("spread_ratio", 0.0),
            top5_bid_depth=features.get("top5_bid_depth", 0.0),
            top5_ask_depth=features.get("top5_ask_depth", 0.0),
            depth_ratio=features.get("depth_ratio", 0.0),
            microprice=features.get("microprice", 0.0),
            cancel_rate=features.get("cancel_rate", 0.0),
            is_vacuum=features.get("liquidity_vacuum", False),
            vacuum_score=features.get("vacuum_score", 0.0),
        )
    
    def _build_flow_context(self, features: Dict[str, Any]) -> FlowContext:
        return FlowContext(
            trade_delta=features.get("trade_delta", 0.0),
            cumulative_delta=features.get("cumulative_delta", 0.0),
            aggressive_buy_volume=features.get("aggressive_buy_volume", 0.0),
            aggressive_sell_volume=features.get("aggressive_sell_volume", 0.0),
            cvd=features.get("cvd", 0.0),
            whale_buy_count=features.get("whale_buy_count", 0),
            whale_sell_count=features.get("whale_sell_count", 0),
            whale_buy_volume=features.get("whale_buy_volume", 0.0),
            whale_sell_volume=features.get("whale_sell_volume", 0.0),
            aggressive_flow=features.get("aggressive_flow", 0.0),
            sweep_score=features.get("sweep_score", 0.0),
            imbalance_5=features.get("imbalance_5", 0.0),
        )
    
    def _build_derivatives_context(self, features: Dict[str, Any]) -> DerivativesContext:
        return DerivativesContext(
            oi=features.get("oi", 0.0),
            oi_delta=features.get("oi_delta", 0.0),
            oi_zscore=features.get("oi_zscore", 0.0),
            funding_rate=features.get("funding_rate", 0.0),
            funding_zscore=features.get("funding_zscore", 0.0),
            oi_funding_divergence=features.get("oi_funding_divergence", 0.0),
            funding_extreme_reversal=features.get("funding_extreme_reversal", False),
            funding_extreme_side=features.get("funding_extreme_side", "none"),
            liquidation_long=features.get("liquidation_long", 0.0),
            liquidation_short=features.get("liquidation_short", 0.0),
            liquidation_total=features.get("liquidation_total", 0.0),
            liquidation_reversal_signal=features.get("liquidation_reversal_signal", False),
        )
    
    def _build_cross_market_context(self, features: Dict[str, Any]) -> CrossMarketContext:
        return CrossMarketContext(
            binance_return=features.get("binance_return", 0.0),
            okx_return=features.get("okx_return", 0.0),
            bybit_return=features.get("bybit_return", 0.0),
            basis=features.get("basis", 0.0),
            premium=features.get("premium", 0.0),
            spread=features.get("cross_market_spread", 0.0),
            lead_exchange=features.get("lead_exchange", ""),
            lead_lag_score=features.get("lead_lag_score", 0.0),
        )
    
    def _build_risk_flags(self, features: Dict[str, Any]) -> RiskFlags:
        return RiskFlags(
            high_volatility=features.get("high_volatility", False),
            low_liquidity=features.get("low_liquidity", False),
            news_event=features.get("news_event", False),
            overtrading=features.get("overtrading", False),
            drawdown_exceeded=features.get("drawdown_exceeded", False),
            slippage_warning=features.get("slippage_warning", False),
            execution_paused=features.get("execution_paused", False),
            regime_change=features.get("regime_change", False),
            extreme_move=features.get("extreme_move", False),
        )
    
    def get_current_context(self) -> Optional[MarketContext]:
        return self._current_context
    
    def get_context_history(self, limit: int = 100) -> list[MarketContext]:
        return self._context_history[-limit:]
    
    def clear_history(self):
        self._context_history = []
        self._current_context = None


# ============== 导出接口 ==============

__all__ = [
    "STANDARD_TIMEFRAMES",
    "MarketContext",
    "MarketContextAuthority",
]
