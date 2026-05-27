"""
Strategy Registry - 策略注册表

核心职责：
1. 管理所有 V2 策略的注册
2. 提供策略查询和实例化功能
3. 维护策略元数据索引
"""

from typing import Dict, Type, List, Optional
from importlib import import_module

from .base import StrategyV2
from .metadata import StrategyMeta


class StrategyRegistry:
    """
    策略注册表
    
    设计原则：
    1. 单例模式，全局唯一
    2. 支持动态注册和查询
    3. 提供按标签、时间周期等维度的查询
    """
    
    _instance = None
    _strategies: Dict[str, Type[StrategyV2]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._strategies = {}
        return cls._instance
    
    @classmethod
    def register(cls, strategy_class: Type[StrategyV2]) -> None:
        """
        注册策略类
        
        Args:
            strategy_class: 策略类（必须继承 StrategyV2）
        
        Raises:
            ValueError: 如果策略类没有定义 meta 属性
        """
        if not issubclass(strategy_class, StrategyV2):
            raise ValueError("策略类必须继承 StrategyV2")
        
        if not hasattr(strategy_class, 'meta') or not isinstance(strategy_class.meta, StrategyMeta):
            raise ValueError(f"策略类 {strategy_class.__name__} 必须定义 meta 属性")
        
        strategy_id = strategy_class.meta.id
        cls._strategies[strategy_id] = strategy_class
    
    @classmethod
    def get_strategy(cls, strategy_id: str) -> Optional[Type[StrategyV2]]:
        """
        获取策略类
        
        Args:
            strategy_id: 策略 ID
        
        Returns:
            策略类，如果不存在返回 None
        """
        return cls._strategies.get(strategy_id)
    
    @classmethod
    def create_instance(cls, strategy_id: str, symbol: str) -> Optional[StrategyV2]:
        """
        创建策略实例
        
        Args:
            strategy_id: 策略 ID
            symbol: 交易对
        
        Returns:
            策略实例，如果不存在返回 None
        """
        strategy_class = cls.get_strategy(strategy_id)
        if strategy_class:
            return strategy_class(symbol)
        return None
    
    @classmethod
    def list_all(cls) -> List[StrategyMeta]:
        """
        获取所有策略的元数据列表
        
        Returns:
            策略元数据列表
        """
        return [strategy.meta for strategy in cls._strategies.values()]
    
    @classmethod
    def list_by_tag(cls, tag: str) -> List[StrategyMeta]:
        """
        按标签过滤策略
        
        Args:
            tag: 标签名称
        
        Returns:
            匹配的策略元数据列表
        """
        return [
            strategy.meta for strategy in cls._strategies.values()
            if tag in strategy.meta.tags
        ]
    
    @classmethod
    def list_by_timeframe(cls, timeframe: str) -> List[StrategyMeta]:
        """
        按时间周期过滤策略
        
        Args:
            timeframe: 时间周期
        
        Returns:
            匹配的策略元数据列表
        """
        return [
            strategy.meta for strategy in cls._strategies.values()
            if timeframe in strategy.meta.all_timeframes
        ]
    
    @classmethod
    def get_required_features(cls, strategy_ids: List[str]) -> List[str]:
        """
        获取多个策略所需的所有原料特征
        
        Args:
            strategy_ids: 策略 ID 列表
        
        Returns:
            去重后的特征列表
        """
        features = set()
        for strategy_id in strategy_ids:
            strategy_class = cls.get_strategy(strategy_id)
            if strategy_class:
                features.update(strategy_class(symbol="").get_required_features())
        return list(features)
    
    @classmethod
    def load_strategies(cls, module_path: str = "engines.compute.strategy_v2.strategies") -> None:
        """
        动态加载策略模块
        
        Args:
            module_path: 策略模块路径
        """
        try:
            module = import_module(module_path)
            # 导入会自动触发注册
        except ImportError as e:
            raise RuntimeError(f"加载策略模块失败: {e}")


def register_strategy(strategy_class: Type[StrategyV2]) -> Type[StrategyV2]:
    """
    装饰器：注册策略类
    
    Usage:
        @register_strategy
        class MyStrategy(StrategyV2):
            meta = StrategyMeta(...)
    """
    StrategyRegistry.register(strategy_class)
    return strategy_class


__all__ = [
    "StrategyRegistry",
    "register_strategy",
]
