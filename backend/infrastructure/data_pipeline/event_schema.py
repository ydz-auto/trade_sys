"""
Unified Event Schema - 统一事件格式

核心问题：
历史事件和实时事件格式不统一，导致 Replay 和 Live 特征计算不一致。

解决方案：
1. 定义标准事件类型和字段
2. 提供从原始数据到统一格式的转换器
3. 确保相同输入产生相同输出
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import pandas as pd
import hashlib

from infrastructure.logging import get_logger
from infrastructure.utilities.time_authority import (
    get_time_authority,
    ensure_time_ms,
    normalize_time_ms
)

logger = get_logger("infrastructure.data_pipeline.event_schema")


class EventType(Enum):
    """标准事件类型"""
    CANDLE = "candle"
    TRADE = "trade"
    ORDERBOOK = "orderbook"
    FUNDING = "funding"
    LIQUIDATION = "liquidation"
    ORDER_UPDATE = "order_update"
    POSITION_UPDATE = "position_update"


@dataclass
class UnifiedEvent:
    """统一事件格式"""
    event_id: str
    event_type: EventType
    symbol: str
    exchange: str
    
    # 时间戳字段（精确到毫秒）- 强制 int64 ms
    exchange_timestamp: int  # 交易所时间（事件发生）
    received_timestamp: int  # 本地接收时间
    processed_timestamp: int  # 系统处理时间
    
    # 有效载荷
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    source: str = ""  # "replay" 或 "live"
    version: str = "1.0"
    verification_hash: str = ""
    
    # 可选字段（用于不同事件类型）
    candle_data: Optional[Dict] = None
    trade_data: Optional[Dict] = None
    orderbook_data: Optional[Dict] = None
    funding_data: Optional[Dict] = None
    liquidation_data: Optional[Dict] = None
    
    def __post_init__(self):
        """自动计算验证哈希并验证时间字段"""
        # 强制验证时间类型
        self._validate_time_fields()
        
        # 自动计算验证哈希
        if not self.verification_hash:
            self.verification_hash = self._compute_hash()
    
    def _validate_time_fields(self):
        """验证所有时间字段必须是 int 类型"""
        time_fields = [
            ('exchange_timestamp', self.exchange_timestamp),
            ('received_timestamp', self.received_timestamp),
            ('processed_timestamp', self.processed_timestamp)
        ]
        
        for field_name, value in time_fields:
            if not isinstance(value, int):
                # 尝试转换
                try:
                    normalized = normalize_time_ms(value, source=self.source, field_name=field_name)
                    setattr(self, field_name, normalized)
                    logger.warning(
                        f"Converted {field_name} from {type(value).__name__} to int: {value} -> {normalized}"
                    )
                except ValueError as e:
                    raise TypeError(
                        f"{field_name} must be int (ms timestamp), got {type(value).__name__}: {value}. {e}"
                    )
    
    def _compute_hash(self) -> str:
        """计算验证哈希（用于确定性检查）"""
        hash_content = {
            "event_type": self.event_type.value,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "exchange_timestamp": self.exchange_timestamp,
            "payload": self.payload
        }
        return hashlib.sha256(
            json.dumps(hash_content, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedEvent':
        """从字典创建"""
        data["event_type"] = EventType(data["event_type"])
        return cls(**data)
    
    def verify(self) -> bool:
        """验证完整性"""
        return self.verification_hash == self._compute_hash()


class UnifiedEventConverter:
    """统一事件转换器"""
    
    @staticmethod
    def from_kline(
        kline_data: Dict,
        symbol: str,
        exchange: str,
        source: str = "unknown",
        is_closed: bool = True
    ) -> UnifiedEvent:
        """
        从 K 线数据创建统一事件

        Args:
            kline_data: 原始 K 线数据，包含:
                - open, high, low, close
                - volume, count
                - start_time, end_time (可选)
            symbol: 交易对
            exchange: 交易所
            source: 来源
            is_closed: 是否是已完成的 K 线
        """
        exchange_ts = int(kline_data.get("start_time", 0) * 1000)
        received_ts = int(datetime.utcnow().timestamp() * 1000)

        payload = {
            "open": float(kline_data.get("open", 0)),
            "high": float(kline_data.get("high", 0)),
            "low": float(kline_data.get("low", 0)),
            "close": float(kline_data.get("close", 0)),
            "volume": float(kline_data.get("volume", 0)),
            "count": int(kline_data.get("count", 0)),
            "is_closed": is_closed
        }

        candle_data = payload.copy()

        return UnifiedEvent(
            event_id=f"{EventType.CANDLE.value}_{exchange_ts}",
            event_type=EventType.CANDLE,
            symbol=symbol,
            exchange=exchange,
            exchange_timestamp=exchange_ts,
            received_timestamp=received_ts,
            processed_timestamp=received_ts,
            payload=payload,
            candle_data=candle_data,
            source=source
        )

    @staticmethod
    def from_trade(
        trade_data: Dict,
        symbol: str,
        exchange: str,
        source: str = "unknown"
    ) -> UnifiedEvent:
        """从 Trade 数据创建统一事件"""
        exchange_ts = int(trade_data.get("timestamp", 0))
        received_ts = int(datetime.utcnow().timestamp() * 1000)

        payload = {
            "price": float(trade_data.get("price", 0)),
            "quantity": float(trade_data.get("quantity", 0)),
            "side": trade_data.get("side", "unknown"),
            "trade_id": str(trade_data.get("id", ""))
        }

        trade_data = payload.copy()

        return UnifiedEvent(
            event_id=f"{EventType.TRADE.value}_{exchange_ts}",
            event_type=EventType.TRADE,
            symbol=symbol,
            exchange=exchange,
            exchange_timestamp=exchange_ts,
            received_timestamp=received_ts,
            processed_timestamp=received_ts,
            payload=payload,
            trade_data=trade_data,
            source=source
        )

    @staticmethod
    def from_orderbook(
        orderbook_data: Dict,
        symbol: str,
        exchange: str,
        source: str = "unknown"
    ) -> UnifiedEvent:
        """从 OrderBook 数据创建统一事件"""
        exchange_ts = int(orderbook_data.get("timestamp", 0) * 1000)
        received_ts = int(datetime.utcnow().timestamp() * 1000)

        payload = {
            "bids": orderbook_data.get("bids", []),
            "asks": orderbook_data.get("asks", [])
        }

        return UnifiedEvent(
            event_id=f"{EventType.ORDERBOOK.value}_{exchange_ts}",
            event_type=EventType.ORDERBOOK,
            symbol=symbol,
            exchange=exchange,
            exchange_timestamp=exchange_ts,
            received_timestamp=received_ts,
            processed_timestamp=received_ts,
            payload=payload,
            orderbook_data=payload.copy(),
            source=source
        )

    @staticmethod
    def from_funding(
        funding_data: Dict,
        symbol: str,
        exchange: str,
        source: str = "unknown"
    ) -> UnifiedEvent:
        """从 Funding 数据创建统一事件"""
        exchange_ts = int(funding_data.get("timestamp", 0) * 1000)
        received_ts = int(datetime.utcnow().timestamp() * 1000)

        payload = {
            "rate": float(funding_data.get("rate", 0)),
            "next_time": int(funding_data.get("next_time", 0) * 1000)
        }

        return UnifiedEvent(
            event_id=f"{EventType.FUNDING.value}_{exchange_ts}",
            event_type=EventType.FUNDING,
            symbol=symbol,
            exchange=exchange,
            exchange_timestamp=exchange_ts,
            received_timestamp=received_ts,
            processed_timestamp=received_ts,
            payload=payload,
            funding_data=payload.copy(),
            source=source
        )

    @staticmethod
    def from_replay_file(
        file_path: str,
        symbol: str,
        exchange: str
    ) -> List[UnifiedEvent]:
        """从回测文件批量加载统一事件"""
        events = []

        # 简单实现：假设是 JSONL
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        event_type = EventType(data.get("type", "candle"))
                        # 根据类型调用对应转换
                        events.append(...)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Failed to load events from {file_path}: {e}")

        return events

    @staticmethod
    def to_dataframe(events: List[UnifiedEvent]) -> pd.DataFrame:
        """批量转换为 DataFrame"""
        data = [e.to_dict() for e in events]
        return pd.DataFrame(data)


class EventSchemaValidator:
    """事件模式验证器"""

    REQUIRED_FIELDS = {
        "event_id", "event_type", "symbol", "exchange",
        "exchange_timestamp", "received_timestamp", "processed_timestamp"
    }

    EVENT_REQUIRED_FIELDS = {
        EventType.CANDLE: {"open", "high", "low", "close", "volume"},
        EventType.TRADE: {"price", "quantity", "side"},
        EventType.FUNDING: {"rate"}
    }

    @classmethod
    def validate(cls, event: UnifiedEvent) -> Tuple[bool, List[str]]:
        """验证事件"""
        issues = []

        # 检查必填字段
        event_dict = event.to_dict()
        for field in cls.REQUIRED_FIELDS:
            if field not in event_dict:
                issues.append(f"Missing required field: {field}")

        # 检查事件类型特定字段
        if event.event_type in cls.EVENT_REQUIRED_FIELDS:
            required = cls.EVENT_REQUIRED_FIELDS[event.event_type]
            for field in required:
                if field not in event.payload:
                    issues.append(f"Missing payload field: {field}")

        # 验证时间顺序
        if event.exchange_timestamp > event.received_timestamp:
            issues.append("Exchange time > receive time")

        if event.received_timestamp > event.processed_timestamp:
            issues.append("Receive time > process time")

        return len(issues) == 0, issues

    @classmethod
    def validate_batch(
        cls,
        events: List[UnifiedEvent]
    ) -> Dict[str, Any]:
        """批量验证"""
        all_issues = []
        for i, event in enumerate(events):
            ok, issues = cls.validate(event)
            if not ok:
                all_issues.append({
                    "index": i,
                    "event_id": event.event_id,
                    "issues": issues
                })

        return {
            "total_events": len(events),
            "invalid_events": len(all_issues),
            "issues": all_issues
        }


_converter_instance: Optional[UnifiedEventConverter] = None


def get_event_converter() -> UnifiedEventConverter:
    """获取统一事件转换器"""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = UnifiedEventConverter()
    return _converter_instance


def validate_event(event: UnifiedEvent) -> Tuple[bool, List[str]]:
    """便捷函数：验证事件"""
    return EventSchemaValidator.validate(event)
