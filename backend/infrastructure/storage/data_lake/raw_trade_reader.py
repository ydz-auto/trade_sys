import os
import re
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import pandas as pd

from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

TRADE_COLUMNS = [
    "timestamp",
    "price",
    "qty",
    "quote_qty",
    "is_buyer_maker",
]


class RawTradeReader:

    CANDIDATE_ROOTS = [
        Path(os.environ.get("DATA_LAKE_ROOT", "")),
        Path(__file__).parent.parent.parent.parent / "data_lake",
        Path("E:\\00_crypto\\00_code\\backend\\data_lake"),
        Path("/mnt/00_crypto/data_lake"),
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

    def _get_trades_base_path(self, exchange: str, symbol: str) -> Path:
        return self.root / "crypto" / exchange / "trades" / f"symbol={symbol}"

    def _get_month_path(self, exchange: str, symbol: str, year: int, month: int) -> Path:
        return (
            self._get_trades_base_path(exchange, symbol)
            / f"year={year}"
            / f"month={month:02d}"
            / "data.parquet"
        )

    @staticmethod
    def _normalize_timestamp(df: pd.DataFrame) -> pd.DataFrame:
        if "timestamp" not in df.columns:
            return df
        if df["timestamp"].dtype == "object" or str(df["timestamp"].dtype).startswith("datetime"):
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        if hasattr(df["timestamp"].dtype, "tz") and df["timestamp"].dtype.tz is not None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        return df

    def load_month(self, exchange: str, symbol: str, year: int, month: int) -> pd.DataFrame:
        parquet_path = self._get_month_path(exchange, symbol, year, month)
        if not parquet_path.exists():
            return pd.DataFrame(columns=TRADE_COLUMNS)

        try:
            df = pd.read_parquet(parquet_path, columns=TRADE_COLUMNS)
            if df is None or df.empty:
                return pd.DataFrame(columns=TRADE_COLUMNS)
            self._normalize_timestamp(df)
            if "timestamp" in df.columns:
                df = df.sort_values("timestamp").reset_index(drop=True)
            return df
        except Exception:
            return pd.DataFrame(columns=TRADE_COLUMNS)

    def list_available_months(self, exchange: str, symbol: str) -> List[Tuple[int, int]]:
        base_path = self._get_trades_base_path(exchange, symbol)
        if not base_path.exists():
            return []

        year_pattern = re.compile(r"^year=(\d{4})$")
        month_pattern = re.compile(r"^month=(\d{2})$")

        result: List[Tuple[int, int]] = []
        for year_dir in sorted(base_path.iterdir()):
            year_match = year_pattern.match(year_dir.name)
            if not year_match or not year_dir.is_dir():
                continue
            year_val = int(year_match.group(1))
            for month_dir in sorted(year_dir.iterdir()):
                month_match = month_pattern.match(month_dir.name)
                if not month_match or not month_dir.is_dir():
                    continue
                month_val = int(month_match.group(1))
                parquet_path = month_dir / "data.parquet"
                if parquet_path.exists():
                    result.append((year_val, month_val))

        return result

    def load_month_range(
        self,
        exchange: str,
        symbol: str,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> Iterator[pd.DataFrame]:
        year = start_year
        month = start_month

        while (year, month) <= (end_year, end_month):
            df = self.load_month(exchange, symbol, year, month)
            if not df.empty:
                yield df
            month += 1
            if month > 12:
                month = 1
                year += 1
