"""
Market Context Builder - 市场上下文构建器

统一组装 MarketContext，整合所有时间周期的特征。
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

from engines.compute.context import MarketContext, TimeframeContext, PriceState
from engines.compute.context import TrendStateData, VolatilityStateData, VolumeStateData
from engines.compute.context import FlowState, LiquidityStateData, DerivativesContext
from engines.compute.context import OIData, FundingData, LiquidationData, RiskContext
from engines.compute.context import TrendState, VolatilityState, VolumeState, FlowPressure, LiquidityState, FundingBias

from features.feature_engine import FeatureEngine


class MarketContextBuilder:
    """
    MarketContext 构建器
    
    职责：
    - 整合多时间周期特征
    - 组装 MarketContext
    - 填充所有必需字段
    
    不包含：
    - 特征计算（委托给 FeatureEngine）
    - 数据获取（委托给 Repository）
    """
    
    def __init__(self, feature_engine: FeatureEngine):
        self.feature_engine = feature_engine
    
    async def build(
        self,
        symbol: str,
        primary_tf: str,
        confirm_tfs: List[str],
        execution_tf: str,
        start_ts: int,
        end_ts: int,
    ) -> MarketContext:
        """
        构建 MarketContext
        
        Args:
            symbol: 交易对
            primary_tf: 主时间周期
            confirm_tfs: 确认时间周期列表
            execution_tf: 执行时间周期
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            MarketContext: 完整的市场上下文
        """
        timeframes = list(set([primary_tf, execution_tf] + confirm_tfs))
        
        features_by_tf = {}
        
        for tf in timeframes:
            features_by_tf[tf] = await self.feature_engine.compute_ohlcv_features(
                symbol=symbol,
                timeframe=tf,
                start_ts=start_ts,
                end_ts=end_ts,
            )
        
        derivatives_features = await self.feature_engine.compute_derivatives_features(
            symbol=symbol,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        
        tf_contexts = {}
        
        for tf, df in features_by_tf.items():
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                tf_contexts[tf] = self._build_timeframe_context(tf, df, latest)
        
        derivatives = self._build_derivatives_context(derivatives_features)
        
        return MarketContext(
            symbol=symbol,
            timestamp=end_ts,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )
    
    async def build_from_features(
        self,
        symbol: str,
        timestamp: int,
        features_by_tf: Dict[str, pd.DataFrame],
        derivatives_features: Optional[pd.DataFrame] = None,
    ) -> MarketContext:
        """
        从已计算的特征构建 MarketContext
        
        Args:
            symbol: 交易对
            timestamp: 时间戳
            features_by_tf: 各时间周期的特征数据
            derivatives_features: 衍生品特征
        
        Returns:
            MarketContext: 市场上下文
        """
        tf_contexts = {}
        
        for tf, df in features_by_tf.items():
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                tf_contexts[tf] = self._build_timeframe_context(tf, df, latest)
        
        derivatives = self._build_derivatives_context(derivatives_features) if derivatives_features is not None else None
        
        return MarketContext(
            symbol=symbol,
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )
    
    def _build_timeframe_context(
        self,
        tf: str,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> TimeframeContext:
        """构建单个时间周期的上下文"""
        
        close = float(latest.get("close", 0))
        open_price = float(latest.get("open", close))
        high = float(latest.get("high", close))
        low = float(latest.get("low", close))
        
        change_percent = float(latest.get("ret", 0)) * 100
        
        price_state = PriceState(
            open=open_price,
            high=high,
            low=low,
            close=close,
            change_percent=change_percent,
        )
        
        trend_state = self._classify_trend(df, latest)
        trend_data = TrendStateData(
            state=trend_state,
            slope=float(latest.get("ret", 0)),
            strength=abs(float(latest.get("price_vs_sma20", 0))) if "price_vs_sma20" in latest else 0.5,
        )
        
        volatility = self._classify_volatility(df, latest)
        volatility_data = VolatilityStateData(
            state=volatility,
            atr_pct=float(latest.get("atr_pct", 0.01)),
        )
        
        volume_state = self._classify_volume(df, latest)
        volume_data = VolumeStateData(
            state=volume_state,
            volume_zscore=float(latest.get("volume_zscore", 0)),
        )
        
        flow_pressure = self._classify_flow(df, latest)
        flow_data = FlowState(
            pressure=flow_pressure,
            score=float(latest.get("buy_ratio", 0.5)) if "buy_ratio" in latest else 0.5,
            cvd=float(latest.get("cvd", 0)) if "cvd" in latest else 0,
            cvd_slope=0.0,
            aggressive_ratio=float(latest.get("buy_ratio", 0.5)) if "buy_ratio" in latest else 0.5,
        )
        
        return TimeframeContext(
            timeframe=tf,
            price=price_state,
            trend=trend_data,
            volatility=volatility_data,
            volume=volume_data,
            flow=flow_data,
        )
    
    def _build_derivatives_context(
        self,
        df: Optional[pd.DataFrame],
    ) -> DerivativesContext:
        """构建衍生品上下文"""
        if df is None or df.empty:
            return DerivativesContext()
        
        latest = df.iloc[-1] if len(df) > 0 else {}
        
        oi_data = None
        if "open_interest" in latest:
            oi_data = OIData(
                value=float(latest.get("open_interest", 0)),
                delta=float(latest.get("oi_change", 0)),
                zscore=float(latest.get("oi_zscore", 0)),
            )
        
        funding_data = None
        if "funding_rate" in latest:
            funding_rate = float(latest.get("funding_rate", 0))
            funding_zscore = float(latest.get("funding_zscore", 0))
            
            if funding_zscore > 2:
                bias = FundingBias.EXTREME_POSITIVE
            elif funding_zscore > 0.5:
                bias = FundingBias.POSITIVE
            elif funding_zscore < -2:
                bias = FundingBias.EXTREME_NEGATIVE
            elif funding_zscore < -0.5:
                bias = FundingBias.NEGATIVE
            else:
                bias = FundingBias.NEUTRAL
            
            funding_data = FundingData(
                rate=funding_rate,
                zscore=funding_zscore,
                bias=bias,
            )
        
        liq_data = None
        if "total_liquidation" in latest:
            liq_data = LiquidationData(
                long=0,
                short=0,
                total=float(latest.get("total_liquidation", 0)),
                long_zscore=0,
                short_zscore=0,
                reversal_signal=False,
            )
        
        return DerivativesContext(
            oi=oi_data,
            funding=funding_data,
            liquidation=liq_data,
        )
    
    def _classify_trend(self, df: pd.DataFrame, latest: pd.Series) -> TrendState:
        """分类趋势状态"""
        if "price_vs_sma20" in latest and "price_vs_sma50" in latest:
            sma20_diff = float(latest["price_vs_sma20"])
            sma50_diff = float(latest["price_vs_sma50"])
            
            if sma20_diff > 0.02 and sma50_diff > 0.02:
                return TrendState.STRONG_UP
            elif sma20_diff > 0 and sma50_diff > 0:
                return TrendState.WEAK_UP
            elif sma20_diff < -0.02 and sma50_diff < -0.02:
                return TrendState.STRONG_DOWN
            elif sma20_diff < 0 and sma50_diff < 0:
                return TrendState.WEAK_DOWN
            else:
                return TrendState.SIDEWAYS
        
        return TrendState.SIDEWAYS
    
    def _classify_volatility(self, df: pd.DataFrame, latest: pd.Series) -> VolatilityState:
        """分类波动率状态"""
        if "volatility_zscore" in latest:
            zscore = float(latest["volatility_zscore"])
            if zscore > 2:
                return VolatilityState.EXTREME
            elif zscore > 1:
                return VolatilityState.ELEVATED
            elif zscore < -1:
                return VolatilityState.LOW
        
        atr_pct = float(latest.get("atr_pct", 0.01))
        if atr_pct > 0.03:
            return VolatilityState.ELEVATED
        elif atr_pct < 0.01:
            return VolatilityState.LOW
        
        return VolatilityState.NORMAL
    
    def _classify_volume(self, df: pd.DataFrame, latest: pd.Series) -> VolumeState:
        """分类成交量状态"""
        if "volume_zscore" in latest:
            zscore = float(latest["volume_zscore"])
            if zscore > 3:
                return VolumeState.CLIMAX
            elif zscore < -2:
                return VolumeState.DRY
        
        return VolumeState.NORMAL
    
    def _classify_flow(self, df: pd.DataFrame, latest: pd.Series) -> FlowPressure:
        """分类资金流向"""
        if "buy_ratio" in latest:
            ratio = float(latest["buy_ratio"])
            if ratio > 0.65:
                return FlowPressure.BUY
            elif ratio < 0.35:
                return FlowPressure.SELL
        
        return FlowPressure.NEUTRAL


__all__ = [
    "MarketContextBuilder",
]
