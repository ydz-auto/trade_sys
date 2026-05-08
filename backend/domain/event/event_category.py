from enum import Enum


class EventCategory(str, Enum):
    MARKET_STRUCTURE = "market_structure"
    FLOW = "flow"
    MACRO = "macro"
    POLICY = "policy"
    PROTOCOL = "protocol"
    RISK = "risk"
    SENTIMENT = "sentiment"

    @classmethod
    def all(cls) -> list[str]:
        return [e.value for e in cls]

    @classmethod
    def priority(cls, category: "EventCategory") -> int:
        priorities = {
            cls.FLOW: 1,
            cls.MARKET_STRUCTURE: 2,
            cls.MACRO: 3,
            cls.POLICY: 4,
            cls.PROTOCOL: 5,
            cls.RISK: 6,
            cls.SENTIMENT: 7,
        }
        return priorities.get(category, 99)
