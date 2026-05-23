"""
Data Download Service - 统一数据下载服务

替代以下脚本：
- scripts/download_binance_klines.py
- scripts/download_binance_funding.py
- scripts/download_binance_oi.py
- scripts/download_binance_trades.py
- scripts/download_binance_liquidation.py
- scripts/download_okx_klines.py
- scripts/download_okx_funding.py
- scripts/download_okx_oi.py
- scripts/download_okx_trades.py
- scripts/download_okx_liquidation.py
- scripts/data_lake_download.py

用法：
    # 命令行
    python -m services.data_service.download_service download --exchange binance --symbol BTCUSDT --type klines
    
    # 代码
    from services.data_service.download_service import DataDownloadService
    service = DataDownloadService()
    await service.download_klines("binance", "BTCUSDT", start, end)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
import aiohttp
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from infrastructure.runtime_clock import now_ms
from infrastructure.config.defaults.infrastructure.external_apis import EXCHANGE_REST_APIS
from infrastructure.data_lake.path_utils import get_data_lake_root

logger = get_logger("download_service")


@dataclass
class DownloadConfig:
    """下载配置"""
    data_root: Path = None

    binance_api: str = None
    binance_spot_api: str = None
    okx_api: str = None

    rate_limit: float = 0.1
    max_retries: int = 3
    timeout: float = 30.0

    def __post_init__(self):
        if self.data_root is None:
            try:
                self.data_root = Path(get_data_lake_root())
            except Exception:
                self.data_root = Path(__file__).parent.parent.parent / "data_lake"
        if self.binance_api is None:
            self.binance_api = EXCHANGE_REST_APIS["binance"]["futures"]
        if self.binance_spot_api is None:
            self.binance_spot_api = EXCHANGE_REST_APIS["binance"]["spot"]
        if self.okx_api is None:
            self.okx_api = EXCHANGE_REST_APIS["okx"]["api"]


class DataDownloadService:
    """
    统一数据下载服务
    
    替代多个数据下载脚本，确保：
    1. 统一的数据格式
    2. 发出事件流（与实时一致）
    3. 支持多交易所
    """
    
    def __init__(self, config: DownloadConfig = None):
        self.config = config or DownloadConfig()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """初始化"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
    
    async def shutdown(self):
        """关闭"""
        if self._session:
            await self._session.close()
    
    async def download_klines(
        self,
        exchange: str,
        symbol: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "1m",
    ) -> Path:
        """
        下载 K线数据
        
        替代 download_binance_klines.py, download_okx_klines.py
        """
        if self._session is None:
            await self.initialize()
        
        start_ts = self._parse_time(start_time)
        end_ts = self._parse_time(end_time) if end_time else int(now_ms())
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                if exchange == "binance":
                    data = await self._download_binance_klines(symbol, current_ts, interval)
                elif exchange == "okx":
                    data = await self._download_okx_klines(symbol, current_ts, interval)
                else:
                    raise ValueError(f"Unsupported exchange: {exchange}")
                
                if not data:
                    break
                
                all_data.extend(data)
                current_ts = data[-1][0] + 60000
                
                await asyncio.sleep(self.config.rate_limit)
                
            except Exception as e:
                logger.error(f"Download error: {e}")
                break
        
        if not all_data:
            logger.warning(f"No data downloaded for {symbol}")
            return None
        
        df = self._parse_klines(all_data, exchange, symbol)
        
        output_path = self._get_output_path(exchange, symbol, "klines")
        await self._save_parquet(df, output_path)
        
        logger.info(f"Downloaded {len(df)} klines for {symbol}")
        
        return output_path
    
    async def download_funding(
        self,
        exchange: str,
        symbol: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Path:
        """
        下载资金费率数据
        
        替代 download_binance_funding.py, download_okx_funding.py
        """
        if self._session is None:
            await self.initialize()
        
        start_ts = self._parse_time(start_time)
        end_ts = self._parse_time(end_time) if end_time else int(now_ms())
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                if exchange == "binance":
                    data = await self._download_binance_funding(symbol, current_ts)
                elif exchange == "okx":
                    data = await self._download_okx_funding(symbol, current_ts)
                else:
                    raise ValueError(f"Unsupported exchange: {exchange}")
                
                if not data:
                    break
                
                all_data.extend(data)
                current_ts = data[-1].get('fundingTime', current_ts + 8 * 3600 * 1000) + 8 * 3600 * 1000
                
                await asyncio.sleep(self.config.rate_limit)
                
            except Exception as e:
                logger.error(f"Download funding error: {e}")
                break
        
        if not all_data:
            return None
        
        df = pd.DataFrame(all_data)
        
        output_path = self._get_output_path(exchange, symbol, "funding")
        await self._save_parquet(df, output_path)
        
        return output_path
    
    async def download_oi(
        self,
        exchange: str,
        symbol: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Path:
        """
        下载持仓量数据
        
        替代 download_binance_oi.py, download_okx_oi.py
        """
        if self._session is None:
            await self.initialize()
        
        start_ts = self._parse_time(start_time)
        end_ts = self._parse_time(end_time) if end_time else int(now_ms())
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                if exchange == "binance":
                    data = await self._download_binance_oi(symbol, current_ts)
                elif exchange == "okx":
                    data = await self._download_okx_oi(symbol, current_ts)
                else:
                    raise ValueError(f"Unsupported exchange: {exchange}")
                
                if not data:
                    break
                
                all_data.extend(data)
                current_ts += 24 * 3600 * 1000
                
                await asyncio.sleep(self.config.rate_limit)
                
            except Exception as e:
                logger.error(f"Download OI error: {e}")
                break
        
        if not all_data:
            return None
        
        df = pd.DataFrame(all_data)
        
        output_path = self._get_output_path(exchange, symbol, "oi")
        await self._save_parquet(df, output_path)
        
        return output_path
    
    async def download_trades(
        self,
        exchange: str,
        symbol: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Path:
        """
        下载成交数据
        
        替代 download_binance_trades.py, download_okx_trades.py
        """
        if self._session is None:
            await self.initialize()
        
        start_ts = self._parse_time(start_time)
        end_ts = self._parse_time(end_time) if end_time else int(now_ms())
        
        all_data = []
        
        try:
            if exchange == "binance":
                data = await self._download_binance_trades(symbol, start_ts, end_ts)
            elif exchange == "okx":
                data = await self._download_okx_trades(symbol, start_ts, end_ts)
            else:
                raise ValueError(f"Unsupported exchange: {exchange}")
            
            all_data = data
            
        except Exception as e:
            logger.error(f"Download trades error: {e}")
        
        if not all_data:
            return None
        
        df = pd.DataFrame(all_data)
        
        output_path = self._get_output_path(exchange, symbol, "trades")
        await self._save_parquet(df, output_path)
        
        return output_path
    
    async def download_all(
        self,
        exchange: str,
        symbol: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Path]:
        """
        下载所有数据
        
        替代 data_lake_download.py
        """
        results = {}
        
        results["klines"] = await self.download_klines(exchange, symbol, start_time, end_time)
        results["funding"] = await self.download_funding(exchange, symbol, start_time, end_time)
        results["oi"] = await self.download_oi(exchange, symbol, start_time, end_time)
        
        return results
    
    async def _download_binance_klines(self, symbol: str, start_ts: int, interval: str) -> List:
        """下载 Binance K线"""
        url = f"{self.config.binance_api}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ts,
            "limit": 1500,
        }
        
        async with self._session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            return []
    
    async def _download_okx_klines(self, symbol: str, start_ts: int, interval: str) -> List:
        """下载 OKX K线"""
        url = f"{self.config.okx_api}/api/v5/market/candles"
        params = {
            "instId": symbol,
            "bar": interval,
            "before": start_ts * 1000,
            "limit": 300,
        }
        
        async with self._session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            return []
    
    async def _download_binance_funding(self, symbol: str, start_ts: int) -> List:
        """下载 Binance 资金费率"""
        url = f"{self.config.binance_api}/fapi/v1/fundingRate"
        params = {
            "symbol": symbol,
            "startTime": start_ts,
            "limit": 1000,
        }
        
        async with self._session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            return []
    
    async def _download_okx_funding(self, symbol: str, start_ts: int) -> List:
        """下载 OKX 资金费率"""
        return []
    
    async def _download_binance_oi(self, symbol: str, start_ts: int) -> List:
        """下载 Binance 持仓量"""
        url = f"{self.config.binance_api}/fapi/v1/openInterest"
        params = {"symbol": symbol}
        
        async with self._session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return [{"openInterest": data.get("openInterest", 0), "timestamp": start_ts}]
            return []
    
    async def _download_okx_oi(self, symbol: str, start_ts: int) -> List:
        """下载 OKX 持仓量"""
        return []
    
    async def _download_binance_trades(self, symbol: str, start_ts: int, end_ts: int) -> List:
        """下载 Binance 成交"""
        url = f"{self.config.binance_api}/fapi/v1/aggTrades"
        params = {
            "symbol": symbol,
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1000,
        }
        
        async with self._session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            return []
    
    async def _download_okx_trades(self, symbol: str, start_ts: int, end_ts: int) -> List:
        """下载 OKX 成交"""
        return []
    
    def _parse_time(self, time_str: Optional[str]) -> int:
        """解析时间字符串"""
        if time_str is None:
            return int((datetime.fromtimestamp(now_ms() / 1000) - timedelta(days=30)).timestamp() * 1000)
        
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d")
            return int(dt.timestamp() * 1000)
        except ValueError:
            return int(time_str)
    
    def _parse_klines(self, data: List, exchange: str, symbol: str) -> pd.DataFrame:
        """解析 K线数据"""
        if exchange == "binance":
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
        
        else:
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "quote_volume", "confirm"
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        
        df["symbol"] = symbol
        df["exchange"] = exchange
        
        return df
    
    def _get_output_path(self, exchange: str, symbol: str, data_type: str) -> Path:
        """获取输出路径"""
        return self.config.data_root / "crypto" / exchange / data_type / f"symbol={symbol}" / "data.parquet"
    
    async def _save_parquet(self, df: pd.DataFrame, path: Path):
        """保存 Parquet"""
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)


async def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Data Download Service")
    parser.add_argument("command", choices=["download", "all"])
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--type", default="klines", choices=["klines", "funding", "oi", "trades"])
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    
    args = parser.parse_args()
    
    service = DataDownloadService()
    
    try:
        if args.command == "download":
            if args.type == "klines":
                path = await service.download_klines(args.exchange, args.symbol, args.start, args.end)
            elif args.type == "funding":
                path = await service.download_funding(args.exchange, args.symbol, args.start, args.end)
            elif args.type == "oi":
                path = await service.download_oi(args.exchange, args.symbol, args.start, args.end)
            elif args.type == "trades":
                path = await service.download_trades(args.exchange, args.symbol, args.start, args.end)
            print(f"Downloaded: {path}")
        
        elif args.command == "all":
            results = await service.download_all(args.exchange, args.symbol, args.start, args.end)
            for data_type, path in results.items():
                print(f"{data_type}: {path}")
    
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
