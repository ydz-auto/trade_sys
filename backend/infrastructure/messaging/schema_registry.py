from typing import Type, Optional, Dict, Any
from dataclasses import dataclass, field
from pydantic import BaseModel

from infrastructure.messaging.topics import Topics


@dataclass
class TopicSchema:
    topic: str
    schema: Type[BaseModel]
    description: str = ""
    version: str = "1.0.0"


class SchemaRegistry:
    _schemas: Dict[str, TopicSchema] = {}

    @classmethod
    def register(
        cls,
        topic: str,
        schema: Type[BaseModel],
        description: str = "",
        version: str = "1.0.0",
    ) -> None:
        cls._schemas[topic] = TopicSchema(
            topic=topic,
            schema=schema,
            description=description,
            version=version,
        )

    @classmethod
    def get(cls, topic: str) -> Optional[TopicSchema]:
        return cls._schemas.get(topic)

    @classmethod
    def get_schema(cls, topic: str) -> Optional[Type[BaseModel]]:
        ts = cls._schemas.get(topic)
        return ts.schema if ts else None

    @classmethod
    def all(cls) -> Dict[str, TopicSchema]:
        return cls._schemas.copy()

    @classmethod
    def clear(cls) -> None:
        cls._schemas.clear()


def register_default_schemas() -> None:
    from pydantic import BaseModel, Field
    from typing import Optional, Dict

    class RawDataSchema(BaseModel):
        symbol: str
        exchange: str
        price: float
        volume_24h: float
        timestamp: float

    class FeatureSchema(BaseModel):
        symbol: str
        factor_values: Dict[str, float]
        regime: str
        timestamp: float

    class FactorSchema(BaseModel):
        symbol: str
        factors: Dict[str, float]
        timestamp: float

    class SignalSchema(BaseModel):
        symbol: str
        action: str
        confidence: float
        timestamp: float

    class OrderSchema(BaseModel):
        order_id: str
        symbol: str
        side: str
        quantity: float
        price: Optional[float] = None

    class EventSchema(BaseModel):
        event_id: str
        event_type: str
        symbol: str
        data: Dict[str, Any]
        timestamp: float

    class AlertSchema(BaseModel):
        alert_id: str
        level: str
        message: str
        symbol: Optional[str] = None
        timestamp: float

    SchemaRegistry.register(Topics.RAW_DATA, RawDataSchema, "原始市场数据")
    SchemaRegistry.register(Topics.FEATURES, FeatureSchema, "计算后的特征数据")
    SchemaRegistry.register(Topics.FACTORS, FactorSchema, "因子数据")
    SchemaRegistry.register(Topics.SIGNALS, SignalSchema, "交易信号")
    SchemaRegistry.register(Topics.ORDERS, OrderSchema, "订单数据")
    SchemaRegistry.register(Topics.EVENTS, EventSchema, "系统事件")
    SchemaRegistry.register(Topics.ALERTS, AlertSchema, "告警信息")
