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
            "timestamp": self.timestamp.iso