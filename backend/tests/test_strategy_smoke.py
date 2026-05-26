"""
策略冒烟测试 - 验证所有策略在最小输入数据下能正常工作

重点检查策略：
1. short_squeeze
2. oi_flush
3. funding_exhaustion_trap
4. cvd_divergence
5. whale_trade
6. aggressive_flow
7. liquidation_cascade
"""
from engines.compute.strategy.registry import get_strategy


def create_minimal_features(strategy_id):
    """
    为策略创建最小化的特征数据

    根据该策略在test_strategy_features.py中显示的使用特征来构建
    """
    base_features = {
        # 基础价格相关
        "close": 50000.0,
        "close_prev": 50200.0,
        "high": 50500.0,
        "low": 49500.0,
        "close_prices": [49800, 49900, 50000, 50100, 50200, 50000],
        "price_change": -0.001,
        "return_1h": -0.005,
        "return_4h": -0.01,
        "timestamp": 1718000000000,
        "symbol": "BTCUSDT",

        # 技术指标
        "rsi_14": 45.0,
        "macd": 50.0,
        "macd_signal": 48.0,
        "sma_10": 49500.0,
        "sma_50": 48000.0,
        "ema_10": 49600.0,
        "ema_50": 48200.0,
        "bb_upper": 51000.0,
        "bb_lower": 49000.0,
        "bb_middle": 50000.0,

        # 成交量/深度
        "volume_ratio": 1.2,
        "spread": 5.0,
        "top5_depth": 0.6,
        "cancel_rate": 0.1,

        # 持仓与资金费率
        "oi_delta": 0.01,
        "oi_zscore": 1.5,
        "oi_history": [0.98, 0.99, 1.0, 1.01, 1.02, 1.01],
        "oi_funding_divergence": -0.5,
        "funding_rate": 0.0001,
        "funding_delta": 0.00001,
        "funding_zscore": 0.8,
        "funding_divergence": 0.3,
        "funding_extreme_reversal": False,

        # 爆仓相关
        "liquidation_long": 50000.0,
        "liquidation_short": 30000.0,
        "liquidation_spike": False,
        "liquidation_reversal_signal": "long",
        "long_liquidations_spike": False,
        "liquidation_pressure": 0.2,

        # 订单流/CDV
        "cvd": 150000.0,
        "cvd_history": [100000, 120000, 150000, 130000, 140000, 150000],
        "cumulative_delta": 200000.0,
        "aggressive_buy_volume": 5000000.0,
        "aggressive_sell_volume": 3500000.0,
        "aggressive_flow": 1.4,

        # 大单/鲸鱼
        "whale_buy_count": 3,
        "whale_sell_count": 1,
        "whale_buy_volume": 200.0,
        "whale_sell_volume": 80.0,

        # 异常检测
        "short_pressure": 1.2,
        "imbalance_5": 0.6,
        "microprice": 50002.0,
        "mid_price": 50002.5,
        "trade_delta": 150000.0,
        "upper_shadow_ratio": 0.05,
        "range_high": 50600.0,
        "range_low": 49400.0,
        "price_position": 0.5,
        "basis": 5.0,
        "premium": 0.001,

        # 其他
        "volumes": [1000, 1200, 1500, 1100, 1300, 1400],
        "binance_return": 0.001,
        "okx_return": 0.0008,
        "momentum": 0.02,
        "sweep_buy_score": 0.6,
        "sweep_sell_score": 0.4,
        "atr_ratio": 1.3,
    }

    return base_features


# 高优先级策略列表
HIGH_PRIORITY_STRATEGIES = [
    "oi_flush",
    "short_squeeze",
    "funding_exhaustion_trap",
    "cvd_divergence",
    "whale_trade",
    "aggressive_flow",
    "liquidation_cascade"
]


def test_high_priority_strategy_smoke(strategy_id):
    """
    测试高优先级策略能正常工作
    """
    print(f"测试: {strategy_id}")
    try:
        # 1. 能初始化策略
        strategy = get_strategy(strategy_id)
        assert strategy is not None
        print(f"  ✓ 初始化成功")

        # 2. 有 generate_signal 方法
        assert hasattr(strategy, 'generate_signal')
        method = getattr(strategy, 'generate_signal')
        assert callable(method)
        print(f"  ✓ 找到 generate_signal 方法")

        # 3. 用最小特征数据调用不抛异常
        features = create_minimal_features(strategy_id)

        result = method(features)
        # 策略可以返回 None 或信号字典
        if result is not None:
            assert isinstance(result, dict)
            assert 'signal_type' in result
            print(f"  ✓ generate_signal 返回信号: {result['signal_type']}")
        else:
            # None 是允许的，表示没有信号
            print(f"  ✓ generate_signal 返回 None (无信号)")

        return True
    except Exception as e:
        print(f"  ✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_all_strategies_have_generate_signal():
    """
    测试所有策略都有 generate_signal 方法
    """
    from engines.compute.strategy.registry import _STRATEGY_REGISTRY

    strategies_without_generate = []
    for strategy_id, strategy_class in _STRATEGY_REGISTRY.items():
        if not hasattr(strategy_class, 'generate_signal'):
            strategies_without_generate.append(strategy_id)

    if strategies_without_generate:
        print(f"✗ 以下策略缺少 generate_signal: {strategies_without_generate}")
        return False
    else:
        print(f"✓ 全部 {len(_STRATEGY_REGISTRY)} 策略都有 generate_signal 方法")
        return True


if __name__ == "__main__":
    print("=== 策略冒烟测试 ===\n")

    print("运行高优先级策略测试...\n")
    all_pass = True

    for strategy_id in HIGH_PRIORITY_STRATEGIES:
        if not test_high_priority_strategy_smoke(strategy_id):
            all_pass = False
        print()

    print("\n检查所有策略是否有 generate_signal 方法...")
    if not test_all_strategies_have_generate_signal():
        all_pass = False

    if all_pass:
        print(f"\n✅ 全部 {len(HIGH_PRIORITY_STRATEGIES)} 个高优先级策略通过冒烟测试！")
    else:
        print(f"\n❌ 有测试失败，请检查！")
        exit(1)
