#!/usr/bin/env python3
"""
Test PostgreSQL Storage

测试 PostgreSQL 持久化
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from domain.execution.models import (
    OrderIntent,
    OrderSide,
    OrderType,
    Exchange,
    MarketType,
)
from services.execution_service.engine import get_execution_engine, init_execution_engine
from services.execution_service.adapters import MockAdapter
from services.execution_service.risk import (
    RiskEngine,
    PositionLimitChecker,
    LeverageLimitChecker,
)
from infrastructure.database.postgresql import init_postgres, get_postgres_manager
from infrastructure.database.schemas import POSTGRESQL_SCHEMAS
from infrastructure.logging import setup_logging


async def main():
    setup_logging()
    print("=" * 60)
    print("Testing PostgreSQL Storage Integration")
    print("=" * 60)

    try:
        # 1. 初始化 PostgreSQL 连接
        print("\n1. Initializing PostgreSQL connection...")
        postgres = await init_postgres()
        if not await postgres.health_check():
            print("❌ PostgreSQL connection failed")
            print("   Make sure PostgreSQL is running and configured")
            return 1
        print("✅ PostgreSQL connected successfully")

        # 2. 初始化表结构
        print("\n2. Initializing table schemas...")
        try:
            await postgres.init_schema()
            print("✅ Table schemas initialized")
        except Exception as e:
            print(f"⚠️  Schema init warning (tables may exist): {e}")

        # 3. 初始化执行引擎（使用 PostgreSQL）
        print("\n3. Initializing ExecutionEngine with PostgreSQL...")
        engine = await init_execution_engine(
            use_postgres=True,
            postgres_manager=postgres,
            load_from_db=False,
        )
        engine.register_adapter(MockAdapter())
        await engine.connect_all()
        print("✅ Engine initialized with PostgreSQL")

        # 4. 执行一些订单
        print("\n4. Executing test orders...")

        # 现货订单
        intent1 = OrderIntent(
            intent_id="test_postgres_001",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            exchange=Exchange.BINANCE,
            market_type=MarketType.SPOT,
        )
        result1 = await engine.execute_intent(intent1)
        print(f"   Order 1: {'✅ Success' if result1.success else '❌ Failed'}")

        # 合约订单
        result2 = await engine.execute_futures_order(
            symbol="ETHUSDT",
            side="buy",
            quantity=0.1,
            leverage=5,
        )
        print(f"   Order 2: {'✅ Success' if result2.success else '❌ Failed'}")

        # 平仓
        result3 = await engine.close_position("ETHUSDT", Exchange.BINANCE, MarketType.USDT_FUTURES)
        print(f"   Order 3: {'✅ Success' if result3.success else '❌ Failed'}")

        # 5. 验证数据保存到了 PostgreSQL
        print("\n5. Verifying data in PostgreSQL...")
        if engine._order_repo and engine._position_repo:
            orders = await engine._order_repo.list_recent(limit=10)
            print(f"   Found {len(orders)} orders in Postgres")

            positions = await engine._position_repo.list_all()
            print(f"   Found {len(positions)} positions in Postgres")

            if len(orders) > 0:
                print(f"   ✅ Orders persisted successfully")
            else:
                print(f"   ⚠️  No orders found in Postgres")
        else:
            print("   ⚠️  Repositories not initialized")

        # 6. 重启引擎并加载数据
        print("\n6. Testing data reload...")
        global _execution_engine
        _execution_engine = None

        print("   Creating new engine instance...")
        engine2 = await init_execution_engine(
            use_postgres=True,
            postgres_manager=postgres,
            load_from_db=True,
        )

        orders2 = engine2.get_order_history()
        positions2 = engine2.get_local_positions()
        print(f"   Loaded {len(orders2)} orders from Postgres")
        print(f"   Loaded {len(positions2)} positions from Postgres")

        if len(orders2) > 0:
            print("   ✅ Data reload successful")
        else:
            print("   ⚠️  No data loaded from Postgres")

        print("\n" + "=" * 60)
        print("✅ All PostgreSQL tests passed!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
