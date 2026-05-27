"""
Account & Balance Model - 账户和资金模型

完整的保证金账户系统:
- Wallet Balance (钱包余额)
- Available Balance (可用余额)
- Used Margin (已用保证金)
- Unrealized PnL (未实现盈亏)
- Equity (账户权益)
- Margin Ratio (保证金率)
"""

from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from domain.execution.models.position import Position
from domain.execution.models.enums import MarketType

import logging

logger = logging.getLogger(__name__)


class AccountStatus(str, Enum):
    """账户状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    DANGER = "danger"
    LIQUIDATED = "liquidated"


@dataclass
class AccountSnapshot:
    """账户快照"""
    timestamp: datetime
    
    wallet_balance: float
    available_balance: float
    used_margin: float
    unrealized_pnl: float
    equity: float
    
    margin_ratio: float
    maintenance_margin: float
    
    total_fees: float
    total_funding: float
    total_realized_pnl: float
    
    status: AccountStatus
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "wallet_balance": self.wallet_balance,
            "available_balance": self.available_balance,
            "used_margin": self.used_margin,
            "unrealized_pnl": self.unrealized_pnl,
            "equity": self.equity,
            "margin_ratio": self.margin_ratio,
            "maintenance_margin": self.maintenance_margin,
            "total_fees": self.total_fees,
            "total_funding": self.total_funding,
            "total_realized_pnl": self.total_realized_pnl,
            "status": self.status.value if self.status else None,
        }


@dataclass
class AccountModel:
    """账户模型 - 完整的保证金账户系统"""
    
    initial_balance: float
    current_balance: float = 0.0
    used_margin: float = 0.0
    unrealized_pnl: float = 0.0
    frozen_balance: float = 0.0
    
    total_fees: float = 0.0
    total_funding: float = 0.0
    total_realized_pnl: float = 0.0
    
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: List[Dict[str, Any]] = field(default_factory=list)
    
    max_leverage: int = 125
    maintenance_margin_rate: float = 0.004
    
    _balance_history: List[AccountSnapshot] = field(default_factory=list)
    
    def __post_init__(self):
        if self.current_balance == 0.0:
            self.current_balance = self.initial_balance
    
    @property
    def available_balance(self) -> float:
        """可用余额 = 钱包余额 - 已用保证金 - 冻结资金 + 未实现盈亏"""
        return self.current_balance - self.used_margin - self.frozen_balance + self.unrealized_pnl
    
    @property
    def equity(self) -> float:
        """账户权益 = 钱包余额 + 未实现盈亏"""
        return self.current_balance + self.unrealized_pnl
    
    @property
    def margin_ratio(self) -> float:
        """保证金率 = 可用余额 / 账户权益"""
        if self.equity == 0:
            return 0.0
        return self.available_balance / self.equity if self.equity > 0 else 0.0
    
    def get_status(self) -> AccountStatus:
        """获取账户状态"""
        if self.margin_ratio <= 0:
            return AccountStatus.LIQUIDATED
        elif self.margin_ratio < 0.05:
            return AccountStatus.DANGER
        elif self.margin_ratio < 0.15:
            return AccountStatus.WARNING
        else:
            return AccountStatus.HEALTHY
    
    def add_fee(self, fee: float):
        """添加手续费"""
        self.total_fees += fee
    
    def add_funding(self, funding: float):
        """添加资金费用"""
        self.total_funding += funding
    
    def add_realized_pnl(self, pnl: float):
        """添加已实现盈亏"""
        self.total_realized_pnl += pnl
    
    def update_unrealized_pnl(self, pnl: float):
        """更新未实现盈亏"""
        self.unrealized_pnl = pnl
    
    def freeze_balance(self, amount: float):
        """冻结资金"""
        if amount > self.available_balance:
            raise ValueError(f"Insufficient balance to freeze: {amount} > {self.available_balance}")
        self.frozen_balance += amount
    
    def unfreeze_balance(self, amount: float):
        """解冻资金"""
        self.frozen_balance = max(0, self.frozen_balance - amount)
    
    def add_margin(self, symbol: str, margin: float):
        """增加持仓保证金"""
        if margin > self.available_balance:
            raise ValueError(f"Insufficient balance for margin: {margin} > {self.available_balance}")
        self.used_margin += margin
    
    def release_margin(self, symbol: str, margin: float):
        """释放持仓保证金"""
        self.used_margin = max(0, self.used_margin - margin)
    
    def create_snapshot(self) -> AccountSnapshot:
        """创建账户快照"""
        snapshot = AccountSnapshot(
            timestamp=datetime.now(),
            wallet_balance=self.current_balance,
            available_balance=self.available_balance,
            used_margin=self.used_margin,
            unrealized_pnl=self.unrealized_pnl,
            equity=self.equity,
            margin_ratio=self.margin_ratio,
            maintenance_margin=self.used_margin * self.maintenance_margin_rate,
            total_fees=self.total_fees,
            total_funding=self.total_funding,
            total_realized_pnl=self.total_realized_pnl,
            status=self.get_status(),
        )
        self._balance_history.append(snapshot)
        return snapshot
    
    def get_history(self) -> List[AccountSnapshot]:
        """获取账户历史"""
        return self._balance_history.copy()
    
    def reset(self):
        """重置账户"""
        self.current_balance = self.initial_balance
        self.used_margin = 0.0
        self.unrealized_pnl = 0.0
        self.frozen_balance = 0.0
        self.total_fees = 0.0
        self.total_funding = 0.0
        self.total_realized_pnl = 0.0
        self.positions.clear()
        self.orders.clear()
        self._balance_history.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "available_balance": self.available_balance,
            "used_margin": self.used_margin,
            "unrealized_pnl": self.unrealized_pnl,
            "frozen_balance": self.frozen_balance,
            "equity": self.equity,
            "margin_ratio": self.margin_ratio,
            "total_fees": self.total_fees,
            "total_funding": self.total_funding,
            "total_realized_pnl": self.total_realized_pnl,
            "status": self.get_status().value,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "max_leverage": self.max_leverage,
            "maintenance_margin_rate": self.maintenance_margin_rate,
        }