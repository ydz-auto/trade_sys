"""
Execution Worker - 风控 + 执行

合并 risk_service + execution_service

职责：
1. 消费决策，执行风控检查
2. 执行通过风控的订单
3. 管理持仓和订单状态
4. Portfolio 层管理

用法:
    python -m services.workers.execution_worker
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("workers.execution_worker")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import (
    DecisionEvent,
    RiskCheckedEvent,
    OrderEvent,
    FillEvent,
    EventType,
    EventSource,
    parse_event,
)
from infrastructure.database.session import DatabaseSessionManager, init_db

from services.execution_service.engine.execution_engine import (
    ExecutionEngine,
    get_execution_engine,
    init_execution_engine,
)
from services.execution_service.adapters.binance_adapter import BinanceAdapter
from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter
from services.execution_service.adapters.okx_adapter import OKXAdapter
from services.execution_service.adapters.mock_adapter import MockAdapter
from services.execution_service.consumers.signal_consumer import SignalConsumer
from services.execution_service.risk.risk_engine import RiskEngine
from services.execution_service.risk.position_limit import PositionLimitChecker
from services.execution_service.risk.leverage_limit import LeverageLimitChecker
from services.execution_service.risk.daily_loss_limit import DailyLossLimitChecker
from services.execution_service.risk.cooldown_checker import CooldownChecker
from services.execution_service.risk.drawdown_limit import DrawdownLimitChecker
from services.execution_service.risk.order_size_limit import OrderSizeLimitChecker
from services.execution_service.risk.symbol_blacklist import SymbolBlacklistChecker
from services.execution_service.risk.stop_loss_check import StopLossTPCheckChecker
from domain.execution.models import MarketType, Exchange

from services.risk_service.risk_engine import (
    RiskService,
    RiskCheckResult,
    RiskConfig,
    TradeRisk,
)

from domain.portfolio import (
    PortfolioService,
    get_portfolio_service,
    ExposureConfig,
    CapitalAllocatorConfig,
)


class ExecutionWorker:
    """
    执行 Worker
    
    合并 risk_service + execution_service + portfolio
    """
    
    def __init__(self):
        self.broker = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.risk_service: Optional[RiskService] = None
        self.signal_consumer: Optional[SignalConsumer] = None
        self.db_manager: Optional[DatabaseSessionManager] = None
        self.portfolio_service: Optional[PortfolioService] = None
        
        self._running = False
        self._stats = {
            "decisions_received": 0,
            "risk_passed": 0,
            "risk_rejected": 0,
            "orders_executed": 0,
            "orders_skipped": 0,
            "errors": 0,
        }
    
    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Execution Worker...")
        
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.broker = get_broker(bootstrap_servers)
        
        use_orm = os.getenv("EXECUTION_USE_ORM", "false").lower() == "true"
        logger.info(f"ORM Storage: {'Enabled' if use_orm else 'Disabled (memory only)'}")
        
        if use_orm:
            try:
                self.db_manager = await init_db()
                await self.db_manager.create_tables()
                logger.info("Database initialized")
            except Exception as e:
                logger.warning(f"DB init failed: {e}")
                use_orm = False
        
        self.execution_engine = await self._setup_execution_engine(use_orm)
        self.risk_engine = self._setup_risk_engine()
        self.risk_service = self._setup_risk_service()
        
        self.signal_consumer = SignalConsumer(
            execution_engine=self.execution_engine,
            risk_engine=self.risk_engine,
        )
        
        self.portfolio_service = self._setup_portfolio_service()
        
        self._running = True
        logger.info("Execution Worker initialized successfully")
    
    async def _setup_execution_engine(self, use_orm: bool) -> ExecutionEngine:
        """初始化执行引擎"""
        engine = await init_execution_engine(
            use_orm=use_orm,
            db_manager=self.db_manager,
            load_from_db=True,
        )

        use_mock = os.getenv("EXECUTION_MOCK", "true").lower() == "true"
        exchange_name = os.getenv("EXECUTION_EXCHANGE", "binance").lower()
        testnet = os.getenv("EXECUTION_TESTNET", "true").lower() == "true"
        market_type_str = os.getenv("EXECUTION_MARKET_TYPE", "spot").lower()

        market_type = MarketType.SPOT
        if market_type_str == "usdt_futures":
            market_type = MarketType.USDT_FUTURES
        elif market_type_str == "coin_futures":
            market_type = MarketType.COIN_FUTURES
        elif market_type_str == "swap":
            market_type = MarketType.SWAP

        if use_mock:
            adapter = MockAdapter()
            logger.info("Using MockAdapter for execution")
        elif exchange_name == "okx":
            adapter = OKXAdapter(
                api_key=os.getenv("OKX_API_KEY"),
                api_secret=os.getenv("OKX_API_SECRET"),
                passphrase=os.getenv("OKX_PASSPHRASE"),
                testnet=testnet,
                market_type=market_type,
            )
            logger.info(f"Using OKXAdapter (testnet={testnet})")
        elif market_type in [MarketType.USDT_FUTURES, MarketType.COIN_FUTURES]:
            adapter = BinanceFuturesAdapter(
                api_key=os.getenv("BINANCE_API_KEY"),
                api_secret=os.getenv("BINANCE_API_SECRET"),
                testnet=testnet,
            )
            logger.info(f"Using BinanceFuturesAdapter (testnet={testnet})")
        else:
            adapter = BinanceAdapter(
                api_key=os.getenv("BINANCE_API_KEY"),
                api_secret=os.getenv("BINANCE_API_SECRET"),
                testnet=testnet,
                market_type=market_type,
            )
            logger.info(f"Using BinanceAdapter (testnet={testnet})")

        engine.register_adapter(adapter)
        await engine.connect_all()

        return engine
    
    def _setup_risk_engine(self) -> RiskEngine:
        """初始化风控引擎（execution_service 内置）"""
        risk_engine = RiskEngine()

        risk_engine.register_checker(PositionLimitChecker(
            max_position_value=float(os.getenv("RISK_MAX_POSITION_VALUE", "10000")),
            max_position_count=int(os.getenv("RISK_MAX_POSITION_COUNT", "10")),
        ))

        risk_engine.register_checker(LeverageLimitChecker(
            max_leverage=int(os.getenv("RISK_MAX_LEVERAGE", "10")),
            warning_leverage=int(os.getenv("RISK_WARNING_LEVERAGE", "5")),
        ))

        risk_engine.register_checker(DailyLossLimitChecker(
            max_daily_loss_pct=float(os.getenv("RISK_MAX_DAILY_LOSS_PCT", "0.1")),
            initial_capital=float(os.getenv("RISK_INITIAL_CAPITAL", "10000")),
        ))

        risk_engine.register_checker(CooldownChecker(
            default_cooldown_seconds=int(os.getenv("RISK_DEFAULT_COOLDOWN", "300")),
        ))

        risk_engine.register_checker(DrawdownLimitChecker(
            max_drawdown_pct=float(os.getenv("RISK_MAX_DRAWDOWN_PCT", "0.2")),
            warning_drawdown_pct=float(os.getenv("RISK_WARNING_DRAWDOWN_PCT", "0.15")),
            initial_capital=float(os.getenv("RISK_INITIAL_CAPITAL", "10000")),
        ))

        risk_engine.register_checker(OrderSizeLimitChecker(
            max_order_value=float(os.getenv("RISK_MAX_ORDER_VALUE", "1000.0")),
            max_order_quantity=os.getenv("RISK_MAX_ORDER_QUANTITY"),
            min_order_value=float(os.getenv("RISK_MIN_ORDER_VALUE", "1.0")),
        ))

        blacklist = os.getenv("RISK_SYMBOL_BLACKLIST", "").split(",")
        if blacklist and blacklist[0]:
            risk_engine.register_checker(SymbolBlacklistChecker(
                blacklist=[s.strip() for s in blacklist],
            ))

        risk_engine.register_checker(StopLossTPCheckChecker(
            require_stop_loss=os.getenv("RISK_REQUIRE_SL", "true").lower() == "true",
        ))

        logger.info(f"Risk engine initialized with {len(risk_engine.checkers)} checkers")
        return risk_engine
    
    def _setup_risk_service(self) -> RiskService:
        """初始化风控服务（risk_service）"""
        risk_config = RiskConfig(
            max_position_size=0.2,
            max_single_loss=0.02,
            max_daily_loss=0.05,
            max_drawdown=0.15,
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
        )
        return RiskService(risk_config)
    
    def _setup_portfolio_service(self) -> PortfolioService:
        """初始化投资组合服务"""
        initial_capital = float(os.getenv("PORTFOLIO_INITIAL_CAPITAL", "10000"))
        
        exposure_config = ExposureConfig(
            max_single_exposure=float(os.getenv("PORTFOLIO_MAX_SINGLE_EXPOSURE", "0.2")),
            max_total_exposure=float(os.getenv("PORTFOLIO_MAX_TOTAL_EXPOSURE", "1.0")),
            max_long_exposure=float(os.getenv("PORTFOLIO_MAX_LONG_EXPOSURE", "0.8")),
            max_short_exposure=float(os.getenv("PORTFOLIO_MAX_SHORT_EXPOSURE", "0.8")),
        )
        
        allocator_config = CapitalAllocatorConfig(
            default_position_size=float(os.getenv("PORTFOLIO_DEFAULT_POSITION_SIZE", "0.1")),
            max_position_size=float(os.getenv("PORTFOLIO_MAX_POSITION_SIZE", "0.2")),
            risk_per_trade=float(os.getenv("PORTFOLIO_RISK_PER_TRADE", "0.02")),
        )
        
        portfolio_service = PortfolioService(
            initial_capital=initial_capital,
            exposure_config=exposure_config,
            allocator_config=allocator_config,
        )
        
        logger.info(f"Portfolio service initialized with capital={initial_capital}")
        return portfolio_service
    
    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Execution Worker...")
        self._running = False
        
        if self.broker:
            await self.broker.stop()
        
        logger.info(f"Execution Worker stopped. Stats: {self._stats}")
    
    def perform_risk_check(self, decision: DecisionEvent) -> RiskCheckedEvent:
        """执行风控检查"""
        if not self.risk_service:
            return RiskCheckedEvent(
                trace_id=decision.trace_id,
                parent_event_id=decision.event_id,
                source=EventSource.EXECUTION_WORKER,
                symbol=decision.symbol,
                exchange=decision.exchange,
                original_decision_id=decision.decision_id,
                approved=True,
                risk_level="medium",
                check_results={"status": "bypassed"},
            )
        
        estimated_value = decision.quantity * (decision.price or 1.0)
        trade_risk = TradeRisk(
            symbol=decision.symbol,
            side="buy" if decision.is_buy else "sell" if decision.is_sell else "hold",
            quantity=decision.quantity,
            price=decision.price or 0.0,
            estimated_value=estimated_value,
            estimated_loss=estimated_value * 0.02,
            risk_level="low",
            stop_loss=decision.price * 0.98 if decision.price else 0,
            take_profit=decision.price * 1.02 if decision.price else 0,
        )
        
        result = self.risk_service.check_trade(trade_risk)
        
        approved = result.check_result == RiskCheckResult.PASSED
        
        return RiskCheckedEvent(
            trace_id=decision.trace_id,
            parent_event_id=decision.event_id,
            source=EventSource.EXECUTION_WORKER,
            symbol=decision.symbol,
            exchange=decision.exchange,
            original_decision_id=decision.decision_id,
            approved=approved,
            risk_level=result.risk_level,
            rejection_reason=result.rejected_reason if not approved else None,
            warnings=result.warnings,
            check_results={
                "check_result": result.check_result.value,
                "metrics": result.metrics,
            },
        )
    
    def check_portfolio_limits(self, decision: DecisionEvent) -> tuple[bool, str]:
        """
        检查 Portfolio 层限制
        
        Returns:
            (是否通过, 原因)
        """
        if not self.portfolio_service:
            return True, "Portfolio service not initialized"
        
        price = decision.price or 50000.0
        
        can_open, reason = self.portfolio_service.can_open_position(
            symbol=decision.symbol,
            exchange=decision.exchange,
            quantity=decision.quantity if decision.is_buy else -decision.quantity,
            price=price,
            leverage=1,
        )
        
        return can_open, reason
    
    async def handle_decision(self, msg: dict) -> None:
        """
        处理决策：风控检查 -> Portfolio 检查 -> 执行
        """
        try:
            decision = DecisionEvent(**msg) if isinstance(msg, dict) else msg
            self._stats["decisions_received"] += 1
            
            trace_id = decision.trace_id
            logger.info(f"[{trace_id}] Received decision: {decision.action} on {decision.symbol}")
            
            checked_decision = self.perform_risk_check(decision)
            
            if checked_decision.approved:
                portfolio_ok, portfolio_reason = self.check_portfolio_limits(decision)
                if not portfolio_ok:
                    checked_decision.approved = False
                    checked_decision.risk_level = "high"
                    checked_decision.rejection_reason = f"Portfolio limit: {portfolio_reason}"
            
            print("\n" + "=" * 70)
            print("🛡️ EXECUTION WORKER - RISK CHECK")
            print("=" * 70)
            print(f"  Trace ID:   {trace_id}")
            print(f"  Decision:   {decision.action} {decision.symbol}")
            print(f"  Approved:   {'✅ YES' if checked_decision.approved else '❌ NO'}")
            print(f"  Risk:       {checked_decision.risk_level.upper()}")
            print(f"  Reason:     {checked_decision.rejection_reason or 'Passed'}")
            
            if self.portfolio_service:
                metrics = self.portfolio_service.get_portfolio_metrics()
                print(f"  Portfolio:  Value={metrics.total_value:.2f}, PnL={metrics.total_pnl:.2f}, Positions={metrics.position_count}")
            
            print("=" * 70)
            
            if not checked_decision.can_execute:
                self._stats["risk_rejected"] += 1
                print("\n⚠️  Decision rejected by risk checks. Skipping execution.\n")
                return
            
            self._stats["risk_passed"] += 1
            
            signal = {
                "symbol": decision.symbol,
                "action": decision.action,
                "quantity": decision.quantity,
                "price": decision.price,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "decision_id": decision.decision_id,
                "trace_id": trace_id,
            }
            
            result = await self.signal_consumer.process_signal(signal)
            
            status_icon = "✅" if result["status"] == "success" else "⚠️" if result["status"] == "skipped" else "❌"
            print(f"\n{status_icon} Execution Result: {result['status']}")
            
            if result.get("order_id"):
                self._stats["orders_executed"] += 1
                print(f"   Order ID: {result['order_id']}")
                
                if self.portfolio_service and decision.price:
                    self.portfolio_service.open_position(
                        symbol=decision.symbol,
                        exchange=decision.exchange,
                        quantity=decision.quantity if decision.is_buy else -decision.quantity,
                        price=decision.price,
                        strategy_id=decision.strategy_id,
                    )
            else:
                self._stats["orders_skipped"] += 1
            
            if result.get("reason"):
                print(f"   Reason: {result['reason']}")
            print("=" * 70 + "\n")
            
        except Exception as e:
            logger.error(f"Error handling decision: {e}")
            self._stats["errors"] += 1
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取投资组合摘要"""
        if not self.portfolio_service:
            return {}
        
        return {
            "metrics": self.portfolio_service.get_portfolio_metrics(),
            "exposure": self.portfolio_service.get_exposure_summary(),
            "positions": [p.to_dict() for p in self.portfolio_service.get_all_positions()],
        }
    
    async def run(self) -> None:
        """运行 Worker"""
        await self.initialize()
        
        try:
            logger.info(f"Subscribing to {Topics.DECISIONS}...")
            
            @self.broker.subscriber(Topics.DECISIONS)
            async def on_decision(msg: dict):
                await self.handle_decision(msg)
            
            await self.broker.run()
            
        except Exception as e:
            logger.warning(f"Kafka not available: {e}")
            logger.info("Running in standalone mode...")
            
            while self._running:
                await asyncio.sleep(5)
                await self.handle_decision({
                    "decision_id": f"test_{int(datetime.now().timestamp())}",
                    "action": "LONG",
                    "symbol": "BTCUSDT",
                    "quantity": 0.001,
                    "confidence": 0.8,
                })
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.shutdown()
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            **self._stats
        }


async def main():
    """主入口"""
    print("=" * 60)
    print("Execution Worker - Risk + Execution + Portfolio")
    print("=" * 60)
    print(f"Subscribe: {Topics.DECISIONS}")
    print("=" * 60)
    
    worker = ExecutionWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
