#!/usr/bin/env python3
"""
更新真实价格数据
"""
import asyncio
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.cache.redis_client import init_redis
from datetime import datetime


async def main():
    print("=" * 80)
    print("  更新真实价格数据")
    print("=" * 80)

    redis = await init_redis()

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    prices = {}

    for symbol in symbols:
        try:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
            price = float(r.json()["price"])
            prices[symbol.replace("USDT", "")] = price
            print(f"  ✓ {symbol}: ${price:,.2f}")
        except Exception as e:
            print(f"  ✗ {symbol}: 获取失败 - {e}")
            prices[symbol.replace("USDT", "")] = 0

    print("\n写入 Redis...")
    for symbol, price in prices.items():
        if price > 0:
            price_data = {
                "symbol": f"{symbol}/USDT",
                "price": price,
                "change24h": 0,
                "volume_24h": 1e9,
                "exchange": "binance",
                "timestamp": datetime.utcnow().isoformat()
            }
            await redis.set_json(f"price:{symbol}:binance", price_data)

    # 更新 Dashboard
    dashboard = await redis.get_json("projection:dashboard:state") or {}
    dashboard["prices"] = {
        f"{symbol}/USDT": {
            "symbol": f"{symbol}/USDT",
            "price": price,
            "change24h": 0,
            "volume_24h": 1e9,
            "exchange": "binance",
            "timestamp": datetime.utcnow().isoformat()
        }
        for symbol, price in prices.items() if price > 0
    }
    dashboard["last_update"] = datetime.utcnow().isoformat()
    await redis.set_json("projection:dashboard:state", dashboard)

    print("\n" + "=" * 80)
    print("  ✅ 价格已更新")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
