#!/usr/bin/env python3
"""
Binance 测试网连接验证脚本
验证 Binance API Key 配置和 Testnet 连接
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv

# Load .env from backend directory (parent of scripts/)
backend_dir = Path(__file__).parent.parent
load_dotenv(backend_dir / ".env")

# Debug: Check environment variables
import os
print(f"[Config] Loaded .env from: {backend_dir / '.env'}")
print(f"[Config] BINANCE_API_KEY: {os.getenv('BINANCE_API_KEY', 'NOT SET')[:20]}...")
print(f"[Config] BINANCE_SECRET_KEY: {os.getenv('BINANCE_SECRET_KEY', 'NOT SET')[:20]}...")

from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter
from infrastructure.logging import get_logger

logger = get_logger("test_binance_connection")


async def test_binance_connection():
    """测试 Binance 测试网连接"""
    
    # 在函数内部获取环境变量
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_SECRET_KEY")
    
    print("=" * 60)
    print("Binance Testnet 连接测试")
    print("=" * 60)
    print(f"API Key:      {api_key[:15] if api_key else 'NOT FOUND'}")
    print(f"API Secret:   {api_secret[:15] if api_secret else 'NOT FOUND'}")
    print()
    
    if not all([api_key, api_secret]):
        print("错误: 请在 .env 文件中配置完整的 Binance API Key")
        return False
    
    print("尝试连接 Binance Testnet...")
    
    adapter = BinanceFuturesAdapter(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True
    )
    
    try:
        # Connect to exchange
        connected = await adapter.connect()
        if not connected:
            print("连接失败")
            return False
        
        print("连接成功！")
        print()
        
        # Get account balance
        print("获取账户余额...")
        balance = await adapter.get_balance()
        print(f"余额: {balance}")
        print()
        
        # Get current price
        print("获取 BTC/USDT 价格...")
        price = await adapter.get_market_price("BTCUSDT")
        print(f"BTC/USDT 价格: {price}")
        print()
        
        # Get positions
        print("获取持仓...")
        positions = await adapter.get_positions()
        print(f"当前持仓数量: {len(positions)}")
        for pos in positions:
            print(f"   - {pos.symbol}: {pos.quantity} @ {pos.average_price}")
        print()
        
        # Disconnect
        await adapter.disconnect()
        print("测试完成！Binance Testnet 配置正确")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_binance_connection())
