#!/usr/bin/env python3
"""
Trade Feature Builder

预聚合 trades 数据为分钟级特征，避免在回测时加载全量原始数据。

生成的特征包括:
- buy_volume: 主动买入成交量
- sell_volume: 主动卖出成交量
- volume_delta: 净成交量 (buy - sell)
- cvd: 累积成交量差异 (累积的 buy_volume - sell_volume)
- trade_count: 成交笔数
- avg_trade_size: 平均每笔成交大小
- large_trade_count: 大额交易笔数 (可选)
- large_trade_volume: 大额交易成交量 (可选)
- buyer_initiated_ratio: 主动买入比例
- sell_pressure: 卖出压力指标
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
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

from infrastructure.storage.parquet_reader import read_parquet_safe


class TradeFeatureBuilder:
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        output_dir: str = None,
        large_trade_threshold: float = 10000.0,  # 1万美元
    ):
        self.symbol = symbol
        self.large_trade_threshold = large_trade_threshold
        
        if output_dir is None:
            self.output_dir = Path(backend_path) / "data_lake" / "crypto" / "binance" / "trade_features" / f"symbol={symbol}"
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 输入数据目录
        self.trades_dir = Path(backend_path) / "data_lake" / "crypto" / "binance" / "trades" / f"symbol={symbol}"
        
        logger.info(f"Trade Feature Builder initialized for {symbol}")
        logger.info(f"Input directory: {self.trades_dir}")
        logger.info(f"Output directory: {self.output_dir}")
    
    def get_available_years_months(self) -> List[tuple]:
        """获取可用的年月份列表"""
        year_month_list = []
        
        for year_dir in sorted(self.trades_dir.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.startswith("year="):
                continue
            
            year = int(year_dir.name.split("=")[1])
            
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.startswith("month="):
                    continue
                
                month = int(month_dir.name.split("=")[1])
                year_month_list.append((year, month))
        
        return year_month_list
    
    def is_month_already_processed(self, year: int, month: int) -> bool:
        """检查某个月是否已经处理过"""
        output_path = self.output_dir / f"year={year}" / f"month={month:02d}" / "data.parquet"
        return output_path.exists()
    
    def process_month(self, year: int, month: int) -> Optional[pd.DataFrame]:
        """处理一个月的 trades 数据"""
        logger.info(f"Processing {year}-{month:02d}...")
        
        # 读取该月的 trades 数据
        input_path = self.trades_dir / f"year={year}" / f"month={month:02d}" / "data.parquet"
        
        if not input_path.exists():
            logger.warning(f"No data found for {year}-{month:02d}")
            return None
        
        try:
            df = read_parquet_safe(input_path)
            if df is None or len(df) == 0:
                logger.warning(f"Empty data for {year}-{month:02d}")
                return None
            
            logger.info(f"Loaded {len(df):,} trades for {year}-{month:02d}")
            
            # 确保时间戳格式正确
            if 'timestamp' not in df.columns and 'time' in df.columns:
                df['timestamp'] = df['time']
            
            if 'timestamp' not in df.columns:
                logger.error(f"No timestamp column in data for {year}-{month:02d}")
                return None
            
            # 转换时间戳为 datetime
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 截断到分钟级
            df['minute'] = df['datetime'].dt.floor('min')
            
            # 计算特征
            features = self._aggregate_trades(df)
            
            return features
            
        except Exception as e:
            logger.error(f"Error processing {year}-{month:02d}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _aggregate_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """聚合 trades 数据为分钟级特征"""
        results = []
        
        # 按分钟分组
        for minute, group in df.groupby('minute'):
            total_trades = len(group)
            
            # 主动买入和主动卖出
            # is_buyer_maker = True: 主动卖出
            # is_buyer_maker = False: 主动买入
            buy_trades = group[~group['is_buyer_maker']]
            sell_trades = group[group['is_buyer_maker']]
            
            buy_volume = buy_trades['quote_qty'].sum()
            sell_volume = sell_trades['quote_qty'].sum()
            
            volume_delta = buy_volume - sell_volume
            
            # 计算大额交易
            large_buy_trades = buy_trades[buy_trades['quote_qty'] >= self.large_trade_threshold]
            large_sell_trades = sell_trades[sell_trades['quote_qty'] >= self.large_trade_threshold]
            
            large_trade_count = len(large_buy_trades) + len(large_sell_trades)
            large_trade_volume = large_buy_trades['quote_qty'].sum() + large_sell_trades['quote_qty'].sum()
            
            # 计算比例
            total_volume = buy_volume + sell_volume
            buyer_initiated_ratio = buy_volume / total_volume if total_volume > 0 else 0.5
            sell_pressure = sell_volume / total_volume if total_volume > 0 else 0.5
            
            # 平均每笔成交大小
            avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
            
            results.append({
                'timestamp': int(minute.timestamp() * 1000),  # 毫秒时间戳
                'datetime': minute,
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'volume_delta': volume_delta,
                'trade_count': total_trades,
                'avg_trade_size': avg_trade_size,
                'large_trade_count': large_trade_count,
                'large_trade_volume': large_trade_volume,
                'buyer_initiated_ratio': buyer_initiated_ratio,
                'sell_pressure': sell_pressure,
            })
        
        # 转换为 DataFrame
        features_df = pd.DataFrame(results)
        
        if len(features_df) > 0:
            # 计算 CVD (累积成交量差异)
            features_df['cvd'] = features_df['volume_delta'].cumsum()
        
        return features_df
    
    def save_features(self, features_df: pd.DataFrame, year: int, month: int):
        """保存特征到 parquet 文件"""
        if features_df is None or len(features_df) == 0:
            logger.warning(f"No features to save for {year}-{month:02d}")
            return
        
        output_dir = self.output_dir / f"year={year}" / f"month={month:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / "data.parquet"
        
        # 确保 datetime 列格式正确
        if 'datetime' in features_df.columns:
            features_df['datetime'] = features_df['datetime'].dt.to_pydatetime()
        
        features_df.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(features_df):,} features to {output_path}")
    
    def process_all(self, resume: bool = True):
        """处理所有可用的 trades 数据"""
        year_month_list = self.get_available_years_months()
        
        logger.info(f"Found {len(year_month_list)} months of data")
        
        processed_count = 0
        skipped_count = 0
        
        for year, month in year_month_list:
            if resume and self.is_month_already_processed(year, month):
                logger.info(f"Skipping {year}-{month:02d} (already processed)")
                skipped_count += 1
                continue
            
            features_df = self.process_month(year, month)
            
            if features_df is not None:
                self.save_features(features_df, year, month)
                processed_count += 1
        
        logger.info(f"Processing complete. Processed: {processed_count}, Skipped: {skipped_count}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Trade Feature Builder")
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from where we left off (skip already processed months)"
    )
    parser.add_argument(
        "--large-trade-threshold",
        type=float,
        default=10000.0,
        help="Threshold for large trades in USD (default: 10000)"
    )
    
    args = parser.parse_args()
    
    builder = TradeFeatureBuilder(
        symbol=args.symbol,
        large_trade_threshold=args.large_trade_threshold
    )
    
    builder.process_all(resume=args.resume)


if __name__ == "__main__":
    main()
