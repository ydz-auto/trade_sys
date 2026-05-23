
from typing import Protocol, Dict, List, Any, Optional, runtime_checkable
from dataclasses import dataclass
from enum import Enum

from research.protocol.core import FeatureSnapshot, FeatureVector
from research.walk_forward.context import ResearchContext, WindowSpec, WindowResult


class SignalDirection(Enum):
    LONG = 1
    SHORT = -1
    NEUTRAL = 0


@dataclass(frozen=True)
class TradeSignal:
    direction: SignalDirection
    confidence: float
    timestamp_ms: int
    
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    size: float = 1.0
    metadata: tuple = ()

    def is_actionable(self) -> bool:
        return self.direction != SignalDirection.NEUTRAL and self.confidence >= 0.5


@dataclass(frozen=True)
class BacktestTrade:
    entry_time_ms: int
    exit_time_ms: int
    
    direction: SignalDirection
    
    entry_price: float
    exit_price: float
    
    quantity: float
    pnl: float
    pnl_bps: float
    
    hold_hours: float
    metadata: tuple = ()


@dataclass(frozen=True)
class WindowMetrics:
    """窗口执行指标"""
    sharpe: float
    sortino: float
    win_rate: float
    total_trades: int
    total_pnl: float
    max_drawdown: float
    annual_return: float
    profit_factor: float
    
    returns: tuple
    drawdowns: tuple


@runtime_checkable
class ResearchStrategy(Protocol):
    """
    策略接口 Protocol —— Research 模块的「策略 ABI」
    
    铁律：
    1. 所有策略必须实现这个 Protocol
    2. 策略不持有任何 Runtime 引用
    3. 策略只通过 ResearchDataset 获取数据
    
    实现示例：
    class MyStrategy:
        def setup(self, context: ResearchContext) -> None:
            ...
        
        def generate_signals(
            self,
            features: Dict[str, float],
            timestamp_ms: int,
        ) -> TradeSignal:
            ...
        
        def on_bar(
            self,
            timestamp_ms: int,
            features: Dict[str, float],
        ) -> Optional[TradeSignal]:
            return self.generate_signals(features, timestamp_ms)
        
        def compute_metrics(
            self,
            trades: List[BacktestTrade],
        ) -> WindowMetrics:
            ...
    """
    
    def setup(self, context: ResearchContext) -> None:
        """初始化策略（接收 ResearchContext）"""
        ...
    
    def on_bar(
        self,
        timestamp_ms: int,
        features: Dict[str, float],
    ) -> Optional[TradeSignal]:
        """处理单个 bar，返回信号"""
        ...
    
    def compute_metrics(
        self,
        trades: List[BacktestTrade],
    ) -> WindowMetrics:
        """计算窗口指标"""
        ...


class SimpleSignalStrategy:
    """
    简单信号策略示例（可作为基类）
    """
    
    def __init__(
        self,
        long_threshold: float = 0.5,
        short_threshold: float = -0.5,
        features: Optional[List[str]] = None,
    ):
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.features = features or ["signal_composite"]
        self._context: Optional[ResearchContext] = None
    
    def setup(self, context: ResearchContext) -> None:
        self._context = context
    
    def on_bar(
        self,
        timestamp_ms: int,
        features: Dict[str, float],
    ) -> Optional[TradeSignal]:
        composite = features.get("signal_composite", 0.0)
        
        if composite >= self.long_threshold:
            return TradeSignal(
                direction=SignalDirection.LONG,
                confidence=min(1.0, abs(composite)),
                timestamp_ms=timestamp_ms,
            )
        elif composite <= self.short_threshold:
            return TradeSignal(
                direction=SignalDirection.SHORT,
                confidence=min(1.0, abs(composite)),
                timestamp_ms=timestamp_ms,
            )
        
        return TradeSignal(
            direction=SignalDirection.NEUTRAL,
            confidence=0.0,
            timestamp_ms=timestamp_ms,
        )
    
    def compute_metrics(
        self,
        trades: List[BacktestTrade],
    ) -> WindowMetrics:
        if not trades:
            return WindowMetrics(
                sharpe=0.0, sortino=0.0, win_rate=0.0,
                total_trades=0, total_pnl=0.0, max_drawdown=0.0,
                annual_return=0.0, profit_factor=0.0,
                returns=(), drawdowns=(),
            )
        
        import statistics
        import math
        
        returns = [t.pnl_bps for t in trades]
        winning = [r for r in returns if r > 0]
        losing = [abs(r) for r in returns if r < 0]
        
        mean_return = statistics.mean(returns) if returns else 0.0
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        sharpe = (mean_return / std_return * math.sqrt(252 * 4)) if std_return > 0 else 0.0
        
        downside = [r for r in returns if r < 0]
        downside_std = statistics.stdev(downside) if len(downside) > 1 else 0.0
        sortino = (mean_return / downside_std * math.sqrt(252 * 4)) if downside_std > 0 else 0.0
        
        win_rate = len(winning) / len(returns) if returns else 0.0
        
        total_pnl = sum(returns)
        profit_factor = (sum(winning) / sum(losing)) if losing and sum(losing) > 0 else 0.0
        
        cumulative = []
        running = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in returns:
            running += r
            cumulative.append(running)
            if running > peak:
                peak = running
            dd = peak - running
            if dd > max_dd:
                max_dd = dd
        
        annual_return = mean_return * 252 * 4
        
        return WindowMetrics(
            sharpe=sharpe,
            sortino=sortino,
            win_rate=win_rate,
            total_trades=len(trades),
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            annual_return=annual_return,
            profit_factor=profit_factor,
            returns=tuple(returns),
            drawdowns=tuple(cumulative),
        )
