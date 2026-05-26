"""
Regime Detection - 市场状态检测（最核心模块！）⭐⭐⭐⭐⭐

检测当前市场处于什么状态：
1. Trend Regime - 趋势市场
2. Chop Regime - 震荡市场
3. Panic Regime - 恐慌市场
4. Squeeze Regime - 挤压市场
5. Illiquid Regime - 低流动性市场
6. High Leverage Regime - 高杠杆市场
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

import logging

logger = logging.getLogger(__name__)


class RegimeType(str, Enum):
    """市场状态类型"""
    TREND = "trend"
    CHOP = "chop"
    PANIC = "panic"
    SQUEEZE = "squeeze"
    ILLIQUID = "illiquid"
    HIGH_LEVERAGE = "high_leverage"
    NEUTRAL = "neutral"


@dataclass
class RegimeSignal:
    """单个状态信号"""
    regime: RegimeType
    active: bool
    strength: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegimeAnalysis:
    """完整的状态分析结果"""
    timestamp: datetime
    symbol: str
    
    # 各个状态的信号
    trend: RegimeSignal
    chop: RegimeSignal
    panic: RegimeSignal
    squeeze: RegimeSignal
    illiquid: RegimeSignal
    high_leverage: RegimeSignal
    
    # 主状态
    primary_regime: RegimeType
    secondary_regime: Optional[RegimeType] = None
    
    # 风险建议
    risk_level: float  # 0.0 (低) - 1.0 (高)
    position_sizing_multiplier: float  # 0.0 - 1.0
    
    # 策略建议
    recommended_strategies: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class RegimeDetector:
    """
    市场状态检测器 - 这是Alpha Engine的心脏！
    
    设计思路：
    - 每个状态独立检测
    - 每个状态有自己的特征阈值
    - 综合评分确定主状态
    - 根据状态动态调整策略权重
    """
    
    def __init__(
        self,
        lookback_periods: int = 100,
        trend_threshold: float = 0.3,
        chop_threshold: float = 0.4,
        panic_threshold: float = 0.4,
        squeeze_threshold: float = 0.35,
        illiquid_threshold: float = 0.5,
        leverage_threshold: float = 0.3,
    ):
        self._lookback_periods = lookback_periods
        
        # 阈值设置
        self._trend_threshold = trend_threshold
        self._chop_threshold = chop_threshold
        self._panic_threshold = panic_threshold
        self._squeeze_threshold = squeeze_threshold
        self._illiquid_threshold = illiquid_threshold
        self._leverage_threshold = leverage_threshold
        
        # 历史数据存储
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        
        logger.info("RegimeDetector initialized")
    
    def detect(
        self,
        symbol: str,
        current_price: float,
        close_prices: List[float],
        volumes: Optional[List[float]] = None,
        funding_zscore: float = 0.0,
        oi_zscore: float = 0.0,
        liquidation_spike: float = 0.0,
        spread: float = 0.0,
        depth_ratio: float = 1.0,
        volatility_1h: float = 0.0,
        adx: Optional[float] = None,
    ) -> RegimeAnalysis:
        """
        主检测函数
        
        Args:
            symbol: 交易对
            current_price: 当前价格
            close_prices: K线收盘价序列
            volumes: 成交量序列（可选）
            funding_zscore: 资金费率Z值
            oi_zscore: 持仓量Z值
            liquidation_spike: 爆仓尖峰
            spread: 买卖价差
            depth_ratio: 深度比
            volatility_1h: 1小时波动率
            adx: ADX指标（可选，用于趋势检测）
            
        Returns:
            RegimeAnalysis: 完整的状态分析
        """
        timestamp = datetime.now()
        
        # 更新历史数据
        self._update_history(symbol, current_price, volumes[-1] if volumes else 0.0)
        
        # 检测各个状态
        trend_signal = self._detect_trend_regime(
            close_prices, volatility_1h, adx
        )
        
        chop_signal = self._detect_chop_regime(
            close_prices, volatility_1h
        )
        
        panic_signal = self._detect_panic_regime(
            liquidation_spike, close_prices, volatility_1h
        )
        
        squeeze_signal = self._detect_squeeze_regime(
            funding_zscore, oi_zscore, close_prices
        )
        
        illiquid_signal = self._detect_illiquid_regime(
            spread, depth_ratio, volumes
        )
        
        high_leverage_signal = self._detect_high_leverage_regime(
            oi_zscore, funding_zscore
        )
        
        # 确定主状态和次状态
        primary, secondary = self._determine_primary_regime(
            trend_signal, chop_signal, panic_signal, squeeze_signal, 
            illiquid_signal, high_leverage_signal
        )
        
        # 计算风险等级
        risk_level = self._calculate_risk_level(
            primary, panic_signal, squeeze_signal, high_leverage_signal
        )
        
        # 计算仓位大小调整系数
        position_sizing = self._calculate_position_sizing(
            primary, risk_level, illiquid_signal
        )
        
        # 推荐策略
        recommended_strategies = self._recommend_strategies(
            primary, secondary
        )
        
        return RegimeAnalysis(
            timestamp=timestamp,
            symbol=symbol,
            trend=trend_signal,
            chop=chop_signal,
            panic=panic_signal,
            squeeze=squeeze_signal,
            illiquid=illiquid_signal,
            high_leverage=high_leverage_signal,
            primary_regime=primary,
            secondary_regime=secondary,
            risk_level=risk_level,
            position_sizing_multiplier=position_sizing,
            recommended_strategies=recommended_strategies,
            metadata={
                "volatility_1h": volatility_1h,
                "funding_zscore": funding_zscore,
                "oi_zscore": oi_zscore,
                "liquidation_spike": liquidation_spike,
                "spread": spread,
            }
        )
    
    def _update_history(self, symbol: str, price: float, volume: float) -> None:
        """更新历史数据"""
        if symbol not in self._price_history:
            self._price_history[symbol] = []
            self._volume_history[symbol] = []
        
        self._price_history[symbol].append(price)
        self._volume_history[symbol].append(volume)
        
        if len(self._price_history[symbol]) > self._lookback_periods:
            self._price_history[symbol] = self._price_history[symbol][-self._lookback_periods:]
            self._volume_history[symbol] = self._volume_history[symbol][-self._lookback_periods:]
    
    def _detect_trend_regime(
        self,
        close_prices: List[float],
        volatility: float,
        adx: Optional[float] = None,
    ) -> RegimeSignal:
        """
        检测趋势市场
        
        特征：
        - ADX > 25 (如果有ADX)
        - 价格持续向一个方向移动
        - 波动率适中（不是极端波动）
        """
        if len(close_prices) < 20:
            return RegimeSignal(
                regime=RegimeType.TREND,
                active=False,
                strength=0.0,
                confidence=0.0
            )
        
        strength = 0.0
        confidence = 0.0
        
        # 计算收益率序列
        returns = np.diff(np.log(close_prices))
        
        # 计算趋势强度：正收益比例
        recent_returns = returns[-20:]
        positive_ratio = sum(1 for r in recent_returns if r > 0) / len(recent_returns)
        negative_ratio = sum(1 for r in recent_returns if r < 0) / len(recent_returns)
        max_side_ratio = max(positive_ratio, negative_ratio)
        
        # 趋势