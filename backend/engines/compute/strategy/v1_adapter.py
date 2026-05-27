"""
V1 策略适配器

作用：
- 把旧的 V1 策略（feature-based）适配到新的统一架构
- V1 策略通过 Adapter 访问 MarketContext，而不是直接访问 features
- 这样可以渐进式迁移，而不需要一次性重写所有策略

设计原则：
- V1 策略依然保留，但必须通过 Adapter 来工作
- Adapter 把 MarketContext 翻译成 V1 策略可用的接口
- 最终目标：所有策略都迁移到 V2，然后可以慢慢废弃 Adapter
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from domain.market_state import MarketContext
from domain.event.base_event import BaseEvent
from engines.compute.strategy.strategies import StrategySignal
from infrastructure.logging import get_logger

logger = get_logger("strategy.v1_adapter")


@dataclass
class V1StrategyAdapter:
    """
    V1 策略适配器
    
    把 MarketContext → V1 策略接口
    """
    
    # 从 MarketContext 提取 V1 策略需要的特征
    @staticmethod
    def extract_features_for_v1(context: MarketContext) -> Dict[str, float]:
        """
        从 MarketContext 提取 V1 策略需要的特征
        
        这样 V1 策略不需要知道新架构的具体实现
        """
        features = {}
        
        # 从 core state 中提取信息
        core = context.core
        
        # 基础特征（从 state 映射到 V1 期望的格式
        features['regime'] = core.regime.name
        features['liquidity_state'] = core.liquidity.name
        features['pressure_state'] = core.pressure.name
        features['volatility_state'] = core.volatility.name
        features['trend_state'] = core.trend.name
        
        # 把 enum 转为数值
        features['confidence'] = core.confidence
        
        # 从 features snapshot 复制
        features.update(context.features)
        
        # 添加语义化标签
        features['is_exhausted'] = 1.0 if context.is_exhausted() else 0.0
        features['is_liquid_vacuum'] = 1.0 if context.is_liquid_vacuum() else 0.0
        features['is_flush'] = 1.0 if context.is_flush() else 0.0
        features['is_squeeze'] = 1.0 if context.is_squeeze() else 0.0
        features['is_quiet'] = 1.0 if context.is_quiet() else 0.0
        
        # 趋势强度和流动性质量
        features['trend_strength'] = context.get_trend_strength()
        features['liquidity_quality'] = context.get_liquidity_quality()
        
        return features
    
    @staticmethod
    def adapt_signal(signal: Any) -> Optional[StrategySignal]:
        """
        适配 V1 策略的信号输出
        """
        # 这里根据实际 V1 策略返回的类型做适配
        return signal


class V1StrategyWrapper:
    """
    V1 策略包装器
    
    把旧的 V1 策略包装成 V2 接口
    """
    
    def __init__(self, v1_strategy):
        self._v1_strategy = v1_strategy
        logger.info(f"V1 strategy wrapped: {v1_strategy.__class__.__name__}")
    
    def generate_signal(
        self,
        market_context: MarketContext,
        event: BaseEvent,
        features: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """
        生成信号（通过 MarketContext）
        """
        # 从 MarketContext 提取 V1 策略需要的特征
        adapted_features = V1StrategyAdapter.extract_features_for_v1(market_context)
        
        # 调用 V1 策略（现在用 adapted_features 替代原始 features 的结合
        v1_signal = self._v1_strategy.generate_signal(
            event, adapted_features)
        
        # 适配信号输出
        return V1StrategyAdapter.adapt_signal(v1_signal)


# ============== 导出接口 ==============

__all__ = [
    "V1StrategyAdapter",
    "V1StrategyWrapper",
]
