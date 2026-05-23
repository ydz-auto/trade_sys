"""
Signal Backtest Module - 信号回测模块
使用 replay 系统进行策略回测
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json

from infrastructure.logging import get_logger
from domain.contracts import Candle, Signal, Timeframe
from infrastructure.observability.manager import get_observability_manager

logger = get_logger("shared.backtest")


class BacktestStatus(str, Enum):
    """回测状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Position:
    """持仓"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: int

    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def update_price(self, price: float):
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity

    def close(self, price: float, time: int) -> float:
        self.realized_pnl = (price - self.entry_price) * self.quantity
        self.unrealized_pnl = 0
        return self.realized_pnl


@dataclass
class Trade:
    """交易记录"""
    trade_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: int
    pnl: float = 0.0
    fee: float = 0.0


@dataclass
class BacktestResult:
    """回测结果"""
    backtest_id: str
    strategy_name: str

    start_time: int
    end_time: int

    initial_capital: float
    final_capital: float

    total_return: float
    annualized_return: float

    max_drawdown: float
    sharpe_ratio: float
    win_rate: float

    total_trades: int
    winning_trades: int
    losing_trades: int

    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)

    status: BacktestStatus = BacktestStatus.COMPLETED
    error: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backtest_id": self.backtest_id,
            "strategy_name": self.strategy_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "status": self.status.value,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 10000.0
    fee_rate: float = 0.001
    slippage: float = 0.0005

    position_size_pct: float = 0.1
    max_positions: int = 5

    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: Optional[BacktestConfig] = None, replay_orchestrator=None):
        self.config = config or BacktestConfig()

        self._capital: float = 0
        self._positions: Dict[str, Position] = {}
        self._trades: List[Trade] = []
        self._equity_curve: List[Dict[str, Any]] = []

        self._strategy: Optional[Callable] = None
        self._trade_counter: int = 0
        self._replay_orchestrator = replay_orchestrator

    def set_strategy(self, strategy: Callable):
        self._strategy = strategy

    def reset(self):
        self._capital = self.config.initial_capital
        self._positions = {}
        self._trades = []
        self._equity_curve = []
        self._trade_counter = 0

    async def run(
        self,
        candles: List[Candle],
        strategy_name: str = "unknown",
    ) -> BacktestResult:
        """运行回测"""
        self.reset()

        observability = get_observability_manager("backtest")
        span = observability.start_operation("backtest_run")

        try:
            for candle in candles:
                await self._process_candle(candle)

            self._close_all_positions(candles[-1].close, candles[-1].open_time)

            result = self._calculate_result(strategy_name, candles)

            observability.end_operation(span, success=True)
            return result

        except Exception as e:
            observability.end_operation(span, success=False)
            logger.error(f"Backtest failed: {e}")

            return BacktestResult(
                backtest_id=f"bt_{int(datetime.now().timestamp())}",
                strategy_name=strategy_name,
                start_time=candles[0].open_time if candles else 0,
                end_time=candles[-1].open_time if candles else 0,
                initial_capital=self.config.initial_capital,
                final_capital=self._capital,
                total_return=0,
                annualized_return=0,
                max_drawdown=0,
                sharpe_ratio=0,
                win_rate=0,
                total_trades=len(self._trades),
                winning_trades=0,
                losing_trades=0,
                status=BacktestStatus.FAILED,
                error=str(e),
            )

    async def _process_candle(self, candle: Candle):
        """处理K线"""
        symbol = candle.symbol

        for pos_symbol, position in list(self._positions.items()):
            position.update_price(candle.close)

            if self.config.stop_loss_pct:
                if position.unrealized_pnl / (position.entry_price * position.quantity) < -self.config.stop_loss_pct:
                    await self._close_position(pos_symbol, candle.close, candle.open_time)

            if self.config.take_profit_pct:
                if position.unrealized_pnl / (position.entry_price * position.quantity) > self.config.take_profit_pct:
                    await self._close_position(pos_symbol, candle.close, candle.open_time)

        if self._strategy:
            signals = await self._generate_signals(candle)

            for signal in signals:
                await self._execute_signal(signal, candle)

        equity = self._calculate_equity(candle.close)
        self._equity_curve.append({
            "timestamp": candle.open_time,
            "equity": equity,
            "cash": self._capital,
            "positions": len(self._positions),
        })

    async def _generate_signals(self, candle: Candle) -> List[Signal]:
        """生成信号"""
        if not self._strategy:
            return []

        try:
            if asyncio.iscoroutinefunction(self._strategy):
                signals = await self._strategy(candle, self._positions, self._capital)
            else:
                signals = self._strategy(candle, self._positions, self._capital)

            return signals if isinstance(signals, list) else [signals] if signals else []
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            return []

    async def _execute_signal(self, signal: Signal, candle: Candle):
        """执行信号"""
        symbol = signal.symbol

        if signal.action == "buy" and symbol not in self._positions:
            if len(self._positions) >= self.config.max_positions:
                return

            position_value = self._capital * self.config.position_size_pct
            price = candle.close * (1 + self.config.slippage)
            quantity = position_value / price

            if quantity > 0 and self._capital >= position_value:
                self._capital -= position_value

                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=price,
                    entry_time=candle.open_time,
                )

                self._trade_counter += 1
                self._trades.append(Trade(
                    trade_id=f"trade_{self._trade_counter}",
                    symbol=symbol,
                    side="buy",
                    quantity=quantity,
                    price=price,
                    timestamp=candle.open_time,
                    fee=position_value * self.config.fee_rate,
                ))

        elif signal.action == "sell" and symbol in self._positions:
            await self._close_position(symbol, candle.close, candle.open_time)

    async def _close_position(self, symbol: str, price: float, timestamp: int):
        """平仓"""
        if symbol not in self._positions:
            return

        position = self._positions[symbol]

        exit_price = price * (1 - self.config.slippage)
        pnl = position.close(exit_price, timestamp)

        self._capital += position.quantity * exit_price

        self._trade_counter += 1
        self._trades.append(Trade(
            trade_id=f"trade_{self._trade_counter}",
            symbol=symbol,
            side="sell",
            quantity=position.quantity,
            price=exit_price,
            timestamp=timestamp,
            pnl=pnl,
            fee=position.quantity * exit_price * self.config.fee_rate,
        ))

        del self._positions[symbol]

    async def _close_all_positions(self, price: float, timestamp: int):
        """平掉所有仓位"""
        for symbol in list(self._positions.keys()):
            await self._close_position(symbol, price, timestamp)

    def _calculate_equity(self, current_price: float) -> float:
        """计算权益"""
        equity = self._capital

        for position in self._positions.values():
            equity += position.quantity * current_price

        return equity

    def _calculate_result(self, strategy_name: str, candles: List[Candle]) -> BacktestResult:
        """计算回测结果"""
        final_equity = self._equity_curve[-1]["equity"] if self._equity_curve else self.config.initial_capital

        total_return = (final_equity - self.config.initial_capital) / self.config.initial_capital

        if candles:
            days = (candles[-1].open_time - candles[0].open_time) / (24 * 3600 * 1000)
            annualized_return = total_return * (365 / max(days, 1)) if days > 0 else 0
        else:
            annualized_return = 0

        max_drawdown = self._calculate_max_drawdown()
        sharpe_ratio = self._calculate_sharpe_ratio()

        winning_trades = sum(1 for t in self._trades if t.pnl > 0)
        losing_trades = sum(1 for t in self._trades if t.pnl < 0)
        total_trades = len([t for t in self._trades if t.side == "sell"])

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        return BacktestResult(
            backtest_id=f"bt_{int(datetime.now().timestamp())}",
            strategy_name=strategy_name,
            start_time=candles[0].open_time if candles else 0,
            end_time=candles[-1].open_time if candles else 0,
            initial_capital=self.config.initial_capital,
            final_capital=final_equity,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            trades=self._trades,
            equity_curve=self._equity_curve,
        )

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self._equity_curve:
            return 0.0

        peak = self._equity_curve[0]["equity"]
        max_dd = 0.0

        for point in self._equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity

            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_sharpe_ratio(self) -> float:
        """计算夏普比率"""
        if len(self._equity_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self._equity_curve)):
            prev = self._equity_curve[i-1]["equity"]
            curr = self._equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return 0.0

        import statistics
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0

        if std_return == 0:
            return 0.0

        return (avg_return * 252) / (std_return * (252 ** 0.5))


_backtest_engine: Optional[BacktestEngine] = None


def get_backtest_engine(config: Optional[BacktestConfig] = None) -> BacktestEngine:
    """获取回测引擎"""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine(config)
    return _backtest_engine
