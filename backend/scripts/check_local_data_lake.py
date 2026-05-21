#!/usr/bin/env python3
"""
检查本地数据湖结构
"""

import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_local_data_lake():
    """检查本地数据湖结构"""
    print("=" * 80)
    print("🏊 本地数据湖结构检查")
    print("=" * 80)
    
    local_data_lake = project_root / "data_lake"
    print(f"\n📁 本地数据湖: {local_data_lake}")
    
    if not local_data_lake.exists():
        print(f"❌ 本地数据湖目录不存在！")
        return
    
    # 列出顶层目录
    print(f"\n🗂️  顶层目录:")
    for item in sorted(local_data_lake.iterdir()):
        if item.is_dir():
            # 计算目录大小
            try:
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                size_mb = size / 1024 / 1024
                size_gb = size / 1024 / 1024 / 1024
                if size_gb >= 1:
                    size_str = f"{size_gb:.2f} GB"
                else:
                    size_str = f"{size_mb:.2f} MB"
                print(f"   • {item.name}/: {size_str}")
            except:
                print(f"   • {item.name}/")
    
    # 检查crypto目录
    crypto_path = local_data_lake / "crypto"
    if crypto_path.exists():
        print(f"\n🔍 加密货币数据:")
        for exchange_dir in sorted(crypto_path.iterdir()):
            if exchange_dir.is_dir():
                print(f"\n   📊 {exchange_dir.name}:")
                for data_type_dir in sorted(exchange_dir.iterdir()):
                    if data_type_dir.is_dir():
                        try:
                            size = sum(f.stat().st_size for f in data_type_dir.rglob("*.parquet") if f.is_file())
                            count = len(list(data_type_dir.rglob("*.parquet")))
                            size_mb = size / 1024 / 1024
                            size_gb = size / 1024 / 1024 / 1024
                            if size_gb >= 1:
                                size_str = f"{size_gb:.2f} GB"
                            else:
                                size_str = f"{size_mb:.2f} MB"
                            print(f"      • {data_type_dir.name}/: {count} files, {size_str}")
                            
                            # 列出符号
                            symbols = []
                            for sym_dir in data_type_dir.iterdir():
                                if sym_dir.is_dir():
                                    sym_name = sym_dir.name.replace("symbol=", "")
                                    symbols.append(sym_name)
                            if symbols:
                                print(f"        符号: {', '.join(sorted(symbols[:5]))}")
                                if len(symbols) > 5:
                                    print(f"        ... 共 {len(symbols)} 个符号")
                        except:
                            print(f"      • {data_type_dir.name}/")
    
    # 检查orderbook_features
    orderbook_path = local_data_lake / "orderbook_features"
    if orderbook_path.exists():
        print(f"\n🔍 OrderBook特征:")
        try:
            size = sum(f.stat().st_size for f in orderbook_path.rglob("*.parquet") if f.is_file())
            count = len(list(orderbook_path.rglob("*.parquet")))
            size_mb = size / 1024 / 1024
            size_gb = size / 1024 / 1024 / 1024
            if size_gb >= 1:
                size_str = f"{size_gb:.2f} GB"
            else:
                size_str = f"{size_mb:.2f} MB"
            print(f"   • {count} files, {size_str}")
        except:
            print(f"   • orderbook_features/")
    else:
        print(f"\n⚠️  orderbook_features目录不存在")
    
    # 检查features目录
    features_path = local_data_lake / "features"
    if features_path.exists():
        print(f"\n🔍 特征数据:")
        try:
            size = sum(f.stat().st_size for f in features_path.rglob("*.parquet") if f.is_file())
            count = len(list(features_path.rglob("*.parquet")))
            size_mb = size / 1024 / 1024
            size_gb = size / 1024 / 1024 / 1024
            if size_gb >= 1:
                size_str = f"{size_gb:.2f} GB"
            else:
                size_str = f"{size_mb:.2f} MB"
            print(f"   • {count} files, {size_str}")
            
            print(f"\n   📂 Features子目录:")
            for subdir in sorted([d for d in features_path.iterdir() if d.is_dir()]):
                try:
                    subdir_size = sum(f.stat().st_size for f in subdir.rglob("*") if f.is_file())
                    subdir_size_mb = subdir_size / 1024 / 1024
                    subdir_size_gb = subdir_size / 1024 / 1024 / 1024
                    if subdir_size_gb >= 1:
                        subdir_size_str = f"{subdir_size_gb:.2f} GB"
                    else:
                        subdir_size_str = f"{subdir_size_mb:.2f} MB"
                    print(f"      • {subdir.name}/: {subdir_size_str}")
                except:
                    pass
        except:
            print(f"   • features/")
    else:
        print(f"\n⚠️  features目录不存在")
    
    print(f"\n{'=' * 80}")
    print("✅ 检查完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    check_local_data_lake()
