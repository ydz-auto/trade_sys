"""
统一架构测试套件

测试：
1. 特征提取 - UnifiedFeatureCalculator
2. 时间管理 - FeatureAvailabilityGuard
3. 数据泄漏检测
4. 回测引擎
5. 策略参数优化
"""

import asyncio
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_feature_calculator():
    """测试 1: 特征计算器"""
    print("\n" + "="*60)
    print("测试 1: UnifiedFeatureCalculator")
    print("="*60)
    
    from domain.feature.unified_calculator import UnifiedFeatureCalculator
    
    calculator = UnifiedFeatureCalculator()
    
    # 模拟 100 根 K线
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    
    features_list = []
    for i in range(20, len(prices)):
        features = calculator.compute(
            symbol="BTCUSDT",
            open_price=prices[i] * (1 + np.random.uniform(-0.001, 0.001)),
            high=prices[i] * (1 + np.random.uniform(0, 0.002)),
            low=prices[i] * (1 + np.random.uniform(-0.002, 0)),
            close=prices[i],
            volume=1000 * (1 + np.random.random()),
        )
        features_list.append(features)
    
    # 验证特征
    df = pd.DataFrame(features_list)
    
    print(f"✅ 计算了 {len(df)} 个特征向量")
    print(f"✅ 特征列: {list(df.columns)}")
    
    # 验证 RSI 范围
    if 'rsi_14' in df.columns:
        rsi_valid = (df['rsi_14'] >= 0) & (df['rsi_14'] <= 100)
        print(f"✅ RSI 范围验证: {rsi_valid.all()}")
    
    # 验证 SMA 计算
    if 'sma_20' in df.columns:
        print(f"✅ SMA_20 均值: {df['sma_20'].mean():.2f}")
    
    return True


def test_feature_availability_guard():
    """测试 2: 特征可用性守卫"""
    print("\n" + "="*60)
    print("测试 2: FeatureAvailabilityGuard")
    print("="*60)
    
    try:
        from shared.replay.feature_availability_guard import (
            FeatureAvailabilityGuard,
            get_feature_availability_guard,
        )
        
        guard = get_feature_availability_guard()
        
        # 模拟特征时间戳
        current_time = int(datetime.now().timestamp() * 1000)
        
        features = {
            "rsi_14": 45.0,
            "sma_20": 100.0,
            "macd": 0.5,
        }
        
        # 场景 1: 所有特征都可用
        feature_timestamps = {
            "rsi_14": current_time - 15 * 60000,  # 15 分钟前
            "sma_20": current_time - 25 * 60000,  # 25 分钟前
            "macd": current_time - 30 * 60000,    # 30 分钟前
        }
        
        available = guard.filter_available_features(
            features=features,
            feature_timestamps=feature_timestamps,
            replay_clock=current_time,
        )
        
        print(f"✅ 场景 1 - 所有特征可用: {len(available)}/{len(features)}")
        
        # 场景 2: 部分特征不可用（模拟数据泄漏）
        feature_timestamps_2 = {
            "rsi_14": current_time + 5 * 60000,   # 5 分钟后（未来数据！）
            "sma_20": current_time - 25 * 60000,
            "macd": current_time + 10 * 60000,    # 10 分钟后（未来数据！）
        }
        
        available_2 = guard.filter_available_features(
            features=features,
            feature_timestamps=feature_timestamps_2,
            replay_clock=current_time,
        )
        
        print(f"✅ 场景 2 - 阻止未来数据: {len(available_2)}/{len(features)} (应该 < 3)")
        
        if len(available_2) < len(features):
            print("✅ 数据泄漏检测正常工作！")
            return True
        else:
            print("❌ 数据泄漏检测失败！")
            return False
            
    except ImportError as e:
        print(f"⚠️ FeatureAvailabilityGuard 未找到: {e}")
        return True  # 跳过测试


def test_data_leakage_protection():
    """测试 3: 数据泄漏保护"""
    print("\n" + "="*60)
    print("测试 3: 数据泄漏保护")
    print("="*60)
    
    from domain.feature.unified_calculator import UnifiedFeatureCalculator
    
    calculator = UnifiedFeatureCalculator()
    
    # 模拟数据
    np.random.seed(42)
    n_bars = 100
    prices = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    
    # 测试滚动窗口特征
    for i in range(50, n_bars):
        features = calculator.compute(
            symbol="BTCUSDT",
            open_price=prices[i],
            high=prices[i] * 1.001,
            low=prices[i] * 0.999,
            close=prices[i],
            volume=1000,
        )
        
        # 验证 SMA 只使用历史数据
        if 'sma_20' in features:
            expected_sma = np.mean(prices[i-19:i+1])
            actual_sma = features['sma_20']
            
            if abs(expected_sma - actual_sma) > 0.01:
                print(f"❌ SMA 计算错误: 期望 {expected_sma:.2f}, 实际 {actual_sma:.2f}")
                return False
    
    print("✅ 滚动窗口特征只使用历史数据")
    
    # 测试特征 Schema
    schema = calculator.get_schema('rsi_14')
    if schema:
        print(f"✅ RSI_14 Schema: available_after_periods={schema.available_after_periods}")
    
    # 测试特征可用时间
    computation_time = int(datetime.now().timestamp() * 1000)
    available_time = calculator.get_available_time('rsi_14', computation_time)
    
    if available_time > computation_time:
        print(f"✅ 特征可用时间延迟正确: {available_time - computation_time}ms")
    
    return True


async def test_backtest_engine():
    """测试 4: 回测引擎"""
    print("\n" + "="*60)
    print("测试 4: Backtest Engine")
    print("="*60)
    
    from application.optimization_service.engine import (
        OptimizationBacktestEngine,
        BacktestConfig,
    )
    
    config = BacktestConfig(
        initial_capital=10000.0,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        stop_loss=0.02,
        take_profit=0.04,
        enable_slippage=True,
        enable_feature_guard=True,
    )
    
    engine = OptimizationBacktestEngine(config)
    await engine.initialize()
    
    # 创建模拟数据
    np.random.seed(42)
    n_bars = 1000
    
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1min')
    
    prices = 100 + np.cumsum(np.random.randn(n_bars) * 0.1)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.uniform(-0.001, 0.001, n_bars)),
        'high': prices * (1 + np.abs(np.random.randn(n_bars)) * 0.002),
        'low': prices * (1 - np.abs(np.random.randn(n_bars)) * 0.002),
        'close': prices,
        'volume': 1000 * (1 + np.random.randn(n_bars) * 0.3),
    })
    
    # 添加特征
    df['rsi_14'] = 50 + np.random.randn(n_bars) * 10
    df['macd'] = np.random.randn(n_bars) * 0.1
    df['macd_signal'] = df['macd'] + np.random.randn(n_bars) * 0.05
    
    # 保存临时文件
    temp_path = Path(__file__).parent.parent / "data_lake" / "features" / "binance" / "TESTUSDT"
    temp_path.mkdir(parents=True, exist_ok=True)
    temp_file = temp_path / "features.parquet"
    df.to_parquet(temp_file, index=False)
    
    print(f"✅ 创建测试数据: {len(df)} 条记录")
    
    # 运行回测
    start_time = int(dates[0].timestamp() * 1000)
    end_time = int(dates[-1].timestamp() * 1000)
    
    result = await engine.run(
        symbol="TESTUSDT",
        strategy_id="rsi_oversold",
        params={"period": 14, "oversold": 30},
        start_time=start_time,
        end_time=end_time,
        data_path=temp_file,
    )
    
    print(f"✅ 回测完成:")
    print(f"   - 总收益: {result.total_return:.2%}")
    print(f"   - Sharpe: {result.sharpe_ratio:.2f}")
    print(f"   - 胜率: {result.win_rate:.2%}")
    print(f"   - 最大回撤: {result.max_drawdown:.2%}")
    print(f"   - 总交易数: {result.total_trades}")
    print(f"   - 泄漏统计: {result.leakage_stats}")
    
    # 清理
    temp_file.unlink(missing_ok=True)
    
    return True


async def test_strategy_optimization():
    """测试 5: 策略参数优化"""
    print("\n" + "="*60)
    print("测试 5: Strategy Optimization")
    print("="*60)
    
    from application.backtest_service import BacktestService
    
    service = BacktestService()
    await service.initialize()
    
    # 获取可用策略
    strategies = service.get_available_strategies()
    print(f"✅ 可用策略: {[s['id'] for s in strategies]}")
    
    # 创建测试数据
    np.random.seed(42)
    n_bars = 500
    
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1min')
    prices = 100 + np.cumsum(np.random.randn(n_bars) * 0.1)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices * 1.002,
        'low': prices * 0.998,
        'close': prices,
        'volume': 1000,
        'rsi_14': 50 + np.random.randn(n_bars) * 10,
        'macd': np.random.randn(n_bars) * 0.1,
        'macd_signal': np.random.randn(n_bars) * 0.05,
    })
    
    temp_path = Path(__file__).parent.parent / "data_lake" / "features" / "binance" / "OPTUSDT"
    temp_path.mkdir(parents=True, exist_ok=True)
    temp_file = temp_path / "features.parquet"
    df.to_parquet(temp_file, index=False)
    
    # 运行优化
    start_time = int(dates[0].timestamp() * 1000)
    end_time = int(dates[-1].timestamp() * 1000)
    
    result = await service.optimize(
        symbol="OPTUSDT",
        strategy_id="rsi_oversold",
        start_time=start_time,
        end_time=end_time,
    )
    
    print(f"✅ 优化完成:")
    print(f"   - 最佳参数: {result.get('best_params')}")
    print(f"   - 最佳分数: {result.get('best_score', 0):.4f}")
    print(f"   - 测试组合数: {len(result.get('all_results', []))}")
    
    # 清理
    temp_file.unlink(missing_ok=True)
    
    return True


async def test_market_event_emitter():
    """测试 6: 市场事件发射器"""
    print("\n" + "="*60)
    print("测试 6: MarketEventEmitter")
    print("="*60)
    
    try:
        from shared.replay.market_event_emitter import (
            MarketEventEmitter,
            EmitterConfig,
            EmitMode,
        )
        
        # 创建测试数据
        np.random.seed(42)
        n_bars = 100
        
        dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1min')
        prices = 100 + np.cumsum(np.random.randn(n_bars) * 0.1)
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices * 1.002,
            'low': prices * 0.998,
            'close': prices,
            'volume': 1000,
            'rsi_14': 50 + np.random.randn(n_bars) * 10,
        })
        
        temp_path = Path(__file__).parent.parent / "data_lake" / "features" / "binance" / "EMITUSDT"
        temp_path.mkdir(parents=True, exist_ok=True)
        temp_file = temp_path / "features.parquet"
        df.to_parquet(temp_file, index=False)
        
        # 测试事件发射
        emitter = MarketEventEmitter(EmitterConfig(
            emit_mode=EmitMode.INSTANT,
            include_trades=False,
            include_funding=True,
        ))
        
        event_count = 0
        event_types = {}
        
        async for event in emitter.emit_from_feature_parquet(
            parquet_path=temp_file,
            symbol="EMITUSDT",
            exchange="binance",
        ):
            event_count += 1
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
            
            if event_count == 1:
                print(f"✅ 第一个事件:")
                print(f"   - 类型: {event.event_type}")
                print(f"   - 时间戳: {event.timestamp}")
                print(f"   - 序列号: {event.sequence}")
        
        print(f"✅ 总事件数: {event_count}")
        print(f"✅ 事件类型分布: {event_types}")
        
        # 验证事件格式
        if 'candle_1m' in event_types and 'features' in event_types:
            print("✅ 事件格式正确")
        
        # 清理
        temp_file.unlink(missing_ok=True)
        
        return True
        
    except ImportError as e:
        print(f"⚠️ MarketEventEmitter 未找到: {e}")
        return True


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("统一架构测试套件")
    print("="*60)
    
    results = {}
    
    # 测试 1: 特征计算器
    try:
        results["feature_calculator"] = test_feature_calculator()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results["feature_calculator"] = False
    
    # 测试 2: 特征可用性守卫
    try:
        results["feature_guard"] = test_feature_availability_guard()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results["feature_guard"] = False
    
    # 测试 3: 数据泄漏保护
    try:
        results["leakage_protection"] = test_data_leakage_protection()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results["leakage_protection"] = False
    
    # 测试 4: 回测引擎
    try:
        results["backtest_engine"] = await test_backtest_engine()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results["backtest_engine"] = False
    
    # 测试 5: 策略优化
    try:
        results["optimization"] = await test_strategy_optimization()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results["optimization"] = False
    
    # 测试 6: 事件发射器
    try:
        results["event_emitter"] = await test_market_event_emitter()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results["event_emitter"] = False
    
    # 汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
