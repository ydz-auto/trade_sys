#!/usr/bin/env python3
"""
Binance Funding Rate 下载脚本
通过 REST API 下载历史资金费率数据并转换为 Parquet 格式
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm

BASE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"


def download_funding(
    symbols: list,
    years: list,
    data_root: Path = None,
):
    """
    下载Binance Funding Rate数据
    
    Args:
        symbols: 交易对列表, 如 ["BTCUSDT", "ETHUSDT"]
        years: 年份列表, 如 [2024, 2025]
        data_root: 数据根目录
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "binance" / "funding"
    save_base.mkdir(parents=True, exist_ok=True)
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"下载 {symbol} Funding Rate 数据")
        print(f"{'='*60}")
        
        save_dir = save_base / f"symbol={symbol}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        all_data = []
        
        start_date = datetime(years[0], 1, 1)
        end_date = datetime.now()
        
        current_start = start_date
        current_end = min(start_date + timedelta(days=30), end_date)
        
        pbar = tqdm(desc=f"{symbol}", unit="requests")
        
        request_count = 0
        max_requests_per_minute = 1200
        
        while current_start < end_date:
            try:
                params = {
                    "symbol": symbol,
                    "startTime": int(current_start.timestamp() * 1000),
                    "endTime": int(current_end.timestamp() * 1000),
                    "limit": 1000,
                }
                
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
                    current_start = current_end
                    current_end = min(current_start + timedelta(days=30), end_date)
                    if current_start >= end_date:
                        break
                    continue
                
                all_data.extend(data)
                
                last_ts = data[-1]["fundingTime"]
                current_start = datetime.fromtimestamp(last_ts / 1000) + timedelta(milliseconds=1)
                current_end = min(current_start + timedelta(days=30), end_date)
                
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
        
        pbar.close()
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms")
            df["exchange"] = "binance"
            
            df = df.drop_duplicates(subset=["fundingTime"])
            df = df.sort_values("timestamp")
            
            final_df = df[[
                "timestamp", "exchange", "symbol",
                "fundingTime", "fundingRate", "markPrice"
            ]]
            
            parquet_path = save_dir / "data.parquet"
            final_df.to_parquet(parquet_path, compression="zstd", index=False)
            
            print(f"保存 {len(final_df)} 条记录到 {parquet_path}")
        else:
            print("未获取到数据")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载Binance Funding Rate数据")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Binance Funding Rate 数据下载")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print("=" * 60)
    
    download_funding(args.symbols, args.years)
