import os
from pathlib import Path
from typing import Optional

import pandas as pd


class TradeFlowWriter:

    CANDIDATE_ROOTS = [
        Path(os.environ.get("DATA_LAKE_ROOT", "")),
        Path(__file__).parent.parent.parent.parent / "data_lake",
        Path("E:\\00_crypto\\00_code\\backend\\data_lake"),
    ]

    def __init__(self, root: Optional[Path] = None):
        if root is not None:
            self.root = Path(root)
        else:
            self.root = self._detect_root()

    @classmethod
    def _detect_root(cls) -> Path:
        for candidate in cls.CANDIDATE_ROOTS:
            if candidate.exists() and (candidate / "crypto").exists():
                return candidate
        for candidate in cls.CANDIDATE_ROOTS:
            if candidate.exists():
                return candidate
        return cls.CANDIDATE_ROOTS[1]

    def _build_path(self, exchange: str, symbol: str, timeframe: str) -> Path:
        return (
            self.root
            / "crypto"
            / exchange
            / "trade_flow"
            / f"symbol={symbol}"
            / f"timeframe={timeframe}"
            / "data.parquet"
        )

    def save(self, exchange: str, symbol: str, timeframe: str, df: pd.DataFrame) -> Path:
        path = self._build_path(exchange, symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, engine="pyarrow", compression="zstd", index=False)
        return path

    def load(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        path = self._build_path(exchange, symbol, timeframe)
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path, engine="pyarrow")
        if df.empty:
            return df
        ts_col = None
        for col in ("timestamp", "open_time", "close_time"):
            if col in df.columns:
                ts_col = col
                break
        if ts_col is not None:
            df[ts_col] = pd.to_datetime(df[ts_col])
            if start_ts is not None:
                df = df[df[ts_col] >= pd.Timestamp(start_ts)]
            if end_ts is not None:
                df = df[df[ts_col] <= pd.Timestamp(end_ts)]
        return df.reset_index(drop=True)

    def get_last_timestamp(
        self, exchange: str, symbol: str, timeframe: str
    ) -> Optional[pd.Timestamp]:
        df = self.load(exchange, symbol, timeframe)
        if df.empty:
            return None
        ts_col = None
        for col in ("timestamp", "open_time", "close_time"):
            if col in df.columns:
                ts_col = col
                break
        if ts_col is None:
            return None
        return pd.Timestamp(df[ts_col].max())
