"""
CapitalAllocator - 资金分配器

管理投资组合的资金分配
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class AllocationStrategy(str, Enum):
    """分配策略"""
    EQUAL = "equal"
    RISK_PARITY = "risk_parity"
    KELLY = "kelly"
    FIXED = "fixed"


@dataclass
class AllocationResult:
    """分配结果"""
    symbol: str
    exchange: str
    
    allocated_capital: float = 0.0
    allocated_quantity: float = 0.0
    suggested_leverage: int = 1
    
    max_position_value: float = 0.0
    risk_amount: float = 0.0
    
    warnings: List[str] = field(default_factory=list)
    approved: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "allocated_capital": self.allocated_capital,
            "allocated_quantity": self.allocated_quantity,
            "suggested_leverage": self.suggested_leverage,
            "max_position_value": self.max_position_value,
            "risk_amount": self.risk_amount,
            "warnings": self.warnings,
            "approved": self.approved,
        }


@dataclass
class CapitalAllocatorConfig:
    """资金分配配置"""
    default_position_size: float = 0.1
    max_position_size: float = 0.2
    min_position_size: float = 0.01
    
    default_leverage: int = 1
    max_leverage: int = 10
    
    risk_per_trade: float = 0.02
    max_daily_risk: float = 0.05
    
    allocation_strategy: AllocationStrategy = AllocationStrategy.FIXED
    
    reserve_ratio: float = 0.1


class CapitalAllocator:
    """
    资金分配器
    
    职责：
    1. 计算可用资金
    2. 分配仓位大小
    3. 风险预算管理
    4. 杠杆建议
    """
    
    def __init__(self, config: CapitalAllocatorConfig = None):
        self.config = config or CapitalAllocatorConfig()
    
    def calculate_available_capital(
        self,
        total_capital: float,
        used_margin: float,
        reserve_ratio: float = None,
    ) -> float:
        """计算可用资金"""
        reserve = reserve_ratio or self.config.reserve_ratio
        reserved_capital = total_capital * reserve
        available = total_capital - used_margin - reserved_capital
        return max(0.0, available)
    
    def calculate_position_size(
        self,
        capital: float,
        price: float,
        stop_loss_price: Optional[float] = None,
        confidence: float = 0.5,
        volatility: float = 0.02,
    ) -> AllocationResult:
        """
        计算仓位大小
        
        Args:
            capital: 可用资金
            price: 当前价格
            stop_loss_price: 止损价格
            confidence: 信号置信度
            volatility: 波动率
        
        Returns:
            AllocationResult
        """
        result = AllocationResult(symbol="", exchange="")
        
        if capital <= 0 or price <= 0:
            result.approved = False
            result.warnings.append("Invalid capital or price")
            return result
        
        if self.config.allocation_strategy == AllocationStrategy.FIXED:
            position_value = capital * self.config.default_position_size
        
        elif self.config.allocation_strategy == AllocationStrategy.KELLY:
            win_rate = 0.5 + confidence * 0.2
            avg_win = volatility * 1.5
            avg_loss = volatility
            
            kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
            kelly_fraction = max(0, min(kelly_fraction, 0.25))
            
            position_value = capital * kelly_fraction
        
        elif self.config.allocation_strategy == AllocationStrategy.RISK_PARITY:
            risk_budget = capital * self.config.risk_per_trade
            
            if stop_loss_price and price > 0:
                risk_per_unit = abs(price - stop_loss_price)
                if risk_per_unit > 0:
                    position_value = risk_budget / risk_per_unit * price
                else:
                    position_value = capital * self.config.default_position_size
            else:
                position_value = capital * self.config.default_position_size
        
        else:
            position_value = capital * self.config.default_position_size
        
        position_value = min(position_value, capital * self.config.max_position_size)
        position_value = max(position_value, capital * self.config.min_position_size)
        
        result.allocated_capital = position_value
        result.allocated_quantity = position_value / price
        result.max_position_value = capital * self.config.max_position_size
        
        if stop_loss_price:
            risk_per_unit = abs(price - stop_loss_price)
            result.risk_amount = result.allocated_quantity * risk_per_unit
        
        if result.allocated_capital > capital * self.config.max_position_size:
            result.warnings.append(f"Position size capped at {self.config.max_position_size:.0%}")
        
        return result
    
    def suggest_leverage(
        self,
        position_value: float,
        available_capital: float,
        confidence: float = 0.5,
        volatility: float = 0.02,
    ) -> int:
        """
        建议杠杆
        
        Args:
            position_value: 仓位价值
            available_capital: 可用资金
            confidence: 信号置信度
            volatility: 波动率
        
        Returns:
            建议杠杆倍数
        """
        if available_capital <= 0:
            return 1
        
        base_leverage = min(
            int(position_value / available_capital) + 1,
            self.config.max_leverage,
        )
        
        if volatility > 0.05:
            base_leverage = max(1, base_leverage - 2)
        
        if confidence < 0.6:
            base_leverage = max(1, base_leverage - 1)
        
        return min(base_leverage, self.config.default_leverage)
    
    def allocate_for_trade(
        self,
        symbol: str,
        exchange: str,
        capital: float,
        price: float,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        confidence: float = 0.5,
        volatility: float = 0.02,
        used_margin: float = 0.0,
    ) -> AllocationResult:
        """
        为交易分配资金
        
        Args:
            symbol: 交易品种
            exchange: 交易所
            capital: 总资金
            price: 当前价格
            stop_loss_price: 止损价格
            take_profit_price: 止盈价格
            confidence: 信号置信度
            volatility: 波动率
            used_margin: 已用保证金
        
        Returns:
            AllocationResult
        """
        result = AllocationResult(symbol=symbol, exchange=exchange)
        
        available = self.calculate_available_capital(capital, used_margin)
        
        if available <= 0:
            result.approved = False
            result.warnings.append("No available capital")
            return result
        
        allocation = self.calculate_position_size(
            capital=available,
            price=price,
            stop_loss_price=stop_loss_price,
            confidence=confidence,
            volatility=volatility,
        )
        
        result.allocated_capital = allocation.allocated_capital
        result.allocated_quantity = allocation.allocated_quantity
        result.risk_amount = allocation.risk_amount
        result.warnings.extend(allocation.warnings)
        
        result.suggested_leverage = self.suggest_leverage(
            position_value=result.allocated_capital,
            available_capital=available,
            confidence=confidence,
            volatility=volatility,
        )
        
        if stop_loss_price:
            risk_ratio = result.risk_amount / capital
            if risk_ratio > self.config.risk_per_trade:
                result.warnings.append(f"Risk {risk_ratio:.2%} exceeds limit {self.config.risk_per_trade:.2%}")
                scale = self.config.risk_per_trade / risk_ratio
                result.allocated_capital *= scale
                result.allocated_quantity *= scale
                result.risk_amount *= scale
        
        result.max_position_value = capital * self.config.max_position_size
        
        return result
    
    def calculate_risk_budget(
        self,
        capital: float,
        daily_pnl: float = 0.0,
    ) -> Dict[str, float]:
        """
        计算风险预算
        
        Args:
            capital: 总资金
            daily_pnl: 今日盈亏
        
        Returns:
            风险预算信息
        """
        max_risk = capital * self.config.max_daily_risk
        used_risk = max(0, -daily_pnl)
        remaining_risk = max(0, max_risk - used_risk)
        
        return {
            "max_daily_risk": max_risk,
            "used_risk": used_risk,
            "remaining_risk": remaining_risk,
            "risk_per_trade": capital * self.config.risk_per_trade,
            "can_trade": remaining_risk > capital * self.config.risk_per_trade,
        }
    
    def rebalance_suggestions(
        self,
        positions: Dict[str, Dict[str, Any]],
        target_allocation: Dict[str, float],
        capital: float,
    ) -> List[Dict[str, Any]]:
        """
        再平衡建议
        
        Args:
            positions: 当前持仓
            target_allocation: 目标分配比例
            capital: 总资金
        
        Returns:
            再平衡建议列表
        """
        suggestions = []
        
        current_values = {}
        for key, pos in positions.items():
            current_values[key] = pos.get("notional_value", 0.0)
        
        total_current = sum(current_values.values())
        
        for symbol, target_ratio in target_allocation.items():
            target_value = capital * target_ratio
            current_value = current_values.get(symbol, 0.0)
            
            diff = target_value - current_value
            
            if abs(diff) > capital * 0.01:
                suggestions.append({
                    "symbol": symbol,
                    "action": "buy" if diff > 0 else "sell",
                    "value": abs(diff),
                    "reason": f"Rebalance to {target_ratio:.1%}",
                })
        
        return suggestions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "default_position_size": self.config.default_position_size,
                "max_position_size": self.config.max_position_size,
                "min_position_size": self.config.min_position_size,
                "default_leverage": self.config.default_leverage,
                "max_leverage": self.config.max_leverage,
                "risk_per_trade": self.config.risk_per_trade,
                "max_daily_risk": self.config.max_daily_risk,
                "allocation_strategy": self.config.allocation_strategy.value,
            },
        }
