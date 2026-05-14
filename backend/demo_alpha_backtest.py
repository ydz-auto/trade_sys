#!/usr/bin/env python3
"""
完整Alpha回测演示 - 因子策略 + Walk-Forward + 实验追踪
演示系统：
1. Feature Pipeline 生成技术因子
2. Factor Evaluator 评估因子表现
3. Walk-Forward 滚动回测
4. Experiment Tracker 记录实验
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd
import numpy as np

# 添加backend路径
sys.path.insert(0, str(Path(__file__).parent))

from research.pipeline.feature_pipeline import FeaturePipeline, TechnicalFeatureEngine
from research.factor.evaluator import FactorEvaluator, EvaluationMetrics
from research.backtest.walk_forward import WalkForwardEngine, WalkForwardConfig
from research.experiment.tracker import ExperimentTracker, Experiment, HyperparameterTrial
from research.strategy.versioning import AlphaPipeline, StrategyVersion, DeploymentStatus
from research.factor.registry import FactorRegistry, FactorMetadata, FactorType, FactorStatus


def generate_mock_historical_data(symbol: str = "BTC/USDT", days: int = 120) -> pd.DataFrame:
    """生成模拟历史数据（模拟真实Data Lake数据）"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    timestamps = pd.date_range(start=start_date, end=end_date, freq="1h")
    
    # 生成带趋势和波动率的价格
    np.random.seed(42)
    n = len(timestamps)
    returns = np.random.normal(0.001, 0.03, n)
    price = 50000 * (1 + returns).cumprod()
    
    # 添加一些趋势和波动率集群
    for i in range(1, n):
        if i % 48 == 0:  # 每2天调整一次趋势
            returns[i] = returns[i] * 1.5
    
    price = 50000 * (1 + returns).cumprod()
    
    # OHLCV
    high = price * (1 + np.random.uniform(0, 0.02, n))
    low = price * (1 - np.random.uniform(0, 0.02, n))
    open_ = low + np.random.uniform(0, 1, n) * (high - low)
    close = price
    volume = np.random.lognormal(10, 1, n)
    
    data = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": symbol,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    })
    data.set_index("timestamp", inplace=True)
    return data


def demo_feature_pipeline():
    """演示特征流水线 - 生成技术因子"""
    print("\n" + "="*80)
    print("1. Feature Pipeline - 特征工程流水线")
    print("="*80)
    
    # 生成数据
    data = generate_mock_historical_data()
    print(f"\n原始数据: {len(data)} 条记录")
    print(data.tail())
    
    # 创建特征引擎
    feature_engine = TechnicalFeatureEngine()
    
    # 计算所有技术指标
    print("\n正在计算技术因子...")
    data_with_features = feature_engine.compute_all_features(data)
    
    print(f"\n生成的特征: {len([col for col in data_with_features.columns if col not in ['open', 'high', 'low', 'close', 'volume']])} 个")
    print("\n特征列表:")
    for col in sorted(data_with_features.columns):
        if col not in ['open', 'high', 'low', 'close', 'volume', 'symbol']:
            print(f"  - {col}")
    
    print("\n带特征的数据预览:")
    feature_cols = [col for col in data_with_features.columns if col.startswith(('rsi', 'macd', 'bb_', 'atr', 'ma'))]
    print(data_with_features[['close'] + feature_cols[:5]].tail())
    
    return data_with_features


def demo_factor_evaluation(data: pd.DataFrame):
    """演示因子评估 - IC/IR/Sharpe"""
    print("\n" + "="*80)
    print("2. Factor Evaluator - 因子评估")
    print("="*80)
    
    evaluator = FactorEvaluator()
    
    # 计算未来收益率
    data['forward_return_1'] = data['close'].pct_change(1).shift(-1)
    data['forward_return_5'] = data['close'].pct_change(5).shift(-5)
    data['forward_return_10'] = data['close'].pct_change(10).shift(-10)
    
    # 选择几个因子进行评估
    factors = ['rsi_14', 'macd_hist', 'bb_width', 'atr_ratio', 'ma_cross_signal']
    periods = [1, 5, 10]
    
    factor_results = {}
    
    for factor_name in factors:
        if factor_name not in data.columns:
            continue
            
        print(f"\n评估因子: {factor_name}")
        factor_values = data[factor_name].dropna()
        aligned_data = data.loc[factor_values.index]
        
        metrics = evaluator.evaluate_factor(
            factor_values=factor_values,
            future_returns=aligned_data['forward_return_5'],
            periods=periods
        )
        
        factor_results[factor_name] = metrics
        print(f"  IC Mean: {metrics.ic_mean:.4f}")
        print(f"  IC IR: {metrics.ic_ir:.4f}")
        print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"  Turnover: {metrics.turnover:.2%}")
        print(f"  Decay: {metrics.decay:.4f}")
    
    return factor_results


def demo_walk_forward(data: pd.DataFrame):
    """演示Walk-Forward滚动回测"""
    print("\n" + "="*80)
    print("3. Walk-Forward Engine - 滚动回测")
    print("="*80)
    
    config = WalkForwardConfig(
        initial_capital=100000,
        train_window=60,  # 60天训练
        test_window=10,   # 10天验证
        step_size=5,      # 5天滚动
        commission_rate=0.001,
        slippage=0.001
    )
    
    engine = WalkForwardEngine(config)
    
    # 简单的因子策略（使用RSI和MACD）
    def factor_strategy(data_window: pd.DataFrame, params: Dict[str, Any]):
        """基于因子的策略"""
        rsi_period = params.get('rsi_period', 14)
        rsi_low = params.get('rsi_low', 30)
        rsi_high = params.get('rsi_high', 70)
        
        signals = []
        for idx, row in data_window.iterrows():
            rsi = row.get(f'rsi_{rsi_period}', 50)
            macd_hist = row.get('macd_hist', 0)
            
            if pd.isna(rsi) or pd.isna(macd_hist):
                signals.append(0)
            elif rsi < rsi_low and macd_hist > 0:
                signals.append(1)  # 买入
            elif rsi > rsi_high and macd_hist < 0:
                signals.append(-1) # 卖出
            else:
                signals.append(0)
        
        return pd.Series(signals, index=data_window.index)
    
    print("\n配置Walk-Forward:")
    print(f"  训练窗口: {config.train_window} 天")
    print(f"  测试窗口: {config.test_window} 天")
    print(f"  滚动步长: {config.step_size} 天")
    
    print("\n正在运行Walk-Forward回测...")
    result = engine.run(
        data=data,
        strategy_func=factor_strategy,
        params={'rsi_period': 14, 'rsi_low': 30, 'rsi_high': 70}
    )
    
    print(f"\nWalk-Forward 结果:")
    print(f"  总收益率: {result.total_return:.2%}")
    print(f"  年化收益率: {result.annualized_return:.2%}")
    print(f"  夏普比率: {result.sharpe_ratio:.2f}")
    print(f"  最大回撤: {result.max_drawdown:.2%}")
    print(f"  总交易次数: {result.total_trades}")
    print(f"  胜率: {result.win_rate:.2%}")
    
    print(f"\n  窗口数量: {len(result.window_results)}")
    for i, win in enumerate(result.window_results[:3]):
        print(f"    窗口{i+1}: 收益 {win.return_pct:.2%}, 夏普 {win.sharpe_ratio:.2f}")
    
    return result


def demo_experiment_tracker():
    """演示实验追踪"""
    print("\n" + "="*80)
    print("4. Experiment Tracker - 实验追踪")
    print("="*80)
    
    tracker = ExperimentTracker()
    
    # 创建实验
    experiment = Experiment(
        name="rsi_macd_factor_strategy_v1",
        description="基于RSI和MACD的因子策略",
        tags=["factor", "rsi", "macd", "walk-forward"]
    )
    tracker.create_experiment(experiment)
    
    # 超参数优化试验
    param_sets = [
        {'rsi_period': 7, 'rsi_low': 20, 'rsi_high': 80},
        {'rsi_period': 14, 'rsi_low': 30, 'rsi_high': 70},
        {'rsi_period': 21, 'rsi_low': 25, 'rsi_high': 75},
    ]
    
    print("\n运行超参数试验...")
    for i, params in enumerate(param_sets):
        trial = HyperparameterTrial(
            experiment_id=experiment.id,
            parameters=params,
            metrics={'dummy_sharpe': 1.0 + i * 0.3, 'dummy_return': 0.15 + i * 0.05}
        )
        tracker.log_trial(trial)
        print(f"  试验{i+1}: {params} → Sharpe {trial.metrics['dummy_sharpe']:.2f}")
    
    # 获取最佳试验
    best = tracker.get_best_trial(experiment.id, 'dummy_sharpe')
    print(f"\n最佳试验: {best.parameters}")
    
    return tracker, experiment


def demo_alpha_pipeline(data: pd.DataFrame):
    """演示Alpha完整流水线"""
    print("\n" + "="*80)
    print("5. Alpha Pipeline - Alpha生产流水线")
    print("="*80)
    
    registry = FactorRegistry()
    alpha_pipeline = AlphaPipeline()
    
    # 1. 注册因子
    print("\n注册因子...")
    factor1 = FactorMetadata(
        name="rsi_reversal",
        type=FactorType.TECHNICAL,
        description="RSI反转因子",
        formula="100 - RSI(14)",
        author="quant_research"
    )
    registry.register_factor(factor1)
    
    factor2 = FactorMetadata(
        name="macd_momentum",
        type=FactorType.TECHNICAL,
        description="MACD动量因子",
        formula="MACD_HIST",
        author="quant_research"
    )
    registry.register_factor(factor2)
    
    # 2. 创建策略版本
    print("\n创建策略版本...")
    strategy_v1 = StrategyVersion(
        name="rsi_macd_combo_v1",
        factors=["rsi_reversal", "macd_momentum"],
        weights=[0.5, 0.5],
        parameters={'lookback': 20}
    )
    
    # 3. 走Alpha流水线
    print("\nAlpha流水线流程:")
    version = alpha_pipeline.create_version(strategy_v1)
    print(f"  ✅ 创建版本: {version.version} → {version.status.value}")
    
    version = alpha_pipeline.promote_to_candidate(version.id)
    print(f"  ✅ 提升候选: {version.status.value}")
    
    version = alpha_pipeline.start_shadow(version.id)
    print(f"  ✅ 启动影子: {version.status.value}")
    
    version = alpha_pipeline.promote_to_paper(version.id)
    print(f"  ✅ 仿真交易: {version.status.value}")
    
    print(f"\n策略版本历史:")
    for v in alpha_pipeline.get_version_history(version.id):
        print(f"  {v.version} - {v.status.value}")


def main():
    """主函数 - 完整演示"""
    print("\n" + "="*80)
    print("  🚀 Alpha 回测系统完整演示")
    print("="*80)
    print("系统模块: Feature Pipeline → Factor Evaluator → Walk-Forward → Experiment → Alpha")
    
    try:
        # 1. Feature Pipeline
        data = demo_feature_pipeline()
        
        # 2. Factor Evaluation
        factor_results = demo_factor_evaluation(data)
        
        # 3. Walk-Forward
        wf_result = demo_walk_forward(data)
        
        # 4. Experiment Tracker
        tracker, experiment = demo_experiment_tracker()
        
        # 5. Alpha Pipeline
        demo_alpha_pipeline(data)
        
        print("\n" + "="*80)
        print("  ✅ 演示完成！Alpha系统已就绪")
        print("="*80)
        print("\n接下来可以:")
        print("  1. 接入真实Data Lake数据替代模拟数据")
        print("  2. 探索更多因子（量价、微观结构、另类数据）")
        print("  3. 运行完整的超参数优化")
        print("  4. 将策略推送到Paper Trading仿真交易")
        
    except Exception as e:
        print(f"\n❌ 演示出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

