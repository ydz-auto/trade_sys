"""
MVP Demo - 真实新闻测试 + 冲突融合

核心升级：多信号 → 每个资产一个最终信号
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.event import EventType, EventCategory, Direction, get_direction
from services.fusion_service import FusionEngine, FusionEvent


class RealNewsDetector:
    """基于真实新闻的事件检测"""

    EVENT_PATTERNS = {
        EventType.FLOW_ETF_INFLOW: ["inflow", "inflows"],
        EventType.FLOW_ETF_OUTFLOW: ["outflow", "outflows"],
        EventType.POLICY_ETF_APPROVAL: ["etf approval", "spot etf", "etf approved", "sec approves"],
        EventType.POLICY_REGULATION_POSITIVE: ["institutional", "institution", "adoption"],
        EventType.POLICY_REGULATION_NEGATIVE: ["ban", "regulation", "sec rejection", "regulatory"],
        EventType.PROTOCOL_HACK: ["hack", "exploit", "bridge", "stolen", "attack"],
        EventType.RISK_STABLECOIN_DEPEG: ["depeg", "stablecoin"],
    }

    def detect(self, title: str, source: str) -> Optional[dict]:
        title_lower = title.lower()

        for event_type, keywords in self.EVENT_PATTERNS.items():
            if any(kw in title_lower for kw in keywords):
                strength = self._calc_strength(title, event_type)
                direction = get_direction(event_type)

                return {
                    "event_type": event_type,
                    "asset": self._extract_asset(title),
                    "strength": strength,
                    "sources": [source],
                    "direction": direction.value,
                }
        return None

    def _calc_strength(self, title: str, event_type: EventType) -> float:
        title_lower = title.lower()
        if "major" in title_lower or "large" in title_lower or "$" in title:
            strength = 0.9
        elif "small" in title_lower or "minor" in title_lower:
            strength = 0.5
        else:
            strength = 0.7

        if event_type == EventType.RISK_STABLECOIN_DEPEG:
            strength = 1.0
        elif event_type == EventType.PROTOCOL_HACK:
            strength = 0.95

        return strength

    def _extract_asset(self, title: str) -> str:
        title_lower = title.lower()
        if "btc" in title_lower or "bitcoin" in title_lower:
            return "BTC"
        elif "eth" in title_lower or "ethereum" in title_lower:
            return "ETH"
        elif "sol" in title_lower or "solana" in title_lower:
            return "SOL"
        return "CRYPTO"


def create_fusion_event(event_data: dict) -> FusionEvent:
    """创建 FusionEvent（不是 FusionSignal）"""
    return FusionEvent(
        id=f"evt_{hash(event_data['event_type'].value)}_{int(datetime.utcnow().timestamp())}",
        timestamp=datetime.utcnow(),
        source=event_data["sources"][0] if event_data["sources"] else "news",
        event_type=event_data["event_type"].value,
        category=event_data["event_type"].category.value,
        asset=event_data["asset"],
        direction=event_data["direction"],
        strength=event_data["strength"],
        sources=event_data["sources"],
        raw_data_ids=[],
        metadata={},
    )


def resolve_conflict(signals: list) -> list[dict]:
    """冲突解决：多个信号 → 每个资产一个最终信号"""
    if not signals:
        print("  ⚠️ 没有信号可融合")
        return []

    asset_map = defaultdict(lambda: {"bullish": 0.0, "bearish": 0.0, "events": 0})

    for s in signals:
        asset = s.assets[0] if s.assets else "CRYPTO"
        direction = s.direction

        if direction == "bullish":
            asset_map[asset]["bullish"] += s.confidence
        elif direction == "bearish":
            asset_map[asset]["bearish"] += s.confidence

        asset_map[asset]["events"] += 1

    final_signals = []

    for asset, v in asset_map.items():
        net = v["bullish"] - v["bearish"]
        total_events = v["events"]

        if abs(net) < 0.05:
            final_signals.append({
                "asset": asset,
                "signal": f"{asset}_NEUTRAL",
                "direction": "neutral",
                "confidence": 0.0,
                "net_bias": net,
                "event_count": total_events,
                "reason": "信号互相抵消",
            })
            continue

        if net > 0:
            direction = "bullish"
            signal_name = f"{asset}_BULLISH"
        else:
            direction = "bearish"
            signal_name = f"{asset}_BEARISH"

        confidence = abs(net)

        final_signals.append({
            "asset": asset,
            "signal": signal_name,
            "direction": direction,
            "confidence": confidence,
            "net_bias": net,
            "event_count": total_events,
            "reason": f"净偏向{direction} (bullish={v['bullish']:.2f}, bearish={v['bearish']:.2f})",
        })

    return final_signals


def decide_action(final_signal: dict) -> dict:
    """根据融合后的信号决定最终 action"""
    confidence = final_signal["confidence"]

    if confidence < 0.1:
        return {
            "action": "HOLD",
            "position": 0.0,
            "reason": "信号模糊，不操作"
        }

    direction = final_signal["direction"]

    if direction == "bullish":
        action = "LONG"
        position = min(confidence * 0.8, 0.9)
    elif direction == "bearish":
        action = "SHORT"
        position = min(confidence * 0.8, 0.9)
    else:
        action = "HOLD"
        position = 0.0

    return {
        "action": action,
        "position": round(position, 2),
        "reason": final_signal.get("reason", "")
    }


REAL_NEWS = [
    {
        "title": "BlackRock's Bitcoin ETF sees $520M daily inflow - largest since launch",
        "source": "coindesk"
    },
    {
        "title": "Bitcoin institutional adoption accelerates as Fidelity files for new crypto ETF",
        "source": "bloomberg"
    },
    {
        "title": "SEC delays decision on multiple spot Bitcoin ETF applications",
        "source": "reuters"
    },
    {
        "title": "On-chain data shows large BTC outflows from exchanges - potential accumulation",
        "source": "glassnode"
    },
    {
        "title": "Major Ethereum hack: attacker drains $60M from DeFi protocol",
        "source": "theblock"
    },
    {
        "title": "Circle's USDC stablecoin briefly depegs during market volatility",
        "source": "coindesk"
    },
]


def run_real_news_demo():
    print("=" * 70)
    print("Real News + Conflict Resolution Test")
    print("=" * 70)

    engine = FusionEngine(window_seconds=300, min_events=1, min_confidence=0.2)
    detector = RealNewsDetector()

    print("\n[Input] 6条真实新闻")
    print("-" * 70)

    for i, news in enumerate(REAL_NEWS, 1):
        print(f"  [{i}] [{news['source']}] {news['title'][:55]}...")

    print("\n[Step 1] 事件检测")
    print("-" * 70)

    for news in REAL_NEWS:
        result = detector.detect(news["title"], news["source"])
        if result:
            emoji = "🟢" if result["direction"] == "bullish" else "🔴"
            print(f"  {emoji} {result['event_type'].value:25} → {result['asset']} ({result['direction']})")
            engine.add_event(create_fusion_event(result))
        else:
            print(f"  ⚪ (无匹配) {news['title'][:50]}...")

    print(f"\n[Step 2] 生成原始信号")
    print("-" * 70)

    signals = engine.process(price_change=0.02)

    print(f"  生成 {len(signals)} 个信号:")
    for s in signals:
        print(f"    {s.signal}: confidence={s.confidence:.3f}, direction={s.direction}")

    print(f"\n[Step 3] 冲突解决（Conflict Resolution）")
    print("=" * 70)

    final_signals = resolve_conflict(signals)

    if final_signals:
        print("\n  融合结果:")
        for fs in final_signals:
            print(f"\n  📊 {fs['asset']}:")
            print(f"     Signal: {fs['signal']}")
            print(f"     Direction: {fs['direction']}")
            print(f"     Confidence: {fs['confidence']:.3f}")
            print(f"     Net Bias: {fs['net_bias']:+.3f}")
            print(f"     Events: {fs['event_count']}")
            print(f"     Reason: {fs['reason']}")
    else:
        print("\n  ⚠️ 没有可融合的信号")

    print("\n" + "=" * 70)
    print("[Step 4] 最终交易决策")
    print("=" * 70)

    if not final_signals:
        print("\n  ❌ 无法生成交易决策（无有效信号）")
    else:
        for fs in final_signals:
            decision = decide_action(fs)
            print(f"\n  🎯 {fs['asset']}:")

            if decision["action"] == "HOLD":
                print(f"     ❌ {decision['action']} - {decision['reason']}")
            else:
                print(f"     ✅ {decision['action']}  @ position={decision['position']}")

    print("\n" + "=" * 70)
    print("✅ Pipeline 完成！")
    print("=" * 70)


if __name__ == "__main__":
    run_real_news_demo()
