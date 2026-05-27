#!/usr/bin/env python3
"""
Signal Runtime - 完整链路演示

演示流程：
    Feature Runtime → Strategy Registry → Signal Runtime → Regime Runtime

包含策略：
    - 第一梯队：爆仓行为策略、OI/资金费率策略
    - 第二梯队：微观结构策略
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import time
from typing import Dict, Any, List

from infrastructure.logging import get_logger, setup_logging

logger = get_logger("signal_runtime.main")

# 设置日志
setup_logging("DEBUG")

# 导入运行时
from runtime.signal_runtime.runtime import (
    get_signal_runtime,
    TimeCausalSignalRuntime,
    SignalConfig
)
from engines.compute.strategy.registry import list_strategies
from engines.compute.strategy.strategies import create_default_strategies


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def demo_integration():
    """演示完整的策略集成链路"""
    
    print_header("1. 策略发现与加载")
    
    # 1. 列出已注册的策略
    all_strategies = list_strategies()
    print(f"  已注册策略总数: {len(all_strategies)}")
    print(f"  策略列表:")
    for s in all_strategies:
        tier_marker = "★" if s.tier == 1 else "☆"
        print(f"    {tier_marker} {s.strategy_id:<30} | {s.name}")
    
    # 2. 配置并初始化 Signal Runtime
    print_header("2. 初始化 Signal Runtime")
    
    config = SignalConfig(
        symbols=["BTCUSDT"],
        mode="paper",
        enable_strategy_registry=True
    )
    
    runtime = get_signal_runtime(config)
    
    # 初始化并自动从 registry 加载策略
    await runtime.initialize(
        symbol="BTCUSDT",
        mode="paper",
        auto_load_strategies=True
    )
    
    print(f"\n  已加载策略: {len(runtime.get_registered_strategies())}")
    for strategy_id in runtime.get_registered_strategies():
        print(f"    - {strategy_id}")
    
    # 3. 模拟市场数据并生成信号
    print_header("3. 模拟信号生成")
    
    # 模拟一些特征更新
    timestamp = int(time.time() * 1000)
    
    # 回调来记录信号
    received_signals = []
    
    def signal_callback(signal: Dict[str, Any]):
        received_signals.append(signal)
        print(f"\n  📊 收到信号:")
        print(f"    策略: {signal.get('strategy_id')}")
        print(f"    方向: {signal.get('signal_type')}")
        print(f"    置信度: {signal.get('confidence', 0):.2%}")
        print(f"    原因: {signal.get('reason')}")
    
    runtime.add_signal_callback(signal_callback)
    
    # 模拟一些市场状态
    print("\n  正在模拟市场状态并生成信号...")
    
    # 这里只是演示，实际会从 Feature Runtime 获取真实数据
    # 我们创建一些模拟的特征
    mock_features = {
        "close": 70000.0,
        "volume": 1000.0,
        "rsi_14": 30.0,
        "macd": 0.05,
        "liquidation_long": 5000000.0,
        "funding_rate": 0.01,
    }
    
    print(f"\n  模拟特征: {mock_features}")
    
    # 直接调用策略的方式（演示用）
    for strategy_id, strategy in runtime._strategies.items():
        if not strategy.is_enabled:
            continue
            
        try:
            print(f"\n  测试策略: {strategy_id}")
            
            # 模拟数据
            mock_data = {
                "close_prices": [70000.0 - i * 10 for i in range(60, 0, -1)],
                "volumes": [1000.0 + i * 10 for i in range(60)],
                "high_prices": [70500.0 - i * 10 for i in range(60, 0, -1)],
                "low_prices": [69500.0 - i * 10 for i in range(60, 0, -1)],
                "symbol": "BTCUSDT",
                "liquidation_long": 5000000.0,
                "funding_rate": 0.01,
            }
            
            if hasattr(strategy, "calculate"):
                signal = strategy.calculate(mock_data)
                if signal:
                    print(f"    ✅ 产生信号: {signal}")
            elif hasattr(strategy, "generate_signal"):
                signal = strategy.generate_signal(mock_data)
                if signal:
                    print(f"    ✅ 产生信号: {signal}")
            
        except Exception as e:
            print(f"    ❌ 策略错误: {e}")
    
    print_header("4. 演示完成")
    print(f"\n  总结:")
    print(f"    - 已集成策略总数: {len(all_strategies)}")
    print(f"    - 链路连接状态: Feature Runtime → Strategy Registry → Signal Runtime ✓")
    print(f"    - Regime Runtime 已连接: {hasattr(runtime, '_regime_runtime') and runtime._regime_runtime is not None}")
    print(f"\n  下一步: 将 Signal Runtime 连接到 Execution Runtime")
    
    await runtime.stop()


async def demo_complete_orchestrator():
    """演示使用完整的策略编排器"""
    print_header("A. 使用 MultiStrategyOrchestrator")
    
    orchestrator = create_default_strategies(["BTCUSDT", "ETHUSDT"], attach_regime=True)
    
    print(f"\n  策略编排器已创建，包含策略:")
    all_strategies = orchestrator.get_active_strategy_ids()
    print(f"    {len(all_strategies)} 个策略已激活")
    
    print_header("B. 完整链路状态")
    print("\n  架构链路:")
    print("    ┌─────────────────┐")
    print("    │ Feature Runtime │ (特征计算)")
    print("    └────────┬────────┘")
    print("             │")
    print("    ┌────────▼────────┐")
    print("    │  Strategy Reg   │ (策略注册)")
    print("    └────────┬────────┘")
    print("             │")
    print("    ┌────────▼────────┐")
    print("    │  Signal Runtime │ (信号生成)")
    print("    └────────┬────────┘")
    print("             │")
    print("    ┌────────▼────────┐")
    print("    │  Regime Runtime │ (策略过滤)")
    print("    └────────┬────────┘")
    print("             │")
    print("    ┌────────▼────────┐")
    print("    │Execution Runtime│ (执行)")
    print("    └─────────────────┘")


def main():
    """主函数"""
    print("\n" + "#" * 80)
    print("#")
    print("#       Behavioral Derivatives Alpha Engine")
    print("#")
    print("#   Feature Runtime → Strategy Registry → Signal Runtime → Regime Runtime")
    print("#")
    print("#" * 80 + "\n")
    
    try:
        # 运行演示
        asyncio.run(demo_integration())
        print("\n")
        asyncio.run(demo_complete_orchestrator())
        
    except KeyboardInterrupt:
        print("\n\n  演示被用户中断")
    except Exception as e:
        print(f"\n\n  ❌ 演示出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "#" * 80)
    print("#  演示结束")
    print("#" * 80)


if __name__ == "__main__":
    main()
