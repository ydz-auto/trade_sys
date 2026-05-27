"""
Feature Engine - 特征计算引擎

只负责特征计算，不关心数据来源和存储。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from datalake.market_repository import MarketDataRepository


class FeatureEngine:
    """
    特征计算引擎
    
    职责：
    - 特征计算
    - 技术指标
    - 微结构特征
    
    不包含：
    - 数据获取（委托给 Repository）
    - 上下文组装（委托给 MarketContextBuilder）
    """
    
    def __init__(self, market_repo: MarketDataRepository):
        self.market_repo = market_repo
    
    async def compute_ohlcv_features(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        lookback: int = 100,
    ) -> pd.DataFrame:
        """
        计算 OHLCV 基础特征
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_ts: 开始时间戳
            end_ts: 结束时间戳
            lookback: 回看窗口
        
        Returns:
            pd.DataFrame: 带特征的 K 线数据
        """
        df = await self.market_repo.get_klines(symbol, timeframe, start_ts, end_ts)
        
        if df.empty or len(df) < lookback:
            return df
        
        df = df.sort_values("ts").reset_index(drop=True)
        
        df["ret"] = df["close"].pct_change()
        df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
        
        df["range"] = (df["high"] - df["low"]) / df["close"]
        df["body"] = abs(df["close"] - df["open"]) / df["close"]
        df["upper_wick"] = (df["high"] - df[["close", "open"]].max(axis=1)) / df["close"]
        df["lower_wick"] = (df[["close", "open"]].min(axis=1) - df["low"]) / df["close"]
        
        rolling = df["volume"].rolling(lookback)
        df["volume_ma"] = rolling.mean()
        df["volume_std"] = rolling.std()
        df["volume_zscore"] = (df["volume"] - df["volume_ma"]) / df["volume_std"]
        
        return df
    
    async def compute_trend_features(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        计算趋势特征
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 带趋势特征的数据
        """
        df = await self.market_repo.get_klines(symbol, timeframe, start_ts, end_ts)
        
        if df.empty:
            return df
        
        df = df.sort_values("ts").reset_index(drop=True)
        
        for period in [20, 50, 100, 200]:
            if len(df) >= period:
                df[f"sma_{period}"] = df["close"].rolling(period).mean()
                df[f"ema_{period}"] = df["close"].ewm(span=period).mean()
        
        df["price_vs_sma20"] = df["close"] / df["sma_20"] - 1
        df["price_vs_sma50"] = df["close"] / df["sma_50"] - 1
        
        short_ema = df["close"].ewm(span=12).mean()
        long_ema = df["close"].ewm(span=26).mean()
        df["macd"] = short_ema - long_ema
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        
        return df
    
    async def compute_volatility_features(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        period: int = 20,
    ) -> pd.DataFrame:
        """
        计算波动率特征
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_ts: 开始时间戳
            end_ts: 结束时间戳
            period: 计算周期
        
        Returns:
            pd.DataFrame: 带波动率特征的数据
        """
        df = await self.market_repo.get_klines(symbol, timeframe, start_ts, end_ts)
        
        if df.empty or len(df) < period:
            return df
        
        df = df.sort_values("ts").reset_index(drop=True)
        
        df["ret"] = df["close"].pct_change()
        df["atr"] = self._calculate_atr(df, period)
        df["atr_pct"] = df["atr"] / df["close"]
        
        rolling_ret = df["ret"].rolling(period)
        df["volatility"] = rolling_ret.std() * np.sqrt(365 * 24)
        df["realized_vol"] = rolling_ret.apply(lambda x: np.sqrt(np.sum(x**2)) * np.sqrt(365 * 24), raw=False)
        
        df["volatility_zscore"] = (df["volatility"] - df["volatility"].rolling(100).mean()) / df["volatility"].rolling(100).std()
        
        return df
    
    async def compute_flow_features(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        计算资金流向特征
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 带资金流向特征的数据
        """
        trades_df = await self.market_repo.get_trades(symbol, start_ts, end_ts, limit=50000)
        
        if trades_df.empty:
            return pd.DataFrame()
        
        trades_df = trades_df.sort_values("ts").reset_index(drop=True)
        
        trades_df["buy_volume"] = trades_df.apply(
            lambda x: x["size"] if x.get("side") == "buy" else 0, axis=1
        )
        trades_df["sell_volume"] = trades_df.apply(
            lambda x: x["size"] if x.get("side") == "sell" else 0, axis=1
        )
        
        trades_df["buy_ratio"] = (
            trades_df["buy_volume"].rolling(100) / 
            (trades_df["buy_volume"].rolling(100) + trades_df["sell_volume"].rolling(100))
        )
        
        trades_df["cvd"] = (trades_df["buy_volume"] - trades_df["sell_volume"]).cumsum()
        
        return trades_df
    
    async def compute_derivatives_features(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        计算衍生品特征
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 带衍生品特征的数据
        """
        oi_df = await self.market_repo.get_open_interest(symbol, start_ts, end_ts)
        funding_df = await self.market_repo.get_funding_rates(symbol, start_ts, end_ts)
        liq_df = await self.market_repo.get_liquidations(symbol, start_ts, end_ts)
        
        result = pd.DataFrame()
        
        if not oi_df.empty:
            oi_df = oi_df.sort_values("ts").reset_index(drop=True)
            oi_df["oi_change"] = oi_df["open_interest"].pct_change()
            oi_df["oi_zscore"] = (
                (oi_df["open_interest"] - oi_df["open_interest"].rolling(100).mean()) / 
                oi_df["open_interest"].rolling(100).std()
            )
            result = oi_df
        
        if not funding_df.empty:
            funding_df = funding_df.sort_values("ts").reset_index(drop=True)
            funding_df["funding_zscore"] = (
                (funding_df["funding_rate"] - funding_df["funding_rate"].rolling(100).mean()) / 
                funding_df["funding_rate"].rolling(100).std()
            )
            if result.empty:
                result = funding_df
            else:
                result = result.merge(funding_df[["ts", "funding_rate", "funding_zscore"]], on="ts", how="outer")
        
        if not liq_df.empty:
            liq_df = liq_df.sort_values("ts").reset_index(drop=True)
            liq_agg = liq_df.groupby("ts").agg({
                "size": "sum",
            }).reset_index()
            liq_agg.columns = ["ts", "total_liquidation"]
            
            if result.empty:
                result = liq_agg
            else:
                result = result.merge(liq_agg, on="ts", how="outer")
        
        return result
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 ATR"""
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr


__all__ = [
    "FeatureEngine",
]
