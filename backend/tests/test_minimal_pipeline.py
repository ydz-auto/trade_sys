#!/usr/bin/env python3
"""
最小闭环测试

验证: 1条Kline → FeatureRuntime 产生特征 → Strategy 产生信号 → ExecutionRuntime 产生 order → trades > 0

不依赖 Kafka / 外部数据源，纯内存运行。
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_minimal_pipeline():
    print("=" * 70)
    print("最小闭环测试: Kline → Feature → Signal → Execution")
    print("=" * 70)

    # ── 1. 构建 FeatureRuntime (replay 模式) ──
    from runtime.feature_runtime import FeatureRuntime, FeatureConfig, FeatureMode
    feature_config = FeatureConfig(symbol="BTCUSDT", mode=FeatureMode.REPLAY)
    feature_rt = FeatureRuntime(feature_config)
    await feature_rt.initialize(symbol="BTCUSDT", mode="replay")
    print("[1/6] FeatureRuntime 初始化完成")

    # ── 2. 构建 SignalRuntime ──
    from runtime.signal_runtime import TimeCausalSignalRuntime, SignalConfig
    signal_config = SignalConfig(symbols=["BTCUSDT"], mode="replay")
    signal_rt = TimeCausalSignalRuntime(signal_config)
    await signal_rt.initialize(symbol="BTCUSDT", mode="replay")
    print("[2/6] SignalRuntime 初始化完成")

    # ── 3. 注册一个简单策略 ──
    class SimpleMAStrategy:
        """简单 MA 交叉策略：sma_10 > ema_20 → buy, sma_10 < ema_20 → sell"""
        def __init__(self):
            self.history = []

        def generate_signal(self, features: dict):
            sma = features.get("sma_10", 0)
            ema = features.get("ema_20", 0)
            if sma == 0 or ema == 0:
                return None

            self.history.append((sma, ema))
            if len(self.history) < 2:
                return None

            prev_sma, prev_ema = self.history[-2]
            if prev_sma <= prev_ema and sma > ema:
                return {"signal_type": "buy", "confidence": 0.7, "reason": f"sma({sma:.0f}) crossed above ema({ema:.0f})"}
            elif prev_sma >= prev_ema and sma < ema:
                return {"signal_type": "sell", "confidence": 0.7, "reason": f"sma({sma:.0f}) crossed below ema({ema:.0f})"}
            return None

    strategy = SimpleMAStrategy()
    signal_rt.register_strategy("simple_ma", strategy)
    print("[3/6] 策略注册完成: simple_ma")

    # ── 4. 构建 ExecutionRuntime (mock 模式) ──
    from runtime.execution_runtime.runtime import ExecutionRuntime, ExecutionConfig
    exec_rt = ExecutionRuntime()
    exec_rt.config.enable_mock = True
    print("[4/6] ExecutionRuntime (mock) 就绪")

    # ── 5. 模拟 Kline 事件流 ──
    base_time = 1700000000000
    kline_data = [
        {"open": 42000, "high": 42500, "low": 41800, "close": 42300, "volume": 100},
        {"open": 42300, "high": 42800, "low": 42100, "close": 42600, "volume": 120},
        {"open": 42600, "high": 43100, "low": 42400, "close": 43000, "volume": 150},
        {"open": 43000, "high": 43200, "low": 42700, "close": 42800, "volume": 110},
        {"open": 42800, "high": 43300, "low": 42600, "close": 43200, "volume": 130},
        {"open": 43200, "high": 43500, "low": 43000, "close": 43400, "volume": 140},
        {"open": 43400, "high": 43800, "low": 43200, "close": 42000, "volume": 200},
        {"open": 42000, "high": 42400, "low": 41800, "close": 41900, "volume": 180},
        {"open": 41900, "high": 42600, "low": 41700, "close": 42500, "volume": 160},
        {"open": 42500, "high": 43000, "low": 42300, "close": 42900, "volume": 145},
    ]

    trades = []
    signals_generated = 0
    features_generated = 0

    print("[5/6] 开始模拟 Kline 事件流...")
    for i, kline in enumerate(kline_data):
        ts = base_time + i * 60000

        # 5a. Feature: 同步处理 kline
        await feature_rt.process_event_immediately("kline", {
            "symbol": "BTCUSDT",
            "open": kline["open"],
            "high": kline["high"],
            "low": kline["low"],
            "close": kline["close"],
            "volume": kline["volume"],
        }, timestamp_ms=ts)

        # 5b. 读取特征 — 查询时间要在 K 线关闭后
        query_time = ts + 60000
        features = await feature_rt.get_features(query_time)
        if features:
            features_generated += 1
        elif i < 3:
            pit_snapshot = feature_rt._pit_store.get_features_at_time(query_time)
            print(f"  [DEBUG i={i}] features={features}, pit_features={pit_snapshot.features}, blocked={pit_snapshot.blocked_features[:3]}")

        # 5c. 生成信号
        signal = await signal_rt.generate_signal(strategy, features, ts)
        if signal:
            signals_generated += 1
            signal["symbol"] = "BTCUSDT"
            signal["quantity"] = 0.001
            signal["timestamp_ms"] = ts

            # 5d. 执行
            trade = await exec_rt.execute_signal(signal)
            if trade:
                trades.append(trade)

        # 推进时钟
        feature_rt._clock.advance_to(ts)

    # ── 6. 验证结果 ──
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)
    print(f"Kline 事件数:     {len(kline_data)}")
    print(f"特征生成次数:     {features_generated}")
    print(f"信号生成次数:     {signals_generated}")
    print(f"成交次数:         {len(trades)}")

    passed = True
    if features_generated == 0:
        print("\n❌ FAIL: 没有产生任何特征")
        passed = False
    else:
        print(f"\n✅ 特征生成正常 ({features_generated} 次)")

    if signals_generated == 0:
        print("❌ FAIL: 没有产生任何信号")
        passed = False
    else:
        print(f"✅ 信号生成正常 ({signals_generated} 次)")

    if len(trades) == 0:
        print("❌ FAIL: 没有产生任何成交")
        passed = False
    else:
        print(f"✅ 成交产生正常 ({len(trades)} 笔)")
        for t in trades[:5]:
            print(f"   {t}")

    print("\n" + "=" * 70)
    if passed:
        print("🎉 最小闭环测试通过！")
    else:
        print("⚠️  最小闭环测试未完全通过，需要排查")
    print("=" * 70)

    return passed


if __name__ == "__main__":
    try:
        result = asyncio.run(test_minimal_pipeline())
        sys.exit(0 if result else 1)
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        traceback.print_exc()
        sys.exit(1)
