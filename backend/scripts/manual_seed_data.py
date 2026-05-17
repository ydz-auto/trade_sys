#!/usr/bin/env python3
"""
手动种子数据脚本 - 往 Redis 写入测试数据
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.cache.redis_client import get_redis_client, init_redis


async def seed_data():
    """往 Redis 写入测试数据"""
    print("=" * 80)
    print("  开始初始化 Redis 测试数据")
    print("=" * 80)

    # 初始化 Redis
    print("[1/5] 初始化 Redis 连接...")
    redis = await init_redis()
    print("  ✓ Redis 连接成功")

    # 1. 写入价格数据
    print("\n[2/5] 写入价格数据...")
    prices = {
        "BTC/USDT": {
            "symbol": "BTC/USDT",
            "price": 81234.56,
            "change24h": 0.023,
            "volume_24h": 1234567890.12,
            "exchange": "binance",
            "timestamp": datetime.utcnow().isoformat()
        },
        "ETH/USDT": {
            "symbol": "ETH/USDT",
            "price": 2345.67,
            "change24h": -0.012,
            "volume_24h": 987654321.09,
            "exchange": "binance",
            "timestamp": datetime.utcnow().isoformat()
        },
        "SOL/USDT": {
            "symbol": "SOL/USDT",
            "price": 95.67,
            "change24h": 0.056,
            "volume_24h": 456789123.45,
            "exchange": "binance",
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    # 写入独立的价格 key
    for symbol, data in prices.items():
        key = f"price:{symbol.split('/')[0]}:binance"
        await redis.set_json(key, data)
        print(f"  ✓ {key}")

    # 2. 写入 Dashboard 状态
    print("\n[3/5] 写入 Dashboard 状态...")
    dashboard_state = {
        "prices": prices,
        "compositeScore": 0.68,
        "regime": {
            "BTC": {
                "state": "trending_up",
                "confidence": 0.72,
                "trendStrength": 0.68
            }
        },
        "factors": {
            "trend": {"type": "trend", "name": "趋势因子", "weight": 0.25, "value": 0.72, "confidence": 82, "color": "green"},
            "momentum": {"type": "momentum", "name": "动量因子", "weight": 0.25, "value": 0.65, "confidence": 78, "color": "blue"},
            "volatility": {"type": "volatility", "name": "波动率因子", "weight": 0.2, "value": 0.45, "confidence": 65, "color": "orange"},
            "sentiment": {"type": "sentiment", "name": "情绪因子", "weight": 0.15, "value": 0.58, "confidence": 71, "color": "purple"},
            "flow": {"type": "flow", "name": "资金流因子", "weight": 0.15, "value": 0.38, "confidence": 59, "color": "cyan"}
        },
        "signals": {
            "BTC/USDT": {
                "direction": "bullish",
                "confidence": 0.78,
                "signal_name": "Trend Breakout"
            }
        },
        "news": [
            {
                "id": "news_1",
                "title": "SEC 批准新的 BTC ETF",
                "content": "美国证券交易委员会今日批准了多支比特币 ETF 的申请，这将为加密货币市场带来新的资金流入。",
                "source": "CoinDesk",
                "sentiment": "bullish",
                "sentiment_score": 0.85,
                "published": int(datetime.utcnow().timestamp()),
                "url": "https://www.coindesk.com"
            },
            {
                "id": "news_2",
                "title": "ETH 2.0 质押量突破 3000 万枚",
                "content": "以太坊信标链质押量已突破 3000 万枚 ETH，创历史新高，显示市场对以太坊长期前景的信心。",
                "source": "The Block",
                "sentiment": "bullish",
                "sentiment_score": 0.78,
                "published": int(datetime.utcnow().timestamp()) - 3600,
                "url": "https://www.theblock.co"
            }
        ],
        "last_update": datetime.utcnow().isoformat(),
        "source": "manual_seed"
    }

    await redis.set_json("projection:dashboard:state", dashboard_state)
    print("  ✓ projection:dashboard:state")

    # 3. 写入持仓数据
    print("\n[4/5] 写入持仓数据...")
    positions = [
        {
            "symbol": "BTC/USDT",
            "side": "long",
            "size": 0.5,
            "entry_price": 78500.00,
            "leverage": 3,
            "pnl": 1367.28,
            "unrealized_pnl": 1367.28,
            "realized_pnl": 0.0,
            "stop_loss": 76000.00,
            "take_profit": 85000.00
        },
        {
            "symbol": "ETH/USDT",
            "side": "long",
            "size": 5,
            "entry_price": 2200.00,
            "leverage": 2,
            "pnl": 728.35,
            "unrealized_pnl": 728.35,
            "realized_pnl": 0.0,
            "stop_loss": 2100.00,
            "take_profit": 2500.00
        }
    ]

    await redis.set_json("positions:active", positions)
    print("  ✓ positions:active")

    # 4. 写入风险状态
    print("\n[5/5] 写入风险状态...")
    risk_state = {
        "score": 35,
        "level": "low",
        "components": {
            "volatility": 0.42,
            "flow": 0.28,
            "sentiment": 0.55,
            "macro": 0.15
        }
    }

    await redis.set_json("projection:risk:state", risk_state)
    print("  ✓ projection:risk:state")

    # 完成
    print("\n" + "=" * 80)
    print("  ✓ 数据初始化完成！")
    print("  现在可以访问 http://localhost:3003 查看数据")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(seed_data())
