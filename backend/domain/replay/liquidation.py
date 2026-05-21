"""
Liquidation Model - 爆仓模型

模拟爆仓:
1. 维持保证金计算
2. 爆仓价格计算
3. 爆仓检测
4. 强平模拟
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("replay.liquidation")


class LiquidationStatus(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    LIQUIDATED = "liquidated"


@dataclass
class LiquidationResult:
    status: LiquidationStatus
    
    entry_price: float
    current_price: float
    liquidation_price: float
    
    margin_used: float
    maintenance_margin: float
    available_margin: float
    
    margin_ratio: float
    distance_to_liquidation_pct: float
    
    unrealized_pnl: float
    equity: float
    
    leverage: float
    effective_leverage: float


@dataclass
class LiquidationModel:
    maintenance_margin_rate: float = 0.005
    
    liquidation_buffer: float = 0.1
    
    warning_threshold: float = 0.5
    danger_threshold: float = 0.2
    
    def check(
        self,
        position_size: float,
        entry_price: float,
        current_price: float,
        leverage: float,
        account_balance: float,
        position_side: str = "long",
    ) -> LiquidationResult:
        position_value = abs(position_size) * entry_price
        margin_used = position_value / leverage
        
        maintenance_margin = position_value * self.maintenance_margin_rate
        
        if position_side == "long":
            unrealized_pnl = (current_price - entry_price) * position_size
            liq_price = entry_price * (1 - (1 / leverage) + self.maintenance_margin_rate)
        else:
            unrealized_pnl = (entry_price - current_price) * abs(position_size)
            liq_price = entry_price * (1 + (1 / leverage) - self.maintenance_margin_rate)
        
        equity = account_balance + unrealized_pnl
        
        available_margin = equity - maintenance_margin
        
        if equity > 0:
            effective_leverage = position_value / equity
        else:
            effective_leverage = float('inf')
        
        if equity <= maintenance_margin:
            margin_ratio = 0.0
        else:
            margin_ratio = maintenance_margin / equity
        
        if position_side == "long":
            if current_price <= liq_price:
                distance_pct = 0.0
            else:
                distance_pct = (current_price - liq_price) / current_price
        else:
            if current_price >= liq_price:
                distance_pct = 0.0
            else:
                distance_pct = (liq_price - current_price) / current_price
        
        status = self._determine_status(margin_ratio, distance_pct)
        
        return LiquidationResult(
            status=status,
            entry_price=entry_price,
            current_price=current_price,
            liquidation_price=liq_price,
            margin_used=margin_used,
            maintenance_margin=maintenance_margin,
            available_margin=available_margin,
            margin_ratio=margin_ratio,
            distance_to_liquidation_pct=distance_pct,
            unrealized_pnl=unrealized_pnl,
            equity=equity,
            leverage=leverage,
            effective_leverage=effective_leverage,
        )
    
    def _determine_status(
        self,
        margin_ratio: float,
        distance_pct: float,
    ) -> LiquidationStatus:
        if margin_ratio >= 1.0 or distance_pct <= 0:
            return LiquidationStatus.LIQUIDATED
        
        if distance_pct < self.danger_threshold:
            return LiquidationStatus.DANGER
        
        if distance_pct < self.warning_threshold:
            return LiquidationStatus.WARNING
        
        return LiquidationStatus.SAFE
    
    def calculate_max_leverage(
        self,
        account_balance: float,
        position_value: float,
        current_price: float,
        entry_price: float,
        position_side: str,
        buffer: float = 0.1,
    ) -> float:
        if position_side == "long":
            price_diff_pct = (current_price - entry_price) / entry_price
        else:
            price_diff_pct = (entry_price - current_price) / entry_price
        
        equity = account_balance + position_value * price_diff_pct
        
        if equity <= 0:
            return 1.0
        
        max_lev = equity / (position_value * self.maintenance_margin_rate * (1 + buffer))
        
        return max(1.0, min(100.0, max_lev))
    
    def simulate_liquidation_cascade(
        self,
        position_size: float,
        entry_price: float,
        leverage: float,
        account_balance: float,
        position_side: str,
        price_steps: int = 100,
    ) -> Dict[str, Any]:
        results = []
        
        if position_side == "long":
            liq_price = entry_price * (1 - (1 / leverage) + self.maintenance_margin_rate)
            prices = np.linspace(entry_price, liq_price * 0.9, price_steps)
        else:
            liq_price = entry_price * (1 + (1 / leverage) - self.maintenance_margin_rate)
            prices = np.linspace(entry_price, liq_price * 1.1, price_steps)
        
        for price in prices:
            result = self.check(
                position_size, entry_price, price,
                leverage, account_balance, position_side
            )
            results.append({
                "price": price,
                "equity": result.equity,
                "margin_ratio": result.margin_ratio,
                "status": result.status.value,
            })
        
        return {
            "liquidation_price": liq_price,
            "cascade": results,
            "total_loss": abs(account_balance),
        }


def check_liquidation(
    position_size: float,
    entry_price: float,
    current_price: float,
    leverage: float,
    account_balance: float,
    position_side: str = "long",
    model: Optional[LiquidationModel] = None,
) -> LiquidationResult:
    model = model or LiquidationModel()
    return model.check(
        position_size, entry_price, current_price,
        leverage, account_balance, position_side
    )
