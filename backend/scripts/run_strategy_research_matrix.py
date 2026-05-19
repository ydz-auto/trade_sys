#!/usr/bin/env python3
"""
策略研究矩阵 - 运行脚本

运行完整的 Event Study + Contextual Analysis
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
import pandas as pd

from services.research_service.strategy_research_matrix import run_research


def main():
    print("="*80)
    print("🚀 策略研究矩阵 - Event Study Framework")
    print("="*80)
    
    data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
    
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        print("请先运行: python scripts/generate_market_structure_features.py")
        return
    
    print(f"\n📥 加载数据: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"   总行数: {len(df)}")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    
    df_2024 = df[df["timestamp"].dt.year == 2024].copy()
    print(f"   研究样本: {len(df_2024)} 行 (2024全年)")
    
    print("\n" + "="*80)
    print("🔍 开始策略研究矩阵分析...")
    print("="*80)
    
    result = run_research(df_2024)
    
    output_dir = backend_path / "data_lake/research"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = output_dir / "strategy_research_matrix_2024.json"
    
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n💾 结果已保存到: {result_file}")
    
    print("\n" + "="*80)
    print("✅ 策略研究矩阵分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()
