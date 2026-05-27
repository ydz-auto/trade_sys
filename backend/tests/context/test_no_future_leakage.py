"""
Test No Future Leakage - 未来信息泄漏防护测试

测试场景：
1. 拒绝未来 as_of
2. 拒绝未关闭的 bar（close_only 模式）
3. 拒绝未来命名字段
"""

import pytest

from engines.compute.context import (
    MarketContextBuilder,
    FutureLeakageError,
    ContextLeakageGuard,
    LeakageGuardMode,
)


def create_valid_features(timestamp: int) -> dict:
    """创建有效的 features（用于测试）"""
    bar_start = timestamp - 3600000  # 1小时前
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
            "close": 42000.0,
            "volume": 100.0,
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
            "close": 42000.0,
            "oi": 1000000.0,
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
            "close": 42000.0,
            "rsi": 55.0,
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
            "close": 42000.0,
            "ema_20": 41900.0,
            "ema_50": 41800.0,
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
            "close": 42000.0,
            "volume": 500.0,
        },
    }


class TestRejectFutureAsOf:
    """测试拒绝未来 as_of"""
    
    def test_reject_future_as_of(self):
        """as_of > ctx_timestamp 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["1h"]["_meta"]["as_of"] = ctx_timestamp + 1000
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "as_of" in str(exc_info.value)
    
    def test_accept_valid_as_of(self):
        """as_of <= ctx_timestamp 应该通过"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        ctx = builder.build(features_by_tf, ctx_timestamp)
        
        assert ctx is not None
        assert ctx.symbol == "BTC/USDT"


class TestRejectUnclosedBar:
    """测试拒绝未关闭的 bar"""
    
    def test_reject_unclosed_bar_in_close_only_mode(self):
        """close_only 模式下，未关闭的 bar 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["15m"]["_meta"]["is_closed"] = False
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "not closed" in str(exc_info.value)
    
    def test_accept_unclosed_bar_in_partial_mode(self):
        """partial_allowed 模式下，未关闭的 bar 应该通过"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["15m"]["_meta"]["is_closed"] = False
        
        guard = ContextLeakageGuard(mode=LeakageGuardMode.PARTIAL_ALLOWED)
        builder = MarketContextBuilder(symbol="BTC/USDT", leakage_guard=guard)
        
        ctx = builder.build(features_by_tf, ctx_timestamp)
        assert ctx is not None


class TestRejectFutureNamedFields:
    """测试拒绝未来命名字段"""
    
    def test_reject_future_return_field(self):
        """包含 future_return 字段的 features 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["15m"]["future_return"] = 0.1
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "forbidden" in str(exc_info.value)
    
    def test_reject_next_bar_field(self):
        """包含 next_bar 字段的 features 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["1h"]["next_close"] = 43000.0
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "forbidden" in str(exc_info.value)
    
    def test_reject_forward_field(self):
        """包含 forward 字段的 features 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["5m"]["forward_returns"] = [0.01, 0.02, 0.03]
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "forbidden" in str(exc_info.value)
    
    def test_reject_target_field(self):
        """包含 target 字段的 features 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["15m"]["target_price"] = 45000.0
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "forbidden" in str(exc_info.value)


class TestMissingMeta:
    """测试缺失 _meta"""
    
    def test_reject_missing_meta(self):
        """缺失 _meta 的 features 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        del features_by_tf["1h"]["_meta"]
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "missing _meta" in str(exc_info.value)


class TestBarEndValidation:
    """测试 bar_end 验证"""
    
    def test_reject_future_bar_end(self):
        """bar_end > ctx_timestamp 应该抛出 FutureLeakageError"""
        ctx_timestamp = 1700000000000
        features_by_tf = create_valid_features(ctx_timestamp)
        features_by_tf["1h"]["_meta"]["bar_end"] = ctx_timestamp + 1000
        
        builder = MarketContextBuilder(symbol="BTC/USDT")
        
        with pytest.raises(FutureLeakageError) as exc_info:
            builder.build(features_by_tf, ctx_timestamp)
        
        assert "bar_end" in str(exc_info.value)
