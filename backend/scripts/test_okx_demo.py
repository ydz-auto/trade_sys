#!/usr/bin/env python3
"""
OKX Demo Trading 连接测试脚本
验证 OKX API Key 配置和 Demo Trading 连接
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv

# Load .env from backend directory
backend_dir = Path(__file__).parent.parent
load_dotenv(backend_dir / ".env")

# Debug: Check environment variables
print(f"[Config] Loaded .env from: {backend_dir / '.env'}")
print(f"[Config] OKX_API_KEY: {os.environ.get('OKX_API_KEY', 'NOT SET')[:20]}...")

from services.execution_service.adapters.okx_adapter import OKXAdapter
from infrastructure.logging import get_logger

logger = get_logger("test_okx_demo")


async def test_okx_demo():
    """测试 OKX Demo Trading 连接"""
    
    # 在函数内部获取环境变量
    api_key = os.environ.get("OKX_API_KEY")
    api_secret = os.environ.get("OKX_API_SECRET")
    passphrase = os.environ.get("OKX_PASSPHRASE")
    
    print("=" * 60)
    print("OKX Demo Trading 连接测试")
    print("=" * 60)
    print(f"API Key:      {api_key[:15] if api_key else 'NOT FOUND'}")
    print(f"API Secret:   {api_secret[:15] if api_secret else 'NOT FOUND'}")
    print(f"Passphrase:   {passphrase[:15] if passphrase else 'NOT FOUND'}")
    print()
    
    if not all([api_key, api_secret, passphrase]):
        print("错误: 请在 .env 文件中配置完整的 OKX API Key")
        print("1. 访问 https://www.okx.com/account/my-api")
        print("2. 切换到 Demo Trading (模拟交易)")
        print("3. 创建 API Key，权限选 Read & Trade")
        print("4. 保存 API Key, Secret Key, Passphrase")
        return False
    
    print("尝试连接 OKX Demo Trading...")
    
    adapter = OKXAdapter(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        demo=True
    )
    
    try:
        connected = await adapter.connect()
        if not connected:
            print("连接失败")
            return False
        
        print("连接成功！")
        print()
        
        # 获取账户余额
        print("获取账户余额...")
        balance = await adapter.get_balance()
        print(f"余额: {balance}")
        print()
        
        # 获取 BTC/USDT 价格
        print("获取 BTC/USDT 价格...")
        price = await adapter.get_market_price("BTCUSDT")
        print(f"价格: {price}")
        print()
        
        # 获取持仓
        print("获取持仓...")
        positions = await adapter.get_positions()
        print(f"当前持仓数: {len(positions)}")
        for pos in positions:
            print(f"  - {pos.symbol}: {pos.quantity} @ {pos.average_price}")
        print()
        
        print("测试完成！OKX Demo Trading 配置正确")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(test_okx_demo())
