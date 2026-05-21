"""
Symbol-Specific Strategy Orchestrator
按币种管理的策略编排器

每个币种使用独立的策略实例和配置参数
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from infrastructure.logging import get_logger

from domain.strategy.symbol_config import (
    SymbolStrategyConfig,
    SymbolStrategyConfigManager,
    get_symbol_config_manager,
)

logger = get_logger("symbol_strategy_orchestrator")


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
    strategy_name: str
    symbol: str
    action: ActionType
    quantity: float
    price: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: __import__('time').time_ns() // 1000000)


class RSISymbolStrategy:
    """币种特定的RSI策略"""
    
    def __init__(self, symbol: str, config: SymbolStrategyConfig):
        self.symbol = symbol
        self.config = config
        self.params = config.rsi_strategy
        self.strategy_id = f"rsi_{symbol.lower()}"
        self._rsi_prev: Optional[float] = None
    
    def calculate_rsi(self, prices: List[float]) -> float:
        """计算RSI"""
        if len(prices) < self.params.period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        # 取最近period个数据
        gains = gains[-self.params.period:]
        losses = losses[-self.params.period:]
        
        avg_gain = sum(gains) / self.params.period
        avg_loss = sum(losses) / self.params.period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < self.params.period + 1:
            return None
        
        current_price = close_prices[-1]
        rsi = self.calculate_rsi(close_prices)
        
        signal = None
        
        if self._rsi_prev is not None:
            if rsi <= self.params.oversold and self._rsi_prev > self.params.oversold:
                # 超卖买入信号
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_name="RSI",
                    symbol=self.symbol,
                    action=ActionType.LONG,
                    quantity=self.params.default_quantity,
                    price=current_price,
                    confidence=min(0.9, (self.params.oversold - rsi) / (self.params.oversold / 2) + 0.5),
                    reason=f"RSI超卖: {rsi:.2f} < {self.params.oversold}",
                    metadata={"rsi": rsi, "prev_rsi": self._rsi_prev},
                )
            elif rsi >= self.params.overbought and self._rsi_prev < self.params.overbought:
                # 超买卖出信号
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_name="RSI",
                    symbol=self.symbol,
                    action=ActionType.SHORT,
                    quantity=self.params.default_quantity,
                    price=current_price,
                    confidence=min(0.9, (rsi - self.params.overbought) / ((100 - self.params.overbought) / 2) + 0.5),
                    reason=f"RSI超买: {rsi:.2f} > {self.params.overbought}",
                    metadata={"rsi": rsi, "prev_rsi": self._rsi_prev},
                )
        
        self._rsi_prev = rsi
        return signal


class MACDSymbolStrategy:
    """币种特定的MACD策略"""
    
    def __init__(self, symbol: str, config: SymbolStrategyConfig):
        self.symbol = symbol
        self.config = config
        self.params = config.macd_strategy
        self.strategy_id = f"macd_{symbol.lower()}"
        self._macd_prev: Optional[float] = None
        self._signal_prev: Optional[float] = None
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """计算EMA"""
        if len(prices) < period:
            return prices
        
        ema = []
        multiplier = 2 / (period + 1)
        
        # 初始SMA
        sma = sum(prices[:period]) / period
        ema.append(sma)
        
        # 计算后续EMA
        for price in prices[period:]:
            ema_val = (price - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_val)
        
        # 补全前面的值（用第一个值填充）
        return [ema[0]] * (period - 1) + ema
    
    def calculate_macd(self, prices: List[float]) -> tuple:
        """计算MACD"""
        if len(prices) < self.params.slow_period + self.params.signal_period:
            return 0.0, 0.0, 0.0
        
        ema_fast = self._calculate_ema(prices, self.params.fast_period)
        ema_slow = self._calculate_ema(prices, self.params.slow_period)
        
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_line = self._calculate_ema(macd_line, self.params.signal_period)
        histogram = [m - s for m, s in zip(macd_line, signal_line)]
        
        return macd_line[-1], signal_line[-1], histogram[-1]
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < self.params.slow_period + self.params.signal_period:
            return None
        
        current_price = close_prices[-1]
        macd_line, signal_line, histogram = self.calculate_macd(close_prices)
        
        signal = None
        
        if self._macd_prev is not None and self._signal_prev is not None:
            if self._macd_prev <= self._signal_prev and macd_line > signal_line:
                # 金叉
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_name="MACD",
                    symbol=self.symbol,
                    action=ActionType.LONG,
                    quantity=self.params.default_quantity,
                    price=current_price,
                    confidence=0.7,
                    reason=f"MACD金叉: {macd_line:.4f} > {signal_line:.4f}",
                    metadata={"macd": macd_line, "signal": signal_line, "histogram": histogram},
                )
            elif self._macd_prev >= self._signal_prev and macd_line < signal_line:
                # 死叉
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_name="MACD",
                    symbol=self.symbol,
                    action=ActionType.SHORT,
                    quantity=self.params.default_quantity,
                    price=current_price,
                    confidence=0.7,
                    reason=f"MACD死叉: {macd_line:.4f} < {signal_line:.4f}",
                    metadata={"macd": macd_line, "signal": signal_line, "histogram": histogram},
                )
        
        self._macd_prev = macd_line
        self._signal_prev = signal_line
        return signal


class PanicReversalSymbolStrategy:
    """币种特定的恐慌反转策略"""
    
    def __init__(self, symbol: str, config: SymbolStrategyConfig):
        self.symbol = symbol
        self.config = config
        self.params = config.panic_reversal
        self.strategy_id = f"panic_reversal_{symbol.lower()}"
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        
        if len(close_prices) < 12:
            return None
        
        current_price = close_prices[-1]
        price_1h_ago = close_prices[-12]
        return_1h = (current_price - price_1h_ago) / price_1h_ago
        
        # 计算成交量比率
        volume_ratio = 1.0
        if len(volumes) >= 288:
            avg_volume = sum(volumes[-288:]) / 288
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        
        if return_1h <= self.params.drop_threshold and volume_ratio >= self.params.volume_ratio_threshold:
            confidence = min(0.9, (abs(return_1h) - abs(self.params.drop_threshold)) * 50 + 0.5)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_name="PanicReversal",
                symbol=self.symbol,
                action=ActionType.LONG,
                quantity=self.params.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"恐慌反转: 1h跌幅{return_1h*100:.2f}%, 成交量比{volume_ratio:.2f}",
                metadata={"return_1h": return_1h, "volume_ratio": volume_ratio},
            )
        
        return None


class SymbolStrategyGroup:
    """单个币种的策略组"""
    
    def __init__(self, symbol: str, config: SymbolStrategyConfig):
        self.symbol = symbol
        self.config = config
        
        # 创建策略实例
        self.strategies: Dict[str, Any] = {}
        
        if "rsi_strategy" in config.enabled_strategies:
            self.strategies["rsi"] = RSISymbolStrategy(symbol, config)
        
        if "macd_strategy" in config.enabled_strategies:
            self.strategies["macd"] = MACDSymbolStrategy(symbol, config)
        
        if "panic_reversal" in config.enabled_strategies:
            self.strategies["panic_reversal"] = PanicReversalSymbolStrategy(symbol, config)
        
        # 可以继续添加其他策略...
        
        logger.info(f"Created strategy group for {symbol} with {len(self.strategies)} strategies")
    
    def process(self, data: Dict) -> List[StrategySignal]:
        """处理市场数据，返回所有策略信号"""
        signals = []
        for strategy in self.strategies.values():
            try:
                signal = strategy.calculate(data)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error in strategy {strategy.strategy_id} for {self.symbol}: {e}")
        return signals


class SymbolStrategyOrchestrator:
    """按币种管理的策略编排器"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_manager = get_symbol_config_manager(config_dir)
        self.strategy_groups: Dict[str, SymbolStrategyGroup] = {}
        self._symbol_data: Dict[str, Dict] = {}
        
        # 为所有启用的币种创建策略组
        self._init_strategy_groups()
        
        logger.info(f"SymbolStrategyOrchestrator initialized with {len(self.strategy_groups)} symbol groups")
    
    def _init_strategy_groups(self):
        """初始化策略组"""
        enabled_symbols = self.config_manager.get_enabled_symbols()
        for symbol in enabled_symbols:
            config = self.config_manager.get_config(symbol)
            if config:
                self.strategy_groups[symbol] = SymbolStrategyGroup(symbol, config)
    
    def update_market_data(self, symbol: str, data: Dict):
        """更新市场数据"""
        self._symbol_data[symbol] = data
    
    def process_symbol(self, symbol: str) -> List[StrategySignal]:
        """处理单个币种"""
        if symbol not in self.strategy_groups:
            logger.warning(f"No strategy group for {symbol}")
            return []
        
        if symbol not in self._symbol_data:
            logger.warning(f"No market data for {symbol}")
            return []
        
        group = self.strategy_groups[symbol]
        data = self._symbol_data[symbol]
        return group.process(data)
    
    def process_all(self) -> Dict[str, List[StrategySignal]]:
        """处理所有币种"""
        all_signals = {}
        for symbol in self.strategy_groups:
            signals = self.process_symbol(symbol)
            if signals:
                all_signals[symbol] = signals
        return all_signals
    
    def reload_symbol_config(self, symbol: str):
        """重新加载币种配置"""
        self.config_manager.reload_config(symbol)
        config = self.config_manager.get_config(symbol)
        if config and config.enabled:
            self.strategy_groups[symbol] = SymbolStrategyGroup(symbol, config)
        elif symbol in self.strategy_groups:
            del self.strategy_groups[symbol]
    
    def get_enabled_symbols(self) -> List[str]:
        """获取启用的币种列表"""
        return list(self.strategy_groups.keys())
    
    def get_risk_config(self, symbol: str) -> Optional[Dict]:
        """获取币种风险配置"""
        config = self.config_manager.get_config(symbol)
        if config:
            return {
                "position_size": config.risk.position_size,
                "max_leverage": config.risk.max_leverage,
                "min_leverage": config.risk.min_leverage,
                "stop_loss_pct": config.risk.stop_loss_pct,
                "take_profit_pct": config.risk.take_profit_pct,
                "max_position_value": config.risk.max_position_value,
            }
        return None


# 全局实例
_orchestrator: Optional[SymbolStrategyOrchestrator] = None


def get_symbol_strategy_orchestrator(config_dir: Optional[str] = None) -> SymbolStrategyOrchestrator:
    """获取全局策略编排器"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SymbolStrategyOrchestrator(config_dir)
    return _orchestrator
