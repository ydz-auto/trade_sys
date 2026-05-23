"""
Event Log - 事件记录系统

职责:
- 在 Record/Live 模式下记录所有事件
- 在 Replay 模式下按完全相同的顺序回放事件
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Iterator
import json
import hashlib
from pathlib import Path

from domain.event.protocol import ImmutableEvent, FrozenDict
from domain.logging import get_logger

logger = get_logger("runtime.replay.event_log")


@dataclass
class LoggedEvent:
    """
    记录的事件 - 完整的事件信息
    """
    event_id: str
    event_type: str
    symbol: str
    exchange: str
    
    # 时间语义
    event_time_ms: int
    available_time_ms: int
    processing_time_ms: int
    
    # 排序
    sequence_number: int
    
    # 数据
    payload: Dict[str, Any]
    
    # 元数据
    source: str
    verification_hash: str
    
    @classmethod
    def from_immutable_event(
        cls,
        event: ImmutableEvent,
        sequence_number: int,
    ) -> 'LoggedEvent':
        """从 ImmutableEvent 创建"""
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            symbol=event.symbol,
            exchange=event.exchange,
            event_time_ms=event.event_time_ms,
            available_time_ms=event.available_time_ms,
            processing_time_ms=event.processing_time_ms,
            sequence_number=sequence_number,
            payload=event.payload.to_dict(),
            source=event.source.value if hasattr(event.source, 'value') else str(event.source),
            verification_hash=event.verification_hash,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "event_time_ms": self.event_time_ms,
            "available_time_ms": self.available_time_ms,
            "processing_time_ms": self.processing_time_ms,
            "sequence_number": self.sequence_number,
            "payload": self.payload,
            "source": self.source,
            "verification_hash": self.verification_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggedEvent':
        """从字典创建"""
        return cls(**data)
    
    def compute_hash(self) -> str:
        """计算内容哈希"""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class EventLog:
    """
    事件日志系统
    
    记录模式: 记录所有事件
    回放模式: 按顺序回放所有事件
    """
    
    def __init__(
        self,
        name: str = "event_log",
        storage_path: Optional[Path] = None,
    ):
        self.name = name
        self.storage_path = storage_path
        self._events: List[LoggedEvent] = []
        self._id_map: Dict[str, LoggedEvent] = {}
        self._is_recording = False
        self._start_time_ms: Optional[int] = None
    
    @property
    def is_recording(self) -> bool:
        return self._is_recording
    
    @property
    def count(self) -> int:
        return len(self._events)
    
    def start_recording(self, start_time_ms: Optional[int] = None) -> None:
        """
        开始记录
        
        Args:
            start_time_ms: 记录开始时间
        """
        self._is_recording = True
        self._start_time_ms = start_time_ms
        self._events = []
        self._id_map = {}
        logger.info(f"EventLog {self.name} started recording")
    
    def stop_recording(self) -> None:
        """停止记录"""
        self._is_recording = False
        logger.info(f"EventLog {self.name} stopped recording, recorded {len(self._events)} events")
    
    def record_event(
        self,
        event: ImmutableEvent,
        sequence_number: int,
    ) -> None:
        """
        记录一个事件
        
        Args:
            event: 要记录的事件
            sequence_number: 全局序列号
        """
        if not self._is_recording:
            return
        
        logged_event = LoggedEvent.from_immutable_event(
            event=event,
            sequence_number=sequence_number,
        )
        
        self._events.append(logged_event)
        self._id_map[event.event_id] = logged_event
        
        logger.debug(f"Recorded event: {event.event_id}, seq={sequence_number}")
    
    def get_event(self, event_id: str) -> Optional[LoggedEvent]:
        """获取指定事件"""
        return self._id_map.get(event_id)
    
    def get_events(
        self,
        start_seq: int = 0,
        end_seq: Optional[int] = None,
    ) -> List[LoggedEvent]:
        """
        获取事件列表
        
        Args:
            start_seq: 起始序列号（包含）
            end_seq: 结束序列号（包含）
        
        Returns:
            事件列表
        """
        if end_seq is None:
            end_seq = len(self._events)
        
        return [
            e for e in self._events
            if start_seq <= e.sequence_number <= end_seq
        ]
    
    def get_event_iterator(
        self,
        start_seq: int = 0,
    ) -> Iterator[LoggedEvent]:
        """
        获取事件迭代器（用于回放）
        
        Args:
            start_seq: 起始序列号
        
        Yields:
            记录的事件
        """
        for event in self._events:
            if event.sequence_number >= start_seq:
                yield event
    
    def save(self, file_path: Optional[Path] = None) -> Path:
        """
        保存事件日志到文件
        
        Args:
            file_path: 保存路径
        
        Returns:
            实际保存的路径
        """
        path = file_path or self.storage_path
        if path is None:
            raise ValueError("No storage path specified")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "name": self.name,
            "start_time_ms": self._start_time_ms,
            "events": [e.to_dict() for e in self._events],
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved EventLog to {path}, {len(self._events)} events")
        return path
    
    @classmethod
    def load(cls, file_path: Path) -> 'EventLog':
        """
        从文件加载事件日志
        
        Args:
            file_path: 文件路径
        
        Returns:
            加载的 EventLog
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        log = cls(name=data["name"], storage_path=file_path)
        log._start_time_ms = data["start_time_ms"]
        
        for e_data in data["events"]:
            event = LoggedEvent.from_dict(e_data)
            log._events.append(event)
            log._id_map[event.event_id] = event
        
        logger.info(f"Loaded EventLog from {file_path}, {len(log._events)} events")
        return log
    
    def verify_integrity(self) -> bool:
        """
        验证日志完整性
        
        Returns:
            是否完整
        """
        prev_seq = -1
        
        for event in self._events:
            # 验证序列号顺序
            if event.sequence_number != prev_seq + 1:
                logger.error(f"Sequence gap: {prev_seq} -> {event.sequence_number}")
                return False
            prev_seq = event.sequence_number
            
            # 验证内容哈希
            computed_hash = event.compute_hash()
            if computed_hash != event.verification_hash:
                logger.error(f"Hash mismatch: {event.event_id}")
                return False
        
        return True
    
    def reset(self) -> None:
        """重置日志"""
        self._events = []
        self._id_map = {}
        self._is_recording = False
        self._start_time_ms = None
    
    def __repr__(self) -> str:
        return f"EventLog(name={self.name}, events={len(self._events)})"
