"""
Market Data Repository - 市场数据仓储

包含所有业务查询逻辑。
Repository 才懂业务表结构。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

from infrastructure.storage.interfaces import AsyncStorageAdapter


class MarketDataRepository:
    """
    市场数据仓储
    
    职责：
    - 业务表查询
    - 数据转换
    - 表名映射
    
    不包含：
    - SQL 执行细节（委托给 StorageAdapter）
    - 特征计算（委托给 FeatureEngine）
    """
    
    def __init__(self, storage: AsyncStorageAdapter):
        self.storage = storage
    
    async def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        获取 K 线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_ts: 开始时间戳（毫秒）
            end_ts: 结束时间戳（毫秒）
        
        Returns:
            pd.DataFrame: K 线数据
        """
        sql = """
        SELECT
            ts,
            symbol,
            timeframe,
            open,
            high,
            low,
            close,
            volume
        FROM klines
        WHERE symbol = %(symbol)s
          AND timeframe = %(timeframe)s
          AND ts >= %(start_ts)s
          AND ts < %(end_ts)s
        ORDER BY ts
        """
        
        rows = await self.storage.fetch(sql, {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_ts": start_ts,
            "end_ts": end_ts,
        })
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        if "ts" in df.columns:
            df["timestamp"] = pd.to_datetime(df["ts"], unit="ms")
        return df
    
    async def get_open_interest(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        获取持仓量数据
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 持仓量数据
        """
        sql = """
        SELECT
            ts,
            symbol,
            exchange,
            open_interest
        FROM open_interest
        WHERE symbol = %(symbol)s
          AND ts >= %(start_ts)s
          AND ts < %(end_ts)s
        ORDER BY ts
        """
        
        rows = await self.storage.fetch(sql, {
            "symbol": symbol,
            "start_ts": start_ts,
            "end_ts": end_ts,
        })
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)
    
    async def get_funding_rates(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        获取资金费率数据
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 资金费率数据
        """
        sql = """
        SELECT
            ts,
            symbol,
            exchange,
            funding_rate
        FROM funding_rates
        WHERE symbol = %(symbol)s
          AND ts >= %(start_ts)s
          AND ts < %(end_ts)s
        ORDER BY ts
        """
        
        rows = await self.storage.fetch(sql, {
            "symbol": symbol,
            "start_ts": start_ts,
            "end_ts": end_ts,
        })
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)
    
    async def get_liquidations(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        获取强平数据
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 强平数据
        """
        sql = """
        SELECT
            ts,
            symbol,
            side,
            size,
            price
        FROM liquidations
        WHERE symbol = %(symbol)s
          AND ts >= %(start_ts)s
          AND ts < %(end_ts)s
        ORDER BY ts
        """
        
        rows = await self.storage.fetch(sql, {
            "symbol": symbol,
            "start_ts": start_ts,
            "end_ts": end_ts,
        })
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)
    
    async def get_trades(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        limit: int = 10000,
    ) -> pd.DataFrame:
        """
        获取成交数据
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
            limit: 返回数量限制
        
        Returns:
            pd.DataFrame: 成交数据
        """
        sql = """
        SELECT
            ts,
            symbol,
            side,
            price,
            size
        FROM trades
        WHERE symbol = %(symbol)s
          AND ts >= %(start_ts)s
          AND ts < %(end_ts)s
        ORDER BY ts
        LIMIT %(limit)s
        """
        
        rows = await self.storage.fetch(sql, {
            "symbol": symbol,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "limit": limit,
        })
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)
    
    async def get_orderbook_snapshots(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        """
        获取订单簿快照
        
        Args:
            symbol: 交易对
            start_ts: 开始时间戳
            end_ts: 结束时间戳
        
        Returns:
            pd.DataFrame: 订单簿快照数据
        """
        sql = """
        SELECT
            ts,
            symbol,
            bids,
            asks
        FROM orderbook_snapshots
        WHERE symbol = %(symbol)s
          AND ts >= %(start_ts)s
          AND ts < %(end_ts)s
        ORDER BY ts
        """
        
        rows = await self.storage.fetch(sql, {
            "symbol": symbol,
            "start_ts": start_ts,
            "end_ts": end_ts,
        })
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows)


class MockMarketDataRepository(MarketDataRepository):
    """
    Mock 市场数据仓储（用于测试）
    """
    
    def __init__(self):
        super().__init__(None)
        self._klines_data: Dict[str, pd.DataFrame] = {}
    
    async def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
    ) -> pd.DataFrame:
        key = f"{symbol}_{timeframe}"
        if key in self._klines_data:
            df = self._klines_data[key]
            return df[(df["ts"] >= start_ts) & (df["ts"] < end_ts)]
        return pd.DataFrame()
    
    def set_klines(self, symbol: str, timeframe: str, df: pd.DataFrame):
        key = f"{symbol}_{timeframe}"
        self._klines_data[key] = df.copy()


__all__ = [
    "MarketDataRepository",
    "MockMarketDataRepository",
]
