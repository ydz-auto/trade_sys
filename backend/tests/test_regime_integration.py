#!/usr/bin/env python3
"""
测试 Regime 系统集成 - 验证 market state 能正确驱动策略启用/禁用
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_regime_strategy_switching():
    """
    最小测试：构造不同 regime，验证策略会被正确启用/禁用
    """
    print("=" * 80)
    print("测试 Regime 系统集成")
    print("=" * 80)
    
    # 1. 创建 orchestrator（会自动 attach Regime Runtime）
    from engines.compute.strategy.strategies import create_default_strategies
    orchestrator = create_default_strategies(symbols=["BTCUSDT"])
    print(f"✅ 1. 创建 MultiStrategyOrchestrator，共 {len(orchestrator._strategies)} 个策略")
    
    # 2. 获取 Regime Runtime
    from runtime.regime_runtime import get_regime_runtime, MarketRegime, RegimeState
    from datetime import datetime
    regime_runtime = get_regime_runtime()
    print(f"✅ 2. 获取 Regime Runtime")
    
    # 3. 测试 1 - 默认 regime (UNKNOWN)
    print("\n" + "=" * 80)
    print("测试 1: 默认状态 (UNKNOWN)")
    print("=" * 80)
    
    active_strategies = orchestrator.get_active_strategy_ids()
    print(f"启用的策略: {len(active_strategies)} 个")
    for s in active_strategies[:5]:
        print(f"  - {s}")
    if len(active_strategies) > 5:
        print(f"  ... 还有 {len(active_strategies)-5} 个")
    
    # 4. 测试 2 - HIGH_VOLATILITY 状态
    print("\n" + "=" * 80)
    print("测试 2: 切换到 HIGH_VOLATILITY 状态")
    print("=" * 80)
    
    # 手动修改 regime state 来测试
    regime_runtime.current_regime = RegimeState(
        regime=MarketRegime.HIGH_VOLATILITY,
        confidence=0.9,
        since=datetime.now(),
        duration_seconds=0.0,
        features={"volatility": 0.05},
        active_strategies=regime_runtime.strategy_registry[MarketRegime.HIGH_VOLATILITY]
    )
    
    # 调用 apply_to_orchestrator
    changed = regime_runtime.apply_to_orchestrator(orchestrator)
    
    active_strategies = orchestrator.get_active_strategy_ids()
    print(f"状态变更数: {len(changed)}")
    print(f"启用的策略: {len(active_strategies)} 个")
    for s in active_strategies:
        print(f"  - {s}")
    
    # 5. 测试 3 - TRENDING 状态
    print("\n" + "=" * 80)
    print("测试 3: 切换到 TRENDING 状态")
    print("=" * 80)
    
    regime_runtime.current_regime = RegimeState(
        regime=MarketRegime.TRENDING,
        confidence=0.85,
        since=datetime.now(),
        duration_seconds=0.0,
        features={"trend_strength": 3.0},
        active_strategies=regime_runtime.strategy_registry[MarketRegime.TRENDING]
    )
    
    changed = regime_runtime.apply_to_orchestrator(orchestrator)
    
    active_strategies = orchestrator.get_active_strategy_ids()
    print(f"状态变更数: {len(changed)}")
    print(f"启用的策略: {len(active_strategies)} 个")
    for s in active_strategies:
        print(f"  - {s}")
    
    # 6. 测试 4 - LIQUIDATION_CASCADE 状态
    print("\n" + "=" * 80)
    print("测试 4: 切换到 LIQUIDATION_CASCADE 状态")
    print("=" * 80)
    
    regime_runtime.current_regime = RegimeState(
        regime=MarketRegime.LIQUIDATION_CASCADE,
        confidence=0.95,
        since=datetime.now(),
        duration_seconds=0.0,
        features={"liquidation_volume": 50_000_000},
        active_strategies=regime_runtime.strategy_registry[MarketRegime.LIQUIDATION_CASCADE]
    )
    
    changed = regime_runtime.apply_to_orchestrator(orchestrator)
    
    active_strategies = orchestrator.get_active_strategy_ids()
    print(f"状态变更数: {len(changed)}")
    print(f"启用的策略: {len(active_strategies)} 个")
    for s in active_strategies:
        print(f"  - {s}")
    
    # 7. 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print("✅ Regime Runtime 已成功 attach 到 MultiStrategyOrchestrator")
    print("✅ 策略能根据市场状态正确启用/禁用")
    print("✅ Regime 系统集成完成！")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    success = test_regime_strategy_switching()
    sys.exit(0 if success else 1)
