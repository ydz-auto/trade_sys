#!/usr/bin/env python3
"""
演示：策略自动发现与自学习系统
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

from services.strategy_service.strategy_discovery import (
    StrategyDiscoveryEngine,
    demo_auto_discovery,
)
from services.strategy_service.strategies import create_default_strategies


def main():
    print("\n" + "=" * 100)
    print("🚀 Crypto 策略自动发现系统演示")
    print("=" * 100)
    
    print("\n📌 1. 创建策略编排器（包含手动添加的策略）")
    orchestrator = create_default_strategies()
    print(f"   已加载 {len(orchestrator._strategies)} 个策略")
    for s in orchestrator._strategies:
        print(f"   - {s}")
    
    print("\n📌 2. 初始化策略发现引擎")
    engine = StrategyDiscoveryEngine(
        min_win_rate=0.55,  # 降低胜率要求
        min_sample_size=20,  # 降低样本要求
        min_avg_return=0.001,  # 降低收益要求
    )
    
    print("\n📌 3. 加载市场数据并自动发现策略")
    df = engine.load_market_data()
    
    if df.empty:
        print("⚠️ 未找到数据，跳过演示")
        return
    
    print(f"   数据加载成功: {len(df)} 条记录")
    
    print("\n📌 4. 自动发现并添加策略")
    new_strategies = engine.auto_discover_and_add(
        df=df,
        orchestrator=orchestrator,
        max_strategies=3,
    )
    
    print("\n📌 5. 打印发现报告")
    engine.print_discovery_report()
    
    print("\n📌 6. 保存发现的模式")
    output_path = backend_path / "data_lake" / "research" / "auto_discovered_patterns.json"
    engine.save_discovered_patterns(str(output_path))
    
    print("\n" + "=" * 100)
    print("✅ 演示完成!")
    print("=" * 100)
    print(f"   总策略数量: {len(orchestrator._strategies)}")
    print(f"   手动添加的: 3个 (RSI, MACD, Panic Reversal)")
    print(f"   自动发现的: {len(new_strategies)}个")
    print(f"   输出文件: {output_path}")


if __name__ == "__main__":
    main()
