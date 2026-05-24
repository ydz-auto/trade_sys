from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from infrastructure.logging import get_logger

logger = get_logger("engines.compute.risk")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class RiskCheckResult(str, Enum):
    PASSED = "passed"
    REJECTED = "rejected"
    WARNING = "warning"


@dataclass
class RiskConfig:
    max_position_size: float = 0.1
    max_single_loss: float = 0.02
    max_daily_loss: float = 0.05
    max_drawdown: float = 0.15
    max_leverage: float = 3.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    min_confidence: float = 0.5


@dataclass
class PositionRisk:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    side: str = "buy"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_pct: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class RiskReport:
    check_result: RiskCheckResult
    risk_level: RiskLevel
    rejected_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    position_risks: List[PositionRisk] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeRisk:
    symbol: str
    side: str
    quantity: float
    price: float
    estimated_value: float
    estimated_loss: float
    risk_level: RiskLevel
    stop_loss: float
    take_profit: float


def compute_unrealized_pnl(entry_price: float, current_price: float, quantity: float) -> float:
    return (current_price - entry_price) * quantity


def compute_pnl_pct(entry_price: float, current_price: float) -> float:
    if entry_price == 0:
        return 0.0
    return (current_price - entry_price) / entry_price


def compute_stop_loss_price(price: float, side: str, stop_loss_pct: float) -> float:
    if side.lower() in ("buy", "long"):
        return price * (1 - stop_loss_pct)
    return price * (1 + stop_loss_pct)


def compute_take_profit_price(price: float, side: str, take_profit_pct: float) -> float:
    if side.lower() in ("buy", "long"):
        return price * (1 + take_profit_pct)
    return price * (1 - take_profit_pct)


def is_stop_loss_triggered(side: str, current_price: float, stop_loss: float) -> bool:
    if side == "buy" and current_price <= stop_loss:
        return True
    if side == "sell" and current_price >= stop_loss:
        return True
    return False


def is_take_profit_triggered(side: str, current_price: float, take_profit: float) -> bool:
    if side == "buy" and current_price >= take_profit:
        return True
    if side == "sell" and current_price <= take_profit:
        return True
    return False


def compute_position_ratio(quantity: float, price: float, equity: float) -> float:
    if equity == 0:
        return 0.0
    return quantity * price / equity


def compute_drawdown(peak_equity: float, current_equity: float) -> float:
    if peak_equity <= 0:
        return 0.0
    return (peak_equity - current_equity) / peak_equity


def compute_current_equity(base_equity: float, daily_pnl: float, positions: List[PositionRisk]) -> float:
    unrealized = sum(pos.unrealized_pnl for pos in positions)
    return base_equity + daily_pnl + unrealized


def compute_win_rate(winning_trades: int, total_trades: int) -> float:
    if total_trades == 0:
        return 0.0
    return winning_trades / total_trades


def compute_exposure_ratio(positions: List[PositionRisk], equity: float) -> float:
    total_exposure = sum(pos.quantity * pos.current_price for pos in positions)
    if equity <= 0:
        return 0.0
    return total_exposure / equity


def check_position_size(position_ratio: float, max_position_size: float) -> Optional[str]:
    if position_ratio > max_position_size:
        return f"仓位过大: {position_ratio:.2%} > {max_position_size:.2%}"
    return None


def check_single_loss(estimated_loss: float, equity: float, max_single_loss: float) -> Optional[str]:
    if abs(estimated_loss) > equity * max_single_loss:
        return f"单笔亏损过大: {abs(estimated_loss):.2f} > {equity * max_single_loss:.2f}"
    return None


def check_daily_loss(daily_pnl: float, estimated_loss: float, equity: float, max_daily_loss: float) -> Optional[str]:
    if abs(daily_pnl - estimated_loss) > equity * max_daily_loss:
        return f"日内亏损超限: {abs(daily_pnl - estimated_loss):.2f} > {equity * max_daily_loss:.2f}"
    return None


def check_max_drawdown(drawdown: float, max_drawdown: float) -> Optional[str]:
    if drawdown > max_drawdown:
        return f"最大回撤超限: {drawdown:.2%} > {max_drawdown:.2%}"
    return None


def determine_risk_level(
    position_ratio: float,
    max_position_size: float,
    has_warnings: bool,
) -> RiskLevel:
    if position_ratio > max_position_size * 0.5:
        return RiskLevel.HIGH
    if has_warnings:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def check_stop_loss_distance(side: str, price: float, stop_loss: float) -> Optional[str]:
    if side.lower() in ("buy", "long"):
        if stop_loss < price * 0.9:
            return "止损距离过大"
    else:
        if stop_loss < price * 0.9:
            return "止盈距离过大"
    return None


def compute_risk_metrics(
    current_equity: float,
    peak_equity: float,
    daily_pnl: float,
    total_trades: int,
    winning_trades: int,
    losing_trades: int,
    positions: List[PositionRisk],
) -> Dict[str, Any]:
    drawdown = compute_drawdown(peak_equity, current_equity)
    win_rate = compute_win_rate(winning_trades, total_trades)
    total_exposure = sum(pos.quantity * pos.current_price for pos in positions)
    exposure_ratio = compute_exposure_ratio(positions, current_equity)
    return {
        "current_equity": current_equity,
        "peak_equity": peak_equity,
        "drawdown": drawdown,
        "daily_pnl": daily_pnl,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "total_exposure": total_exposure,
        "exposure_ratio": exposure_ratio,
        "positions_count": len(positions),
    }


def evaluate_trade_risk(
    trade: TradeRisk,
    config: RiskConfig,
    current_equity: float,
    daily_pnl: float,
    peak_equity: float,
    positions: List[PositionRisk],
    total_trades: int = 0,
    winning_trades: int = 0,
    losing_trades: int = 0,
) -> RiskReport:
    warnings: List[str] = []

    position_ratio = compute_position_ratio(trade.quantity, trade.price, current_equity)

    rejection = check_position_size(position_ratio, config.max_position_size)
    if rejection:
        return RiskReport(
            check_result=RiskCheckResult.REJECTED,
            risk_level=RiskLevel.HIGH,
            rejected_reason=rejection,
            position_risks=positions,
            metrics=compute_risk_metrics(
                current_equity, peak_equity, daily_pnl,
                total_trades, winning_trades, losing_trades, positions,
            ),
        )

    if position_ratio > config.max_position_size * 0.8:
        warnings.append(f"仓位接近上限: {position_ratio:.2%}")

    rejection = check_single_loss(trade.estimated_loss, current_equity, config.max_single_loss)
    if rejection:
        return RiskReport(
            check_result=RiskCheckResult.REJECTED,
            risk_level=RiskLevel.EXTREME,
            rejected_reason=rejection,
            position_risks=positions,
            metrics=compute_risk_metrics(
                current_equity, peak_equity, daily_pnl,
                total_trades, winning_trades, losing_trades, positions,
            ),
        )

    rejection = check_daily_loss(daily_pnl, trade.estimated_loss, current_equity, config.max_daily_loss)
    if rejection:
        return RiskReport(
            check_result=RiskCheckResult.REJECTED,
            risk_level=RiskLevel.HIGH,
            rejected_reason=rejection,
            position_risks=positions,
            metrics=compute_risk_metrics(
                current_equity, peak_equity, daily_pnl,
                total_trades, winning_trades, losing_trades, positions,
            ),
        )

    drawdown = compute_drawdown(peak_equity, current_equity)
    rejection = check_max_drawdown(drawdown, config.max_drawdown)
    if rejection:
        return RiskReport(
            check_result=RiskCheckResult.REJECTED,
            risk_level=RiskLevel.EXTREME,
            rejected_reason=rejection,
            position_risks=positions,
            metrics=compute_risk_metrics(
                current_equity, peak_equity, daily_pnl,
                total_trades, winning_trades, losing_trades, positions,
            ),
        )

    distance_warning = check_stop_loss_distance(trade.side, trade.price, trade.stop_loss)
    if distance_warning:
        warnings.append(distance_warning)

    risk_level = determine_risk_level(position_ratio, config.max_position_size, bool(warnings))
    check_result = RiskCheckResult.WARNING if warnings else RiskCheckResult.PASSED

    return RiskReport(
        check_result=check_result,
        risk_level=risk_level,
        warnings=warnings,
        position_risks=positions,
        metrics=compute_risk_metrics(
            current_equity, peak_equity, daily_pnl,
            total_trades, winning_trades, losing_trades, positions,
        ),
    )


def build_trade_risk_from_signal(
    action: str,
    symbol: str,
    quantity: float,
    price: float,
    confidence: float,
    config: RiskConfig,
) -> TradeRisk:
    estimated_value = quantity * price
    estimated_loss = estimated_value * config.stop_loss_pct

    if action in ("LONG", "BUY"):
        side = "buy"
    else:
        side = "sell"

    stop_loss = compute_stop_loss_price(price, side, config.stop_loss_pct)
    take_profit = compute_take_profit_price(price, side, config.take_profit_pct)

    return TradeRisk(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        estimated_value=estimated_value,
        estimated_loss=estimated_loss,
        risk_level=RiskLevel.LOW,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
