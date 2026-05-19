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


class PanicReversalStrategy(BaseStrategy):
    """
    恐慌反转策略
    
    检测条件：
    - 1小时下跌 > 1.5%
    - 成交量 > 1.5倍平均
    
    适合做多，在恐慌性下跌后反弹
    """
    
    def __init__(
        self,
        strategy_id: str = "panic_reversal",
        drop_threshold: float = -0.015,
        volume_ratio_threshold: float = 1.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.drop_threshold = drop_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        # 获取价格和成交量数据
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")
        
        if len(close_prices) < 12:
            return None
        
        current_price = close_prices[-1]
        
        # 计算1小时跌幅（假设数据是5分钟K线，12个点=1小时）
        price_1h_ago = close_prices[-12]
        return_1h = (current_price - price_1h_ago) / price_1h_ago
        
        # 计算成交量比率
        if len(volumes) >= 288:  # 24小时平均
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0
        
        # 检测恐慌反转
        signal = None
        
        if return_1h <= self.drop_threshold and volume_ratio >= self.volume_ratio_threshold:
            # 恐慌下跌 -> 做多信号
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (abs(return_1h) - abs(self.drop_threshold)) * 50 + 0.5),
                reason=f"恐慌反转: 1h跌幅={return_1h*100:.2f}%, 成交量比={volume_ratio:.2f}",
                metadata={"return_1h": return_1h, "volume_ratio": volume_ratio},
            )
        
        return signal


class LongLiquidationBounceStrategy(BaseStrategy):
    """
    多头踩踏反弹策略 (LLB)
    
    检测条件：
    - 1小时跌幅 > 2%
    - 多头爆仓量 spike > 3x 均值
    - OI 24h 变化 < -15%
    - RSI < 25
    - 成交量冲击 > 2x 均值
    
    适合做多，在多头恐慌性踩踏后抢反弹
    """
    
    def __init__(
        self,
        strategy_id: str = "long_liquidation_bounce",
        drop_threshold: float = -0.02,
        rsi_threshold: float = 25.0,
        volume_ratio_threshold: float = 2.0,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.drop_threshold = drop_threshold
        self.rsi_threshold = rsi_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity
        
        self._rsi_prev = None
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算 RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = deltas.copy()
        gains[gains < 0] = 0
        losses = -deltas.copy()
        losses[losses < 0] = 0
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        # 获取价格和成交量数据
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")
        
        if len(close_prices) < 14:
            return None
        
        current_price = close_prices[-1]
        
        # 计算1小时跌幅
        if len(close_prices) >= 12:
            price_1h_ago = close_prices[-12]
            return_1h = (current_price - price_1h_ago) / price_1h_ago
        else:
            return_1h = 0.0
        
        # 计算 RSI
        rsi = self.calculate_rsi(close_prices)
        
        # 计算成交量比率
        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0
        
        # 获取额外数据（如果有
        long_liquidations_spike = data.get("long_liquidations_spike", False)
        oi_drop = data.get("oi_24h_change", 0.0)
        
        # 计算条件满足情况
        conditions_met = 0
        total_conditions = 3
        
        # 条件 1: 跌幅达标
        if return_1h <= self.drop_threshold:
            conditions_met += 1
        
        # 条件 2: RSI 超卖
        if rsi <= self.rsi_threshold:
            conditions_met += 1
        
        # 条件 3: 成交量冲击达标
        if volume_ratio >= self.volume_ratio_threshold:
            conditions_met += 1
        
        # 条件 4 (额外加分项：如果有爆仓数据
        if long_liquidations_spike:
            total_conditions += 1
            conditions_met += 1
        
        # 条件 5 (额外加分项：OI 下降
        if oi_drop <= -0.15:
            total_conditions += 1
            conditions_met += 1
        
        # 生成信号
        signal = None
        
        if conditions_met >= 2:
            confidence = min(0.9, (conditions_met / total_conditions) * 0.7 + 0.2)
            
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"多头踩踏反弹: 1h跌幅={return_1h*100:.2f}%, RSI={rsi:.1f}, 成交量比={volume_ratio:.2f}",
                metadata={
                    "return_1h": return_1h,
                    "rsi": rsi,
                    "volume_ratio": volume_ratio,
                    "conditions_met": conditions_met,
                    "total_conditions": total_conditions,
                },
            )
        
        self._rsi_prev = rsi
        
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
    
    # Panic Reversal 策略
    panic_reversal_strategy = PanicReversalStrategy(
        strategy_id="panic_reversal",
        drop_threshold=-0.015,
        volume_ratio_threshold=1.5,
    )
    orchestrator.add_strategy(panic_reversal_strategy)
    
    # Long Liquidation Bounce 策略（新加）
    long_liquidation_bounce_strategy = LongLiquidationBounceStrategy(
        strategy_id="long_liquidation_bounce",
        drop_threshold=-0.02,
        rsi_threshold=25.0,
        volume_ratio_threshold=2.0,
    )
    orchestrator.add_strategy(long_liquidation_bounce_strategy)
    
    logger.info("Default strategies created: RSI, MACD, Panic Reversal, Long Liquidation Bounce")
    return orchestrator


class VolumeClimaxFadeStrategy(BaseStrategy):
    """
    放量高潮衰竭策略
    
    核心逻辑：放量新高后衰竭，做空
    """
    
    def __init__(
        self,
        strategy_id: str = "volume_climax_fade",
        volume_ratio_threshold: float = 2.0,
        upper_shadow_threshold: float = 0.3,
        price_threshold: float = 0.003,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.volume_ratio_threshold = volume_ratio_threshold
        self.upper_shadow_threshold = upper_shadow_threshold
        self.price_threshold = price_threshold
        self.default_quantity = default_quantity
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        # 获取数据
        close_prices = data.get("close_prices", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")
        
        if len(close_prices) < 12:
            return None
        
        current_price = close_prices[-1]
        current_high = high_prices[-1]
        current_low = low_prices[-1]
        
        # 计算上影线比例
        candle_range = current_high - current_low if current_high - current_low > 0 else 1e-10
        upper_shadow = current_high - current_price
        upper_shadow_ratio = upper_shadow / candle_range
        
        # 计算成交量比例
        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0
        
        # 计算价格涨幅
        price_1h_ago = close_prices[-12]
        return_1h = (current_price - price_1h_ago) / price_1h_ago
        
        # 检测信号
        signal = None
        
        # 条件：放量 + 上影线长 + 价格上涨
        if (volume_ratio >= self.volume_ratio_threshold and
            upper_shadow_ratio >= self.upper_shadow_threshold and
            return_1h >= self.price_threshold):
            
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (
                    (volume_ratio / self.volume_ratio_threshold) * 0.3 +
                    (upper_shadow_ratio / self.upper_shadow_threshold) * 0.4 + 0.2
                )),
                reason=f"放量高潮衰竭: 成交量比={volume_ratio:.2f}, 上影线比={upper_shadow_ratio:.2f}, 1h涨幅={return_1h*100:.2f}%",
                metadata={
                    "volume_ratio": volume_ratio,
                    "upper_shadow_ratio": upper_shadow_ratio,
                    "return_1h": return_1h,
                },
            )
        
        return signal


class WeakBounceShortStrategy(BaseStrategy):
    """
    弱反弹做空策略
    
    核心逻辑：大跌后反弹弱，继续做空
    """
    
    def __init__(
        self,
        strategy_id: str = "weak_bounce_short",
        drop_threshold_4h: float = -0.02,
        bounce_min: float = 0.003,
        bounce_max: float = 0.015,
        volume_ratio_threshold: float = 1.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.drop_threshold_4h = drop_threshold_4h
        self.bounce_min = bounce_min
        self.bounce_max = bounce_max
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")
        
        if len(close_prices) < 60:
            return None
        
        current_price = close_prices[-1]
        
        # 计算4小时前和1小时前价格
        price_4h_ago = close_prices[-48]
        price_1h_ago = close_prices[-12]
        
        # 计算跌幅和反弹幅度
        drop_4h = (price_4h_ago - price_1h_ago) / price_4h_ago
        bounce = (current_price - price_1h_ago) / price_1h_ago
        
        # 计算成交量比例
        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0
        
        # 检测信号
        signal = None
        
        # 条件：4小时前跌幅足够大 + 1小时内有弱反弹 + 成交量放大
        if (drop_4h <= self.drop_threshold_4h and
            self.bounce_min <= bounce <= self.bounce_max and
            volume_ratio >= self.volume_ratio_threshold):
            
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (
                    (abs(drop_4h) / abs(self.drop_threshold_4h)) * 0.4 +
                    (bounce / self.bounce_max) * 0.3 +
                    (volume_ratio / self.volume_ratio_threshold) * 0.3
                )),
                reason=f"弱反弹做空: 4h跌幅={drop_4h*100:.2f}%, 反弹幅={bounce*100:.2f}%, 成交量比={volume_ratio:.2f}",
                metadata={
                    "drop_4h": drop_4h,
                    "bounce": bounce,
                    "volume_ratio": volume_ratio,
                },
            )
        
        return signal


class DynamicStrategySelector:
    """
    动态策略选择器
    
    根据市场环境自动选择策略
    """
    
    def __init__(self):
        self._all_strategies = {}
        self._last_month_return = None
        self._enabled_strategies = []
        
    def register_strategy(self, strategy: BaseStrategy, market_condition: str):
        """
        注册策略
        
        Args:
            strategy: 策略
            market_condition: 适用的市场环境（"panic_drop", "slow_drop", "bounce", "normal"}
        """
        if market_condition not in self._all_strategies:
            self._all_strategies[market_condition] = []
        self._all_strategies[market_condition].append(strategy)
        
    def detect_market_condition(self, data: Dict) -> str:
        """
        检测市场环境
        
        Returns:
            市场环境类型
        """
        close_prices = data.get("close_prices", [])
        if len(close_prices) < 48:
            return "normal"
        
        # 计算4小时跌幅
        price_4h_ago = close_prices[-48]
        price_current = close_prices[-1]
        return_4h = (price_current - price_4h_ago) / price_4h_ago
        
        # 判断市场环境
        if return_4h < -0.08:
            return "panic_drop"
        elif return_4h < -0.02:
            return "slow_drop"
        elif return_4h > 0.02:
            return "bounce"
        else:
            return "normal"
        
    def get_enabled_strategies(self, data: Dict) -> List[BaseStrategy]:
        """
        获取当前环境启用的策略
        
        Returns:
            启用的策略列表
        """
        market_condition = self.detect_market_condition(data)
        
        # 返回该市场环境下的所有策略
        return self._all_strategies.get(market_condition, [])
