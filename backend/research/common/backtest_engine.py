"""
统一的策略回测引擎
让 simple_backtest 和 walk_forward 使用相同的回测逻辑
"""

from dataclasses import dataclass
from typing import List, Any, Optional, Tuple
import numpy as np

from engines.compute.strategy_v2 import StrategyV2, SignalType


@dataclass
class SingleSignalResult:
    """单个信号的回测结果"""
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    direction: str  # "long" or "short"
    pnl: float
    pnl_pct: float
    holding_bars: int
    confidence: float
    reason: str


@dataclass
class BacktestMetrics:
    """回测指标"""
    total_trades: int
    long_trades: int
    short_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_trade_return: float
    median_trade_return: float
    avg_win: float
    avg_loss: float
    total_pnl_pct: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float


def run_single_bar_backtest(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    start_idx: int = 0,
    end_idx: Optional[int] = None,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage_bps: float = 2.0,
) -> Tuple[List[SingleSignalResult], BacktestMetrics]:
    """
    统一的单bar回测逻辑（walk_forward风格，每个信号只持有1 bar）

    Args:
        strategy: 策略实例
        market_contexts: MarketContext列表
        timestamps: 时间戳列表
        prices: 价格序列
        start_idx: 开始索引
        end_idx: 结束索引
        maker_fee: Maker手续费
        taker_fee: Taker手续费
        slippage_bps: 滑点（基点）

    Returns:
        (信号结果列表, 回测指标)
    """
    if end_idx is None:
        end_idx = len(market_contexts)

    results: List[SingleSignalResult] = []

    for i in range(start_idx, end_idx):
        if i + 1 >= end_idx:
            break

        ctx = market_contexts[i]
        signal = strategy.generate_signal(ctx)

        if signal.type not in (SignalType.LONG, SignalType.SHORT):
            continue

        entry_price = prices[i]
        exit_price = prices[i + 1]

        # 计算方向
        direction = "long" if signal.type == SignalType.LONG else "short"

        # 应用滑点
        slippage = (slippage_bps / 10000) * entry_price
        if direction == "long":
            entry_price_slipped = entry_price + slippage
            exit_price_slipped = exit_price - slippage
        else:
            entry_price_slipped = entry_price - slippage
            exit_price_slipped = exit_price + slippage

        # 计算手续费
        fee_entry = entry_price_slipped * taker_fee
        fee_exit = exit_price_slipped * taker_fee

        # 计算收益
        if direction == "long":
            price_change = exit_price_slipped - entry_price_slipped
        else:
            price_change = entry_price_slipped - exit_price_slipped

        total_fee = fee_entry + fee_exit
        pnl = price_change - total_fee
        pnl_pct = pnl / entry_price_slipped

        results.append(SingleSignalResult(
            entry_time=timestamps[i],
            exit_time=timestamps[i + 1],
            entry_price=entry_price_slipped,
            exit_price=exit_price_slipped,
            direction=direction,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_bars=1,
            confidence=signal.confidence,
            reason=signal.reason
        ))

    metrics = _compute_metrics(results)
    return results, metrics


def run_holding_period_backtest(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    start_idx: int = 0,
    end_idx: Optional[int] = None,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage_bps: float = 2.0,
    max_holding_bars: int = 10,
) -> Tuple[List[SingleSignalResult], BacktestMetrics]:
    """
    统一的持有周期回测逻辑（simple_backtest风格）

    Args:
        strategy: 策略实例
        market_contexts: MarketContext列表
        timestamps: 时间戳列表
        prices: 价格序列
        start_idx: 开始索引
        end_idx: 结束索引
        maker_fee: Maker手续费
        taker_fee: Taker手续费
        slippage_bps: 滑点（基点）
        max_holding_bars: 最大持有bar数

    Returns:
        (信号结果列表, 回测指标)
    """
    if end_idx is None:
        end_idx = len(market_contexts)

    results: List[SingleSignalResult] = []
    current_position = None

    for i in range(start_idx, end_idx):
        ctx = market_contexts[i]
        signal = strategy.generate_signal(ctx)
        price = prices[i]

        if current_position is None:
            if signal.type in (SignalType.LONG, SignalType.SHORT):
                # 开仓
                direction = "long" if signal.type == SignalType.LONG else "short"
                slippage = (slippage_bps / 10000) * price
                if direction == "long":
                    entry_price = price + slippage
                else:
                    entry_price = price - slippage

                current_position = {
                    "direction": direction,
                    "entry_price": entry_price,
                    "entry_time": timestamps[i],
                    "entry_bar": i,
                    "confidence": signal.confidence,
                    "reason": signal.reason,
                    "fee_entry": entry_price * taker_fee
                }
        else:
            # 检查是否平仓
            holding_bars = i - current_position["entry_bar"]
            should_close = False
            close_reason = "max_holding"

            if current_position["direction"] == "long":
                if signal.type == SignalType.SHORT:
                    should_close = True
                    close_reason = "reverse_signal"
                elif holding_bars >= max_holding_bars:
                    should_close = True
            else:
                if signal.type == SignalType.LONG:
                    should_close = True
                    close_reason = "reverse_signal"
                elif holding_bars >= max_holding_bars:
                    should_close = True

            if should_close:
                if i + 1 >= end_idx:
                    # 最后一个bar，用当前价格平仓
                    exit_price = price
                    exit_time = timestamps[i]
                else:
                    exit_price = prices[i + 1]
                    exit_time = timestamps[i + 1]

                direction = current_position["direction"]
                slippage = (slippage_bps / 10000) * exit_price
                if direction == "long":
                    exit_price_slipped = exit_price - slippage
                else:
                    exit_price_slipped = exit_price + slippage

                fee_exit = exit_price_slipped * taker_fee

                if direction == "long":
                    price_change = exit_price_slipped - current_position["entry_price"]
                else:
                    price_change = current_position["entry_price"] - exit_price_slipped

                total_fee = current_position["fee_entry"] + fee_exit
                pnl = price_change - total_fee
                pnl_pct = pnl / current_position["entry_price"]

                results.append(SingleSignalResult(
                    entry_time=current_position["entry_time"],
                    exit_time=exit_time,
                    entry_price=current_position["entry_price"],
                    exit_price=exit_price_slipped,
                    direction=direction,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    holding_bars=holding_bars,
                    confidence=current_position["confidence"],
                    reason=f"{current_position['reason']}->{close_reason}"
                ))

                current_position = None

    # 处理最后未平仓的仓位
    if current_position is not None and end_idx > 0:
        i = end_idx - 1
        price = prices[i]
        direction = current_position["direction"]
        slippage = (slippage_bps / 10000) * price
        if direction == "long":
            exit_price_slipped = price - slippage
        else:
            exit_price_slipped = price + slippage

        fee_exit = exit_price_slipped * taker_fee
        holding_bars = i - current_position["entry_bar"]

        if direction == "long":
            price_change = exit_price_slipped - current_position["entry_price"]
        else:
            price_change = current_position["entry_price"] - exit_price_slipped

        total_fee = current_position["fee_entry"] + fee_exit
        pnl = price_change - total_fee
        pnl_pct = pnl / current_position["entry_price"]

        results.append(SingleSignalResult(
            entry_time=current_position["entry_time"],
            exit_time=timestamps[i],
            entry_price=current_position["entry_price"],
            exit_price=exit_price_slipped,
            direction=direction,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_bars=holding_bars,
            confidence=current_position["confidence"],
            reason=f"{current_position['reason']}->end_of_data"
        ))

    metrics = _compute_metrics(results)
    return results, metrics


def _compute_metrics(results: List[SingleSignalResult]) -> BacktestMetrics:
    """计算回测指标"""
    if not results:
        return BacktestMetrics(
            total_trades=0, long_trades=0, short_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0, avg_trade_return=0, median_trade_return=0, avg_win=0, avg_loss=0,
            total_pnl_pct=0, max_drawdown=0, sharpe_ratio=0, profit_factor=0
        )

    pnls_pct = [r.pnl_pct for r in results]

    long_trades = sum(1 for r in results if r.direction == "long")
    short_trades = sum(1 for r in results if r.direction == "short")

    winning_trades = sum(1 for r in results if r.pnl > 0)
    losing_trades = sum(1 for r in results if r.pnl <= 0)

    avg_trade_return = np.mean(pnls_pct)
    median_trade_return = np.median(pnls_pct)

    wins = [r.pnl_pct for r in results if r.pnl > 0]
    losses = [r.pnl_pct for r in results if r.pnl <= 0]
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0

    total_pnl_pct = np.sum(pnls_pct)

    # 计算最大回撤
    cumulative = np.cumsum(pnls_pct)
    running_max = np.maximum.accumulate(cumulative)
    max_drawdown = np.min(cumulative - running_max)

    # 计算夏普比率
    if np.std(pnls_pct) > 0 and len(pnls_pct) > 1:
        sharpe_ratio = np.mean(pnls_pct) / np.std(pnls_pct) * np.sqrt(len(pnls_pct))
    else:
        sharpe_ratio = 0

    # 计算盈利因子
    total_win_pnl = sum(r.pnl for r in results if r.pnl > 0)
    total_loss_pnl = abs(sum(r.pnl for r in results if r.pnl <= 0))
    if total_loss_pnl > 0:
        profit_factor = total_win_pnl / total_loss_pnl
    else:
        profit_factor = float('inf')

    win_rate = winning_trades / len(results) if results else 0

    return BacktestMetrics(
        total_trades=len(results),
        long_trades=long_trades,
        short_trades=short_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        avg_trade_return=avg_trade_return,
        median_trade_return=median_trade_return,
        avg_win=avg_win,
        avg_loss=avg_loss,
        total_pnl_pct=total_pnl_pct,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        profit_factor=profit_factor
    )


__all__ = [
    "SingleSignalResult",
    "BacktestMetrics",
    "run_single_bar_backtest",
    "run_holding_period_backtest"
]
