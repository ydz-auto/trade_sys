#!/usr/bin/env python3
"""
测试双交易所支持 - Binance + OKX
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from dotenv import load_dotenv
import os

# 先加载环境变量
load_dotenv(override=True)

from infrastructure.logging import get_logger
from services.execution_service.setup import setup_execution_engine
from domain.execution.models import Exchange, MarketType, OrderSide, OrderType
from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter
from services.execution_service.adapters.okx_adapter import OKXAdapter

logger = get_logger("test_dual_exchanges")


async def test_binance_connection():
    """测试 Binance 连接"""
    logger.info("=" * 60)
    logger.info("Testing Binance Connection")
    logger.info("=" * 60)
    
    try:
        adapter = BinanceFuturesAdapter(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET_KEY"),
            testnet=True,
        )
        
        connected = await adapter.connect()
        logger.info(f"Binance connected: {connected}")
        
        if connected:
            # 获取余额
            balance = await adapter.get_balance()
            logger.info(f"Binance balance: {balance}")
            
            # 获取价格
            price = await adapter.get_market_price("BTCUSDT")
            logger.info(f"Binance BTCUSDT price: {price}")
            
            # 获取持仓
            positions = await adapter.get_positions()
            logger.info(f"Binance positions: {positions}")
        
        await adapter.disconnect()
        return connected
    except Exception as e:
        logger.error(f"Binance test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_okx_connection():
    """测试 OKX 连接"""
    logger.info("=" * 60)
    logger.info("Testing OKX Connection")
    logger.info("=" * 60)
    
    try:
        adapter = OKXAdapter(
            api_key=os.getenv("OKX_API_KEY"),
            api_secret=os.getenv("OKX_API_SECRET"),
            passphrase=os.getenv("OKX_PASSPHRASE"),
            demo=True,  # OKX 使用 demo 参数
            market_type=MarketType.USDT_FUTURES,
        )
        
        connected = await adapter.connect()
        logger.info(f"OKX connected: {connected}")
        
        if connected:
            # 获取余额
            balance = await adapter.get_balance()
            logger.info(f"OKX balance: {balance}")
            
            # 获取价格
            price = await adapter.get_market_price("BTCUSDT")
            logger.info(f"OKX BTC-USDT price: {price}")
            
            # 获取持仓
            positions = await adapter.get_positions()
            logger.info(f"OKX positions: {positions}")
        
        await adapter.disconnect()
        return connected
    except Exception as e:
        logger.error(f"OKX test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_dual_exchange_engine():
    """测试双交易所引擎"""
    logger.info("=" * 60)
    logger.info("Testing Dual Exchange Execution Engine")
    logger.info("=" * 60)
    
    try:
        engine = await setup_execution_engine(use_orm=False)
        
        # 检查注册的适配器
        logger.info(f"Registered adapters: {list(engine._adapters.keys())}")
        
        # 验证有两个适配器
        if len(engine._adapters) >= 2:
            logger.info("✓ Both exchanges registered successfully")
        else:
            logger.warning(f"Only {len(engine._adapters)} exchanges registered")
        
        # 测试获取适配器
        binance_adapter = engine.get_adapter(Exchange.BINANCE)
        okx_adapter = engine.get_adapter(Exchange.OKX)
        
        if binance_adapter:
            logger.info("✓ Binance adapter available")
        if okx_adapter:
            logger.info("✓ OKX adapter available")
        
        await engine.disconnect_all()
        return True
    except Exception as e:
        logger.error(f"Dual exchange engine test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("Dual Exchange Support Test - Binance + OKX")
    print("=" * 60 + "\n")
    
    # 测试 Binance
    binance_ok = await test_binance_connection()
    
    # 测试 OKX
    okx_ok = await test_okx_connection()
    
    # 测试双交易所引擎
    engine_ok = await test_dual_exchange_engine()
    
    # 总结
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Binance: {'✓ Success' if binance_ok else '✗ Failed'}")
    print(f"  OKX:     {'✓ Success' if okx_ok else '✗ Failed'} (Note: May fail due to network issues)")
    print(f"  Engine:  {'✓ Success' if engine_ok else '✗ Failed'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
