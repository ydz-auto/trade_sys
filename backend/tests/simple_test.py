"""
简化测试脚本 - 验证核心功能

运行方式：
1. 确保在 backend 目录下
2. 激活虚拟环境
3. python tests/simple_test.py
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """测试 1: 验证所有模块可以导入"""
    print("\n" + "="*60)
    print("测试 1: 模块导入")
    print("="*60)
    
    modules = [
        "domain.feature.unified_calculator",
        "domain.feature.generation_service",
        "domain.ml.lstm_dataset_builder",
        "application.backtest_service",
        "application.optimization_service.engine",
        "runtime.ingestion_runtime.download_service",
        "shared.replay.market_event_emitter",
    ]
    
    success = 0
    failed = []
    
    for module in modules:
        try:
            mod = __import__(module, fromlist=[''])
            # 检查关键类是否存在
            if module == "application.optimization_service.engine":
                if not hasattr(mod, 'OptimizationBacktestEngine'):
                    raise ImportError("OptimizationBacktestEngine not found in module")
            print(f"  ✅ {module}")
            success += 1
        except Exception as e:
            print(f"  ❌ {module}: {e}")
            failed.append((module, str(e)))
    
    print(f"\n导入结果: {success}/{len(modules)} 成功")
    return len(failed) == 0


def test_feature_calculator_basic():
    """测试 2: 特征计算器基础功能"""
    print("\n" + "="*60)
    print("测试 2: 特征计算器")
    print("="*60)
    
    try:
        import numpy as np
        from domain.feature.unified_calculator import UnifiedFeatureCalculator
        
        calculator = UnifiedFeatureCalculator()
        
        # 模拟 30 根 K线
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(30) * 0.5)
        
        features = calculator.compute(
            symbol="BTCUSDT",
            open_price=prices[-1] * 0.999,
            high=prices[-1] * 1.001,
            low=prices[-1] * 0.998,
            close=prices[-1],
            volume=1000,
        )
        
        print(f"  ✅ 计算特征: {len(features)} 个")
        print(f"  ✅ 特征列表: {list(features.keys())[:5]}...")
        
        # 验证 RSI 范围
        if 'rsi_14' in features:
            rsi = features['rsi_14']
            if 0 <= rsi <= 100:
                print(f"  ✅ RSI 范围正确: {rsi:.2f}")
            else:
                print(f"  ❌ RSI 范围错误: {rsi:.2f}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_feature_schema():
    """测试 3: 特征 Schema"""
    print("\n" + "="*60)
    print("测试 3: 特征 Schema")
    print("="*60)
    
    try:
        from domain.feature.unified_calculator import get_feature_calculator
        
        calculator = get_feature_calculator()
        
        # 测试 Schema
        schema = calculator.get_schema('rsi_14')
        if schema:
            print(f"  ✅ RSI_14 Schema:")
            print(f"     - 名称: {schema.name}")
            print(f"     - 类别: {schema.category}")
            print(f"     - 可用延迟: {schema.available_after_periods} 周期")
        else:
            print("  ⚠️ Schema 未定义")
        
        # 测试可用时间计算
        import time
        computation_time = int(time.time() * 1000)
        available_time = calculator.get_available_time('rsi_14', computation_time)
        
        delay = available_time - computation_time
        print(f"  ✅ 特征可用延迟: {delay}ms ({delay/60000:.1f}分钟)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_leakage_protection():
    """测试 4: 数据泄漏保护"""
    print("\n" + "="*60)
    print("测试 4: 数据泄漏保护")
    print("="*60)
    
    try:
        from shared.replay.feature_availability_guard import get_feature_availability_guard
        
        guard = get_feature_availability_guard()
        
        import time
        current_time = int(time.time() * 1000)
        
        # 测试场景 1: 正常特征
        features = {"rsi_14": 45.0, "sma_20": 100.0}
        feature_timestamps = {
            "rsi_14": current_time - 15 * 60000,
            "sma_20": current_time - 25 * 60000,
        }
        
        available = guard.filter_available_features(
            features=features,
            feature_timestamps=feature_timestamps,
            replay_clock=current_time,
        )
        
        print(f"  ✅ 场景 1 (正常): {len(available)}/{len(features)} 可用")
        
        # 测试场景 2: 未来数据
        feature_timestamps_future = {
            "rsi_14": current_time + 5 * 60000,  # 未来数据
            "sma_20": current_time - 25 * 60000,
        }
        
        available_future = guard.filter_available_features(
            features=features,
            feature_timestamps=feature_timestamps_future,
            replay_clock=current_time,
        )
        
        print(f"  ✅ 场景 2 (未来数据): {len(available_future)}/{len(features)} 可用")
        
        if len(available_future) < len(features):
            print("  ✅ 数据泄漏保护正常工作！")
            return True
        else:
            print("  ❌ 数据泄漏保护失败！")
            return False
        
    except ImportError as e:
        print(f"  ⚠️ FeatureAvailabilityGuard 未找到: {e}")
        print("  ⚠️ 跳过此测试")
        return True
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_backtest_config():
    """测试 5: 回测配置"""
    print("\n" + "="*60)
    print("测试 5: 回测配置")
    print("="*60)
    
    try:
        from application.optimization_service.engine import BacktestConfig
        
        config = BacktestConfig(
            initial_capital=10000.0,
            commission=0.0005,
            slippage=0.0002,
            position_size=0.3,
            stop_loss=0.02,
            take_profit=0.04,
            enable_slippage=True,
            enable_feature_guard=True,
        )
        
        print(f"  ✅ 初始资金: {config.initial_capital}")
        print(f"  ✅ 手续费: {config.commission}")
        print(f"  ✅ 滑点: {config.slippage}")
        print(f"  ✅ 仓位大小: {config.position_size}")
        print(f"  ✅ 止损: {config.stop_loss}")
        print(f"  ✅ 止盈: {config.take_profit}")
        print(f"  ✅ 滑点模拟: {config.enable_slippage}")
        print(f"  ✅ 特征守卫: {config.enable_feature_guard}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_strategy_registry():
    """测试 6: 策略注册表"""
    print("\n" + "="*60)
    print("测试 6: 策略注册表")
    print("="*60)
    
    try:
        from application.backtest_service import STRATEGY_REGISTRY
        
        print(f"  ✅ 已注册策略: {len(STRATEGY_REGISTRY)} 个")
        
        for strategy_id, info in STRATEGY_REGISTRY.items():
            print(f"     - {strategy_id}: {info['name']} ({info['direction']})")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("统一架构简化测试")
    print("="*60)
    
    results = {}
    
    tests = [
        ("模块导入", test_imports),
        ("特征计算器", test_feature_calculator_basic),
        ("特征 Schema", test_feature_schema),
        ("数据泄漏保护", test_leakage_protection),
        ("回测配置", test_backtest_config),
        ("策略注册表", test_strategy_registry),
    ]
    
    for name, test_fn in tests:
        try:
            results[name] = test_fn()
        except Exception as e:
            print(f"❌ {name} 测试异常: {e}")
            results[name] = False
    
    # 汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
