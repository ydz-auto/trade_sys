#!/usr/bin/env python3
"""
OKX Funding Rate 下载脚本
通过 REST API 下载历史资金费率数据并转换为 Parquet 格式
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

BASE_URL = "https://www.okx.com/api/v5/public/funding-rate-history"


def download_funding(
    symbols: list,
    years: list,
    data_root: Path = None,
):
    """
    下载OKX Funding Rate数据
    
    Args:
        symbols: 交易对列表, 如 ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        years: 年份列表, 如 [2024, 2025]
        data_root: 数据根目录
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "okx" / "funding"
    save_base.mkdir(parents=True, exist_ok=True)
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"下载 {symbol} Funding Rate 数据")
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
        max_requests_per_minute = 20
        
        while True:
            try:
                params = {
                    "instId": symbol,
                    "limit": 100,
                }
                
                if all_data:
                    before_ts = int(all_data[0]["fundingTime"]) - 1
                    params["before"] = str(before_ts)
                
                r = requests.get(BASE_URL, params=params, timeout=30)
                
                if r.status_code == 429:
                    print("\n触发限流, 等待60秒...")
                    time.sleep(60)
                    continue
                
                if r.status_code != 200:
                    print(f"\n请求失败: {r.status_code}")
                    break
                
                data = r.json()
                
                if data.get("code") != "0":
                    print(f"\nAPI错误: {data.get('msg')}")
                    break
                
                funding_data = data.get("data", [])
                
                if not funding_data:
                    break
                
                oldest_ts = int(funding_data[-1]["fundingTime"])
                if oldest_ts < min_ts:
                    filtered = [d for d in funding_data if int(d["fundingTime"]) >= min_ts]
                    if filtered:
                        all_data = filtered + all_data
                    break
                
                all_data = funding_data + all_data
                
                pbar.update(1)
                request_count += 1
                
                if request_count >= max_requests_per_minute:
                    time.sleep(60)
                    request_count = 0
                else:
                    time.sleep(0.2)
                
            except Exception as e:
                print(f"\n错误: {e}")
                time.sleep(5)
                break
        
        pbar.close()
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            df["timestamp"] = pd.to_datetime(df["fundingTime"].astype(int), unit="ms")
            df["exchange"] = "okx"
            df["symbol"] = symbol
            
            df["funding_rate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
            
            df = df.drop_duplicates(subset=["timestamp"])
            df = df.sort_values("timestamp")
            
            final_df = df[[
                "timestamp", "exchange", "symbol",
                "funding_rate", "fundingTime", "instId"
            ]]
            
            final_df.to_parquet(parquet_path, compression="zstd", index=False)
            
            print(f"保存 {len(final_df)} 条记录到 {parquet_path}")
        else:
            print("未获取到数据")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载OKX Funding Rate数据")
    parser.add_argument("--symbols", nargs="+", 
                       default=["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "ZEC-USDT-SWAP"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OKX Funding Rate 数据下载")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print("=" * 60)
    
    download_funding(args.symbols, args.years)
