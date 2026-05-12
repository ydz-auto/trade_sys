"""
Risk Service - 风控服务

功能：
- 仓位管理
- 止损止盈
- 最大回撤控制
- 资金使用率控制
- 风险敞口监控

架构：
Signal → RiskService → Check → ExecutionService → Order
"""

from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger

logger = get_logger("risk_service")


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class RiskCheckResult(str, Enum):
    """风控检查结果"""
    PASSED = "passed"
    REJECTED = "rejected"
    WARNING = "warning"


@dataclass
class RiskConfig:
    """风控配置"""
    max_position_size: float = 0.1  # 最大仓位 (占总资金比例)
    max_single_loss: float = 0.02   # 单笔最大亏损 (2%)
    max_daily_loss: float = 0.05   # 日内最大亏损 (5%)
    max_drawdown: float = 0.15     # 最大回撤 (15%)
    max_leverage: float = 3.0      # 最大杠杆
    stop_loss_pct: float = 0.02    # 止损比例 (2%)
    take_profit_pct: float = 0.05 # 止盈比例 (5%)
    min_confidence: float = 0.5    # 最小置信度


@dataclass
class PositionRisk:
    """持仓风险"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    side: str = "buy"  # 持仓方向
    stop_loss: float = 0.0
    take_profit: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_pct: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class RiskReport:
    """风控报告"""
    check_result: RiskCheckResult
    risk_level: RiskLevel
    rejected_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    position_risks: List[PositionRisk] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeRisk:
    """交易风险"""
    symbol: str
    side: str
    quantity: float
    price: float
    estimated_value: float
    estimated_loss: float
    risk_level: RiskLevel
    stop_loss: float
    take_profit: float


class RiskService:
    """风控服务

    在订单执行前进行风险检查
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self._positions: Dict[str, PositionRisk] = {}
        self._daily_pnl: float = 0.0
        self._peak_equity: float = 0.0
        self._current_equity: float = 100000.0  # 模拟初始资金
        self._total_trades: int = 0
        self._winning_trades: int = 0
        self._losing_trades: int = 0
        self._trade_history: List[Dict] = []

    def update_price(self, symbol: str, price: float):
        """更新持仓价格"""
        if symbol in self._positions:
            pos = self._positions[symbol]
            pos.current_price = price
            pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            pos.pnl_pct = (price - pos.entry_price) / pos.entry_price

    def add_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        current_price: float = None,
        side: str = "buy"
    ):
        """添加持仓"""
        current_price = current_price or entry_price
        stop_loss = entry_price * (1 - self.config.stop_loss_pct)
        take_profit = entry_price * (1 + self.config.take_profit_pct)

        pos = PositionRisk(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            side=side,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        pos.unrealized_pnl = (current_price - entry_price) * quantity
        pos.pnl_pct = (current_price - entry_price) / entry_price

        self._positions[symbol] = pos
        self._update_equity()

    def remove_position(self, symbol: str, pnl: float = 0):
        """移除持仓"""
        if symbol in self._positions:
            del self._positions[symbol]

            # 更新统计
            self._total_trades += 1
            if pnl > 0:
                self._winning_trades += 1
            else:
                self._losing_trades += 1

            self._daily_pnl += pnl
            self._update_equity()

    def _update_equity(self):
        """更新权益"""
        unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())
        self._current_equity = 100000.0 + self._daily_pnl + unrealized

        if self._current_equity > self._peak_equity:
            self._peak_equity = self._current_equity

    def check_trade(self, trade: TradeRisk) -> RiskReport:
        """检查交易风险"""
        warnings = []
        risk_level = RiskLevel.LOW

        # 1. 检查仓位大小
        position_ratio = trade.quantity * trade.price / self._current_equity
        if position_ratio > self.config.max_position_size:
            return RiskReport(
                check_result=RiskCheckResult.REJECTED,
                risk_level=RiskLevel.HIGH,
                rejected_reason=f"仓位过大: {position_ratio:.2%} > {self.config.max_position_size:.2%}"
            )

        if position_ratio > self.config.max_position_size * 0.8:
            warnings.append(f"仓位接近上限: {position_ratio:.2%}")

        # 2. 检查置信度
        # 如果有置信度信息，进行检查
        confidence = trade.metadata.get("confidence", 1.0) if hasattr(trade, "metadata") else 1.0

        # 3. 检查单笔亏损
        if abs(trade.estimated_loss) > self._current_equity * self.config.max_single_loss:
            return RiskReport(
                check_result=RiskCheckResult.REJECTED,
                risk_level=RiskLevel.EXTREME,
                rejected_reason=f"单笔亏损过大: {abs(trade.estimated_loss):.2f} > {self._current_equity * self.config.max_single_loss:.2f}"
            )

        # 4. 检查日内亏损
        if abs(self._daily_pnl - trade.estimated_loss) > self._current_equity * self.config.max_daily_loss:
            return RiskReport(
                check_result=RiskCheckResult.REJECTED,
                risk_level=RiskLevel.HIGH,
                rejected_reason=f"日内亏损超限: {abs(self._daily_pnl - trade.estimated_loss):.2f} > {self._current_equity * self.config.max_daily_loss:.2f}"
            )

        # 5. 检查最大回撤
        drawdown = (self._peak_equity - self._current_equity) / self._peak_equity if self._peak_equity > 0 else 0
        if drawdown > self.config.max_drawdown:
            return RiskReport(
                check_result=RiskCheckResult.REJECTED,
                risk_level=RiskLevel.EXTREME,
                rejected_reason=f"最大回撤超限: {drawdown:.2%} > {self.config.max_drawdown:.2%}"
            )

        # 6. 检查止损止盈
        if trade.side.lower() in ["buy", "long"]:
            if trade.stop_loss < trade.price * 0.9:  # 止损不能超过 10%
                warnings.append("止损距离过大")
        else:
            if trade.take_profit < trade.price * 0.9:
                warnings.append("止盈距离过大")

        # 确定风险等级
        if warnings:
            risk_level = RiskLevel.MEDIUM
        if position_ratio > self.config.max_position_size * 0.5:
            risk_level = RiskLevel.HIGH

        # 返回结果
        check_result = RiskCheckResult.PASSED
        if warnings:
            check_result = RiskCheckResult.WARNING

        return RiskReport(
            check_result=check_result,
            risk_level=risk_level,
            warnings=warnings,
            position_risks=list(self._positions.values()),
            metrics=self.get_metrics()
        )

    def check_signal(self, signal: dict) -> RiskReport:
        """检查信号风险"""
        action = signal.get("action", "")
        symbol = signal.get("symbol", "BTC")
        quantity = signal.get("quantity", 0)
        price = signal.get("price", 50000.0)
        confidence = signal.get("confidence", 0.5)

        # 跳过 HOLD
        if action == "HOLD":
            return RiskReport(
                check_result=RiskCheckResult.PASSED,
                risk_level=RiskLevel.LOW,
                metrics=self.get_metrics()
            )

        # 估算价值
        estimated_value = quantity * price
        estimated_loss = estimated_value * self.config.stop_loss_pct

        # 获取方向
        side = "buy" if action in ["LONG", "BUY"] else "sell"

        # 止损止盈
        if side == "buy":
            stop_loss = price * (1 - self.config.stop_loss_pct)
            take_profit = price * (1 + self.config.take_profit_pct)
        else:
            stop_loss = price * (1 + self.config.stop_loss_pct)
            take_profit = price * (1 - self.config.take_profit_pct)

        trade = TradeRisk(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            estimated_value=estimated_value,
            estimated_loss=estimated_loss,
            risk_level=RiskLevel.LOW,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        trade.metadata = {"confidence": confidence}

        return self.check_trade(trade)

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """检查是否触发止损"""
        if symbol not in self._positions:
            return False

        pos = self._positions[symbol]

        if pos.side == "buy" and current_price <= pos.stop_loss:
            logger.warning(f"Stop loss triggered for {symbol}: {current_price} <= {pos.stop_loss}")
            return True

        if pos.side == "sell" and current_price >= pos.stop_loss:
            logger.warning(f"Stop loss triggered for {symbol}: {current_price} >= {pos.stop_loss}")
            return True

        return False

    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """检查是否触发止盈"""
        if symbol not in self._positions:
            return False

        pos = self._positions[symbol]

        if pos.side == "buy" and current_price >= pos.take_profit:
            logger.info(f"Take profit triggered for {symbol}: {current_price} >= {pos.take_profit}")
            return True

        if pos.side == "sell" and current_price <= pos.take_profit:
            logger.info(f"Take profit triggered for {symbol}: {current_price} <= {pos.take_profit}")
            return True

        return False

    def get_metrics(self) -> Dict[str, Any]:
        """获取风控指标"""
        drawdown = (self._peak_equity - self._current_equity) / self._peak_equity if self._peak_equity > 0 else 0
        win_rate = self._winning_trades / self._total_trades if self._total_trades > 0 else 0

        total_exposure = sum(pos.quantity * pos.current_price for pos in self._positions.values())
        exposure_ratio = total_exposure / self._current_equity if self._current_equity > 0 else 0

        return {
            "current_equity": self._current_equity,
            "peak_equity": self._peak_equity,
            "drawdown": drawdown,
            "daily_pnl": self._daily_pnl,
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "losing_trades": self._losing_trades,
            "win_rate": win_rate,
            "total_exposure": total_exposure,
            "exposure_ratio": exposure_ratio,
            "positions_count": len(self._positions)
        }

    def get_positions_risk(self) -> List[PositionRisk]:
        """获取所有持仓风险"""
        return list(self._positions.values())


# 全局实例
_risk_service: Optional[RiskService] = None


def get_risk_service() -> RiskService:
    """获取风控服务单例"""
    global _risk_service
    if _risk_service is None:
        _risk_service = RiskService()
    return _risk_service


def init_risk_service(config: RiskConfig = None) -> RiskService:
    """初始化风控服务"""
    global _risk_service
    _risk_service = RiskService(config)
    return _risk_service
