#!/usr/bin/env python3
"""
统一交易所连接测试脚本
同时测试 Binance 和 OKX 的连接
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict

# Add project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# 必须在导入 adapter 之前加载环境变量
from dotenv import load_dotenv
load_dotenv(root_dir / ".env")

from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter
from services.execution_service.adapters.okx_adapter import OKXAdapter
from infrastructure.logging import get_logger

logger = get_logger("test_exchanges")


async def test_binance() -> Dict:
    """测试 Binance 连接"""
    print("\n" + "=" * 60)
    print("测试 Binance Testnet")
    print("=" * 60)
    
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Binance API Key 或 Secret 未配置")
        return {
            "exchange": "Binance",
            "status": "skipped",
            "reason": "API Key 或 Secret 未配置"
        }
    
    print(f"API Key: {api_key[:15]}...")
    
    adapter = None
    result = {
        "exchange": "Binance",
        "status": "failed",
        "error": None,
        "balance": None,
        "price": None,
        "positions": 0
    }
    
    try:
        adapter = BinanceFuturesAdapter(api_key=api_key, api_secret=api_secret, testnet=True, timeout=30)
        
        print("\n尝试连接...")
        connected = await adapter.connect()
        if not connected:
            result["reason"] = "连接失败"
            print("❌ 连接失败")
            return result
        
        print("✅ 连接成功")
        
        print("\n获取 BTC/USDT 价格...")
        try:
            price = await adapter.get_market_price("BTCUSDT")
            if price:
                result["price"] = price
                print(f"✅ BTC/USDT 价格: {price}")
            else:
                print("⚠️ 价格获取失败")
        except Exception as e:
            print(f"⚠️ 获取价格失败: {e}")
        
        print("\n获取账户余额...")
        try:
            balance = await adapter.get_balance()
            result["balance"] = balance
            if balance:
                print(f"✅ 余额: {len(balance)} 个资产")
                for asset, amount in balance.items():
                    print(f"   - {asset}: {amount}")
            else:
                print("⚠️ 无余额数据")
        except Exception as e:
            print(f"⚠️ 获取余额失败: {e}")
        
        print("\n获取持仓...")
        try:
            positions = await adapter.get_positions()
            result["positions"] = len(positions)
            print(f"✅ 当前持仓: {len(positions)} 个")
            for pos in positions:
                print(f"   - {pos.symbol}: {pos.quantity} @ {pos.avg_entry_price}")
        except Exception as e:
            print(f"⚠️ 获取持仓失败: {e}")
        
        result["status"] = "success"
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    finally:
        if adapter:
            try:
                await adapter.disconnect()
                print("\n✅ 已断开连接")
            except:
                pass
    
    return result


async def test_okx() -> Dict:
    """测试 OKX 连接"""
    print("\n" + "=" * 60)
    print("测试 OKX Demo Trading")
    print("=" * 60)
    
    api_key = os.environ.get("OKX_API_KEY")
    api_secret = os.environ.get("OKX_API_SECRET")
    passphrase = os.environ.get("OKX_PASSPHRASE")
    
    if not api_key or not api_secret or not passphrase:
        print("❌ OKX API Key、Secret 或 Passphrase 未配置")
        return {
            "exchange": "OKX",
            "status": "skipped",
            "reason": "API Key、Secret 或 Passphrase 未配置"
        }
    
    print(f"API Key: {api_key[:15]}...")
    
    adapter = None
    result = {
        "exchange": "OKX",
        "status": "failed",
        "error": None,
        "balance": None,
        "price": None,
        "positions": 0
    }
    
    try:
        adapter = OKXAdapter(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            demo=True,
            timeout=30
        )
        
        print("\n尝试连接...")
        connected = await adapter.connect()
        if not connected:
            result["reason"] = "连接失败"
            print("❌ 连接失败")
            return result
        
        print("✅ 连接成功")
        
        print("\n获取 BTC/USDT 价格...")
        try:
            price = await adapter.get_market_price("BTCUSDT")
            if price:
                result["price"] = price
                print(f"✅ BTC/USDT 价格: {price}")
            else:
                print("⚠️ 价格获取失败")
        except Exception as e:
            print(f"⚠️ 获取价格失败: {e}")
        
        print("\n获取账户余额...")
        try:
            balance = await adapter.get_balance()
            result["balance"] = balance
            if balance:
                print(f"✅ 余额: {len(balance)} 个资产")
                for asset, amount in balance.items():
                    print(f"   - {asset}: {amount}")
            else:
                print("⚠️ 无余额数据")
        except Exception as e:
            print(f"⚠️ 获取余额失败: {e}")
        
        print("\n获取持仓...")
        try:
            positions = await adapter.get_positions()
            result["positions"] = len(positions)
            print(f"✅ 当前持仓: {len(positions)} 个")
            for pos in positions:
                print(f"   - {pos.symbol}: {pos.quantity} @ {pos.avg_entry_price}")
        except Exception as e:
            print(f"⚠️ 获取持仓失败: {e}")
        
        result["status"] = "success"
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    finally:
        if adapter:
            try:
                await adapter.disconnect()
                print("\n✅ 已断开连接")
            except:
                pass
    
    return result


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("交易所连接测试")
    print("=" * 60)
    print(f"配置文件: {root_dir / '.env'}")
    
    # 同时测试两个交易所
    binance_result = await test_binance()
    okx_result = await test_okx()
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for result in [binance_result, okx_result]:
        status_icon = "✅" if result["status"] == "success" else "❌" if result["status"] == "failed" else "⏭️"
        print(f"\n{status_icon} {result['exchange']}")
        print(f"   状态: {result['status']}")
        if result.get("error"):
            print(f"   错误: {result['error']}")
        if result.get("reason"):
            print(f"   原因: {result['reason']}")
        if result.get("price"):
            print(f"   BTC/USDT: {result['price']}")
        if result.get("balance"):
            print(f"   余额资产: {len(result['balance'])}")
        print(f"   持仓: {result.get('positions', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
