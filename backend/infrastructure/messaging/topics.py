from typing import Final

class Topics:
    NAMESPACE: Final[str] = "tradeagent"

    RAW_DATA: Final[str] = f"{NAMESPACE}.raw_data"
    FEATURES: Final[str] = f"{NAMESPACE}.features"
    FACTORS: Final[str] = f"{NAMESPACE}.factors"
    SIGNALS: Final[str] = f"{NAMESPACE}.signals"
    ORDERS: Final[str] = f"{NAMESPACE}.orders"
    EVENTS: Final[str] = f"{NAMESPACE}.events"
    ALERTS: Final[str] = f"{NAMESPACE}.alerts"

    @classmethod
    def all(cls) -> list[str]:
        return [
            cls.RAW_DATA,
            cls.FEATURES,
            cls.FACTORS,
            cls.SIGNALS,
            cls.ORDERS,
            cls.EVENTS,
            cls.ALERTS,
        ]

    @classmethod
    def by_name(cls, name: str) -> str:
        return f"{cls.NAMESPACE}.{name}"


class TopicGroups:
    DATA_INPUT = "data_input"
    PROCESSING = "processing"
    OUTPUT = "output"

    @classmethod
    def get_topics(cls, group: str) -> list[str]:
        groups = {
            cls.DATA_INPUT: [Topics.RAW_DATA],
            cls.PROCESSING: [Topics.FEATURES, Topics.FACTORS],
            cls.OUTPUT: [Topics.SIGNALS, Topics.ORDERS, Topics.ALERTS],
        }
        return groups.get(group, [])
