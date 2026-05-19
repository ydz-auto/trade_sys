#!/usr/bin/env python3
"""
Crypto Behavioral Playbooks - 完整研究系统

运行所有顶级Crypto市场行为策略研究
"""

import sys
from pathlib import Path

# 添加backend到路径
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import json
from datetime import datetime

import pandas as pd

from services.research_service.crypto_behavioral_playbooks import CryptoBehavioralPlaybooks


def main():
    print("="*80)
    print("🚀 CRYPTO BEHAVIORAL PLAYBOOKS 研究系统")
    print("="*80)
    
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
    
    # 运行分析
    print("\n" + "="*80)
    print("🔍 开始 Crypto Behavioral Playbooks 研究...")
    print("="*80)
    
    system = CryptoBehavioralPlaybooks()
    result = system.analyze(df_2024)
    
    # 打印报告
    system.print_report(result)
    
    # 保存结果
    output_dir = backend_path / "data_lake/research"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = output_dir / "crypto_behavioral_playbooks_2024.json"
    
    # 转换为可序列化格式
    def make_serializable(obj):
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return make_serializable(obj.__dict__)
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)
    
    serializable_result = make_serializable(result)
    
    with open(result_file, "w") as f:
        json.dump(serializable_result, f, indent=2)
    
    print(f"\n💾 结果已保存到: {result_file}")
    
    # 生成摘要
    print("\n" + "="*80)
    print("📋 关键发现摘要")
    print("="*80)
    
    for playbook_type, stats in result.get("playbooks", {}).items():
        playbook_name = getattr(stats, 'playbook_name', playbook_type)
        total_events = getattr(stats, 'total_events', 0)
        avg_return_1h = getattr(stats, 'avg_return_1h', 0)
        positive_rate_1h = getattr(stats, 'positive_rate_1h', 0)
        best_entry = getattr(stats, 'best_entry_window', 'unknown')
        best_exit = getattr(stats, 'best_exit_window', 'unknown')
        
        print(f"\n🎯 {playbook_name}:")
        print(f"   样本数: {total_events}")
        print(f"   1h平均收益: {avg_return_1h*100:+.2f}%")
        print(f"   正收益概率: {positive_rate_1h*100:.1f}%")
        print(f"   最佳入场: {best_entry}")
        print(f"   最佳出场: {best_exit}")
    
    print("\n" + "="*80)
    print("✅ Crypto Behavioral Playbooks 研究完成！")
    print("="*80)


if __name__ == "__main__":
    main()
