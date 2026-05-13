"""
额外的策略示例
"""

from typing import Optional, Dict, List
from datetime import datetime
import numpy as np
from services.strategy_service.strategies import BaseStrategy, StrategySignal, ActionType


class BollingerBandsStrategy(BaseStrategy):
    """
    布林带策略
    - 价格跌破下轨: 做多信号
    - 价格突破上轨: 做空信号
    """
    
    def __init__(
        self,
        strategy_id: str = "bollinger_bands",
        period: int = 20,
        std_dev: float = 2.0,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.period = period
        self.std_dev = std_dev
        self.default_quantity = default_quantity
        
        self._prev_upper = None
        self._prev_lower = None
        self._prev_close = None
    
    def calculate_bollinger_bands(self, close_prices: List[float]) -> Dict[str, float]:
        """计算布林带"""
        if len(close_prices) < self.period:
            return {
                "sma": np.mean(close_prices) if close_prices else 0,
                "upper": 0,
                "lower": 0,
            }
        
        recent_prices = close_prices[-self.period:]
        sma = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        return {
            "sma": sma,
            "upper": sma + self.std_dev * std,
            "lower": sma - self.std_dev * std,
        }
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self.is_enabled:
            return None
        
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < self.period + 1:
            return None
        
        current_price = close_prices[-1]
        symbol = data.get("symbol", "BTCUSDT")
        
        # 计算布林带
        bands = self.calculate_bollinger_bands(close_prices)
        
        signal = None
        
        # 检查买入条件（价格跌破下轨）
        if (self._prev_close is not None and self._prev_lower is not None):
            if self._prev_close >= self._prev_lower and current_price < bands["lower"]:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type="technical",
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.7,
                    reason=f"价格跌破布林带下轨: {current_price:.2f} < {bands['lower']:.2f}",
                    metadata={"sma": bands["sma"], "upper": bands["upper"], "lower": bands["lower"]},
                )
            # 检查卖出条件（价格突破上轨）
            elif self._prev_close <= self._prev_upper and current_price > bands["upper"]:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type="technical",
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.7,
                    reason=f"价格突破布林带上轨: {current_price:.2f} > {bands['upper']:.2f}",
                    metadata={"sma": bands["sma"], "upper": bands["upper"], "lower": bands["lower"]},
                )
        
        # 更新历史数据
        self._prev_upper = bands["upper"]
        self._prev_lower = bands["lower"]
        self._prev_close = current_price
        
        return signal


class MovingAverageCrossStrategy(BaseStrategy):
    """
    均线交叉策略
    - 金叉（短期上穿长期）: 做多信号
    - 死叉（短期下穿长期）: 做空信号
    """
    
    def __init__(
        self,
        strategy_id: str = "ma_cross",
        fast_period: int = 50,
        slow_period: int = 200,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.default_quantity = default_quantity
        
        self._prev_fast = None
        self._prev_slow = None
    
    def calculate_sma(self, prices: List[float], period: int) -> float:
        """计算简单移动平均"""
        if len(prices) < period:
            return np.mean(prices) if prices else 0
        return np.mean(prices[-period:])
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self.is_enabled:
            return None
        
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < max(self.fast_period, self.slow_period) + 1:
            return None
        
        current_price = close_prices[-1]
        symbol = data.get("symbol", "BTCUSDT")
        
        # 计算均线
        fast_ma = self.calculate_sma(close_prices, self.fast_period)
        slow_ma = self.calculate_sma(close_prices, self.slow_period)
        
        signal = None
        
        # 检查交叉
        if self._prev_fast is not None and self._prev_slow is not None:
            # 金叉（短期从下到上穿越长期）
            if self._prev_fast <= self._prev_slow and fast_ma > slow_ma:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type="technical",
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.75,
                    reason=f"均线金叉: {self.fast_period}MA({fast_ma:.2f}) > {self.slow_period}MA({slow_ma:.2f})",
                    metadata={"fast_ma": fast_ma, "slow_ma": slow_ma},
                )
            # 死叉（短期从上到下穿越长期）
            elif self._prev_fast >= self._prev_slow and fast_ma < slow_ma:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type="technical",
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.75,
                    reason=f"均线死叉: {self.fast_period}MA({fast_ma:.2f}) < {self.slow_period}MA({slow_ma:.2f})",
                    metadata={"fast_ma": fast_ma, "slow_ma": slow_ma},
                )
        
        # 更新历史数据
        self._prev_fast = fast_ma
        self._prev_slow = slow_ma
        
        return signal


class RSIMACDStrategy(BaseStrategy):
    """
    RSI + MACD 组合策略
    - RSI 超卖 + MACD 金叉: 做多信号
    - RSI 超买 + MACD 死叉: 做空信号
    """
    
    def __init__(
        self,
        strategy_id: str = "rsi_macd",
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.default_quantity = default_quantity
        
        self._prev_rsi = None
        self._prev_macd_line = None
        self._prev_signal_line = None
    
    def calculate_rsi(self, close_prices: List[float]) -> float:
        """计算 RSI"""
        if len(close_prices) < self.rsi_period + 1:
            return 50.0
        
        deltas = np.diff(close_prices[-(self.rsi_period + 1):])
        gains = deltas[deltas >= 0]
        losses = -deltas[deltas < 0]
        
        if len(gains) == 0:
            return 0.0
        if len(losses) == 0:
            return 100.0
        
        avg_gain = np.mean(gains[-self.rsi_period:]) if len(gains) >= self.rsi_period else np.mean(gains)
        avg_loss = np.mean(losses[-self.rsi_period:]) if len(losses) >= self.rsi_period else np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def calculate_macd(self, close_prices: List[float]) -> Dict[str, float]:
        """计算 MACD"""
        if len(close_prices) < self.macd_slow + self.macd_signal:
            return {"macd": 0, "signal": 0, "histogram": 0}
        
        prices_np = np.array(close_prices)
        
        # 计算 EMA
        def ema(data, period):
            k = 2 / (period + 1)
            ema_values = np.zeros_like(data)
            ema_values[0] = data[0]
            for i in range(1, len(data)):
                ema_values[i] = ema_values[i-1] * (1 - k) + data[i] * k
            return ema_values
        
        ema_fast = ema(prices_np, self.macd_fast)
        ema_slow = ema(prices_np, self.macd_slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, self.macd_signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line[-1],
            "signal": signal_line[-1],
            "histogram": histogram[-1],
        }
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self.is_enabled:
            return None
        
        close_prices = data.get("close_prices", [])
        min_required = max(self.rsi_period + 1, self.macd_slow + self.macd_signal) + 1
        if not close_prices or len(close_prices) < min_required:
            return None
        
        current_price = close_prices[-1]
        symbol = data.get("symbol", "BTCUSDT")
        
        # 计算指标
        rsi = self.calculate_rsi(close_prices)
        macd = self.calculate_macd(close_prices)
        
        signal = None
        
        # 组合信号条件
        if (self._prev_rsi is not None and 
            self._prev_macd_line is not None and 
            self._prev_signal_line is not None):
            
            # RSI 超卖 + MACD 金叉 = 买入信号
            if (self._prev_rsi <= self.rsi_oversold and 
                self._prev_macd_line <= self._prev_signal_line and
                macd["macd"] > macd["signal"]):
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type="technical",
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.85,
                    reason=f"组合买入信号: RSI({rsi:.1f})超卖 + MACD金叉",
                    metadata={"rsi": rsi, "macd": macd},
                )
            
            # RSI 超买 + MACD 死叉 = 卖出信号
            elif (self._prev_rsi >= self.rsi_overbought and 
                  self._prev_macd_line >= self._prev_signal_line and
                  macd["macd"] < macd["signal"]):
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type="technical",
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=0.85,
                    reason=f"组合卖出信号: RSI({rsi:.1f})超买 + MACD死叉",
                    metadata={"rsi": rsi, "macd": macd},
                )
        
        # 更新历史数据
        self._prev_rsi = rsi
        self._prev_macd_line = macd["macd"]
        self._prev_signal_line = macd["signal"]
        
        return signal


# 策略注册（在策略引擎中使用）
def register_all_strategies(orchestrator) -> None:
    """注册所有示例策略"""
    orchestrator.add_strategy(BollingerBandsStrategy())
    orchestrator.add_strategy(MovingAverageCrossStrategy())
    orchestrator.add_strategy(RSIMACDStrategy())
