"""
Feature Contracts - 特征接口定义

定义所有 Feature 必须遵循的协议
"""

from typing import Protocol, runtime_checkable
import pandas as pd
from abc import ABC, abstractmethod


@runtime_checkable
class Feature(Protocol):
    """特征接口协议"""

    @property
    def name(self) -> str:
        """特征名称"""
        ...

    @property
    def description(self) -> str:
        """特征描述"""
        ...

    @property
    def category(self) -> str:
        """特征类别: technical, market, microstructure, regime"""
        ...

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """
        计算特征

        Args:
            df: 包含基础数据的 DataFrame

        Returns:
            计算后的特征 Series
        """
        ...


class BaseFeature(ABC):
    """特征基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """特征名称"""
        pass

    @property
    def description(self) -> str:
        """特征描述，默认返回名称"""
        return self.name

    @property
    @abstractmethod
    def category(self) -> str:
        """特征类别"""
        pass

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算特征"""
        pass


class TechnicalFeature(BaseFeature):
    """技术指标基类"""
    category = "technical"


class MarketFeature(BaseFeature):
    """市场数据特征基类"""
    category = "market"


class MicrostructureFeature(BaseFeature):
    """微观结构特征基类"""
    category = "microstructure"


class RegimeFeature(BaseFeature):
    """市场状态特征基类"""
    category = "regime"


class CompositeFeature(BaseFeature):
    """复合特征基类 - 由多个基础特征组合"""

    @property
    @abstractmethod
    def dependencies(self) -> list[str]:
        """依赖的特征列表"""
        pass

    @property
    def category(self) -> str:
        return "composite"
