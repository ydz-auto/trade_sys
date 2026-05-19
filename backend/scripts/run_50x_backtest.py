#!/usr/bin/env python3
"""
完整策略研究矩阵 - 50倍合约回测

运行完整Pipeline：
1. Feature Engine → Feature Matrix
2. Event Detection → Event Table
3. Context Engine → Context Tags
4. Outcome Engine → Outcome Table
5. Playbook Database → Playbook
6. Event Study Backtest → 50x回测报告
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import pandas as pd
from services.research_service.strategy_research_pipeline import (
    StrategyResearchPipeline,
    run_pipeline_with_backtest
)


def main():
    print("="*80)
    print("🚀 完整策略研究矩阵 - 50倍合约回测")
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
    
    from datetime import datetime, timedelta
    
    now = datetime.now()
    three_months_ago = now - timedelta(days=90)
    
    df_recent = df[df["timestamp"] >= pd.Timestamp(three_months_ago)].copy()
    
    print(f"   研究样本: {len(df_recent)} 行 (最近3个月)")
    print(f"   时间范围: {df_recent['timestamp'].min()} ~ {df_recent['timestamp'].max()}")
    
    print("\n" + "="*80)
    print("🔍 Step 1-5: 运行完整Pipeline...")
    print("="*80)
    
    pipeline = StrategyResearchPipeline()
    result = pipeline.run_full_pipeline(df_recent)
    
    print(f"\n📊 Pipeline结果:")
    print(f"   总事件数: {result['total_events']}")
    print(f"   Playbook数: {len(result['playbooks'])}")
    
    for et, count in result["events_by_type"].items():
        print(f"   - {et}: {count}")
    
    print("\n" + "="*80)
    print("📈 Step 6: 50倍合约回测...")
    print("="*80)
    
    results = run_pipeline_with_backtest(df_recent, leverage=50)
    
    print("\n" + "="*80)
    print("💾 保存结果...")
    print("="*80)
    
    output_dir = backend_path / "data_lake/research/50x_backtest_3months"
    pipeline.save_results(results, output_dir)
    
    print(f"\n✅ 全部完成！")
    print(f"   结果保存在: {output_dir}")


if __name__ == "__main__":
    main()
