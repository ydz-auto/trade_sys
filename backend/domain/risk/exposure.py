"""
Portfolio Exposure Risk - 投资组合敞口风险管理

提供组合级别的风险控制：
- 敞口聚合（按交易所、币种、方向）
- 敞口限制检查
- 相关性感知风险
- 动态杠杆控制
- 组合级止损
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import math

import logging

logger = logging.getLogger("domain.risk.exposure")


class ExposureType(str, Enum):
    """敞口类型"""
    LONG = "long"
    SHORT = "short"
    NET = "net"
    GROSS = "gross"


@dataclass
class PositionExposure:
    """持仓敞口"""
    symbol: str
    exchange: str
    
    quantity: float
    value: float
    
    entry_price: float
    current_price: float
    
    unrealized_pnl: float
    unrealized_pnl_pct: float
    
    leverage: float
    margin_used: float
    
    side: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "quantity": self.quantity,
            "value": self.value,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "leverage": self.leverage,
            "margin_used": self.margin_used,
            "side": self.side,
        }


@dataclass
class AggregatedExposure:
    """聚合敞口"""
    dimension: str
    value: str
    
    long_value: float
    short_value: float
    net_value: float
    gross_value: float
    
    leverage: float
    margin_used: float
    
    unrealized_pnl: float
    
    positions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "long_value": self.long_value,
            "short_value": self.short_value,
            "net_value": self.net_value,
            "gross_value": self.gross_value,
            "leverage": self.leverage,
            "margin_used": self.margin_used,
            "unrealized_pnl": self.unrealized_pnl,
            "positions": self.positions,
        }


@dataclass
class ExposureLimit:
    """敞口限制"""
    dimension: str
    value: Optional[str] = None
    
    max_long: Optional[float] = None
    max_short: Optional[float] = None
    max_net: Optional[float] = None
    max_gross: Optional[float] = None
    
    max_leverage: Optional[float] = None
    max_margin_pct: Optional[float] = None
    
    max_concentration: Optional[float] = None
    
    def check(
        self,
        exposure: AggregatedExposure,
    ) -> Tuple[bool, List[str]]:
        """检查敞口是否超限"""
        violations = []
        
        if self.max_long is not None and exposure.long_value > self.max_long:
            violations.append(f"Long exposure {exposure.long_value} exceeds limit {self.max_long}")
        
        if self.max_short is not None and exposure.short_value > self.max_short:
            violations.append(f"Short exposure {exposure.short_value} exceeds limit {self.max_short}")
        
        if self.max_net is not None and abs(exposure.net_value) > self.max_net:
            violations.append(f"Net exposure {exposure.net_value} exceeds limit {self.max_net}")
        
        if self.max_gross is not None and exposure.gross_value > self.max_gross:
            violations.append(f"Gross exposure {exposure.gross_value} exceeds limit {self.max_gross}")
        
        if self.max_leverage is not None and exposure.leverage > self.max_leverage:
            violations.append(f"Leverage {exposure.leverage} exceeds limit {self.max_leverage}")
        
        return len(violations) == 0, violations


@dataclass
class PortfolioRiskState:
    """组合风险状态"""
    timestamp: datetime
    
    total_capital: float
    available_capital: float
    locked_capital: float
    
    total_exposure: float
    net_exposure: float
    gross_exposure: float
    
    portfolio_leverage: float
    margin_used: float
    
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    
    drawdown: float
    max_drawdown: float
    
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    
    correlation_risk: Optional[float] = None
    
    violations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_capital": self.total_capital,
            "available_capital": self.available_capital,
            "locked_capital": self.locked_capital,
            "total_exposure": self.total_exposure,
            "net_exposure": self.net_exposure,
            "gross_exposure": self.gross_exposure,
            "portfolio_leverage": self.portfolio_leverage,
            "margin_used": self.margin_used,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "drawdown": self.drawdown,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "correlation_risk": self.correlation_risk,
            "violations": self.violations,
        }


class PortfolioExposureManager:
    """组合敞口管理器
    
    提供组合级别的敞口聚合和风险控制
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
    ):
        self.initial_capital = initial_capital
        self.total_capital = initial_capital
        self.available_capital = initial_capital
        self.locked_capital = 0.0
        
        self._positions: Dict[str, PositionExposure] = {}
        
        self._limits: Dict[str, ExposureLimit] = {}
        self._setup_default_limits()
        
        self._realized_pnl = 0.0
        self._peak_capital = initial_capital
        self._max_drawdown = 0.0
        
        self._correlations: Dict[Tuple[str, str], float] = {}
    
    def _setup_default_limits(self) -> None:
        """设置默认限制"""
        self._limits["portfolio"] = ExposureLimit(
            dimension="portfolio",
            max_gross=self.initial_capital * 2.0,
            max_leverage=3.0,
            max_margin_pct=0.8,
        )
        
        self._limits["exchange"] = ExposureLimit(
            dimension="exchange",
            max_gross=self.initial_capital * 1.0,
            max_leverage=5.0,
        )
        
        self._limits["symbol"] = ExposureLimit(
            dimension="symbol",
            max_gross=self.initial_capital * 0.2,
            max_concentration=0.2,
        )
    
    def set_limit(self, limit: ExposureLimit) -> None:
        """设置敞口限制"""
        key = f"{limit.dimension}:{limit.value or 'all'}"
        self._limits[key] = limit
        logger.info(f"Exposure limit set: {key}")
    
    def update_position(
        self,
        symbol: str,
        exchange: str,
        quantity: float,
        entry_price: float,
        current_price: float,
        leverage: float = 1.0,
    ) -> PositionExposure:
        """更新持仓"""
        position_key = f"{exchange}:{symbol}"
        
        value = abs(quantity) * current_price
        margin_used = value / leverage if leverage > 0 else value
        
        unrealized_pnl = (current_price - entry_price) * quantity
        unrealized_pnl_pct = unrealized_pnl / (abs(quantity) * entry_price) if entry_price > 0 else 0
        
        side = "long" if quantity > 0 else "short"
        
        position = PositionExposure(
            symbol=symbol,
            exchange=exchange,
            quantity=quantity,
            value=value,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            leverage=leverage,
            margin_used=margin_used,
            side=side,
        )
        
        self._positions[position_key] = position
        
        self._recalculate_capital()
        
        return position
    
    def remove_position(
        self,
        symbol: str,
        exchange: str,
        realized_pnl: float = 0.0,
    ) -> Optional[PositionExposure]:
        """移除持仓"""
        position_key = f"{exchange}:{symbol}"
        
        position = self._positions.pop(position_key, None)
        
        if position:
            self._realized_pnl += realized_pnl
            self._recalculate_capital()
        
        return position
    
    def _recalculate_capital(self) -> None:
        """重新计算资金"""
        total_margin = sum(p.margin_used for p in self._positions.values())
        total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        
        self.locked_capital = total_margin
        self.available_capital = self.total_capital - self.locked_capital
        
        current_capital = self.total_capital + total_unrealized + self._realized_pnl
        
        if current_capital > self._peak_capital:
            self._peak_capital = current_capital
        
        drawdown = (self._peak_capital - current_capital) / self._peak_capital
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown
    
    def get_exposure_by_exchange(self) -> Dict[str, AggregatedExposure]:
        """按交易所聚合敞口"""
        result: Dict[str, AggregatedExposure] = {}
        
        for pos in self._positions.values():
            exchange = pos.exchange
            
            if exchange not in result:
                result[exchange] = AggregatedExposure(
                    dimension="exchange",
                    value=exchange,
                    long_value=0.0,
                    short_value=0.0,
                    net_value=0.0,
                    gross_value=0.0,
                    leverage=0.0,
                    margin_used=0.0,
                    unrealized_pnl=0.0,
                    positions=[],
                )
            
            exp = result[exchange]
            
            if pos.side == "long":
                exp.long_value += pos.value
            else:
                exp.short_value += pos.value
            
            exp.net_value += pos.value if pos.side == "long" else -pos.value
            exp.gross_value += pos.value
            exp.margin_used += pos.margin_used
            exp.unrealized_pnl += pos.unrealized_pnl
            exp.positions.append(f"{pos.exchange}:{pos.symbol}")
        
        for exp in result.values():
            if exp.margin_used > 0:
                exp.leverage = exp.gross_value / exp.margin_used
        
        return result
    
    def get_exposure_by_symbol(self) -> Dict[str, AggregatedExposure]:
        """按币种聚合敞口"""
        result: Dict[str, AggregatedExposure] = {}
        
        for pos in self._positions.values():
            symbol = pos.symbol
            
            if symbol not in result:
                result[symbol] = AggregatedExposure(
                    dimension="symbol",
                    value=symbol,
                    long_value=0.0,
                    short_value=0.0,
                    net_value=0.0,
                    gross_value=0.0,
                    leverage=0.0,
                    margin_used=0.0,
                    unrealized_pnl=0.0,
                    positions=[],
                )
            
            exp = result[symbol]
            
            if pos.side == "long":
                exp.long_value += pos.value
            else:
                exp.short_value += pos.value
            
            exp.net_value += pos.value if pos.side == "long" else -pos.value
            exp.gross_value += pos.value
            exp.margin_used += pos.margin_used
            exp.unrealized_pnl += pos.unrealized_pnl
            exp.positions.append(f"{pos.exchange}:{pos.symbol}")
        
        for exp in result.values():
            if exp.margin_used > 0:
                exp.leverage = exp.gross_value / exp.margin_used
        
        return result
    
    def get_total_exposure(self) -> AggregatedExposure:
        """获取总敞口"""
        long_value = sum(p.value for p in self._positions.values() if p.side == "long")
        short_value = sum(p.value for p in self._positions.values() if p.side == "short")
        net_value = long_value - short_value
        gross_value = long_value + short_value
        margin_used = sum(p.margin_used for p in self._positions.values())
        unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())
        
        leverage = gross_value / margin_used if margin_used > 0 else 0.0
        
        return AggregatedExposure(
            dimension="portfolio",
            value="total",
            long_value=long_value,
            short_value=short_value,
            net_value=net_value,
            gross_value=gross_value,
            leverage=leverage,
            margin_used=margin_used,
            unrealized_pnl=unrealized_pnl,
            positions=list(self._positions.keys()),
        )
    
    def check_limits(self) -> Tuple[bool, List[str]]:
        """检查所有限制"""
        all_violations = []
        
        total_exposure = self.get_total_exposure()
        
        for key in ["portfolio:all", "portfolio"]:
            if key in self._limits:
                ok, violations = self._limits[key].check(total_exposure)
                all_violations.extend(violations)
                break
        
        for exchange, exposure in self.get_exposure_by_exchange().items():
            key = f"exchange:{exchange}"
            if key in self._limits:
                ok, violations = self._limits[key].check(exposure)
                all_violations.extend(violations)
            elif "exchange" in self._limits:
                ok, violations = self._limits["exchange"].check(exposure)
                all_violations.extend(violations)
        
        for symbol, exposure in self.get_exposure_by_symbol().items():
            key = f"symbol:{symbol}"
            if key in self._limits:
                ok, violations = self._limits[key].check(exposure)
                all_violations.extend(violations)
            elif "symbol" in self._limits:
                ok, violations = self._limits["symbol"].check(exposure)
                all_violations.extend(violations)
        
        return len(all_violations) == 0, all_violations
    
    def check_order(
        self,
        symbol: str,
        exchange: str,
        side: str,
        quantity: float,
        price: float,
        leverage: float = 1.0,
    ) -> Tuple[bool, List[str]]:
        """检查订单是否会导致敞口超限"""
        order_value = abs(quantity) * price
        order_margin = order_value / leverage if leverage > 0 else order_value
        
        if order_margin > self.available_capital:
            return False, [f"Insufficient capital: need {order_margin}, available {self.available_capital}"]
        
        simulated_positions = dict(self._positions)
        position_key = f"{exchange}:{symbol}"
        
        if position_key in simulated_positions:
            existing = simulated_positions[position_key]
            new_quantity = existing.quantity + (quantity if side == "long" else -quantity)
            if abs(new_quantity) < 1e-8:
                del simulated_positions[position_key]
            else:
                simulated_positions[position_key] = PositionExposure(
                    symbol=symbol,
                    exchange=exchange,
                    quantity=new_quantity,
                    value=abs(new_quantity) * price,
                    entry_price=existing.entry_price,
                    current_price=price,
                    unrealized_pnl=0,
                    unrealized_pnl_pct=0,
                    leverage=leverage,
                    margin_used=abs(new_quantity) * price / leverage,
                    side="long" if new_quantity > 0 else "short",
                )
        else:
            simulated_positions[position_key] = PositionExposure(
                symbol=symbol,
                exchange=exchange,
                quantity=quantity if side == "long" else -quantity,
                value=order_value,
                entry_price=price,
                current_price=price,
                unrealized_pnl=0,
                unrealized_pnl_pct=0,
                leverage=leverage,
                margin_used=order_margin,
                side=side,
            )
        
        violations = []
        
        total_gross = sum(p.value for p in simulated_positions.values())
        total_margin = sum(p.margin_used for p in simulated_positions.values())
        
        if "portfolio" in self._limits:
            limit = self._limits["portfolio"]
            if limit.max_gross and total_gross > limit.max_gross:
                violations.append(f"Order would exceed gross exposure limit: {total_gross} > {limit.max_gross}")
            if limit.max_leverage and total_margin > 0:
                total_leverage = total_gross / total_margin
                if total_leverage > limit.max_leverage:
                    violations.append(f"Order would exceed leverage limit: {total_leverage} > {limit.max_leverage}")
        
        return len(violations) == 0, violations
    
    def get_risk_state(self) -> PortfolioRiskState:
        """获取风险状态"""
        total_exposure = self.get_total_exposure()
        
        ok, violations = self.check_limits()
        
        total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        
        return PortfolioRiskState(
            timestamp=datetime.utcnow(),
            total_capital=self.total_capital,
            available_capital=self.available_capital,
            locked_capital=self.locked_capital,
            total_exposure=total_exposure.gross_value,
            net_exposure=total_exposure.net_value,
            gross_exposure=total_exposure.gross_value,
            portfolio_leverage=total_exposure.leverage,
            margin_used=total_exposure.margin_used,
            unrealized_pnl=total_unrealized,
            realized_pnl=self._realized_pnl,
            total_pnl=total_unrealized + self._realized_pnl,
            drawdown=self._max_drawdown,
            max_drawdown=self._max_drawdown,
            violations=violations if not ok else [],
        )
    
    def get_positions(self) -> Dict[str, PositionExposure]:
        """获取所有持仓"""
        return dict(self._positions)
    
    def get_position(
        self,
        symbol: str,
        exchange: str,
    ) -> Optional[PositionExposure]:
        """获取单个持仓"""
        position_key = f"{exchange}:{symbol}"
        return self._positions.get(position_key)
    
    def set_correlation(
        self,
        symbol1: str,
        symbol2: str,
        correlation: float,
    ) -> None:
        """设置相关性"""
        key = (symbol1, symbol2) if symbol1 < symbol2 else (symbol2, symbol1)
        self._correlations[key] = correlation
    
    def get_correlation_risk(self) -> float:
        """计算相关性风险"""
        if len(self._positions) < 2:
            return 0.0
        
        symbols = list(set(p.symbol for p in self._positions.values()))
        
        total_correlation_risk = 0.0
        count = 0
        
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i+1:]:
                key = (s1, s2) if s1 < s2 else (s2, s1)
                corr = self._correlations.get(key, 0.0)
                
                pos1 = next((p for p in self._positions.values() if p.symbol == s1), None)
                pos2 = next((p for p in self._positions.values() if p.symbol == s2), None)
                
                if pos1 and pos2:
                    weight1 = pos1.value / sum(p.value for p in self._positions.values())
                    weight2 = pos2.value / sum(p.value for p in self._positions.values())
                    
                    total_correlation_risk += abs(corr * weight1 * weight2)
                    count += 1
        
        return total_correlation_risk / count if count > 0 else 0.0


_exposure_manager: Optional[PortfolioExposureManager] = None


def get_exposure_manager(
    initial_capital: float = 100000.0,
) -> PortfolioExposureManager:
    """获取敞口管理器实例"""
    global _exposure_manager
    if _exposure_manager is None:
        _exposure_manager = PortfolioExposureManager(initial_capital)
    return _exposure_manager
