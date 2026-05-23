
from typing import Protocol, List, Optional, Iterator, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

from research.protocol.core import (
    EventSnapshot,
    FeatureSnapshot,
    LabelSnapshot,
    Timepoint,
    deep_freeze,
)
from infrastructure.logging import get_logger

logger = get_logger("research.adapters")


class EventAdapter(Protocol):
    """事件数据适配器 Protocol"""
    
    def iter_events(
        self,
        start_ms: int,
        end_ms: int,
        symbols: Optional[List[str]] = None,
    ) -> Iterator[EventSnapshot]:
        ...
    
    def count_events(self, start_ms: int, end_ms: int) -> int:
        ...


class FeatureAdapter(Protocol):
    """特征数据适配器 Protocol"""
    
    def iter_features(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        feature_names: Optional[List[str]] = None,
    ) -> Iterator[FeatureSnapshot]:
        ...
    
    def count_features(self, symbol: str, start_ms: int, end_ms: int) -> int:
        ...


class LabelAdapter(Protocol):
    """标签数据适配器 Protocol"""
    
    def compute_labels(
        self,
        symbol: str,
        label_type: str,
        horizon_ms: int,
        start_ms: int,
        end_ms: int,
    ) -> List[LabelSnapshot]:
        ...


@dataclass
class JournalEventAdapter:
    """
    EventJournal 适配器
    
    关键：这里可以 import Runtime 相关代码
    但产出的是只读 EventSnapshot
    ResearchDataset 本身不认识 Runtime
    """
    _journal = None
    
    async def initialize(self) -> None:
        from infrastructure.messaging.event_journal import get_event_journal
        self._journal = await get_event_journal()
        logger.info("JournalEventAdapter initialized")
    
    def iter_events(
        self,
        start_ms: int,
        end_ms: int,
        symbols: Optional[List[str]] = None,
    ) -> Iterator[EventSnapshot]:
        import asyncio
        loop = asyncio.get_event_loop()
        events = loop.run_until_complete(
            self._journal.query(start_ms, end_ms, limit=100000)
        )
        for event in events:
            if symbols and event.symbol not in symbols:
                continue
            yield self._to_snapshot(event)
    
    def count_events(self, start_ms: int, end_ms: int) -> int:
        return 0
    
    def _to_snapshot(self, event) -> EventSnapshot:
        return EventSnapshot(
            event_id=event.event_id,
            symbol=event.symbol,
            event_type=event.event_type,
            timeline=Timepoint(
                exchange_ms=event.event_time_ms,
                receive_ms=event.ingest_time_ms,
                available_ms=event.process_time_ms,
            ),
            payload=deep_freeze(event.metadata or {}),
            metadata=deep_freeze({
                "schema_version": event.schema_version,
                "trace_id": event.trace_id,
                "category": getattr(event, "category", ""),
                "source": event.source,
            }),
        )


@dataclass
class ParquetFeatureAdapter:
    """
    Parquet 特征适配器（未来大规模特征存储）
    
    目前占位，未来实现 Arrow/Parquet 列式存储
    """
    data_dir: str = ""
    symbol: str = "BTCUSDT"
    
    def iter_features(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        feature_names: Optional[List[str]] = None,
    ) -> Iterator[FeatureSnapshot]:
        logger.warning("ParquetFeatureAdapter: using mock implementation")
        return iter([])
    
    def count_features(self, symbol: str, start_ms: int, end_ms: int) -> int:
        return 0


@dataclass
class ReplayFeatureAdapter:
    """
    回放特征适配器（Replay/Live 对齐）
    """
    _runtime = None
    
    def iter_features(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        feature_names: Optional[List[str]] = None,
    ) -> Iterator[FeatureSnapshot]:
        logger.warning("ReplayFeatureAdapter: using mock implementation")
        return iter([])
    
    def count_features(self, symbol: str, start_ms: int, end_ms: int) -> int:
        return 0


@dataclass
class BacktestLabelAdapter:
    """
    回测标签适配器
    """
    
    def compute_labels(
        self,
        symbol: str,
        label_type: str,
        horizon_ms: int,
        start_ms: int,
        end_ms: int,
    ) -> List[LabelSnapshot]:
        logger.info(
            f"Computing labels: {label_type} horizon={horizon_ms}ms "
            f"for {symbol} [{start_ms} -> {end_ms}]"
        )
        
        labels = []
        horizon_hours = horizon_ms / 3600000
        
        if label_type == "return":
            bars_per_horizon = int(horizon_hours)
            step_ms = 3600000
            current = start_ms
            prev_close = None
            
            for i in range(bars_per_horizon, 1000):
                bar_end_ms = start_ms + i * step_ms
                if bar_end_ms >= end_ms:
                    break
            
            return labels
        
        return labels
