"""
Portfolio Runtime - 组合运行时（实盘核心）

负责：
- 实时仓位管理
- 实时风险监控
- 实时净敞口计算
- 实时资金分配
- 策略冲突检测

这是实盘的核心，不能只停留在 domain 层。
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from uuid import UUID

from runtime.base import BaseRuntime, RuntimeConfig
from runtime.shared import RuntimeLifecycle, RuntimeMetrics, RuntimeHealthCheck
from infrastructure.logging import get_logger
from infrastructure.runtime_clock import now_ms

from domain.portfolio import Portfolio, Position
from domain.signal import Signal, SignalRegistry


logger = get_logger("portfolio_runtime")


def _utcnow() -> datetime:
    return datetime.utcfromtimestamp(now_ms() / 1000)


@dataclass
class PortfolioRuntimeConfig(RuntimeConfig):
    """Portfolio Runtime 配置"""
    name: str = "portfolio_runtime"
    
    # 风险参数
    max_total_exposure: float = 1.0  # 最大总敞口
    max_single_symbol_exposure: float = 0.3  # 单个交易对最大敞口
    max_leverage: float = 5.0  # 最大杠杆
    
    # 更新参数
    update_interval_seconds: float = 1.0  # 更新间隔
    risk_check_interval_seconds: float = 5.0  # 风险检查间隔


class PortfolioRuntime(BaseRuntime):
    """Portfolio Runtime - 组合运行时"""
    
    def __init__(self, config: Optional[PortfolioRuntimeConfig] = None):
        config = config or PortfolioRuntimeConfig()
        super().__init__(config)
        self.config: PortfolioRuntimeConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.portfolio: Optional[Portfolio] = None
        self.signal_registry: Optional[SignalRegistry] = None
        
        self.risk_alerts: List[Dict[str, Any]] = []
        self.last_updated: Optional[datetime] = None
        self._state: Dict[str, Any] = {"positions": [], "accounts": {}}
    
    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Portfolio Runtime...")
        
        self.lifecycle = RuntimeLifecycle("portfolio")
        self.metrics = RuntimeMetrics("portfolio")
        self.health_check = RuntimeHealthCheck("portfolio")
        
        self.signal_registry = SignalRegistry()
        
        logger.info("Portfolio Runtime initialized successfully")
    
    async def load_portfolio(self, portfolio: Portfolio) -> None:
        """加载组合"""
        self.portfolio = portfolio
        logger.info(f"Portfolio loaded: {portfolio.portfolio_id}")
    
    async def update_position(self, position: Position) -> None:
        """更新仓位"""
        if not self.portfolio:
            logger.warning("Portfolio not loaded")
            return
        
        self.portfolio.update_position(position)
        self.last_updated = _utcnow()
        self.metrics.increment("position_updates")
    
    async def close_position(self, symbol: str) -> None:
        """平仓"""
        if not self.portfolio:
            logger.warning("Portfolio not loaded")
            return
        
        self.portfolio.close_position(symbol)
        self.last_updated = _utcnow()
        self.metrics.increment("position_closes")
    
    async def calculate_exposure(self) -> Dict[str, float]:
        """计算敞口"""
        if not self.portfolio:
            return {}
        
        total_exposure = 0.0
        by_symbol: Dict[str, float] = {}
        net_exposure = 0.0
        
        for position in self.portfolio.positions.values():
            exposure = position.notional_value
            total_exposure += abs(exposure)
            by_symbol[position.symbol] = exposure
            
            if position.side == "long":
                net_exposure += exposure
            else:
                net_exposure -= exposure
        
        return {
            "total": total_exposure,
            "net": net_exposure,
            "by_symbol": by_symbol,
            "leverage": total_exposure / self.portfolio.equity if self.portfolio.equity > 0 else 0.0,
        }
    
    async def check_risk(self) -> Dict[str, Any]:
        """风险检查"""
        if not self.portfolio:
            return {"status": "no_portfolio"}
        
        exposure = await self.calculate_exposure()
        alerts = []
        
        if exposure["leverage"] > self.config.max_leverage:
            alert = {
                "type": "leverage_limit",
                "severity": "critical",
                "message": f"Leverage {exposure['leverage']:.2f} exceeds limit {self.config.max_leverage}",
                "timestamp": _utcnow().isoformat(),
            }
            alerts.append(alert)
            self.risk_alerts.append(alert)
            logger.critical(alert["message"])
        
        if exposure["total"] > self.config.max_total_exposure * self.portfolio.equity:
            alert = {
                "type": "total_exposure",
                "severity": "high",
                "message": f"Total exposure {exposure['total']:.2f} exceeds limit",
                "timestamp": _utcnow().isoformat(),
            }
            alerts.append(alert)
            self.risk_alerts.append(alert)
            logger.warning(alert["message"])
        
        for symbol, exp in exposure["by_symbol"].items():
            if exp > self.config.max_single_symbol_exposure * self.portfolio.equity:
                alert = {
                    "type": "single_exposure",
                    "severity": "high",
                    "symbol": symbol,
                    "message": f"Single symbol {symbol} exposure {exp:.2f} exceeds limit",
                    "timestamp": _utcnow().isoformat(),
                }
                alerts.append(alert)
                self.risk_alerts.append(alert)
                logger.warning(alert["message"])
        
        status = "ok" if not alerts else "alerts"
        
        return {
            "status": status,
            "exposure": exposure,
            "alerts": alerts,
            "portfolio_value": self.portfolio.equity,
            "timestamp": _utcnow().isoformat(),
        }
    
    async def allocate_capital(self, signals: List[Signal]) -> Dict[str, float]:
        """根据信号分配资金"""
        if not self.portfolio:
            return {}
        
        allocations: Dict[str, float] = {}
        
        active_signals = [s for s in signals if s.is_active()]
        
        if not active_signals:
            return allocations
        
        total_weight = sum(s.confidence.value * s.strength.magnitude for s in active_signals)
        
        if total_weight <= 0:
            return allocations
        
        available_capital = self.portfolio.equity * self.config.max_total_exposure
        
        for signal in active_signals:
            weight = (signal.confidence.value * signal.strength.magnitude) / total_weight
            allocation = available_capital * weight
            
            allocations[signal.symbol] = allocations.get(signal.symbol, 0.0) + allocation
        
        for symbol in allocations:
            max_alloc = self.portfolio.equity * self.config.max_single_symbol_exposure
            allocations[symbol] = min(allocations[symbol], max_alloc)
        
        self.metrics.increment("capital_allocations")
        
        return allocations
    
    async def detect_conflicts(self, signals: List[Signal]) -> List[Dict[str, Any]]:
        """检测策略冲突"""
        conflicts = []
        
        by_symbol: Dict[str, List[Signal]] = {}
        for signal in signals:
            if signal.symbol not in by_symbol:
                by_symbol[signal.symbol] = []
            by_symbol[signal.symbol].append(signal)
        
        for symbol, symbol_signals in by_symbol.items():
            longs = [s for s in symbol_signals if s.direction.value == "long" and s.is_active()]
            shorts = [s for s in symbol_signals if s.direction.value == "short" and s.is_active()]
            
            if longs and shorts:
                conflicts.append({
                    "type": "direction_conflict",
                    "symbol": symbol,
                    "long_signals": [str(s.signal_id) for s in longs],
                    "short_signals": [str(s.signal_id) for s in shorts],
                    "timestamp": _utcnow().isoformat(),
                })
        
        return conflicts
    
    def get_state(self) -> Dict[str, Any]:
        if self.portfolio:
            positions = []
            for pos in self.portfolio.positions.values():
                if hasattr(pos, 'to_dict'):
                    positions.append(pos.to_dict())
                elif isinstance(pos, dict):
                    positions.append(pos)
            accounts = {}
            if hasattr(self.portfolio, 'portfolio_id'):
                accounts[self.portfolio.portfolio_id] = {
                    "balance": getattr(self.portfolio, 'equity', 0),
                    "unrealized_pnl": 0.0,
                }
            self._state = {"positions": positions, "accounts": accounts}
        return self._state

    async def run(self) -> None:
        """主循环"""
        logger.info("Starting Portfolio Runtime main loop...")
        
        await self.lifecycle.transition_to_running()
        
        last_risk_check = _utcnow()
        
        while not self.context.is_shutdown_requested():
            try:
                now = _utcnow()
                
                if (now - last_risk_check).total_seconds() >= self.config.risk_check_interval_seconds:
                    await self.check_risk()
                    last_risk_check = now
                
                if self.signal_registry:
                    self.signal_registry.cleanup_expired()
                
                await asyncio.sleep(self.config.update_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in portfolio runtime loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)
    
    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Portfolio Runtime...")
        
        logger.info(f"Portfolio Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        base_health = await super().health_check()
        
        exposure = await self.calculate_exposure() if self.portfolio else {}
        
        base_health.update({
            "portfolio_loaded": self.portfolio is not None,
            "exposure": exposure,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "risk_alerts_count": len(self.risk_alerts),
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
        })
        
        return base_health


_portfolio_runtime: Optional[PortfolioRuntime] = None


def get_portfolio_runtime() -> PortfolioRuntime:
    """获取 Portfolio Runtime 单例"""
    global _portfolio_runtime
    if _portfolio_runtime is None:
        _portfolio_runtime = PortfolioRuntime()
    return _portfolio_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Portfolio Runtime - Real-time Portfolio Management")
    print("=" * 60)
    
    runtime = get_portfolio_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
