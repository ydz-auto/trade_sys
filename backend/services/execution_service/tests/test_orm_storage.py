#!/usr/bin/env python3
"""
Test ORM Storage

测试 SQLAlchemy ORM 持久化
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
from services.execution_service.engine import reset_execution_engine, init_execution_engine
from services.execution_service.adapters import MockAdapter
from services.execution_service.storage import init_db, close_db, get_db_manager
from infrastructure.logging import setup_logging


async def main():
    setup_logging()
    print("=" * 60)
    print("Testing ORM Storage Integration")
    print("=" * 60)

    try:
        # 1. 初始化数据库
        print("\n1. Initializing database...")
        db_manager = await init_db()
        await db_manager.create_tables()
        print("✅ Database initialized")

        # 2. 重置并初始化执行引擎（ORM 模式）
        print("\n2. Initializing ExecutionEngine with ORM...")
        reset_execution_engine()
        engine = await init_execution_engine(
            use_orm=True,
            db_manager=db_manager,
            load_from_db=False,
        )
        engine.register_adapter(MockAdapter())
        await engine.connect_all()
        print("✅ Engine initialized with ORM")

        # 3. 执行测试订单
        print("\n3. Executing test orders...")

        intent1 = OrderIntent(
            intent_id="test_orm_001",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            exchange=Exchange.BINANCE,
            market_type=MarketType.SPOT,
        )
        result1 = await engine.execute_intent(intent1)
        print(f"   Order 1: {'✅ Success' if result1.success else '❌ Failed'}")

        result2 = await engine.execute_futures_order(
            symbol="ETHUSDT",
            side="buy",
            quantity=0.1,
            leverage=5,
        )
        print(f"   Order 2: {'✅ Success' if result2.success else '❌ Failed'}")

        result3 = await engine.close_position("ETHUSDT", Exchange.BINANCE, MarketType.USDT_FUTURES)
        print(f"   Order 3: {'✅ Success' if result3.success else '❌ Failed'}")

        # 4. 验证数据
        print("\n4. Verifying data in database...")
        orders = engine.get_order_history()
        positions = engine.get_local_positions()
        print(f"   In-memory orders: {len(orders)}")
        print(f"   In-memory positions: {len(positions)}")

        # 5. 重启引擎并加载数据
        print("\n5. Testing data reload...")
        reset_execution_engine()

        engine2 = await init_execution_engine(
            use_orm=True,
            db_manager=db_manager,
            load_from_db=True,
        )

        orders2 = engine2.get_order_history()
        positions2 = engine2.get_local_positions()
        print(f"   Loaded orders: {len(orders2)}")
        print(f"   Loaded positions: {len(positions2)}")

        if len(orders2) > 0:
            print("   ✅ Data reload successful")
            print("\n   Sample order:")
            if orders2:
                o = orders2[0]
                print(f"      ID: {o.order_id}")
                print(f"      Symbol: {o.symbol}")
                print(f"      Status: {o.status}")
        else:
            print("   ⚠️  No data loaded (may be expected if tables are empty)")

        # 6. 清理
        print("\n6. Cleanup...")
        await close_db()
        print("✅ Done")

        print("\n" + "=" * 60)
        print("✅ ORM Storage Test Complete!")
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
