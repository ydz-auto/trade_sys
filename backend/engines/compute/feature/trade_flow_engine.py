import logging
from typing import Dict

import numpy as np
import pandas as pd
import gc
from infrastructure.acceleration.memory_optimizer import MemoryOptimizer

logger = logging.getLogger(__name__)

TF_RESAMPLE_MAP: Dict[str, str] = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "1d": "1D",
}

LARGE_TRADE_QUANTILE: float = 0.95
ZSCORE_WINDOW: int = 240
SWEEP_LARGE_RATIO_WEIGHT: float = 0.6
SWEEP_PRICE_MOVE_WEIGHT: float = 0.4
PRESSURE_CVD_WEIGHT: float = 0.4
PRESSURE_VOL_WEIGHT: float = 0.3
PRESSURE_IMBALANCE_WEIGHT: float = 0.3
EXTREME_ZSCORE_THRESHOLD: float = 2.0
SQUEEZE_CVD_THRESHOLD: float = 2.0
SQUEEZE_IMBALANCE_THRESHOLD: float = 0.6
FLUSH_CVD_THRESHOLD: float = -2.0
FLUSH_IMBALANCE_THRESHOLD: float = -0.6

TRADE_FEATURE_COLUMNS: list[str] = [
    "timestamp",
    "symbol",
    "exchange",
    "trade_delta",
    "cumulative_delta",
    "aggressive_buy_volume",
    "aggressive_sell_volume",
    "total_volume",
    "total_value",
    "num_trades",
    "trade_velocity",
    "avg_trade_size",
    "max_trade_size",
    "large_trade_ratio",
    "large_trade_volume",
    "sweep_buy_score",
    "sweep_sell_score",
    "liquidity_vacuum",
    "trade_imbalance",
    "buy_sell_ratio",
    "taker_buy_ratio",
    "trade_pressure_score",
    "long_pressure_score",
    "short_pressure_score",
    "squeeze_pressure_score",
    "flush_pressure_score",
    "cvd_delta",
    "cvd_zscore",
    "volume_zscore",
]


class TradeFlowEngine:

    def aggregate(self, trades_df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        resample_rule = TF_RESAMPLE_MAP.get(timeframe)
        if resample_rule is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        df = trades_df.copy()

        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        if hasattr(df["timestamp"].dtype, "tz") and df["timestamp"].dtype.tz is not None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        df = df.set_index("timestamp")

        df["qty"] = df["qty"].astype(np.float32)
        df["quote_qty"] = df["quote_qty"].astype(np.float32)
        df["price"] = df["price"].astype(np.float32)

        is_buy = ~df["is_buyer_maker"]
        is_sell = df["is_buyer_maker"]

        df["buy_qty"] = df["qty"].where(is_buy, np.float32(0.0))
        df["sell_qty"] = df["qty"].where(is_sell, np.float32(0.0))
        df["buy_quote"] = df["quote_qty"].where(is_buy, np.float32(0.0))
        df["sell_quote"] = df["quote_qty"].where(is_sell, np.float32(0.0))

        del df["is_buyer_maker"]

        large_threshold = df["quote_qty"].quantile(LARGE_TRADE_QUANTILE)
        is_large = df["quote_qty"] >= large_threshold
        df["large_buy_qty"] = df["qty"].where(is_buy & is_large, np.float32(0.0))
        df["large_sell_qty"] = df["qty"].where(is_sell & is_large, np.float32(0.0))
        df["large_buy_count"] = is_buy.where(is_large, False).astype(np.float32)
        df["large_sell_count"] = is_sell.where(is_large, False).astype(np.float32)

        del is_buy, is_sell, is_large

        agg_columns = [
            "buy_qty", "sell_qty", "buy_quote", "sell_quote",
            "total_volume", "total_value", "num_trades", "max_trade_size",
            "large_buy_qty", "large_sell_qty", "large_buy_count", "large_sell_count",
            "price_first", "price_last", "price_max", "price_min",
        ]

        agg_dict: Dict[str, list] = {
            "buy_qty": ["sum"],
            "sell_qty": ["sum"],
            "buy_quote": ["sum"],
            "sell_quote": ["sum"],
            "qty": ["sum", "count", "max"],
            "quote_qty": ["sum"],
            "large_buy_qty": ["sum"],
            "large_sell_qty": ["sum"],
            "large_buy_count": ["sum"],
            "large_sell_count": ["sum"],
            "price": ["first", "last", "max", "min"],
        }

        grouped = df.resample(resample_rule).agg(agg_dict)
        grouped.columns = agg_columns

        del df

        grouped = grouped[grouped["num_trades"] > 0]

        result = pd.DataFrame(index=grouped.index)

        result["aggressive_buy_volume"] = grouped["buy_qty"]
        result["aggressive_sell_volume"] = grouped["sell_qty"]
        result["total_volume"] = grouped["total_volume"]
        result["total_value"] = grouped["total_value"]
        result["num_trades"] = grouped["num_trades"].astype(int)
        result["max_trade_size"] = grouped["max_trade_size"]
        result["avg_trade_size"] = np.where(
            grouped["num_trades"] > 0,
            grouped["total_volume"] / grouped["num_trades"],
            0.0,
        )
        result["trade_velocity"] = grouped["total_volume"]

        large_volume = grouped["large_buy_qty"] + grouped["large_sell_qty"]
        result["large_trade_volume"] = large_volume
        result["large_trade_ratio"] = np.where(
            grouped["total_volume"] > 0,
            large_volume / grouped["total_volume"],
            0.0,
        )

        result["trade_delta"] = grouped["buy_qty"] - grouped["sell_qty"]
        result["cumulative_delta"] = result["trade_delta"].cumsum()

        result["trade_imbalance"] = np.where(
            (grouped["buy_qty"] + grouped["sell_qty"]) > 0,
            (grouped["buy_qty"] - grouped["sell_qty"]) / (grouped["buy_qty"] + grouped["sell_qty"]),
            0.0,
        )

        result["buy_sell_ratio"] = np.where(
            grouped["sell_qty"] > 0,
            grouped["buy_qty"] / grouped["sell_qty"],
            np.where(grouped["buy_qty"] > 0, np.inf, 0.0),
        )

        result["taker_buy_ratio"] = np.where(
            grouped["total_volume"] > 0,
            grouped["buy_qty"] / grouped["total_volume"],
            0.0,
        )

        cvd = result["trade_delta"].cumsum()
        cvd_delta = result["trade_delta"].diff().fillna(0.0)
        result["cvd_delta"] = cvd_delta

        cvd_mean = cvd.rolling(window=ZSCORE_WINDOW, min_periods=1).mean()
        cvd_std = cvd.rolling(window=ZSCORE_WINDOW, min_periods=1).std()
        cvd_std = cvd_std.replace(0.0, np.nan).fillna(1.0)
        result["cvd_zscore"] = ((cvd - cvd_mean) / cvd_std).fillna(0.0)

        vol_mean = result["total_volume"].rolling(window=ZSCORE_WINDOW, min_periods=1).mean()
        vol_std = result["total_volume"].rolling(window=ZSCORE_WINDOW, min_periods=1).std()
        vol_std = vol_std.replace(0.0, np.nan).fillna(1.0)
        result["volume_zscore"] = ((result["total_volume"] - vol_mean) / vol_std).fillna(0.0)

        result["trade_pressure_score"] = (
            PRESSURE_CVD_WEIGHT * result["cvd_zscore"]
            + PRESSURE_VOL_WEIGHT * result["volume_zscore"]
            + PRESSURE_IMBALANCE_WEIGHT * result["trade_imbalance"]
        )

        result["long_pressure_score"] = np.clip(result["trade_pressure_score"], 0.0, None)
        result["short_pressure_score"] = np.clip(-result["trade_pressure_score"], 0.0, None)

        price_change = grouped["price_last"] - grouped["price_first"]
        price_range = grouped["price_max"] - grouped["price_min"]
        price_move_up = np.where(price_range > 0, (price_change / price_range), 0.0)
        price_move_down = np.where(price_range > 0, (-price_change / price_range), 0.0)

        large_buy_ratio = np.where(
            grouped["num_trades"] > 0,
            grouped["large_buy_count"] / grouped["num_trades"],
            0.0,
        )
        large_sell_ratio = np.where(
            grouped["num_trades"] > 0,
            grouped["large_sell_count"] / grouped["num_trades"],
            0.0,
        )

        result["sweep_buy_score"] = (
            SWEEP_LARGE_RATIO_WEIGHT * large_buy_ratio
            + SWEEP_PRICE_MOVE_WEIGHT * np.clip(price_move_up, 0.0, 1.0)
        )
        result["sweep_sell_score"] = (
            SWEEP_LARGE_RATIO_WEIGHT * large_sell_ratio
            + SWEEP_PRICE_MOVE_WEIGHT * np.clip(price_move_down, 0.0, 1.0)
        )

        time_diffs = pd.Series(np.diff(grouped.index.view(np.int64)), index=grouped.index[1:])
        time_diffs = pd.concat([pd.Series([0], index=[grouped.index[0]]), time_diffs])
        time_diffs = time_diffs.astype(float)
        avg_interval = time_diffs.rolling(window=ZSCORE_WINDOW, min_periods=1).mean()
        liquidity_vacuum_raw = np.where(
            avg_interval > 0,
            1.0 - (time_diffs / avg_interval).clip(upper=1.0),
            0.0,
        )
        result["liquidity_vacuum"] = np.where(
            (grouped["num_trades"] > 0) & (price_range > 0),
            liquidity_vacuum_raw * (grouped["total_volume"] / grouped["total_volume"].rolling(window=ZSCORE_WINDOW, min_periods=1).mean().replace(0.0, np.nan).fillna(1.0)).clip(upper=3.0),
            0.0,
        )

        squeeze_cond = (result["cvd_zscore"] > SQUEEZE_CVD_THRESHOLD) & (result["trade_imbalance"] > SQUEEZE_IMBALANCE_THRESHOLD)
        result["squeeze_pressure_score"] = np.where(
            squeeze_cond,
            np.clip(result["trade_pressure_score"], 0.0, None),
            0.0,
        )

        flush_cond = (result["cvd_zscore"] < FLUSH_CVD_THRESHOLD) & (result["trade_imbalance"] < FLUSH_IMBALANCE_THRESHOLD)
        result["flush_pressure_score"] = np.where(
            flush_cond,
            np.clip(-result["trade_pressure_score"], 0.0, None),
            0.0,
        )

        for _col in ["buy_qty", "sell_qty", "buy_quote", "sell_quote", "large_buy_qty", "large_sell_qty", "large_buy_count", "large_sell_count", "price_first", "price_last", "price_max", "price_min", "total_volume", "total_value", "num_trades", "max_trade_size"]:
            if _col in grouped.columns:
                del grouped[_col]
        gc.collect()

        result["timestamp"] = result.index
        result["symbol"] = ""
        result["exchange"] = ""

        result = result.reset_index(drop=True)
        result = result[TRADE_FEATURE_COLUMNS]

        for col in result.select_dtypes(include=["float64"]).columns:
            result[col] = result[col].astype(np.float32)

        return result


def _aggregate_single_month(
    exchange: str, symbol: str, year: int, month: int, timeframe: str
) -> pd.DataFrame:
    from infrastructure.storage.data_lake.raw_trade_reader import RawTradeReader

    reader = RawTradeReader()
    trades = reader.load_month(exchange, symbol, year, month)
    if trades is not None and len(trades) > 0:
        trades = MemoryOptimizer.optimize_dtypes(trades)
    if trades is None or len(trades) == 0:
        return pd.DataFrame(columns=TRADE_FEATURE_COLUMNS)

    engine = TradeFlowEngine()
    result = engine.aggregate(trades, timeframe)
    result["symbol"] = symbol
    result["exchange"] = exchange

    return result
