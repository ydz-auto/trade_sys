"""
Signal Validation - 信号验证工具

目标：证明 signal 有信息含量（不是赚钱）

核心指标：
- signal_count: 信号总数
- long_short_ratio: 多空比例
- confidence_distribution: 置信度分布
- reason_distribution: 信号原因分布

验证的不是"策略能赚钱"，而是"策略产生的信号是否有一致性"
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from collections import Counter
import pandas as pd
import numpy as np
from scipy import stats
import argparse
import os

# 自动添加项目根目录到 sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engines.compute.strategy_v2 import Signal, StrategyV2, StrategyMeta, SignalType

try:
    from research.common.loaders import get_strategy_class, save_results_to_json, load_from_datalake
    from research.common.types import StrategyName
except ImportError:
    from common.loaders import get_strategy_class, save_results_to_json, load_from_datalake
    from common.types import StrategyName


@dataclass
class SignalValidationResult:
    """信号验证结果"""
    
    # 基础统计
    sample_count: int
    active_signal_count: int
    long_signals: int
    short_signals: int
    none_signals: int
    active_signal_rate: float
    long_short_ratio: float
    
    # 置信度分布
    avg_confidence_active: float
    avg_confidence_all: float
    median_confidence: float
    min_confidence: float
    max_confidence: float
    confidence_std: float
    
    # 置信度分位数
    confidence_p25: float
    confidence_p50: float
    confidence_p75: float
    
    # 信号原因分布
    reason_distribution: Dict[str, int]
    top_reasons: List[Tuple[str, int]]
    
    # 时间分布
    signals_per_day: float
    signals_per_hour: float
    
    # 信号一致性指标
    long_confidence_distribution: Dict[str, float]
    short_confidence_distribution: Dict[str, float]
    
    # 统计检验
    confidence_t_test: float
    confidence_p_value: float
    
    def __repr__(self):
        return f"""SignalValidationResult:
  样本数: {self.sample_count}
  有效交易信号: {self.active_signal_count}
  触发率: {self.active_signal_rate:.2%}
  多头信号: {self.long_signals}
  空头信号: {self.short_signals}
  无信号: {self.none_signals}
  多空比例: {self.long_short_ratio:.2f}
  
  置信度统计:
    活跃信号平均: {self.avg_confidence_active:.3f}
    所有信号平均: {self.avg_confidence_all:.3f}
    中位数: {self.median_confidence:.3f}
    标准差: {self.confidence_std:.3f}
    范围: [{self.min_confidence:.3f}, {self.max_confidence:.3f}]
  
  信号原因Top5: {self.top_reasons}
  日均信号数: {self.signals_per_day:.2f}
"""


class SignalValidator:
    """
    信号验证器
    
    核心职责：
    1. 统计信号产生的频率和分布
    2. 分析置信度的统计特性
    3. 验证信号产生的一致性
    4. 识别信号的主要触发原因
    """
    
    def __init__(self, strategy: StrategyV2):
        self.strategy = strategy
        self.signals: List[Signal] = []
        self.signal_timestamps: List[int] = []
    
    def add_signal(self, signal: Signal, timestamp: int):
        """添加信号记录"""
        self.signals.append(signal)
        self.signal_timestamps.append(timestamp)
    
    def validate(self) -> SignalValidationResult:
        """执行完整的信号验证"""
        if not self.signals:
            raise ValueError("没有信号数据可验证")
        
        sample_count = len(self.signals)
        
        # 基础统计 - 正确区分 active 和 none 信号（使用 SignalType 枚举）
        long_signals = sum(1 for s in self.signals if s.type == SignalType.LONG)
        short_signals = sum(1 for s in self.signals if s.type == SignalType.SHORT)
        none_signals = sum(1 for s in self.signals if s.type == SignalType.NONE)
        active_signal_count = long_signals + short_signals
        active_signal_rate = active_signal_count / sample_count if sample_count > 0 else 0.0
        
        long_short_ratio = long_signals / short_signals if short_signals > 0 else float('inf')
        
        # 置信度统计 - 区分 active 和 all
        all_confs = [s.confidence for s in self.signals if s.confidence is not None]
        active_confs = [s.confidence for s in self.signals 
                        if s.confidence is not None and s.type in (SignalType.LONG, SignalType.SHORT)]
        
        if all_confs:
            avg_confidence_all = np.mean(all_confs)
            median_confidence = np.median(all_confs)
            min_confidence = np.min(all_confs)
            max_confidence = np.max(all_confs)
            confidence_std = np.std(all_confs)
            confidence_p25 = np.percentile(all_confs, 25)
            confidence_p50 = np.percentile(all_confs, 50)
            confidence_p75 = np.percentile(all_confs, 75)
            
            # 统计检验：置信度是否显著大于0.5（随机猜测）
            t_stat, p_value = stats.ttest_1samp(all_confs, 0.5)
        else:
            avg_confidence_all = median_confidence = min_confidence = max_confidence = 0.0
            confidence_std = confidence_p25 = confidence_p50 = confidence_p75 = 0.0
            t_stat = p_value = 0.0
        
        avg_confidence_active = np.mean(active_confs) if active_confs else 0.0
        
        # 信号原因分布
        reasons = [s.reason for s in self.signals if s.reason]
        reason_distribution = Counter(reasons)
        top_reasons = reason_distribution.most_common(5)
        
        # 时间分布
        if self.signal_timestamps:
            timestamps = np.array(self.signal_timestamps)
            duration_days = (timestamps[-1] - timestamps[0]) / (1000 * 60 * 60 * 24)
            signals_per_day = active_signal_count / duration_days if duration_days > 0 else 0
            signals_per_hour = signals_per_day / 24
        else:
            signals_per_day = signals_per_hour = 0
        
        # 多空置信度分布
        long_confs = [s.confidence for s in self.signals if s.type == SignalType.LONG and s.confidence]
        short_confs = [s.confidence for s in self.signals if s.type == SignalType.SHORT and s.confidence]
        
        long_confidence_distribution = self._compute_distribution(long_confs)
        short_confidence_distribution = self._compute_distribution(short_confs)
        
        return SignalValidationResult(
            sample_count=sample_count,
            active_signal_count=active_signal_count,
            long_signals=long_signals,
            short_signals=short_signals,
            none_signals=none_signals,
            active_signal_rate=active_signal_rate,
            long_short_ratio=long_short_ratio,
            avg_confidence_active=avg_confidence_active,
            avg_confidence_all=avg_confidence_all,
            median_confidence=median_confidence,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            confidence_std=confidence_std,
            confidence_p25=confidence_p25,
            confidence_p50=confidence_p50,
            confidence_p75=confidence_p75,
            reason_distribution=dict(reason_distribution),
            top_reasons=top_reasons,
            signals_per_day=signals_per_day,
            signals_per_hour=signals_per_hour,
            long_confidence_distribution=long_confidence_distribution,
            short_confidence_distribution=short_confidence_distribution,
            confidence_t_test=t_stat,
            confidence_p_value=p_value,
        )
    
    def _compute_distribution(self, values: List[float]) -> Dict[str, float]:
        """计算数值分布（分桶统计）"""
        if not values:
            return {}
        
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        labels = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        
        hist, _ = np.histogram(values, bins=bins)
        total = len(values)
        
        return {
            label: hist[i] / total for i, label in enumerate(labels)
        }
    
    def get_signals_df(self) -> pd.DataFrame:
        """获取信号数据的 DataFrame"""
        data = []
        for signal, timestamp in zip(self.signals, self.signal_timestamps):
            data.append({
                "timestamp": timestamp,
                "type": signal.type,
                "confidence": signal.confidence,
                "reason": signal.reason,
                "strategy": self.strategy.meta.name,
            })
        return pd.DataFrame(data)


def validate_strategy(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int]
) -> SignalValidationResult:
    """
    验证策略产生的信号
    
    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 对应的时间戳列表
    
    Returns:
        SignalValidationResult: 验证结果
    """
    validator = SignalValidator(strategy)
    
    for ctx, ts in zip(market_contexts, timestamps):
        signal = strategy.generate_signal(ctx)
        validator.add_signal(signal, ts)
    
    return validator.validate()


def compare_strategies(
    strategies: List[StrategyV2],
    market_contexts: List[Any],
    timestamps: List[int]
) -> pd.DataFrame:
    """
    比较多个策略的信号验证结果
    
    Args:
        strategies: 策略列表
        market_contexts: MarketContext 列表
        timestamps: 对应的时间戳列表
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = []
    
    for strategy in strategies:
        result = validate_strategy(strategy, market_contexts, timestamps)
        results.append({
            "strategy": strategy.meta.name,
            "sample_count": result.sample_count,
            "active_signal_count": result.active_signal_count,
            "active_signal_rate": result.active_signal_rate,
            "long_signals": result.long_signals,
            "short_signals": result.short_signals,
            "none_signals": result.none_signals,
            "long_short_ratio": result.long_short_ratio,
            "avg_confidence_active": result.avg_confidence_active,
            "avg_confidence_all": result.avg_confidence_all,
            "median_confidence": result.median_confidence,
            "confidence_std": result.confidence_std,
            "signals_per_day": result.signals_per_day,
            "confidence_p_value": result.confidence_p_value,
        })
    
    return pd.DataFrame(results)


__all__ = [
    "SignalValidationResult",
    "SignalValidator",
    "validate_strategy",
    "compare_strategies",
]


# ==================== CLI 命令行接口 ====================

def generate_test_contexts(num_samples: int = 1000):
    """生成测试用的 MarketContext 序列"""
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
    
    market_contexts = []
    timestamps = []
    
    base_timestamp = int(pd.Timestamp("2024-01-01").value / 10**6)
    base_price = 45000.0
    
    # 必需的时间周期
    REQUIRED_TFS = ["1m", "5m", "15m", "1h", "4h"]
    
    for i in range(num_samples):
        timestamp = base_timestamp + i * 15 * 60 * 1000
        timestamps.append(timestamp)
        
        price_change = np.random.normal(0, 0.003) * base_price
        price = base_price + price_change
        base_price = price
        
        tf_contexts = {}
        
        # 增加极端情况概率
        extreme_prob = 0.15  # 15% 概率触发极端情况
        
        # 1m
        m1_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
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
                state=np.random.choice([LiquidityState.NORMAL, LiquidityState.THIN], p=[0.9, 0.1]),
                spread=0.5,
            ),
            flow=FlowState(
                pressure=m1_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-100, 100),
            ),
        )
        
        # 5m
        m5_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
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
            ),
        )
        
        # 15m（主周期）
        m15_trend = np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                    p=[0.35, 0.35, 0.3])
        m15_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        
        # 增加价格上涨概率（触发 short squeeze）
        if np.random.random() < extreme_prob:
            m15_change_percent = np.random.uniform(0.5, 1.5)
        else:
            m15_change_percent = np.random.uniform(-1.2, 1.2)
        
        tf_contexts["15m"] = TimeframeContext(
            timeframe="15m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.006)),
                low=price * (1 - np.random.uniform(0, 0.006)),
                close=price,
                change_percent=m15_change_percent,
            ),
            trend=TrendStateData(
                state=m15_trend,
                slope=np.random.uniform(-0.012, 0.012),
                strength=np.random.uniform(0.3, 0.95),
            ),
            volatility=VolatilityStateData(
                state=np.random.choice([VolatilityState.NORMAL, VolatilityState.ELEVATED, VolatilityState.LOW], 
                                      p=[0.5, 0.35, 0.15]),
                atr_pct=np.random.uniform(0.008, 0.025),
            ),
            volume=VolumeStateData(
                state=np.random.choice([VolumeState.NORMAL, VolumeState.CLIMAX, VolumeState.DRY], 
                                      p=[0.6, 0.25, 0.15]),
                volume_zscore=np.random.uniform(-2.5, 2.5),
            ),
            flow=FlowState(
                pressure=m15_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-1200, 1200),
                cvd_slope=np.random.uniform(-0.15, 0.15),
                aggressive_ratio=np.random.uniform(0.25, 0.75),
            ),
        )
        
        # 1h
        tf_contexts["1h"] = TimeframeContext(
            timeframe="1h",
            trend=TrendStateData(
                state=np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                      p=[0.35, 0.35, 0.3]),
                slope=np.random.uniform(-0.006, 0.006),
                strength=np.random.uniform(0.3, 0.95),
            ),
            price=PriceState(close=price, change_percent=np.random.uniform(-1.8, 1.8)),
        )
        
        # 4h
        tf_contexts["4h"] = TimeframeContext(
            timeframe="4h",
            trend=TrendStateData(
                state=np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                      p=[0.35, 0.35, 0.3]),
                slope=np.random.uniform(-0.004, 0.004),
                strength=np.random.uniform(0.3, 0.95),
            ),
        )
        
        # 增加极端持仓量和负资金费率概率（触发 short squeeze）
        if np.random.random() < extreme_prob:
            oi_zscore = np.random.uniform(1.6, 3.5)
        else:
            oi_zscore = np.random.uniform(-2.8, 2.8)
        
        if np.random.random() < extreme_prob:
            funding_zscore = np.random.uniform(-3.5, -1.6)
        else:
            funding_zscore = np.random.uniform(-2.8, 2.8)
        
        if funding_zscore > 2.0:
            funding_bias = FundingBias.EXTREME_POSITIVE
        elif funding_zscore > 0.5:
            funding_bias = FundingBias.POSITIVE
        elif funding_zscore < -2.0:
            funding_bias = FundingBias.EXTREME_NEGATIVE
        elif funding_zscore < -0.5:
            funding_bias = FundingBias.NEGATIVE
        else:
            funding_bias = FundingBias.NEUTRAL
        
        derivatives = DerivativesContext(
            oi=OIData(
                value=np.random.uniform(1500000, 6000000),
                delta=np.random.uniform(-150000, 150000),
                zscore=oi_zscore,
            ),
            funding=FundingData(
                rate=np.random.uniform(-0.012, 0.012),
                zscore=funding_zscore,
                bias=funding_bias,
            ),
            liquidation=LiquidationData(
                long=np.random.uniform(0, 150000),
                short=np.random.uniform(0, 150000),
                total=np.random.uniform(0, 300000),
                long_zscore=np.random.uniform(-3.5, 3.5),
                short_zscore=np.random.uniform(-3.5, 3.5),
                reversal_signal=np.random.random() < 0.1,
            ),
        )
        
        ctx = MarketContext(
            symbol="BTCUSDT",
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )
        
        market_contexts.append(ctx)
    
    return market_contexts, timestamps


def main():
    """CLI 入口函数"""
    parser = argparse.ArgumentParser(description="Signal Validation Tool - 信号验证工具")
    
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=StrategyName.ALL,
        help=f"策略名称: {', '.join(StrategyName.ALL)}"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="交易对 (默认: BTCUSDT)"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="测试天数 (默认: 30)"
    )
    
    parser.add_argument(
        "--source",
        type=str,
        default="mock",
        choices=["mock", "datalake", "parquet"],
        help="数据源: mock / datalake / parquet (默认: mock)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径"
    )
    
    args = parser.parse_args()
    
    print(f"信号验证: {args.strategy} | {args.symbol} | {args.days}天")
    print(f"数据源: {args.source}")
    print("="*50)
    
    # 获取策略类
    strategy_class = get_strategy_class(args.strategy)
    if not strategy_class:
        print(f"错误: 未知策略 {args.strategy}")
        sys.exit(1)
    
    # 根据数据源获取数据
    if args.source == "parquet":
        print(f"从 Parquet 加载 {args.symbol} 最近 {args.days} 天数据...")
        from research.common.loaders import load_from_parquet
        market_contexts, timestamps, prices = load_from_parquet(args.symbol, args.days)
        
        if not market_contexts:
            print("警告: 从 Parquet 未获取到数据，使用 mock 数据")
            samples_per_day = 96
            num_samples = args.days * samples_per_day
            market_contexts, timestamps = generate_test_contexts(num_samples)
    
    elif args.source == "datalake":
        print(f"从 DataLake 加载 {args.symbol} 最近 {args.days} 天数据...")
        data, timestamps, prices = load_from_datalake(args.symbol, args.days)
        
        if not data:
            print("警告: 从 DataLake 未获取到数据，使用 mock 数据")
            samples_per_day = 96
            num_samples = args.days * samples_per_day
            market_contexts, timestamps = generate_test_contexts(num_samples)
        else:
            print(f"将 {len(data)} 条数据转换为 MarketContext...")
            from engines.compute.context import MarketContextBuilder
            builder = MarketContextBuilder()
            market_contexts = [builder.build_from_raw(row) for row in data]
    
    else:
        # 生成测试数据
        samples_per_day = 96  # 15分钟bar
        num_samples = args.days * samples_per_day
        print(f"生成 {num_samples} 个 mock 样本...")
        market_contexts, timestamps = generate_test_contexts(num_samples)
    
    # 创建策略实例并验证
    strategy = strategy_class(args.symbol)
    result = validate_strategy(strategy, market_contexts, timestamps)
    
    # 打印结果
    print(result)
    
    # 输出统计检验结果
    print(f"置信度 t检验: t={result.confidence_t_test:.2f}, p={result.confidence_p_value:.4f}")
    if result.confidence_p_value < 0.05:
        print("✓ 置信度显著大于随机猜测")
    else:
        print("✗ 置信度不显著")
    
    # 验收检查
    print("\n验收检查:")
    checks = [
        ("sample_count > 0", result.sample_count > 0),
        ("active_signal_count > 0", result.active_signal_count > 0),
        ("confidence_std > 0", result.confidence_std > 0),
        ("reason_count >= 1", len(result.reason_distribution) >= 1),
        ("无异常单边爆炸", result.long_short_ratio < 10 and result.long_short_ratio > 0.1),
    ]
    
    all_pass = True
    for check, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_pass = False
    
    if all_pass:
        print("\n✓ 所有检查通过")
    else:
        print("\n✗ 部分检查未通过")
    
    # 保存结果
    if args.output:
        result_dict = {
            "strategy": args.strategy,
            "symbol": args.symbol,
            "days": args.days,
            "sample_count": result.sample_count,
            "active_signal_count": result.active_signal_count,
            "active_signal_rate": result.active_signal_rate,
            "long_signals": result.long_signals,
            "short_signals": result.short_signals,
            "none_signals": result.none_signals,
            "long_short_ratio": result.long_short_ratio,
            "avg_confidence_active": result.avg_confidence_active,
            "avg_confidence_all": result.avg_confidence_all,
            "confidence_std": result.confidence_std,
            "signals_per_day": result.signals_per_day,
            "reason_distribution": result.reason_distribution,
            "confidence_p_value": result.confidence_p_value,
        }
        save_results_to_json(result_dict, args.output)


if __name__ == "__main__":
    main()
