"""
Research Tools Test Script - 研究工具测试脚本

测试四个核心研究工具：
1. Signal Validation - 信号验证
2. Event Study - 事件研究
3. Walk Forward - 滚动验证
4. Regime Test - 状态测试

测试策略：short_squeeze, oi_behavior, funding_extreme_reversal, liquidation_cascade, trade_pressure_bounce
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from engines.compute.strategy_v2 import StrategyRegistry
from engines.compute.strategy_v2.strategies import (
    ShortSqueezeStrategy,
    OpenInterestBehaviorStrategy,
    FundingExtremeReversalStrategy,
    LiquidationCascadeStrategy,
    TradePressureBounceStrategy,
)
from engines.compute.context import (
    MarketContext,
    TimeframeContext,
    PriceState,
    TrendStateData,
    VolatilityStateData,
    VolumeStateData,
    FlowState,
    LiquidityStateData,
    DerivativesContext,
    OIData,
    FundingData,
    LiquidationData,
    RiskContext,
    TrendState,
    FlowPressure,
    FundingBias,
    LiquidityState,
    VolatilityState,
    VolumeState,
)

from research.signal_validation import validate_strategy, compare_strategies
from research.event_study import run_event_study, compare_strategy_events
from research.simple_backtest import run_simple_backtest, compare_strategy_backtests
from research.walk_forward_simple import run_walk_forward, compare_strategy_walk_forward
from research.regime_test import run_regime_test, compare_strategy_regimes


def generate_test_market_contexts(num_samples: int = 1000) -> tuple:
    """
    生成测试用的 MarketContext 序列
    
    Returns:
        (market_contexts, timestamps, prices)
    """
    market_contexts = []
    timestamps = []
    prices = []
    
    base_timestamp = int(datetime(2024, 1, 1).timestamp() * 1000)
    base_price = 45000.0
    
    for i in range(num_samples):
        # 时间戳（每15分钟一个bar）
        timestamp = base_timestamp + i * 15 * 60 * 1000
        timestamps.append(timestamp)
        
        # 价格（模拟随机游走 + 趋势）
        price_change = np.random.normal(0, 0.003) * base_price
        price = base_price + price_change + np.sin(i / 30) * 800
        prices.append(price)
        base_price = price
        
        # 创建时间周期上下文
        tf_contexts = {}
        
        # 增加极端情况的概率以触发信号
        extreme_prob = 0.3  # 30% 概率出现极端情况
        
        # 1m
        if np.random.random() < extreme_prob:
            m1_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL])
        else:
            m1_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL])
        
        tf_contexts["1m"] = TimeframeContext(
            timeframe="1m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.0015)),
                low=price * (1 - np.random.uniform(0, 0.0015)),
                close=price,
                change_percent=np.random.uniform(-0.3, 0.3),
            ),
            liquidity=LiquidityStateData(
                state=np.random.choice([LiquidityState.NORMAL, LiquidityState.THIN], p=[0.8, 0.2]),
                spread=0.5,
            ),
            flow=FlowState(
                pressure=m1_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-100, 100),
                cvd_slope=np.random.uniform(-0.1, 0.1),
                aggressive_ratio=np.random.uniform(0.3, 0.7),
            ),
        )
        
        # 5m
        if np.random.random() < extreme_prob:
            m5_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL])
        else:
            m5_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL])
        
        tf_contexts["5m"] = TimeframeContext(
            timeframe="5m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.004)),
                low=price * (1 - np.random.uniform(0, 0.004)),
                close=price,
                change_percent=np.random.uniform(-0.6, 0.6),
            ),
            flow=FlowState(
                pressure=m5_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-500, 500),
                cvd_slope=np.random.uniform(-0.05, 0.05),
                aggressive_ratio=np.random.uniform(0.3, 0.7),
            ),
        )
        
        # 15m（主周期）
        m15_trend = np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], p=[0.35, 0.35, 0.3])
        if np.random.random() < extreme_prob:
            m15_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL])
            m15_flow_score = np.random.uniform(0.6, 1.0) * np.random.choice([-1, 1])
        else:
            m15_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL])
            m15_flow_score = np.random.uniform(-1, 1)
        
        tf_contexts["15m"] = TimeframeContext(
            timeframe="15m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.008)),
                low=price * (1 - np.random.uniform(0, 0.008)),
                close=price,
                change_percent=np.random.uniform(-1.2, 1.2),
            ),
            trend=TrendStateData(
                state=m15_trend,
                slope=np.random.uniform(-0.015, 0.015),
                strength=np.random.uniform(0.3, 0.9),
            ),
            volatility=VolatilityStateData(
                state=np.random.choice([VolatilityState.NORMAL, VolatilityState.ELEVATED, VolatilityState.LOW], p=[0.5, 0.35, 0.15]),
                atr_pct=np.random.uniform(0.008, 0.025),
            ),
            volume=VolumeStateData(
                state=np.random.choice([VolumeState.NORMAL, VolumeState.CLIMAX, VolumeState.DRY], p=[0.6, 0.25, 0.15]),
                volume_zscore=np.random.uniform(-2.5, 2.5),
            ),
            flow=FlowState(
                pressure=m15_flow_pressure,
                score=m15_flow_score,
                cvd=np.random.uniform(-1500, 1500),
                cvd_slope=np.random.uniform(-0.15, 0.15),
                aggressive_ratio=np.random.uniform(0.25, 0.75),
            ),
        )
        
        # 1h
        h1_trend = np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], p=[0.35, 0.35, 0.3])
        tf_contexts["1h"] = TimeframeContext(
            timeframe="1h",
            trend=TrendStateData(
                state=h1_trend,
                slope=np.random.uniform(-0.008, 0.008),
                strength=np.random.uniform(0.3, 0.9),
            ),
            price=PriceState(
                close=price,
                change_percent=np.random.uniform(-2.0, 2.0),
            ),
        )
        
        # 4h
        h4_trend = np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], p=[0.35, 0.35, 0.3])
        tf_contexts["4h"] = TimeframeContext(
            timeframe="4h",
            trend=TrendStateData(
                state=h4_trend,
                slope=np.random.uniform(-0.005, 0.005),
                strength=np.random.uniform(0.3, 0.9),
            ),
        )
        
        # 衍生品数据（增加极端情况概率以触发信号）
        if np.random.random() < extreme_prob:
            oi_zscore = np.random.uniform(1.5, 3.0) * np.random.choice([-1, 1])
        else:
            oi_zscore = np.random.uniform(-2.5, 2.5)
        
        if np.random.random() < extreme_prob:
            funding_zscore = np.random.uniform(1.8, 3.0) * np.random.choice([-1, 1])
        else:
            funding_zscore = np.random.uniform(-2.5, 2.5)
        
        if funding_zscore > 2.0:
            funding_bias = FundingBias.EXTREME_POSITIVE
        elif funding_zscore > 0.8:
            funding_bias = FundingBias.POSITIVE
        elif funding_zscore < -2.0:
            funding_bias = FundingBias.EXTREME_NEGATIVE
        elif funding_zscore < -0.8:
            funding_bias = FundingBias.NEGATIVE
        else:
            funding_bias = FundingBias.NEUTRAL
        
        # 强平数据（增加极端情况）
        if np.random.random() < extreme_prob * 0.5:
            liq_long_zscore = np.random.uniform(2.0, 3.5)
            liq_short_zscore = np.random.uniform(-1, 1)
        elif np.random.random() < extreme_prob * 0.5:
            liq_short_zscore = np.random.uniform(2.0, 3.5)
            liq_long_zscore = np.random.uniform(-1, 1)
        else:
            liq_long_zscore = np.random.uniform(-3, 3)
            liq_short_zscore = np.random.uniform(-3, 3)
        
        derivatives = DerivativesContext(
            oi=OIData(
                value=np.random.uniform(2000000, 6000000),
                delta=np.random.uniform(-150000, 150000),
                zscore=oi_zscore,
            ),
            funding=FundingData(
                rate=np.random.uniform(-0.015, 0.015),
                zscore=funding_zscore,
                bias=funding_bias,
            ),
            liquidation=LiquidationData(
                long=np.random.uniform(0, 200000),
                short=np.random.uniform(0, 200000),
                total=np.random.uniform(0, 400000),
                long_zscore=liq_long_zscore,
                short_zscore=liq_short_zscore,
                reversal_signal=np.random.random() < 0.1,  # 增加反转信号概率
            ),
        )
        
        risk = RiskContext(
            multiplier=np.random.uniform(0.85, 1.15),
        )
        
        ctx = MarketContext(
            symbol="BTCUSDT",
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=risk,
        )
        
        market_contexts.append(ctx)
    
    return market_contexts, timestamps, np.array(prices)


def run_signal_validation_test(strategies, market_contexts, timestamps):
    """运行信号验证测试"""
    print("\n" + "="*60)
    print("1. 信号验证测试 (Signal Validation)")
    print("="*60)
    
    results = compare_strategies(strategies, market_contexts, timestamps)
    print(results.to_string())
    
    # 详细输出第一个策略的验证结果
    print("\n--- 详细信号验证结果 (Short Squeeze) ---")
    result = validate_strategy(strategies[0], market_contexts, timestamps)
    print(result)


def run_event_study_test(strategies, market_contexts, timestamps, prices):
    """运行事件研究测试"""
    print("\n" + "="*60)
    print("2. 事件研究测试 (Event Study)")
    print("="*60)
    print("验证: 信号触发后，市场是否真的往预期方向走")
    print()
    
    for strategy in strategies:
        try:
            result = run_event_study(strategy, market_contexts, timestamps, prices)
            
            if result.total_events == 0:
                print(f"[{strategy.meta.name}] 无有效事件，跳过")
                continue
            
            print(f"[{strategy.meta.name}] 事件数:{result.total_events}, 胜率:{result.overall_hit_rate:.2%}")
            print(f"  +1bar收益: {result.overall_avg_return:.4f}, MFE/MAE: {result.mfe_mae_ratio:.2f}")
            print(f"  p-value: {result.p_value:.4f}")
            
            if result.p_value < 0.05:
                print(f"  ✓ 统计显著 (p < 0.05)")
            else:
                print(f"  ✗ 不显著 (p >= 0.05)")
            print()
            
        except ValueError as e:
            print(f"[{strategy.meta.name}] {e}")
    
    print("--- 详细事件研究结果 (Short Squeeze) ---")
    try:
        result = run_event_study(strategies[0], market_contexts, timestamps, prices)
        if result.total_events > 0:
            print(result)
    except ValueError:
        print("无有效事件")


def run_simple_backtest_test(strategies, market_contexts, timestamps, prices):
    """运行简单回测"""
    print("\n" + "="*60)
    print("3. 简单回测 (Simple Backtest)")
    print("="*60)
    print("验证: 在简单规则下，策略能否盈利")
    print()
    
    for strategy in strategies:
        try:
            trades, metrics = run_simple_backtest(strategy, market_contexts, timestamps, prices)
            
            if metrics.total_trades == 0:
                print(f"[{strategy.meta.name}] 无交易，跳过")
                continue
            
            print(f"[{strategy.meta.name}] 交易数:{metrics.total_trades}, 胜率:{metrics.win_rate:.2%}")
            print(f"  平均收益:{metrics.avg_trade_return*100:.2f}%, Sharpe:{metrics.sharpe_ratio:.2f}")
            print(f"  总盈亏:{metrics.total_pnl_pct:.4f}, 最大回撤:{metrics.max_drawdown:.4f}")
            print(f"  盈利因子:{metrics.profit_factor:.2f}")
            
            if metrics.total_pnl_pct > 0 and metrics.sharpe_ratio > 0.5:
                print(f"  ✓ 盈利且 Sharpe > 0.5")
            elif metrics.total_pnl_pct > 0:
                print(f"  ✓ 盈利")
            else:
                print(f"  ✗ 亏损")
            print()
            
        except Exception as e:
            print(f"[{strategy.meta.name}] {e}")
    
    print("--- 详细回测结果 (Short Squeeze) ---")
    try:
        trades, metrics = run_simple_backtest(strategies[0], market_contexts, timestamps, prices)
        if metrics.total_trades > 0:
            print(f"  trades={metrics.total_trades}, win_rate={metrics.win_rate:.2%}, "
                  f"sharpe={metrics.sharpe_ratio:.2f}, pf={metrics.profit_factor:.2f}")
    except Exception:
        print("无交易")


def run_walk_forward_test(strategies, market_contexts, timestamps, prices):
    """运行滚动验证测试"""
    print("\n" + "="*60)
    print("4. 滚动验证测试 (Walk Forward)")
    print("="*60)
    print("验证: 随着时间推移，策略是否持续有效（不是过拟合）")
    print()
    
    for strategy in strategies:
        try:
            result = run_walk_forward(
                strategy, market_contexts, timestamps, prices,
                train_period_days=7,
                test_period_days=2
            )
            
            if result.total_windows == 0:
                print(f"[{strategy.meta.name}] 无有效窗口，跳过")
                continue
            
            print(f"[{strategy.meta.name}] 窗口数:{result.total_windows}")
            print(f"  平均胜率:{result.avg_hit_rate:.2%}, 胜率一致性:{result.win_rate_consistency:.2%}")
            print(f"  平均收益:{result.avg_return:.4f}, 收益稳定性:{result.return_std:.4f}")
            print(f"  最佳窗口:{result.best_window_return:.4f}, 最差窗口:{result.worst_window_return:.4f}")
            
            consistency_ratio = result.win_rate_consistency
            if consistency_ratio > 0.7:
                print(f"  ✓ 胜率一致性高 ({consistency_ratio:.2%})")
            elif consistency_ratio > 0.5:
                print(f"  △ 胜率一致性中等 ({consistency_ratio:.2%})")
            else:
                print(f"  ✗ 胜率一致性低 ({consistency_ratio:.2%})")
            print()
            
        except Exception as e:
            print(f"[{strategy.meta.name}] {e}")


def run_regime_test(strategies, market_contexts, timestamps, prices):
    """运行状态测试"""
    print("\n" + "="*60)
    print("5. 状态测试 (Regime Test)")
    print("="*60)
    print("验证: 策略在不同市场状态下是否表现一致")
    print()
    
    for strategy in strategies:
        try:
            result = run_regime_test(strategy, market_contexts, timestamps, prices)
            
            if result.total_samples == 0:
                print(f"[{strategy.meta.name}] 无有效样本，跳过")
                continue
            
            print(f"[{strategy.meta.name}] 样本数:{result.total_samples}, 信号数:{result.total_signals}")
            print(f"  状态分布: {dict(result.regime_distribution)}")
            print(f"  状态依赖度: {result.regime_dependence_score:.2%}")
            
            if result.regime_results:
                print(f"  各状态表现:")
                for regime, regime_result in result.regime_results.items():
                    if regime_result.signals > 0:
                        print(f"    {regime}: 胜率={regime_result.hit_rate:.2%}, 收益={regime_result.avg_return:.4f}")
            
            if result.regime_dependence_score < 0.5:
                print(f"  ✓ 状态依赖性低，策略稳健")
            else:
                print(f"  △ 状态依赖性高，需要在不同状态下单独评估")
            print()
            
        except Exception as e:
            print(f"[{strategy.meta.name}] {e}")


def main():
    """主测试函数"""
    print("="*60)
    print("研究工具测试脚本 - 按顺序验证")
    print("1. Signal Validation  - 证明信号有信息含量")
    print("2. Event Study        - 证明信号触发后市场走向预期方向")
    print("3. Simple Backtest     - 证明交易规则能赚钱")
    print("4. Walk Forward       - 证明不是过拟合")
    print("5. Regime Test        - 分析状态依赖性")
    print("="*60)
    
    # 初始化策略注册表
    StrategyRegistry.load_strategies()
    
    # 创建策略实例
    strategies = [
        ShortSqueezeStrategy("BTCUSDT"),
        OpenInterestBehaviorStrategy("BTCUSDT"),
        FundingExtremeReversalStrategy("BTCUSDT"),
        LiquidationCascadeStrategy("BTCUSDT"),
        TradePressureBounceStrategy("BTCUSDT"),
    ]
    
    print(f"\n测试策略: {[s.meta.name for s in strategies]}")
    
    # 生成测试数据
    print("\n生成测试数据...")
    market_contexts, timestamps, prices = generate_test_market_contexts(num_samples=2000)
    print(f"样本数量: {len(market_contexts)}")
    
    # ==================== 按顺序执行测试 ====================
    
    # 1. Signal Validation - 验证信号分布
    run_signal_validation_test(strategies, market_contexts, timestamps)
    
    # 2. Event Study - 验证信号触发后的市场走势
    run_event_study_test(strategies, market_contexts, timestamps, prices)
    
    # 3. Simple Backtest - 验证交易规则能赚钱
    run_simple_backtest_test(strategies, market_contexts, timestamps, prices)
    
    # 4. Walk Forward - 验证不是过拟合
    run_walk_forward_test(strategies, market_contexts, timestamps, prices)
    
    # 5. Regime Test - 分析状态依赖性
    run_regime_test(strategies, market_contexts, timestamps, prices)
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
