"""
Event Service - 业务逻辑处理器

业务逻辑：事件检测、事件分类
"""

from typing import Optional, Dict, Any

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.raw_data import RawData
from infrastructure.messaging.schema.event import Event
from domain.event import EventType, Direction, get_direction

logger = get_logger("event_service.handlers")


class EventDetector:
    """事件检测器 - 纯业务逻辑"""

    EVENT_PATTERNS = {
        "inflow": EventType.FLOW_ETF_INFLOW,
        "outflow": EventType.FLOW_ETF_OUTFLOW,
        "etf": EventType.POLICY_ETF_APPROVAL,
        "hack": EventType.PROTOCOL_HACK,
        "exploit": EventType.PROTOCOL_HACK,
        "depeg": EventType.RISK_STABLECOIN_DEPEG,
        "institutional": EventType.POLICY_REGULATION_POSITIVE,
        "adoption": EventType.POLICY_REGULATION_POSITIVE,
    }

    def detect(self, title: str, content: str) -> Optional[Event]:
        """
        从文本中检测事件

        Args:
            title: 标题
            content: 内容

        Returns:
            Event 或 None
        """
        text = (title + " " + content).lower()

        for keyword, event_type in self.EVENT_PATTERNS.items():
            if keyword in text:
                direction = get_direction(event_type)
                strength = 0.7 + (0.3 * hash(title) % 100 / 100)

                asset = "BTC"
                if "eth" in text or "ethereum" in text:
                    asset = "ETH"
                elif "sol" in text or "solana" in text:
                    asset = "SOL"

                return Event(
                    event_type=event_type.value,
                    category=event_type.category.value,
                    source="news",
                    asset=asset,
                    direction=direction.value,
                    strength=min(strength, 1.0),
                    sources=["news"],
                    metadata={"title": title, "source": "coindesk"},
                )

        return None

    def process_raw_data(self, msg: Dict[str, Any]) -> Optional[Event]:
        """
        处理原始数据，检测事件

        Args:
            msg: 原始数据消息

        Returns:
            Event 或 None
        """
        try:
            raw_data = RawData(**msg) if isinstance(msg, dict) else msg

            title = raw_data.data.get("title", "") if isinstance(raw_data.data, dict) else ""
            content = raw_data.data.get("content", "") if isinstance(raw_data.data, dict) else ""

            event = self.detect(title, content)

            if event:
                logger.info(f"Detected: {event.event_type} -> {event.asset} ({event.direction})")
            else:
                logger.debug(f"No event detected for: {title[:50]}...")

            return event

        except Exception as e:
            logger.error(f"Error processing raw data: {e}")
            return None


def get_event_detector() -> EventDetector:
    """获取事件检测器实例"""
    return EventDetector()
