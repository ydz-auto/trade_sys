"""
Execution Service - 初始化和配置

业务逻辑：执行引擎和风控引擎的初始化
"""

import os
from typing import Optional

from infrastructure.logging import get_logger
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

logger = get_logger("execution_service.setup")


async def setup_execution_engine(
    use_orm: bool = False,
    db_manager: Optional[DatabaseSessionManager] = None,
) -> ExecutionEngine:
    """
    初始化执行引擎
    
    Args:
        use_orm: 是否使用 ORM 存储
        db_manager: 数据库管理器
        
    Returns:
        ExecutionEngine
    """
    engine = await init_execution_engine(
        use_orm=use_orm, 
        db_manager=db_manager, 
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
        logger.info(f"Using OKXAdapter (testnet={testnet}, market={market_type_str})")
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
        logger.info(f"Using BinanceAdapter (testnet={testnet}, market={market_type_str})")

    engine.register_adapter(adapter)
    await engine.connect_all()

    return engine


def setup_risk_engine() -> RiskEngine:
    """
    初始化风控引擎
    
    Returns:
        RiskEngine
    """
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
