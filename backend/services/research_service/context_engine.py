#!/usr/bin/env python3
"""
Step 3: Context Engine - 市场上下文标注

功能：
- 给事件打Context标签
- 让同类事件在不同市场环境下可区分
- 保证Event Study的有效性

Context标签：
- funding_high / funding_low
- oi_up / oi_down
- volatility_high / volatility_low
- session (US / Asia / Europe)
- regime (trending / ranging / volatile)
- weekend / weekday
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("context_engine")


class FundingContext(str, Enum):
    HIGH = "funding_high"
    LOW = "funding_low"
    NEUTRAL = "funding_neutral"


class OIContext(str, Enum):
    INCREASING = "oi_up"
    DECREASING = "oi_down"
    STABLE = "oi_stable"


class VolatilityContext(str, Enum):
    HIGH = "volatility_high"
    LOW = "volatility_low"
    NORMAL = "volatility_normal"


class SessionContext(str, Enum):
    ASIA = "session_asia"      # 00:00 - 08:00 UTC
    EUROPE = "session_europe"   # 08:00 - 16:00 UTC
    US = "session_us"           # 16:00 - 00:00 UTC


class RegimeContext(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"


@dataclass
class ContextTags:
    """上下文标签集合"""
    funding: str
    oi: str
    volatility: str
    session: str
    regime: str
    is_weekend: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "funding": self.funding,
            "oi": self.oi,
            "volatility": self.volatility,
            "session": self.session,
            "regime": self.regime,
            "is_weekend": self.is_weekend,
        }


@dataclass
class ContextThresholds:
    """Context阈值配置"""
    funding_high: float = 0.0003
    funding_low: float = -0.0003
    
    oi_change_high: float = 0.02
    oi_change_low: float = -0.02
    
    volatility_quantile_high: float = 0.8
    volatility_quantile_low: float = 0.2
    
    trend_threshold: float = 0.005
    
    volume_ratio_weekend_max: float = 0.7


class ContextEngine:
    """
    Context Engine - 市场上下文标注引擎
    
    功能：
    1. 基于Feature Matrix计算当前市场Context
    2. 给事件打Context标签
    3. 支持Context过滤和分组
    """
    
    def __init__(self, thresholds: Optional[ContextThresholds] = None):
        self.thresholds = thresholds or ContextThresholds()
        logger.info("ContextEngine initialized")
    
    def add_context_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        给DataFrame添加Context列
        
        Args:
            df: 包含timestamp, funding_rate, open_interest等列
            
        Returns:
            添加了context列的DataFrame
        """
        df = df.copy()
        
        df["session"] = df["timestamp"].dt.hour.apply(self._get_session)
        df["is_weekend"] = df["timestamp"].dt.dayofweek >= 5
        
        df["funding_context"] = self._get_funding_context(df)
        
        if "oi_change_1h" in df.columns:
            df["oi_context"] = self._get_oi_context(df)
        
        if "volatility_1h" in df.columns:
            df["volatility_context"] = self._get_volatility_context(df)
        
        if "returns_1h" in df.columns:
            df["regime"] = self._get_regime(df)
        
        df["context_tags"] = df.apply(self._create_context_tags, axis=1)
        
        return df
    
    def _get_session(self, hour: int) -> str:
        """根据小时获取会话"""
        if 0 <= hour < 8:
            return SessionContext.ASIA.value
        elif 8 <= hour < 16:
            return SessionContext.EUROPE.value
        else:
            return SessionContext.US.value
    
    def _get_funding_context(self, df: pd.DataFrame) -> pd.Series:
        """根据资金费率获取Context"""
        funding = df.get("funding_rate", pd.Series([0]*len(df)))
        
        conditions = [
            funding > self.thresholds.funding_high,
            funding < self.thresholds.funding_low,
        ]
        choices = [
            FundingContext.HIGH.value,
            FundingContext.LOW.value,
        ]
        
        return np.select(conditions, choices, default=FundingContext.NEUTRAL.value)
    
    def _get_oi_context(self, df: pd.DataFrame) -> pd.Series:
        """根据OI变化获取Context"""
        oi_change = df.get("oi_change_1h", pd.Series([0]*len(df)))
        
        conditions = [
            oi_change > self.thresholds.oi_change_high,
            oi_change < self.thresholds.oi_change_low,
        ]
        choices = [
            OIContext.INCREASING.value,
            OIContext.DECREASING.value,
        ]
        
        return np.select(conditions, choices, default=OIContext.STABLE.value)
    
    def _get_volatility_context(self, df: pd.DataFrame) -> pd.Series:
        """根据波动率获取Context"""
        vol = df.get("volatility_1h", pd.Series([0]*len(df)))
        
        q_high = vol.quantile(self.thresholds.volatility_quantile_high)
        q_low = vol.quantile(self.thresholds.volatility_quantile_low)
        
        conditions = [
            vol > q_high,
            vol < q_low,
        ]
        choices = [
            VolatilityContext.HIGH.value,
            VolatilityContext.LOW.value,
        ]
        
        return np.select(conditions, choices, default=VolatilityContext.NORMAL.value)
    
    def _get_regime(self, df: pd.DataFrame) -> pd.Series:
        """根据趋势获取市场状态"""
        returns_1h = df.get("returns_1h", pd.Series([0]*len(df)))
        volatility = df.get("volatility_1h", pd.Series([0]*len(df)))
        
        q_vol = volatility.quantile(0.8) if len(volatility) > 10 else 0
        
        conditions = [
            returns_1h > self.thresholds.trend_threshold,
            returns_1h < -self.thresholds.trend_threshold,
            volatility > q_vol,
        ]
        choices = [
            RegimeContext.TRENDING_UP.value,
            RegimeContext.TRENDING_DOWN.value,
            RegimeContext.VOLATILE.value,
        ]
        
        return np.select(conditions, choices, default=RegimeContext.RANGING.value)
    
    def _create_context_tags(self, row: pd.Series) -> str:
        """创建Context标签字符串"""
        tags = []
        
        if "funding_context" in row:
            tags.append(row["funding_context"])
        if "oi_context" in row:
            tags.append(row["oi_context"])
        if "volatility_context" in row:
            tags.append(row["volatility_context"])
        if "session" in row:
            tags.append(row["session"])
        if "regime" in row:
            tags.append(row["regime"])
        if row.get("is_weekend", False):
            tags.append("weekend")
        
        return "|".join(tags)
    
    def get_context_for_event(
        self, 
        timestamp: pd.Timestamp,
        df: pd.DataFrame
    ) -> ContextTags:
        """获取特定时间点的Context"""
        idx = df[df["timestamp"] <= timestamp].index
        
        if len(idx) == 0:
            return self._default_context()
        
        row = df.loc[idx[-1]]
        
        return ContextTags(
            funding=row.get("funding_context", FundingContext.NEUTRAL.value),
            oi=row.get("oi_context", OIContext.STABLE.value),
            volatility=row.get("volatility_context", VolatilityContext.NORMAL.value),
            session=row.get("session", SessionContext.ASIA.value),
            regime=row.get("regime", RegimeContext.RANGING.value),
            is_weekend=row.get("is_weekend", False),
        )
    
    def _default_context(self) -> ContextTags:
        """默认Context"""
        return ContextTags(
            funding=FundingContext.NEUTRAL.value,
            oi=OIContext.STABLE.value,
            volatility=VolatilityContext.NORMAL.value,
            session=SessionContext.ASIA.value,
            regime=RegimeContext.RANGING.value,
            is_weekend=False,
        )
    
    def filter_by_context(
        self, 
        df: pd.DataFrame, 
        context_filter: Dict[str, str]
    ) -> pd.DataFrame:
        """
        按Context过滤数据
        
        Args:
            df: 输入数据
            context_filter: 过滤条件，如 {"funding": "funding_high", "session": "session_us"}
        """
        result = df.copy()
        
        for key, value in context_filter.items():
            if key == "funding":
                result = result[result["funding_context"] == value]
            elif key == "oi":
                result = result[result["oi_context"] == value]
            elif key == "volatility":
                result = result[result["volatility_context"] == value]
            elif key == "session":
                result = result[result["session"] == value]
            elif key == "regime":
                result = result[result["regime"] == value]
            elif key == "is_weekend":
                result = result[result["is_weekend"] == value]
        
        return result
    
    def group_by_context(
        self, 
        df: pd.DataFrame, 
        group_cols: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """按Context分组"""
        result = {}
        
        for col in group_cols:
            if col in df.columns:
                for value in df[col].unique():
                    key = f"{col}_{value}"
                    result[key] = df[df[col] == value]
        
        return result
    
    def get_context_summary(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """获取Context分布统计"""
        summary = {}
        
        for col in ["funding_context", "oi_context", "volatility_context", "session", "regime", "is_weekend"]:
            if col in df.columns:
                counts = df[col].value_counts().to_dict()
                summary[col] = {
                    "total": len(df),
                    "distribution": counts,
                }
        
        return summary
