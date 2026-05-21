#!/usr/bin/env python3
"""
检查OrderBook数据下载情况
"""

import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.data_lake import get_data_lake_subpath, get_data_lake_root


def check_orderbook_data():
    """检查orderbook数据"""
    print("=" * 80)
    print("📊 OrderBook数据下载情况检查")
    print("=" * 80)
    
    data_lake_root = get_data_lake_root()
    print(f"\n📁 数据湖根目录: {data_lake_root}")
    
    # 检查orderbook_features目录
    orderbook_features_path = get_data_lake_subpath("orderbook_features")
    print(f"\n🔍 检查: {orderbook_features_path}")
    
    if not orderbook_features_path.exists():
        print("❌ 目录不存在")
        return
    
    # 统计文件
    total_files = 0
    total_size = 0
    symbol_stats = {}
    
    for item in orderbook_features_path.iterdir():
        if item.is_dir():
            # 可能是按symbol/year/month分区的目录
            for parquet_file in item.rglob("*.parquet"):
                total_files += 1
                file_size = parquet_file.stat().st_size
                total_size += file_size
                
                # 分析文件路径
                parts = parquet_file.relative_to(orderbook_features_path).parts
                if len(parts) >= 3:
                    symbol = parts[0].replace("symbol=", "")
                    year = parts[1].replace("year=", "")
                    month = parts[2].replace("month=", "")
                    key = f"{symbol}/{year}/{month}"
                    if key not in symbol_stats:
                        symbol_stats[key] = {"files": 0, "size": 0}
                    symbol_stats[key]["files"] += 1
                    symbol_stats[key]["size"] += file_size
        elif item.suffix == ".parquet":
            # 直接的parquet文件
            total_files += 1
            file_size = item.stat().st_size
            total_size += file_size
    
    print(f"\n📈 统计:")
    print(f"   • 总文件数: {total_files}")
    print(f"   • 总大小: {total_size / 1024 / 1024:.2f} MB ({total_size / 1024 / 1024 / 1024:.2f} GB)")
    
    if symbol_stats:
        print(f"\n🗂️  按符号和时间统计:")
        for key, stats in sorted(symbol_stats.items()):
            print(f"   • {key}: {stats['files']} 个文件, {stats['size'] / 1024 / 1024:.2f} MB")
    
    # 检查crypto目录的trades数据（用于生成orderbook特征）
    print(f"\n🔍 检查Trades数据（用于生成OrderBook特征）:")
    crypto_trades_path = get_data_lake_subpath("crypto", "binance", "trades")
    if crypto_trades_path.exists():
        print(f"   Trades数据目录: {crypto_trades_path}")
        
        trade_total_files = 0
        trade_total_size = 0
        trade_stats = {}
        
        for item in crypto_trades_path.iterdir():
            if item.is_dir():
                for parquet_file in item.rglob("*.parquet"):
                    trade_total_files += 1
                    file_size = parquet_file.stat().st_size
                    trade_total_size += file_size
                    
                    parts = parquet_file.relative_to(crypto_trades_path).parts
                    if len(parts) >= 3:
                        symbol = parts[0].replace("symbol=", "")
                        year = parts[1].replace("year=", "")
                        month = parts[2].replace("month=", "")
                        key = f"{symbol}/{year}/{month}"
                        if key not in trade_stats:
                            trade_stats[key] = {"files": 0, "size": 0}
                        trade_stats[key]["files"] += 1
                        trade_stats[key]["size"] += file_size
        
        print(f"   • Trades总文件数: {trade_total_files}")
        print(f"   • Trades总大小: {trade_total_size / 1024 / 1024:.2f} MB ({trade_total_size / 1024 / 1024 / 1024:.2f} GB)")
        
        if trade_stats:
            print(f"\n🗂️  Trades数据按符号和时间统计:")
            for key, stats in sorted(trade_stats.items()):
                print(f"   • {key}: {stats['files']} 个文件, {stats['size'] / 1024 / 1024:.2f} MB")
    else:
        print(f"   ❌ Trades数据目录不存在: {crypto_trades_path}")
    
    # 检查features目录
    print(f"\n🔍 检查特征数据目录:")
    features_path = get_data_lake_subpath("features")
    if features_path.exists():
        print(f"   Features目录: {features_path}")
        
        features_total_files = 0
        features_total_size = 0
        
        for item in features_path.rglob("*.parquet"):
            features_total_files += 1
            file_size = item.stat().st_size
            features_total_size += file_size
        
        print(f"   • Features总文件数: {features_total_files}")
        print(f"   • Features总大小: {features_total_size / 1024 / 1024:.2f} MB ({features_total_size / 1024 / 1024 / 1024:.2f} GB)")
        
        # 列出主要子目录
        print(f"\n🗂️  Features子目录:")
        for subdir in [d for d in features_path.iterdir() if d.is_dir()][:10]:
            subdir_size = sum(f.stat().st_size for f in subdir.rglob("*") if f.is_file())
            print(f"   • {subdir.name}: {subdir_size / 1024 / 1024:.2f} MB")
    else:
        print(f"   ❌ Features目录不存在: {features_path}")
    
    print(f"\n{'=' * 80}")
    print("✅ 检查完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    check_orderbook_data()
