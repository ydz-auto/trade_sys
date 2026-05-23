"""
PortfolioService - 投资组合服务

整合 Portfolio、ExposureManager、CapitalAllocator
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from domain.portfolio.portfolio import Portfolio, PortfolioState, PortfolioMetrics
from domain.portfolio.position import Position, PositionSide
from domain.portfolio.exposure_manager import ExposureManager, ExposureConfig
from domain.portfolio.capital_allocator import CapitalAllocator, CapitalAllocatorConfig, AllocationResult


class PortfolioService:
    """
    投资组合服务
    
    整合投资组合管理的所有功能
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        exposure_config: ExposureConfig = None,
        allocator_config: CapitalAllocatorConfig = None,
    ):
        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            current_capital=initial_capital,
            available_capital=initial_capital,
        )
        
        self.exposure_manager = ExposureManager(exposure_config)
        self.capital_allocator = CapitalAllocator(allocator_config)
        
        self._price_cache: Dict[str, float] = {}
    
    def update_price(self, symbol: str, price: float, exchange: str = "binance") -> None:
        """更新价格"""
        key = f"{exchange}:{symbol}"
        self._price_cache[key] = price
        self.portfolio.update_position_price(symbol, price, exchange)
    
    def get_price(self, symbol: str, exchange: str = "binance") -> float:
        """获取价格"""
        key = f"{exchange}:{symbol}"
        return self._price_cache.get(key, 0.0)
    
    def can_open_position(
        self,
        symbol: str,
        exchange: str,
        quantity: float,
        price: float,
        leverage: int = 1,
    ) -> tuple[bool, str]:
        """
        检查是否可以开仓
        
        Returns:
            (是否可以, 原因)
        """
        if self.portfolio.state != PortfolioState.ACTIVE:
            return False, "Portfolio not active"
        
        if not self.portfolio.can_open_position(symbol, quantity, price, leverage):
            return False, "Position limit exceeded"
        
        additional_value = abs(quantity) * price
        passed, reason = self.exposure_manager.check_exposure_limit(
            symbol=symbol,
            exchange=exchange,
            additional_value=additional_value,
            capital=self.portfolio.current_capital,
            is_long=quantity > 0,
        )
        
        if not passed:
            return False, reason
        
        return True, "OK"
    
    def open_position(
        self,
        symbol: str,
        exchange: str,
        quantity: float,
        price: float,
        leverage: int = 1,
        strategy_id: str = "",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> tuple[Optional[Position], str]:
        """
        开仓
        
        Returns:
            (Position, 原因)
        """
        can_open, reason = self.can_open_position(symbol, exchange, quantity, price, leverage)
        
        if not can_open:
            return None, reason
        
        position = self.portfolio.open_position(
            symbol=symbol,
            exchange=exchange,
            quantity=quantity,
            price=price,
            leverage=leverage,
            strategy_id=strategy_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        
        self.exposure_manager.update_exposure(
            symbol=symbol,
            exchange=exchange,
            long_quantity=quantity if quantity > 0 else 0,
            short_quantity=abs(quantity) if quantity < 0 else 0,
            price=price,
        )
        
        self._price_cache[f"{exchange}:{symbol}"] = price
        
        return position, "OK"
    
    def close_position(
        self,
        symbol: str,
        exchange: str,
        quantity: Optional[float] = None,
        price: float = 0.0,
    ) -> tuple[float, str]:
        """
        平仓
        
        Returns:
            (已实现盈亏, 原因)
        """
        position = self.portfolio.get_position(symbol, exchange)
        if not position:
            return 0.0, "No position found"
        
        if price <= 0:
            price = self.get_price(symbol, exchange)
        
        realized_pnl = self.portfolio.close_position(symbol, exchange, quantity, price)
        
        remaining = self.portfolio.get_position(symbol, exchange)
        if remaining:
            self.exposure_manager.update_exposure(
                symbol=symbol,
                exchange=exchange,
                long_quantity=remaining.quantity if remaining.quantity > 0 else 0,
                short_quantity=abs(remaining.quantity) if remaining.quantity < 0 else 0,
                price=price,
            )
        else:
            key = f"{exchange}:{symbol}"
            if key in self.exposure_manager.exposures:
                del self.exposure_manager.exposures[key]
        
        return realized_pnl, "OK"
    
    def allocate_for_trade(
        self,
        symbol: str,
        exchange: str,
        price: float,
        stop_loss_price: Optional[float] = None,
        confidence: float = 0.5,
        volatility: float = 0.02,
    ) -> AllocationResult:
        """
        为交易分配资金
        """
        return self.capital_allocator.allocate_for_trade(
            symbol=symbol,
            exchange=exchange,
            capital=self.portfolio.current_capital,
            price=price,
            stop_loss_price=stop_loss_price,
            confidence=confidence,
            volatility=volatility,
            used_margin=self.portfolio.total_margin,
        )
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """获取投资组合指标"""
        return self.portfolio.get_metrics()
    
    def get_exposure_summary(self) -> Dict[str, Any]:
        """获取敞口摘要"""
        return self.exposure_manager.to_dict()
    
    def get_exposure_warnings(self) -> List[Dict[str, Any]]:
        """获取敞口预警"""
        return self.exposure_manager.get_exposure_warnings(self.portfolio.current_capital)
    
    def get_risk_budget(self, daily_pnl: float = 0.0) -> Dict[str, float]:
        """获取风险预算"""
        return self.capital_allocator.calculate_risk_budget(
            capital=self.portfolio.current_capital,
            daily_pnl=daily_pnl,
        )
    
    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self.portfolio.positions.values())
    
    def get_positions_by_strategy(self, strategy_id: str) -> List[Position]:
        """按策略获取持仓"""
        return self.portfolio.get_positions_by_strategy(strategy_id)
    
    def get_total_pnl(self) -> float:
        """获取总盈亏"""
        return self.portfolio.total_pnl
    
    def get_total_value(self) -> float:
        """获取总价值"""
        return self.portfolio.total_value
    
    def pause(self) -> None:
        """暂停投资组合"""
        self.portfolio.state = PortfolioState.PAUSED
    
    def resume(self) -> None:
        """恢复投资组合"""
        self.portfolio.state = PortfolioState.ACTIVE
    
    def liquidate_all(self, prices: Dict[str, float]) -> Dict[str, float]:
        """
        清算所有持仓
        
        Returns:
            各品种已实现盈亏
        """
        results = {}
        
        for key, position in list(self.portfolio.positions.items()):
            if position.is_flat:
                continue
            
            price = prices.get(position.symbol, self.get_price(position.symbol, position.exchange))
            
            realized, _ = self.close_position(
                symbol=position.symbol,
                exchange=position.exchange,
                price=price,
            )
            
            results[position.symbol] = realized
        
        self.portfolio.state = PortfolioState.CLOSED
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "portfolio": self.portfolio.to_dict(),
            "exposure": self.exposure_manager.to_dict(),
            "allocator": self.capital_allocator.to_dict(),
            "metrics": self.get_portfolio_metrics().to_dict() if hasattr(self.get_portfolio_metrics(), 'to_dict') else {},
        }


_portfolio_service: Optional[PortfolioService] = None


def get_portfolio_service(
    initial_capital: float = 10000.0,
    reset: bool = False,
) -> PortfolioService:
    """获取全局投资组合服务"""
    global _portfolio_service
    
    if _portfolio_service is None or reset:
        _portfolio_service = PortfolioService(initial_capital=initial_capital)
    
    return _portfolio_service
