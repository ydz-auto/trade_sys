#!/usr/bin/env python3
"""
独立特征生成测试脚本

直接调用特征生成逻辑，无需启动完整的API服务器
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

TRADES_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake\crypto\binance\trades")
FEATURES_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake\features")


class FeatureGenerator:
    """特征生成器"""
    
    INTERVAL_CONFIG = {
        "1m": {"freq": "1T"},
        "5m": {"freq": "5T"},
        "15m": {"freq": "15T"},
        "1h": {"freq": "1H"},
        "4h": {"freq": "4H"},
        "1d": {"freq": "1D"},
    }
    
    def extract_base_features(self, trades_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """从Trades提取基础特征"""
        if len(trades_df) == 0:
            return pd.DataFrame()
        
        trades_df = trades_df.sort_values('timestamp').reset_index(drop=True)
        trades_df['datetime'] = pd.to_datetime(trades_df['timestamp'])
        trades_df['second'] = trades_df['datetime'].dt.floor('s')
        
        features = []
        cumulative_delta = 0
        cumulative_buy_volume = 0
        cumulative_sell_volume = 0
        
        grouped = trades_df.groupby('second')
        
        for second, group in tqdm(grouped, desc=f"处理 {symbol}", leave=False, total=len(grouped)):
            buy_trades = group[~group['is_buyer_maker']]
            sell_trades = group[group['is_buyer_maker']]
            
            buy_volume = buy_trades['qty'].sum()
            sell_volume = sell_trades['qty'].sum()
            buy_value = buy_trades['quote_qty'].sum()
            sell_value = sell_trades['quote_qty'].sum()
            
            total_volume = buy_volume + sell_volume
            total_value = buy_value + sell_value
            trade_delta = buy_volume - sell_volume
            
            cumulative_delta += trade_delta
            cumulative_buy_volume += buy_volume
            cumulative_sell_volume += sell_volume
            
            vwap = total_value / total_volume if total_volume > 0 else group['price'].mean()
            num_trades = len(group)
            avg_trade_size = total_volume / num_trades if num_trades > 0 else 0
            max_trade_size = group['qty'].max()
            
            large_trades = group[group['quote_qty'] >= 10000]
            large_trade_ratio = len(large_trades) / num_trades if num_trades > 0 else 0
            
            buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
            
            features.append({
                'timestamp': int(second.timestamp() * 1000),
                'datetime': second,
                'symbol': symbol,
                'exchange': 'binance',
                
                'mid_price': vwap,
                'microprice': vwap,
                'spread': abs(vwap * 0.0002),
                
                'trade_delta': trade_delta,
                'cumulative_delta': cumulative_delta,
                'aggressive_buy_volume': buy_volume,
                'aggressive_sell_volume': sell_volume,
                'total_volume': total_volume,
                'total_value': total_value,
                'num_trades': num_trades,
                'avg_trade_size': avg_trade_size,
                'max_trade_size': max_trade_size,
                'large_trade_ratio': large_trade_ratio,
                'buy_sell_ratio': buy_sell_ratio,
                
                'cumulative_buy_volume': cumulative_buy_volume,
                'cumulative_sell_volume': cumulative_sell_volume,
            })
        
        return pd.DataFrame(features)
    
    def aggregate_to_interval(self, base_features: pd.DataFrame, interval: str) -> pd.DataFrame:
        """聚合到指定周期"""
        if len(base_features) == 0:
            return pd.DataFrame()
        
        base_features = base_features.set_index('datetime')
        
        freq = self.INTERVAL_CONFIG.get(interval, {}).get('freq', '1T')
        
        agg_dict = {
            'mid_price': ['first', 'max', 'min', 'last'],
            'trade_delta': 'sum',
            'cumulative_delta': 'last',
            'aggressive_buy_volume': 'sum',
            'aggressive_sell_volume': 'sum',
            'total_volume': 'sum',
            'total_value': 'sum',
            'num_trades': 'sum',
            'avg_trade_size': 'mean',
            'max_trade_size': 'max',
            'large_trade_ratio': 'mean',
            'buy_sell_ratio': 'mean',
            'cumulative_buy_volume': 'last',
            'cumulative_sell_volume': 'last',
        }
        
        resampled = base_features.resample(freq).agg(agg_dict)
        resampled.columns = ['_'.join(col).strip('_') for col in resampled.columns]
        
        resampled = resampled.reset_index()
        resampled['timestamp'] = resampled['datetime'].apply(lambda x: int(x.timestamp() * 1000))
        resampled['symbol'] = base_features['symbol'].iloc[0]
        resampled['exchange'] = 'binance'
        
        return resampled
    
    def generate_and_store(
        self,
        symbol: str,
        year: int,
        month: int,
        intervals: list,
        force_regenerate: bool = False
    ):
        """生成并存储特征"""
        month_str = f"{month:02d}"
        
        trades_path = TRADES_ROOT / f"symbol={symbol}" / f"year={year}" / f"month={month_str}" / "data.parquet"
        
        if not trades_path.exists():
            print(f"  ⚠️  Trades数据未找到: {trades_path}")
            return None
        
        print(f"  加载Trades数据: {len(pd.read_parquet(trades_path)):,} 条记录")
        
        trades_df = pd.read_parquet(trades_path)
        
        print(f"  提取基础特征...")
        base_features = self.extract_base_features(trades_df, symbol)
        
        if len(base_features) == 0:
            print(f"  ❌ 特征提取失败")
            return None
        
        print(f"  基础特征: {len(base_features):,} 条")
        
        results = {}
        
        for interval in intervals:
            output_dir = FEATURES_ROOT / interval / f"symbol={symbol}" / f"year={year}" / f"month={month_str}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "data.parquet"
            
            if output_path.exists() and not force_regenerate:
                df_existing = pd.read_parquet(output_path)
                print(f"  {interval}: 已存在 {len(df_existing):,} 条记录 (跳过)")
                results[interval] = {"status": "skipped", "records": len(df_existing)}
                continue
            
            print(f"  聚合到 {interval}...")
            aggregated = self.aggregate_to_interval(base_features, interval)
            
            if len(aggregated) == 0:
                print(f"  {interval}: 聚合结果为空")
                results[interval] = {"status": "empty", "records": 0}
                continue
            
            aggregated.to_parquet(output_path, compression='zstd', index=False)
            size_mb = output_path.stat().st_size / (1024 * 1024)
            
            print(f"  {interval}: ✅ {len(aggregated):,} 条记录, {size_mb:.2f} MB")
            results[interval] = {"status": "success", "records": len(aggregated), "size_mb": size_mb}
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="特征生成测试")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对")
    parser.add_argument("--year", type=int, default=2024, help="年份")
    parser.add_argument("--month", type=int, default=1, help="月份")
    parser.add_argument("--intervals", nargs="+", default=["1m", "5m", "15m"], help="时间周期")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("特征生成测试")
    print(f"交易对: {args.symbol}")
    print(f"时间: {args.year}-{args.month:02d}")
    print(f"周期: {args.intervals}")
    print("=" * 80)
    
    generator = FeatureGenerator()
    
    results = generator.generate_and_store(
        symbol=args.symbol,
        year=args.year,
        month=args.month,
        intervals=args.intervals,
        force_regenerate=args.force
    )
    
    print("\n" + "=" * 80)
    print("生成结果")
    print("=" * 80)
    
    if results:
        for interval, result in results.items():
            print(f"{interval}: {result}")
    
    print("\n特征数据存储位置:")
    print(f"  {FEATURES_ROOT}")
    
    print("\n下一步:")
    print("  1. 查看生成的数据: ls", FEATURES_ROOT)
    print("  2. 启动API服务器: make start")
    print("  3. 访问API文档: http://localhost:8000/docs")
    print("=" * 80)


if __name__ == "__main__":
    main()
