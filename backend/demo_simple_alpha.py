#!/usr/bin/env python3
"""
简化版Alpha回测演示 - 直接运行Walk-Forward回测
整合P1和P2的核心模块
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from services.backtest_service import BacktestEngine, BacktestConfig, SignalType
from research.pipeline.feature_pipeline import TechnicalFeatureEngine
from research.factor.registry import FactorRegistry, FactorMetadata, FactorType, FactorStatus
from research.experiment.tracker import ExperimentTracker, Experiment, HyperparameterTrial


def generate_historical_data(symbol: str = "BTC/USDT", hours: int = 1000):
    """生成历史数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=hours)
    timestamps = pd.date_range(start=start_date, end=end_date, freq="1h")
    
    np.random.seed(42)
    n = len(timestamps)
    
    # 更真实的价格生成
    price = 50000.0
    prices = [price]
    
    for i in range(1, n):
        # 带一定自相关性和波动率集群
        volatility = 0.02 + 0.01 * np.sin(i / 100)
        drift = 0.0005
        shock = np.random.normal(0, volatility)
        price = price * (1 + drift + shock)
        prices.append(price)
    
    price_array = np.array(prices)
    high = price_array * (1 + np.random.uniform(0, 0.015, n))
    low = price_array * (1 - np.random.uniform(0, 0.015, n))
    open_ = low + np.random.uniform(0, 1, n) * (high - low)
    close = price_array
    volume = np.random.lognormal(10, 0.8, n)
    
    data = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": symbol,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    })
    return data


def compute_rsi(data, period=14):
    """计算RSI"""
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(data, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = data['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def compute_bollinger_bands(data, period=20, std_dev=2):
    """计算布林带"""
    sma = data['close'].rolling(window=period).mean()
    std = data['close'].rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower


def rsi_macd_strategy(bar, position):
    """基于RSI和MACD的组合策略（量化因子策略）"""
    if 'rsi' not in bar or 'macd_hist' not in bar:
        return SignalType.HOLD
    
    rsi = bar['rsi']
    macd_hist = bar['macd_hist']
    
    if pd.isna(rsi) or pd.isna(macd_hist):
        return SignalType.HOLD
    
    # 因子组合信号
    if rsi < 35 and macd_hist > 0:
        return SignalType.BUY
    elif rsi > 65 and macd_hist < 0:
        return SignalType.SELL
    
    return SignalType.HOLD


def momentum_strategy(bar, position):
    """动量因子策略"""
    if 'ma_short' not in bar or 'ma_long' not in bar:
        return SignalType.HOLD
    
    ma_short = bar['ma_short']
    ma_long = bar['ma_long']
    
    if pd.isna(ma_short) or pd.isna(ma_long):
        return SignalType.HOLD
    
    if ma_short > ma_long * 1.005:
        return SignalType.BUY
    elif ma_short < ma_long * 0.995:
        return SignalType.SELL
    
    return SignalType.HOLD


def mean_reversion_strategy(bar, position):
    """均值回归因子策略（布林带）"""
    if 'bb_upper' not in bar or 'bb_lower' not in bar:
        return SignalType.HOLD
    
    close = bar['close']
    bb_upper = bar['bb_upper']
    bb_lower = bar['bb_lower']
    
    if pd.isna(close) or pd.isna(bb_upper) or pd.isna(bb_lower):
        return SignalType.HOLD
    
    if close < bb_lower * 0.995:
        return SignalType.BUY
    elif close > bb_upper * 1.005:
        return SignalType.SELL
    
    return SignalType.HOLD


def add_features_to_bars(bars_df):
    """给K线数据添加技术因子"""
    df = bars_df.copy()
    
    # RSI
    df['rsi'] = compute_rsi(df)
    
    # MACD
    df['macd_line'], df['macd_signal'], df['macd_hist'] = compute_macd(df)
    
    # 布林带
    df['bb_middle'], df['bb_upper'], df['bb_lower'] = compute_bollinger_bands(df)
    
    # 移动平均线
    df['ma_short'] = df['close'].rolling(window=7).mean()
    df['ma_long'] = df['close'].rolling(window=21).mean()
    
    # 动量因子
    df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
    df['momentum_20'] = df['close'] / df['close'].shift(20) - 1
    
    # 波动率因子
    df['volatility_20'] = df['close'].pct_change().rolling(window=20).std()
    
    return df


def main():
    print("\n" + "="*80)
    print("  🚀 Alpha回测演示 - 因子策略")
    print("="*80)
    
    # 1. 生成数据
    print("\n1. 生成历史数据...")
    data = generate_historical_data(hours=1200)
    print(f"   数据长度: {len(data)}")
    print(f"   时间范围: {data['timestamp'].iloc[0]} 至 {data['timestamp'].iloc[-1]}")
    
    # 2. 计算因子
    print("\n2. 计算技术因子...")
    data_with_features = add_features_to_bars(data)
    feature_count = len([col for col in data_with_features.columns if col not in 
                        ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']])
    print(f"   生成 {feature_count} 个因子")
    print(f"   因子列表: {[col for col in data_with_features.columns if col not in ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']]}")
    
    # 转换格式给backtest engine
    bars = []
    for idx, row in data_with_features.iterrows():
        bar = {
            'timestamp': row['timestamp'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume']
        }
        # 添加因子
        for col in data_with_features.columns:
            if col not in ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']:
                bar[col] = row[col]
        bars.append(bar)
    
    # 3. 配置回测
    print("\n3. 配置回测引擎...")
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.001,
        slippage=0.001,
        position_size_pct=0.3
    )
    engine = BacktestEngine(config)
    
    # 4. 策略对比回测
    print("\n4. 运行多策略对比回测...")
    strategies = [
        ("RSI+MACD因子策略", rsi_macd_strategy),
        ("动量因子策略", momentum_strategy),
        ("均值回归因子策略", mean_reversion_strategy),
    ]
    
    results = []
    
    for name, strategy in strategies:
        print(f"\n   运行策略: {name}")
        result = engine.run(bars, strategy)
        results.append((name, result))
        engine.print_result(result)
    
    # 5. 对比总结
    print("\n" + "="*80)
    print("  📊 策略对比总结")
    print("="*80)
    print(f"{'策略名称':<30} {'总收益':>12} {'夏普':>8} {'最大回撤':>12} {'交易次数':>10}")
    print("-" * 80)
    
    for name, result in results:
        print(f"{name:<30} {result['total_return']:>12.2%} {result['sharpe_ratio']:>8.2f} {result['max_drawdown']:>12.2%} {result['total_trades']:>10}")
    
    # 6. 实验追踪演示
    print("\n" + "="*80)
    print("  🔬 实验追踪系统")
    print("="*80)
    
    tracker = ExperimentTracker()
    experiment = Experiment(
        name="factor_strategy_comparison_v1",
        description="对比三个因子策略的表现",
        tags=["factor", "rsi", "macd", "momentum", "bollinger"]
    )
    tracker.create_experiment(experiment)
    
    for name, result in results:
        trial = HyperparameterTrial(
            experiment_id=experiment.id,
            parameters={'strategy': name},
            metrics={
                'total_return': result['total_return'],
                'sharpe_ratio': result['sharpe_ratio'],
                'max_drawdown': result['max_drawdown'],
                'win_rate': result['win_rate']
            }
        )
        tracker.log_trial(trial)
    
    best = tracker.get_best_trial(experiment.id, 'sharpe_ratio')
    print(f"\n最佳策略: {best.parameters['strategy']}")
    print(f"  夏普比率: {best.metrics['sharpe_ratio']:.2f}")
    print(f"  总收益: {best.metrics['total_return']:.2%}")
    
    # 7. 因子注册演示
    print("\n" + "="*80)
    print("  📦 因子注册系统")
    print("="*80)
    
    registry = FactorRegistry()
    
    factors = [
        FactorMetadata(
            name="rsi_reversal",
            type=FactorType.TECHNICAL,
            description="RSI反转因子，捕捉超买超卖",
            formula="100 - RSI(14)",
            author="quant_team"
        ),
        FactorMetadata(
            name="macd_momentum",
            type=FactorType.TECHNICAL,
            description="MACD动量因子，捕捉趋势",
            formula="MACD_HIST",
            author="quant_team"
        ),
        FactorMetadata(
            name="bollinger_mean_reversion",
            type=FactorType.TECHNICAL,
            description="布林带均值回归因子",
            formula="(Close - BB_Lower) / (BB_Upper - BB_Lower)",
            author="quant_team"
        )
    ]
    
    for factor in factors:
        registry.register_factor(factor)
        print(f"   注册因子: {factor.name}")
    
    print(f"\n因子库总数量: {len(registry.list_factors())}")
    
    print("\n" + "="*80)
    print("  ✅ 回测演示完成！")
    print("="*80)
    print("\n下一步可以:")
    print("  1. 接入真实Data Lake数据")
    print("  2. 使用Walk-Forward滚动回测防过拟合")
    print("  3. 探索更多因子（量价、微观结构）")
    print("  4. 将策略推送到Paper Trading仿真交易")


if __name__ == "__main__":
    main()

