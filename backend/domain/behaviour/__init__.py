"""
Behaviour Detection - 市场行为检测

将 Feature 转化为可交易行为:
1. Panic Detection - 恐慌检测
2. Absorption Detection - 吸筹检测
3. Breakout Detection - 突破检测
4. Liquidation Cascade - 爆仓连锁检测
5. Trend Exhaustion - 趋势耗竭检测
6. Mean Reversion - 均值回归检测
"""
from .panic import PanicDetector, detect_panic
from .absorption import AbsorptionDetector, detect_absorption
from .breakout import BreakoutDetector, detect_breakout
from .liquidation_cascade import LiquidationCascadeDetector, detect_liquidation_cascade
from .trend_exhaustion import TrendExhaustionDetector, detect_trend_exhaustion
from .mean_reversion import MeanReversionDetector, detect_mean_reversion
from .detector import BehaviourDetector

__all__ = [
    "PanicDetector",
    "detect_panic",
    "AbsorptionDetector",
    "detect_absorption",
    "BreakoutDetector",
    "detect_breakout",
    "LiquidationCascadeDetector",
    "detect_liquidation_cascade",
    "TrendExhaustionDetector",
    "detect_trend_exhaustion",
    "MeanReversionDetector",
    "detect_mean_reversion",
    "BehaviourDetector",
]
