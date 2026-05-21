#!/usr/bin/env python3
"""
从Trades数据批量生成Orderbook特征

基于现有架构:
- services/aggregation_service/models/orderbook_model.py
- services/aggregation_service/aggregators/orderbook/orderbook_aggregator.py

特征包括:
- Imbalance (买卖盘失衡)
- Trade Flow (成交流)
- Sweep Detection (扫单检测)
- Depth Pressure (深度压力)
- VWAP / Microprice
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import pandas as pd
import numpy as np
from tqdm import tqdm

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.logging import get_logger
from infrastructure.data_lake import get_crypto_data_path, get_data_lake_subpath

logger = get_logger("batch_orderbook_features")


class TradeBasedOrderbookFeatureExtractor:
    """
    基于Trades数据的Orderbook特征提取器
    
    从Trades数据推导Orderbook特征:
    - 通过成交流推断买卖压力
    - 通过价格变动推断深度
    - 通过大单检测扫单行为
    """
    
    def __init__(
        self,
        window_seconds: int = 60,
        large_trade_threshold_usd: float = 10000,
        imbalance_window: int = 100
    ):
        self.window_seconds = window_seconds
        self.large_trade_threshold_usd = large_trade_threshold_usd
        self.imbalance_window = imbalance_window
    
    def extract_features_from_trades(
        self,
        trades_df: pd.DataFrame,
        symbol: str,
        exchange: str = "binance"
    ) -> pd.DataFrame:
        """
        从Trades数据提取Orderbook特征
        
        Args:
            trades_df: Trades数据DataFrame
            symbol: 交易对
            exchange: 交易所
            
        Returns:
            特征DataFrame
        """
        if len(trades_df) == 0:
            return pd.DataFrame()
        
        trades_df = trades_df.copy()
        trades_df['datetime'] = pd.to_datetime(trades_df['timestamp'])
        trades_df = trades_df.sort_values('datetime').reset_index(drop=True)
        
        trades_df['window'] = trades_df['datetime'].dt.floor(f'{self.window_seconds}S')
        
        trades_df['is_buy'] = ~trades_df['is_buyer_maker']
        trades_df['buy_volume'] = trades_df['qty'] * trades_df['is_buy']
        trades_df['sell_volume'] = trades_df['qty'] * (~trades_df['is_buy'])
        trades_df['trade_value'] = trades_df['price'] * trades_df['qty']
        trades_df['is_large'] = trades_df['trade_value'] >= self.large_trade_threshold_usd
        
        features = []
        
        cumulative_delta = 0.0
        prev_imbalance = 0.0
        imbalance_history = []
        
        for window_start, group in tqdm(
            trades_df.groupby('window'),
            desc=f"Processing {symbol}",
            leave=False
        ):
            if len(group) == 0:
                continue
            
            feature = self._calculate_window_features(
                group=group,
                window_start=window_start,
                symbol=symbol,
                exchange=exchange,
                cumulative_delta=cumulative_delta,
                prev_imbalance=prev_imbalance,
                imbalance_history=imbalance_history
            )
            
            if feature:
                features.append(feature)
                
                cumulative_delta = feature['cumulative_delta']
                imbalance_history.append(feature['imbalance'])
                if len(imbalance_history) > self.imbalance_window:
                    imbalance_history.pop(0)
                prev_imbalance = feature['imbalance']
        
        if not features:
            return pd.DataFrame()
        
        return pd.DataFrame(features)
    
    def _calculate_window_features(
        self,
        group: pd.DataFrame,
        window_start: datetime,
        symbol: str,
        exchange: str,
        cumulative_delta: float,
        prev_imbalance: float,
        imbalance_history: List[float]
    ) -> Optional[Dict]:
        """计算单个时间窗口的特征"""
        
        total_volume = group['qty'].sum()
        total_value = group['trade_value'].sum()
        
        if total_volume == 0:
            return None
        
        buy_volume = group['buy_volume'].sum()
        sell_volume = group['sell_volume'].sum()
        
        trade_delta = buy_volume - sell_volume
        cumulative_delta += trade_delta
        
        imbalance = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0.0
        
        buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')
        
        vwap = total_value / total_volume if total_volume > 0 else 0.0
        
        prices = group['price'].values
        high_price = prices.max()
        low_price = prices.min()
        open_price = prices[0]
        close_price = prices[-1]
        
        price_range = high_price - low_price
        mid_price = (high_price + low_price) / 2
        price_volatility = price_range / mid_price if mid_price > 0 else 0.0
        
        trade_count = len(group)
        trade_velocity = trade_count / self.window_seconds
        
        large_trades = group[group['is_large']]
        large_trade_count = len(large_trades)
        large_trade_ratio = large_trade_count / trade_count if trade_count > 0 else 0.0
        large_trade_volume = large_trades['qty'].sum()
        
        avg_trade_size = total_volume / trade_count if trade_count > 0 else 0.0
        max_trade_size = group['qty'].max()
        min_trade_size = group['qty'].min()
        
        trade_sizes = group['qty'].values
        if len(trade_sizes) > 1:
            size_std = np.std(trade_sizes)
            size_cv = size_std / avg_trade_size if avg_trade_size > 0 else 0.0
        else:
            size_cv = 0.0
        
        sweep_score = 0.0
        if large_trade_count > 0:
            large_buy = large_trades['buy_volume'].sum()
            large_sell = large_trades['sell_volume'].sum()
            if large_buy > large_sell * 2:
                sweep_score = large_buy / total_volume
            elif large_sell > large_buy * 2:
                sweep_score = -large_sell / total_volume
        
        imbalance_slope = imbalance - prev_imbalance
        
        imbalance_volatility = 0.0
        if len(imbalance_history) >= 10:
            imb_arr = np.array(imbalance_history[-10:])
            imbalance_volatility = np.std(imb_arr)
        
        book_pressure = imbalance * total_volume
        
        price_impact = 0.0
        if open_price > 0:
            price_impact = abs(close_price - open_price) / open_price
        
        timestamp_ms = int(window_start.timestamp() * 1000)
        
        return {
            'timestamp': timestamp_ms,
            'datetime': window_start,
            'exchange': exchange,
            'symbol': symbol,
            
            'mid_price': mid_price,
            'vwap': vwap,
            'high_price': high_price,
            'low_price': low_price,
            'price_range': price_range,
            'price_volatility': price_volatility,
            
            'imbalance': imbalance,
            'imbalance_slope': imbalance_slope,
            'imbalance_volatility': imbalance_volatility,
            
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'total_volume': total_volume,
            'total_value': total_value,
            'buy_sell_ratio': buy_sell_ratio,
            
            'trade_delta': trade_delta,
            'cumulative_delta': cumulative_delta,
            
            'trade_count': trade_count,
            'trade_velocity': trade_velocity,
            'avg_trade_size': avg_trade_size,
            'max_trade_size': max_trade_size,
            'min_trade_size': min_trade_size,
            'size_cv': size_cv,
            
            'large_trade_count': large_trade_count,
            'large_trade_ratio': large_trade_ratio,
            'large_trade_volume': large_trade_volume,
            
            'sweep_score': sweep_score,
            'book_pressure': book_pressure,
            'price_impact': price_impact,
        }


def process_symbol(
    extractor: TradeBasedOrderbookFeatureExtractor,
    symbol: str,
    exchange: str,
    years: Optional[List[int]] = None,
    months: Optional[List[int]] = None,
    output_dir: Optional[Path] = None
) -> Dict:
    """
    处理单个交易对的所有Trades数据
    
    Args:
        extractor: 特征提取器
        symbol: 交易对
        exchange: 交易所
        years: 年份列表（None表示全部）
        months: 月份列表（None表示全部）
        output_dir: 输出目录
        
    Returns:
        处理统计信息
    """
    trades_path = get_crypto_data_path(exchange, 'trades')
    symbol_dir = trades_path / f"symbol={symbol}"
    
    if not symbol_dir.exists():
        logger.warning(f"Symbol directory not found: {symbol_dir}")
        return {"error": "directory not found"}
    
    if output_dir is None:
        output_dir = get_data_lake_subpath("orderbook_features", exchange, symbol)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "symbol": symbol,
        "exchange": exchange,
        "files_processed": 0,
        "total_trades": 0,
        "total_features": 0,
        "total_size_mb": 0.0,
        "errors": []
    }
    
    year_dirs = sorted([d for d in symbol_dir.iterdir() if d.is_dir()])
    
    for year_dir in year_dirs:
        year_str = year_dir.name.replace("year=", "")
        year = int(year_str)
        
        if years and year not in years:
            continue
        
        month_dirs = sorted([d for d in year_dir.iterdir() if d.is_dir()])
        
        for month_dir in month_dirs:
            month_str = month_dir.name.replace("month=", "")
            month = int(month_str)
            
            if months and month not in months:
                continue
            
            parquet_file = month_dir / "data.parquet"
            if not parquet_file.exists():
                continue
            
            logger.info(f"Processing {symbol} {year}-{month:02d}")
            
            try:
                trades_df = pd.read_parquet(parquet_file)
                stats["files_processed"] += 1
                stats["total_trades"] += len(trades_df)
                
                features_df = extractor.extract_features_from_trades(
                    trades_df=trades_df,
                    symbol=symbol,
                    exchange=exchange
                )
                
                if len(features_df) > 0:
                    output_file = output_dir / f"features_{year}_{month:02d}.parquet"
                    features_df.to_parquet(output_file, compression="zstd", index=False)
                    
                    file_size_mb = output_file.stat().st_size / 1024 / 1024
                    stats["total_size_mb"] += file_size_mb
                    stats["total_features"] += len(features_df)
                    
                    logger.info(f"  ✓ {len(features_df):,} features, {file_size_mb:.2f} MB")
                
            except Exception as e:
                error_msg = f"{year}-{month:02d}: {str(e)}"
                stats["errors"].append(error_msg)
                logger.error(f"  ✗ Error: {e}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="从Trades数据批量生成Orderbook特征")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT"], help="交易对列表")
    parser.add_argument("--exchange", default="binance", help="交易所")
    parser.add_argument("--years", nargs="+", type=int, default=None, help="年份列表")
    parser.add_argument("--months", nargs="+", type=int, default=None, help="月份列表")
    parser.add_argument("--window", type=int, default=60, help="时间窗口（秒）")
    parser.add_argument("--output", type=str, default=None, help="输出目录")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("📊 从Trades数据批量生成Orderbook特征")
    print("=" * 80)
    print(f"\n配置:")
    print(f"  • 交易对: {args.symbols}")
    print(f"  • 交易所: {args.exchange}")
    print(f"  • 年份: {args.years or '全部'}")
    print(f"  • 月份: {args.months or '全部'}")
    print(f"  • 时间窗口: {args.window}秒")
    
    extractor = TradeBasedOrderbookFeatureExtractor(
        window_seconds=args.window
    )
    
    output_dir = Path(args.output) if args.output else None
    
    all_stats = []
    
    for symbol in args.symbols:
        print(f"\n{'=' * 80}")
        print(f"处理 {symbol}")
        print(f"{'=' * 80}")
        
        stats = process_symbol(
            extractor=extractor,
            symbol=symbol,
            exchange=args.exchange,
            years=args.years,
            months=args.months,
            output_dir=output_dir
        )
        
        all_stats.append(stats)
        
        print(f"\n统计:")
        print(f"  • 处理文件数: {stats['files_processed']}")
        print(f"  • 总Trades数: {stats['total_trades']:,}")
        print(f"  • 总特征数: {stats['total_features']:,}")
        print(f"  • 输出大小: {stats['total_size_mb']:.2f} MB")
        
        if stats['errors']:
            print(f"  • 错误: {len(stats['errors'])}")
            for err in stats['errors']:
                print(f"    - {err}")
    
    print(f"\n{'=' * 80}")
    print("✅ 完成")
    print(f"{'=' * 80}")
    
    total_features = sum(s['total_features'] for s in all_stats)
    total_size = sum(s['total_size_mb'] for s in all_stats)
    print(f"\n总计:")
    print(f"  • 总特征数: {total_features:,}")
    print(f"  • 总大小: {total_size:.2f} MB")


if __name__ == "__main__":
    main()
