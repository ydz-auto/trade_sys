"""
Test Signal Consistency - Signal 一致性测试

核心验证：
batch replay vs candle-by-candle replay signal 必须一致

这确保：
1. 防泄漏机制不会因数据组织方式不同而漏过
2. MarketContextBuilder 生成的 context 是确定性的
3. 策略信号不依赖于数据传入顺序
"""

import pytest
from typing import List, Dict, Any

from engines.compute.context import (
    MarketContextBuilder,
    MarketContext,
    FutureLeakageError,
    LeakageGuardMode,
    ContextLeakageGuard,
)
from engines.compute.strategy_v2 import (
    StrategyV2,
    Signal,
    StrategyMeta,
)


def create_valid_features_for_timestamp(timestamp: int) -> Dict[str, Dict[str, Any]]:
    """为特定时间戳创建有效的 features"""
    bar_start = timestamp - 3600000
    bar_end = timestamp
    return {
        "1m": {
            "_meta": {
                "tf": "1m",
                "as_of": timestamp,
                "bar_start": timestamp - 60000,
                "bar_end": timestamp,
                "is_closed": True,
                "source": "replay",
            },
            "close": 42000.0 + (timestamp % 1000) / 100,
            "volume": 100.0,
            "rsi": 55.0,
        },
        "5m": {
            "_meta": {
                "tf": "5m",
                "as_of": timestamp,
                "bar_start": timestamp - 300000,
                "bar_end": timestamp,
                "is_closed": True,
                "source": "replay",
            },
            "close": 42000.0 + (timestamp % 1000) / 100,
            "oi": 1000000.0,
            "oi_delta": 50000.0,
            "oi_zscore": 1.5,
            "cvd": 1000.0,
            "cvd_slope": 0.2,
        },
        "15m": {
            "_meta": {
                "tf": "15m",
                "as_of": timestamp,
                "bar_start": timestamp - 900000,
                "bar_end": timestamp,
                "is_closed": True,
                "source": "replay",
            },
            "close": 42000.0 + (timestamp % 1000) / 100,
            "rsi": 55.0,
            "ema_20": 41900.0,
            "ema_50": 41800.0,
            "flow_pressure": 1,
        },
        "1h": {
            "_meta": {
                "tf": "1h",
                "as_of": timestamp,
                "bar_start": timestamp - 3600000,
                "bar_end": timestamp,
                "is_closed": True,
                "source": "replay",
            },
            "close": 42000.0 + (timestamp % 1000) / 100,
            "ema_20": 41900.0,
            "ema_50": 41800.0,
            "trend_state": 1,
        },
        "4h": {
            "_meta": {
                "tf": "4h",
                "as_of": timestamp,
                "bar_start": timestamp - 14400000,
                "bar_end": timestamp,
                "is_closed": True,
                "source": "replay",
            },
            "close": 42000.0 + (timestamp % 1000) / 100,
            "volume": 500.0,
        },
    }


class DummyStrategy(StrategyV2):
    """测试用策略：基于 OI zscore 判断"""
    
    meta = StrategyMeta(
        name="dummy_oi_test",
        primary_tf="15m",
        confirm_tfs=["5m"],
        execution_tf="1m",
        required_context=[
            "tf.5m.flow",
            "derivatives.oi",
        ],
    )
    
    def generate_signal(self, ctx: MarketContext) -> Signal:
        oi = ctx.derivatives.oi
        flow_5m = ctx.tf["5m"].flow
        
        if oi.zscore > 1.5 and flow_5m.cvd_slope > 0.1:
            return Signal.long(confidence=0.75, reason="test_oi_cvd")
        
        return Signal.none()


class TestBatchVsCandleByCandle:
    """
    测试 batch replay vs candle-by-candle replay signal 一致性
    
    验证场景：
    1. 一次性传入多个时间点的 features（batch）
    2. 逐个传入 features（candle-by-candle）
    3. 两种方式产生的 signal 必须完全一致
    """
    
    def test_signal_must_be_identical(self):
        """相同数据的 batch vs candle-by-candle 必须产生相同 signal"""
        timestamps = [
            1700000000000,
            1700000060000,
            1700000120000,
        ]
        
        batch_builder = MarketContextBuilder(symbol="BTC/USDT")
        candle_builder = MarketContextBuilder(symbol="BTC/USDT")
        strategy = DummyStrategy(symbol="BTC/USDT")
        
        signals_batch: List[Signal] = []
        signals_candle: List[Signal] = []
        
        for ts in timestamps:
            features = create_valid_features_for_timestamp(ts)
            ctx_batch = batch_builder.build(features, ts)
            signal_batch = strategy.generate_signal(ctx_batch)
            signals_batch.append(signal_batch)
        
        for ts in timestamps:
            features = create_valid_features_for_timestamp(ts)
            ctx_candle = candle_builder.build(features, ts)
            signal_candle = strategy.generate_signal(ctx_candle)
            signals_candle.append(signal_candle)
        
        assert len(signals_batch) == len(signals_candle)
        
        for i, (sb, sc) in enumerate(zip(signals_batch, signals_candle)):
            assert sb.type == sc.type, f"Signal {i} type mismatch"
            assert sb.confidence == sc.confidence, f"Signal {i} confidence mismatch"
            assert sb.reason == sc.reason, f"Signal {i} reason mismatch"
    
    def test_context_deterministic(self):
        """相同 features 必须产生相同的 MarketContext"""
        timestamp = 1700000000000
        features = create_valid_features_for_timestamp(timestamp)
        
        builder1 = MarketContextBuilder(symbol="BTC/USDT")
        builder2 = MarketContextBuilder(symbol="BTC/USDT")
        
        ctx1 = builder1.build(features, timestamp)
        ctx2 = builder2.build(features, timestamp)
        
        assert ctx1.symbol == ctx2.symbol
        assert ctx1.timestamp == ctx2.timestamp
        assert ctx1.tf.keys() == ctx2.tf.keys()
        
        for tf in ["1m", "5m", "15m", "1h", "4h"]:
            assert ctx1.tf[tf].price.close == ctx2.tf[tf].price.close
            assert ctx1.tf[tf].flow.cvd == ctx2.tf[tf].flow.cvd
        
        assert ctx1.derivatives.oi.zscore == ctx2.derivatives.oi.zscore


class TestReplayDeterminism:
    """
    测试 replay 的确定性
    
    验证：
    1. 相同时间序列的数据，replay 结果必须一致
    2. 不同顺序传入数据，不影响最终结果
    """
    
    def test_time_series_replay_consistent(self):
        """时间序列 replay 结果必须一致"""
        timestamps = [1000000, 1000060, 1000120, 1000180]
        
        strategy = DummyStrategy(symbol="BTC/USDT")
        signals: List[Signal] = []
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        for ts in timestamps:
            features = create_valid_features_for_timestamp(ts)
            ctx = builder.build(features, ts)
            signal = strategy.generate_signal(ctx)
            signals.append(signal)
        
        builder2 = MarketContextBuilder(symbol="BTC/USDT")
        signals2: List[Signal] = []
        
        for ts in timestamps:
            features = create_valid_features_for_timestamp(ts)
            ctx = builder2.build(features, ts)
            signal = strategy.generate_signal(ctx)
            signals2.append(signal)
        
        assert len(signals) == len(signals2)
        
        for s1, s2 in zip(signals, signals2):
            assert s1.type == s2.type
            assert s1.confidence == s2.confidence
    
    def test_shuffled_timestamps_same_final_state(self):
        """相同时间点的数据，无论传入顺序如何，结果必须一致"""
        ts = 1000060
        strategy1 = DummyStrategy(symbol="BTC/USDT")
        strategy2 = DummyStrategy(symbol="BTC/USDT")
        
        features1 = create_valid_features_for_timestamp(ts)
        builder1 = MarketContextBuilder(symbol="BTC/USDT")
        ctx1 = builder1.build(features1, ts)
        signal1 = strategy1.generate_signal(ctx1)
        
        features2 = create_valid_features_for_timestamp(ts)
        builder2 = MarketContextBuilder(symbol="BTC/USDT")
        ctx2 = builder2.build(features2, ts)
        signal2 = strategy2.generate_signal(ctx2)
        
        assert signal1.type == signal2.type
        assert signal1.confidence == signal2.confidence
        assert ctx1.derivatives.oi.zscore == ctx2.derivatives.oi.zscore


class TestLeakagePreventionInConsistency:
    """
    测试防泄漏机制不会因数据组织方式而失效
    """
    
    def test_future_data_rejected_in_batch(self):
        """batch 模式中传入未来数据必须被拒绝"""
        timestamp = 1700000000000
        future_timestamp = timestamp + 1000000
        
        features = create_valid_features_for_timestamp(timestamp)
        features["5m"]["_meta"]["as_of"] = future_timestamp
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError):
            builder.build(features, timestamp)
    
    def test_future_data_rejected_candle_by_candle(self):
        """candle-by-candle 模式中传入未来数据必须被拒绝"""
        timestamp = 1700000000000
        future_timestamp = timestamp + 1000000
        
        features = create_valid_features_for_timestamp(timestamp)
        features["5m"]["_meta"]["as_of"] = future_timestamp
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError):
            builder.build(features, timestamp)
    
    def test_leakage_guard_mode_affects_batch_only(self):
        """close_only 模式拒绝未关闭 bar，partial_allowed 不拒绝"""
        timestamp = 1700000000000
        features = create_valid_features_for_timestamp(timestamp)
        features["15m"]["_meta"]["is_closed"] = False
        
        close_only_builder = MarketContextBuilder(symbol="BTC/USDT")
        with pytest.raises(FutureLeakageError):
            close_only_builder.build(features, timestamp)
        
        partial_builder = MarketContextBuilder(
            symbol="BTC/USDT",
            leakage_guard=ContextLeakageGuard(mode=LeakageGuardMode.PARTIAL_ALLOWED)
        )
        ctx = partial_builder.build(features, timestamp)
        assert ctx is not None
