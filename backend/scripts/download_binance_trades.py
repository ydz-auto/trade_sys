#!/usr/bin/env python3
"""
Binance Trades 下载脚本
从 Binance Data Vision 下载历史成交数据并转换为 Parquet 格式
"""

import os
import zipfile
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import time
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/trades"

TRADES_COLUMNS = ["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"]


def create_session_with_retries(retries=3, backoff_factor=0.5, status_forcelist=(500, 502, 504)):
    """创建带有重试机制的requests session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def download_trades(
    symbols: list,
    years: list,
    data_root: Path = None,
):
    """
    下载Binance Trades数据
    
    Args:
        symbols: 交易对列表, 如 ["BTCUSDT", "ETHUSDT"]
        years: 年份列表, 如 [2024, 2025]
        data_root: 数据根目录
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "binance" / "trades"
    save_base.mkdir(parents=True, exist_ok=True)
    
    total_tasks = len(symbols) * len(years) * 12
    pbar = tqdm(total=total_tasks, desc="总进度")
    
    stats = {
        "success": 0,
        "skip": 0,
        "not_found": 0,
        "error": 0,
    }
    
    session = create_session_with_retries(retries=3, backoff_factor=1.0)
    
    for symbol in symbols:
        for year in years:
            for month in range(1, 13):
                pbar.set_description(f"{symbol} {year}-{month:02d}")
                
                mm = str(month).zfill(2)
                filename = f"{symbol}-trades-{year}-{mm}.zip"
                url = f"{BASE_URL}/{symbol}/{filename}"
                
                save_dir = save_base / f"symbol={symbol}" / f"year={year}" / f"month={mm}"
                save_dir.mkdir(parents=True, exist_ok=True)
                
                zip_path = save_dir / filename
                parquet_path = save_dir / "data.parquet"
                
                if parquet_path.exists():
                    stats["skip"] += 1
                    pbar.update(1)
                    continue
                
                max_retries = 3
                retry_delay = 5
                
                for attempt in range(max_retries):
                    try:
                        r = session.get(url, timeout=(10, 60), stream=True)
                        
                        if r.status_code != 200:
                            stats["not_found"] += 1
                            pbar.update(1)
                            break
                        
                        total_size = int(r.headers.get('content-length', 0))
                        
                        with open(zip_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        if zip_path.exists() and zip_path.stat().st_size < 100:
                            zip_path.unlink()
                            raise Exception("下载文件过小，可能是错误页面")
                        
                        with zipfile.ZipFile(zip_path, "r") as zip_ref:
                            zip_ref.extractall(save_dir)
                        
                        csv_files = list(save_dir.glob("*.csv"))
                        if not csv_files:
                            stats["error"] += 1
                            pbar.update(1)
                            break
                        
                        csv_file = csv_files[0]
                        
                        df = pd.read_csv(csv_file, low_memory=False)
                        
                        if 'id' in df.columns:
                            df = df.rename(columns={
                                'id': 'id',
                                'price': 'price',
                                'qty': 'qty',
                                'quoteQty': 'quote_qty',
                                'time': 'time',
                                'isBuyerMaker': 'is_buyer_maker'
                            })
                        else:
                            df.columns = TRADES_COLUMNS
                        
                        df["timestamp"] = pd.to_datetime(df["time"], unit="ms", errors="coerce")
                        df = df.dropna(subset=["timestamp"])
                        df["exchange"] = "binance"
                        df["symbol"] = symbol
                        
                        for col in ["id", "price", "qty", "quote_qty"]:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                        
                        df = df.dropna(subset=["id", "price"])
                        
                        final_df = df[[
                            "timestamp", "exchange", "symbol",
                            "id", "price", "qty", "quote_qty",
                            "is_buyer_maker"
                        ]]
                        
                        final_df.to_parquet(
                            parquet_path,
                            compression="zstd",
                            index=False
                        )
                        
                        zip_path.unlink()
                        csv_file.unlink()
                        
                        stats["success"] += 1
                        break
                        
                    except (requests.exceptions.SSLError, 
                            requests.exceptions.ConnectionError,
                            requests.exceptions.Timeout,
                            Exception) as e:
                        if attempt < max_retries - 1:
                            print(f"\n重试 {symbol} {year}-{mm} (尝试 {attempt + 1}/{max_retries}): {e}")
                            time.sleep(retry_delay * (attempt + 1))
                            if zip_path.exists():
                                zip_path.unlink()
                        else:
                            print(f"\n错误 {symbol} {year}-{mm}: {e}")
                            stats["error"] += 1
                            if zip_path.exists():
                                zip_path.unlink()
                
                pbar.update(1)
                time.sleep(0.2)
    
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
    
    parser = argparse.ArgumentParser(description="下载Binance Trades数据")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Binance Trades 数据下载")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print("=" * 60)
    
    download_trades(args.symbols, args.years)
