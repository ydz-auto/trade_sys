"""
Trade Pressure Event Detector
交易压力事件检测器

专门用于检测市场微观结构中的交易压力事件，包括：
- 压力积聚 (Pressure Buildup)
- 压力释放/洗牌 (Pressure Flush)
- 压力耗尽 (Pressure Exhaustion)
- 压力吸收 (Pressure Absorption)
- 压力背离 (Pressure Divergence)
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from domain.event.event_type import EventType

logger = logging.getLogger(__name__)


class TradePressureSignal(str, Enum):
    """交易压力信号类型"""
    NONE = "none"
    BULLISH_FLUSH = "bullish_flush"
    BEARISH_FLUSH = "bearish_flush"
    BULLISH_EXHAUSTION = "bullish_exhaustion"
    BEARISH_EXHAUSTION = "bearish_exhaustion"
    ABSORPTION = "absorption"
    DIVERGENCE = "divergence"
    SQUEEZE = "squeeze"


@dataclass
class TradePressureEvent:
    """交易压力事件"""
    timestamp: datetime
    symbol: str
    
    # 事件类型
    event_type: Optional[EventType]
    signal_type: TradePressureSignal
    
    # 指标值
    pressure_score: float
    buy_sell_imbalance: float
    volume_spike_ratio: float
    price_movement: float
    volatility_spike: float
    
    # 信心度
    confidence: float
    
    # 方向
    direction: int  # 1 = bullish, -1 = bearish, 0 = neutral
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class TradePressureDetector:
    """
    交易压力事件检测器
    
    核心功能：
    - 检测压力积聚和释放
    - 检测市场耗尽
    - 检测流动性吸收
    - 检测压力和价格背离
    """
    
    def __init__(
        self,
        lookback_periods: int = 60,
        volume_spike_threshold: float = 2.0,
        pressure_threshold: float = 0.7,
        divergence_threshold: float = 0.5,
    ):
        self.lookback_periods = lookback_periods
        self.volume_spike_threshold = volume_spike_threshold
        self.pressure_threshold = pressure_threshold
        self.divergence_threshold = divergence_threshold
        
        # 历史数据缓存
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        self._buy_imbalance_history: Dict[str, List[float]] = {}
        
        logger.info("TradePressureDetector initialized")
    
    def detect(
        self,
        current_price: float,
        volume: float,
        buy_volume: float,
        sell_volume: float,
        orderbook_imbalance: float,
        price_change_5min: float,
        price_change_15min: float,
        symbol: str,
        timestamp: Optional[datetime] = None,
    ) -> TradePressureEvent:
        """
        检测交易压力事件
        
        Args:
            current_price: 当前价格
            volume: 交易量
            buy_volume: 主动买入量
            sell_volume: 主动卖出量
            orderbook_imbalance: 订单簿不平衡
            price_change_5min: 5分钟价格变化率
            price_change_15min: 15分钟价格变化率
            symbol: 交易对
            timestamp: 时间戳
        
        Returns:
            TradePressureEvent
        """
        timestamp = timestamp or datetime.utcnow()
        
        # 更新历史数据
        self._update_history(symbol, current_price, volume, buy_volume, sell_volume)
        
        # 计算各项指标
        buy_sell_imbalance = self._calculate_buy_sell_imbalance(buy_volume, sell_volume)
        volume_spike_ratio = self._calculate_volume_spike_ratio(symbol, volume)
        volatility_spike = self._calculate_volatility_spike(symbol)
        
        # 检测各类事件
        flush_event = self._detect_flush(
            price_change_5min,
            volume_spike_ratio,
            buy_sell_imbalance,
        )
        exhaustion_event = self._detect_exhaustion(
            price_change_15min,
            buy_sell_imbalance,
            volatility_spike,
            symbol,
        )
        absorption_event = self._detect_absorption(
            price_change_5min,
            volume_spike_ratio,
            buy_sell_imbalance,
            orderbook_imbalance,
        )
        divergence_event = self._detect_divergence(
            price_change_15min,
            buy_sell_imbalance,
            symbol,
        )
        squeeze_event = self._detect_squeeze(
            orderbook_imbalance,
            volatility_spike,
            volume_spike_ratio,
        )
        
        # 确定主导事件和信心度
        event_type, signal_type, pressure_score, direction = self._determine_dominant_event(
            flush_event,
            exhaustion_event,
            absorption_event,
            divergence_event,
            squeeze_event,
        )
        
        confidence = self._calculate_confidence(
            pressure_score,
            volume_spike_ratio,
            volatility_spike,
        )
        
        return TradePressureEvent(
            timestamp=timestamp,
            symbol=symbol,
            event_type=event_type,
            signal_type=signal_type,
            pressure_score=pressure_score,
            buy_sell_imbalance=buy_sell_imbalance,
            volume_spike_ratio=volume_spike_ratio,
            price_movement=price_change_5min,
            volatility_spike=volatility_spike,
            confidence=confidence,
            direction=direction,
        )
    
    def _update_history(
        self,
        symbol: str,
        price: float,
        volume: float,
        buy_volume: float,
        sell_volume: float,
    ) -> None:
        """更新历史数据"""
        if symbol not in self._price_history:
            self._price_history[symbol] = []
            self._volume_history[symbol] = []
            self._buy_imbalance_history[symbol] = []
        
        # 计算买卖不平衡
        total = buy_volume + sell_volume
        imbalance = (buy_volume - sell_volume) / total if total > 0 else 0.0
        
        # 添加历史数据
        self._price_history[symbol].append(price)
        self._volume_history[symbol].append(volume)
        self._buy_imbalance_history[symbol].append(imbalance)
        
        # 限制历史长度
        if len(self._price_history[symbol]) > self.lookback_periods * 2:
            self._price_history[symbol] = self._price_history[symbol][-self.lookback_periods * 2:]
            self._volume_history[symbol] = self._volume_history[symbol][-self.lookback_periods * 2:]
            self._buy_imbalance_history[symbol] = self._buy_imbalance_history[symbol][-self.lookback_periods * 2:]
    
    def _calculate_buy_sell_imbalance(
        self,
        buy_volume: float,
        sell_volume: float,
    ) -> float:
        """计算买卖不平衡"""
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        return (buy_volume - sell_volume) / total
    
    def _calculate_volume_spike_ratio(
        self,
        symbol: str,
        current_volume: float,
    ) -> float:
        """计算交易量爆发比率"""
        history = self._volume_history.get(symbol, [])
        if len(history) < 5:
            return 1.0
        
        avg_volume = sum(history[-20:-1]) / 19  # 过去20期的平均（不含当前）
        if avg_volume == 0:
            return 1.0
        
        return current_volume / avg_volume
    
    def _calculate_volatility_spike(self, symbol: str) -> float:
        """计算波动率爆发"""
        history = self._price_history.get(symbol, [])
        if len(history) < 10:
            return 0.0
        
        # 计算最近的价格波动
        recent_prices = history[-20:]
        recent_volatility = max(recent_prices) / min(recent_prices) - 1.0
        
        # 计算历史波动率
        older_prices = history[-40:-20]
        if len(older_prices) < 10:
            return 1.0
        historical_volatility = max(older_prices) / min(older_prices) - 1.0
        
        if historical_volatility == 0:
            return 1.0
        
        return recent_volatility / historical_volatility
    
    def _detect_flush(
        self,
        price_change: float,
        volume_spike: float,
        imbalance: float,
    ) -> Optional[tuple]:
        """检测压力释放/洗牌事件"""
        # 看跌释放：价格下跌 + 大量卖出 + 成交量爆发
        if (
            price_change < -0.02
            and imbalance < -0.3
            and volume_spike > self.volume_spike_threshold
        ):
            return (EventType.TRADE_PRESSURE_FLUSH, TradePressureSignal.BEARISH_FLUSH, 0.8, -1)
        
        # 看涨释放：价格上涨 + 大量买入 + 成交量爆发
        if (
            price_change > 0.02
            and imbalance > 0.3
            and volume_spike > self.volume_spike_threshold
        ):
            return (EventType.TRADE_PRESSURE_FLUSH, TradePressureSignal.BULLISH_FLUSH, 0.8, 1)
        
        return None
    
    def _detect_exhaustion(
        self,
        price_change: float,
        imbalance: float,
        volatility_spike: float,
        symbol: str,
    ) -> Optional[tuple]:
        """检测压力耗尽事件"""
        # 看跌耗尽：价格继续下跌，但买卖不平衡开始转向买入
        if (
            price_change < -0.01
            and imbalance > 0.1
            and volatility_spike > 1.5
        ):
            return (EventType.TRADE_PRESSURE_EXHAUSTION, TradePressureSignal.BULLISH_EXHAUSTION, 0.7, 1)
        
        # 看涨耗尽：价格继续上涨，但买卖不平衡开始转向卖出
        if (
            price_change > 0.01
            and imbalance < -0.1
            and volatility_spike > 1.5
        ):
            return (EventType.TRADE_PRESSURE_EXHAUSTION, TradePressureSignal.BEARISH_EXHAUSTION, 0.7, -1)
        
        return None
    
    def _detect_absorption(
        self,
        price_change: float,
        volume_spike: float,
        imbalance: float,
        orderbook_imbalance: float,
    ) -> Optional[tuple]:
        """检测压力吸收事件"""
        # 特征：价格变动小 + 成交量大 + 订单簿不平衡
        if (
            abs(price_change) < 0.005
            and volume_spike > self.volume_spike_threshold
            and abs(orderbook_imbalance) > 0.3
        ):
            return (EventType.TRADE_PRESSURE_ABSORPTION, TradePressureSignal.ABSORPTION, 0.6, 0)
        
        return None
    
    def _detect_divergence(
        self,
        price_change: float,
        imbalance: float,
        symbol: str,
    ) -> Optional[tuple]:
        """检测压力背离事件"""
        history = self._buy_imbalance_history.get(symbol, [])
        if len(history) < 10:
            return None
        
        # 价格和压力背离
        avg_imbalance_recent = sum(history[-5:]) / 5
        avg_imbalance_old = sum(history[-15:-5]) / 10
        
        # 价格下跌，但压力转向买入
        if price_change < -0.01 and avg_imbalance_recent > avg_imbalance_old + 0.2:
            return (EventType.TRADE_PRESSURE_DIVERGENCE, TradePressureSignal.DIVERGENCE, 0.6, 1)
        
        # 价格上涨，但压力转向卖出
        if price_change > 0.01 and avg_imbalance_recent < avg_imbalance_old - 0.2:
            return (EventType.TRADE_PRESSURE_DIVERGENCE, TradePressureSignal.DIVERGENCE, 0.6, -1)
        
        return None
    
    def _detect_squeeze(
        self,
        orderbook_imbalance: float,
        volatility_spike: float,
        volume_spike: float,
    ) -> Optional[tuple]:
        """检测挤压事件"""
        if (
            abs(orderbook_imbalance) > 0.4
            and volatility_spike > 1.5
            and volume_spike > self.volume_spike_threshold * 0.8
        ):
            return (EventType.TRADE_PRESSURE_SQUEEZE, TradePressureSignal.SQUEEZE, 0.7, 0)
        
        return None
    
    def _determine_dominant_event(
        self,
        *events: Optional[tuple],
    ) -> tuple:
        """确定主导事件"""
        valid_events = [e for e in events if e is not None]
        if not valid_events:
            return None, TradePressureSignal.NONE, 0.0, 0
        
        # 按分数排序，取最高的
        valid_events.sort(key=lambda x: x[2], reverse=True)
        return valid_events[0]
    
    def _calculate_confidence(
        self,
        pressure_score: float,
        volume_spike: float,
        volatility_spike: float,
    ) -> float:
        """计算信心度"""
        base = 0.3
        
        # 压力分数
        base += pressure_score * 0.4
        
        # 成交量确认
        if volume_spike > self.volume_spike_threshold:
            base += 0.2
        elif volume_spike > self.volume_spike_threshold * 0.8:
            base += 0.1
        
        # 波动率确认
        if volatility_spike > 2.0:
            base += 0.1
        
        return min(1.0, base)
    
    def reset(self, symbol: Optional[str] = None) -> None:
        """重置检测器状态"""
        if symbol is not None:
            self._price_history.pop(symbol, None)
            self._volume_history.pop(symbol, None)
            self._buy_imbalance_history.pop(symbol, None)
        else:
            self._price_history.clear()
            self._volume_history.clear()
            self._buy_imbalance_history.clear()
