"""
Backtest Service - 回测服务

功能：
- 历史数据回放
- 策略回测评估
- 绩效指标计算
- 报告生成

架构：
Historical Data → BacktestEngine → Signals → Execution → Performance Report
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

from infrastructure.logging import get_logger

logger = get_logger("backtest_service")


class SignalType(str, Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    """K线数据"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    """交易记录"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    side: SignalType


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_trade_duration: float = 0.0


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 100000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005    # 0.05%
    position_size: float = 0.1  # 10%
    stop_loss: float = 0.02    # 2%
    take_profit: float = 0.05   # 5%


@dataclass
class BacktestResult:
    """回测结果"""
    config: BacktestConfig
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: List[float]
    drawdown_curve: List[float]
    start_date: datetime
    end_date: datetime
    duration_days: int


class MockDataGenerator:
    """模拟数据生成器"""

    @staticmethod
    def generate_bars(
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_price: float = 50000.0,
        volatility: float = 0.02
    ) -> List[Bar]:
        """生成模拟 K 线数据"""
        import random
        bars = []
        current_price = initial_price
        current_date = start_date

        while current_date <= end_date:
            # 跳过周末
            if current_date.weekday() < 5:
                # 随机波动
                change = random.gauss(0, volatility)
                open_price = current_price
                close_price = current_price * (1 + change)

                high_price = max(open_price, close_price) * (1 + abs(change) * 0.5)
                low_price = min(open_price, close_price) * (1 - abs(change) * 0.5)

                volume = random.uniform(1000, 10000)

                bars.append(Bar(
                    timestamp=current_date,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume
                ))

                current_price = close_price

            current_date += timedelta(days=1)

        return bars


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._bars: List[Bar] = []
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._drawdown_curve: List[float] = []
        self._position: Optional[Dict] = None
        self._capital: float = 0.0

    def load_data(self, bars: List[Bar]) -> "BacktestEngine":
        """加载历史数据"""
        self._bars = sorted(bars, key=lambda x: x.timestamp)
        return self

    def load_mock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_price: float = 50000.0
    ) -> "BacktestEngine":
        """加载模拟数据"""
        self._bars = MockDataGenerator.generate_bars(
            symbol, start_date, end_date, initial_price
        )
        return self

    def run(
        self,
        signal_generator: Callable[[Bar, Optional[Dict]], SignalType]
    ) -> BacktestResult:
        """运行回测

        Args:
            signal_generator: 信号生成函数，接受 (current_bar, position) 返回 SignalType
        """
        if not self._bars:
            raise ValueError("No data loaded")

        self._trades = []
        self._equity_curve = []
        self._drawdown_curve = []
        self._position = None
        self._capital = self.config.initial_capital

        peak_equity = self._capital

        for i, bar in enumerate(self._bars):
            # 生成信号
            signal = signal_generator(bar, self._position)

            # 检查持仓
            if self._position:
                # 检查止损/止盈
                pnl_pct = (bar.close - self._position["entry_price"]) / self._position["entry_price"]

                if self._position["side"] == SignalType.SELL:
                    pnl_pct = -pnl_pct

                # 止损
                if pnl_pct <= -self.config.stop_loss:
                    self._close_position(bar, "stop_loss")
                # 止盈
                elif pnl_pct >= self.config.take_profit:
                    self._close_position(bar, "take_profit")
                # 止损
                elif signal == SignalType.SELL:
                    self._close_position(bar, "signal")

            # 开仓
            if not self._position and signal != SignalType.HOLD:
                self._open_position(bar, signal)

            # 记录权益
            current_equity = self._capital
            if self._position:
                pos_pnl = (bar.close - self._position["entry_price"]) * self._position["quantity"]
                if self._position["side"] == SignalType.SELL:
                    pos_pnl = -pos_pnl
                current_equity += pos_pnl

            self._equity_curve.append(current_equity)

            # 记录回撤
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = peak_equity - current_equity
            drawdown_pct = drawdown / peak_equity if peak_equity > 0 else 0
            self._drawdown_curve.append(drawdown_pct)

        # 平仓未平仓位
        if self._position:
            self._close_position(self._bars[-1], "end")

        # 计算指标
        metrics = self._calculate_metrics()

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self._trades,
            equity_curve=self._equity_curve,
            drawdown_curve=self._drawdown_curve,
            start_date=self._bars[0].timestamp if self._bars else datetime.now(),
            end_date=self._bars[-1].timestamp if self._bars else datetime.now(),
            duration_days=len(self._bars)
        )

    def _open_position(self, bar: Bar, signal: SignalType):
        """开仓"""
        position_value = self._capital * self.config.position_size
        quantity = position_value / bar.close

        # 扣除手续费和滑点
        cost = position_value * (1 + self.config.commission + self.config.slippage)

        if cost > self._capital:
            return

        self._position = {
            "entry_time": bar.timestamp,
            "entry_price": bar.close * (1 + self.config.slippage),
            "quantity": quantity,
            "side": signal,
            "capital_used": cost
        }

        self._capital -= cost

    def _close_position(self, bar: Bar, reason: str):
        """平仓"""
        if not self._position:
            return

        exit_price = bar.close * (1 - self.config.slippage)
        if self._position["side"] == SignalType.SELL:
            exit_price = bar.close * (1 + self.config.slippage)

        pnl = (exit_price - self._position["entry_price"]) * self._position["quantity"]

        if self._position["side"] == SignalType.SELL:
            pnl = -pnl

        # 扣除手续费
        pnl -= self._position["capital_used"] * self.config.commission

        trade = Trade(
            entry_time=self._position["entry_time"],
            exit_time=bar.timestamp,
            entry_price=self._position["entry_price"],
            exit_price=exit_price,
            quantity=self._position["quantity"],
            pnl=pnl,
            pnl_pct=pnl / self._position["capital_used"],
            side=self._position["side"]
        )

        self._trades.append(trade)

        # 返还资金
        self._capital += self._position["capital_used"] + pnl
        self._position = None

    def _calculate_metrics(self) -> PerformanceMetrics:
        """计算绩效指标"""
        if not self._equity_curve:
            return PerformanceMetrics()

        total_return = self._equity_curve[-1] - self.config.initial_capital
        total_return_pct = total_return / self.config.initial_capital

        # 最大回撤
        peak = self.config.initial_capital
        max_drawdown = 0.0
        for equity in self._equity_curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        max_drawdown_pct = max_drawdown / peak if peak > 0 else 0

        # 交易统计
        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.pnl > 0)
        losing_trades = sum(1 for t in self._trades if t.pnl <= 0)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = sum(t.pnl for t in self._trades if t.pnl > 0) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t.pnl for t in self._trades if t.pnl <= 0) / losing_trades if losing_trades > 0 else 0

        total_wins = sum(t.pnl for t in self._trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self._trades if t.pnl <= 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # 夏普比率（简化版）
        returns = []
        for i in range(1, len(self._equity_curve)):
            ret = (self._equity_curve[i] - self._equity_curve[i-1]) / self._equity_curve[i-1]
            returns.append(ret)

        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # 平均交易收益
        avg_trade_return = sum(t.pnl_pct for t in self._trades) / total_trades if total_trades > 0 else 0

        # 平均持仓时间
        durations = [(t.exit_time - t.entry_time).days for t in self._trades]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            avg_trade_duration=avg_duration
        )

    def print_result(self, result: BacktestResult):
        """打印回测结果"""
        print("\n" + "=" * 70)
        print("📊 回测结果")
        print("=" * 70)

        print(f"\n📅 时间范围: {result.start_date.date()} ~ {result.end_date.date()}")
        print(f"   持续天数: {result.duration_days}")

        m = result.metrics

        print(f"\n💰 收益")
        print(f"   总收益: ${m.total_return:,.2f} ({m.total_return_pct:.2%})")
        print(f"   夏普比率: {m.sharpe_ratio:.2f}")

        print(f"\n📉 风险")
        print(f"   最大回撤: ${m.max_drawdown:,.2f} ({m.max_drawdown_pct:.2%})")

        print(f"\n📈 交易统计")
        print(f"   总交易: {m.total_trades}")
        print(f"   胜率: {m.win_rate:.2%}")
        print(f"   盈利交易: {m.winning_trades}")
        print(f"   亏损交易: {m.losing_trades}")
        print(f"   平均盈利: ${m.avg_win:,.2f}")
        print(f"   平均亏损: ${m.avg_loss:,.2f}")
        print(f"   盈亏比: {m.profit_factor:.2f}")
        print(f"   平均持仓: {m.avg_trade_duration:.1f} 天")

        print("\n" + "=" * 70)


# 全局函数
def run_backtest(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    strategy: Callable[[Bar, Optional[Dict]], SignalType],
    config: BacktestConfig = None
) -> BacktestResult:
    """运行回测的便捷函数"""
    engine = BacktestEngine(config)
    engine.load_mock_data(symbol, start_date, end_date)
    result = engine.run(strategy)
    engine.print_result(result)
    return result


# 示例策略
def example_sma_crossover_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """简单移动平均线交叉策略"""
    import random

    # 简化：随机生成信号
    if position:
        return SignalType.HOLD

    # 模拟金叉/死叉
    if random.random() > 0.95:
        return SignalType.BUY

    return SignalType.HOLD


if __name__ == "__main__":
    # 示例回测
    result = run_backtest(
        symbol="BTC/USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        strategy=example_sma_crossover_strategy
    )
