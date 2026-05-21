#!/usr/bin/env python3
"""
详细检查OrderBook相关数据
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_orderbook_details():
    """检查orderbook数据详情"""
    print("=" * 80)
    print("📊 OrderBook数据详情检查")
    print("=" * 80)
    
    local_data_lake = project_root / "data_lake"
    
    # 检查orderbook_features
    orderbook_path = local_data_lake / "orderbook_features"
    if orderbook_path.exists():
        print(f"\n🔍 OrderBook特征数据:")
        print(f"   目录: {orderbook_path}")
        
        total_files = 0
        total_size = 0
        files_details = []
        
        for item in orderbook_path.rglob("*.parquet"):
            total_files += 1
            file_size = item.stat().st_size
            total_size += file_size
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            files_details.append({
                "path": item,
                "size": file_size,
                "mtime": mtime
            })
        
        size_mb = total_size / 1024 / 1024
        print(f"   • 总文件数: {total_files}")
        print(f"   • 总大小: {size_mb:.2f} MB")
        
        if files_details:
            print(f"\n   📄 文件列表:")
            for f in sorted(files_details, key=lambda x: x["mtime"], reverse=True):
                size_str = f"{f['size'] / 1024 / 1024:.2f} MB"
                print(f"      • {f['path'].relative_to(orderbook_path)}")
                print(f"          大小: {size_str}, 修改时间: {f['mtime'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 尝试读取样本
                try:
                    df = pd.read_parquet(f["path"])
                    print(f"          数据行数: {len(df):,}")
                    print(f"          数据列: {list(df.columns)}")
                    if len(df) > 0:
                        print(f"          时间范围: {df['datetime'].min()} 至 {df['datetime'].max()}")
                except Exception as e:
                    print(f"          读取失败: {e}")
                print()
    
    # 检查features/binance
    features_path = local_data_lake / "features" / "binance"
    if features_path.exists():
        print(f"\n🔍 Features/Binance数据:")
        print(f"   目录: {features_path}")
        
        total_files = 0
        total_size = 0
        files_details = []
        
        for item in features_path.rglob("*.parquet"):
            total_files += 1
            file_size = item.stat().st_size
            total_size += file_size
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            files_details.append({
                "path": item,
                "size": file_size,
                "mtime": mtime
            })
        
        size_mb = total_size / 1024 / 1024
        size_gb = size_mb / 1024
        print(f"   • 总文件数: {total_files}")
        print(f"   • 总大小: {size_gb:.2f} GB ({size_mb:.2f} MB)")
        
        if files_details:
            print(f"\n   📄 文件列表:")
            for f in sorted(files_details, key=lambda x: x["size"], reverse=True):
                size_str = f"{f['size'] / 1024 / 1024:.2f} MB"
                print(f"      • {f['path'].relative_to(features_path.parent)}")
                print(f"          大小: {size_str}, 修改时间: {f['mtime'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 尝试读取样本
                try:
                    df = pd.read_parquet(f["path"])
                    print(f"          数据行数: {len(df):,}")
                    print(f"          数据列: {list(df.columns[:10])}...")
                    if len(df) > 0 and 'datetime' in df.columns:
                        print(f"          时间范围: {df['datetime'].min()} 至 {df['datetime'].max()}")
                except Exception as e:
                    print(f"          读取失败: {e}")
                print()
    
    # 检查trades数据
    trades_path = local_data_lake / "crypto" / "binance" / "trades"
    if trades_path.exists():
        print(f"\n🔍 Trades数据（用于生成OrderBook特征）:")
        print(f"   目录: {trades_path}")
        
        for sym_dir in sorted(trades_path.iterdir()):
            if sym_dir.is_dir():
                symbol = sym_dir.name.replace("symbol=", "")
                print(f"\n   📊 {symbol}:")
                
                total_size = 0
                total_files = 0
                time_ranges = []
                
                for year_dir in sorted(sym_dir.iterdir()):
                    if year_dir.is_dir():
                        year = year_dir.name.replace("year=", "")
                        for month_dir in sorted(year_dir.iterdir()):
                            if month_dir.is_dir():
                                month = month_dir.name.replace("month=", "")
                                parquet_file = month_dir / "data.parquet"
                                if parquet_file.exists():
                                    file_size = parquet_file.stat().st_size
                                    total_size += file_size
                                    total_files += 1
                                    mtime = datetime.fromtimestamp(parquet_file.stat().st_mtime)
                                    
                                    # 读取样本
                                    try:
                                        df = pd.read_parquet(parquet_file)
                                        if len(df) > 0:
                                            time_ranges.append({
                                                "year": year,
                                                "month": month,
                                                "rows": len(df),
                                                "start": df['timestamp'].min(),
                                                "end": df['timestamp'].max()
                                            })
                                        size_mb = file_size / 1024 / 1024
                                        print(f"      • {year}-{month}: {size_mb:.2f} MB, {len(df):,} 行")
                                    except Exception as e:
                                        print(f"      • {year}-{month}: 读取失败 - {e}")
                
                total_size_mb = total_size / 1024 / 1024
                total_size_gb = total_size_mb / 1024
                print(f"\n      总计: {total_files} 个文件, {total_size_gb:.2f} GB")
    
    print(f"\n{'=' * 80}")
    print("✅ 检查完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    check_orderbook_details()
