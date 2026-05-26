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

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        生成信号（新接口）

        Args:
            features: 特征数据

        Returns:
            信号字典或 None
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

        deltas = np.diff(prices)

        gains = deltas.copy()
        gains[gains < 0] = 0

        losses = -deltas.copy()
        losses[losses < 0] = 0

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

        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < self.period + 1:
            return None

        current_price = close_prices[-1]
        symbol = data.get("symbol", "BTCUSDT")

        rsi = self.calculate_rsi(close_prices)

        if self._rsi_prev is None:
            self._rsi_prev = rsi
            return None

        signal = None

        if rsi <= self.oversold and self._rsi_prev > self.oversold:
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

        self._rsi_prev = rsi

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）"""
        if not self._enabled:
            return None

        rsi = features.get('rsi_14')
        if rsi is None:
            return None

        oversold = self.params.get('oversold', self.oversold)
        overbought = self.params.get('overbought', self.overbought)

        if rsi < oversold:
            return {
                'signal_type': 'buy',
                'confidence': 1.0 - rsi / 100,
                'reason': f"RSI {rsi:.1f} < {oversold}"
            }
        elif rsi > overbought:
            return {
                'signal_type': 'sell',
                'confidence': (rsi - 50) / 50,
                'reason': f"RSI {rsi:.1f} > {overbought}"
            }
        return None


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

        macd_line, signal_line, histogram = self.calculate_macd(close_prices)

        signal = None

        if (self._macd_prev is not None and
            self._signal_prev is not None):
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

        self._macd_prev = macd_line
        self._signal_prev = signal_line

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）"""
        if not self._enabled:
            return None

        macd = features.get('macd')
        signal = features.get('macd_signal')
        
        if macd is None or signal is None:
            return None

        if self._macd_prev is None:
            self._macd_prev = macd
            self._signal_prev = signal
            return None

        if self._macd_prev <= self._signal_prev and macd > signal:
            result = {
                'signal_type': 'buy',
                'confidence': 0.7,
                'reason': f"MACD 金叉: {macd:.4f} > {signal:.4f}"
            }
        elif self._macd_prev >= self._signal_prev and macd < signal:
            result = {
                'signal_type': 'sell',
                'confidence': 0.7,
                'reason': f"MACD 死叉: {macd:.4f} < {signal:.4f}"
            }
        else:
            result = None

        self._macd_prev = macd
        self._signal_prev = signal
        return result


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

        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 12:
            return None

        current_price = close_prices[-1]

        price_1h_ago = close_prices[-12]
        return_1h = (current_price - price_1h_ago) / price_1h_ago

        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0

        signal = None

        if return_1h <= self.drop_threshold and volume_ratio >= self.volume_ratio_threshold:
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

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）"""
        if not self._enabled:
            return None

        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')

        if return_1h is None or volume_ratio is None:
            return None

        drop_threshold = self.params.get('drop_threshold', self.drop_threshold) if hasattr(self, 'params') else self.drop_threshold
        volume_ratio_threshold = self.params.get('volume_ratio_threshold', self.volume_ratio_threshold) if hasattr(self, 'params') else self.volume_ratio_threshold

        if return_1h <= drop_threshold and volume_ratio >= volume_ratio_threshold:
            confidence = min(0.9, (abs(return_1h) - abs(drop_threshold)) * 50 + 0.5)
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"恐慌反转: 1h跌幅={return_1h*100:.2f}%, 成交量比={volume_ratio:.2f}"
            }

        return None


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
        params: Dict[str, Any] = None,
    ):
        super().__init__(strategy_id)
        self.drop_threshold = drop_threshold
        self.rsi_threshold = rsi_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity
        self.params = params or {}

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

        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 14:
            return None

        current_price = close_prices[-1]

        if len(close_prices) >= 12:
            price_1h_ago = close_prices[-12]
            return_1h = (current_price - price_1h_ago) / price_1h_ago
        else:
            return_1h = 0.0

        rsi = self.calculate_rsi(close_prices)

        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0

        long_liquidations_spike = data.get("long_liquidations_spike", False)
        oi_drop = data.get("oi_24h_change", 0.0)

        conditions_met = 0
        total_conditions = 3

        if return_1h <= self.drop_threshold:
            conditions_met += 1

        if rsi <= self.rsi_threshold:
            conditions_met += 1

        if volume_ratio >= self.volume_ratio_threshold:
            conditions_met += 1

        if long_liquidations_spike:
            total_conditions += 1
            conditions_met += 1

        if oi_drop <= -0.15:
            total_conditions += 1
            conditions_met += 1

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

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')
        rsi_14 = features.get('rsi_14')
        long_liquidations_spike = features.get('long_liquidations_spike')

        if return_1h is None or volume_ratio is None:
            return None

        drop_threshold = self.params.get('drop_threshold', self.drop_threshold)
        volume_ratio_threshold = self.params.get('volume_ratio_threshold', self.volume_ratio_threshold)

        conditions_met = 0
        total_conditions = 2

        if return_1h <= drop_threshold:
            conditions_met += 1

        if volume_ratio >= volume_ratio_threshold:
            conditions_met += 1

        if rsi_14 is not None and rsi_14 <= self.rsi_threshold:
            total_conditions += 1
            conditions_met += 1

        if long_liquidations_spike:
            total_conditions += 1
            conditions_met += 1

        if conditions_met >= 2:
            confidence = min(0.9, (conditions_met / total_conditions) * 0.7 + 0.2)
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"多头踩踏反弹: 1h跌幅={return_1h*100:.2f}%, 成交量比={volume_ratio:.2f}, RSI={rsi_14}"
            }

        return None


class SymbolStrategyConfig:
    """币种策略配置（独立参数优化）"""

    def __init__(
        self,
        symbol: str,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        panic_drop_threshold: float = -0.015,
        volume_ratio_threshold: float = 1.5,
        default_quantity: float = 0.01,
    ):
        self.symbol = symbol
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.panic_drop_threshold = panic_drop_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity


class MultiStrategyOrchestrator:
    """
    多策略编排器（币种感知 + Regime 驱动 + Confluence 融合）

    支持：
    - 按币种独立管理策略实例
    - 每个币种有独立的策略参数配置
    - 策略只在对应币种数据上运行
    - Regime 驱动策略启用/禁用
    - 多策略信号 Confluence 融合
    """

    def __init__(self, symbols: List[str] = None):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._symbol_strategies: Dict[str, List[str]] = {}
        self._symbol_data: Dict[str, Dict] = {}
        self._symbol_configs: Dict[str, SymbolStrategyConfig] = {}
        self._regime_runtime: Optional[Any] = None
        self._confluence_engine: Optional[Any] = None

        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]

        for symbol in self.symbols:
            self._symbol_strategies[symbol] = []

        logger.info(f"MultiStrategyOrchestrator initialized for symbols: {self.symbols}")

    def attach_regime_runtime(self, regime_runtime: Any) -> None:
        self._regime_runtime = regime_runtime
        regime_runtime.apply_to_orchestrator(self)
        logger.info(f"Attached regime runtime, current regime: {regime_runtime.current_regime.regime.value}")

    def attach_confluence_engine(self, confluence_engine: Any = None) -> None:
        if confluence_engine is None:
            from engines.compute.signal.confluence_engine import SignalConfluenceEngine
            confluence_engine = SignalConfluenceEngine()
        self._confluence_engine = confluence_engine
        logger.info("Attached confluence engine")

    def add_strategy(self, strategy: BaseStrategy, symbol: str = None):
        self._strategies[strategy.strategy_id] = strategy

        if symbol:
            strategy.symbol = symbol
            if symbol not in self._symbol_strategies:
                self._symbol_strategies[symbol] = []
            self._symbol_strategies[symbol].append(strategy.strategy_id)
        else:
            for sym in self.symbols:
                if sym not in self._symbol_strategies:
                    self._symbol_strategies[sym] = []
                self._symbol_strategies[sym].append(strategy.strategy_id)

        logger.info(f"Strategy added: {strategy.strategy_id} for {symbol or 'all symbols'}")

    def remove_strategy(self, strategy_id: str):
        if strategy_id in self._strategies:
            strategy = self._strategies[strategy_id]
            symbol = getattr(strategy, 'symbol', None)

            if symbol and symbol in self._symbol_strategies:
                self._symbol_strategies[symbol] = [
                    sid for sid in self._symbol_strategies[symbol]
                    if sid != strategy_id
                ]

            del self._strategies[strategy_id]
            logger.info(f"Strategy removed: {strategy_id}")

    def update_market_data(self, symbol: str, data: Dict):
        self._symbol_data[symbol] = data

    def process(self, symbol: str = None, use_confluence: bool = True) -> List[Any]:
        all_signals = []

        target_symbols = [symbol] if symbol else list(self._symbol_data.keys())

        if self._regime_runtime:
            self._regime_runtime.apply_to_orchestrator(self)

        for sym in target_symbols:
            if sym not in self._symbol_data:
                continue

            data = self._symbol_data[sym]
            strategy_ids = self._symbol_strategies.get(sym, [])

            for strategy_id in strategy_ids:
                strategy = self._strategies.get(strategy_id)
                if not strategy or not strategy.is_enabled:
                    continue

                signal = strategy.calculate(data)
                if signal:
                    signal.symbol = sym
                    all_signals.append(signal)

        logger.debug(f"Generated {len(all_signals)} signals from {len(self._strategies)} strategies")

        if use_confluence and self._confluence_engine and all_signals:
            regime = None
            if self._regime_runtime:
                regime = self._regime_runtime.current_regime.regime.value
            confluence_signals = self._confluence_engine.process_signals(all_signals, regime=regime)
            return confluence_signals

        return all_signals

    def process_all_symbols(self, use_confluence: bool = True) -> Dict[str, List[Any]]:
        results = {}

        for symbol in self._symbol_data.keys():
            signals = self.process(symbol, use_confluence=use_confluence)
            if signals:
                results[symbol] = signals

        return results

    def get_symbol_strategies(self, symbol: str) -> List[str]:
        return self._symbol_strategies.get(symbol, [])

    def get_strategy_for_symbol(self, symbol: str, strategy_id: str) -> Optional[BaseStrategy]:
        if strategy_id in self._symbol_strategies.get(symbol, []):
            return self._strategies.get(strategy_id)
        return None

    def get_active_strategy_ids(self) -> List[str]:
        return [sid for sid, s in self._strategies.items() if s.is_enabled]

    def get_regime_state(self) -> Optional[Dict[str, Any]]:
        if self._regime_runtime:
            return self._regime_runtime.current_regime.__dict__
        return None


def create_default_strategies(symbols: List[str] = None, attach_regime: bool = True) -> MultiStrategyOrchestrator:
    """
    创建默认策略集合（按币种独立）

    Args:
        symbols: 币种列表
        attach_regime: 是否自动 attach Regime Runtime
    """
    symbols = symbols or ["BTCUSDT", "ETHUSDT"]
    orchestrator = MultiStrategyOrchestrator(symbols)
    
    if attach_regime:
        try:
            from runtimes.regime_runtime import get_regime_runtime
            regime_runtime = get_regime_runtime()
            orchestrator.attach_regime_runtime(regime_runtime)
        except ImportError as e:
            logger.warning(f"无法导入 Regime Runtime: {e}，跳过 attach")
        except Exception as e:
            logger.error(f"attach Regime Runtime 失败: {e}")

    for symbol in symbols:
        rsi_strategy = RSIStrategy(
            strategy_id=f"rsi_14_{symbol}",
            period=14,
            oversold=30,
            overbought=70,
        )
        orchestrator.add_strategy(rsi_strategy, symbol)

        macd_strategy = MACDStrategy(
            strategy_id=f"macd_12_26_9_{symbol}",
        )
        orchestrator.add_strategy(macd_strategy, symbol)

        panic_reversal_strategy = PanicReversalStrategy(
            strategy_id=f"panic_reversal_{symbol}",
            drop_threshold=-0.015,
            volume_ratio_threshold=1.5,
        )
        orchestrator.add_strategy(panic_reversal_strategy, symbol)

        long_liquidation_bounce_strategy = LongLiquidationBounceStrategy(
            strategy_id=f"long_liquidation_bounce_{symbol}",
            drop_threshold=-0.02,
            rsi_threshold=25.0,
            volume_ratio_threshold=2.0,
        )
        orchestrator.add_strategy(long_liquidation_bounce_strategy, symbol)

        volume_climax_fade_strategy = VolumeClimaxFadeStrategy(
            strategy_id=f"volume_climax_fade_{symbol}",
            volume_ratio_threshold=2.0,
            upper_shadow_threshold=0.3,
        )
        orchestrator.add_strategy(volume_climax_fade_strategy, symbol)

        weak_bounce_short_strategy = WeakBounceShortStrategy(
            strategy_id=f"weak_bounce_short_{symbol}",
            drop_threshold_4h=-0.02,
            bounce_max=0.015,
        )
        orchestrator.add_strategy(weak_bounce_short_strategy, symbol)

        oi_flush_strategy = OIFlushStrategy(
            strategy_id=f"oi_flush_{symbol}",
            oi_flush_threshold=-0.10,
            funding_normalization_threshold=0.5,
        )
        orchestrator.add_strategy(oi_flush_strategy, symbol)

        short_squeeze_strategy = ShortSqueezeStrategy(
            strategy_id=f"short_squeeze_{symbol}",
            funding_extreme_threshold=-2.0,
            oi_growth_threshold=0.02,
        )
        orchestrator.add_strategy(short_squeeze_strategy, symbol)

        funding_exhaustion_trap_strategy = FundingExhaustionTrapStrategy(
            strategy_id=f"funding_exhaustion_trap_{symbol}",
            funding_extreme_threshold=2.5,
        )
        orchestrator.add_strategy(funding_exhaustion_trap_strategy, symbol)

        dead_cat_echo_strategy = DeadCatEchoStrategy(
            strategy_id=f"dead_cat_echo_{symbol}",
            drop_threshold_4h=-0.02,
            bounce_ratio_max=0.30,
        )
        orchestrator.add_strategy(dead_cat_echo_strategy, symbol)

        imbalance_pressure_strategy = ImbalancePressureStrategy(
            strategy_id=f"imbalance_pressure_{symbol}",
            imbalance_threshold=0.3,
        )
        orchestrator.add_strategy(imbalance_pressure_strategy, symbol)

        sweep_detection_strategy = SweepDetectionStrategy(
            strategy_id=f"sweep_detection_{symbol}",
            sweep_threshold=0.7,
        )
        orchestrator.add_strategy(sweep_detection_strategy, symbol)

        liquidity_vacuum_strategy = LiquidityVacuumStrategy(
            strategy_id=f"liquidity_vacuum_{symbol}",
            spread_expansion_factor=2.0,
        )
        orchestrator.add_strategy(liquidity_vacuum_strategy, symbol)

        aggressive_flow_strategy = AggressiveFlowStrategy(
            strategy_id=f"aggressive_flow_{symbol}",
            flow_imbalance_threshold=2.0,
        )
        orchestrator.add_strategy(aggressive_flow_strategy, symbol)

        breakout_strategy = BreakoutStrategy(
            strategy_id=f"breakout_{symbol}",
            lookback=48,
            volume_ratio_threshold=1.5,
        )
        orchestrator.add_strategy(breakout_strategy, symbol)

        trend_following_strategy = TrendFollowingStrategy(
            strategy_id=f"trend_following_{symbol}",
            fast_period=10,
            slow_period=50,
        )
        orchestrator.add_strategy(trend_following_strategy, symbol)

        volatility_expansion_strategy = VolatilityExpansionStrategy(
            strategy_id=f"volatility_expansion_{symbol}",
            atr_expansion_ratio=1.5,
        )
        orchestrator.add_strategy(volatility_expansion_strategy, symbol)

        bb_compression_breakout_strategy = BBCompressionBreakoutStrategy(
            strategy_id=f"bb_compression_breakout_{symbol}",
            compression_threshold=0.02,
        )
        orchestrator.add_strategy(bb_compression_breakout_strategy, symbol)

        momentum_ignition_strategy = MomentumIgnitionStrategy(
            strategy_id=f"momentum_ignition_{symbol}",
            volume_spike_ratio=3.0,
            return_threshold=0.01,
        )
        orchestrator.add_strategy(momentum_ignition_strategy, symbol)

        lead_lag_strategy = LeadLagStrategy(
            strategy_id=f"lead_lag_{symbol}",
            divergence_threshold=0.005,
        )
        orchestrator.add_strategy(lead_lag_strategy, symbol)

        premium_divergence_strategy = PremiumDivergenceStrategy(
            strategy_id=f"premium_divergence_{symbol}",
            premium_threshold=0.005,
        )
        orchestrator.add_strategy(premium_divergence_strategy, symbol)

        sma_crossover_strategy = SMACrossoverStrategy(
            strategy_id=f"sma_crossover_{symbol}",
            fast_period=10,
            slow_period=20,
        )
        orchestrator.add_strategy(sma_crossover_strategy, symbol)

        ema_crossover_strategy = EMACrossoverStrategy(
            strategy_id=f"ema_crossover_{symbol}",
            fast_period=10,
            slow_period=20,
        )
        orchestrator.add_strategy(ema_crossover_strategy, symbol)

        bollinger_bands_strategy = BollingerBandsStrategy(
            strategy_id=f"bollinger_bands_{symbol}",
            period=20,
            std_dev=2.0,
        )
        orchestrator.add_strategy(bollinger_bands_strategy, symbol)

        momentum_strategy = MomentumStrategy(
            strategy_id=f"momentum_{symbol}",
            period=10,
            threshold=0.02,
        )
        orchestrator.add_strategy(momentum_strategy, symbol)

    logger.info(f"Default strategies created for {len(symbols)} symbols: {symbols}")
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

        candle_range = current_high - current_low if current_high - current_low > 0 else 1e-10
        upper_shadow = current_high - current_price
        upper_shadow_ratio = upper_shadow / candle_range

        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0

        price_1h_ago = close_prices[-12]
        return_1h = (current_price - price_1h_ago) / price_1h_ago

        signal = None

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

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）"""
        if not self._enabled:
            return None

        volume_ratio = features.get('volume_ratio')
        upper_shadow_ratio = features.get('upper_shadow_ratio')
        return_1h = features.get('return_1h')

        if volume_ratio is None or upper_shadow_ratio is None or return_1h is None:
            return None

        volume_ratio_threshold = getattr(self, 'params', {}).get('volume_ratio_threshold', self.volume_ratio_threshold)
        upper_shadow_threshold = getattr(self, 'params', {}).get('upper_shadow_threshold', self.upper_shadow_threshold)
        price_threshold = getattr(self, 'params', {}).get('price_threshold', self.price_threshold)

        if (volume_ratio >= volume_ratio_threshold and
            upper_shadow_ratio >= upper_shadow_threshold and
            return_1h >= price_threshold):

            confidence = min(0.9, (
                (volume_ratio / volume_ratio_threshold) * 0.3 +
                (upper_shadow_ratio / upper_shadow_threshold) * 0.4 + 0.2
            ))

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"放量高潮衰竭: 成交量比={volume_ratio:.2f}, 上影线比={upper_shadow_ratio:.2f}, 1h涨幅={return_1h*100:.2f}%"
            }

        return None


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

        price_4h_ago = close_prices[-48]
        price_1h_ago = close_prices[-12]

        drop_4h = (price_4h_ago - price_1h_ago) / price_4h_ago
        bounce = (current_price - price_1h_ago) / price_1h_ago

        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0

        signal = None

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

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）"""
        if not self._enabled:
            return None

        return_4h = features.get('return_4h')
        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')

        if return_4h is None or return_1h is None or volume_ratio is None:
            return None

        drop_threshold = getattr(self, 'params', {}).get('drop_threshold_4h', self.drop_threshold_4h)
        bounce_min = getattr(self, 'params', {}).get('bounce_min', self.bounce_min)
        bounce_max = getattr(self, 'params', {}).get('bounce_max', self.bounce_max)
        volume_threshold = getattr(self, 'params', {}).get('volume_ratio_threshold', self.volume_ratio_threshold)

        if (return_4h <= drop_threshold and
            bounce_min <= return_1h <= bounce_max and
            volume_ratio >= volume_threshold):

            confidence = min(0.9, (
                (abs(return_4h) / abs(drop_threshold)) * 0.4 +
                (return_1h / bounce_max) * 0.3 +
                (volume_ratio / volume_threshold) * 0.3
            ))

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"弱反弹做空: 4h跌幅={return_4h*100:.2f}%, 反弹幅={return_1h*100:.2f}%, 成交量比={volume_ratio:.2f}"
            }

        return None


class OIFlushStrategy(BaseStrategy):
    """
    OI清洗策略

    核心逻辑：持仓量急跌+资金费率回归 → 趋势恢复
    """

    def __init__(
        self,
        strategy_id: str = "oi_flush",
        oi_flush_threshold: float = -0.10,
        funding_normalization_threshold: float = 0.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.oi_flush_threshold = oi_flush_threshold
        self.funding_normalization_threshold = funding_normalization_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        oi_delta = data.get("oi_delta", 0.0)
        oi_zscore = data.get("oi_zscore", 0.0)
        funding_delta = data.get("funding_delta", 0.0)
        liquidation_pressure = data.get("liquidation_pressure", 0.0)
        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if not close_prices or len(close_prices) < 48:
            return None

        current_price = close_prices[-1]
        price_24h_ago = close_prices[-48]
        price_drop = (current_price - price_24h_ago) / price_24h_ago

        signal = None

        if oi_delta < self.oi_flush_threshold:
            funding_normalizing = abs(funding_delta) > self.funding_normalization_threshold
            if funding_normalizing:
                if price_drop < 0:
                    action = ActionType.LONG
                    reason = f"OI清洗做多: OI变化={oi_delta*100:.2f}%, 资金费率变化={funding_delta:.4f}, 价格变化={price_drop*100:.2f}%"
                else:
                    action = ActionType.SHORT
                    reason = f"OI清洗做空: OI变化={oi_delta*100:.2f}%, 资金费率变化={funding_delta:.4f}, 价格变化={price_drop*100:.2f}%"

                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.EVENT_DRIVEN,
                    symbol=symbol,
                    action=action,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=min(0.9, (
                        (abs(oi_delta) / abs(self.oi_flush_threshold)) * 0.4 +
                        (abs(funding_delta) / self.funding_normalization_threshold) * 0.3 +
                        abs(liquidation_pressure) * 0.3
                    )),
                    reason=reason,
                    metadata={
                        "oi_delta": oi_delta,
                        "oi_zscore": oi_zscore,
                        "funding_delta": funding_delta,
                        "liquidation_pressure": liquidation_pressure,
                        "price_drop": price_drop,
                    },
                )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        oi_delta = features.get('oi_delta')
        funding_delta = features.get('funding_delta')
        return_1h = features.get('return_1h')
        close = features.get('close')
        liquidation_pressure = features.get('liquidation_pressure', 0.0)

        if oi_delta is None or funding_delta is None:
            return None

        oi_flush_threshold = getattr(self, 'params', {}).get('oi_flush_threshold', self.oi_flush_threshold)
        funding_threshold = getattr(self, 'params', {}).get('funding_normalization_threshold', self.funding_normalization_threshold)

        if oi_delta >= oi_flush_threshold:
            return None

        if abs(funding_delta) <= funding_threshold:
            return None

        if return_1h is None and close is None:
            return None

        price_change = return_1h if return_1h is not None else 0.0
        if close is not None and 'close_prev' in features:
            price_change = (close - features.get('close_prev', close)) / features.get('close_prev', close)

        if price_change < 0:
            signal_type = 'buy'
            reason = f"OI清洗做多: OI变化={oi_delta*100:.2f}%, 资金费率变化={funding_delta:.4f}, 价格变化={price_change*100:.2f}%"
        else:
            signal_type = 'sell'
            reason = f"OI清洗做空: OI变化={oi_delta*100:.2f}%, 资金费率变化={funding_delta:.4f}, 价格变化={price_change*100:.2f}%"

        confidence = min(0.9, (
            (abs(oi_delta) / abs(oi_flush_threshold)) * 0.4 +
            (abs(funding_delta) / funding_threshold) * 0.3 +
            abs(liquidation_pressure) * 0.3
        ))

        return {
            'signal_type': signal_type,
            'confidence': confidence,
            'reason': reason
        }


class ShortSqueezeStrategy(BaseStrategy):
    """
    空头挤压策略

    核心逻辑：极端负资金费率+OI增加+价格上涨 → 空头被迫平仓
    """

    def __init__(
        self,
        strategy_id: str = "short_squeeze",
        funding_extreme_threshold: float = -2.0,
        oi_growth_threshold: float = 0.0,
        price_momentum_threshold: float = 0.005,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.funding_extreme_threshold = funding_extreme_threshold
        self.oi_growth_threshold = oi_growth_threshold
        self.price_momentum_threshold = price_momentum_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        funding_zscore = data.get("funding_zscore", 0.0)
        oi_delta = data.get("oi_delta", 0.0)
        short_pressure = data.get("short_pressure", 0.0)
        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if not close_prices or len(close_prices) < 12:
            return None

        current_price = close_prices[-1]
        price_1h_ago = close_prices[-12]
        price_momentum = (current_price - price_1h_ago) / price_1h_ago

        signal = None

        if (funding_zscore < self.funding_extreme_threshold and
            oi_delta > self.oi_growth_threshold and
            price_momentum > self.price_momentum_threshold):

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (
                    (abs(funding_zscore) / abs(self.funding_extreme_threshold)) * 0.4 +
                    (oi_delta / max(abs(oi_delta), 0.01)) * 0.2 +
                    (price_momentum / self.price_momentum_threshold) * 0.2 +
                    abs(short_pressure) * 0.2
                )),
                reason=f"空头挤压做多: 资金费率Z={funding_zscore:.2f}, OI变化={oi_delta*100:.2f}%, 价格动量={price_momentum*100:.2f}%",
                metadata={
                    "funding_zscore": funding_zscore,
                    "oi_delta": oi_delta,
                    "short_pressure": short_pressure,
                    "price_momentum": price_momentum,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        funding_zscore = features.get('funding_zscore')
        oi_delta = features.get('oi_delta')
        short_pressure = features.get('short_pressure')

        if funding_zscore is None or oi_delta is None:
            return None

        funding_threshold = self.params.get('funding_extreme_threshold', self.funding_extreme_threshold) if hasattr(self, 'params') else self.funding_extreme_threshold
        oi_threshold = self.params.get('oi_growth_threshold', self.oi_growth_threshold) if hasattr(self, 'params') else self.oi_growth_threshold
        price_momentum_threshold = self.params.get('price_momentum_threshold', self.price_momentum_threshold) if hasattr(self, 'params') else self.price_momentum_threshold

        if (funding_zscore < funding_threshold and
            oi_delta > oi_threshold and
            oi_delta > 0.02):

            confidence = min(0.9, (
                (abs(funding_zscore) / abs(funding_threshold)) * 0.4 +
                (oi_delta / max(abs(oi_delta), 0.01)) * 0.3 +
                abs(short_pressure) * 0.3 if short_pressure is not None else 0.0
            ))

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"空头挤压做多: 资金费率Z={funding_zscore:.2f}, OI变化={oi_delta*100:.2f}%, 空头压力={short_pressure}"
            }

        return None


class FundingExhaustionTrapStrategy(BaseStrategy):
    """
    资金费率耗尽陷阱策略

    核心逻辑：资金费率极端 → 反转陷阱
    """

    def __init__(
        self,
        strategy_id: str = "funding_exhaustion_trap",
        funding_extreme_threshold: float = 2.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.funding_extreme_threshold = funding_extreme_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        funding_zscore = data.get("funding_zscore", 0.0)
        funding_divergence = data.get("funding_divergence", 0.0)
        oi_alignment = data.get("oi_alignment", 0.0)
        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if not close_prices:
            return None

        current_price = close_prices[-1]

        signal = None

        if funding_zscore > self.funding_extreme_threshold:
            action = ActionType.SHORT
            reason = f"资金费率耗尽做空: 资金费率Z={funding_zscore:.2f}, 背离={funding_divergence:.4f}"
        elif funding_zscore < -self.funding_extreme_threshold:
            action = ActionType.LONG
            reason = f"资金费率耗尽做多: 资金费率Z={funding_zscore:.2f}, 背离={funding_divergence:.4f}"
        else:
            return None

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            strategy_type=StrategyType.EVENT_DRIVEN,
            symbol=symbol,
            action=action,
            quantity=self.default_quantity,
            price=current_price,
            confidence=min(0.9, (
                (abs(funding_zscore) / self.funding_extreme_threshold) * 0.5 +
                abs(funding_divergence) * 0.3 +
                abs(oi_alignment) * 0.2
            )),
            reason=reason,
            metadata={
                "funding_zscore": funding_zscore,
                "funding_divergence": funding_divergence,
                "oi_alignment": oi_alignment,
            },
        )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        funding_zscore = features.get('funding_zscore')
        funding_divergence = features.get('funding_divergence')

        if funding_zscore is None:
            return None

        threshold = self.params.get('funding_extreme_threshold', self.funding_extreme_threshold) if hasattr(self, 'params') else self.funding_extreme_threshold

        if funding_zscore > threshold:
            confidence = min(0.9, (funding_zscore / threshold) * 0.5 + abs(funding_divergence or 0) * 0.3)
            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"资金费率耗尽做空: funding_zscore={funding_zscore:.2f} > {threshold}, 背离={funding_divergence}"
            }
        elif funding_zscore < -threshold:
            confidence = min(0.9, (abs(funding_zscore) / threshold) * 0.5 + abs(funding_divergence or 0) * 0.3)
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"资金费率耗尽做多: funding_zscore={funding_zscore:.2f} < -{threshold}, 背离={funding_divergence}"
            }

        return None


class DeadCatEchoStrategy(BaseStrategy):
    """
    死猫回声策略

    核心逻辑：大跌→弱反弹→继续下跌
    """

    def __init__(
        self,
        strategy_id: str = "dead_cat_echo",
        drop_threshold_4h: float = -0.02,
        bounce_ratio_max: float = 0.30,
        volume_fade_threshold: float = 0.8,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.drop_threshold_4h = drop_threshold_4h
        self.bounce_ratio_max = bounce_ratio_max
        self.volume_fade_threshold = volume_fade_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        trend_exhaustion = data.get("trend_exhaustion", 0.0)
        weak_bounce = data.get("weak_bounce", 0.0)
        volume_fade = data.get("volume_fade", 0.0)
        symbol = data.get("symbol", "BTCUSDT")

        if not close_prices or len(close_prices) < 48:
            return None

        current_price = close_prices[-1]

        price_4h_ago = close_prices[-48]
        drop_low = min(close_prices[-48:])
        drop_4h = (price_4h_ago - drop_low) / price_4h_ago

        bounce_from_low = (current_price - drop_low) / drop_low if drop_low > 0 else 0.0
        bounce_ratio = bounce_from_low / drop_4h if drop_4h > 0 else 0.0

        if len(volumes) >= 48:
            avg_volume_first = np.mean(volumes[-48:-24])
            avg_volume_second = np.mean(volumes[-24:])
            volume_ratio = avg_volume_second / avg_volume_first if avg_volume_first > 0 else 1.0
        else:
            volume_ratio = 1.0

        signal = None

        if (drop_4h >= abs(self.drop_threshold_4h) and
            bounce_ratio <= self.bounce_ratio_max and
            volume_ratio <= self.volume_fade_threshold):

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(0.9, (
                    (drop_4h / abs(self.drop_threshold_4h)) * 0.35 +
                    (1.0 - bounce_ratio / self.bounce_ratio_max) * 0.35 +
                    (1.0 - volume_ratio / self.volume_fade_threshold) * 0.15 +
                    abs(trend_exhaustion) * 0.15
                )),
                reason=f"死猫回声做空: 4h跌幅={drop_4h*100:.2f}%, 反弹比={bounce_ratio*100:.2f}%, 成交量衰减={volume_ratio:.2f}",
                metadata={
                    "drop_4h": drop_4h,
                    "bounce_ratio": bounce_ratio,
                    "volume_ratio": volume_ratio,
                    "trend_exhaustion": trend_exhaustion,
                    "weak_bounce": weak_bounce,
                    "volume_fade": volume_fade,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        return_4h = features.get('return_4h')
        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')

        if return_4h is None or volume_ratio is None:
            return None

        drop_threshold = getattr(self, 'params', {}).get('drop_threshold_4h', self.drop_threshold_4h)
        bounce_ratio_max = getattr(self, 'params', {}).get('bounce_ratio_max', self.bounce_ratio_max)
        volume_fade_threshold = getattr(self, 'params', {}).get('volume_fade_threshold', self.volume_fade_threshold)

        abs_drop = abs(return_4h)
        bounce_ratio = return_1h / abs_drop if abs_drop > 0 and return_4h < 0 else 0.0

        if (abs_drop >= abs(drop_threshold) and
            bounce_ratio <= bounce_ratio_max and
            volume_ratio <= volume_fade_threshold):

            confidence = min(0.9, (
                (abs_drop / abs(drop_threshold)) * 0.35 +
                (1.0 - bounce_ratio / bounce_ratio_max) * 0.35 +
                (1.0 - volume_ratio / volume_fade_threshold) * 0.15 +
                0.15
            ))

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"死猫回声做空: 4h跌幅={abs_drop*100:.2f}%, 反弹比={bounce_ratio*100:.2f}%, 成交量衰减={volume_ratio:.2f}"
            }

        return None


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

        price_4h_ago = close_prices[-48]
        price_current = close_prices[-1]
        return_4h = (price_current - price_4h_ago) / price_4h_ago

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

        return self._all_strategies.get(market_condition, [])


class BreakoutStrategy(BaseStrategy):
    """
    突破策略

    核心逻辑：价格突破4h高低点且成交量放大，跟随突破方向
    """

    def __init__(
        self,
        strategy_id: str = "breakout",
        lookback: int = 48,
        volume_ratio_threshold: float = 1.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.lookback = lookback
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.lookback + 1:
            return None

        current_price = close_prices[-1]

        range_high = max(high_prices[-self.lookback:-1])
        range_low = min(low_prices[-self.lookback:-1])

        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0

        signal = None

        if current_price > range_high and volume_ratio >= self.volume_ratio_threshold:
            breakout_magnitude = (current_price - range_high) / range_high
            confidence = min(0.9, breakout_magnitude * 50 + (volume_ratio / self.volume_ratio_threshold) * 0.3)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"向上突破: 价格={current_price:.2f}, 4h高点={range_high:.2f}, 成交量比={volume_ratio:.2f}",
                metadata={
                    "range_high": range_high,
                    "range_low": range_low,
                    "breakout_magnitude": breakout_magnitude,
                    "volume_ratio": volume_ratio,
                },
            )
        elif current_price < range_low and volume_ratio >= self.volume_ratio_threshold:
            breakout_magnitude = (range_low - current_price) / range_low
            confidence = min(0.9, breakout_magnitude * 50 + (volume_ratio / self.volume_ratio_threshold) * 0.3)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"向下突破: 价格={current_price:.2f}, 4h低点={range_low:.2f}, 成交量比={volume_ratio:.2f}",
                metadata={
                    "range_high": range_high,
                    "range_low": range_low,
                    "breakout_magnitude": breakout_magnitude,
                    "volume_ratio": volume_ratio,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        close = features.get('close')
        high = features.get('high')
        low = features.get('low')
        volume_ratio = features.get('volume_ratio')

        if close is None or high is None or low is None or volume_ratio is None:
            return None

        range_high = features.get('range_high')
        range_low = features.get('range_low')

        if range_high is None or range_low is None:
            return None

        volume_ratio_threshold = getattr(self, 'params', {}).get(
            'volume_ratio_threshold', self.volume_ratio_threshold
        )

        if close > range_high and volume_ratio >= volume_ratio_threshold:
            breakout_magnitude = (close - range_high) / range_high if range_high > 0 else 0
            confidence = min(0.9, breakout_magnitude * 50 + (volume_ratio / volume_ratio_threshold) * 0.3)

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"向上突破: 价格={close:.2f}, 区间高点={range_high:.2f}, 成交量比={volume_ratio:.2f}"
            }

        if close < range_low and volume_ratio >= volume_ratio_threshold:
            breakout_magnitude = (range_low - close) / range_low if range_low > 0 else 0
            confidence = min(0.9, breakout_magnitude * 50 + (volume_ratio / volume_ratio_threshold) * 0.3)

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"向下突破: 价格={close:.2f}, 区间低点={range_low:.2f}, 成交量比={volume_ratio:.2f}"
            }

        return None


class TrendFollowingStrategy(BaseStrategy):
    """
    趋势跟踪策略

    核心逻辑：EMA10 > EMA50 且两者上升 → 做多；EMA10 < EMA50 且两者下降 → 做空
    """

    def __init__(
        self,
        strategy_id: str = "trend_following",
        fast_period: int = 10,
        slow_period: int = 50,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.default_quantity = default_quantity

        self._ema_fast_prev = None
        self._ema_slow_prev = None

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
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.slow_period + 2:
            return None

        current_price = close_prices[-1]

        prices_np = np.array(close_prices)
        ema_fast_full = self._calculate_ema(prices_np, self.fast_period)
        ema_slow_full = self._calculate_ema(prices_np, self.slow_period)

        ema_fast = ema_fast_full[-1]
        ema_fast_prev = ema_fast_full[-2]
        ema_slow = ema_slow_full[-1]
        ema_slow_prev = ema_slow_full[-2]

        signal = None

        if (self._ema_fast_prev is not None and
            self._ema_slow_prev is not None):

            ema_separation = abs(ema_fast - ema_slow) / current_price

            if (ema_fast > ema_slow and
                ema_fast > self._ema_fast_prev and
                ema_slow > self._ema_slow_prev):
                confidence = min(0.9, ema_separation * 200 + 0.4)

                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"上升趋势: EMA{self.fast_period}={ema_fast:.2f} > EMA{self.slow_period}={ema_slow:.2f}, 均线上升",
                    metadata={
                        "ema_fast": ema_fast,
                        "ema_slow": ema_slow,
                        "ema_separation": ema_separation,
                    },
                )

            elif (ema_fast < ema_slow and
                  ema_fast < self._ema_fast_prev and
                  ema_slow < self._ema_slow_prev):
                confidence = min(0.9, ema_separation * 200 + 0.4)

                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"下降趋势: EMA{self.fast_period}={ema_fast:.2f} < EMA{self.slow_period}={ema_slow:.2f}, 均线下降",
                    metadata={
                        "ema_fast": ema_fast,
                        "ema_slow": ema_slow,
                        "ema_separation": ema_separation,
                    },
                )

        self._ema_fast_prev = ema_fast
        self._ema_slow_prev = ema_slow

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        ema_fast = features.get('ema_fast')
        ema_slow = features.get('ema_slow')

        if ema_fast is None or ema_slow is None:
            return None

        if self._ema_fast_prev is None or self._ema_slow_prev is None:
            self._ema_fast_prev = ema_fast
            self._ema_slow_prev = ema_slow
            return None

        if ema_fast > ema_slow and ema_fast > self._ema_fast_prev and ema_slow > self._ema_slow_prev:
            ema_separation = abs(ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0
            confidence = min(0.9, ema_separation * 200 + 0.4)

            self._ema_fast_prev = ema_fast
            self._ema_slow_prev = ema_slow

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"上升趋势: EMA{self.fast_period}={ema_fast:.2f} > EMA{self.slow_period}={ema_slow:.2f}, 均线上升"
            }

        elif ema_fast < ema_slow and ema_fast < self._ema_fast_prev and ema_slow < self._ema_slow_prev:
            ema_separation = abs(ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0
            confidence = min(0.9, ema_separation * 200 + 0.4)

            self._ema_fast_prev = ema_fast
            self._ema_slow_prev = ema_slow

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"下降趋势: EMA{self.fast_period}={ema_fast:.2f} < EMA{self.slow_period}={ema_slow:.2f}, 均线下降"
            }

        self._ema_fast_prev = ema_fast
        self._ema_slow_prev = ema_slow

        return None


class VolatilityExpansionStrategy(BaseStrategy):
    """
    波动率扩张策略

    核心逻辑：ATR扩张（当前ATR > 1.5x均值ATR）且价格接近区间边缘 → 跟随突破方向
    """

    def __init__(
        self,
        strategy_id: str = "volatility_expansion",
        atr_period: int = 14,
        atr_expansion_ratio: float = 1.5,
        lookback: int = 48,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.atr_period = atr_period
        self.atr_expansion_ratio = atr_expansion_ratio
        self.lookback = lookback
        self.default_quantity = default_quantity

    def _calculate_atr(self, high_prices: List[float], low_prices: List[float], close_prices: List[float]) -> List[float]:
        """计算 ATR 序列"""
        if len(high_prices) < self.atr_period + 1:
            return []

        tr_list = []
        for i in range(1, len(high_prices)):
            tr = max(
                high_prices[i] - low_prices[i],
                abs(high_prices[i] - close_prices[i - 1]),
                abs(low_prices[i] - close_prices[i - 1]),
            )
            tr_list.append(tr)

        if len(tr_list) < self.atr_period:
            return []

        atr_values = []
        first_atr = np.mean(tr_list[:self.atr_period])
        atr_values.append(first_atr)

        for i in range(self.atr_period, len(tr_list)):
            current_atr = (atr_values[-1] * (self.atr_period - 1) + tr_list[i]) / self.atr_period
            atr_values.append(current_atr)

        return atr_values

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.lookback + self.atr_period + 1:
            return None

        current_price = close_prices[-1]

        atr_values = self._calculate_atr(high_prices, low_prices, close_prices)
        if len(atr_values) < self.atr_period:
            return None

        current_atr = atr_values[-1]
        avg_atr = np.mean(atr_values[-self.atr_period:])

        if avg_atr <= 0:
            return None

        atr_ratio = current_atr / avg_atr

        if atr_ratio < self.atr_expansion_ratio:
            return None

        range_high = max(high_prices[-self.lookback:])
        range_low = min(low_prices[-self.lookback:])
        range_mid = (range_high + range_low) / 2
        range_size = range_high - range_low

        if range_size <= 0:
            return None

        price_position = (current_price - range_mid) / (range_size / 2)

        signal = None

        if price_position > 0.5:
            confidence = min(0.9, (atr_ratio / self.atr_expansion_ratio) * 0.4 + price_position * 0.4 + 0.1)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"波动率扩张向上: ATR比={atr_ratio:.2f}, 价格位置={price_position:.2f}",
                metadata={
                    "current_atr": current_atr,
                    "avg_atr": avg_atr,
                    "atr_ratio": atr_ratio,
                    "price_position": price_position,
                },
            )
        elif price_position < -0.5:
            confidence = min(0.9, (atr_ratio / self.atr_expansion_ratio) * 0.4 + abs(price_position) * 0.4 + 0.1)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"波动率扩张向下: ATR比={atr_ratio:.2f}, 价格位置={price_position:.2f}",
                metadata={
                    "current_atr": current_atr,
                    "avg_atr": avg_atr,
                    "atr_ratio": atr_ratio,
                    "price_position": price_position,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        atr_ratio = features.get('atr_ratio')
        price_position = features.get('price_position')
        close = features.get('close')

        if atr_ratio is None or price_position is None:
            return None

        atr_expansion_ratio = getattr(self, 'params', {}).get(
            'atr_expansion_ratio', self.atr_expansion_ratio
        )

        if atr_ratio < atr_expansion_ratio:
            return None

        if price_position > 0.5:
            confidence = min(0.9, (atr_ratio / atr_expansion_ratio) * 0.4 + price_position * 0.4 + 0.1)
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"波动率扩张向上: ATR比={atr_ratio:.2f}, 价格位置={price_position:.2f}"
            }

        if price_position < -0.5:
            confidence = min(0.9, (atr_ratio / atr_expansion_ratio) * 0.4 + abs(price_position) * 0.4 + 0.1)
            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"波动率扩张向下: ATR比={atr_ratio:.2f}, 价格位置={price_position:.2f}"
            }

        return None


class BBCompressionBreakoutStrategy(BaseStrategy):
    """
    布林带压缩突破策略

    核心逻辑：BB带宽压缩后价格突破中轨 → 跟随突破方向
    """

    def __init__(
        self,
        strategy_id: str = "bb_compression_breakout",
        bb_period: int = 20,
        bb_std: float = 2.0,
        compression_threshold: float = 0.02,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.compression_threshold = compression_threshold
        self.default_quantity = default_quantity

        self._prev_above_middle = None

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        bb_upper = data.get("bb_upper", None)
        bb_lower = data.get("bb_lower", None)
        bb_middle = data.get("bb_middle", None)

        if len(close_prices) < self.bb_period:
            return None

        current_price = close_prices[-1]

        if bb_upper is None or bb_lower is None or bb_middle is None:
            if len(close_prices) < self.bb_period:
                return None

            recent = np.array(close_prices[-self.bb_period:])
            bb_middle = np.mean(recent)
            bb_std_val = np.std(recent)
            bb_upper = bb_middle + self.bb_std * bb_std_val
            bb_lower = bb_middle - self.bb_std * bb_std_val

        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 1.0

        if bb_width >= self.compression_threshold:
            self._prev_above_middle = current_price > bb_middle
            return None

        currently_above_middle = current_price > bb_middle

        signal = None

        if self._prev_above_middle is not None:
            compression_degree = (self.compression_threshold - bb_width) / self.compression_threshold

            if not self._prev_above_middle and currently_above_middle:
                breakout_strength = (current_price - bb_middle) / bb_middle if bb_middle > 0 else 0
                confidence = min(0.9, compression_degree * 0.5 + breakout_strength * 100 + 0.3)

                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"BB压缩向上突破: 带宽={bb_width:.4f}, 压缩度={compression_degree:.2f}",
                    metadata={
                        "bb_width": bb_width,
                        "bb_upper": bb_upper,
                        "bb_lower": bb_lower,
                        "bb_middle": bb_middle,
                        "compression_degree": compression_degree,
                    },
                )

            elif self._prev_above_middle and not currently_above_middle:
                breakout_strength = (bb_middle - current_price) / bb_middle if bb_middle > 0 else 0
                confidence = min(0.9, compression_degree * 0.5 + breakout_strength * 100 + 0.3)

                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"BB压缩向下突破: 带宽={bb_width:.4f}, 压缩度={compression_degree:.2f}",
                    metadata={
                        "bb_width": bb_width,
                        "bb_upper": bb_upper,
                        "bb_lower": bb_lower,
                        "bb_middle": bb_middle,
                        "compression_degree": compression_degree,
                    },
                )

        self._prev_above_middle = currently_above_middle

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        bb_upper = features.get('bb_upper')
        bb_lower = features.get('bb_lower')
        bb_middle = features.get('bb_middle')
        close = features.get('close')

        if bb_upper is None or bb_lower is None or bb_middle is None or close is None:
            return None

        compression_threshold = getattr(self, 'params', {}).get('compression_threshold', self.compression_threshold)

        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 1.0

        if bb_width >= compression_threshold:
            self._prev_above_middle = close > bb_middle
            return None

        currently_above_middle = close > bb_middle

        if self._prev_above_middle is None:
            self._prev_above_middle = currently_above_middle
            return None

        compression_degree = (compression_threshold - bb_width) / compression_threshold

        if not self._prev_above_middle and currently_above_middle:
            breakout_strength = (close - bb_middle) / bb_middle if bb_middle > 0 else 0
            confidence = min(0.9, compression_degree * 0.5 + breakout_strength * 100 + 0.3)

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"BB压缩向上突破: 带宽={bb_width:.4f}, 压缩度={compression_degree:.2f}"
            }

        elif self._prev_above_middle and not currently_above_middle:
            breakout_strength = (bb_middle - close) / bb_middle if bb_middle > 0 else 0
            confidence = min(0.9, compression_degree * 0.5 + breakout_strength * 100 + 0.3)

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"BB压缩向下突破: 带宽={bb_width:.4f}, 压缩度={compression_degree:.2f}"
            }

        self._prev_above_middle = currently_above_middle

        return None


class MomentumIgnitionStrategy(BaseStrategy):
    """
    动量点火策略

    核心逻辑：成交量急放（>3x均值）+ 价格大幅移动（1h涨跌幅>1%）→ 跟随动量方向
    """

    def __init__(
        self,
        strategy_id: str = "momentum_ignition",
        volume_spike_ratio: float = 3.0,
        return_threshold: float = 0.01,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.volume_spike_ratio = volume_spike_ratio
        self.return_threshold = return_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 12:
            return None

        current_price = close_prices[-1]

        price_1h_ago = close_prices[-12]
        return_1h = (current_price - price_1h_ago) / price_1h_ago

        if len(volumes) >= 288:
            avg_volume = np.mean(volumes[-288:])
            volume_spike = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_spike = 1.0

        signal = None

        if volume_spike >= self.volume_spike_ratio and return_1h >= self.return_threshold:
            confidence = min(0.9, (
                (volume_spike / self.volume_spike_ratio) * 0.4 +
                (return_1h / self.return_threshold) * 0.4 + 0.1
            ))

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"动量点火做多: 成交量急放={volume_spike:.2f}x, 1h涨幅={return_1h*100:.2f}%",
                metadata={
                    "volume_spike": volume_spike,
                    "return_1h": return_1h,
                },
            )
        elif volume_spike >= self.volume_spike_ratio and return_1h <= -self.return_threshold:
            confidence = min(0.9, (
                (volume_spike / self.volume_spike_ratio) * 0.4 +
                (abs(return_1h) / self.return_threshold) * 0.4 + 0.1
            ))

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"动量点火做空: 成交量急放={volume_spike:.2f}x, 1h跌幅={return_1h*100:.2f}%",
                metadata={
                    "volume_spike": volume_spike,
                    "return_1h": return_1h,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        volume_ratio = features.get('volume_ratio')
        return_1h = features.get('return_1h')

        if volume_ratio is None or return_1h is None:
            return None

        volume_spike_ratio = getattr(self, 'params', {}).get('volume_spike_ratio', self.volume_spike_ratio)
        return_threshold = getattr(self, 'params', {}).get('return_threshold', self.return_threshold)

        if volume_ratio >= volume_spike_ratio and return_1h >= return_threshold:
            confidence = min(0.9, (
                (volume_ratio / volume_spike_ratio) * 0.4 +
                (return_1h / return_threshold) * 0.4 + 0.1
            ))
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"动量点火做多: 成交量急放={volume_ratio:.2f}x, 1h涨幅={return_1h*100:.2f}%"
            }
        elif volume_ratio >= volume_spike_ratio and return_1h <= -return_threshold:
            confidence = min(0.9, (
                (volume_ratio / volume_spike_ratio) * 0.4 +
                (abs(return_1h) / return_threshold) * 0.4 + 0.1
            ))
            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"动量点火做空: 成交量急放={volume_ratio:.2f}x, 1h跌幅={return_1h*100:.2f}%"
            }

        return None


class ImbalancePressureStrategy(BaseStrategy):
    """
    订单簿失衡压力策略

    检测条件：
    - 订单簿买卖失衡预测短期方向
    - imbalance_5 > 0.3 (买盘偏重) 且 microprice > mid_price → 做多
    - imbalance_5 < -0.3 (卖盘偏重) 且 microprice < mid_price → 做空
    """

    def __init__(
        self,
        strategy_id: str = "imbalance_pressure",
        imbalance_threshold: float = 0.3,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.imbalance_threshold = imbalance_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        imbalance_1 = data.get("imbalance_1", 0.0)
        imbalance_5 = data.get("imbalance_5", 0.0)
        depth_ratio = data.get("depth_ratio", 1.0)
        microprice = data.get("microprice", 0.0)
        mid_price = data.get("mid_price", 0.0)
        symbol = data.get("symbol", "BTCUSDT")

        if mid_price == 0.0:
            return None

        current_price = data.get("current_price", mid_price)

        signal = None

        if imbalance_5 > self.imbalance_threshold and microprice > mid_price:
            imbalance_strength = (imbalance_5 - self.imbalance_threshold) / (1.0 - self.imbalance_threshold)
            depth_confirm = min(depth_ratio / 2.0, 1.0)
            confidence = min(0.9, imbalance_strength * 0.6 + depth_confirm * 0.3 + 0.1)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"订单簿买盘失衡: imbalance_5={imbalance_5:.3f}, microprice偏移={((microprice - mid_price) / mid_price) * 100:.4f}%",
                metadata={
                    "imbalance_1": imbalance_1,
                    "imbalance_5": imbalance_5,
                    "depth_ratio": depth_ratio,
                    "microprice": microprice,
                    "mid_price": mid_price,
                },
            )

        elif imbalance_5 < -self.imbalance_threshold and microprice < mid_price:
            imbalance_strength = (abs(imbalance_5) - self.imbalance_threshold) / (1.0 - self.imbalance_threshold)
            depth_confirm = min(depth_ratio / 2.0, 1.0)
            confidence = min(0.9, imbalance_strength * 0.6 + depth_confirm * 0.3 + 0.1)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"订单簿卖盘失衡: imbalance_5={imbalance_5:.3f}, microprice偏移={((microprice - mid_price) / mid_price) * 100:.4f}%",
                metadata={
                    "imbalance_1": imbalance_1,
                    "imbalance_5": imbalance_5,
                    "depth_ratio": depth_ratio,
                    "microprice": microprice,
                    "mid_price": mid_price,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        imbalance_5 = features.get('imbalance_5')
        microprice = features.get('microprice')
        mid_price = features.get('mid_price')

        if imbalance_5 is None or microprice is None or mid_price is None:
            return None

        if mid_price == 0:
            return None

        imbalance_threshold = self.params.get('imbalance_threshold', self.imbalance_threshold) if hasattr(self, 'params') else self.imbalance_threshold

        if imbalance_5 > imbalance_threshold and microprice > mid_price:
            imbalance_strength = (imbalance_5 - imbalance_threshold) / (1.0 - imbalance_threshold)
            confidence = min(0.9, imbalance_strength * 0.7 + 0.2)

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"订单簿买盘失衡: imbalance_5={imbalance_5:.3f}, microprice偏移={((microprice - mid_price) / mid_price) * 100:.4f}%"
            }

        elif imbalance_5 < -imbalance_threshold and microprice < mid_price:
            imbalance_strength = (abs(imbalance_5) - imbalance_threshold) / (1.0 - imbalance_threshold)
            confidence = min(0.9, imbalance_strength * 0.7 + 0.2)

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"订单簿卖盘失衡: imbalance_5={imbalance_5:.3f}, microprice偏移={((microprice - mid_price) / mid_price) * 100:.4f}%"
            }

        return None


class SweepDetectionStrategy(BaseStrategy):
    """
    扫单检测策略

    检测条件：
    - 大单扫穿订单簿
    - sweep_buy_score > 0.7 → 做多 (买方扫单)
    - sweep_sell_score > 0.7 → 做空 (卖方扫单)
    """

    def __init__(
        self,
        strategy_id: str = "sweep_detection",
        sweep_threshold: float = 0.7,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.sweep_threshold = sweep_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        trade_delta = data.get("trade_delta", 0.0)
        sweep_buy_score = data.get("sweep_buy_score", 0.0)
        sweep_sell_score = data.get("sweep_sell_score", 0.0)
        liquidity_vacuum = data.get("liquidity_vacuum", 0.0)
        symbol = data.get("symbol", "BTCUSDT")
        current_price = data.get("current_price", 0.0)

        signal = None

        if sweep_buy_score > self.sweep_threshold:
            sweep_strength = (sweep_buy_score - self.sweep_threshold) / (1.0 - self.sweep_threshold)
            delta_confirm = min(abs(trade_delta) / 100.0, 1.0)
            vacuum_boost = min(liquidity_vacuum, 1.0)
            confidence = min(0.9, sweep_strength * 0.5 + delta_confirm * 0.25 + vacuum_boost * 0.15 + 0.1)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"买方扫单: sweep_buy_score={sweep_buy_score:.3f}, trade_delta={trade_delta:.1f}, liquidity_vacuum={liquidity_vacuum:.3f}",
                metadata={
                    "trade_delta": trade_delta,
                    "sweep_buy_score": sweep_buy_score,
                    "sweep_sell_score": sweep_sell_score,
                    "liquidity_vacuum": liquidity_vacuum,
                },
            )

        elif sweep_sell_score > self.sweep_threshold:
            sweep_strength = (sweep_sell_score - self.sweep_threshold) / (1.0 - self.sweep_threshold)
            delta_confirm = min(abs(trade_delta) / 100.0, 1.0)
            vacuum_boost = min(liquidity_vacuum, 1.0)
            confidence = min(0.9, sweep_strength * 0.5 + delta_confirm * 0.25 + vacuum_boost * 0.15 + 0.1)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"卖方扫单: sweep_sell_score={sweep_sell_score:.3f}, trade_delta={trade_delta:.1f}, liquidity_vacuum={liquidity_vacuum:.3f}",
                metadata={
                    "trade_delta": trade_delta,
                    "sweep_buy_score": sweep_buy_score,
                    "sweep_sell_score": sweep_sell_score,
                    "liquidity_vacuum": liquidity_vacuum,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        sweep_buy_score = features.get('sweep_buy_score')
        sweep_sell_score = features.get('sweep_sell_score')

        if sweep_buy_score is None or sweep_sell_score is None:
            return None

        sweep_threshold = getattr(self, 'params', {}).get('sweep_threshold', self.sweep_threshold)

        if sweep_buy_score > sweep_threshold:
            sweep_strength = (sweep_buy_score - sweep_threshold) / (1.0 - sweep_threshold) if sweep_threshold < 1.0 else sweep_buy_score
            confidence = min(0.9, sweep_strength * 0.7 + 0.2)

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"买方扫单: sweep_buy_score={sweep_buy_score:.3f} > {sweep_threshold}"
            }

        if sweep_sell_score > sweep_threshold:
            sweep_strength = (sweep_sell_score - sweep_threshold) / (1.0 - sweep_threshold) if sweep_threshold < 1.0 else sweep_sell_score
            confidence = min(0.9, sweep_strength * 0.7 + 0.2)

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"卖方扫单: sweep_sell_score={sweep_sell_score:.3f} > {sweep_threshold}"
            }

        return None


class LiquidityVacuumStrategy(BaseStrategy):
    """
    流动性真空突破策略

    检测条件：
    - 价差扩大 (spread > 2x均值) 且深度下降 (top5_depth下降) 且 cancel_rate高
    - 沿 trade_delta 方向突破
    """

    def __init__(
        self,
        strategy_id: str = "liquidity_vacuum",
        spread_expansion_factor: float = 2.0,
        cancel_rate_threshold: float = 0.3,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.spread_expansion_factor = spread_expansion_factor
        self.cancel_rate_threshold = cancel_rate_threshold
        self.default_quantity = default_quantity

        self._avg_spread = None
        self._prev_top5_depth = None

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        spread = data.get("spread", 0.0)
        spread_volatility = data.get("spread_volatility", 0.0)
        top5_depth = data.get("top5_depth", 0.0)
        cancel_rate = data.get("cancel_rate", 0.0)
        trade_delta = data.get("trade_delta", 0.0)
        symbol = data.get("symbol", "BTCUSDT")
        current_price = data.get("current_price", 0.0)

        if self._avg_spread is None:
            self._avg_spread = spread
            self._prev_top5_depth = top5_depth
            return None

        self._avg_spread = self._avg_spread * 0.95 + spread * 0.05

        spread_expansion = spread / self._avg_spread if self._avg_spread > 0 else 1.0

        depth_declining = False
        depth_decline_ratio = 0.0
        if self._prev_top5_depth is not None and self._prev_top5_depth > 0:
            depth_decline_ratio = (self._prev_top5_depth - top5_depth) / self._prev_top5_depth
            depth_declining = depth_decline_ratio > 0.1

        self._prev_top5_depth = top5_depth

        signal = None

        if spread_expansion >= self.spread_expansion_factor and depth_declining and cancel_rate >= self.cancel_rate_threshold:
            spread_score = min((spread_expansion - self.spread_expansion_factor) / self.spread_expansion_factor, 1.0)
            depth_score = min(depth_decline_ratio / 0.3, 1.0)
            cancel_score = min(cancel_rate / 0.5, 1.0)
            confidence = min(0.9, spread_score * 0.4 + depth_score * 0.3 + cancel_score * 0.2 + 0.1)

            action = ActionType.LONG if trade_delta > 0 else ActionType.SHORT

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=action,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"流动性真空突破: spread扩张={spread_expansion:.2f}x, 深度下降={depth_decline_ratio*100:.1f}%, cancel_rate={cancel_rate:.3f}, trade_delta={trade_delta:.1f}",
                metadata={
                    "spread": spread,
                    "spread_expansion": spread_expansion,
                    "spread_volatility": spread_volatility,
                    "top5_depth": top5_depth,
                    "depth_decline_ratio": depth_decline_ratio,
                    "cancel_rate": cancel_rate,
                    "trade_delta": trade_delta,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        spread = features.get('spread')
        top5_depth = features.get('top5_depth')
        cancel_rate = features.get('cancel_rate')
        trade_delta = features.get('trade_delta')

        if spread is None or top5_depth is None or cancel_rate is None or trade_delta is None:
            return None

        spread_expansion_factor = getattr(self, 'params', {}).get('spread_expansion_factor', self.spread_expansion_factor)
        cancel_rate_threshold = getattr(self, 'params', {}).get('cancel_rate_threshold', self.cancel_rate_threshold)

        if self._avg_spread is None:
            self._avg_spread = spread
            self._prev_top5_depth = top5_depth
            return None

        self._avg_spread = self._avg_spread * 0.95 + spread * 0.05

        spread_expansion = spread / self._avg_spread if self._avg_spread > 0 else 1.0

        depth_declining = False
        depth_decline_ratio = 0.0
        if self._prev_top5_depth is not None and self._prev_top5_depth > 0:
            depth_decline_ratio = (self._prev_top5_depth - top5_depth) / self._prev_top5_depth
            depth_declining = depth_decline_ratio > 0.1

        self._prev_top5_depth = top5_depth

        if spread_expansion >= spread_expansion_factor and depth_declining and cancel_rate >= cancel_rate_threshold:
            spread_score = min((spread_expansion - spread_expansion_factor) / spread_expansion_factor, 1.0)
            depth_score = min(depth_decline_ratio / 0.3, 1.0)
            cancel_score = min(cancel_rate / 0.5, 1.0)
            confidence = min(0.9, spread_score * 0.4 + depth_score * 0.3 + cancel_score * 0.2 + 0.1)

            if trade_delta > 0:
                signal_type = 'buy'
            else:
                signal_type = 'sell'

            return {
                'signal_type': signal_type,
                'confidence': confidence,
                'reason': f"流动性真空突破: spread扩张={spread_expansion:.2f}x, 深度下降={depth_decline_ratio*100:.1f}%, cancel_rate={cancel_rate:.3f}, trade_delta={trade_delta:.1f}"
            }

        return None


class AggressiveFlowStrategy(BaseStrategy):
    """
    激进流向策略

    检测条件：
    - 激进买量 > 2x 激进卖量 且 cumulative_delta 为正 → 做多
    - 激进卖量 > 2x 激进买量 且 cumulative_delta 为负 → 做空
    """

    def __init__(
        self,
        strategy_id: str = "aggressive_flow",
        flow_imbalance_threshold: float = 2.0,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.flow_imbalance_threshold = flow_imbalance_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        cumulative_delta = data.get("cumulative_delta", 0.0)
        aggressive_buy_volume = data.get("aggressive_buy_volume", 0.0)
        aggressive_sell_volume = data.get("aggressive_sell_volume", 0.0)
        symbol = data.get("symbol", "BTCUSDT")
        current_price = data.get("current_price", 0.0)

        signal = None

        if aggressive_sell_volume > 0:
            buy_sell_ratio = aggressive_buy_volume / aggressive_sell_volume
        else:
            buy_sell_ratio = float('inf') if aggressive_buy_volume > 0 else 1.0

        if aggressive_buy_volume > 0:
            sell_buy_ratio = aggressive_sell_volume / aggressive_buy_volume
        else:
            sell_buy_ratio = float('inf') if aggressive_sell_volume > 0 else 1.0

        if buy_sell_ratio >= self.flow_imbalance_threshold and cumulative_delta > 0:
            flow_imbalance = min((buy_sell_ratio - self.flow_imbalance_threshold) / self.flow_imbalance_threshold, 1.0)
            delta_alignment = min(abs(cumulative_delta) / 100.0, 1.0)
            confidence = min(0.9, flow_imbalance * 0.5 + delta_alignment * 0.3 + 0.2)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"激进买盘主导: 买/卖比={buy_sell_ratio:.2f}, cumulative_delta={cumulative_delta:.1f}",
                metadata={
                    "cumulative_delta": cumulative_delta,
                    "aggressive_buy_volume": aggressive_buy_volume,
                    "aggressive_sell_volume": aggressive_sell_volume,
                    "buy_sell_ratio": buy_sell_ratio,
                },
            )

        elif sell_buy_ratio >= self.flow_imbalance_threshold and cumulative_delta < 0:
            flow_imbalance = min((sell_buy_ratio - self.flow_imbalance_threshold) / self.flow_imbalance_threshold, 1.0)
            delta_alignment = min(abs(cumulative_delta) / 100.0, 1.0)
            confidence = min(0.9, flow_imbalance * 0.5 + delta_alignment * 0.3 + 0.2)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"激进卖盘主导: 卖/买比={sell_buy_ratio:.2f}, cumulative_delta={cumulative_delta:.1f}",
                metadata={
                    "cumulative_delta": cumulative_delta,
                    "aggressive_buy_volume": aggressive_buy_volume,
                    "aggressive_sell_volume": aggressive_sell_volume,
                    "sell_buy_ratio": sell_buy_ratio,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        cumulative_delta = features.get('cumulative_delta')
        aggressive_buy_volume = features.get('aggressive_buy_volume')
        aggressive_sell_volume = features.get('aggressive_sell_volume')

        if cumulative_delta is None or aggressive_buy_volume is None or aggressive_sell_volume is None:
            return None

        flow_imbalance_threshold = getattr(self, 'params', {}).get(
            'flow_imbalance_threshold', self.flow_imbalance_threshold
        )

        if aggressive_sell_volume > 0:
            buy_sell_ratio = aggressive_buy_volume / aggressive_sell_volume
        else:
            buy_sell_ratio = float('inf') if aggressive_buy_volume > 0 else 1.0

        if aggressive_buy_volume > 0:
            sell_buy_ratio = aggressive_sell_volume / aggressive_buy_volume
        else:
            sell_buy_ratio = float('inf') if aggressive_sell_volume > 0 else 1.0

        if buy_sell_ratio >= flow_imbalance_threshold and cumulative_delta > 0:
            flow_imbalance = min((buy_sell_ratio - flow_imbalance_threshold) / flow_imbalance_threshold, 1.0)
            delta_alignment = min(abs(cumulative_delta) / 100.0, 1.0)
            confidence = min(0.9, flow_imbalance * 0.5 + delta_alignment * 0.3 + 0.2)

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"激进买盘主导: 买/卖比={buy_sell_ratio:.2f}, cumulative_delta={cumulative_delta:.1f}"
            }

        elif sell_buy_ratio >= flow_imbalance_threshold and cumulative_delta < 0:
            flow_imbalance = min((sell_buy_ratio - flow_imbalance_threshold) / flow_imbalance_threshold, 1.0)
            delta_alignment = min(abs(cumulative_delta) / 100.0, 1.0)
            confidence = min(0.9, flow_imbalance * 0.5 + delta_alignment * 0.3 + 0.2)

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"激进卖盘主导: 卖/买比={sell_buy_ratio:.2f}, cumulative_delta={cumulative_delta:.1f}"
            }

        return None


class LeadLagStrategy(BaseStrategy):
    """
    跨交易所领先滞后策略

    检测条件：
    - Binance 1h收益率 > OKX 1h收益率 + 阈值 → OKX将追赶，做多
    - Binance 1h收益率 < OKX 1h收益率 - 阈值 → OKX将追赶，做空
    - Binance领先，OKX跟随
    """

    def __init__(
        self,
        strategy_id: str = "lead_lag",
        divergence_threshold: float = 0.005,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.divergence_threshold = divergence_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        binance_return = data.get("binance_return", 0.0)
        okx_return = data.get("okx_return", 0.0)
        latency_delta = data.get("latency_delta", 0.0)
        symbol = data.get("symbol", "BTCUSDT")
        current_price = data.get("current_price", 0.0)

        return_divergence = binance_return - okx_return

        signal = None

        if return_divergence > self.divergence_threshold:
            divergence_magnitude = (return_divergence - self.divergence_threshold) / self.divergence_threshold
            consistency = min(abs(latency_delta) / 1000.0, 1.0)
            confidence = min(0.9, divergence_magnitude * 0.5 + consistency * 0.3 + 0.2)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"领先滞后做多: Binance领先, 收益率差={return_divergence*100:.3f}%, 延迟差={latency_delta:.1f}ms",
                metadata={
                    "binance_return": binance_return,
                    "okx_return": okx_return,
                    "return_divergence": return_divergence,
                    "latency_delta": latency_delta,
                },
            )

        elif return_divergence < -self.divergence_threshold:
            divergence_magnitude = (abs(return_divergence) - self.divergence_threshold) / self.divergence_threshold
            consistency = min(abs(latency_delta) / 1000.0, 1.0)
            confidence = min(0.9, divergence_magnitude * 0.5 + consistency * 0.3 + 0.2)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"领先滞后做空: Binance领跌, 收益率差={return_divergence*100:.3f}%, 延迟差={latency_delta:.1f}ms",
                metadata={
                    "binance_return": binance_return,
                    "okx_return": okx_return,
                    "return_divergence": return_divergence,
                    "latency_delta": latency_delta,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        binance_return = features.get('binance_return')
        okx_return = features.get('okx_return')

        if binance_return is None or okx_return is None:
            return None

        threshold = self.params.get('divergence_threshold', self.divergence_threshold) if hasattr(self, 'params') else self.divergence_threshold

        return_diff = binance_return - okx_return

        if return_diff > threshold:
            divergence_magnitude = (return_diff - threshold) / threshold
            confidence = min(0.9, divergence_magnitude * 0.7 + 0.2)
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"领先滞后做多: Binance领先, 收益率差={return_diff*100:.3f}%, threshold={threshold*100:.3f}%"
            }

        elif return_diff < -threshold:
            divergence_magnitude = (abs(return_diff) - threshold) / threshold
            confidence = min(0.9, divergence_magnitude * 0.7 + 0.2)
            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"领先滞后做空: Binance领跌, 收益率差={return_diff*100:.3f}%, threshold={threshold*100:.3f}%"
            }

        return None


class PremiumDivergenceStrategy(BaseStrategy):
    """
    跨交易所溢价背离策略

    检测条件：
    - 溢价 > 阈值(0.5%) → 贵的交易所价格将回归，做空
    - 溢价 < -阈值 → 便宜的交易所价格将回归，做多
    - 溢价将正常化
    """

    def __init__(
        self,
        strategy_id: str = "premium_divergence",
        premium_threshold: float = 0.005,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.premium_threshold = premium_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        basis = data.get("basis", 0.0)
        premium = data.get("premium", 0.0)
        spread_cross_exchange = data.get("spread_cross_exchange", 0.0)
        symbol = data.get("symbol", "BTCUSDT")
        current_price = data.get("current_price", 0.0)

        signal = None

        if premium > self.premium_threshold:
            premium_magnitude = (premium - self.premium_threshold) / self.premium_threshold
            basis_alignment = min(abs(basis) / 0.01, 1.0)
            confidence = min(0.9, premium_magnitude * 0.5 + basis_alignment * 0.3 + 0.2)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"溢价背离做空: 溢价={premium*100:.3f}%, 基差={basis*100:.3f}%, 跨所价差={spread_cross_exchange*100:.3f}%",
                metadata={
                    "basis": basis,
                    "premium": premium,
                    "spread_cross_exchange": spread_cross_exchange,
                },
            )

        elif premium < -self.premium_threshold:
            premium_magnitude = (abs(premium) - self.premium_threshold) / self.premium_threshold
            basis_alignment = min(abs(basis) / 0.01, 1.0)
            confidence = min(0.9, premium_magnitude * 0.5 + basis_alignment * 0.3 + 0.2)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.MULTI_FACTOR,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"溢价背离做多: 溢价={premium*100:.3f}%, 基差={basis*100:.3f}%, 跨所价差={spread_cross_exchange*100:.3f}%",
                metadata={
                    "basis": basis,
                    "premium": premium,
                    "spread_cross_exchange": spread_cross_exchange,
                },
            )
        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        premium = features.get('premium')
        basis = features.get('basis')
        spread = features.get('spread')

        if premium is None:
            return None

        premium_threshold = self.params.get('premium_threshold', self.premium_threshold) if hasattr(self, 'params') else self.premium_threshold

        if premium > premium_threshold:
            premium_magnitude = (premium - premium_threshold) / premium_threshold if premium_threshold > 0 else 0
            basis_alignment = min(abs(basis) / 0.01, 1.0) if basis is not None else 0.5
            confidence = min(0.9, premium_magnitude * 0.5 + basis_alignment * 0.3 + 0.2)

            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"溢价背离做空: 溢价={premium*100:.3f}%, 基差={basis*100:.3f}%",
                'metadata': {
                    'premium': premium,
                    'basis': basis,
                    'spread': spread,
                }
            }

        elif premium < -premium_threshold:
            premium_magnitude = (abs(premium) - premium_threshold) / premium_threshold if premium_threshold > 0 else 0
            basis_alignment = min(abs(basis) / 0.01, 1.0) if basis is not None else 0.5
            confidence = min(0.9, premium_magnitude * 0.5 + basis_alignment * 0.3 + 0.2)

            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"溢价背离做多: 溢价={premium*100:.3f}%, 基差={basis*100:.3f}%",
                'metadata': {
                    'premium': premium,
                    'basis': basis,
                    'spread': spread,
                }
            }

        return None


class SMACrossoverStrategy(BaseStrategy):
    """
    SMA交叉策略
    
    核心逻辑：
    - 短期SMA上穿长期SMA → 做多
    - 短期SMA下穿长期SMA → 做空
    """

    def __init__(
        self,
        strategy_id: str = "sma_crossover",
        fast_period: int = 10,
        slow_period: int = 20,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.default_quantity = default_quantity
        self._fast_prev = None
        self._slow_prev = None

    def _calculate_sma(self, prices: list, period: int) -> float:
        """计算简单移动平均"""
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < max(self.fast_period, self.slow_period) + 1:
            return None

        current_price = close_prices[-1]

        fast_sma = self._calculate_sma(close_prices, self.fast_period)
        slow_sma = self._calculate_sma(close_prices, self.slow_period)

        signal = None

        if self._fast_prev is not None and self._slow_prev is not None:
            # 金叉：快线上穿慢线
            if self._fast_prev <= self._slow_prev and fast_sma > slow_sma:
                confidence = min(0.9, 0.5 + (fast_sma - slow_sma) / slow_sma * 2)
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"SMA金叉: SMA{self.fast_period}={fast_sma:.2f} > SMA{self.slow_period}={slow_sma:.2f}",
                    metadata={
                        "fast_sma": fast_sma,
                        "slow_sma": slow_sma,
                        "fast_period": self.fast_period,
                        "slow_period": self.slow_period,
                    },
                )
            # 死叉：快线下穿慢线
            elif self._fast_prev >= self._slow_prev and fast_sma < slow_sma:
                confidence = min(0.9, 0.5 + (slow_sma - fast_sma) / slow_sma * 2)
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"SMA死叉: SMA{self.fast_period}={fast_sma:.2f} < SMA{self.slow_period}={slow_sma:.2f}",
                    metadata={
                        "fast_sma": fast_sma,
                        "slow_sma": slow_sma,
                        "fast_period": self.fast_period,
                        "slow_period": self.slow_period,
                    },
                )

        self._fast_prev = fast_sma
        self._slow_prev = slow_sma

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）- 直接从features获取特征"""
        if not self._enabled:
            return None

        sma_fast = features.get('sma_fast')
        sma_slow = features.get('sma_slow')

        if sma_fast is None or sma_slow is None:
            return None

        if self._fast_prev is None or self._slow_prev is None:
            self._fast_prev = sma_fast
            self._slow_prev = sma_slow
            return None

        if sma_fast > sma_slow and self._fast_prev <= self._slow_prev:
            confidence = min(0.9, 0.5 + (sma_fast - sma_slow) / sma_slow * 2)
            self._fast_prev = sma_fast
            self._slow_prev = sma_slow
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"SMA金叉: SMA{self.fast_period}={sma_fast:.2f} > SMA{self.slow_period}={sma_slow:.2f}"
            }
        elif sma_fast < sma_slow and self._fast_prev >= self._slow_prev:
            confidence = min(0.9, 0.5 + (sma_slow - sma_fast) / sma_slow * 2)
            self._fast_prev = sma_fast
            self._slow_prev = sma_slow
            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"SMA死叉: SMA{self.fast_period}={sma_fast:.2f} < SMA{self.slow_period}={sma_slow:.2f}"
            }

        self._fast_prev = sma_fast
        self._slow_prev = sma_slow

        return None


class EMACrossoverStrategy(BaseStrategy):
    """
    EMA交叉策略
    
    核心逻辑：
    - 短期EMA上穿长期EMA → 做多
    - 短期EMA下穿长期EMA → 做空
    """

    def __init__(
        self,
        strategy_id: str = "ema_crossover",
        fast_period: int = 10,
        slow_period: int = 20,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.default_quantity = default_quantity
        self._fast_prev = None
        self._slow_prev = None

    def _calculate_ema(self, prices: list, period: int) -> float:
        """计算指数移动平均"""
        if len(prices) < period:
            return 0.0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < max(self.fast_period, self.slow_period) + 1:
            return None

        current_price = close_prices[-1]

        fast_ema = self._calculate_ema(close_prices, self.fast_period)
        slow_ema = self._calculate_ema(close_prices, self.slow_period)

        signal = None

        if self._fast_prev is not None and self._slow_prev is not None:
            # 金叉：快线上穿慢线
            if self._fast_prev <= self._slow_prev and fast_ema > slow_ema:
                confidence = min(0.9, 0.5 + (fast_ema - slow_ema) / slow_ema * 2)
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"EMA金叉: EMA{self.fast_period}={fast_ema:.2f} > EMA{self.slow_period}={slow_ema:.2f}",
                    metadata={
                        "fast_ema": fast_ema,
                        "slow_ema": slow_ema,
                        "fast_period": self.fast_period,
                        "slow_period": self.slow_period,
                    },
                )
            # 死叉：快线下穿慢线
            elif self._fast_prev >= self._slow_prev and fast_ema < slow_ema:
                confidence = min(0.9, 0.5 + (slow_ema - fast_ema) / slow_ema * 2)
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"EMA死叉: EMA{self.fast_period}={fast_ema:.2f} < EMA{self.slow_period}={slow_ema:.2f}",
                    metadata={
                        "fast_ema": fast_ema,
                        "slow_ema": slow_ema,
                        "fast_period": self.fast_period,
                        "slow_period": self.slow_period,
                    },
                )

        self._fast_prev = fast_ema
        self._slow_prev = slow_ema

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """基于特征生成交易信号"""
        if not self._enabled:
            return None

        ema_fast = features.get('ema_fast')
        ema_slow = features.get('ema_slow')
        symbol = features.get('symbol', 'BTCUSDT')
        price = features.get('close', features.get('price', 0))

        if ema_fast is None or ema_slow is None:
            return None

        action = None
        if ema_fast > ema_slow:
            action = ActionType.LONG
        elif ema_fast < ema_slow:
            action = ActionType.SHORT

        if action is None:
            return None

        confidence = min(0.9, 0.5 + abs(ema_fast - ema_slow) / ema_slow * 2)

        return {
            'strategy_id': self.strategy_id,
            'action': action,
            'quantity': self.default_quantity,
            'price': price,
            'confidence': confidence,
            'symbol': symbol,
            'reason': f"EMA交叉: EMA{self.fast_period}={ema_fast:.2f} vs EMA{self.slow_period}={ema_slow:.2f}",
            'metadata': {
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'fast_period': self.fast_period,
                'slow_period': self.slow_period,
            }
        }


class BollingerBandsStrategy(BaseStrategy):
    """
    布林带策略
    
    核心逻辑：
    - 价格跌破下轨 → 超卖，做多
    - 价格突破上轨 → 超买，做空
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
        self._price_prev = None

    def _calculate_bollinger_bands(self, prices: list) -> tuple:
        """计算布林带"""
        if len(prices) < self.period:
            return (0.0, 0.0, 0.0)
        
        recent_prices = np.array(prices[-self.period:])
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        upper = middle + self.std_dev * std
        lower = middle - self.std_dev * std
        return (upper, middle, lower)

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.period + 1:
            return None

        current_price = close_prices[-1]
        upper, middle, lower = self._calculate_bollinger_bands(close_prices)

        signal = None

        if self._price_prev is not None:
            # 价格跌破下轨（超卖）→ 做多
            if self._price_prev > lower and current_price <= lower:
                confidence = min(0.9, 0.5 + (lower - current_price) / lower)
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"布林带跌破下轨: 价格={current_price:.2f}, 下轨={lower:.2f}",
                    metadata={
                        "upper": upper,
                        "middle": middle,
                        "lower": lower,
                        "period": self.period,
                        "std_dev": self.std_dev,
                    },
                )
            # 价格突破上轨（超买）→ 做空
            elif self._price_prev < upper and current_price >= upper:
                confidence = min(0.9, 0.5 + (current_price - upper) / upper)
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.TECHNICAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"布林带突破上轨: 价格={current_price:.2f}, 上轨={upper:.2f}",
                    metadata={
                        "upper": upper,
                        "middle": middle,
                        "lower": lower,
                        "period": self.period,
                        "std_dev": self.std_dev,
                    },
                )

        self._price_prev = current_price

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从特征数据生成交易信号"""
        if not self._enabled:
            return None

        close = features.get('close')
        bb_upper = features.get('bb_upper')
        bb_lower = features.get('bb_lower')

        if close is None or bb_upper is None or bb_lower is None:
            return None

        signal = None

        if self._price_prev is not None:
            if self._price_prev > bb_lower and close <= bb_lower:
                confidence = min(0.9, 0.5 + (bb_lower - close) / bb_lower)
                signal = {
                    'signal_type': 'buy',
                    'confidence': confidence,
                    'reason': f"布林带跌破下轨: 价格={close:.2f}, 下轨={bb_lower:.2f}",
                    'metadata': {
                        'bb_upper': bb_upper,
                        'bb_lower': bb_lower,
                        'period': self.period,
                        'std_dev': self.std_dev,
                    }
                }
            elif self._price_prev < bb_upper and close >= bb_upper:
                confidence = min(0.9, 0.5 + (close - bb_upper) / bb_upper)
                signal = {
                    'signal_type': 'sell',
                    'confidence': confidence,
                    'reason': f"布林带突破上轨: 价格={close:.2f}, 上轨={bb_upper:.2f}",
                    'metadata': {
                        'bb_upper': bb_upper,
                        'bb_lower': bb_lower,
                        'period': self.period,
                        'std_dev': self.std_dev,
                    }
                }

        self._price_prev = close

        return signal


class MomentumStrategy(BaseStrategy):
    """
    动量策略
    
    核心逻辑：
    - 价格在N期内涨幅超过阈值 → 做多
    - 价格在N期内跌幅超过阈值 → 做空
    """

    def __init__(
        self,
        strategy_id: str = "momentum",
        period: int = 10,
        threshold: float = 0.02,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.period = period
        self.threshold = threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.period + 1:
            return None

        current_price = close_prices[-1]
        prev_price = close_prices[-(self.period + 1)]
        price_change = (current_price - prev_price) / prev_price

        signal = None

        if price_change > self.threshold:
            confidence = min(0.9, 0.5 + price_change / self.threshold * 0.4)
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"动量向上: {self.period}期涨幅={price_change*100:.2f}%",
                metadata={
                    "period": self.period,
                    "threshold": self.threshold,
                    "price_change": price_change,
                },
            )
        elif price_change < -self.threshold:
            confidence = min(0.9, 0.5 + abs(price_change) / self.threshold * 0.4)
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"动量向下: {self.period}期跌幅={abs(price_change)*100:.2f}%",
                metadata={
                    "period": self.period,
                    "threshold": self.threshold,
                    "price_change": price_change,
                },
            )

        return signal

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号（新接口）"""
        if not self._enabled:
            return None

        momentum = features.get('momentum')
        close = features.get('close')

        if momentum is None:
            return None

        threshold = self.params.get('threshold', self.threshold)

        if momentum > threshold:
            confidence = min(0.9, 0.5 + momentum / threshold * 0.4)
            return {
                'signal_type': 'buy',
                'confidence': confidence,
                'reason': f"动量向上: momentum={momentum*100:.2f}%",
                'metadata': {
                    'threshold': threshold,
                    'momentum': momentum,
                    'close': close,
                }
            }
        elif momentum < -threshold:
            confidence = min(0.9, 0.5 + abs(momentum) / threshold * 0.4)
            return {
                'signal_type': 'sell',
                'confidence': confidence,
                'reason': f"动量向下: momentum={momentum*100:.2f}%",
                'metadata': {
                    'threshold': threshold,
                    'momentum': momentum,
                    'close': close,
                }
            }

        return None
