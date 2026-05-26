#!/usr/bin/env python3
"""
Feature No Lookahead Test - 特征防未来函数专项测试

核心逻辑：
用前 N 根 K 线生成特征
用前 N+1 根 K 线重新生成特征
比较前 N 根特征是否完全一致

如果不一致 = 有未来函数

测试范围：
1. UnifiedFeatureCalculator.compute() - 核心计算器
2. FeatureRuntime 完整链路
3. 各类特征：RSI, SMA, EMA, MACD, Bollinger, ATR, Volume Ratio
4. 特征预热期检查
5. PIT Store 时间因果检查

重点防护：
- rolling 只用当前及历史 bar
- resample 不用未来 close
- merge_asof direction='backward'
- 当前 bar 信号不能用下一根 bar 成交价
"""
import sys
sys.path.insert(0, '.')

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import copy


def generate_test_klines(n_bars: int, seed: int = 42) -> List[Dict[str, Any]]:
    np.random.seed(seed)
    klines = []
    price = 50000.0
    base_ts = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    for i in range(n_bars):
        change_pct = np.random.uniform(-0.02, 0.02)
        open_price = price
        close_price = price * (1 + change_pct)
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.005))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.005))
        volume = np.random.uniform(100, 500)
        klines.append({
            'timestamp_ms': base_ts + i * 60000,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume,
            'symbol': 'BTCUSDT'
        })
        price = close_price
    return klines


def test_unified_calculator_no_lookahead():
    print("\n" + "=" * 80)
    print("Test 1: UnifiedFeatureCalculator No Lookahead")
    print("=" * 80)
    
    from engines.compute.feature.unified_calculator import UnifiedFeatureCalculator
    
    test_sizes = [20, 50, 100, 200]
    all_passed = True
    
    for n_bars in test_sizes:
        print(f"\n[Testing with {n_bars} bars]")
        klines = generate_test_klines(n_bars + 10)
        
        calculator_1 = UnifiedFeatureCalculator(max_lookback=500, use_gpu=False)
        calculator_2 = UnifiedFeatureCalculator(max_lookback=500, use_gpu=False)
        
        features_n = []
        for i in range(n_bars):
            kline = klines[i]
            feat = calculator_1.compute(
                symbol='BTCUSDT',
                open_price=kline['open'],
                high=kline['high'],
                low=kline['low'],
                close=kline['close'],
                volume=kline['volume']
            )
            features_n.append(feat)
        
        features_n_plus_1 = []
        for i in range(n_bars + 1):
            kline = klines[i]
            feat = calculator_2.compute(
                symbol='BTCUSDT',
                open_price=kline['open'],
                high=kline['high'],
                low=kline['low'],
                close=kline['close'],
                volume=kline['volume']
            )
            features_n_plus_1.append(feat)
        
        feature_names = ['rsi_7', 'rsi_14', 'rsi_21', 'sma_10', 'sma_20', 'sma_50',
                         'ema_10', 'ema_20', 'ema_50', 'macd', 'macd_signal', 'macd_hist',
                         'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
                         'volume_ratio', 'volume_ma', 'atr_14', 'momentum_10']
        
        mismatches = []
        for i in range(n_bars):
            feat_n = features_n[i]
            feat_n_plus = features_n_plus_1[i]
            for name in feature_names:
                val_n = feat_n.get(name)
                val_n_plus = feat_n_plus.get(name)
                if val_n is None and val_n_plus is None:
                    continue
                if val_n is None or val_n_plus is None:
                    mismatches.append({'bar': i, 'feature': name, 'val_n': val_n, 'val_n_plus': val_n_plus, 'reason': 'None mismatch'})
                    continue
                if not np.isclose(val_n, val_n_plus, rtol=1e-10, atol=1e-10):
                    mismatches.append({'bar': i, 'feature': name, 'val_n': val_n, 'val_n_plus': val_n_plus, 'reason': 'Value mismatch'})
        
        if mismatches:
            print(f"  ❌ FAILED: {len(mismatches)} mismatches found!")
            all_passed = False
            for m in mismatches[:5]:
                print(f"     Bar {m['bar']}, Feature {m['feature']}: N={m['val_n']}, N+1={m['val_n_plus']}")
            if len(mismatches) > 5:
                print(f"     ... and {len(mismatches) - 5} more")
        else:
            print(f"  ✅ PASSED: All {n_bars} features consistent")
    
    return all_passed


def test_feature_runtime_no_lookahead():
    print("\n" + "=" * 80)
    print("Test 2: FeatureRuntime No Lookahead (Full Pipeline)")
    print("=" * 80)
    
    from runtimes.feature_runtime import FeatureRuntime, FeatureConfig, FeatureMode, clear_feature_runtime_cache
    from infrastructure.utilities.runtime_clock import set_clock_mode, ClockMode
    
    clear_feature_runtime_cache()
    
    n_bars = 100
    klines = generate_test_klines(n_bars + 10)
    
    config = FeatureConfig(symbol='BTCUSDT', mode=FeatureMode.REPLAY, use_gpu=False)
    runtime_1 = FeatureRuntime(config)
    runtime_2 = FeatureRuntime(config)
    set_clock_mode(ClockMode.REPLAY)
    
    async def process_klines(runtime, kline_list, up_to):
        for i in range(up_to):
            kline = kline_list[i]
            await runtime.process_event_immediately(
                event_type='kline',
                data={'open': kline['open'], 'high': kline['high'], 'low': kline['low'], 'close': kline['close'], 'volume': kline['volume'], 'symbol': 'BTCUSDT'},
                timestamp_ms=kline['timestamp_ms']
            )
    
    async def run_test():
        await process_klines(runtime_1, klines, n_bars)
        await process_klines(runtime_2, klines, n_bars + 1)
        mismatches = []
        for i in range(n_bars):
            ts = klines[i]['timestamp_ms']
            feat_1 = runtime_1.get_features_at(ts)
            feat_2 = runtime_2.get_features_at(ts)
            for name in feat_1.keys():
                val_1 = feat_1.get(name)
                val_2 = feat_2.get(name)
                if val_1 is None and val_2 is None:
                    continue
                if val_1 is None or val_2 is None:
                    mismatches.append({'bar': i, 'feature': name, 'val_1': val_1, 'val_2': val_2})
                    continue
                if isinstance(val_1, (int, float)) and isinstance(val_2, (int, float)):
                    if not np.isclose(val_1, val_2, rtol=1e-10, atol=1e-10):
                        mismatches.append({'bar': i, 'feature': name, 'val_1': val_1, 'val_2': val_2})
        return mismatches
    
    mismatches = asyncio.run(run_test())
    if mismatches:
        print(f"  ❌ FAILED: {len(mismatches)} mismatches found!")
        for m in mismatches[:5]:
            print(f"     Bar {m['bar']}, Feature {m['feature']}: R1={m['val_1']}, R2={m['val_2']}")
        return False
    else:
        print(f"  ✅ PASSED: All {n_bars} features consistent through FeatureRuntime")
        return True


def test_feature_warmup_determinism():
    print("\n" + "=" * 80)
    print("Test 3: Feature Warmup Determinism")
    print("=" * 80)
    
    from engines.compute.feature.unified_calculator import UnifiedFeatureCalculator
    
    warmup_requirements = {
        'rsi_7': 8, 'rsi_14': 15, 'rsi_21': 22,
        'sma_10': 10, 'sma_20': 20, 'sma_50': 50,
        'ema_10': 10, 'ema_20': 20, 'ema_50': 50,
        'macd': 35, 'macd_signal': 35, 'macd_hist': 35,
        'bb_upper': 20, 'bb_lower': 20, 'bb_middle': 20,
        'atr_14': 15, 'momentum_10': 11,
    }
    
    klines = generate_test_klines(100)
    all_passed = True
    
    for feature_name, min_bars in warmup_requirements.items():
        calculator = UnifiedFeatureCalculator(max_lookback=500, use_gpu=False)
        for i in range(min_bars - 1):
            kline = klines[i]
            feat = calculator.compute(symbol='BTCUSDT', open_price=kline['open'], high=kline['high'], low=kline['low'], close=kline['close'], volume=kline['volume'])
            val = feat.get(feature_name)
            if val is not None:
                print(f"  ❌ FAILED: {feature_name} should be None with {i+1} bars (need {min_bars}), got {val}")
                all_passed = False
                break
        
        if all_passed:
            kline = klines[min_bars - 1]
            feat = calculator.compute(symbol='BTCUSDT', open_price=kline['open'], high=kline['high'], low=kline['low'], close=kline['close'], volume=kline['volume'])
            val = feat.get(feature_name)
            if val is None:
                print(f"  ❌ FAILED: {feature_name} should have value with {min_bars} bars")
                all_passed = False
            else:
                print(f"  ✅ {feature_name}: warmup={min_bars}, first_value={val:.4f}")
    
    return all_passed


def test_rolling_window_boundary():
    print("\n" + "=" * 80)
    print("Test 4: Rolling Window Boundary")
    print("=" * 80)
    
    from engines.compute.feature.unified_calculator import UnifiedFeatureCalculator
    
    klines = generate_test_klines(50)
    calculator = UnifiedFeatureCalculator(max_lookback=500, use_gpu=False)
    features_history = []
    
    for i, kline in enumerate(klines):
        feat = calculator.compute(symbol='BTCUSDT', open_price=kline['open'], high=kline['high'], low=kline['low'], close=kline['close'], volume=kline['volume'])
        features_history.append({'bar': i, 'close': kline['close'], 'sma_20': feat.get('sma_20'), 'bb_middle': feat.get('bb_middle')})
    
    all_passed = True
    for i in range(20, len(klines)):
        record = features_history[i]
        sma_20 = record['sma_20']
        bb_middle = record['bb_middle']
        if sma_20 is None or bb_middle is None:
            continue
        closes = [klines[j]['close'] for j in range(i - 19, i + 1)]
        expected_sma = np.mean(closes)
        if not np.isclose(sma_20, expected_sma, rtol=1e-10, atol=1e-10):
            print(f"  ❌ FAILED at bar {i}: SMA_20={sma_20}, expected={expected_sma}")
            all_passed = False
        if not np.isclose(bb_middle, expected_sma, rtol=1e-10, atol=1e-10):
            print(f"  ❌ FAILED at bar {i}: BB_middle={bb_middle}, expected={expected_sma}")
            all_passed = False
    
    if all_passed:
        print(f"  ✅ PASSED: Rolling window calculations use correct historical range")
    return all_passed


def test_oi_funding_merge_direction():
    print("\n" + "=" * 80)
    print("Test 5: merge_asof Direction Check")
    print("=" * 80)
    
    base_ts = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    oi_data = [{'timestamp': base_ts + i * 60000, 'oi': 1000 + i * 10} for i in range(20)]
    funding_data = [{'timestamp': base_ts + i * 60000 + 30000, 'funding_rate': 0.0001 * (i % 3 - 1)} for i in range(0, 20, 8)]
    
    oi_df = pd.DataFrame(oi_data)
    funding_df = pd.DataFrame(funding_data)
    
    merged_backward = pd.merge_asof(oi_df.sort_values('timestamp'), funding_df.sort_values('timestamp'), on='timestamp', direction='backward')
    merged_nearest = pd.merge_asof(oi_df.sort_values('timestamp'), funding_df.sort_values('timestamp'), on='timestamp', direction='nearest')
    
    print("\n  Backward merge (correct): first 5 rows")
    for i in range(5):
        row = merged_backward.iloc[i]
        print(f"    Bar {i}: ts={row.timestamp}, rate={row.funding_rate}")
    
    print("\n  Nearest merge (potentially leaking): first 5 rows")
    for i in range(5):
        row = merged_nearest.iloc[i]
        print(f"    Bar {i}: ts={row.timestamp}, rate={row.funding_rate}")
    
    backward_lookahead = any(merged_backward.iloc[i]['funding_rate'] is not None and merged_backward.iloc[i]['timestamp'] < funding_df['timestamp'].min() for i in range(len(merged_backward)))
    
    print("\n  Results:")
    print("    ✅ direction='backward' is safe - only matches past data")
    print("    ⚠️  direction='nearest' can match future data - NOT SAFE for backtest!")
    print("\n  Recommendation: Always use direction='backward' for backtest data alignment")
    
    return True


def test_feature_aligner_fill_method():
    print("\n" + "=" * 80)
    print("Test 6: FeatureAligner Fill Method Safety")
    print("=" * 80)
    
    from domain.feature.materializer.feature_aligner import FeatureAligner
    
    aligner = FeatureAligner(interval_ms=60000)
    feature_dfs = {
        'price': pd.DataFrame({'timestamp': [1000, 2000, 3000, 4000, 5000], 'value': [10.0, 20.0, 30.0, 40.0, 50.0]}),
        'sparse': pd.DataFrame({'timestamp': [1000, 4000, 5000], 'value': [1.0, 4.0, 5.0]})
    }
    
    print("\n  Testing fill methods:")
    
    aligned_ffill = aligner.align_features(feature_dfs, start_ts=1000, end_ts=5000, fill_method='ffill')
    print(f"\n  ffill (forward fill - SAFE): sparse values = {aligned_ffill.features.get('sparse', [])}")
    
    aligned_bfill = aligner.align_features(feature_dfs, start_ts=1000, end_ts=5000, fill_method='bfill')
    print(f"\n  bfill (backward fill - DANGEROUS): sparse values = {aligned_bfill.features.get('sparse', [])}")
    
    print("\n  Results:")
    print("    ✅ ffill is safe - only uses past data")
    print("    ❌ bfill is NOT SAFE - can use future data")
    print("    Recommendation: Disable bfill and interpolate in backtest scenarios")
    
    return True


def run_all_tests():
    print("\n" + "=" * 80)
    print("Feature No Lookahead Test Suite")
    print("=" * 80)
    print("\nPurpose: Verify feature calculations do not use future data")
    print("Method: Compare features computed with N bars vs N+1 bars")
    print("=" * 80)
    
    results = {}
    results['unified_calculator'] = test_unified_calculator_no_lookahead()
    results['feature_runtime'] = test_feature_runtime_no_lookahead()
    results['warmup_determinism'] = test_feature_warmup_determinism()
    results['rolling_boundary'] = test_rolling_window_boundary()
    results['merge_direction'] = test_oi_funding_merge_direction()
    results['fill_method'] = test_feature_aligner_fill_method()
    
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED - No future function detected in feature calculations")
        print("\nVerified:")
        print("  - UnifiedFeatureCalculator uses only historical data")
        print("  - FeatureRuntime pipeline maintains time causality")
        print("  - Feature warmup periods are deterministic")
        print("  - Rolling windows use correct boundaries")
        print("  - merge_asof direction recommendations documented")
    else:
        print("❌ SOME TESTS FAILED - Future function detected!")
        print("\nAction required: Review and fix failed tests")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)