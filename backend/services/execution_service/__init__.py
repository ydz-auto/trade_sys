"""
Execution Service

订单执行服务

架构：
    Signal → SignalConsumer → RiskEngine → ExecutionEngine → ExchangeAdapter → Order

模块：
    - adapters: 交易所适配器
    - engine: 执行引擎（订单管理、持仓管理）
    - storage: 存储层（订单、持仓持久化）
    - risk: 风控引擎
    - consumers: 消息消费者
    - publishers: 事件发布者
"""

from services.execution_service.engine.execution_engine import (
    ExecutionEngine,
    get_execution_engine,
    init_execution_engine,
)
from services.execution_service.engine.order_manager import OrderManager
from services.execution_service.engine.position_manager import PositionManager
from services.execution_service.adapters.base import BaseExchangeAdapter
from services.execution_service.adapters.binance_adapter import BinanceAdapter
from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter
from services.execution_service.adapters.mock_adapter import MockAdapter
from services.execution_service.storage.order_repository import OrderRepository
from services.execution_service.storage.position_repository import PositionRepository
from services.execution_service.risk.risk_engine import RiskEngine, RiskCheckResult
from services.execution_service.risk.position_limit import PositionLimitChecker
from services.execution_service.risk.leverage_limit import LeverageLimitChecker
from services.execution_service.risk.daily_loss_limit import DailyLossLimitChecker
from services.execution_service.risk.cooldown_checker import CooldownChecker
from services.execution_service.consumers.signal_consumer import SignalConsumer
from services.execution_service.publishers.order_publisher import OrderPublisher
from services.execution_service.fill_sync import FillSyncManager

__all__ = [
    "ExecutionEngine",
    "get_execution_engine",
    "init_execution_engine",
    "OrderManager",
    "PositionManager",
    "BaseExchangeAdapter",
    "BinanceAdapter",
    "BinanceFuturesAdapter",
    "MockAdapter",
    "OrderRepository",
    "PositionRepository",
    "RiskEngine",
    "RiskCheckResult",
    "PositionLimitChecker",
    "LeverageLimitChecker",
    "DailyLossLimitChecker",
    "CooldownChecker",
    "SignalConsumer",
    "OrderPublisher",
    "FillSyncManager",
]
