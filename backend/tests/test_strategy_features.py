"""
策略特征覆盖验证 - 检查所有策略的特征需求完整性

重点检查策略：
1. short_squeeze
2. oi_flush
3. funding_exhaustion_trap
4. cvd_divergence
5. whale_trade
6. aggressive_flow
7. liquidation_cascade
"""
import inspect
import re
from typing import Dict, Any, List, Set
from engines.compute.strategy.registry import (
    _STRATEGY_REGISTRY,
    _STRATEGY_INFO,
    RSIStrategy,
    MACDStrategy,
    PanicReversalStrategy,
    LongLiquidationBounceStrategy,
    VolumeClimaxFadeStrategy,
    WeakBounceShortStrategy,
    DeadCatEchoStrategy,
    OIFlushStrategy,
    ShortSqueezeStrategy,
    FundingExhaustionTrapStrategy,
    ImbalancePressureStrategy,
    SweepDetectionStrategy,
    LiquidityVacuumStrategy,
    AggressiveFlowStrategy,
    BreakoutStrategy,
    TrendFollowingStrategy,
    VolatilityExpansionStrategy,
    BBCompressionBreakoutStrategy,
    MomentumIgnitionStrategy,
    SMACrossStrategy,
    EMACrossStrategy,
    BollingerBandsStrategy,
    MomentumStrategy,
    LeadLagStrategy,
    PremiumDivergenceStrategy,
)
from engines.compute.strategy.behavioral_strategies import (
    OpenInterestBehaviorStrategy,
    FundingExtremeReversalStrategy,
    LiquidationCascadeStrategy,
    CVDDivergenceStrategy,
    WhaleTradeStrategy,
    FundingSettlementStrategy
)


def extract_used_features_from_generate_signal(method) -> Set[str]:
    """
    从generate_signal方法的源代码中提取使用的features key

    Returns:
        features: 提取到的特征名称集合
    """
    try:
        source = inspect.getsource(method)
    except TypeError:
        return set()

    # 寻找 features.get('xxx') 或 features['xxx'] 的模式
    get_pattern = r"features\.get\(['\"](\w+)['\"]"
    index_pattern = r"features\['(\w+)'\]"
    bracket_pattern = r"features\[['\"](\w+)['\"]"

    used_features = set()

    for match in re.finditer(get_pattern, source):
        used_features.add(match.group(1))
    for match in re.finditer(index_pattern, source):
        used_features.add(match.group(1))
    for match in re.finditer(bracket_pattern, source):
        used_features.add(match.group(1))

    return used_features


def check_feature_coverage():
    """
    检查所有策略的特征覆盖情况

    Returns:
        report: 检查报告字典
    """
    report = {
        "total_strategies": 0,
        "covered_strategies": 0,
        "uncovered_features": {},
        "missing_required_features": {},
        "all_used_features": set(),
        "high_priority_strategies": []
    }

    # 重点策略
    high_priority = [
        "oi_flush",
        "short_squeeze",
        "funding_exhaustion_trap",
        "cvd_divergence",
        "whale_trade",
        "aggressive_flow",
        "liquidation_cascade"
    ]

    for strategy_id, strategy_class in _STRATEGY_REGISTRY.items():
        if strategy_id not in _STRATEGY_INFO:
            continue

        info = _STRATEGY_INFO[strategy_id]
        report["total_strategies"] += 1

        # 提取实际使用的特征
        if hasattr(strategy_class, 'generate_signal'):
            used_features = extract_used_features_from_generate_signal(
                strategy_class.generate_signal
            )
            report["all_used_features"].update(used_features)
        else:
            used_features = set()

        # 检查特征覆盖
        required_features = set(info.required_features)

        # 有使用但没声明的特征
        used_but_not_declared = used_features - required_features
        # 有声明但没使用的特征
        declared_but_not_used = required_features - used_features

        strategy_report = {
            "strategy_id": strategy_id,
            "required_features": list(required_features),
            "used_features": list(used_features),
            "used_but_not_declared": list(used_but_not_declared),
            "declared_but_not_used": list(declared_but_not_used)
        }

        if strategy_id in high_priority:
            report["high_priority_strategies"].append(strategy_report)
            print(f"\n=== HIGH PRIORITY: {strategy_id} ===")
            print(f"Required: {sorted(info.required_features)}")
            print(f"Used:     {sorted(used_features)}")
            if used_but_not_declared:
                print(f"⚠️  Used but not declared: {sorted(used_but_not_declared)}")
                report["uncovered_features"][strategy_id] = list(used_but_not_declared)
            if declared_but_not_used:
                print(f"ℹ️   Declared but not used: {sorted(declared_but_not_used)}")
                report["missing_required_features"][strategy_id] = list(declared_but_not_used)

        # 只要有 generate_signal 就算覆盖
        if hasattr(strategy_class, 'generate_signal'):
            report["covered_strategies"] += 1

    return report


if __name__ == "__main__":
    print("=== 策略特征覆盖验证 ===\n")
    report = check_feature_coverage()

    print(f"\n=== Summary ===")
    print(f"Total strategies: {report['total_strategies']}")
    print(f"Strategies with generate_signal(): {report['covered_strategies']}")
    print(f"All used features ({len(report['all_used_features'])}):")
    for feature in sorted(report['all_used_features']):
        print(f"  - {feature}")

    print(f"\nHigh priority strategy count: {len(report['high_priority_strategies'])}")
