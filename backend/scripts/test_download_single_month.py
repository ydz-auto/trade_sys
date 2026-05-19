#!/usr/bin/env python3
"""
测试下载单个月份的 Trades 数据
"""

import os
import zipfile
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import time

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/trades"


def download_single_month(symbol: str, year: int, month: int):
    """下载单个月份的Trades数据"""
    
    data_root = Path(__file__).parent.parent / "data_lake"
    save_base = data_root / "crypto" / "binance" / "trades"
    save_base.mkdir(parents=True, exist_ok=True)
    
    mm = str(month).zfill(2)
    filename = f"{symbol}-trades-{year}-{mm}.zip"
    url = f"{BASE_URL}/{symbol}/{filename}"
    
    save_dir = save_base / f"symbol={symbol}" / f"year={year}" / f"month={mm}"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = save_dir / filename
    parquet_path = save_dir / "data.parquet"
    
    print(f"正在下载: {symbol} {year}-{mm}")
    print(f"URL: {url}")
    
    if parquet_path.exists():
        print(f"已存在，跳过: {parquet_path}")
        return
    
    try:
        r = requests.get(url, timeout=300)
        
        if r.status_code != 200:
            print(f"下载失败，状态码: {r.status_code}")
            return
        
        print(f"下载中... 大小: {len(r.content) / 1024 / 1024:.2f} MB")
        
        with open(zip_path, "wb") as f:
            f.write(r.content)
        
        print("解压中...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(save_dir)
        
        csv_files = list(save_dir.glob("*.csv"))
        if not csv_files:
            print("未找到CSV文件")
            return
        
        csv_file = csv_files[0]
        print(f"读取CSV: {csv_file}")
        
        df = pd.read_csv(csv_file)
        print(f"  记录数: {len(df):,}")
        
        df["timestamp"] = pd.to_datetime(df["time"], unit="ms")
        df["exchange"] = "binance"
        df["symbol"] = symbol
        
        final_df = df[[
            "timestamp", "exchange", "symbol",
            "id", "price", "qty", "quote_qty",
            "is_buyer_maker"
        ]]
        
        print(f"转换为Parquet...")
        final_df.to_parquet(
            parquet_path,
            compression="zstd",
            index=False
        )
        
        zip_path.unlink()
        csv_file.unlink()
        
        print(f"完成！保存到: {parquet_path}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("测试下载 Binance Trades 数据（单个月）")
    print("=" * 60)
    
    # 下载 BTCUSDT 2024年1月的数据
    download_single_month("BTCUSDT", 2024, 1)
