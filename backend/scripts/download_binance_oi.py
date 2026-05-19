#!/usr/bin/env python3
"""
Binance Open Interest 下载脚本
通过 REST API 下载历史持仓量数据并转换为 Parquet 格式
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm

BASE_URL = "https://fapi.binance.com/futures/data/openInterestHist"


def download_oi(
    symbols: list,
    years: list,
    data_root: Path = None,
):
    """
    下载Binance Open Interest数据
    
    Args:
        symbols: 交易对列表, 如 ["BTCUSDT", "ETHUSDT"]
        years: 年份列表, 如 [2024, 2025]
        data_root: 数据根目录
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "binance" / "oi"
    save_base.mkdir(parents=True, exist_ok=True)
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"下载 {symbol} Open Interest 数据")
        print(f"{'='*60}")
        
        save_dir = save_base / f"symbol={symbol}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        parquet_path = save_dir / "data.parquet"
        if parquet_path.exists():
            print(f"跳过，已存在: {parquet_path}")
            continue
        
        all_data = []
        
        min_ts = int(datetime(years[0], 1, 1).timestamp() * 1000)
        
        pbar = tqdm(desc=f"{symbol}", unit="requests")
        
        request_count = 0
        max_requests_per_minute = 1200
        
        while True:
            try:
                params = {
                    "symbol": symbol,
                    "period": "5m",
                    "limit": 500,
                }
                
                if all_data:
                    first_ts = all_data[0]["timestamp"]
                    params["endTime"] = first_ts - 1
                
                r = requests.get(BASE_URL, params=params, timeout=30)
                
                if r.status_code == 429:
                    print("\n触发限流, 等待60秒...")
                    time.sleep(60)
                    continue
                
                if r.status_code != 200:
                    print(f"\n请求失败: {r.status_code}")
                    break
                
                data = r.json()
                
                if not data:
                    break
                
                oldest_ts = data[-1]["timestamp"]
                if oldest_ts < min_ts:
                    filtered = [d for d in data if d["timestamp"] >= min_ts]
                    if filtered:
                        all_data = filtered + all_data
                    break
                
                all_data = data + all_data
                
                pbar.update(1)
                request_count += 1
                
                if request_count >= max_requests_per_minute:
                    time.sleep(60)
                    request_count = 0
                else:
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"\n错误: {e}")
                time.sleep(5)
                break
        
        pbar.close()
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["exchange"] = "binance"
            df["symbol"] = symbol
            
            df = df.drop_duplicates(subset=["timestamp"])
            df = df.sort_values("timestamp")
            
            final_df = df[[
                "timestamp", "exchange", "symbol",
                "sumOpenInterest", "sumOpenInterestValue"
            ]]
            
            final_df.to_parquet(parquet_path, compression="zstd", index=False)
            
            print(f"保存 {len(final_df)} 条记录到 {parquet_path}")
        else:
            print("未获取到数据")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载Binance Open Interest数据")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Binance Open Interest 数据下载")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print("=" * 60)
    
    download_oi(args.symbols, args.years)
