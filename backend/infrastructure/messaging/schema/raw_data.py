from typing import Any, Optional

from pydantic import Field

from infrastructure.messaging.schema.base import BaseMessage


class RawData(BaseMessage):
    type: str = Field(description="news / social / price / onchain")
    symbol: Optional[str] = Field(default=None, description="交易品种")
    exchange: Optional[str] = Field(default=None, description="交易所")
    data: Any = Field(description="原始数据内容")
    raw_id: Optional[str] = Field(default=None, description="原始数据ID")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "news",
                "symbol": "BTC",
                "source": "news_api",
                "data": {"title": "ETF获批", "content": "..."},
            }
        }
