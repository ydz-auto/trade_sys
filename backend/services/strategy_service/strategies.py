"""
策略模块 - 实现各种交易策略
"""

from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("strategy_service")


class StrategyType(str, Enum):
    """策略类型"""
    TECHNICAL = "technical"
    EVENT_DRIVEN = "event_driven"
    MULTI_FACTOR = "multi_factor"
    ML_BASED = "ml_based"


class ActionType(str, Enum):
    """动作类型"""
    LONG = "long"
    SHORT = "short"
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class StrategySignal:
    """策略信号"""
    strategy_id: str
    strategy_type: StrategyType
    symbol: str
    action: ActionType
    quantity: float
    price: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class BaseStrategy:
    """策略基类"""
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self._enabled = True
    
    def enable(self):
        """启用策略"""
        self._enabled = True
    
    def disable(self):
        """禁用策略"""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """
        策略核心逻辑
        
        Args:
            data: 市场数据
            
        Returns:
            StrategySignal 或 None
        """
        raise NotImplementedError


class RSIStrategy(BaseStrategy):
    """
    RSI 策略
    
    RSI < 30: 超卖 -> 买入信号
    RSI > 70: 超买 -> 卖出信号
    """
    
    def __init__(
        self,
        strategy_id: str = "rsi_strategy",
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.default_quantity = default_quantity
        
        self._rsi_prev = None
    
    def calculate_rsi(self, prices: List[float]) -> float:
        """计算 RSI"""
        if len(prices) < self.period + 1:
            return 50.0
        
        # 计算价格变化
        deltas = np.diff(prices)
        
        # 分离涨跌
        gains = deltas.copy()
        gains[gains < 0] = 0
        
        losses = -deltas.copy()
        losses[losses < 0] = 0
        
        # 计算平均涨跌
        avg_gain = np.mean(gains[-self.period:])
        avg_loss = np.mean(losses[-self.period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        # 获取价格数据
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < self.period + 1:
            return None
        
        # 获取当前价格
        current_price = close_prices[-1]
        symbol = data.get("symbol", "BTCUSDT")
        
        # 计算 RSI
        rsi = self.calculate_rsi(close_prices)
        
        # 生成信号
        if self._rsi_prev is None:
            self._rsi_prev = rsi
            return None
        
        # RSI 策略
        signal = None
        
        if rsi <= self.oversold and self._rsi_prev > self.oversold:
            # RSI 从上方穿过 30，超卖 -> 买入
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (self.oversold - rsi) / (self.oversold / 2)),
                reason=f"RSI 超卖: {rsi:.2f} < {self.oversold}",
                metadata={"rsi": rsi, "prev_rsi": self._rsi_prev},
            )
        elif rsi >= self.overbought and self._rsi_prev < self.overbought:
            # RSI 从下方穿过 70，超买 -> 卖出
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (rsi - self.overbought) / ((100 - self.overbought) / 2)),
                reason=f"RSI 超买: {rsi:.2f} > {self.overbought}",
                metadata={"rsi": rsi, "prev_rsi": self._rsi_prev},
            )
        
        # 更新上一个 RSI
        self._rsi_prev = rsi
        
        return signal


class MACDStrategy(BaseStrategy):
    """
    MACD 策略
    
    MACD 线从上穿信号线 -> 买入信号
    MACD 线从下穿信号线 -> 卖出信号
    """
    
    def __init__(
        self,
        strategy_id: str = "macd_strategy",
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.default_quantity = default_quantity
        
        self._macd_prev = None
        self._signal_prev = None
    
    def calculate_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """
        计算 MACD
        
        Returns:
            (MACD 线, 信号线, 柱状图)
        """
        if len(prices) < self.slow_period + self.signal_period:
            return 0.0, 0.0, 0.0
        
        # 计算 EMA
        prices_np = np.array(prices)
        
        ema_fast = self._calculate_ema(prices_np, self.fast_period)
        ema_slow = self._calculate_ema(prices_np, self.slow_period)
        
        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, self.signal_period)
        histogram = macd_line - signal_line
        
        return macd_line[-1], signal_line[-1], histogram[-1]
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """计算 EMA"""
        k = 2 / (period + 1)
        
        ema = np.zeros_like(prices)
        ema[period - 1] = np.mean(prices[:period])
        
        for i in range(period, len(prices)):
            ema[i] = ema[i - 1] * (1 - k) + prices[i] * k
        
        return ema
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < self.slow_period + self.signal_period:
            return None
        
        current_price = close_prices[-1]
        symbol = data.get("symbol", "BTCUSDT")
        
        # 计算 MACD
        macd_line, signal_line, histogram = self.calculate_macd(close_prices)
        
        # 生成信号
        signal = None
        
        if (self._macd_prev is not None and 
            self._signal_prev is not None):
            # 金叉：MACD 从下穿过信号线
            if (self._macd_prev <= self._signal_prev and 
                macd_line > signal_line):
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.7,
                    reason=f"MACD 金叉: {macd_line:.4f} > {signal_line:.4f}",
                    metadata={"macd": macd_line, "signal": signal_line, "histogram": histogram},
                )
            
            # 死叉：MACD 从上穿过信号线
            elif (self._macd_prev >= self._signal_prev and 
                  macd_line < signal_line):
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.7,
                    reason=f"MACD 死叉: {macd_line:.4f} < {signal_line:.4f}",
                    metadata={"macd": macd_line, "signal": signal_line, "histogram": histogram},
                )
        
        # 更新上一个值
        self._macd_prev = macd_line
        self._signal_prev = signal_line
        
        return signal


class MultiStrategyOrchestrator:
    """
    多策略编排器
    
    同时运行多个策略，合并信号
    """
    
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._symbol_data: Dict[str, Dict] = {}
        logger.info("MultiStrategyOrchestrator initialized")
    
    def add_strategy(self, strategy: BaseStrategy):
        """添加策略"""
        self._strategies[strategy.strategy_id] = strategy
        logger.info(f"Strategy added: {strategy.strategy_id}")
    
    def remove_strategy(self, strategy_id: str):
        """移除策略"""
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            logger.info(f"Strategy removed: {strategy_id}")
    
    def update_market_data(self, symbol: str, data: Dict):
        """更新市场数据"""
        self._symbol_data[symbol] = data
    
    def process(self) -> List[StrategySignal]:
        """
        运行所有策略
        
        Returns:
            策略信号列表
        """
        all_signals = []
        
        for strategy in self._strategies.values():
            if not strategy.is_enabled:
                continue
            
            for symbol, data in self._symbol_data.items():
                signal = strategy.calculate(data)
                if signal:
                    all_signals.append(signal)
        
        logger.debug(f"Generated {len(all_signals)} signals from {len(self._strategies)} strategies")
        return all_signals


# 策略工厂
def create_default_strategies() -> MultiStrategyOrchestrator:
    """创建默认策略集合"""
    orchestrator = MultiStrategyOrchestrator()
    
    # RSI 策略
    rsi_strategy = RSIStrategy(
        strategy_id="rsi_14",
        period=14,
        oversold=30,
        overbought=70,
    )
    orchestrator.add_strategy(rsi_strategy)
    
    # MACD 策略
    macd_strategy = MACDStrategy(
        strategy_id="macd_12_26_9",
    )
    orchestrator.add_strategy(macd_strategy)
    
    logger.info("Default strategies created: RSI and MACD")
    return orchestrator
