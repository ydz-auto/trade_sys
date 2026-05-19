#!/usr/bin/env python3
"""
Binance K线数据下载脚本
从 Binance Data Vision 下载历史K线数据并转换为 Parquet 格式
"""

import os
import zipfile
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import time

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/klines"

KLINES_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore"
]


def download_klines(
    symbols: list,
    years: list,
    interval: str = "1m",
    data_root: Path = None,
):
    """
    下载Binance K线数据
    
    Args:
        symbols: 交易对列表, 如 ["BTCUSDT", "ETHUSDT"]
        years: 年份列表, 如 [2024, 2025]
        interval: K线周期, 默认1m
        data_root: 数据根目录
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "binance" / "klines"
    save_base.mkdir(parents=True, exist_ok=True)
    
    total_tasks = len(symbols) * len(years) * 12
    pbar = tqdm(total=total_tasks, desc="总进度")
    
    stats = {
        "success": 0,
        "skip": 0,
        "not_found": 0,
        "error": 0,
    }
    
    for symbol in symbols:
        for year in years:
            for month in range(1, 13):
                pbar.set_description(f"{symbol} {year}-{month:02d}")
                
                mm = str(month).zfill(2)
                filename = f"{symbol}-{interval}-{year}-{mm}.zip"
                url = f"{BASE_URL}/{symbol}/{interval}/{filename}"
                
                save_dir = save_base / f"symbol={symbol}" / f"year={year}" / f"month={mm}"
                save_dir.mkdir(parents=True, exist_ok=True)
                
                zip_path = save_dir / filename
                parquet_path = save_dir / "data.parquet"
                
                if parquet_path.exists():
                    stats["skip"] += 1
                    pbar.update(1)
                    continue
                
                try:
                    r = requests.get(url, timeout=30)
                    
                    if r.status_code != 200:
                        stats["not_found"] += 1
                        pbar.update(1)
                        continue
                    
                    with open(zip_path, "wb") as f:
                        f.write(r.content)
                    
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(save_dir)
                    
                    csv_files = list(save_dir.glob("*.csv"))
                    if not csv_files:
                        stats["error"] += 1
                        pbar.update(1)
                        continue
                    
                    csv_file = csv_files[0]
                    
                    df = pd.read_csv(csv_file)
                    
                    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
                    df["exchange"] = "binance"
                    df["symbol"] = symbol
                    df["interval"] = interval
                    
                    final_df = df[[
                        "timestamp", "exchange", "symbol", "interval",
                        "open", "high", "low", "close", "volume",
                        "quote_volume", "count",
                        "taker_buy_volume", "taker_buy_quote_volume"
                    ]]
                    
                    final_df.to_parquet(
                        parquet_path,
                        compression="zstd",
                        index=False
                    )
                    
                    zip_path.unlink()
                    csv_file.unlink()
                    
                    stats["success"] += 1
                    
                except Exception as e:
                    print(f"\n错误 {symbol} {year}-{mm}: {e}")
                    stats["error"] += 1
                
                pbar.update(1)
                time.sleep(0.1)
    
    pbar.close()
    
    print("\n" + "=" * 60)
    print("下载统计:")
    print(f"  成功: {stats['success']}")
    print(f"  跳过: {stats['skip']}")
    print(f"  未找到: {stats['not_found']}")
    print(f"  错误: {stats['error']}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载Binance K线数据")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    parser.add_argument("--interval", default="1m")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Binance K线数据下载")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print(f"周期: {args.interval}")
    print("=" * 60)
    
    download_klines(args.symbols, args.years, args.interval)
