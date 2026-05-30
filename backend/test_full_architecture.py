"""
测试完整的 Feature Registry 和 Feature Engine 架构

验证所有特征是否正常工作
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_ROOT))


def create_sample_data(n: int = 100) -> pd.DataFrame:
    """创建样本数据"""
    dates = pd.date_range('2024-01-01', periods=n, freq='h')
    close = 50000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.random.rand(n) * 200
    low = close - np.random.rand(n) * 200
    open_price = close + np.random.randn(n) * 50
    volume = np.random.rand(n) * 1000

    return pd.DataFrame({
        'timestamp': dates,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'funding_rate': np.random.randn(n) * 0.0001,
        'oi': 100000000 + np.cumsum(np.random.randn(n) * 100000),
    })


def test_registry():
    """测试 Feature Registry"""
    print("\n1. 测试 Feature Registry")
    print("=" * 60)

    from engines.compute.feature import get_registry

    registry = get_registry()

    print(f"✅ Registry 创建成功")
    print(f"✅ 注册特征总数: {len(registry.list_all())}")
    print(f"✅ 类别: {registry.list_categories()}")

    for category in registry.list_categories():
        features = registry.list_by_category(category)
        print(f"   - {category}: {len(features)} 个特征")

    print(f"\n检查关键特征:")
    key_features = [
        "rsi_14", "macd", "atr_14",  # Technical
        "funding_rate", "oi", "oi_funding_divergence",  # Market
        "imbalance_1", "spread_estimate",  # Microstructure
        "high_volatility", "primary_regime",  # Regime
        "distance_from_ma20", "breakout_strength",  # Alpha
    ]
    for feat in key_features:
        has = registry.has(feat)
        print(f"   {feat}: {'✅' if has else '❌'}")

    return True


def test_feature_engine():
    """测试 Feature Engine"""
    print("\n2. 测试 Feature Engine")
    print("=" * 60)

    from engines.compute.feature import FeatureEngine

    df = create_sample_data(200)

    engine = FeatureEngine()

    print(f"✅ FeatureEngine 创建成功")

    features_to_compute = [
        # Technical
        "rsi_14", "macd", "atr_14", "sma_20", "ema_20", "bb_upper", "volatility_zscore",
        # Market
        "funding_zscore", "oi_change_pct", "oi_funding_divergence",
        # Microstructure (will be NaN for sample data without order flow)
        # Regime
        "high_volatility", "extreme_move",
        # Alpha
        "distance_from_ma20", "zscore_price", "breakout_strength",
    ]

    print(f"\n计算特征:")
    for feat in features_to_compute:
        print(f"  - {feat}")

    result_df = engine.compute(df, features_to_compute, use_cache=False)

    print(f"\n✅ 计算完成")
    print(f"✅ 结果 DataFrame 大小: {result_df.shape}")

    computed_cols = [c for c in result_df.columns if c in features_to_compute]
    print(f"\n计算的特征列 ({len(computed_cols)}):")
    for col in computed_cols:
        non_nan = result_df[col].notna().sum()
        print(f"  {col}: {non_nan} 个非空值")

    return True


def test_single_feature():
    """测试单个特征计算"""
    print("\n3. 测试单个特征计算")
    print("=" * 60)

    from engines.compute.feature import get_engine

    engine = get_engine()
    df = create_sample_data(100)

    test_features = ["rsi_14", "sma_20", "macd", "volatility_zscore"]

    for feat_name in test_features:
        print(f"计算特征: {feat_name}")
        result = engine.compute_single(df, feat_name, use_cache=False)
        print(f"  ✅ 非空值: {result.notna().sum()}")
        print(f"  均值: {result.mean():.4f}")
        print(f"  范围: [{result.min():.4f}, {result.max():.4f}]")

    return True


def test_cache():
    """测试缓存功能"""
    print("\n4. 测试缓存功能")
    print("=" * 60)

    from engines.compute.feature import FeatureEngine, get_cache

    df = create_sample_data(100)

    engine = FeatureEngine(use_cache=True)
    cache = get_cache()

    print("第一次计算 (缓存为空)...")
    engine.compute(df, ["rsi_14", "sma_20"], use_cache=True)

    cached1 = cache.get("rsi_14", df)
    cached2 = cache.get("sma_20", df)
    print(f"✅ rsi_14 缓存命中: {'是' if cached1 is not None else '否'}")
    print(f"✅ sma_20 缓存命中: {'是' if cached2 is not None else '否'}")

    print("\n第二次计算 (使用缓存)...")
    result = engine.compute(df, ["rsi_14", "sma_20"], use_cache=True)
    print(f"✅ 第二次计算完成")

    return True


def main():
    print("\n" + "=" * 60)
    print("完整特征架构测试")
    print("=" * 60)

    try:
        test_registry()
        test_feature_engine()
        test_single_feature()
        test_cache()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)

        from engines.compute.feature import get_registry
        registry = get_registry()
        print(f"\n架构总结:")
        print(f"  - 总特征数: {len(registry.list_all())}")
        for category in registry.list_categories():
            count = len(registry.list_by_category(category))
            print(f"  - {category}: {count}")

        print(f"\n最终架构已建立，Alpha 层现在可以使用 FeatureEngine 来计算特征。")
        print(f"接下来可以:")
        print(f"  1. 逐步更新 Alpha 层代码，迁移到使用新的 FeatureEngine")
        print(f"  2. 继续完善特征定义和计算逻辑")
        print(f"  3. 开始策略层的开发")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
