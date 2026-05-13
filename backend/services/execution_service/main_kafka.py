"""
Execution Service - Kafka Consumer

消费风控后的决策，执行订单
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import RiskCheckedDecision
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

logger = get_logger("execution_service.kafka")


async def setup_engine(use_orm=False, db_manager=None) -> ExecutionEngine:
    """初始化执行引擎"""
    engine = await init_execution_engine(
        use_orm=use_orm, db_manager=db_manager, load_from_db=True,
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
    """初始化风控引擎"""
    risk_engine = RiskEngine()

    # 1. 持仓限制
    risk_engine.register_checker(PositionLimitChecker(
        max_position_value=float(os.getenv("RISK_MAX_POSITION_VALUE", "10000")),
        max_position_count=int(os.getenv("RISK_MAX_POSITION_COUNT", "10")),
    ))

    # 2. 杠杆限制
    risk_engine.register_checker(LeverageLimitChecker(
        max_leverage=int(os.getenv("RISK_MAX_LEVERAGE", "10")),
        warning_leverage=int(os.getenv("RISK_WARNING_LEVERAGE", "5")),
    ))

    # 3. 每日亏损
    risk_engine.register_checker(DailyLossLimitChecker(
        max_daily_loss_pct=float(os.getenv("RISK_MAX_DAILY_LOSS_PCT", "0.1")),
        initial_capital=float(os.getenv("RISK_INITIAL_CAPITAL", "10000")),
    ))

    # 4. 冷却时间
    risk_engine.register_checker(CooldownChecker(
        default_cooldown_seconds=int(os.getenv("RISK_DEFAULT_COOLDOWN", "300")),
    ))

    # 5. 最大回撤 (NEW
    risk_engine.register_checker(DrawdownLimitChecker(
        max_drawdown_pct=float(os.getenv("RISK_MAX_DRAWDOWN_PCT", "0.2")),
        warning_drawdown_pct=float(os.getenv("RISK_WARNING_DRAWDOWN_PCT", "0.15")),
        initial_capital=float(os.getenv("RISK_INITIAL_CAPITAL", "10000")),
    ))

    # 6. 订单大小限制 (NEW
    risk_engine.register_checker(OrderSizeLimitChecker(
        max_order_value=float(os.getenv("RISK_MAX_ORDER_VALUE", "1000.0")),
        max_order_quantity=os.getenv("RISK_MAX_ORDER_QUANTITY"),
        min_order_value=float(os.getenv("RISK_MIN_ORDER_VALUE", "1.0")),
    ))

    # 7. 交易对黑名单 (NEW
    blacklist = os.getenv("RISK_SYMBOL_BLACKLIST", "").split(",")
    if blacklist and blacklist[0]:
        risk_engine.register_checker(SymbolBlacklistChecker(
            blacklist=[s.strip() for s in blacklist],
        ))

    # 8. 止损/止盈检查 (NEW
    risk_engine.register_checker(StopLossTPCheckChecker(
        require_stop_loss=os.getenv("RISK_REQUIRE_SL", "true").lower() == "true",
    ))

    logger.info(f"Risk engine initialized with {len(risk_engine.checkers)} checkers")
    return risk_engine


broker = None
signal_consumer: SignalConsumer = None


async def handle_risk_checked_decision(msg: dict):
    """处理风控后的决策"""
    global signal_consumer

    try:
        checked_decision = RiskCheckedDecision(**msg) if isinstance(msg, dict) else msg
        original_decision = checked_decision.original_decision

        print("\n" + "=" * 60)
        print("🛡️ RECEIVED RISK CHECKED DECISION")
        print("=" * 60)
        print(f"   Decision ID: {checked_decision.decision_id}")
        print(f"   Approved:    {'✅ YES' if checked_decision.approved else '❌ NO'}")
        print(f"   Risk Level:  {checked_decision.risk_level}")
        print(f"   Symbol:      {original_decision.symbol}")
        print(f"   Action:      {original_decision.action}")
        print(f"   Quantity:    {original_decision.quantity:.4f}")
        print(f"   Confidence:  {original_decision.confidence:.3f}")
        print(f"   Reason:      {checked_decision.reason or 'No reason'}")
        print("=" * 60)

        if not checked_decision.can_execute:
            print("\n⚠️  Decision rejected by risk checks. Skipping execution.")
            print("=" * 60 + "\n")
            return

        # 转换为信号格式供 signal_consumer 使用
        signal = {
            "symbol": original_decision.symbol,
            "action": original_decision.action,
            "quantity": original_decision.quantity,
            "price": original_decision.price,
            "confidence": original_decision.confidence,
            "reason": original_decision.reason,
            "decision_id": checked_decision.decision_id,
        }

        result = await signal_consumer.process_signal(signal)

        status_icon = "✅" if result["status"] == "success" else "⚠️" if result["status"] == "skipped" else "❌"
        print(f"\n{status_icon} Result: {result['status']}")

        if result.get("order_id"):
            print(f"   Order ID: {result['order_id']}")
        if result.get("reason"):
            print(f"   Reason: {result['reason']}")
        if result.get("warnings"):
            print(f"   Warnings: {result['warnings']}")
        print("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Error handling risk checked decision: {e}", exc_info=True)


async def handle_signal(msg: dict):
    """处理信号（向后兼容）"""
    global signal_consumer

    try:
        signal = msg
        symbol = signal.get("symbol")
        if not symbol:
            assets = signal.get("assets", ["BTC"])
            symbol = assets[0] if assets else "BTC/USDT"
        if "/" not in symbol and "USDT" in symbol and len(symbol) > 4:
            symbol = f"{symbol.replace('USDT', '/USDT')}"

        action = signal.get("action", signal.get("signal", "HOLD"))
        confidence = signal.get("confidence", 0.5)

        print("\n" + "=" * 60)
        print("📊 RECEIVED SIGNAL (LEGACY)")
        print("=" * 60)
        print(f"   Symbol:   {symbol}")
        print(f"   Action:   {action}")
        print(f"   Confidence: {confidence:.3f}")
        print("=" * 60)

        result = await signal_consumer.process_signal(signal)

        status_icon = "✅" if result["status"] == "success" else "⚠️" if result["status"] == "skipped" else "❌"
        print(f"\n{status_icon} Result: {result['status']}")

        if result.get("order_id"):
            print(f"   Order ID: {result['order_id']}")
        if result.get("reason"):
            print(f"   Reason: {result['reason']}")
        if result.get("warnings"):
            print(f"   Warnings: {result['warnings']}")
        print("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Error handling signal: {e}", exc_info=True)


async def main():
    global broker, signal_consumer

    print("=" * 60)
    print("Execution Service - Kafka Consumer")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.decisions_risk_checked()}, {Topics.decisions_approved()}")
    print(f"Legacy Subscribe: {Topics.SIGNALS} (for backward compatibility)")

    # 检查是否启用 ORM
    use_orm = os.getenv("EXECUTION_USE_ORM", "false").lower() == "true"
    print(f"ORM Storage: {'✅ Enabled' if use_orm else '❌ Disabled (memory only)'}")
    print("=" * 60)

    # 初始化数据库（如果启用 ORM）
    db_manager = None
    if use_orm:
        try:
            db_manager = await init_db()
            await db_manager.create_tables()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️ DB init failed: {e}")
            use_orm = False

    # 初始化引擎
    engine = await setup_engine(use_orm=use_orm, db_manager=db_manager)
    risk_engine = setup_risk_engine()

    signal_consumer = SignalConsumer(
        execution_engine=engine,
        risk_engine=risk_engine,
    )

    try:
        broker = get_broker(bootstrap_servers)

        print("\n[execution_service] Waiting for risk checked decisions...\n")

        @broker.subscriber(Topics.decisions_risk_checked())
        async def on_risk_checked_decision(msg: dict):
            await handle_risk_checked_decision(msg)

        @broker.subscriber(Topics.decisions_approved())
        async def on_approved_decision(msg: dict):
            await handle_risk_checked_decision(msg)

        @broker.subscriber(Topics.SIGNALS)
        async def on_signal(msg: dict):
            await handle_signal(msg)

        await broker.run()

    except Exception as e:
        print(f"\n[execution_service] Kafka not available: {e}")
        print("[execution_service] Running in standalone mode...\n")

        # 独立模式测试
        while True:
            await asyncio.sleep(5)
            await handle_signal({
                "action": "LONG",
                "symbol": "BTC/USDT",
                "confidence": 0.8,
            })


if __name__ == "__main__":
    asyncio.run(main())
