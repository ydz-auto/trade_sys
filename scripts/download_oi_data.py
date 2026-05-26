#!/usr/bin/env python3
"""
OI (Open Interest) 历史数据下载工具

从 Binance 获取 BTCUSDT 的历史 Open Interest 数据
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import requests
import time
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)


class OIDataDownloader:
    """Binance OI 历史数据下载器"""
    
    BASE_URL = "https://fapi.binance.com"
    
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        output_dir: str = None,
    ):
        self.symbol = symbol
        self.interval = "1h"  # 小时级别 OI 数据
        
        if output_dir is None:
            self.output_dir = Path(backend_path) / "data_lake" / "crypto" / "binance" / "oi" / f"symbol={symbol}"
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"OIDataDownloader initialized for {symbol}")
        logger.info(f"Output directory: {self.output_dir}")
    
    def get_top_long_short_account_ratio(
        self,
        period: str = "1h",
        limit: int = 500,
        start_time: int = None,
        end_time: int = None,
    ) -> Optional[pd.DataFrame]:
        """获取多空持仓比率数据"""
        endpoint = f"{self.BASE_URL}/futures/data/topLongShortAccountRatio"
        
        params = {
            "symbol": self.symbol,
            "period": period,
            "limit": limit,
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                logger.warning(f"No data returned for {self.symbol}")
                return None
            
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 转换数值列
            df['longAccount'] = df['longAccount'].astype(float)
            df['shortAccount'] = df['shortAccount'].astype(float)
            df['longShortRatio'] = df['longShortRatio'].astype(float)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching topLongShortAccountRatio: {str(e)}")
            return None
    
    def get_global_long_short_account_ratio(
        self,
        period: str = "1h",
        limit: int = 500,
        start_time: int = None,
        end_time: int = None,
    ) -> Optional[pd.DataFrame]:
        """获取全局多空持仓比率数据"""
        endpoint = f"{self.BASE_URL}/futures/data/globalLongShortAccountRatio"
        
        params = {
            "symbol": self.symbol,
            "period": period,
            "limit": limit,
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                logger.warning(f"No data returned for {self.symbol}")
                return None
            
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 转换数值列
            df['longAccount'] = df['longAccount'].astype(float)
            df['shortAccount'] = df['shortAccount'].astype(float)
            df['longShortRatio'] = df['longShortRatio'].astype(float)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching globalLongShortAccountRatio: {str(e)}")
            return None
    
    def get_top_long_short_position_ratio(
        self,
        period: str = "1h",
        limit: int = 500,
        start_time: int = None,
        end_time: int = None,
    ) -> Optional[pd.DataFrame]:
        """获取多空持仓量比率数据"""
        endpoint = f"{self.BASE_URL}/futures/data/topLongShortPositionRatio"
        
        params = {
            "symbol": self.symbol,
            "period": period,
            "limit": limit,
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                logger.warning(f"No data returned for {self.symbol}")
                return None
            
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 转换数值列
            df['longPositionSide'] = df['longPositionSide'].astype(float)
            df['shortPositionSide'] = df['shortPositionSide'].astype(float)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching topLongShortPositionRatio: {str(e)}")
            return None
    
    def download_historical_data(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, pd.DataFrame]:
        """下载历史数据"""
        start_time = int(start_date.timestamp() * 1000)
        end_time = int(end_date.timestamp() * 1000)
        
        results = {}
        
        # 下载多空持仓比率
        logger.info("Downloading topLongShortAccountRatio...")
        df_account = self.get_top_long_short_account_ratio(
            start_time=start_time,
            end_time=end_time,
            limit=1500,
        )
        if df_account is not None:
            results['topLongShortAccountRatio'] = df_account
            logger.info(f"Downloaded {len(df_account)} rows of account ratio data")
        
        time.sleep(0.5)  # 避免请求过快
        
        # 下载全局多空持仓比率
        logger.info("Downloading globalLongShortAccountRatio...")
        df_global = self.get_global_long_short_account_ratio(
            start_time=start_time,
            end_time=end_time,
            limit=1500,
        )
        if df_global is not None:
            results['globalLongShortAccountRatio'] = df_global
            logger.info(f"Downloaded {len(df_global)} rows of global account ratio data")
        
        time.sleep(0.5)
        
        # 下载多空持仓量比率
        logger.info("Downloading topLongShortPositionRatio...")
        df_position = self.get_top_long_short_position_ratio(
            start_time=start_time,
            end_time=end_time,
            limit=1500,
        )
        if df_position is not None:
            results['topLongShortPositionRatio'] = df_position
            logger.info(f"Downloaded {len(df_position)} rows of position ratio data")
        
        return results
    
    def save_data(self, data: Dict[str, pd.DataFrame], year: int, month: int):
        """保存数据到 parquet 文件"""
        if not data:
            logger.warning(f"No data to save for {year}-{month:02d}")
            return
        
        output_dir = self.output_dir / f"year={year}" / f"month={month:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for name, df in data.items():
            if df is None or len(df) == 0:
                continue
            
            output_path = output_dir / f"{name}.parquet"
            df.to_parquet(output_path, index=False)
            logger.info(f"Saved {len(df)} rows to {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="OI Data Downloader")
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)"
    )
    parser.add_argument(
        "--start-date",
        default="2022-01-01",
        help="Start date (default: 2022-01-01)"
    )
    parser.add_argument(
        "--end-date",
        default="2024-12-31",
        help="End date (default: 2024-12-31)"
    )
    
    args = parser.parse_args()
    
    downloader = OIDataDownloader(symbol=args.symbol)
    
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    
    logger.info(f"Downloading OI data from {start_date} to {end_date}")
    
    data = downloader.download_historical_data(start_date, end_date)
    
    if data:
        logger.info("Data download complete!")
        
        # 保存数据
        for year in range(start_date.year, end_date.year + 1):
            for month in range(1, 13):
                if year == start_date.year and month < start_date.month:
                    continue
                if year == end_date.year and month > end_date.month:
                    break
                
                # 过滤该月的数据
                month_data = {}
                for name, df in data.items():
                    if df is not None:
                        mask = (df['timestamp'].dt.year == year) & (df['timestamp'].dt.month == month)
                        if mask.any():
                            month_data[name] = df.loc[mask].copy()
                
                if month_data:
                    downloader.save_data(month_data, year, month)
    else:
        logger.warning("No data downloaded")


if __name__ == "__main__":
    main()
