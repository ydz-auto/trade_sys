#!/usr/bin/env python3
"""
市场行为研究系统 - 使用示例

这个系统不是"预测未来"，而是"统计历史行为规律"
"""

import sys
from pathlib import Path

# 添加backend到路径
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from datetime import datetime

import pandas as pd

from services.research_service import MarketBehaviorResearchSystem, run_market_behavior_analysis


def main():
    print("="*70)
    print("📊 市场行为研究系统")
    print("="*70)
    
    # 加载数据
    data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
    
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        print("请先运行: python scripts/generate_market_structure_features.py")
        return
    
    print(f"\n📥 加载数据: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"   总行数: {len(df)}")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    
    # 取2024年数据进行研究
    df_2024 = df[df["timestamp"].dt.year == 2024].copy()
    print(f"   研究样本: {len(df_2024)} 行 (2024全年)")
    
    # 运行市场行为分析
    print("\n" + "="*70)
    print("🔍 开始市场行为研究...")
    print("="*70)
    
    system = MarketBehaviorResearchSystem()
    result = system.analyze(df_2024)
    
    # 打印报告
    system.print_report(result)
    
    # 保存详细结果
    output_dir = backend_path / "data_lake/research"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存事件
    print(f"\n💾 保存研究结果...")
    
    result_file = output_dir / "market_behavior_analysis.json"
    
    # 转换为可序列化格式
    import json
    
    # 保存统计结果
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"   ✅ 已保存到: {result_file}")
    
    print("\n" + "="*70)
    print("✅ 市场行为研究完成！")
    print("="*70)


if __name__ == "__main__":
    main()
