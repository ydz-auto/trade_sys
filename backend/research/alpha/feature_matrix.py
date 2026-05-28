"""
Feature Matrix - 特征矩阵构建
包含两个版本：
1. 尝试使用真实统一特征矩阵系统（domain.feature 层）
2. 回退到从FileDataLakeReader手动构建
"""

import sys
from pathlib import Path
from typing import Optional, List, Any

import pandas as pd
import numpy as np

from infrastructure.acceleration.gpu_matrix_ops import GPUMatrixOps
from infrastructure.acceleration.memory_optimizer import MemoryOptimizer

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_feature_matrix(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
    exclude_sources: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    构建特征矩阵

    Args:
        symbol: 交易对
        exchange: 交易所
        days: 回看天数
        timeframe: K线周期

    Returns:
        特征矩阵 DataFrame
    """
    # 先尝试真实特征矩阵系统
    try:
        from domain.feature.feature_matrix import get_historical_feature_matrix
        from engines.compute.feature.historical_materializer import HistoricalFeatureMaterializer

        end_ts = int(pd.Timestamp.now().timestamp() * 1000)
        start_ts = int((pd.Timestamp.now() - pd.Timedelta(days=days)).timestamp() * 1000)
        interval_ms = _timeframe_to_ms(timeframe)

        data_lake = BACKEND_ROOT / "data_lake"
        materializer = HistoricalFeatureMaterializer(data_lake)

        matrix = materializer.materialize_symbol(
            symbol=symbol,
            interval_ms=interval_ms,
            start_ts=start_ts,
            end_ts=end_ts,
            force=False
        )

        if matrix is not None and len(matrix.timestamps) > 0:
            df = matrix.to_dataframe()
            print(f"  真实特征矩阵: {len(df.columns)}列 × {len(df)}行")
            return df

    except Exception as e:
        print(f"  真实特征矩阵系统不可用: {e}")

    # 回退到手动构建
    return _fallback_build(symbol, exchange, days, timeframe, exclude_sources)


def _fallback_build(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
    exclude_sources: Optional[List[str]] = None,
) -> pd.DataFrame:
    """回退方案：从FileDataLakeReader手动构建"""
    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

    exclude_sources = exclude_sources or []
    exclude_set = {s.lower().strip() for s in exclude_sources}

    reader = FileDataLakeReader()

    klines = _load_klines(reader, exchange, symbol, timeframe, days)
    
    klines_ts = pd.to_datetime(klines["timestamp"])
    klines_min = klines_ts.min()
    klines_max = klines_ts.max()
    
    funding = None
    if "funding" not in exclude_set:
        funding = _safe_load(reader, reader.load_funding, exchange, symbol)

    oi = None
    if "oi" not in exclude_set:
        oi = _safe_load(reader, reader.load_oi, exchange, symbol)

    trades = None
    is_materialized_trades = False
    if "trades" not in exclude_set:
        from infrastructure.storage.data_lake.trade_flow_writer import TradeFlowWriter
        tf_writer = TradeFlowWriter()
        trade_flow = tf_writer.load(exchange, symbol, timeframe)
        if trade_flow is not None and len(trade_flow) > 0:
            print(f"  Loaded materialized trade_flow: {len(trade_flow)} bars")
            trades = trade_flow
            is_materialized_trades = True
        else:
            print(f"  No materialized trade_flow, loading raw trades for {klines_min.date()} ~ {klines_max.date()}...")
            trades = reader.load_trades(exchange, symbol, start_ts=klines_min, end_ts=klines_max)

    if trades is not None and len(trades) > 0:
        trades["timestamp"] = pd.to_datetime(trades["timestamp"])
        trades_max = trades["timestamp"].max()
        trades_min = trades["timestamp"].min()
        klines_ts = pd.to_datetime(klines["timestamp"])
        klines_min = klines_ts.min()

        if trades_max < klines_min:
            print(f"  ⚠️ trades 数据 ({trades_max.date()}) 早于 klines ({klines_min.date()})")
            print(f"  调整 klines 时间范围到 trades 可用区间...")
            cutoff = trades_max - pd.Timedelta(days=days)
            klines_all = reader.load_klines(exchange, symbol, timeframe)
            if klines_all is not None and len(klines_all) > 0:
                klines_all["timestamp"] = pd.to_datetime(klines_all["timestamp"])
                klines = klines_all[
                    (klines_all["timestamp"] >= cutoff)
                    & (klines_all["timestamp"] <= trades_max)
                ].copy()
                if len(klines) > 0:
                    print(f"  使用 {klines['timestamp'].min().date()} ~ {klines['timestamp'].max().date()} 的 klines")
                else:
                    print(f"  klines 在 trades 时间范围内无数据，保留原始 klines")
                    klines = _load_klines(reader, exchange, symbol, timeframe, days)

            funding_ts_col = "funding_time" if "funding_time" in funding.columns else "timestamp" if funding is not None and len(funding) > 0 else None
            if funding is not None and len(funding) > 0 and funding_ts_col:
                funding["timestamp"] = pd.to_datetime(funding.get(funding_ts_col, funding.get("timestamp")))
                funding = funding[
                    (funding["timestamp"] >= cutoff) & (funding["timestamp"] <= trades_max)
                ].copy()
                if len(funding) == 0:
                    funding = None

            if oi is not None and len(oi) > 0:
                oi["timestamp"] = pd.to_datetime(oi["timestamp"])
                oi = oi[
                    (oi["timestamp"] >= cutoff) & (oi["timestamp"] <= trades_max)
                ].copy()
                if len(oi) == 0:
                    oi = None

    return build_feature_matrix_from_df(
        klines, funding, oi, trades, timeframe,
        is_materialized_trades=is_materialized_trades,
    )


def build_feature_matrix_from_df(
    klines: pd.DataFrame,
    funding: Optional[pd.DataFrame] = None,
    oi: Optional[pd.DataFrame] = None,
    trades: Optional[pd.DataFrame] = None,
    timeframe: str = "1h",
    is_materialized_trades: bool = False,
) -> pd.DataFrame:
    """从DataFrame手动构建特征矩阵"""

    df = klines[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["close"]

    # 基础收益
    df["ret_1"] = close.pct_change(1)
    df["ret_3"] = close.pct_change(3)
    df["ret_5"] = close.pct_change(5)
    df["ret_10"] = close.pct_change(10)
    df["ret_15"] = close.pct_change(15)
    df["ret_20"] = close.pct_change(20)
    df["ret_30"] = close.pct_change(30)
    df["ret_60"] = close.pct_change(60)
    df["change_pct"] = df["ret_1"]

    # 波动率
    bars_per_day = _timeframe_to_bars_per_day(timeframe)
    df["vol_20"] = df["ret_1"].rolling(20).std() * np.sqrt(bars_per_day * 252)
    df["vol_60"] = df["ret_1"].rolling(60).std() * np.sqrt(bars_per_day * 252)
    df["realized_vol"] = df["vol_60"]
    df["atr_14"] = (df["high"] - df["low"]).rolling(14).mean()
    df["atr"] = df["atr_14"]
    df["atr_pct"] = df["atr_14"] / close
    df["atr_expansion"] = df["atr_14"] / df["atr_14"].rolling(60).mean()

    # ZScore
    _gpu_ops = GPUMatrixOps()
    df["volatility_zscore"] = _gpu_ops.rolling_zscore(df["vol_20"].values.astype(np.float32), 100)
    df["realized_vol_zscore"] = df["volatility_zscore"]

    df["volume_zscore"] = _gpu_ops.rolling_zscore(df["volume"].values.astype(np.float32), 100)
    vol_ma = df["volume"].rolling(100).mean()
    df["volume_ma"] = vol_ma
    df["volume_ratio"] = df["volume"] / vol_ma

    # 趋势
    df["trend_20"] = (close - close.rolling(20).mean()) / close.rolling(20).mean()
    df["trend_60"] = (close - close.rolling(60).mean()) / close.rolling(60).mean()
    df["slope"] = df["trend_20"]

    # 回撤与结构
    df["drawdown_from_high"] = (close - close.rolling(60).max()) / close.rolling(60).max()
    df["distance_from_high"] = df["drawdown_from_high"]
    df["new_high_60"] = (close >= close.rolling(60).max()).astype(float)
    df["new_high_20"] = (close >= close.rolling(20).max()).astype(float)
    df["new_low_60"] = (close <= close.rolling(60).min()).astype(float)

    # 抛物线
    df["parabolic_ret_10"] = np.exp(np.log(1 + df["ret_1"]).rolling(10).sum()) - 1
    p_ma = df["parabolic_ret_10"].rolling(100).mean()
    p_std = df["parabolic_ret_10"].rolling(100).std()
    df["parabolic_ret_zscore"] = (df["parabolic_ret_10"] - p_ma) / p_std.replace(0, np.nan)

    # K线形态
    df["range_pct"] = (df["high"] - df["low"]) / df["low"].replace(0, np.nan)
    df["upper_wick_pct"] = (df["high"] - np.maximum(df["open"], close)) / df["low"].replace(0, np.nan)
    df["lower_wick_pct"] = (np.minimum(df["open"], close) - df["low"]) / df["low"].replace(0, np.nan)
    df["body_pct"] = (close - df["open"]) / df["low"].replace(0, np.nan)

    # 连续涨跌
    df["is_up"] = (close > df["open"]).astype(float)
    df["is_down"] = (close < df["open"]).astype(float)
    df["consecutive_green"] = df["is_up"].groupby((~df["is_up"].astype(bool)).cumsum()).cumsum()
    df["consecutive_red"] = df["is_down"].groupby((~df["is_down"].astype(bool)).cumsum()).cumsum()

    # 波动率spike
    df["volatility_spike"] = df["volatility_zscore"]

    # 大量下跌
    df["high_volume_decline"] = ((df["ret_1"] < 0) & (df["volume_zscore"] > 1.5)).astype(float)

    # 附加特征用于可用性审计
    df["return_1h"] = df["ret_60"] if timeframe == "1m" else df["ret_1"]

    # Funding
    if funding is not None and len(funding) > 0:
        df = _merge_funding(df, funding)
    else:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan

    df["funding_extreme_positive"] = (df["funding_zscore"] > 2).astype(float)

    # OI
    if oi is not None and len(oi) > 0:
        df = _merge_oi(df, oi)
    else:
        df["oi"] = np.nan
        df["oi_change_pct"] = np.nan
        df["oi_zscore"] = np.nan

    # Order Flow (Trades)
    if trades is not None and len(trades) > 0:
        if is_materialized_trades:
            df = _merge_materialized_trades(df, trades)
        else:
            df = _merge_trades(df, trades, timeframe)
    else:
        _add_nan_order_flow_cols(df)

    # GPU/CPU 加速技术指标
    df = _compute_tech_indicators(df)

    # Liquidity 估计特征（从 trades 合成）
    if trades is not None and len(trades) > 0 and not is_materialized_trades:
        df = _compute_liquidity_estimates(df, trades, timeframe)
    else:
        _add_nan_liquidity_cols(df)

    # OI-Funding 关联特征
    if oi is not None and len(oi) > 0 and funding is not None and len(funding) > 0:
        df = _compute_oi_funding_features(df)
    else:
        _add_nan_oi_funding_cols(df)

    # Regime 特征
    df = _compute_regime_features(df)

    # Event-driven 特征
    df = _compute_event_features(df)

    df = MemoryOptimizer.optimize_dtypes(df)

    return df


# ========== 辅助函数 ==========

def _load_klines(
    reader, exchange: str, symbol: str, timeframe: str, days: int
) -> pd.DataFrame:
    klines = reader.load_klines(exchange, symbol, timeframe=timeframe)

    if klines is None or len(klines) == 0:
        if timeframe != "1m":
            print(f"  {timeframe}数据不存在，从1m重采样...")
            klines_1m = reader.load_klines(exchange, symbol, timeframe="1m")
            if klines_1m is not None and len(klines_1m) > 0:
                klines = _resample_klines(klines_1m, timeframe)
            else:
                raise ValueError(f"没有1m数据作为fallback")
        else:
            raise ValueError(f"没有{timeframe} klines数据")

    klines["timestamp"] = pd.to_datetime(klines["timestamp"])
    cutoff = klines["timestamp"].max() - pd.Timedelta(days=days)
    klines = klines[klines["timestamp"] >= cutoff]

    return klines


def _safe_load(reader, load_fn, *args):
    try:
        df = load_fn(*args)
        if df is not None and len(df) > 0:
            df = df.copy()
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return None


def _merge_funding(df: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    df_ts = pd.to_datetime(df["timestamp"])
    fund_ts = pd.to_datetime(funding.get("funding_time", funding.get("timestamp", None)))

    if fund_ts is None:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        return df

    fund = pd.DataFrame({
        "ts": fund_ts,
        "rate": pd.to_numeric(funding.get("funding_rate", funding.get("fundingRate", np.nan)), errors="coerce")
    }).dropna()

    if len(fund) == 0:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        return df

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    fund_sorted = fund.sort_values("ts")

    merged = pd.merge_asof(
        df_sorted, fund_sorted, left_on="_ts", right_on="ts", direction="backward"
    )

    df["funding_rate"] = merged["rate"].values
    fr = df["funding_rate"]
    df["funding_zscore"] = (fr - fr.rolling(100).mean()) / fr.rolling(100).std().replace(0, np.nan)

    return df


def _merge_oi(df: pd.DataFrame, oi: pd.DataFrame) -> pd.DataFrame:
    df_ts = pd.to_datetime(df["timestamp"])

    if "timestamp" in oi.columns:
        oi_ts = pd.to_datetime(oi["timestamp"])
    else:
        oi_ts = pd.to_datetime(oi.get("open_interest_time", None))

    if oi_ts is None:
        df["oi"] = np.nan
        df["oi_change_pct"] = np.nan
        df["oi_zscore"] = np.nan
        return df

    oi_data = pd.DataFrame({
        "ts": oi_ts,
        "value": pd.to_numeric(oi.get("oi", oi.get("sumOpenInterest", oi.get("open_interest", np.nan))), errors="coerce")
    }).dropna()

    if len(oi_data) == 0:
        df["oi"] = np.nan
        df["oi_change_pct"] = np.nan
        df["oi_zscore"] = np.nan
        return df

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    oi_sorted = oi_data.sort_values("ts")

    merged = pd.merge_asof(
        df_sorted, oi_sorted, left_on="_ts", right_on="ts", direction="backward"
    )

    df["oi"] = merged["value"].values
    df["oi_change_pct"] = df["oi"].pct_change()
    oi_val = df["oi"]
    df["oi_zscore"] = (oi_val - oi_val.rolling(100).mean()) / oi_val.rolling(100).std().replace(0, np.nan)

    return df


ORDER_FLOW_COLUMNS = [
    "cvd", "cvd_slope", "cvd_delta", "cvd_zscore",
    "cumulative_delta",
    "aggressive_buy_volume", "aggressive_sell_volume",
    "aggressive_buy", "aggressive_sell",
    "aggressive_ratio", "taker_buy_ratio", "buy_sell_ratio",
    "trade_imbalance", "trade_delta",
    "trade_velocity", "large_trade_ratio", "large_trade_volume",
    "whale_buy_count", "whale_sell_count",
    "whale_buy_volume", "whale_sell_volume",
    "sweep_buy_score", "sweep_sell_score",
    "trade_pressure_score", "long_pressure_score", "short_pressure_score",
    "squeeze_pressure_score", "flush_pressure_score",
    "trade_price", "trade_volume",
]


def _add_nan_order_flow_cols(df: pd.DataFrame):
    for col in ORDER_FLOW_COLUMNS:
        df[col] = np.nan


def _merge_trades(
    df: pd.DataFrame, trades: pd.DataFrame, timeframe: str
) -> pd.DataFrame:
    """
    从 trades 逐笔数据提取 order_flow 特征，聚合到 K 线时间轴。

    策略：先按 K 线窗口向量化聚合 trades，再计算 order_flow 指标。
    避免逐行 iterrows，对 1.7 亿行 trades 使用 pandas groupby 向量化。
    """
    trades = trades.copy()
    trades["timestamp"] = pd.to_datetime(trades["timestamp"])

    df_ts = pd.to_datetime(df["timestamp"])
    window_ms = _timeframe_to_ms(timeframe)

    if len(trades) > 5_000_000:
        print(f"  trades 数据量较大 ({len(trades):,} 行)，按时间范围裁剪...")
        cutoff = df_ts.min() - pd.Timedelta(hours=1)
        trades = trades[trades["timestamp"] >= cutoff]
        print(f"  裁剪后: {len(trades):,} 行")

    if len(trades) == 0:
        print(f"  trades 裁剪后为空，尝试加载最近数据...")
        from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
        reader = FileDataLakeReader()
        end_ts = df_ts.max().to_pydatetime()
        start_ts = (df_ts.min() - pd.Timedelta(hours=1)).to_pydatetime()
        trades = reader.load_trades(exchange="binance", symbol="BTCUSDT", start_ts=start_ts, end_ts=end_ts)
        if trades is not None and len(trades) > 0:
            trades["timestamp"] = pd.to_datetime(trades["timestamp"])
            print(f"  重新加载 trades: {len(trades):,} 行")
        else:
            _add_nan_order_flow_cols(df)
            return df

    print(f"  向量化聚合 order_flow 特征 (window={timeframe})...")

    trades["qty"] = pd.to_numeric(trades["qty"], errors="coerce").fillna(0)
    trades["quote_qty"] = pd.to_numeric(trades["quote_qty"], errors="coerce").fillna(0)
    trades["price"] = pd.to_numeric(trades["price"], errors="coerce")
    trades["is_sell"] = trades["is_buyer_maker"].astype(bool)
    trades["is_buy"] = ~trades["is_sell"]

    trades["buy_qty"] = np.where(trades["is_buy"], trades["qty"], 0.0)
    trades["sell_qty"] = np.where(trades["is_sell"], trades["qty"], 0.0)
    trades["buy_quote"] = np.where(trades["is_buy"], trades["quote_qty"], 0.0)
    trades["sell_quote"] = np.where(trades["is_sell"], trades["quote_qty"], 0.0)

    large_threshold = trades["quote_qty"].quantile(0.95) if len(trades) > 1000 else 10000.0
    trades["is_large"] = trades["quote_qty"] >= large_threshold
    trades["large_buy_qty"] = np.where(trades["is_buy"] & trades["is_large"], trades["qty"], 0.0)
    trades["large_sell_qty"] = np.where(trades["is_sell"] & trades["is_large"], trades["qty"], 0.0)
    trades["large_buy_count"] = (trades["is_buy"] & trades["is_large"]).astype(int)
    trades["large_sell_count"] = (trades["is_sell"] & trades["is_large"]).astype(int)

    trades = MemoryOptimizer.downcast_float(trades)

    window_str = _timeframe_to_resample(timeframe)
    trades = trades.set_index("timestamp").sort_index()

    agg = trades.resample(window_str).agg(
        buy_volume=("buy_qty", "sum"),
        sell_volume=("sell_qty", "sum"),
        buy_quote=("buy_quote", "sum"),
        sell_quote=("sell_quote", "sum"),
        num_trades=("qty", "count"),
        total_volume=("qty", "sum"),
        total_quote=("quote_qty", "sum"),
        max_trade_size=("qty", "max"),
        last_price=("price", "last"),
        large_buy_volume=("large_buy_qty", "sum"),
        large_sell_volume=("large_sell_qty", "sum"),
        large_buy_count=("large_buy_count", "sum"),
        large_sell_count=("large_sell_count", "sum"),
    )

    agg = agg[agg["num_trades"] > 0].reset_index()
    agg["timestamp"] = pd.to_datetime(agg["timestamp"])

    total_vol = agg["buy_volume"] + agg["sell_volume"]
    total_quote = agg["buy_quote"] + agg["sell_quote"]

    feat_df = pd.DataFrame()
    feat_df["timestamp"] = agg["timestamp"]
    feat_df["aggressive_buy_volume"] = agg["buy_volume"]
    feat_df["aggressive_sell_volume"] = agg["sell_volume"]
    feat_df["aggressive_buy"] = agg["buy_volume"]
    feat_df["aggressive_sell"] = agg["sell_volume"]
    feat_df["trade_delta"] = agg["buy_volume"] - agg["sell_volume"]
    feat_df["total_volume"] = total_vol
    feat_df["total_value"] = total_quote
    feat_df["num_trades"] = agg["num_trades"]
    feat_df["avg_trade_size"] = total_vol / agg["num_trades"].replace(0, np.nan)
    feat_df["max_trade_size"] = agg["max_trade_size"]
    feat_df["trade_velocity"] = agg["num_trades"] / (window_ms / 1000.0)
    feat_df["trade_price"] = agg["last_price"]
    feat_df["trade_volume"] = total_vol

    feat_df["taker_buy_ratio"] = agg["buy_volume"] / total_vol.replace(0, np.nan)
    feat_df["buy_sell_ratio"] = agg["buy_volume"] / agg["sell_volume"].replace(0, np.nan)
    feat_df["trade_imbalance"] = (agg["buy_volume"] - agg["sell_volume"]) / total_vol.replace(0, np.nan)
    feat_df["aggressive_ratio"] = feat_df["buy_sell_ratio"]

    feat_df["large_trade_volume"] = agg["large_buy_volume"] + agg["large_sell_volume"]
    feat_df["large_trade_ratio"] = feat_df["large_trade_volume"] / total_vol.replace(0, np.nan)

    feat_df["whale_buy_volume"] = agg["large_buy_volume"]
    feat_df["whale_sell_volume"] = agg["large_sell_volume"]
    feat_df["whale_buy_count"] = agg["large_buy_count"]
    feat_df["whale_sell_count"] = agg["large_sell_count"]

    feat_df["cumulative_delta"] = feat_df["trade_delta"].cumsum()
    feat_df["cvd"] = feat_df["cumulative_delta"]
    feat_df["cvd_delta"] = feat_df["trade_delta"].diff()
    feat_df["cvd_slope"] = feat_df["cvd_delta"]

    cvd_mean = feat_df["cvd_delta"].rolling(100).mean()
    cvd_std = feat_df["cvd_delta"].rolling(100).std()
    feat_df["cvd_zscore"] = (feat_df["cvd_delta"] - cvd_mean) / cvd_std.replace(0, np.nan)

    vol_mean = feat_df["total_volume"].rolling(100).mean()
    vol_std = feat_df["total_volume"].rolling(100).std()
    vol_zscore = (feat_df["total_volume"] - vol_mean) / vol_std.replace(0, np.nan)

    feat_df["trade_pressure_score"] = (
        0.4 * feat_df["cvd_zscore"].fillna(0)
        + 0.3 * vol_zscore.fillna(0)
        + 0.3 * feat_df["trade_imbalance"].fillna(0)
    )
    feat_df["long_pressure_score"] = feat_df["trade_pressure_score"]
    feat_df["short_pressure_score"] = -feat_df["trade_pressure_score"]

    squeeze_cond = (vol_zscore > 1.5) & (feat_df["cvd_zscore"].abs() > 1.5)
    feat_df["squeeze_pressure_score"] = np.where(
        squeeze_cond,
        np.minimum(3.0, vol_zscore.fillna(0) + feat_df["cvd_zscore"].abs().fillna(0)),
        0.0,
    )
    feat_df["flush_pressure_score"] = 0.0

    price_change = feat_df["trade_price"].pct_change().fillna(0)
    buy_sweep = (
        (price_change > 0.001)
        & (feat_df["cvd_zscore"] > 2.0)
        & (feat_df["taker_buy_ratio"] > 0.6)
        & (vol_zscore > 1.5)
    )
    sell_sweep = (
        (price_change < -0.001)
        & (feat_df["cvd_zscore"] < -2.0)
        & (feat_df["taker_buy_ratio"] < 0.4)
        & (vol_zscore > 1.5)
    )
    feat_df["sweep_buy_score"] = np.where(buy_sweep, feat_df["cvd_zscore"].fillna(0) * feat_df["taker_buy_ratio"].fillna(0), 0.0)
    feat_df["sweep_sell_score"] = np.where(sell_sweep, -feat_df["cvd_zscore"].fillna(0) * (1 - feat_df["taker_buy_ratio"].fillna(0)), 0.0)

    keep_cols = ["timestamp"] + [c for c in ORDER_FLOW_COLUMNS if c in feat_df.columns]
    feat_df = feat_df[[c for c in keep_cols if c in feat_df.columns]]

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    feat_sorted = feat_df.sort_values("timestamp")

    merged = pd.merge_asof(
        df_sorted,
        feat_sorted,
        left_on="_ts",
        right_on="timestamp",
        direction="backward",
    )

    for col in ORDER_FLOW_COLUMNS:
        if col in merged.columns:
            df[col] = merged[col].values
        else:
            df[col] = np.nan

    non_null = df[ORDER_FLOW_COLUMNS[0]].notna().sum()
    print(f"  order_flow 特征: {non_null}/{len(df)} 行有数据")

    return df


_MATERIALIZED_COL_MAP = {
    "cvd": "cumulative_delta",
    "cvd_slope": "cvd_delta",
    "cvd_delta": "cvd_delta",
    "cvd_zscore": "cvd_zscore",
    "cumulative_delta": "cumulative_delta",
    "aggressive_buy_volume": "aggressive_buy_volume",
    "aggressive_sell_volume": "aggressive_sell_volume",
    "aggressive_buy": "aggressive_buy_volume",
    "aggressive_sell": "aggressive_sell_volume",
    "aggressive_ratio": "buy_sell_ratio",
    "taker_buy_ratio": "taker_buy_ratio",
    "buy_sell_ratio": "buy_sell_ratio",
    "trade_imbalance": "trade_imbalance",
    "trade_delta": "trade_delta",
    "trade_velocity": "trade_velocity",
    "large_trade_ratio": "large_trade_ratio",
    "large_trade_volume": "large_trade_volume",
    "sweep_buy_score": "sweep_buy_score",
    "sweep_sell_score": "sweep_sell_score",
    "trade_pressure_score": "trade_pressure_score",
    "long_pressure_score": "long_pressure_score",
    "short_pressure_score": "short_pressure_score",
    "squeeze_pressure_score": "squeeze_pressure_score",
    "flush_pressure_score": "flush_pressure_score",
    "trade_volume": "total_volume",
}


def _merge_materialized_trades(
    df: pd.DataFrame, trade_flow: pd.DataFrame
) -> pd.DataFrame:
    trade_flow = trade_flow.copy()
    if "timestamp" in trade_flow.columns:
        trade_flow["timestamp"] = pd.to_datetime(trade_flow["timestamp"])

    feat_df = pd.DataFrame()
    feat_df["timestamp"] = trade_flow["timestamp"]

    for target_col, source_col in _MATERIALIZED_COL_MAP.items():
        if source_col in trade_flow.columns:
            feat_df[target_col] = trade_flow[source_col].values
        else:
            feat_df[target_col] = np.nan

    for col in ORDER_FLOW_COLUMNS:
        if col not in feat_df.columns:
            feat_df[col] = np.nan

    keep_cols = ["timestamp"] + [c for c in ORDER_FLOW_COLUMNS if c in feat_df.columns]
    feat_df = feat_df[[c for c in keep_cols if c in feat_df.columns]]

    df_ts = pd.to_datetime(df["timestamp"])
    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    feat_sorted = feat_df.sort_values("timestamp")

    merged = pd.merge_asof(
        df_sorted,
        feat_sorted,
        left_on="_ts",
        right_on="timestamp",
        direction="backward",
    )

    for col in ORDER_FLOW_COLUMNS:
        if col in merged.columns:
            df[col] = merged[col].values
        else:
            df[col] = np.nan

    non_null = df[ORDER_FLOW_COLUMNS[0]].notna().sum()
    print(f"  order_flow 特征 (materialized): {non_null}/{len(df)} 行有数据")

    return df


def _timeframe_to_resample(tf: str) -> str:
    return {
        "1m": "1min", "3m": "3min", "5m": "5min",
        "15m": "15min", "30m": "30min", "1h": "1h",
        "2h": "2h", "4h": "4h", "1d": "1D",
    }.get(tf, "1h")


LIQUIDITY_ESTIMATE_COLUMNS = [
    "spread_estimate", "spread_pct_estimate",
    "microprice_estimate", "imbalance_1", "imbalance_10",
    "imbalance_slope", "depth_pressure", "depth_change",
    "liquidity_shift", "spoof_probability", "wall_detection",
]


OI_FUNDING_COLUMNS = [
    "oi_funding_divergence", "oi_squeeze_probability",
    "oi_liq_pressure", "funding_extreme_reversal",
    "leverage_crowdedness",
]


def _add_nan_liquidity_cols(df: pd.DataFrame):
    for col in LIQUIDITY_ESTIMATE_COLUMNS:
        df[col] = np.nan


def _add_nan_oi_funding_cols(df: pd.DataFrame):
    for col in OI_FUNDING_COLUMNS:
        df[col] = np.nan


def _compute_tech_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """GPU/CPU 加速计算技术指标"""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    try:
        from infrastructure.acceleration import get_is_gpu
        use_gpu = get_is_gpu()
    except Exception:
        use_gpu = False

    if use_gpu and len(df) > 1000:
        try:
            from infrastructure.acceleration import torch, to_gpu, to_cpu, get_device
            closes_t = torch.tensor(close.values.astype(np.float32), device=get_device())
            highs_t = torch.tensor(high.values.astype(np.float32), device=get_device())
            lows_t = torch.tensor(low.values.astype(np.float32), device=get_device())
            volumes_t = torch.tensor(volume.values.astype(np.float32), device=get_device())

            for period in [7, 14, 21]:
                deltas = closes_t[1:] - closes_t[:-1]
                gains = torch.where(deltas > 0, deltas, torch.zeros_like(deltas))
                losses = torch.where(deltas < 0, -deltas, torch.zeros_like(deltas))
                kernel = torch.ones(period, device=get_device()) / period
                kernel = kernel.view(1, 1, -1)
                gains_padded = torch.nn.functional.pad(gains.view(1, 1, -1), (period - 1, 0))
                losses_padded = torch.nn.functional.pad(losses.view(1, 1, -1), (period - 1, 0))
                avg_gains = torch.nn.functional.conv1d(gains_padded, kernel).squeeze()
                avg_losses = torch.nn.functional.conv1d(losses_padded, kernel).squeeze()
                rsi = torch.where(
                    avg_losses > 0,
                    100.0 - (100.0 / (1 + avg_gains / avg_losses)),
                    torch.tensor(100.0, device=get_device()),
                )
                rsi = torch.cat([torch.full((period,), float("nan"), device=get_device()), rsi])
                df[f"rsi_{period}"] = to_cpu(rsi[: len(df)])

            for window in [10, 20, 50, 100]:
                kernel = torch.ones(window, device=get_device()) / window
                kernel = kernel.view(1, 1, -1)
                padded = torch.nn.functional.pad(closes_t.view(1, 1, -1), (window - 1, 0))
                sma = torch.nn.functional.conv1d(padded, kernel).squeeze()
                sma = torch.cat([torch.full((window - 1,), float("nan"), device=get_device()), sma])
                df[f"sma_{window}"] = to_cpu(sma[: len(df)])

            for span in [10, 20, 50]:
                alpha = 2.0 / (span + 1)
                ema = torch.zeros_like(closes_t)
                ema[0] = closes_t[0]
                for i in range(1, len(closes_t)):
                    ema[i] = alpha * closes_t[i] + (1 - alpha) * ema[i - 1]
                df[f"ema_{span}"] = to_cpu(ema)

            ema_fast = _torch_ema(closes_t, 12)
            ema_slow = _torch_ema(closes_t, 26)
            macd = ema_fast - ema_slow
            macd_signal = _torch_ema(macd, 9)
            macd_hist = macd - macd_signal
            df["macd"] = to_cpu(macd)
            df["macd_signal"] = to_cpu(macd_signal)
            df["macd_hist"] = to_cpu(macd_hist)

            window = 20
            kernel = torch.ones(window, device=get_device()) / window
            kernel = kernel.view(1, 1, -1)
            padded = torch.nn.functional.pad(closes_t.view(1, 1, -1), (window - 1, 0))
            sma = torch.nn.functional.conv1d(padded, kernel).squeeze()
            padded_sq = torch.nn.functional.pad((closes_t ** 2).view(1, 1, -1), (window - 1, 0))
            sma_sq = torch.nn.functional.conv1d(padded_sq, kernel).squeeze()
            var = sma_sq - sma ** 2
            std = torch.sqrt(torch.clamp(var, min=0))
            df["bb_upper"] = to_cpu(torch.cat([closes_t[: window - 1], sma + 2 * std])[: len(df)])
            df["bb_lower"] = to_cpu(torch.cat([closes_t[: window - 1], sma - 2 * std])[: len(df)])
            df["bb_width"] = to_cpu(torch.cat([torch.zeros(window - 1, device=get_device()), 4 * std / sma])[: len(df)])

            print(f"  技术指标: GPU 加速完成")
            return df
        except Exception as e:
            print(f"  GPU 计算失败，回退 CPU: {e}")

    for period in [7, 14, 21]:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

    for window in [10, 20, 50, 100]:
        df[f"sma_{window}"] = close.rolling(window).mean()

    for span in [10, 20, 50]:
        df[f"ema_{span}"] = close.ewm(span=span, adjust=False).mean()

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    df["bb_upper"] = sma_20 + 2 * std_20
    df["bb_lower"] = sma_20 - 2 * std_20
    df["bb_width"] = 4 * std_20 / sma_20.replace(0, np.nan)

    print(f"  技术指标: CPU 完成")
    return df


def _torch_ema(data, span: int):
    from infrastructure.acceleration import torch, get_device
    alpha = 2.0 / (span + 1)
    ema = torch.zeros_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


def _compute_liquidity_estimates(
    df: pd.DataFrame, trades: pd.DataFrame, timeframe: str
) -> pd.DataFrame:
    """从 trades 数据合成 liquidity 估计特征"""
    trades = trades.copy()
    trades["timestamp"] = pd.to_datetime(trades["timestamp"])
    trades["price"] = pd.to_numeric(trades["price"], errors="coerce")
    trades["qty"] = pd.to_numeric(trades["qty"], errors="coerce")
    trades["quote_qty"] = pd.to_numeric(trades["quote_qty"], errors="coerce")
    trades["is_buy"] = ~trades["is_buyer_maker"].astype(bool)

    df_ts = pd.to_datetime(df["timestamp"])
    window_str = _timeframe_to_resample(timeframe)

    cutoff = df_ts.min() - pd.Timedelta(hours=1)
    trades = trades[trades["timestamp"] >= cutoff]

    if len(trades) == 0:
        _add_nan_liquidity_cols(df)
        return df

    trades = trades.set_index("timestamp").sort_index()

    agg = trades.resample(window_str).agg(
        high_price=("price", "max"),
        low_price=("price", "min"),
        first_price=("price", "first"),
        last_price=("price", "last"),
        total_qty=("qty", "sum"),
        total_quote=("quote_qty", "sum"),
        num_trades=("qty", "count"),
        buy_qty=("is_buy", "sum"),
    )
    agg = agg[agg["num_trades"] > 0].reset_index()
    agg["timestamp"] = pd.to_datetime(agg["timestamp"])

    agg["spread_estimate"] = agg["high_price"] - agg["low_price"]
    agg["spread_pct_estimate"] = agg["spread_estimate"] / agg["last_price"].replace(0, np.nan)

    agg["microprice_estimate"] = agg["last_price"]

    sell_qty = agg["total_qty"] - agg["buy_qty"]
    agg["imbalance_1"] = (agg["buy_qty"] - sell_qty) / agg["total_qty"].replace(0, np.nan)
    agg["imbalance_10"] = agg["imbalance_1"].rolling(10).mean()
    agg["imbalance_slope"] = agg["imbalance_1"].diff()
    agg["depth_pressure"] = agg["imbalance_1"] * agg["total_qty"]
    agg["depth_change"] = agg["imbalance_1"].pct_change()
    agg["liquidity_shift"] = (agg["buy_qty"] - sell_qty) / agg["total_qty"].replace(0, np.nan)

    agg["spoof_probability"] = 0.0
    agg["wall_detection"] = 0.0

    keep_cols = ["timestamp"] + [c for c in LIQUIDITY_ESTIMATE_COLUMNS if c in agg.columns]
    feat_df = agg[[c for c in keep_cols if c in agg.columns]]

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    feat_sorted = feat_df.sort_values("timestamp")

    merged = pd.merge_asof(
        df_sorted, feat_sorted, left_on="_ts", right_on="timestamp", direction="backward"
    )

    for col in LIQUIDITY_ESTIMATE_COLUMNS:
        if col in merged.columns:
            df[col] = merged[col].values
        else:
            df[col] = np.nan

    return df


def _compute_oi_funding_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算 OI-Funding 关联特征"""
    oi = df["oi"]
    fr = df["funding_rate"]

    oi_chg = oi.pct_change()
    fr_chg = fr.diff()

    oi_pos = oi_chg > 0
    fr_pos = fr > 0
    oi_neg = oi_chg < 0
    fr_neg = fr < 0

    divergence = np.where(
        (oi_pos & fr_neg) | (oi_neg & fr_pos),
        np.abs(oi_chg) * np.abs(fr),
        0.0,
    )
    df["oi_funding_divergence"] = pd.Series(divergence, index=df.index)

    oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
    fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))

    squeeze_prob = np.where(
        (oi_z.abs() > 1.5) & (fr_z.abs() > 1.5),
        np.minimum(1.0, (oi_z.abs() + fr_z.abs()) / 6.0),
        0.0,
    )
    df["oi_squeeze_probability"] = pd.Series(squeeze_prob, index=df.index)

    df["oi_liq_pressure"] = oi * fr.abs()

    reversal = np.where(
        fr_z.abs() > 2.5,
        -np.sign(fr) * fr_z.abs() / 3.0,
        0.0,
    )
    df["funding_extreme_reversal"] = pd.Series(reversal, index=df.index)

    leverage_crowd = np.where(
        (oi_z > 1.5) & (fr_z > 1.5),
        (oi_z + fr_z) / 3.0,
        0.0,
    )
    df["leverage_crowdedness"] = pd.Series(leverage_crowd, index=df.index)

    return df


def _compute_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算 Regime 特征（从已有特征派生）"""
    vol_z = df.get("volatility_zscore", pd.Series(0.0, index=df.index))
    vol_z = vol_z.fillna(0)

    df["high_volatility"] = (vol_z > 1.5).astype(float)
    df["low_liquidity"] = 0.0
    if "volume_zscore" in df.columns:
        df["low_liquidity"] = (df["volume_zscore"].fillna(0) < -1.5).astype(float)

    if "trend_20" in df.columns:
        trend = df["trend_20"].fillna(0)
        df["trend_regime"] = np.where(
            trend > 0.01, "trend",
            np.where(trend < -0.01, "trend", "chop"),
        )

    if "volatility_zscore" in df.columns:
        vz = df["volatility_zscore"].fillna(0)
        df["volatility_regime"] = np.where(
            vz > 2.0, "extreme",
            np.where(vz > 1.0, "high",
                     np.where(vz < -1.0, "low", "normal")),
        )

    df["extreme_move"] = 0.0
    if "ret_1" in df.columns:
        ret = df["ret_1"].fillna(0)
        ret_std = ret.rolling(100).std().fillna(0)
        df["extreme_move"] = (ret.abs() > 3 * ret_std).astype(float)

    df["regime_change"] = 0.0
    if "trend_regime" in df.columns:
        df["regime_change"] = (df["trend_regime"] != df["trend_regime"].shift(1)).astype(float)

    df["risk_multiplier"] = 1.0
    if "high_volatility" in df.columns:
        df["risk_multiplier"] = np.where(df["high_volatility"] > 0, 0.5, 1.0)

    df["risk_on_off"] = 0.0
    if "trend_20" in df.columns and "volatility_zscore" in df.columns:
        df["risk_on_off"] = (
            np.sign(df["trend_20"].fillna(0))
            * (1 - df["volatility_zscore"].fillna(0).clip(-3, 3) / 3.0)
        )

    df["primary_regime"] = "neutral"
    if "trend_regime" in df.columns and "volatility_regime" in df.columns:
        tr = df["trend_regime"].fillna("chop")
        vr = df["volatility_regime"].fillna("normal")
        df["primary_regime"] = np.where(
            vr == "extreme", "panic",
            np.where(
                (tr == "trend") & (vr == "high"), "squeeze",
                np.where(
                    tr == "trend", "trend",
                    np.where(vr == "high", "high_leverage", "neutral"),
                ),
            ),
        )

    df["regime_risk_level"] = 0.5
    if "volatility_zscore" in df.columns:
        df["regime_risk_level"] = df["volatility_zscore"].fillna(0).clip(-3, 3).abs() / 3.0

    df["position_sizing_multiplier"] = 1.0 - df.get("regime_risk_level", 0.5) * 0.5

    return df


def _compute_event_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算 Event-driven 特征（从已有特征派生）"""
    if "funding_zscore" in df.columns:
        fr_z = df["funding_zscore"].fillna(0)
        df["funding_explosion"] = (fr_z.abs() > 3).astype(float)
    else:
        df["funding_explosion"] = 0.0

    if "volume_zscore" in df.columns:
        df["volume_vacuum_event"] = (df["volume_zscore"].fillna(0) < -2).astype(float)
    else:
        df["volume_vacuum_event"] = 0.0

    df["news_event"] = 0.0

    return df


def _resample_klines(df: pd.DataFrame, target: str) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.set_index("timestamp").sort_index()
    resampled = df.resample({
        "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
        "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"
    }[target]).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna(subset=["close"])

    return resampled.reset_index()


def _timeframe_to_ms(tf: str) -> int:
    ms_map = {
        "1m": 60000, "3m": 180000, "5m": 300000,
        "15m": 900000, "30m": 1800000, "1h": 3600000,
        "2h": 7200000, "4h": 14400000, "1d": 86400000
    }
    return ms_map.get(tf, 3600000)


def _timeframe_to_bars_per_day(tf: str) -> int:
    bars_map = {
        "1m": 1440, "3m": 480, "5m": 288,
        "15m": 96, "30m": 48, "1h": 24,
        "2h": 12, "4h": 6, "1d": 1
    }
    return bars_map.get(tf, 24)


__all__ = ["build_feature_matrix", "build_feature_matrix_from_df"]
