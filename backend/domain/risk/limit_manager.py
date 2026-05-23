"""
Limit Manager - 限额管理

管理交易限额:
1. 仓位限额
2. 亏损限额
3. 频率限额
4. 杠杆限额
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("risk.limit_manager")


class LimitType(str, Enum):
    POSITION_SIZE = "position_size"
    DAILY_LOSS = "daily_loss"
    DRAWDOWN = "drawdown"
    LEVERAGE = "leverage"
    TRADE_COUNT = "trade_count"
    EXPOSURE = "exposure"


@dataclass
class LimitCheck:
    limit_type: LimitType
    current_value: float
    limit_value: float
    utilization_pct: float
    
    is_breached: bool
    is_warning: bool
    
    message: str


@dataclass
class LimitCheckResult:
    timestamp: datetime
    
    checks: List[LimitCheck]
    
    all_passed: bool
    any_warning: bool
    any_breach: bool
    
    breached_limits: List[LimitType]
    
    can_trade: bool
    recommended_action: str


@dataclass
class LimitManager:
    max_position_size: float = 10000.0
    max_daily_loss: float = 50000.0
    max_drawdown: float = 0.1
    max_leverage: float = 10.0
    max_trades_per_day: int = 50
    max_gross_exposure: float = 100000.0
    
    warning_threshold: float = 0.8
    
    def __post_init__(self):
        self._daily_pnl: float = 0.0
        self._trade_count: int = 0
        self._last_reset: datetime = datetime.now()
    
    def check(
        self,
        position_size: float,
        position_value: float,
        leverage: float,
        account_balance: float,
        peak_balance: float,
        gross_exposure: float,
    ) -> LimitCheckResult:
        timestamp = datetime.now()
        self._reset_if_new_day(timestamp)
        
        checks = []
        
        checks.append(self._check_position_size(position_size))
        checks.append(self._check_daily_loss(account_balance))
        checks.append(self._check_drawdown(account_balance, peak_balance))
        checks.append(self._check_leverage(leverage))
        checks.append(self._check_trade_count())
        checks.append(self._check_exposure(gross_exposure))
        
        all_passed = all(not c.is_breached for c in checks)
        any_warning = any(c.is_warning for c in checks)
        any_breach = any(c.is_breached for c in checks)
        
        breached = [c.limit_type for c in checks if c.is_breached]
        
        can_trade = all_passed and not any_breach
        
        action = self._determine_action(can_trade, any_warning, breached)
        
        return LimitCheckResult(
            timestamp=timestamp,
            checks=checks,
            all_passed=all_passed,
            any_warning=any_warning,
            any_breach=any_breach,
            breached_limits=breached,
            can_trade=can_trade,
            recommended_action=action,
        )
    
    def _check_position_size(self, size: float) -> LimitCheck:
        utilization = abs(size) / self.max_position_size if self.max_position_size > 0 else 0.0
        
        return LimitCheck(
            limit_type=LimitType.POSITION_SIZE,
            current_value=abs(size),
            limit_value=self.max_position_size,
            utilization_pct=utilization * 100,
            is_breached=utilization > 1.0,
            is_warning=utilization > self.warning_threshold,
            message=f"Position size: {abs(size):.2f} / {self.max_position_size:.2f}",
        )
    
    def _check_daily_loss(self, balance: float) -> LimitCheck:
        loss = max(0, -self._daily_pnl)
        utilization = loss / self.max_daily_loss if self.max_daily_loss > 0 else 0.0
        
        return LimitCheck(
            limit_type=LimitType.DAILY_LOSS,
            current_value=loss,
            limit_value=self.max_daily_loss,
            utilization_pct=utilization * 100,
            is_breached=utilization > 1.0,
            is_warning=utilization > self.warning_threshold,
            message=f"Daily loss: {loss:.2f} / {self.max_daily_loss:.2f}",
        )
    
    def _check_drawdown(self, balance: float, peak: float) -> LimitCheck:
        if peak <= 0:
            drawdown = 0.0
        else:
            drawdown = (peak - balance) / peak
        
        return LimitCheck(
            limit_type=LimitType.DRAWDOWN,
            current_value=drawdown,
            limit_value=self.max_drawdown,
            utilization_pct=drawdown / self.max_drawdown * 100 if self.max_drawdown > 0 else 0.0,
            is_breached=drawdown > self.max_drawdown,
            is_warning=drawdown > self.max_drawdown * self.warning_threshold,
            message=f"Drawdown: {drawdown * 100:.2f}% / {self.max_drawdown * 100:.2f}%",
        )
    
    def _check_leverage(self, leverage: float) -> LimitCheck:
        return LimitCheck(
            limit_type=LimitType.LEVERAGE,
            current_value=leverage,
            limit_value=self.max_leverage,
            utilization_pct=leverage / self.max_leverage * 100 if self.max_leverage > 0 else 0.0,
            is_breached=leverage > self.max_leverage,
            is_warning=leverage > self.max_leverage * self.warning_threshold,
            message=f"Leverage: {leverage:.1f}x / {self.max_leverage:.1f}x",
        )
    
    def _check_trade_count(self) -> LimitCheck:
        return LimitCheck(
            limit_type=LimitType.TRADE_COUNT,
            current_value=self._trade_count,
            limit_value=self.max_trades_per_day,
            utilization_pct=self._trade_count / self.max_trades_per_day * 100 if self.max_trades_per_day > 0 else 0.0,
            is_breached=self._trade_count >= self.max_trades_per_day,
            is_warning=self._trade_count >= self.max_trades_per_day * self.warning_threshold,
            message=f"Trade count: {self._trade_count} / {self.max_trades_per_day}",
        )
    
    def _check_exposure(self, exposure: float) -> LimitCheck:
        return LimitCheck(
            limit_type=LimitType.EXPOSURE,
            current_value=exposure,
            limit_value=self.max_gross_exposure,
            utilization_pct=exposure / self.max_gross_exposure * 100 if self.max_gross_exposure > 0 else 0.0,
            is_breached=exposure > self.max_gross_exposure,
            is_warning=exposure > self.max_gross_exposure * self.warning_threshold,
            message=f"Gross exposure: {exposure:.2f} / {self.max_gross_exposure:.2f}",
        )
    
    def _reset_if_new_day(self, now: datetime) -> None:
        if now.date() != self._last_reset.date():
            self._daily_pnl = 0.0
            self._trade_count = 0
            self._last_reset = now
    
    def _determine_action(
        self,
        can_trade: bool,
        any_warning: bool,
        breached: List[LimitType],
    ) -> str:
        if not can_trade:
            return f"Trading blocked: {', '.join(b.value for b in breached)} limits breached"
        
        if any_warning:
            return "Warning: Approaching limit thresholds"
        
        return "All limits OK - trading allowed"
    
    def record_trade(self, pnl: float) -> None:
        self._daily_pnl += pnl
        self._trade_count += 1


def check_limits(
    position_size: float,
    position_value: float,
    leverage: float,
    account_balance: float,
    peak_balance: float,
    gross_exposure: float,
    manager: Optional[LimitManager] = None,
) -> LimitCheckResult:
    manager = manager or LimitManager()
    return manager.check(
        position_size, position_value, leverage,
        account_balance, peak_balance, gross_exposure
    )
