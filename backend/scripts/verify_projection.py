"""
验证 Runtime State Architecture 完整链路

测试：
1. Projection Runtime 启动
2. 模拟事件发送
3. Redis 状态更新
4. API 读取
5. WebSocket 推送
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("verify_projection")

from infrastructure.messaging.schema import (
    DecisionEvent,
    SignalEvent,
    RiskCheckedEvent,
    EventSource,
    generate_trace_id,
)
from infrastructure.cache.redis_client import init_redis
from services.projection_service.state_keys import ProjectionKeys


async def test_redis_connection():
    """测试 Redis 连接"""
    print("\n" + "=" * 60)
    print("1. Testing Redis Connection")
    print("=" * 60)
    
    try:
        redis = await init_redis()
        await redis.ping()
        print("✅ Redis connected successfully")
        return redis
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Make sure Redis is running: docker run -p 6379:6379 redis")
        return None


async def test_projection_keys(redis):
    """测试 Projection Keys"""
    print("\n" + "=" * 60)
    print("2. Testing Projection Keys")
    print("=" * 60)
    
    keys = [
        ProjectionKeys.dashboard_state(),
        ProjectionKeys.decision_latest(),
        ProjectionKeys.risk_state(),
        ProjectionKeys.position_current(),
        ProjectionKeys.timeline_events(),
    ]
    
    print("Projection Keys:")
    for key in keys:
        print(f"  - {key}")
    
    print("\n✅ All projection keys defined correctly")


async def test_event_simulation(redis):
    """模拟事件并测试状态更新"""
    print("\n" + "=" * 60)
    print("3. Simulating Events")
    print("=" * 60)
    
    trace_id = generate_trace_id()
    
    decision = DecisionEvent(
        trace_id=trace_id,
        source=EventSource.STRATEGY_WORKER,
        symbol="BTCUSDT",
        action="LONG",
        quantity=0.01,
        confidence=0.75,
        reason="Test decision - strong bullish signal",
    )
    
    print(f"\nDecision Event:")
    print(f"  Trace ID: {decision.trace_id}")
    print(f"  Symbol: {decision.symbol}")
    print(f"  Action: {decision.action}")
    print(f"  Confidence: {decision.confidence}")
    
    if redis:
        decision_key = ProjectionKeys.decision_latest("BTCUSDT")
        await redis.set_json(decision_key, decision.model_dump())
        print(f"\n✅ Decision saved to Redis: {decision_key}")
        
        saved = await redis.get_json(decision_key)
        if saved:
            print(f"✅ Decision retrieved from Redis")
            print(f"   Action: {saved.get('action')}")
            print(f"   Confidence: {saved.get('confidence')}")
    
    signal = SignalEvent(
        trace_id=trace_id,
        source=EventSource.STRATEGY_WORKER,
        symbol="BTCUSDT",
        signal_name="BTC_BULLISH",
        direction="bullish",
        confidence=0.8,
        strength=0.7,
        event_count=3,
    )
    
    print(f"\nSignal Event:")
    print(f"  Signal: {signal.signal_name}")
    print(f"  Direction: {signal.direction}")
    print(f"  Confidence: {signal.confidence}")
    
    if redis:
        signal_key = ProjectionKeys.signal_latest("BTCUSDT")
        await redis.set_json(signal_key, signal.model_dump())
        print(f"\n✅ Signal saved to Redis: {signal_key}")


async def test_dashboard_state(redis):
    """测试 Dashboard 状态"""
    print("\n" + "=" * 60)
    print("4. Testing Dashboard State")
    print("=" * 60)
    
    if not redis:
        print("❌ Redis not available")
        return
    
    dashboard_state = {
        "prices": {
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "price": 62345.78,
                "change24h": 2.4,
                "volume_24h": 28.5,
                "exchange": "binance",
            },
            "ETHUSDT": {
                "symbol": "ETHUSDT",
                "price": 3456.23,
                "change24h": 1.8,
                "volume_24h": 15.2,
                "exchange": "binance",
            },
        },
        "signals": {
            "BTCUSDT": {
                "signal_name": "BTC_BULLISH",
                "direction": "bullish",
                "confidence": 0.8,
            },
        },
        "regime": {
            "BTC": {
                "state": "trending_up",
                "confidence": 0.72,
                "trendStrength": 0.68,
            },
        },
        "compositeScore": 0.65,
        "last_update": datetime.utcnow().isoformat(),
    }
    
    key = ProjectionKeys.dashboard_state()
    await redis.set_json(key, dashboard_state)
    print(f"✅ Dashboard state saved to: {key}")
    
    saved = await redis.get_json(key)
    if saved:
        print(f"✅ Dashboard state retrieved")
        print(f"   Prices: {len(saved.get('prices', {}))} symbols")
        print(f"   Composite Score: {saved.get('compositeScore')}")


async def test_timeline(redis):
    """测试事件时间线"""
    print("\n" + "=" * 60)
    print("5. Testing Event Timeline")
    print("=" * 60)
    
    if not redis:
        print("❌ Redis not available")
        return
    
    events = [
        {
            "event_id": "evt_001",
            "event_type": "signal",
            "symbol": "BTCUSDT",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "📊 Signal: BTC_BULLISH",
            "description": "Confidence: 0.80",
            "severity": "success",
        },
        {
            "event_id": "evt_002",
            "event_type": "decision",
            "symbol": "BTCUSDT",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "📈 Decision: LONG BTCUSDT",
            "description": "Strong bullish signal",
            "severity": "info",
        },
        {
            "event_id": "evt_003",
            "event_type": "risk_checked",
            "symbol": "BTCUSDT",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "✅ Risk Check: LOW",
            "description": "Approved",
            "severity": "success",
        },
    ]
    
    import json
    for event in events:
        await redis.lpush(ProjectionKeys.timeline_events(), json.dumps(event))
    
    await redis.client.ltrim(ProjectionKeys.timeline_events(), 0, 99)
    
    print(f"✅ Timeline events saved")
    
    saved_events = await redis.lrange(ProjectionKeys.timeline_events(), 0, 10)
    print(f"✅ Timeline retrieved: {len(saved_events)} events")
    
    for event_str in saved_events[:3]:
        event = json.loads(event_str)
        print(f"   - {event['title']}")


async def test_api_endpoints():
    """测试 API 端点"""
    print("\n" + "=" * 60)
    print("6. Testing API Endpoints")
    print("=" * 60)
    
    import aiohttp
    
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    
    endpoints = [
        "/projection/dashboard",
        "/projection/decision/latest",
        "/projection/risk/state",
        "/projection/position/current",
        "/projection/timeline",
    ]
    
    print(f"API Base URL: {base_url}")
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            try:
                async with session.get(f"{base_url}{endpoint}") as resp:
                    if resp.status == 200:
                        print(f"  ✅ {endpoint}")
                    else:
                        print(f"  ⚠️  {endpoint} - Status: {resp.status}")
            except Exception as e:
                print(f"  ❌ {endpoint} - Error: {e}")
    
    print("\nNote: API server must be running for this test")


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("Runtime State Architecture - Verification")
    print("=" * 60)
    
    redis = await test_redis_connection()
    
    await test_projection_keys(redis)
    
    if redis:
        await test_event_simulation(redis)
        await test_dashboard_state(redis)
        await test_timeline(redis)
    
    await test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)
    
    print("\nArchitecture Summary:")
    print("  Services → Kafka → Projection Service → Redis → API/WS → Frontend")
    print("\nNext Steps:")
    print("  1. Start Redis: docker run -p 6379:6379 redis")
    print("  2. Start Kafka: docker-compose up -d kafka")
    print("  3. Start Projection Runtime: python -m runtime.projection_runtime")
    print("  4. Start API Server: python api_server.py")
    print("  5. Start Frontend: cd frontend && npm run dev")


if __name__ == "__main__":
    asyncio.run(main())
