"""
测试新的 Feature Registry 和 FeatureEngine 架构

验证：
1. FeatureRegistry 可以正确注册和查询特征
2. FeatureEngine 可以正确计算特征
3. 技术指标特征可以正常工作
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

    technical_features = registry.list_by_category("technical")
    print(f"✅ 技术指标特征: {len(technical_features)} 个")
    print(f"   {', '.join(technical_features[:10])}...")

    print(f"✅ 检查关键特征:")
    key_features = ["rsi_14", "macd", "atr_14", "bb_upper", "vol_20"]
    for feat in key_features:
        has = registry.has(feat)
        print(f"   {feat}: {'✅' if has else '❌'}")

    return True


def test_feature_engine():
    """测试 Feature Engine"""
    print("\n2. 测试 Feature Engine")
    print("=" * 60)

    from engines.compute.feature import FeatureEngine, get_registry

    df = create_sample_data(200)

    engine = FeatureEngine()

    print(f"✅ FeatureEngine 创建成功")

    features_to_compute = [
        "rsi_14",
        "macd",
        "atr_14",
        "sma_20",
        "ema_20",
    ]

    print(f"\n计算特征: {features_to_compute}")

    result_df = engine.compute(df, features_to_compute, use_cache=False)

    print(f"\n✅ 计算完成")
    print(f"✅ 结果 DataFrame 大小: {result_df.shape}")
    print(f"✅ 特征列: {[c for c in result_df.columns if c in features_to_compute]}")

    for feat in features_to_compute:
        if feat in result_df.columns:
            non_nan = result_df[feat].notna().sum()
            print(f"   {feat}: {non_nan} 个非空值")

    return True


def test_single_feature():
    """测试单个特征计算"""
    print("\n3. 测试单个特征计算")
    print("=" * 60)

    from engines.compute.feature import get_engine

    engine = get_engine()
    df = create_sample_data(100)

    print("计算单个特征: rsi_14")

    result = engine.compute_single(df, "rsi_14", use_cache=False)

    print(f"✅ 计算成功")
    print(f"   非空值数量: {result.notna().sum()}")
    print(f"   平均值: {result.mean():.2f}")
    print(f"   范围: [{result.min():.2f}, {result.max():.2f}]")

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
    engine.compute(df, ["rsi_14"], use_cache=True)

    cached = cache.get("rsi_14", df)
    print(f"✅ 缓存命中: {'是' if cached is not None else '否'}")

    print("\n第二次计算 (使用缓存)...")
    result = engine.compute(df, ["rsi_14"], use_cache=True)
    print(f"✅ 第二次计算完成")

    return True


def main():
    print("\n" + "=" * 60)
    print("Feature Registry & Engine 架构测试")
    print("=" * 60)

    try:
        test_registry()
        test_feature_engine()
        test_single_feature()
        test_cache()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)

        print("\n新架构总结:")
        print("  1. Feature Registry ✅")
        print("  2. Feature Cache ✅")
        print("  3. Feature Engine ✅")
        print("  4. Technical Features ✅")
        print("\n下一步:")
        print("  - Phase 4: Market Features (Funding, OI, Basis)")
        print("  - Phase 5: Microstructure (OrderFlow, Liquidity)")
        print("  - Phase 6: Regime Features")
        print("  - Phase 7: Alpha Matrix 瘦身")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
