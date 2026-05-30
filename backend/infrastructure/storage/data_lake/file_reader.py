"""
FileDataLakeReader - 文件系统数据湖统一读取器

统一读取 CSV/Parquet 格式的原始数据，支持：
- klines: year=/month= 分层存储 (CSV 无 header + Parquet 有 header)
- oi/funding: 单文件存储
- trades: 分层存储

CSV 与 Parquet 格式差异：
- CSV (2020-2021): 无 header, Binance 标准 12 列, open_time 为 ms 整数
- Parquet (2022+): 有 header, timestamp 为 datetime, 含 exchange/symbol/interval

使用方式：
    reader = FileDataLakeReader()
    klines = reader.load_klines("binance", "BTCUSDT", start_ts, end_ts)
    oi = reader.load_oi("binance", "BTCUSDT", start_ts, end_ts)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd


KLINES_CSV_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count",
    "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]

KLINES_PARQUET_COLUMNS = [
    "timestamp", "exchange", "symbol", "interval",
    "open", "high", "low", "close", "volume",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
]

KLINES_CANONICAL_COLUMNS = [
    "timestamp", "exchange", "symbol", "interval",
    "open", "high", "low", "close", "volume",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
]


class FileDataLakeReader:
    """
    统一文件系统数据湖读取器

    数据目录结构：
        {root}/crypto/{exchange}/{data_type}/symbol={symbol}/
            klines: year=YYYY/month=MM/data.parquet 或 *.csv
            oi: data.parquet (单文件)
            funding: data.parquet (单文件)
            trades: year=YYYY/month=MM/data.parquet

    自动检测路径优先级：
        1. 环境变量 DATA_LAKE_ROOT
        2. ./data_lake (项目相对路径)
        3. E:\\00_crypto\\data_lake (常见 Windows 路径)
        4. /mnt/00_crypto/data_lake (常见 Linux 路径)
    """

    CANDIDATE_ROOTS = [
        Path(os.environ.get("DATA_LAKE_ROOT", "")),
        Path(__file__).parent.parent.parent.parent / "data_lake",
        Path("E:\\00_crypto\\data_lake"),
        Path("/mnt/00_crypto/data_lake"),
    ]

    def __init__(self, root: Optional[Path] = None):
        if root is not None:
            self.root = Path(root)
        else:
            self.root = self._detect_root()

    @classmethod
    def _detect_root(cls) -> Path:
        """自动检测数据湖根目录"""
        for candidate in cls.CANDIDATE_ROOTS:
            if candidate.exists() and (candidate / "crypto").exists():
                return candidate
        for candidate in cls.CANDIDATE_ROOTS:
            if candidate.exists():
                return candidate
        return cls.CANDIDATE_ROOTS[1]

    def _get_klines_path(self, exchange: str, symbol: str) -> Path:
        return self.root / "crypto" / exchange / "klines" / f"symbol={symbol}"

    def _get_oi_path(self, exchange: str, symbol: str) -> Path:
        return self.root / "crypto" / exchange / "oi" / f"symbol={symbol}"

    def _get_funding_path(self, exchange: str, symbol: str) -> Path:
        return self.root / "crypto" / exchange / "funding" / f"symbol={symbol}"

    def _get_trades_path(self, exchange: str, symbol: str) -> Path:
        return self.root / "crypto" / exchange / "trades" / f"symbol={symbol}"

    @staticmethod
    def _normalize_timestamp_col(df: pd.DataFrame, col: str = "timestamp") -> pd.DataFrame:
        """统一 timestamp 列为 tz-naive datetime64[ns]"""
        if col not in df.columns:
            return df
        if df[col].dtype == "object" or str(df[col].dtype).startswith("datetime"):
            df[col] = pd.to_datetime(df[col])
        if hasattr(df[col].dtype, "tz") and df[col].dtype.tz is not None:
            df[col] = df[col].dt.tz_localize(None)
        return df

    @staticmethod
    def _filter_by_time(
        df: pd.DataFrame,
        start_ts: Optional[datetime],
        end_ts: Optional[datetime],
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """按时间范围过滤 DataFrame"""
        if timestamp_col not in df.columns:
            return df
        if start_ts is not None:
            df = df[df[timestamp_col] >= start_ts]
        if end_ts is not None:
            df = df[df[timestamp_col] <= end_ts]
        return df

    def _read_klines_csv(self, csv_path: Path, exchange: str, symbol: str) -> pd.DataFrame:
        """
        读取无 header 的 Binance Kline CSV，规范化为统一列名

        CSV 格式: open_time, open, high, low, close, volume,
                  close_time, quote_volume, count,
                  taker_buy_volume, taker_buy_quote_volume, ignore
        """
        try:
            df = pd.read_csv(csv_path, header=None, names=KLINES_CSV_COLUMNS)
        except Exception:
            return pd.DataFrame()

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
        df["exchange"] = exchange
        df["symbol"] = symbol

        filename = csv_path.stem
        parts = filename.split("-")
        if len(parts) >= 2:
            df["interval"] = parts[1]
        else:
            df["interval"] = "1m"

        df = df.drop(columns=["open_time", "close_time", "ignore"], errors="ignore")

        canonical = [c for c in KLINES_CANONICAL_COLUMNS if c in df.columns]
        extra = [c for c in df.columns if c not in canonical]
        df = df[canonical + extra]

        return df

    def _load_klines_partitioned(
        self,
        base_path: Path,
        exchange: str,
        symbol: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        加载分区存储的 Klines (year=/month= 结构)

        优先读 Parquet，回退读 CSV，输出统一列名。
        """
        if not base_path.exists():
            return pd.DataFrame()

        dfs = []
        for year_dir in sorted(base_path.glob("year=*")):
            for month_dir in sorted(year_dir.glob("month=*")):
                parquet_path = month_dir / "data.parquet"
                csv_files = sorted(month_dir.glob("*.csv"))

                if parquet_path.exists():
                    try:
                        df = pd.read_parquet(parquet_path)
                        if df is not None and not df.empty:
                            self._normalize_timestamp_col(df)
                            dfs.append(df)
                            continue
                    except Exception:
                        pass

                for csv_path in csv_files:
                    df = self._read_klines_csv(csv_path, exchange, symbol)
                    if not df.empty:
                        dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        result = pd.concat(dfs, ignore_index=True)
        self._normalize_timestamp_col(result)
        result = self._filter_by_time(result, start_ts, end_ts)
        if "timestamp" in result.columns:
            result = result.sort_values("timestamp").reset_index(drop=True)
        # 清理多进程安全
        result = self._clean_dataframe_for_multiprocessing(result)
        return result

    def _load_partitioned_parquet(
        self,
        base_path: Path,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """加载分区存储的 Parquet (year=/month= 结构)"""
        if not base_path.exists():
            return pd.DataFrame()

        dfs = []
        for parquet_path in sorted(base_path.glob("year=*/month=*/data.parquet")):
            try:
                df = pd.read_parquet(parquet_path)
                if df is not None and not df.empty:
                    self._normalize_timestamp_col(df, timestamp_col)
                    dfs.append(df)
            except Exception:
                continue

        if not dfs:
            return pd.DataFrame()

        result = pd.concat(dfs, ignore_index=True)
        self._normalize_timestamp_col(result, timestamp_col)
        result = self._filter_by_time(result, start_ts, end_ts, timestamp_col)
        if timestamp_col in result.columns:
            result = result.sort_values(timestamp_col).reset_index(drop=True)
        return result

    def _load_flat_parquet(
        self,
        base_path: Path,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """加载单文件 Parquet"""
        parquet_path = base_path / "data.parquet"
        if not parquet_path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_parquet(parquet_path)
            if df is None or df.empty:
                return pd.DataFrame()
            self._normalize_timestamp_col(df, timestamp_col)
            df = self._filter_by_time(df, start_ts, end_ts, timestamp_col)
            if timestamp_col in df.columns:
                df = df.sort_values(timestamp_col).reset_index(drop=True)
            # 清理多进程安全
            df = self._clean_dataframe_for_multiprocessing(df)
            return df
        except Exception:
            return pd.DataFrame()

    def load_klines(
        self,
        exchange: str,
        symbol: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        timeframe: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        加载 K线数据

        自动检测 CSV/Parquet 格式，输出统一列名：
        timestamp, exchange, symbol, interval, open, high, low, close, volume, ...

        Args:
            exchange: 交易所，如 "binance"
            symbol: 交易对，如 "BTCUSDT"
            start_ts: 开始时间
            end_ts: 结束时间
            timeframe: K线周期，如 "1m", "5m", "15m", "1h", "4h"
        """
        path = self._get_klines_path(exchange, symbol)
        df = self._load_klines_partitioned(path, exchange, symbol, start_ts, end_ts)

        if df.empty:
            return df

        if timeframe is not None and "interval" in df.columns:
            df = df[df["interval"] == timeframe]

        return df

    def load_oi(
        self,
        exchange: str,
        symbol: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        加载持仓量数据

        Returns:
            OI DataFrame，列：timestamp, exchange, symbol, sumOpenInterest, sumOpenInterestValue
        """
        path = self._get_oi_path(exchange, symbol)
        return self._load_flat_parquet(path, start_ts, end_ts)

    def load_funding(
        self,
        exchange: str,
        symbol: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        加载资金费率数据

        Returns:
            Funding DataFrame，列：timestamp, exchange, symbol, fundingTime, fundingRate, markPrice
        """
        path = self._get_funding_path(exchange, symbol)
        return self._load_flat_parquet(path, start_ts, end_ts)

    def load_trades(
        self,
        exchange: str,
        symbol: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        加载交易数据

        Returns:
            Trades DataFrame
        """
        path = self._get_trades_path(exchange, symbol)
        return self._load_partitioned_parquet(path, start_ts, end_ts)

    def load_all_derivatives(
        self,
        exchange: str,
        symbol: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        一次性加载所有衍生品数据 (OI + Funding)

        Returns:
            {"oi": DataFrame, "funding": DataFrame}
        """
        return {
            "oi": self.load_oi(exchange, symbol, start_ts, end_ts),
            "funding": self.load_funding(exchange, symbol, start_ts, end_ts),
        }

    def _convert_arrow_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换 pyarrow 类型为标准 pandas 类型，避免多进程传递问题
        
        解决 Windows 上 pyarrow 类型 + multiprocessing.spawn 导致的 Access Violation 问题
        """
        if df.empty:
            return df
        
        df = df.copy()
        
        for col in df.columns:
            # 转换 Arrow 字符串类型为标准字符串
            if hasattr(df[col].dtype, '__module__') and 'pyarrow' in df[col].dtype.__module__:
                try:
                    df[col] = df[col].astype(str)
                except Exception:
                    pass
            elif str(df[col].dtype).startswith('string[pyarrow]'):
                try:
                    df[col] = df[col].astype(str)
                except Exception:
                    pass
            # 转换 Arrow 日期时间类型
            elif str(df[col].dtype).startswith('timestamp') and hasattr(df[col].dtype, '__module__') and 'pyarrow' in df[col].dtype.__module__:
                try:
                    df[col] = pd.to_datetime(df[col])
                except Exception:
                    pass
            # 确保所有 object 类型列安全
            elif df[col].dtype == 'object':
                try:
                    # 尝试转换为字符串
                    df[col] = df[col].astype(str)
                except Exception:
                    pass
        
        return df
    
    def _clean_dataframe_for_multiprocessing(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清理 DataFrame 以确保在 Windows 多进程中安全传递
        
        包括:
        - 转换 Arrow 类型
        - 确保所有类型都是标准类型
        - 避免 Access Violation (0xC0000005)
        """
        if df.empty:
            return df
        
        df = df.copy()
        df = self._convert_arrow_types(df)
        
        return df
    
    def get_available_symbols(
        self,
        exchange: str,
        data_type: str = "klines",
    ) -> List[str]:
        """
        获取可用的交易对列表

        Args:
            exchange: 交易所
            data_type: 数据类型 (klines, oi, funding, trades)

        Returns:
            交易对列表
        """
        data_root = self.root / "crypto" / exchange / data_type
        if not data_root.exists():
            return []

        symbols = []
        for item in data_root.iterdir():
            if item.is_dir() and item.name.startswith("symbol="):
                symbols.append(item.name.replace("symbol=", ""))
        return sorted(symbols)

    def read_klines(
        self,
        exchange: str,
        symbol: str,
        timeframe: Optional[str] = "1h",
        days: Optional[int] = None,
    ) -> pd.DataFrame:
        """read_klines 是 load_klines 的别名（向后兼容）"""
        start_ts = None
        end_ts = None
        if days is not None:
            from datetime import timedelta
            end_ts = datetime.now()
            start_ts = end_ts - timedelta(days=days)
        
        df = self.load_klines(exchange, symbol, start_ts, end_ts, None)
        
        if df.empty:
            return df
        
        if timeframe and timeframe != "1m":
            if "interval" in df.columns:
                df_1m = df[df["interval"] == "1m"]
                if not df_1m.empty:
                    print(f"  [FileDataLakeReader] 从 1m 数据重采样到 {timeframe}...")
                    df_1m = self._resample_klines(df_1m, timeframe)
                    return df_1m
                else:
                    existing_intervals = df["interval"].unique() if "interval" in df.columns else []
                    print(f"  [FileDataLakeReader] 警告: 没有找到 1m 数据，现有 interval: {existing_intervals}")
                    return pd.DataFrame()
            else:
                print(f"  [FileDataLakeReader] 警告: 数据中没有 interval 列，尝试直接从 1m 重采样...")
                return self._resample_klines(df, timeframe)
        elif "interval" in df.columns:
            df = df[df["interval"] == timeframe]
        
        return df
    
    def _resample_klines(self, df: pd.DataFrame, target: str) -> pd.DataFrame:
        """
        将 K线数据从 1m 重采样到目标周期
        
        Args:
            df: 1m K线数据
            target: 目标周期，如 "1h", "4h", "1d"
        
        Returns:
            重采样后的 K线数据
        """
        if df.empty:
            return df
        
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        resample_map = {
            "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
            "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"
        }
        
        window_str = resample_map.get(target, "1h")
        
        df = df.set_index("timestamp").sort_index()
        resampled = df.resample(window_str).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna(subset=["close"])
        
        resampled = resampled.reset_index()
        
        for col in ["open", "high", "low", "close", "volume"]:
            if col in resampled.columns:
                resampled[col] = resampled[col].astype(float)
        
        resampled["interval"] = target
        
        return resampled

    def read_funding(
        self,
        exchange: str,
        symbol: str,
        timeframe: Optional[str] = "1h",
        klines: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """read_funding 是 load_funding 的别名（向后兼容）"""
        start_ts = klines["timestamp"].min() if klines is not None and not klines.empty else None
        end_ts = klines["timestamp"].max() if klines is not None and not klines.empty else None
        return self.load_funding(exchange, symbol, start_ts, end_ts)

    def read_open_interest(
        self,
        exchange: str,
        symbol: str,
        timeframe: Optional[str] = "1h",
        klines: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """read_open_interest 是 load_oi 的别名（向后兼容）"""
        start_ts = klines["timestamp"].min() if klines is not None and not klines.empty else None
        end_ts = klines["timestamp"].max() if klines is not None and not klines.empty else None
        return self.load_oi(exchange, symbol, start_ts, end_ts)

    def read_orderbook(
        self,
        exchange: str,
        symbol: str,
        timeframe: Optional[str] = "1h",
        klines: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """read_orderbook 当前返回空 DataFrame（占位符）"""
        return pd.DataFrame()

    def read_liquidations(
        self,
        exchange: str,
        symbol: str,
        timeframe: Optional[str] = "1h",
        klines: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """read_liquidations 当前返回空 DataFrame（占位符）"""
        return pd.DataFrame()


_file_reader: Optional[FileDataLakeReader] = None


def get_file_reader() -> FileDataLakeReader:
    """获取全局 FileDataLakeReader 实例"""
    global _file_reader
    if _file_reader is None:
        _file_reader = FileDataLakeReader()
    return _file_reader
