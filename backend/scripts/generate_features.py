#!/usr/bin/env python3
"""
数据归一化与特征生成流水线

功能：
1. 读取原始Parquet (K线, Funding, OI)
2. 归一化到统一Schema
3. 合并多源数据
4. 计算特征
5. 输出特征Parquet
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import numpy as np
from tqdm import tqdm


class UnifiedMarketData:
    """统一市场数据结构"""
    
    def __init__(self, data_root: Optional[Path] = None):
        if data_root is None:
            data_root = Path(__file__).parent.parent / "data_lake"
        self.data_root = Path(data_root)
    
    def _load_klines(self, exchange: str, symbol: str) -> pd.DataFrame:
        """加载所有K线数据（合并Spot和Futures）"""
        dfs = []
        
        spot_klines_dir = self.data_root / "crypto" / exchange / "spot_klines" / f"symbol={symbol}"
        futures_klines_dir = self.data_root / "crypto" / exchange / "klines" / f"symbol={symbol}"
        
        for klines_dir, market in [(spot_klines_dir, "spot"), (futures_klines_dir, "futures")]:
            if not klines_dir.exists():
                continue
            
            for year_dir in klines_dir.iterdir():
                if not year_dir.is_dir() or not year_dir.name.startswith("year="):
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir() or not month_dir.name.startswith("month="):
                        continue
                    
                    parquet_path = month_dir / "data.parquet"
                    csv_files = list(month_dir.glob("*.csv"))
                    
                    if parquet_path.exists():
                        df = pd.read_parquet(parquet_path)
                        dfs.append(df)
                    elif csv_files:
                        for csv_file in csv_files:
                            try:
                                df = pd.read_csv(csv_file, header=None)
                                if len(df.columns) >= 11:
                                    df.columns = [
                                        "open_time", "open", "high", "low", "close", "volume",
                                        "close_time", "quote_volume", "trades", "taker_buy_base",
                                        "taker_buy_quote", "ignore"
                                    ][:len(df.columns)]
                                    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
                                    df["exchange"] = exchange
                                    df["symbol"] = symbol
                                    df["interval"] = "1m"
                                    df = df[["timestamp", "exchange", "symbol", "interval",
                                            "open", "high", "low", "close", "volume"]]
                                    dfs.append(df)
                            except Exception as e:
                                print(f"读取CSV失败 {csv_file}: {e}")
        
        if not dfs:
            return pd.DataFrame()
        
        result = pd.concat(dfs, ignore_index=True)
        result = result.drop_duplicates(subset=["timestamp"], keep="last")
        result = result.sort_values("timestamp").reset_index(drop=True)
        
        return result
    
    def _load_funding(self, exchange: str, symbol: str) -> pd.DataFrame:
        """加载Funding数据"""
        funding_dir = self.data_root / "crypto" / exchange / "funding" / f"symbol={symbol}"
        parquet_path = funding_dir / "data.parquet"
        
        if not parquet_path.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(parquet_path)
        
        if "fundingRate" in df.columns:
            df["funding_rate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
        
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    
    def _load_oi(self, exchange: str, symbol: str) -> pd.DataFrame:
        """加载Open Interest数据"""
        oi_dir = self.data_root / "crypto" / exchange / "oi" / f"symbol={symbol}"
        parquet_path = oi_dir / "data.parquet"
        
        if not parquet_path.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(parquet_path)
        
        if "sumOpenInterest" in df.columns:
            df["open_interest"] = pd.to_numeric(df["sumOpenInterest"], errors="coerce")
        if "sumOpenInterestValue" in df.columns:
            df["open_interest_value"] = pd.to_numeric(df["sumOpenInterestValue"], errors="coerce")
        
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    
    def merge_data(
        self,
        exchange: str,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        合并所有数据源
        
        策略：
        1. K线作为主数据（每1分钟一条）
        2. Funding是每8小时一条，前向填充
        3. OI是每5分钟一条，前向填充
        """
        print(f"合并 {exchange}/{symbol} 数据...")
        
        klines_df = self._load_klines(exchange, symbol)
        if klines_df.empty:
            print(f"没有K线数据: {exchange}/{symbol}")
            return pd.DataFrame()
        
        klines_df = klines_df.sort_values("timestamp").reset_index(drop=True)
        
        funding_df = self._load_funding(exchange, symbol)
        oi_df = self._load_oi(exchange, symbol)
        
        result = klines_df[["timestamp", "exchange", "symbol", "interval", 
                           "open", "high", "low", "close", "volume"]].copy()
        
        result["funding_rate"] = np.nan
        result["open_interest"] = np.nan
        result["open_interest_value"] = np.nan
        
        if not funding_df.empty and "funding_rate" in funding_df.columns:
            try:
                funding_df = funding_df.set_index("timestamp").sort_index()
                result = result.set_index("timestamp")
                result["funding_rate"] = funding_df["funding_rate"].reindex(result.index, method="ffill")
                result = result.reset_index()
            except Exception as e:
                print(f"填充Funding失败: {e}")
        
        if not oi_df.empty and "open_interest" in oi_df.columns:
            try:
                oi_df = oi_df.set_index("timestamp").sort_index()
                result = result.set_index("timestamp")
                result["open_interest"] = oi_df["open_interest"].reindex(result.index, method="ffill")
                if "open_interest_value" in oi_df.columns:
                    result["open_interest_value"] = oi_df["open_interest_value"].reindex(result.index, method="ffill")
                result = result.reset_index()
            except Exception as e:
                print(f"填充OI失败: {e}")
        
        if start_date:
            result = result[result["timestamp"] >= pd.Timestamp(start_date)]
        if end_date:
            result = result[result["timestamp"] <= pd.Timestamp(end_date)]
        
        result = result.sort_values("timestamp").reset_index(drop=True)
        
        print(f"合并完成: {len(result)} 条记录")
        
        return result


class FeatureMaterializer:
    """特征物化器 - 预计算并保存特征"""
    
    def __init__(self, data_root: Optional[Path] = None):
        if data_root is None:
            data_root = Path(__file__).parent.parent / "data_lake"
        self.data_root = Path(data_root)
        self.feature_dir = self.data_root / "features"
        self.feature_dir.mkdir(parents=True, exist_ok=True)
        
        self.unified_loader = UnifiedMarketData(data_root)
    
    def _enrich_data_for_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """为特征计算准备数据格式"""
        df = df.copy()
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        return df
    
    def compute_features_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """批量计算特征"""
        
        df = self._enrich_data_for_features(df)
        result_df = df.copy()
        
        prices = df["close"].values
        volumes = df["volume"].values
        timestamps = df["timestamp"].values
        
        # ========== 1. Returns ==========
        result_df["returns_1m"] = np.zeros(len(df))
        result_df["returns_1m"][1:] = (prices[1:] - prices[:-1]) / prices[:-1]
        
        result_df["returns_5m"] = np.zeros(len(df))
        result_df["returns_5m"][5:] = (prices[5:] - prices[:-5]) / prices[:-5]
        
        result_df["returns_1h"] = np.zeros(len(df))
        result_df["returns_1h"][60:] = (prices[60:] - prices[:-60]) / prices[:-60]
        
        # ========== 2. Volatility ==========
        window = 60
        rolling_returns = result_df["returns_1m"].rolling(window)
        result_df["volatility_1h"] = rolling_returns.std()
        
        window = 120
        rolling_returns = result_df["returns_1m"].rolling(window)
        result_df["realized_vol_2h"] = rolling_returns.std()
        
        # ========== 3. RSI ==========
        period = 14
        
        deltas = np.diff(prices)
        deltas = np.concatenate([[np.nan], deltas])
        
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        
        avg_gain = pd.Series(gains).rolling(window=period).mean().values
        avg_loss = pd.Series(losses).rolling(window=period).mean().values
        
        with np.errstate(divide="ignore"):
            rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss)
        
        rsi = 100.0 - (100.0 / (1.0 + rs))
        result_df["rsi_14"] = rsi
        
        # ========== 4. MACD ==========
        def ema(series, period):
            return series.ewm(span=period, adjust=False).mean()
        
        close_series = pd.Series(prices)
        ema12 = ema(close_series, 12)
        ema26 = ema(close_series, 26)
        
        macd_line = ema12 - ema26
        signal_line = ema(macd_line, 9)
        histogram = macd_line - signal_line
        
        result_df["macd"] = macd_line.values
        result_df["macd_signal"] = signal_line.values
        result_df["macd_hist"] = histogram.values
        
        # ========== 5. Bollinger Bands ==========
        period_bb = 20
        sma = close_series.rolling(window=period_bb).mean()
        std = close_series.rolling(window=period_bb).std()
        
        bb_upper = sma + 2 * std
        bb_middle = sma
        bb_lower = sma - 2 * std
        
        bb_position = (prices - bb_lower) / (bb_upper - bb_lower)
        bb_position = np.where(bb_upper == bb_lower, 0.5, bb_position)
        
        result_df["bb_upper"] = bb_upper.values
        result_df["bb_middle"] = bb_middle.values
        result_df["bb_lower"] = bb_lower.values
        result_df["bb_position"] = bb_position
        
        # ========== 6. Volume Features ==========
        volume_series = pd.Series(volumes)
        volume_ma20 = volume_series.rolling(window=20).mean()
        
        result_df["volume_ma20"] = volume_ma20.values
        result_df["volume_ratio"] = volumes / volume_ma20.values
        
        # ========== 7. Funding Features ==========
        if "funding_rate" in df.columns:
            result_df["funding_rate"] = df["funding_rate"]
            
            funding_series = pd.Series(df["funding_rate"].values)
            result_df["funding_ma8h"] = funding_series.rolling(window=48).mean().values
            result_df["funding_delta"] = result_df["funding_rate"] - result_df["funding_ma8h"]
            
            funding_std = funding_series.rolling(window=288).std()
            result_df["funding_zscore"] = (result_df["funding_rate"] - result_df["funding_ma8h"]) / funding_std
        
        # ========== 8. Open Interest Features ==========
        if "open_interest" in df.columns:
            result_df["open_interest"] = df["open_interest"]
            
            oi_series = pd.Series(df["open_interest"].values)
            oi_ma60 = oi_series.rolling(window=60).mean()
            
            result_df["oi_ma60"] = oi_ma60.values
            result_df["oi_delta"] = result_df["open_interest"] - result_df["oi_ma60"]
            result_df["oi_change_1h"] = oi_series.pct_change(60).values
        
        print(f"特征计算完成: {len(result_df)} 条, {len(result_df.columns)} 列")
        
        return result_df
    
    def process_symbol(self, exchange: str, symbol: str):
        """处理单个交易对"""
        print(f"========== 处理 {exchange}/{symbol} ==========")
        
        merged_df = self.unified_loader.merge_data(exchange, symbol)
        if merged_df.empty:
            print(f"没有数据可处理")
            return
        
        feature_df = self.compute_features_batch(merged_df)
        
        output_dir = self.feature_dir / exchange / symbol
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / "features.parquet"
        feature_df.to_parquet(output_path, compression="zstd", index=False)
        
        print(f"特征保存到: {output_path}")
        print(f"统计: {len(feature_df)} 行, {len(feature_df.columns)} 列")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="特征生成流水线")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--exchange", default="binance")
    
    args = parser.parse_args()
    
    print("="*60)
    print("数据归一化与特征生成流水线")
    print(f"交易所: {args.exchange}")
    print(f"交易对: {args.symbols}")
    print("="*60)
    
    materializer = FeatureMaterializer()
    
    for symbol in args.symbols:
        materializer.process_symbol(args.exchange, symbol)
    
    print("\n✅ 全部完成！")


if __name__ == "__main__":
    main()
