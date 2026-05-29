"""
Offline Trade Flow Aggregation - 离线交易流聚合

将海量原始 trade 数据（单月 1.2 亿行）预聚合为多时间维度的 trade flow 特征，
输出为轻量 parquet 文件，供 Alpha Pipeline 直接使用。

输出目录结构:
  data_lake/crypto/binance/trade_flow/
    symbol=BTCUSDT/
      timeframe=1h/
        data.parquet
      timeframe=1m/
        data.parquet

用法:
  python scripts/offline_trade_flow.py --symbol BTCUSDT --timeframe 1h
  python scripts/offline_trade_flow.py --symbol BTCUSDT --timeframe 1m,5m,15m,1h
  python scripts/offline_trade_flow.py --symbols BTCUSDT,SOLUSDT,ETCUSDT,ZECUSDT --timeframe 1h
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DATA_LAKE_ROOT = BACKEND_ROOT / "data_lake"

TRADE_FLOW_COLUMNS = [
    "timestamp",
    "buy_volume", "sell_volume", "total_volume",
    "buy_quote", "sell_quote", "total_quote",
    "num_trades", "avg_trade_size", "max_trade_size",
    "taker_buy_ratio", "buy_sell_ratio", "trade_imbalance",
    "trade_delta", "cumulative_delta",
    "cvd", "cvd_delta", "cvd_zscore",
    "large_trade_volume", "large_trade_ratio",
    "whale_buy_volume", "whale_sell_volume",
    "whale_buy_count", "whale_sell_count",
    "trade_velocity",
    "trade_pressure_score", "long_pressure_score", "short_pressure_score",
    "sweep_buy_score", "sweep_sell_score",
    "spread_estimate", "spread_pct_estimate",
    "imbalance_1", "imbalance_10", "imbalance_slope",
]


TF_RESAMPLE_MAP = {
    "1m": "1min", "3m": "3min", "5m": "5min",
    "15m": "15min", "30m": "30min", "1h": "1h",
    "2h": "2h", "4h": "4h", "1d": "1D",
}


def _load_trades_month(trades_path: Path) -> Optional[pd.DataFrame]:
    parquet_path = trades_path / "data.parquet"
    if not parquet_path.exists():
        return None
    try:
        df = pd.read_parquet(
            parquet_path,
            columns=["timestamp", "price", "qty", "quote_qty", "is_buyer_maker"],
        )
        if df is None or df.empty:
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        print(f"  Error reading {parquet_path}: {e}")
        return None


def _aggregate_trades(
    trades: pd.DataFrame,
    timeframe: str,
) -> pd.DataFrame:
    trades = trades.copy()
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
    trades["large_buy_count"] = (trades["is_buy"] & trades["is_large"]).astype(np.int32)
    trades["large_sell_count"] = (trades["is_sell"] & trades["is_large"]).astype(np.int32)

    window_str = TF_RESAMPLE_MAP.get(timeframe, "1h")
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

    feat = pd.DataFrame()
    feat["timestamp"] = agg["timestamp"]
    feat["buy_volume"] = agg["buy_volume"].values
    feat["sell_volume"] = agg["sell_volume"].values
    feat["total_volume"] = total_vol.values
    feat["buy_quote"] = agg["buy_quote"].values
    feat["sell_quote"] = agg["sell_quote"].values
    feat["total_quote"] = total_quote.values
    feat["num_trades"] = agg["num_trades"].values
    feat["avg_trade_size"] = (total_vol / agg["num_trades"].replace(0, np.nan)).values
    feat["max_trade_size"] = agg["max_trade_size"].values

    feat["taker_buy_ratio"] = (agg["buy_volume"] / total_vol.replace(0, np.nan)).values
    feat["buy_sell_ratio"] = (agg["buy_volume"] / agg["sell_volume"].replace(0, np.nan)).values
    feat["trade_imbalance"] = ((agg["buy_volume"] - agg["sell_volume"]) / total_vol.replace(0, np.nan)).values
    feat["trade_delta"] = (agg["buy_volume"] - agg["sell_volume"]).values

    feat["cumulative_delta"] = feat["trade_delta"].cumsum()
    feat["cvd"] = feat["cumulative_delta"]
    feat["cvd_delta"] = feat["trade_delta"].diff()

    cvd_mean = feat["cvd_delta"].rolling(100, min_periods=1).mean()
    cvd_std = feat["cvd_delta"].rolling(100, min_periods=1).std()
    feat["cvd_zscore"] = ((feat["cvd_delta"] - cvd_mean) / cvd_std.replace(0, np.nan)).values

    feat["large_trade_volume"] = (agg["large_buy_volume"] + agg["large_sell_volume"]).values
    feat["large_trade_ratio"] = (feat["large_trade_volume"] / total_vol.replace(0, np.nan)).values
    feat["whale_buy_volume"] = agg["large_buy_volume"].values
    feat["whale_sell_volume"] = agg["large_sell_volume"].values
    feat["whale_buy_count"] = agg["large_buy_count"].values
    feat["whale_sell_count"] = agg["large_sell_count"].values

    window_ms = {
        "1m": 60000, "3m": 180000, "5m": 300000,
        "15m": 900000, "30m": 1800000, "1h": 3600000,
        "2h": 7200000, "4h": 14400000, "1d": 86400000,
    }.get(timeframe, 3600000)
    feat["trade_velocity"] = (agg["num_trades"] / (window_ms / 1000.0)).values

    vol_mean = total_vol.rolling(100, min_periods=1).mean()
    vol_std = total_vol.rolling(100, min_periods=1).std()
    vol_zscore = (total_vol - vol_mean) / vol_std.replace(0, np.nan)

    feat["trade_pressure_score"] = (
        0.4 * feat["cvd_zscore"].fillna(0)
        + 0.3 * vol_zscore.fillna(0).values
        + 0.3 * feat["trade_imbalance"].fillna(0)
    )
    feat["long_pressure_score"] = feat["trade_pressure_score"]
    feat["short_pressure_score"] = -feat["trade_pressure_score"]

    price_change = agg["last_price"].pct_change().fillna(0)
    buy_sweep = (
        (price_change > 0.001)
        & (feat["cvd_zscore"] > 2.0)
        & (feat["taker_buy_ratio"] > 0.6)
        & (vol_zscore > 1.5)
    )
    sell_sweep = (
        (price_change < -0.001)
        & (feat["cvd_zscore"] < -2.0)
        & (feat["taker_buy_ratio"] < 0.4)
        & (vol_zscore > 1.5)
    )
    feat["sweep_buy_score"] = np.where(
        buy_sweep,
        feat["cvd_zscore"].fillna(0) * feat["taker_buy_ratio"].fillna(0),
        0.0,
    )
    feat["sweep_sell_score"] = np.where(
        sell_sweep,
        -feat["cvd_zscore"].fillna(0) * (1 - feat["taker_buy_ratio"].fillna(0)),
        0.0,
    )

    feat["spread_estimate"] = 0.0
    feat["spread_pct_estimate"] = 0.0
    if "last_price" in agg.columns:
        price_std = agg["last_price"].rolling(5, min_periods=1).std().fillna(0)
        feat["spread_estimate"] = price_std.values
        feat["spread_pct_estimate"] = (price_std / agg["last_price"].replace(0, np.nan)).values

    sell_qty = agg["total_volume"] - agg["buy_volume"]
    feat["imbalance_1"] = ((agg["buy_volume"] - sell_qty) / agg["total_volume"].replace(0, np.nan)).values
    feat["imbalance_10"] = feat["imbalance_1"].rolling(10, min_periods=1).mean().values
    feat["imbalance_slope"] = feat["imbalance_1"].diff().values

    return feat


def aggregate_symbol(
    symbol: str,
    exchange: str,
    timeframe: str,
    output_root: Optional[Path] = None,
) -> Path:
    if output_root is None:
        output_root = DATA_LAKE_ROOT

    trades_base = DATA_LAKE_ROOT / "crypto" / exchange / "trades" / f"symbol={symbol}"
    if not trades_base.exists():
        print(f"  No trades directory for {symbol}, skipping")
        return Path("")

    output_dir = output_root / "crypto" / exchange / "trade_flow" / f"symbol={symbol}" / f"timeframe={timeframe}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "data.parquet"

    if output_path.exists():
        existing = pd.read_parquet(output_path, columns=["timestamp"])
        if len(existing) > 0:
            existing_max = pd.to_datetime(existing["timestamp"]).max()
            print(f"  Existing trade_flow up to {existing_max}, checking for new data...")

    year_dirs = sorted(trades_base.glob("year=*"))
    all_features = []

    for year_dir in year_dirs:
        month_dirs = sorted(year_dir.glob("month=*"))
        for month_dir in month_dirs:
            month_label = f"{year_dir.name}/{month_dir.name}"
            print(f"  Processing {month_label}...")

            trades = _load_trades_month(month_dir)
            if trades is None or len(trades) == 0:
                print(f"    No data in {month_label}")
                continue

            print(f"    Loaded {len(trades):,} trades")

            feat = _aggregate_trades(trades, timeframe)
            if len(feat) > 0:
                all_features.append(feat)
                print(f"    Aggregated to {len(feat)} bars")

            del trades

    if not all_features:
        print(f"  No trade data aggregated for {symbol}")
        return Path("")

    result = pd.concat(all_features, ignore_index=True)
    result = result.drop_duplicates(subset=["timestamp"], keep="last")
    result = result.sort_values("timestamp").reset_index(drop=True)

    result.to_parquet(output_path, index=False, compression="zstd")
    print(f"  Saved {len(result):,} bars to {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Offline Trade Flow Aggregation")
    parser.add_argument("--symbols", type=str, default="BTCUSDT",
                        help="Comma-separated symbol list")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--timeframe", type=str, default="1h",
                        help="Comma-separated timeframe list (1m,5m,15m,1h)")
    parser.add_argument("--output-root", type=str, default=None,
                        help="Output root directory (default: data_lake)")

    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    timeframes = [t.strip() for t in args.timeframe.split(",")]
    output_root = Path(args.output_root) if args.output_root else None

    print("=" * 60)
    print("Offline Trade Flow Aggregation")
    print(f"  Symbols: {symbols}")
    print(f"  Timeframes: {timeframes}")
    print(f"  Exchange: {args.exchange}")
    print("=" * 60)

    for symbol in symbols:
        for tf in timeframes:
            print(f"\n[{symbol} | {tf}]")
            aggregate_symbol(symbol, args.exchange, tf, output_root)

    print("\nDone.")


if __name__ == "__main__":
    main()
