#!/usr/bin/env python3
"""
OKX K线数据下载脚本
通过 REST API 下载历史K线数据并转换为 Parquet 格式
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm

BASE_URL = "https://www.okx.com/api/v5/market/history-candles"

OKX_KLINES_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vol_ccy",
    "vol_ccy_quote",
    "confirm"
]


def download_klines(
    symbols: list,
    years: list,
    interval: str = "1m",
    data_root: Path = None,
):
    """
    下载OKX K线数据
    
    Args:
        symbols: 交易对列表, 如 ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        years: 年份列表, 如 [2024, 2025]
        interval: K线周期, 默认1m
        data_root: 数据根目录
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "okx" / "klines"
    save_base.mkdir(parents=True, exist_ok=True)
    
    interval_map = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1H": "1H",
        "4H": "4H",
        "1D": "1D",
    }
    bar = interval_map.get(interval, "1m")
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"下载 {symbol} K线数据")
        print(f"{'='*60}")
        
        save_dir = save_base / f"symbol={symbol}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已存在
        parquet_path = save_dir / "data.parquet"
        if parquet_path.exists():
            print(f"跳过，已存在: {parquet_path}")
            continue
        
        all_data = []
        
        current_end = datetime.now()
        min_ts = int(datetime(years[0], 1, 1).timestamp() * 1000)
        
        pbar = tqdm(desc=f"{symbol}", unit="requests")
        
        request_count = 0
        max_requests_per_minute = 20
        
        while True:
            try:
                params = {
                    "instId": symbol,
                    "bar": bar,
                    "limit": "100",
                }
                
                if all_data:
                    before_ts = int(current_end.timestamp() * 1000)
                    params["before"] = str(before_ts)
                
                r = requests.get(BASE_URL, params=params, timeout=30)
                
                if r.status_code == 429:
                    print("\n触发限流，等待60秒...")
                    time.sleep(60)
                    continue
                
                if r.status_code != 200:
                    print(f"\n请求失败: {r.status_code}")
                    break
                
                data = r.json()
                
                if data.get("code") != "0":
                    print(f"\nAPI错误: {data.get('msg')}")
                    break
                
                candles = data.get("data", [])
                
                if not candles:
                    break
                
                # 检查是否超出了我们需要的时间范围
                oldest_ts = int(candles[-1][0])
                if oldest_ts < min_ts:
                    # 过滤掉早于目标日期的数据
                    filtered = [c for c in candles if int(c[0]) >= min_ts]
                    if filtered:
                        all_data.extend(filtered)
                    break
                
                all_data.extend(candles)
                
                # 更新下一次请求的时间
                current_end = datetime.fromtimestamp(oldest_ts / 1000)
                
                pbar.update(1)
                pbar.set_postfix({"candles": len(all_data)})
                
                request_count += 1
                
                if request_count >= max_requests_per_minute:
                    time.sleep(60)
                    request_count = 0
                else:
                    time.sleep(0.2)
                
            except Exception as e:
                print(f"\n错误: {e}")
                time.sleep(5)
        
        pbar.close()
        
        if all_data:
            df = pd.DataFrame(all_data, columns=OKX_KLINES_COLUMNS)
            
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
            df["exchange"] = "okx"
            df["symbol"] = symbol
            df["interval"] = bar
            
            df = df.drop_duplicates(subset=["timestamp"])
            df = df.sort_values("timestamp")
            
            for col in ["open", "high", "low", "close", "volume", "vol_ccy", "vol_ccy_quote"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            final_df = df[[
                "timestamp", "exchange", "symbol", "interval",
                "open", "high", "low", "close", "volume",
                "vol_ccy", "vol_ccy_quote", "confirm"
            ]]
            
            final_df.to_parquet(parquet_path, compression="zstd", index=False)
            
            print(f"保存 {len(final_df)} 条记录到 {parquet_path}")
        else:
            print("未获取到数据")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载OKX K线数据")
    parser.add_argument("--symbols", nargs="+",
                       default=["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "ZEC-USDT-SWAP"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    parser.add_argument("--interval", default="1m")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OKX K线数据下载")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print(f"周期: {args.interval}")
    print("=" * 60)
    
    download_klines(args.symbols, args.years, args.interval)
