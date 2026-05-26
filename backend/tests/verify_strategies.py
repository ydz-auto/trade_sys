#!/usr/bin/env python3
"""
策略验证脚本
检查所有策略是否正确注册
"""
import sys
from pathlib import Path

# Add the backend dir to sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from infrastructure.logging import setup_root_logger
setup_root_logger()

from engines.compute.strategy.strategies import create_default_strategies
from engines.compute.strategy.registry import (
    list_strategies, get_strategy_info, get_strategy
)


def verify_strategies():
    print("=" * 80)
    print("策略验证")
    print("=" * 80)
    
    # 1. 检查策略列表
    print("\n1. 检查策略注册表中的所有策略:")
    strategies = list_strategies()
    print(f"   共有 {len(strategies)} 个策略已注册")
    
    strategy_ids = [s.strategy_id for s in strategies]
    print(f"   策略ID列表:")
    for i, sid in enumerate(sorted(strategy_ids), 1):
        info = get_strategy_info(sid)
        print(f"   {i:2d}. {sid} - {info.name}")
    
    # 2. 检查 create_default_strategies 创建的策略
    print("\n2. 检查 create_default_strategies 函数:")
    try:
        orchestrator = create_default_strategies(symbols=["BTCUSDT"])
        active_strategies = orchestrator.get_active_strategy_ids()
        print(f"   成功创建编排器，共有 {len(active_strategies)} 个策略")
        print(f"   策略ID:")
        for i, sid in enumerate(sorted(active_strategies), 1):
            print(f"   {i:2d}. {sid}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 验证缺失的策略（基于文档对比
    print("\n3. 文档中提到的策略（来自 BACKTEST_35_STRATEGIES.md 和 backtest_26_strategies.py):")
    documented_strategies = [
        # 基础策略
        "rsi_oversold", "rsi_overbought", "macd_cross", 
        "sma_cross", "ema_cross", "bollinger_bands", "momentum",
        # 高级策略
        "panic_reversal", "long_liquidation_bounce", "volume_climax_fade",
        "weak_bounce_short", "dead_cat_echo", "oi_flush", "short_squeeze",
        "funding_exhaustion_trap", "imbalance_pressure", "sweep_detection",
        "liquidity_vacuum", "aggressive_flow", "breakout", "trend_following",
        "volatility_expansion", "bb_compression_breakout", "momentum_ignition",
        "lead_lag", "premium_divergence"
    ]
    
    print(f"   文档中提到 {len(documented_strategies)} 个策略")
    
    # 检查缺失
    missing = []
    found = []
    for sid in documented_strategies:
        if get_strategy_info(sid):
            found.append(sid)
        else:
            missing.append(sid)
    
    print(f"\n✅ 已找到 {len(found)} 个策略")
    if missing:
        print(f"❌ 缺失 {len(missing)} 个策略: {missing}")
    else:
        print(f"✅ 所有文档中提到的策略都已注册！")
    
    print("\n" + "=" * 80)
    print("验证完成!")
    print("=" * 80)
    
    return {
        "total_registered": len(strategies),
        "found": len(found),
        "missing": missing
    }


if __name__ == "__main__":
    verify_strategies()
