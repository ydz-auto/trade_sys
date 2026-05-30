"""
Feature Registry - 特征注册中心

管理所有可用特征的注册和查询
"""

from typing import Dict, List, Optional, Type, Callable
import pandas as pd
from engines.compute.feature.contracts import Feature, BaseFeature


class FeatureRegistry:
    """特征注册中心"""

    def __init__(self):
        self._features: Dict[str, Feature] = {}
        self._categories: Dict[str, List[str]] = {
            "technical": [],
            "market": [],
            "microstructure": [],
            "regime": [],
            "alpha": [],
        }
        self._dependencies: Dict[str, List[str]] = {}

    def register(self, feature: Feature) -> None:
        """注册特征"""
        if not isinstance(feature, Feature):
            raise TypeError(f"Feature must implement Feature protocol, got {type(feature)}")

        self._features[feature.name] = feature

        if hasattr(feature, 'category'):
            category = getattr(feature, 'category', 'technical')
            if category in self._categories:
                if feature.name not in self._categories[category]:
                    self._categories[category].append(feature.name)

        if isinstance(feature, BaseFeature) and hasattr(feature, 'dependencies'):
            self._dependencies[feature.name] = feature.dependencies

    def get(self, name: str) -> Optional[Feature]:
        """获取特征"""
        return self._features.get(name)

    def list_all(self) -> List[str]:
        """列出所有特征"""
        return list(self._features.keys())

    def list_by_category(self, category: str) -> List[str]:
        """按类别列出特征"""
        return self._categories.get(category, [])

    def list_categories(self) -> List[str]:
        """列出所有类别"""
        return list(self._categories.keys())

    def has(self, name: str) -> bool:
        """检查特征是否存在"""
        return name in self._features

    def get_dependencies(self, name: str) -> List[str]:
        """获取特征依赖"""
        return self._dependencies.get(name, [])

    def resolve_dependencies(self, names: List[str]) -> List[str]:
        """解析特征依赖，返回完整的特征列表（按依赖顺序）"""
        resolved = []
        seen = set()
        to_resolve = list(names)

        while to_resolve:
            name = to_resolve.pop(0)
            if name in seen:
                continue

            deps = self.get_dependencies(name)
            for dep in deps:
                if dep not in seen and dep not in to_resolve:
                    to_resolve.append(dep)

            seen.add(name)
            resolved.append(name)

        return resolved


# 全局注册中心实例
_global_registry: Optional[FeatureRegistry] = None


def get_registry() -> FeatureRegistry:
    """获取全局注册中心"""
    global _global_registry
    if _global_registry is None:
        _global_registry = FeatureRegistry()
        _register_default_features(_global_registry)
    return _global_registry


def _register_default_features(registry: FeatureRegistry) -> None:
    """注册默认特征"""
    from engines.compute.feature.technical import (
        RSI7Feature, RSI14Feature, RSI21Feature,
        EMA10Feature, EMA20Feature, EMA50Feature,
        SMA10Feature, SMA20Feature, SMA50Feature, SMA100Feature,
        ATR14Feature, MACDFeature, MACDSignalFeature, MACDHistFeature,
        BBandsFeature, BBUpperFeature, BBMiddleFeature, BBLowerFeature, BBWidthFeature,
        Volatility20Feature, Volatility60Feature, RealizedVolatilityFeature, VolatilityZScoreFeature,
    )
    from engines.compute.feature.market import (
        FundingRateFeature, FundingZScoreFeature, FundingExtremePositiveFeature,
        FundingExtremeReversalFeature, FundingExplosionFeature,
        OpenInterestFeature, OIChangePctFeature, OIZScoreFeature,
        OIFundingDivergenceFeature, OISqueezeProbabilityFeature,
        OILiquidityPressureFeature, LeverageCrowdednessFeature,
    )
    from engines.compute.feature.microstructure import (
        SpreadEstimateFeature, SpreadPctEstimateFeature, MicropriceEstimateFeature,
        Imbalance1Feature, Imbalance10Feature, ImbalanceSlopeFeature,
        DepthPressureFeature, DepthChangeFeature, LiquidityShiftFeature,
        SpoofProbabilityFeature, WallDetectionFeature,
    )
    from engines.compute.feature.regime import (
        HighVolatilityFeature, LowLiquidityFeature, TrendRegimeFeature,
        VolatilityRegimeFeature, ExtremeMoveFeature, RegimeChangeFeature,
        RiskMultiplierFeature, RiskOnOffFeature, PrimaryRegimeFeature,
        RegimeRiskLevelFeature, PositionSizingMultiplierFeature,
    )
    from engines.compute.feature.alpha_factors import (
        DistanceFromMA20Feature, DistanceFromMA60Feature, DistanceFromVWAPFeature,
        ZScorePriceFeature, MA20SlopeZScoreFeature, PriceDeviationBandFeature,
        Ret3AccelerationFeature, Ret5AccelerationFeature, Ret10AccelerationFeature,
        SlopeAccelerationFeature, CurvatureFeature, VelocityIncreaseFeature,
        MomentumDivergenceFeature, UpperShadowRatioFeature, LowerShadowRatioFeature,
        BodyPctFeature, ConsecutiveGreenFeature, ConsecutiveRedFeature,
        VolumeClimaxFeature, TakerBuyClimaxFeature, NewHigh120Feature,
        BreakoutStrengthFeature, BreakoutFailureFeature, BreakoutRetractionFeature,
        DoubleTopProbabilityFeature, FailedReboundStrengthFeature,
        OIZScoreLongFeature, BasisZScoreFeature, LongShortRatioFeature,
        LeverageRatioLongFeature, FundingOICombinedFeature, CrowdedLongScoreFeature,
        LiquidationRiskLongFeature, ShortSqueezeProbFeature, MarginUsageLongFeature,
    )

    default_features = [
        # Technical
        RSI7Feature(),
        RSI14Feature(),
        RSI21Feature(),
        EMA10Feature(),
        EMA20Feature(),
        EMA50Feature(),
        SMA10Feature(),
        SMA20Feature(),
        SMA50Feature(),
        SMA100Feature(),
        ATR14Feature(),
        MACDFeature(),
        MACDSignalFeature(),
        MACDHistFeature(),
        BBandsFeature(),
        BBUpperFeature(),
        BBMiddleFeature(),
        BBLowerFeature(),
        BBWidthFeature(),
        Volatility20Feature(),
        Volatility60Feature(),
        RealizedVolatilityFeature(),
        VolatilityZScoreFeature(),

        # Market
        FundingRateFeature(),
        FundingZScoreFeature(),
        FundingExtremePositiveFeature(),
        FundingExtremeReversalFeature(),
        FundingExplosionFeature(),
        OpenInterestFeature(),
        OIChangePctFeature(),
        OIZScoreFeature(),
        OIFundingDivergenceFeature(),
        OISqueezeProbabilityFeature(),
        OILiquidityPressureFeature(),
        LeverageCrowdednessFeature(),

        # Microstructure
        SpreadEstimateFeature(),
        SpreadPctEstimateFeature(),
        MicropriceEstimateFeature(),
        Imbalance1Feature(),
        Imbalance10Feature(),
        ImbalanceSlopeFeature(),
        DepthPressureFeature(),
        DepthChangeFeature(),
        LiquidityShiftFeature(),
        SpoofProbabilityFeature(),
        WallDetectionFeature(),

        # Regime
        HighVolatilityFeature(),
        LowLiquidityFeature(),
        TrendRegimeFeature(),
        VolatilityRegimeFeature(),
        ExtremeMoveFeature(),
        RegimeChangeFeature(),
        RiskMultiplierFeature(),
        RiskOnOffFeature(),
        PrimaryRegimeFeature(),
        RegimeRiskLevelFeature(),
        PositionSizingMultiplierFeature(),

        # Alpha Factors
        DistanceFromMA20Feature(),
        DistanceFromMA60Feature(),
        DistanceFromVWAPFeature(),
        ZScorePriceFeature(),
        MA20SlopeZScoreFeature(),
        PriceDeviationBandFeature(),
        Ret3AccelerationFeature(),
        Ret5AccelerationFeature(),
        Ret10AccelerationFeature(),
        SlopeAccelerationFeature(),
        CurvatureFeature(),
        VelocityIncreaseFeature(),
        MomentumDivergenceFeature(),
        UpperShadowRatioFeature(),
        LowerShadowRatioFeature(),
        BodyPctFeature(),
        ConsecutiveGreenFeature(),
        ConsecutiveRedFeature(),
        VolumeClimaxFeature(),
        TakerBuyClimaxFeature(),
        NewHigh120Feature(),
        BreakoutStrengthFeature(),
        BreakoutFailureFeature(),
        BreakoutRetractionFeature(),
        DoubleTopProbabilityFeature(),
        FailedReboundStrengthFeature(),
        OIZScoreLongFeature(),
        BasisZScoreFeature(),
        LongShortRatioFeature(),
        LeverageRatioLongFeature(),
        FundingOICombinedFeature(),
        CrowdedLongScoreFeature(),
        LiquidationRiskLongFeature(),
        ShortSqueezeProbFeature(),
        MarginUsageLongFeature(),
    ]

    for feature in default_features:
        registry.register(feature)
