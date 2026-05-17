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
from services.execution_service.adapters.paper_trading_adapter import PaperTradingAdapter
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
from domain.execution.trading_mode import (
    TradingMode,
    TradingModeConfig,
    get_trading_mode_config,
    get_current_mode,
)

logger = get_logger("execution_service.setup")


async def setup_execution_engine(
    use_orm: bool = False,
    db_manager: Optional[DatabaseSessionManager] = None,
    force_mode: Optional[TradingMode] = None,
) -> ExecutionEngine:
    """
    初始化执行引擎（支持三种交易模式: demo/paper/prod
    
    Args:
        use_orm: 是否使用 ORM 存储
        db_manager: 数据库管理器
        force_mode: 强制使用的交易模式（如果为None则从环境变量读取
        
    Returns:
        ExecutionEngine
    """
    engine = await init_execution_engine(
        use_orm=use_orm, 
        db_manager=db_manager, 
        load_from_db=True,
    )

    # 获取交易模式配置
    config = get_trading_mode_config(force_mode)
    mode = config.mode
    
    logger.info(f"Setting up Execution Engine in {mode.value} mode")

    if mode == TradingMode.PAPER:
        # PAPER 模式：真实行情 + 本地撮合
        await _setup_paper_trading(engine, config)
    elif mode == TradingMode.DEMO:
        # DEMO 模式：测试网环境
        await _setup_demo_mode(engine, config)
    elif mode == TradingMode.PROD:
        # PROD 模式：真实交易
        await _setup_prod_mode(engine, config)
    else:
        # 默认回退到 Paper Trading
        logger.warning(f"Unknown mode {mode}, falling back to PAPER")
        await _setup_paper_trading(engine, config)

    await engine.connect_all()
    return engine


async def _setup_paper_trading(engine: ExecutionEngine, config: TradingModeConfig):
    """设置 Paper Trading 模式
    
    特点：
    - 真实市场数据
    - 本地撮合引擎
    - 支持多个交易所的 Paper Trading
    """
    logger.info("=" * 60)
    logger.info("Setting up PAPER TRADING MODE - Real Market Data + Local Matching")
    logger.info("=" * 60)
    
    paper_config = config.paper_config
    initial_balance = paper_config.get("initial_balance", {"USDT": 100000.0})
    slippage = paper_config.get("slippage", 0.001)
    fee_maker = paper_config.get("fee", {}).get("maker", 0.0002)
    fee_taker = paper_config.get("fee", {}).get("taker", 0.0004)
    
    # Binance Paper Trading
    binance_paper = PaperTradingAdapter(
        exchange=Exchange.BINANCE,
        initial_balance=initial_balance.copy(),
        slippage=slippage,
        fee_maker=fee_maker,
        fee_taker=fee_taker,
    )
    engine.register_adapter(binance_paper)
    logger.info("Registered Binance Paper Trading Adapter")
    
    # OKX Paper Trading
    okx_paper = PaperTradingAdapter(
        exchange=Exchange.OKX,
        initial_balance=initial_balance.copy(),
        slippage=slippage,
        fee_maker=fee_maker,
        fee_taker=fee_taker,
    )
    engine.register_adapter(okx_paper)
    logger.info("Registered OKX Paper Trading Adapter")


async def _setup_demo_mode(engine: ExecutionEngine, config: TradingModeConfig):
    """设置 Demo 模式
    
    特点：
    - Binance Testnet
    - OKX Demo Trading
    """
    logger.info("=" * 60)
    logger.info("Setting up DEMO MODE - Testnet Environment")
    logger.info("=" * 60)
    
    enabled_exchanges = os.getenv("ENABLED_EXCHANGES", "binance,okx").lower().split(",")
    enabled_exchanges = [ex.strip() for ex in enabled_exchanges if ex.strip()]
    market_type_str = os.getenv("EXECUTION_MARKET_TYPE", "usdt_futures").lower()
    
    market_type = MarketType.SPOT
    if market_type_str == "usdt_futures":
        market_type = MarketType.USDT_FUTURES
    elif market_type_str == "coin_futures":
        market_type = MarketType.COIN_FUTURES
    elif market_type_str == "swap":
        market_type = MarketType.SWAP
    
    # Binance Testnet
    if "binance" in enabled_exchanges:
        if os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_SECRET_KEY"):
            if market_type in [MarketType.USDT_FUTURES, MarketType.COIN_FUTURES]:
                binance_adapter = BinanceFuturesAdapter(
                    api_key=os.getenv("BINANCE_API_KEY"),
                    api_secret=os.getenv("BINANCE_SECRET_KEY"),
                    testnet=True,
                )
                engine.register_adapter(binance_adapter)
                logger.info("Registered Binance Futures Testnet Adapter")
            else:
                binance_adapter = BinanceAdapter(
                    api_key=os.getenv("BINANCE_API_KEY"),
                    api_secret=os.getenv("BINANCE_SECRET_KEY"),
                    testnet=True,
                    market_type=market_type,
                )
                engine.register_adapter(binance_adapter)
                logger.info("Registered Binance Testnet Adapter")
        else:
            logger.warning("Binance API keys not found, skipping Binance adapter")
    
    # OKX Demo
    if "okx" in enabled_exchanges:
        if os.getenv("OKX_API_KEY") and os.getenv("OKX_API_SECRET") and os.getenv("OKX_PASSPHRASE"):
            okx_adapter = OKXAdapter(
                api_key=os.getenv("OKX_API_KEY"),
                api_secret=os.getenv("OKX_API_SECRET"),
                passphrase=os.getenv("OKX_PASSPHRASE"),
                demo=True,
                market_type=market_type,
            )
            engine.register_adapter(okx_adapter)
            logger.info("Registered OKX Demo Trading Adapter")
        else:
            logger.warning("OKX API keys not found, skipping OKX adapter")
    
    # 如果没有真实适配器，回退到 mock
    if not engine._adapters:
        logger.warning("No exchange adapters registered, adding MockAdapter")
        adapter = MockAdapter()
        engine.register_adapter(adapter)


async def _setup_prod_mode(engine: ExecutionEngine, config: TradingModeConfig):
    """设置 Prod 模式
    
    特点：
    - 真实交易
    - 真实 API
    """
    logger.info("=" * 60)
    logger.info("Setting up PROD MODE - Live Trading!")
    logger.info("=" * 60)
    
    enabled_exchanges = os.getenv("ENABLED_EXCHANGES", "binance,okx").lower().split(",")
    enabled_exchanges = [ex.strip() for ex in enabled_exchanges if ex.strip()]
    market_type_str = os.getenv("EXECUTION_MARKET_TYPE", "usdt_futures").lower()
    
    market_type = MarketType.SPOT
    if market_type_str == "usdt_futures":
        market_type = MarketType.USDT_FUTURES
    elif market_type_str == "coin_futures":
        market_type = MarketType.COIN_FUTURES
    elif market_type_str == "swap":
        market_type = MarketType.SWAP
    
    # Binance Live
    if "binance" in enabled_exchanges:
        if os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_SECRET_KEY"):
            if market_type in [MarketType.USDT_FUTURES, MarketType.COIN_FUTURES]:
                binance_adapter = BinanceFuturesAdapter(
                    api_key=os.getenv("BINANCE_API_KEY"),
                    api_secret=os.getenv("BINANCE_SECRET_KEY"),
                    testnet=False,
                )
                engine.register_adapter(binance_adapter)
                logger.info("Registered Binance Futures Live Adapter")
            else:
                binance_adapter = BinanceAdapter(
                    api_key=os.getenv("BINANCE_API_KEY"),
                    api_secret=os.getenv("BINANCE_SECRET_KEY"),
                    testnet=False,
                    market_type=market_type,
                )
                engine.register_adapter(binance_adapter)
                logger.info("Registered Binance Live Adapter")
        else:
            logger.warning("Binance API keys not found, skipping Binance adapter")
    
    # OKX Live
    if "okx" in enabled_exchanges:
        if os.getenv("OKX_API_KEY") and os.getenv("OKX_API_SECRET") and os.getenv("OKX_PASSPHRASE"):
            okx_adapter = OKXAdapter(
                api_key=os.getenv("OKX_API_KEY"),
                api_secret=os.getenv("OKX_API_SECRET"),
                passphrase=os.getenv("OKX_PASSPHRASE"),
                demo=False,
                market_type=market_type,
            )
            engine.register_adapter(okx_adapter)
            logger.info("Registered OKX Live Trading Adapter")
        else:
            logger.warning("OKX API keys not found, skipping OKX adapter")
    
    # 如果没有真实适配器，回退到 mock
    if not engine._adapters:
        logger.warning("No exchange adapters registered, adding MockAdapter")
        adapter = MockAdapter()
        engine.register_adapter(adapter)


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
