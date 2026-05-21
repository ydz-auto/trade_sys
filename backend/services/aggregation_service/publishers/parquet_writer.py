"""
Parquet Writer - OrderBook特征Parquet存储（70G优化版）

1秒特征快照存储，支持：
- BTC + ETH
- parquet + zstd压缩
- 分区存储（按日期）
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pathlib import Path
import asyncio
from collections import defaultdict

from infrastructure.logging import get_logger
from services.aggregation_service.models.orderbook_model import OrderBookFeature

logger = get_logger("aggregation_service.parquet_writer")

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False
    logger.warning("pyarrow not installed, parquet storage disabled")


def _get_default_base_path() -> str:
    """获取默认的基础路径"""
    try:
        from infrastructure.data_lake import get_data_lake_subpath
        return str(get_data_lake_subpath("orderbook_features"))
    except ImportError:
        return "data_lake/orderbook_features"


class OrderBookFeatureParquetWriter:
    """OrderBook特征Parquet写入器
    
    存储策略：
    - 1秒快照
    - 按日期分区
    - 按交易对分文件
    - zstd压缩
    """
    
    SCHEMA = pa.schema([
        ('timestamp', pa.int64()),
        ('datetime', pa.timestamp('ms')),
        ('exchange', pa.string()),
        ('symbol', pa.string()),
        
        ('best_bid', pa.float64()),
        ('best_ask', pa.float64()),
        ('spread', pa.float64()),
        ('spread_pct', pa.float64()),
        ('mid_price', pa.float64()),
        ('microprice', pa.float64()),
        
        ('imbalance_1', pa.float64()),
        ('imbalance_5', pa.float64()),
        ('imbalance_10', pa.float64()),
        ('imbalance_slope', pa.float64()),
        
        ('top5_bid_volume', pa.float64()),
        ('top5_ask_volume', pa.float64()),
        ('top10_bid_volume', pa.float64()),
        ('top10_ask_volume', pa.float64()),
        ('depth_ratio', pa.float64()),
        ('depth_change', pa.float64()),
        
        ('trade_delta', pa.float64()),
        ('cumulative_delta', pa.float64()),
        ('aggressive_buy_volume', pa.float64()),
        ('aggressive_sell_volume', pa.float64()),
        ('large_trade_ratio', pa.float64()),
        ('trade_velocity', pa.float64()),
        ('total_volume', pa.float64()),
        ('total_value', pa.float64()),
        ('avg_trade_size', pa.float64()),
        ('buy_sell_ratio', pa.float64()),
        ('trade_intensity', pa.float64()),
        ('vwap', pa.float64()),
        ('max_trade_size', pa.float64()),
        ('min_trade_size', pa.float64()),
        ('price_impact', pa.float64()),
        
        ('sweep_buy_score', pa.float64()),
        ('sweep_sell_score', pa.float64()),
        ('multi_level_fill', pa.int32()),
        ('liquidity_vacuum', pa.float64()),
        
        ('spread_volatility', pa.float64()),
        ('quote_update_rate', pa.float64()),
        ('cancel_rate', pa.float64()),
        ('book_flip_rate', pa.float64()),
        ('book_pressure', pa.float64()),
    ])
    
    def __init__(
        self,
        base_path: str = None,
        buffer_size: int = 1000,
        flush_interval_seconds: int = 60
    ):
        if not HAS_PARQUET:
            raise RuntimeError("pyarrow not installed")
        
        if base_path is None:
            base_path = _get_default_base_path()
        self.base_path = Path(base_path)
        self.buffer_size = buffer_size
        self.flush_interval_seconds = flush_interval_seconds
        
        self.buffer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.last_flush_time: Dict[str, float] = {}
        
        self._ensure_base_path()
    
    def _ensure_base_path(self):
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(
        self, 
        exchange: str, 
        symbol: str, 
        dt: datetime
    ) -> Path:
        date_str = dt.strftime("%Y%m%d")
        symbol_safe = symbol.replace("/", "_").replace("-", "_")
        
        dir_path = self.base_path / exchange / symbol_safe / f"date={date_str}"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        return dir_path / "features.parquet"
    
    def add_feature(self, feature: OrderBookFeature) -> bool:
        key = f"{feature.exchange}:{feature.symbol}"
        
        row = {
            'timestamp': feature.timestamp,
            'datetime': datetime.fromtimestamp(feature.timestamp / 1000),
            'exchange': feature.exchange,
            'symbol': feature.symbol,
            
            'best_bid': feature.mid_price - feature.spread / 2 if feature.spread else 0,
            'best_ask': feature.mid_price + feature.spread / 2 if feature.spread else 0,
            'spread': feature.spread,
            'spread_pct': feature.spread_pct,
            'mid_price': feature.mid_price,
            'microprice': feature.microprice,
            
            'imbalance_1': feature.imbalance_1,
            'imbalance_5': feature.imbalance_5,
            'imbalance_10': feature.imbalance_10,
            'imbalance_slope': feature.imbalance_slope,
            
            'top5_bid_volume': feature.top5_bid_volume,
            'top5_ask_volume': feature.top5_ask_volume,
            'top10_bid_volume': feature.top10_bid_volume,
            'top10_ask_volume': feature.top10_ask_volume,
            'depth_ratio': feature.depth_ratio,
            'depth_change': feature.depth_change,
            
            'trade_delta': feature.trade_delta,
            'cumulative_delta': feature.cumulative_delta,
            'aggressive_buy_volume': feature.aggressive_buy_volume,
            'aggressive_sell_volume': feature.aggressive_sell_volume,
            'large_trade_ratio': feature.large_trade_ratio,
            'trade_velocity': feature.trade_velocity,
            'total_volume': feature.total_volume,
            'total_value': feature.total_value,
            'avg_trade_size': feature.avg_trade_size,
            'buy_sell_ratio': feature.buy_sell_ratio,
            'trade_intensity': feature.trade_intensity,
            'vwap': feature.vwap,
            'max_trade_size': feature.max_trade_size,
            'min_trade_size': feature.min_trade_size,
            'price_impact': feature.price_impact,
            
            'sweep_buy_score': feature.sweep_buy_score,
            'sweep_sell_score': feature.sweep_sell_score,
            'multi_level_fill': feature.multi_level_fill,
            'liquidity_vacuum': feature.liquidity_vacuum,
            
            'spread_volatility': feature.spread_volatility,
            'quote_update_rate': feature.quote_update_rate,
            'cancel_rate': feature.cancel_rate,
            'book_flip_rate': feature.book_flip_rate,
            'book_pressure': feature.book_pressure,
        }
        
        self.buffer[key].append(row)
        
        if len(self.buffer[key]) >= self.buffer_size:
            return self._flush_buffer(key)
        
        return False
    
    def _flush_buffer(self, key: str) -> bool:
        if key not in self.buffer or not self.buffer[key]:
            return False
        
        rows = self.buffer[key]
        exchange, symbol = key.split(":")
        
        try:
            df = pd.DataFrame(rows)
            
            dt = datetime.fromtimestamp(rows[0]['timestamp'] / 1000)
            file_path = self._get_file_path(exchange, symbol, dt)
            
            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=['timestamp'], keep='last')
                df = df.sort_values('timestamp').reset_index(drop=True)
            
            table = pa.Table.from_pandas(df, schema=self.SCHEMA, preserve_index=False)
            
            pq.write_table(
                table,
                file_path,
                compression='zstd',
                compression_level=3,
            )
            
            logger.debug(f"Flushed {len(rows)} features to {file_path}")
            
            self.buffer[key] = []
            self.last_flush_time[key] = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to flush buffer for {key}: {e}")
            return False
    
    def flush_all(self) -> int:
        flushed = 0
        for key in list(self.buffer.keys()):
            if self._flush_buffer(key):
                flushed += 1
        return flushed
    
    def read_features(
        self,
        exchange: str,
        symbol: str,
        start_time: int,
        end_time: int
    ) -> Optional[pd.DataFrame]:
        symbol_safe = symbol.replace("/", "_").replace("-", "_")
        
        start_dt = datetime.fromtimestamp(start_time / 1000)
        end_dt = datetime.fromtimestamp(end_time / 1000)
        
        dfs = []
        current_date = start_dt.date()
        end_date = end_dt.date()
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            file_path = self.base_path / exchange / symbol_safe / f"date={date_str}" / "features.parquet"
            
            if file_path.exists():
                try:
                    df = pd.read_parquet(file_path)
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Failed to read {file_path}: {e}")
            
            from datetime import timedelta
            current_date += timedelta(days=1)
        
        if not dfs:
            return None
        
        result = pd.concat(dfs, ignore_index=True)
        result = result[
            (result['timestamp'] >= start_time) & 
            (result['timestamp'] <= end_time)
        ]
        result = result.sort_values('timestamp').reset_index(drop=True)
        
        return result
    
    def get_storage_stats(self) -> Dict[str, Any]:
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'symbols': {},
        }
        
        for exchange_dir in self.base_path.iterdir():
            if not exchange_dir.is_dir():
                continue
            
            for symbol_dir in exchange_dir.iterdir():
                if not symbol_dir.is_dir():
                    continue
                
                symbol_key = f"{exchange_dir.name}:{symbol_dir.name}"
                symbol_size = 0
                file_count = 0
                
                for date_dir in symbol_dir.iterdir():
                    if not date_dir.is_dir():
                        continue
                    
                    for f in date_dir.glob("*.parquet"):
                        symbol_size += f.stat().st_size
                        file_count += 1
                
                stats['symbols'][symbol_key] = {
                    'size_mb': symbol_size / (1024 * 1024),
                    'file_count': file_count,
                }
                stats['total_files'] += file_count
                stats['total_size_mb'] += symbol_size / (1024 * 1024)
        
        return stats


_writer: Optional[OrderBookFeatureParquetWriter] = None


def get_parquet_writer(
    base_path: str = None
) -> OrderBookFeatureParquetWriter:
    global _writer
    if _writer is None:
        if not HAS_PARQUET:
            raise RuntimeError("pyarrow not installed")
        _writer = OrderBookFeatureParquetWriter(base_path=base_path)
    return _writer
