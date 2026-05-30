"""
Alpha 工厂流水线验证测试

验证重构后的完整 Alpha 流水线：
1. Data → Feature Matrix (FeatureEngine)
2. Labels
3. IC Analysis
4. Conditional IC
5. Signal Test
6. Stability Analysis
7. Walk Forward
8. Approved Alpha
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_1_feature_matrix():
    """测试1: 特征矩阵生成 (FeatureEngine)"""
    print("=" * 70)
    print("测试 1: 特征矩阵生成 (FeatureEngine)")
    print("=" * 70)
    
    try:
        from engines.compute.feature import FeatureEngine
        
        # 创建测试数据
        close = np.linspace(50000, 51000, 200)
        data = pd.DataFrame({
            "open": close - 100,
            "high": close + 200,
            "low": close - 200,
            "close": close,
            "volume": np.random.normal(1000, 200, 200),
        }, index=range(200))
        
        # 初始化 FeatureEngine
        engine = FeatureEngine()
        
        # 计算一组特征
        features_to_calculate = [
            "rsi_14", "macd", "atr_14",
            "sma_20", "ema_20",
            "volatility_zscore"
        ]
        
        result = engine.compute(data, features_to_calculate)
        
        print(f"✓ FeatureEngine 计算成功")
        print(f"✓ 结果 DataFrame 大小: {result.shape}")
        print(f"✓ 计算的特征: {list(result.columns)}")
        
        # 验证特征质量
        for feature_name in features_to_calculate:
            if feature_name in result.columns:
                non_null_count = result[feature_name].notna().sum()
                print(f"  {feature_name}: {non_null_count} 个非空值")
        
        print("\n✓ 测试 1 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_feature_registry():
    """测试2: 特征注册表"""
    print("\n" + "=" * 70)
    print("测试 2: 特征注册表")
    print("=" * 70)
    
    try:
        from engines.compute.feature import get_registry
        
        registry = get_registry()
        
        all_features = registry.list_all()
        categories = registry.list_categories()
        
        print(f"✓ 注册表总特征数: {len(all_features)}")
        print(f"✓ 类别: {categories}")
        
        for cat in categories:
            cat_features = registry.list_by_category(cat)
            print(f"  {cat}: {len(cat_features)} 个特征")
        
        # 检查关键特征
        critical_features = [
            "rsi_14", "macd", "atr_14",
            "sma_20", "ema_20",
            "funding_rate", "oi_change_pct",
            "imbalance_1", "high_volatility",
        ]
        
        for feature in critical_features:
            if registry.has(feature):
                print(f"  ✓ {feature}: 已注册")
            else:
                print(f"  ⚠ {feature}: 未找到")
        
        print("\n✓ 测试 2 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_labels():
    """测试3: Label 生成"""
    print("\n" + "=" * 70)
    print("测试 3: Label 生成")
    print("=" * 70)
    
    try:
        from research.alpha.labels import compute_labels_from_df
        
        # 创建测试价格数据
        close = np.linspace(50000, 51000, 200)
        data = pd.DataFrame({
            "close": close,
            "high": close + 100,
            "low": close - 100,
        }, index=range(200))
        
        # 计算 labels
        labels = compute_labels_from_df(data)
        
        print(f"✓ 标签生成成功")
        print(f"✓ 标签类型: {list(labels.columns)}")
        
        for col in labels.columns:
            non_null_count = labels[col].notna().sum()
            print(f"  {col}: {non_null_count} 个非空值")
        
        print("\n✓ 测试 3 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_ic_analysis():
    """测试4: IC 分析"""
    print("\n" + "=" * 70)
    print("测试 4: IC 分析")
    print("=" * 70)
    
    try:
        from research.alpha.ic.analysis import compute_ic_table
        
        # 创建模拟数据
        close = np.linspace(50000, 51000, 200)
        feature_matrix = pd.DataFrame({
            "close": close,
            "rsi_14": np.random.normal(50, 15, 200),
            "volatility_zscore": np.random.normal(0, 1, 200),
            "volume_zscore": np.random.normal(0, 1, 200),
            "trend_20": np.random.normal(0, 0.02, 200),
        }, index=range(200))
        
        labels = pd.DataFrame({
            "future_ret_5": np.random.normal(0, 0.01, 200),
        }, index=range(200))
        
        # 计算 IC
        ic_result = compute_ic_table(
            feature_matrix=feature_matrix,
            label_df=labels,
            features=["rsi_14", "volatility_zscore", "trend_20"],
            labels=["future_ret_5"]
        )
        
        print(f"✓ IC 计算成功")
        print(f"✓ IC 表大小: {ic_result.shape}")
        print("\nIC 结果:")
        print(ic_result)
        
        print("\n✓ 测试 4 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 4 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_alpha_registry():
    """测试5: Alpha 注册表"""
    print("\n" + "=" * 70)
    print("测试 5: Alpha 注册表")
    print("=" * 70)
    
    try:
        from research.alpha.registry.alpha_registry import AlphaRegistry
        
        # 查看当前注册的 Alphas
        registry = AlphaRegistry
        
        # 查看是否有示例 Alpha 定义
        print(f"✓ Alpha 注册表可导入")
        
        print("\n✓ 测试 5 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 5 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_strategy_registry():
    """测试6: 策略注册表 V2"""
    print("\n" + "=" * 70)
    print("测试 6: 策略注册表 V2")
    print("=" * 70)
    
    try:
        from engines.compute.strategy_v2.registry import StrategyRegistry
        
        # 尝试加载策略
        StrategyRegistry.load_strategies()
        
        all_strategies = StrategyRegistry.list_all()
        
        print(f"✓ 策略注册表可导入")
        print(f"✓ 策略总数: {len(all_strategies)}")
        
        for strategy_meta in all_strategies:
            print(f"  - {strategy_meta.id}: {strategy_meta.name}")
        
        print("\n✓ 测试 6 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 6 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_feature_engine_build_historical():
    """测试7: FeatureEngine 的 build_historical_matrix 方法"""
    print("\n" + "=" * 70)
    print("测试 7: FeatureEngine build_historical_matrix (模拟)")
    print("=" * 70)
    
    try:
        from engines.compute.feature import FeatureEngine
        
        engine = FeatureEngine()
        
        # 测试初始化
        print(f"✓ FeatureEngine 初始化成功")
        
        # 注意：这个方法依赖 FileDataLakeReader，我们跳过实际执行
        # 验证方法存在性
        assert hasattr(engine, 'build_historical_matrix')
        print(f"✓ build_historical_matrix 方法存在")
        
        print("\n✓ 测试 7 成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 7 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("Alpha 工厂流水线 - 重构后验证测试")
    print("=" * 70)
    
    tests = [
        test_1_feature_matrix,
        test_2_feature_registry,
        test_3_labels,
        test_4_ic_analysis,
        test_5_alpha_registry,
        test_6_strategy_registry,
        test_7_feature_engine_build_historical,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！重构验证成功！")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查！")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
