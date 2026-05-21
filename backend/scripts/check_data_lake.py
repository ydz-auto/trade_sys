#!/usr/bin/env python3
"""
检查数据湖整体结构
"""

import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.data_lake import get_data_lake_subpath, get_data_lake_root


def check_data_lake():
    """检查数据湖结构"""
    print("=" * 80)
    print("🏊 数据湖整体结构检查")
    print("=" * 80)
    
    data_lake_root = get_data_lake_root()
    print(f"\n📁 数据湖根目录: {data_lake_root}")
    
    if not data_lake_root.exists():
        print(f"❌ 数据湖根目录不存在！")
        return
    
    # 列出顶层目录
    print(f"\n🗂️  顶层目录:")
    for item in sorted(data_lake_root.iterdir()):
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
    crypto_path = data_lake_root / "crypto"
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
    
    print(f"\n{'=' * 80}")
    print("✅ 检查完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    check_data_lake()
