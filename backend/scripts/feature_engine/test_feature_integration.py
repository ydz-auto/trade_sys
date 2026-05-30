#!/usr/bin/env python3
"""
测试 FeatureRuntime 与各特征模块的集成
"""
import sys
import os
import time
import asyncio
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from engines.context.market_context_builder import MarketContextBuilder


def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def test_trade_features():
    """测试 Trade 特征集成"""
    print_separator("测试 Trade 特征集成")
    
    runtime = MarketContextBuilder()
    
    # 注册回调
    received_features = []
    def on_feature(ts, features):
        print(f"  [回调] 收到特征 (时间: {ts}):")
        for k, v in features.items():
            print(f"    {k}: {v}")
        received_features.append(features)
    
    runtime.set_callbacks(on_feature=on_feature)
    
    # 发送模拟 Trade 事件
    timestamp = int(time.time() * 1000)
    
    trades = []
    for i in range(20):
        trades.append({
            "timestamp": timestamp + i * 100,
            "price": 50000 + i * 10,
            "quantity": 0.1 + i * 0.01,
            "quote_qty": (50000 + i * 10) * (0.1 + i * 0.01),
            "is_buyer_maker": i % 2 == 0,
            "id": f"trade_{i}"
        })
    
    await runtime.emit_event("trade", {
        "symbol": "BTCUSDT",
        "trades": trades
    }, timestamp)
    
    # 等待处理
    await asyncio.sleep(0.1)
    
    # 获取特征
    features = runtime.get_features_at(timestamp)
    
    print(f"\n  从 PIT 存储获取的特征数量: {len(features)}")
    
    # 检查关键 Trade 特征
    expected_trade_features = [
        "trade_delta", "cumulative_delta", "aggressive_buy_volume",
        "aggressive_sell_volume", "total_volume", "total_value"
    ]
    
    missing_features = [f for f in expected_trade_features if f not in features]
    if missing_features:
        print(f"  ❌ 缺失的特征: {missing_features}")
        return False
    else:
        print(f"  ✅ 所有关键 Trade 特征已生成")
        for f in expected_trade_features:
            print(f"    {f}: {features.get(f)}")
    
    return True


async def test_liquidation_features():
    """测试 Liquidation 特征集成"""
    print_separator("测试 Liquidation 特征集成")
    
    runtime = MarketContextBuilder()
    
    timestamp = int(time.time() * 1000)
    
    liquidations = [
        {"timestamp": timestamp, "side": "long", "price": 50000, "quantity": 1.0, "quote_qty": 50000},
        {"timestamp": timestamp + 500, "side": "short", "price": 49900, "quantity": 0.5, "quote_qty": 24950},
        {"timestamp": timestamp + 1000, "side": "long", "price": 49800, "quantity": 2.0, "quote_qty": 99600},
    ]
    
    await runtime.emit_event("liquidation", {
        "symbol": "BTCUSDT",
        "liquidations": liquidations
    }, timestamp + 1000)
    
    await asyncio.sleep(0.1)
    
    features = runtime.get_features_at(timestamp + 1000)
    
    expected_liq_features = [
        "liquidation_long", "liquidation_short", "liquidation_total",
        "liquidation_pressure", "long_liq_ratio"
    ]
    
    missing_features = [f for f in expected_liq_features if f not in features]
    if missing_features:
        print(f"  ❌ 缺失的特征: {missing_features}")
        return False
    else:
        print(f"  ✅ 所有关键 Liquidation 特征已生成")
        for f in expected_liq_features:
            print(f"    {f}: {features.get(f)}")
    
    return True


async def test_oi_funding_features():
    """测试 OI/Funding 特征集成"""
    print_separator("测试 OI/Funding 特征集成")
    
    runtime = MarketContextBuilder()
    
    base_timestamp = int(time.time() * 1000)
    
    # 发送 OI 数据
    oi_values = [1000000 + i * 10000 for i in range(30)]
    for i, oi in enumerate(oi_values):
        ts = base_timestamp + i * 60000
        await runtime.emit_event("open_interest", {
            "symbol": "BTCUSDT",
            "open_interest": oi
        }, ts)
    
    # 发送 Funding 数据
    funding_values = [0.0001 + i * 0.00001 for i in range(30)]
    for i, fr in enumerate(funding_values):
        ts = base_timestamp + i * 60000
        await runtime.emit_event("funding", {
            "symbol": "BTCUSDT",
            "funding_rate": fr
        }, ts)
    
    await asyncio.sleep(0.1)
    
    features = runtime.get_features_at(base_timestamp + 29 * 60000)
    
    expected_oi_features = [
        "oi", "oi_zscore", "funding_rate", "funding_zscore",
        "oi_funding_divergence", "leverage_crowdedness"
    ]
    
    missing_features = [f for f in expected_oi_features if f not in features]
    if missing_features:
        print(f"  ❌ 缺失的特征: {missing_features}")
        return False
    else:
        print(f"  ✅ 所有关键 OI/Funding 特征已生成")
        for f in expected_oi_features:
            print(f"    {f}: {features.get(f)}")
    
    return True


async def test_all_features():
    """运行所有测试"""
    print("\n" + "#" * 80)
    print("# 开始 FeatureRuntime 集成测试")
    print("#" * 80)
    
    results = []
    
    results.append(("Trade 特征", await test_trade_features()))
    results.append(("Liquidation 特征", await test_liquidation_features()))
    results.append(("OI/Funding 特征", await test_oi_funding_features()))
    
    print_separator("测试结果汇总")
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "#" * 80)
    if all_passed:
        print("# 所有测试通过！🎉")
    else:
        print("# 部分测试失败，请检查代码")
    print("#" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_all_features())
    sys.exit(0 if success else 1)
