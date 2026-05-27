"""
MarketContext Builder - 从 raw features 构建结构化上下文

核心职责：
1. 接收 raw features
2. 按时间周期分组
3. 验证 features 是否有泄漏（通过 ContextLeakageGuard）
4. 构建各个分层上下文
5. 返回完整的 MarketContext

数据流：
raw data -> features_by_tf -> MarketContextBuilder -> MarketContext

防泄漏规则：
- 所有 feature 输出必须包含 _meta
- as_of 必须 <= ctx_timestamp
- close_only 模式下 bar 必须已关闭
- 禁止使用未来信息字段名

特征获取规则：
- 必需特征使用 require_feature()，缺失时报错
- 可选特征使用 features.get()
"""

from typing import Dict, Any, Optional

from .schema import (
    MarketContext,
    TimeframeContext,
    PriceState,
    TrendStateData,
    MomentumState,
    VolatilityStateData,
    VolumeStateData,
    FlowState,
    LiquidityStateData,
    DerivativesContext,
    OIData,
    FundingData,
    LiquidationData,
    CrossMarketData,
    RiskContext,
    STANDARD_TIMEFRAMES,
    TrendState,
    MomentumDirection,
    VolatilityState,
    VolumeState,
    FlowPressure,
    LiquidityState,
    FundingBias,
)
from .leakage_guard import ContextLeakageGuard, LeakageGuardMode, create_guard


class MissingFeatureError(Exception):
    """必需特征缺失错误"""
    pass


def require_feature(features: Dict[str, Any], name: str, context_hint: str = "") -> Any:
    """
    要求特征必须存在
    
    Args:
        features: 特征字典
        name: 特征名称
        context_hint: 上下文提示信息（用于错误消息）
        
    Returns:
        特征值
        
    Raises:
        MissingFeatureError: 特征不存在
    """
    if name not in features:
        hint = f" (context: {context_hint})" if context_hint else ""
        raise MissingFeatureError(f"Required feature '{name}' missing{hint}")
    return features[name]


class MarketContextBuilder:
    """
    将 raw features 转换为结构化的 MarketContext
    
    强制规则：
    1. 所有 feature 必须包含 _meta
    2. build() 第一行执行 leakage_guard.validate()
    3. 禁止跳过验证
    4. 必需特征使用 require_feature()
    """
    
    def __init__(
        self,
        symbol: str,
        leakage_guard: Optional[ContextLeakageGuard] = None,
    ):
        self.symbol = symbol
        self.leakage_guard = leakage_guard or create_guard(mode=LeakageGuardMode.CLOSE_ONLY)
    
    def build(
        self,
        features_by_tf: Dict[str, Dict[str, Any]],
        timestamp: int,
    ) -> MarketContext:
        """
        构建完整的 MarketContext
        
        强制流程：
        1. 调用 leakage_guard.validate() - 第一行
        2. 构建时间周期上下文
        3. 构建跨周期上下文
        
        Args:
            features_by_tf: 按时间周期分组的特征，如 {"1m": {"close": 42000, ...}, ...}
            timestamp: 毫秒时间戳
            
        Returns:
            完整的 MarketContext
            
        Raises:
            FutureLeakageError: 如果检测到未来信息泄漏
            MissingFeatureError: 如果必需特征缺失
        """
        # Step 1: 防泄漏验证（第一行，禁止跳过！）
        self.leakage_guard.validate(features_by_tf, timestamp)
        
        # Step 2: 构建时间周期上下文
        tf_contexts: Dict[str, TimeframeContext] = {}
        for tf in STANDARD_TIMEFRAMES:
            features = features_by_tf.get(tf, {})
            tf_contexts[tf] = self._build_timeframe_context(tf, features)
        
        # Step 3: 构建跨周期上下文
        derivatives = self._build_derivatives_context(features_by_tf)
        cross_market = self._build_cross_market_context(features_by_tf)
        risk = self._build_risk_context(features_by_tf, tf_contexts)
        
        return MarketContext(
            symbol=self.symbol,
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            cross_market=cross_market,
            risk=risk,
        )
    
    def _build_timeframe_context(
        self,
        timeframe: str,
        features: Dict[str, Any],
    ) -> TimeframeContext:
        """构建单个时间周期的上下文"""
        return TimeframeContext(
            timeframe=timeframe,
            price=self._build_price_state(features, timeframe),
            trend=self._build_trend_state(features, timeframe),
            momentum=self._build_momentum_state(features, timeframe),
            volatility=self._build_volatility_state(features, timeframe),
            volume=self._build_volume_state(features, timeframe),
            flow=self._build_flow_state(features, timeframe),
            liquidity=self._build_liquidity_state(features, timeframe),
        )
    
    def _build_price_state(self, features: Dict[str, Any], timeframe: str) -> PriceState:
        """构建价格状态"""
        ctx = f"tf.{timeframe}.price"
        return PriceState(
            open=require_feature(features, "open", ctx),
            high=require_feature(features, "high", ctx),
            low=require_feature(features, "low", ctx),
            close=require_feature(features, "close", ctx),
            return_1h=features.get("return_1h", 0.0),
            return_24h=features.get("return_24h", 0.0),
            change=features.get("change", 0.0),
            change_percent=features.get("change_percent", 0.0),
            closes=tuple(features.get("closes", [])),
            highs=tuple(features.get("highs", [])),
            lows=tuple(features.get("lows", [])),
            support=features.get("support"),
            resistance=features.get("resistance"),
        )
    
    def _build_trend_state(self, features: Dict[str, Any], timeframe: str) -> TrendStateData:
        """构建趋势状态"""
        ctx = f"tf.{timeframe}.trend"
        ema_20 = require_feature(features, "ema_20", ctx)
        ema_50 = require_feature(features, "ema_50", ctx)
        close = require_feature(features, "close", ctx)
        
        if ema_20 > ema_50:
            if close > ema_20 * 1.005:
                state = TrendState.STRONG_UP
            else:
                state = TrendState.WEAK_UP
        elif ema_20 < ema_50:
            if close < ema_20 * 0.995:
                state = TrendState.STRONG_DOWN
            else:
                state = TrendState.WEAK_DOWN
        else:
            state = TrendState.SIDEWAYS
        
        return TrendStateData(
            state=state,
            ema_20=ema_20,
            ema_50=ema_50,
            slope=features.get("slope", 0.0),
            structure=features.get("structure", "unknown"),
            strength=features.get("strength", 0.0),
        )
    
    def _build_momentum_state(self, features: Dict[str, Any], timeframe: str) -> MomentumState:
        """构建动量状态"""
        ctx = f"tf.{timeframe}.momentum"
        rsi_14 = require_feature(features, "rsi_14", ctx)
        macd = require_feature(features, "macd", ctx)
        macd_signal = require_feature(features, "macd_signal", ctx)
        
        score = 0.0
        if rsi_14 > 50:
            score = (rsi_14 - 50) / 50
        else:
            score = (rsi_14 - 50) / 50
        
        if macd > macd_signal:
            score += 0.3
        else:
            score -= 0.3
        
        score = max(-1.0, min(1.0, score))
        
        if score > 0.2:
            direction = MomentumDirection.BUY
        elif score < -0.2:
            direction = MomentumDirection.SELL
        else:
            direction = MomentumDirection.NEUTRAL
        
        return MomentumState(
            direction=direction,
            score=score,
            rsi=rsi_14,
            macd=macd,
            macd_signal=macd_signal,
        )
    
    def _build_volatility_state(self, features: Dict[str, Any], timeframe: str) -> VolatilityStateData:
        """构建波动率状态"""
        atr_pct = features.get("atr_pct", 0.0)
        realized_vol_zscore = features.get("realized_vol_zscore", 0.0)
        
        if realized_vol_zscore > 2.0 or atr_pct > 3.0:
            state = VolatilityState.EXTREME
        elif realized_vol_zscore > 1.0 or atr_pct > 1.5:
            state = VolatilityState.ELEVATED
        elif realized_vol_zscore < -1.0 or atr_pct < 0.5:
            state = VolatilityState.LOW
        else:
            state = VolatilityState.NORMAL
        
        return VolatilityStateData(
            state=state,
            atr=features.get("atr", 0.0),
            atr_pct=atr_pct,
            bb_width=features.get("bb_width", 0.0),
            bb_width_pct=features.get("bb_width_pct", 0.0),
            realized_vol=features.get("realized_vol", 0.0),
            realized_vol_zscore=realized_vol_zscore,
        )
    
    def _build_volume_state(self, features: Dict[str, Any], timeframe: str) -> VolumeStateData:
        """构建成交量状态"""
        ctx = f"tf.{timeframe}.volume"
        volume = require_feature(features, "volume", ctx)
        
        volume_zscore = features.get("volume_zscore", 0.0)
        
        if volume_zscore > 2.0:
            state = VolumeState.CLIMAX
        elif volume_zscore < -1.0:
            state = VolumeState.DRY
        else:
            state = VolumeState.NORMAL
        
        return VolumeStateData(
            state=state,
            volume=volume,
            volume_ma=features.get("volume_ma", 0.0),
            volume_zscore=volume_zscore,
            volume_ratio=features.get("volume_ratio", 1.0),
        )
    
    def _build_flow_state(self, features: Dict[str, Any], timeframe: str) -> FlowState:
        """构建资金流状态"""
        ctx = f"tf.{timeframe}.flow"
        aggressive_buy_volume = require_feature(features, "aggressive_buy_volume", ctx)
        aggressive_sell_volume = require_feature(features, "aggressive_sell_volume", ctx)
        
        cvd_slope = features.get("cvd_slope", 0.0)
        
        total = aggressive_buy_volume + aggressive_sell_volume
        if total > 0:
            score = (aggressive_buy_volume - aggressive_sell_volume) / total
        else:
            score = 0.0
        
        score += cvd_slope * 0.5
        score = max(-1.0, min(1.0, score))
        
        if score > 0.2:
            pressure = FlowPressure.BUY
        elif score < -0.2:
            pressure = FlowPressure.SELL
        else:
            pressure = FlowPressure.NEUTRAL
        
        return FlowState(
            pressure=pressure,
            score=score,
            cvd=features.get("cvd", 0.0),
            cvd_slope=cvd_slope,
            cumulative_delta=features.get("cumulative_delta", 0.0),
            aggressive_buy=aggressive_buy_volume,
            aggressive_sell=aggressive_sell_volume,
            aggressive_ratio=features.get("aggressive_ratio", 1.0),
            whale_buy_count=features.get("whale_buy_count", 0),
            whale_sell_count=features.get("whale_sell_count", 0),
            whale_buy_volume=features.get("whale_buy_volume", 0.0),
            whale_sell_volume=features.get("whale_sell_volume", 0.0),
            imbalance_5=features.get("imbalance_5", 0.0),
        )
    
    def _build_liquidity_state(self, features: Dict[str, Any], timeframe: str) -> LiquidityStateData:
        """构建流动性状态"""
        ctx = f"tf.{timeframe}.liquidity"
        spread_bps = require_feature(features, "spread_bps", ctx)
        
        vacuum_score = features.get("vacuum_score", 0.0)
        is_vacuum = features.get("is_vacuum", False)
        
        if is_vacuum or vacuum_score > 0.7:
            state = LiquidityState.VACUUM
        elif spread_bps > 5 or features.get("depth_ratio", 1.0) < 0.5:
            state = LiquidityState.THIN
        elif features.get("depth_ratio", 1.0) > 2.0:
            state = LiquidityState.FLOODED
        else:
            state = LiquidityState.NORMAL
        
        return LiquidityStateData(
            state=state,
            spread=features.get("spread", 0.0),
            spread_bps=spread_bps,
            depth_ratio=features.get("depth_ratio", 1.0),
            top5_bid_depth=features.get("top5_bid_depth", 0.0),
            top5_ask_depth=features.get("top5_ask_depth", 0.0),
            microprice=features.get("microprice", 0.0),
            is_vacuum=is_vacuum,
            vacuum_score=vacuum_score,
            cancel_rate=features.get("cancel_rate", 0.0),
        )
    
    def _build_derivatives_context(
        self,
        features_by_tf: Dict[str, Dict[str, Any]],
    ) -> DerivativesContext:
        """构建衍生品上下文（取最新特征）"""
        all_features: Dict[str, Any] = {}
        for tf_features in features_by_tf.values():
            all_features.update(tf_features)
        
        ctx = "derivatives.oi"
        oi = require_feature(all_features, "oi", ctx)
        
        oi_zscore = all_features.get("oi_zscore", 0.0)
        oi_trend = "neutral"
        if oi_zscore > 1.0:
            oi_trend = "rising"
        elif oi_zscore < -1.0:
            oi_trend = "falling"
        elif abs(oi_zscore) > 2.0:
            oi_trend = "spike"
        
        oi_data = OIData(
            value=oi,
            delta=all_features.get("oi_delta", 0.0),
            zscore=oi_zscore,
            history=tuple(all_features.get("oi_history", [])),
            trend=oi_trend,
        )
        
        ctx = "derivatives.funding"
        funding_rate = require_feature(all_features, "funding_rate", ctx)
        
        funding_zscore = all_features.get("funding_zscore", 0.0)
        if funding_zscore > 2.0:
            funding_bias = FundingBias.EXTREME_POSITIVE
        elif funding_zscore > 0.5:
            funding_bias = FundingBias.POSITIVE
        elif funding_zscore < -2.0:
            funding_bias = FundingBias.EXTREME_NEGATIVE
        elif funding_zscore < -0.5:
            funding_bias = FundingBias.NEGATIVE
        else:
            funding_bias = FundingBias.NEUTRAL
        
        funding_data = FundingData(
            rate=funding_rate,
            zscore=funding_zscore,
            bias=funding_bias,
            history=tuple(all_features.get("funding_history", [])),
        )
        
        liquidation_data = LiquidationData(
            long=all_features.get("liquidation_long", 0.0),
            short=all_features.get("liquidation_short", 0.0),
            total=all_features.get("liquidation_total", 0.0),
            long_zscore=all_features.get("liquidation_long_zscore", 0.0),
            short_zscore=all_features.get("liquidation_short_zscore", 0.0),
            reversal_signal=all_features.get("liquidation_reversal_signal", False),
        )
        
        return DerivativesContext(
            oi=oi_data,
            funding=funding_data,
            liquidation=liquidation_data,
        )
    
    def _build_cross_market_context(
        self,
        features_by_tf: Dict[str, Dict[str, Any]],
    ) -> CrossMarketData:
        """构建跨市场上下文"""
        all_features: Dict[str, Any] = {}
        for tf_features in features_by_tf.values():
            all_features.update(tf_features)
        
        returns = {
            "binance": all_features.get("binance_return", 0.0),
            "okx": all_features.get("okx_return", 0.0),
            "bybit": all_features.get("bybit_return", 0.0),
        }
        
        lead_exchange = max(returns, key=returns.get, default="")
        lag_exchange = min(returns, key=returns.get, default="")
        
        return CrossMarketData(
            binance_return=all_features.get("binance_return", 0.0),
            okx_return=all_features.get("okx_return", 0.0),
            bybit_return=all_features.get("bybit_return", 0.0),
            basis=all_features.get("basis", 0.0),
            premium=all_features.get("premium", 0.0),
            spread=all_features.get("spread", 0.0),
            lead_exchange=lead_exchange,
            lag_exchange=lag_exchange,
            lead_lag_score=all_features.get("lead_lag_score", 0.0),
        )
    
    def _build_risk_context(
        self,
        features_by_tf: Dict[str, Dict[str, Any]],
        tf_contexts: Dict[str, TimeframeContext],
    ) -> RiskContext:
        """构建风险上下文（由 4h 周期决定）"""
        h4 = tf_contexts.get("4h")
        
        high_volatility = False
        low_liquidity = False
        extreme_move = False
        regime_change = False
        multiplier = 1.0
        
        if h4:
            if h4.volatility.state in [VolatilityState.ELEVATED, VolatilityState.EXTREME]:
                high_volatility = True
            
            if h4.liquidity.state in [LiquidityState.THIN, LiquidityState.VACUUM]:
                low_liquidity = True
            
            if h4.price.change_percent > 5:
                extreme_move = True
            
            if h4.trend.state == TrendState.SIDEWAYS:
                regime_change = True
            
            if high_volatility or low_liquidity:
                multiplier = 0.7
            elif extreme_move:
                multiplier = 0.5
            elif regime_change:
                multiplier = 0.8
        
        return RiskContext(
            high_volatility=high_volatility,
            low_liquidity=low_liquidity,
            news_event=features_by_tf.get("1h", {}).get("news_event", False),
            overtrading=False,
            drawdown_exceeded=False,
            slippage_warning=False,
            execution_paused=False,
            regime_change=regime_change,
            extreme_move=extreme_move,
            multiplier=multiplier,
        )


__all__ = [
    "MarketContextBuilder",
    "MissingFeatureError",
    "require_feature",
]
