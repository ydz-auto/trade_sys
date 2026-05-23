
import hashlib
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from infrastructure.logging import get_logger
from infrastructure.runtime_clock import now_ms
from research.protocol.core import (
    ResearchDataset,
    InMemoryDataset,
    ResearchMetadata,
    EventSnapshot,
    FeatureSnapshot,
    LabelSnapshot,
    Timepoint,
    deep_freeze,
    SCHEMA_VERSION,
)
from research.protocol.adapters import (
    EventAdapter,
    FeatureAdapter,
    LabelAdapter,
)

logger = get_logger("research.builder")


def compute_fingerprint(data: List[Any], prefix: str = "") -> str:
    if not data:
        return hashlib.sha256(prefix.encode()).hexdigest()[:16]
    
    sample = []
    for item in data[:1000]:
        try:
            if hasattr(item, "__dict__"):
                d = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
                sample.append(d)
            elif isinstance(item, dict):
                sample.append(item)
        except Exception:
            pass
    
    content = json.dumps(sample, sort_keys=True, default=str)
    full = prefix + content
    return hashlib.sha256(full.encode()).hexdigest()[:16]


def get_build_commit() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


@dataclass
class DatasetBuilder:
    """
    统一研究数据构建器
    
    关键原则：
    1. Builder 持有 Adapter（Adapter 可以访问 Runtime）
    2. Builder 产出 ResearchDataset（只读合约，Research 不认识 Runtime）
    3. 数据通过 deep_freeze 结构化冻结
    
    铁律：Research 模块永远只拿到 ResearchDataset，
          永远不知道背后是谁提供的
    """
    
    dataset_id: str
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"
    
    _event_adapter: Optional[EventAdapter] = None
    _feature_adapter: Optional[FeatureAdapter] = None
    _label_adapter: Optional[LabelAdapter] = None
    
    _events: List[EventSnapshot] = field(default_factory=list)
    _features: List[FeatureSnapshot] = field(default_factory=list)
    _labels: List[LabelSnapshot] = field(default_factory=list)
    
    _start_ms: int = 0
    _end_ms: int = 0
    _train_start_ms: int = 0
    _train_end_ms: int = 0
    _test_start_ms: int = 0
    
    def set_event_adapter(self, adapter: EventAdapter) -> "DatasetBuilder":
        self._event_adapter = adapter
        return self
    
    def set_feature_adapter(self, adapter: FeatureAdapter) -> "DatasetBuilder":
        self._feature_adapter = adapter
        return self
    
    def set_label_adapter(self, adapter: LabelAdapter) -> "DatasetBuilder":
        self._label_adapter = adapter
        return self
    
    def set_time_range(
        self,
        start_ms: int,
        end_ms: int,
        train_duration_days: int = 90,
    ) -> "DatasetBuilder":
        self._start_ms = start_ms
        self._end_ms = end_ms
        
        train_ms = train_duration_days * 86400000
        self._train_start_ms = start_ms
        self._train_end_ms = start_ms + train_ms
        self._test_start_ms = self._train_end_ms
        
        return self
    
    def ingest_events(self) -> "DatasetBuilder":
        if self._event_adapter is None:
            logger.warning("No event adapter set, skipping events")
            return self
        
        logger.info(f"Ingesting events: {self._start_ms} -> {self._end_ms}")
        
        count = 0
        for event in self._event_adapter.iter_events(
            self._start_ms,
            self._end_ms,
            symbols=[self.symbol],
        ):
            self._events.append(event)
            count += 1
        
        logger.info(f"Ingested {count} events")
        return self
    
    def ingest_features(
        self,
        feature_names: Optional[List[str]] = None,
    ) -> "DatasetBuilder":
        if self._feature_adapter is None:
            logger.warning("No feature adapter set, skipping features")
            return self
        
        logger.info(f"Ingesting features: {self._start_ms} -> {self._end_ms}")
        
        count = 0
        for feature in self._feature_adapter.iter_features(
            symbol=self.symbol,
            start_ms=self._start_ms,
            end_ms=self._end_ms,
            feature_names=feature_names,
        ):
            self._features.append(feature)
            count += 1
        
        logger.info(f"Ingested {count} features")
        return self
    
    def compute_labels(
        self,
        label_type: str = "return",
        horizon_ms: int = 14400000,
    ) -> "DatasetBuilder":
        if self._label_adapter is None:
            logger.warning("No label adapter set, skipping labels")
            return self
        
        logger.info(f"Computing labels: {label_type} horizon={horizon_ms}ms")
        
        labels = self._label_adapter.compute_labels(
            symbol=self.symbol,
            label_type=label_type,
            horizon_ms=horizon_ms,
            start_ms=self._start_ms,
            end_ms=self._end_ms,
        )
        
        self._labels.extend(labels)
        logger.info(f"Computed {len(labels)} labels")
        return self
    
    def build(self) -> ResearchDataset:
        logger.info(
            f"Building dataset {self.dataset_id}: "
            f"{len(self._events)} events, "
            f"{len(self._features)} features, "
            f"{len(self._labels)} labels"
        )
        
        metadata = ResearchMetadata(
            dataset_id=self.dataset_id,
            schema_version=SCHEMA_VERSION,
            symbol=self.symbol,
            timeframe=self.timeframe,
            data_start_ms=self._start_ms,
            data_end_ms=self._end_ms,
            num_events=len(self._events),
            num_features=len(self._features),
            num_labels=len(self._labels),
            dataset_fingerprint=compute_fingerprint(
                self._events, f"{self.dataset_id}_events"
            ),
            feature_fingerprint=compute_fingerprint(
                self._features, f"{self.dataset_id}_features"
            ),
            label_fingerprint=compute_fingerprint(
                self._labels, f"{self.dataset_id}_labels"
            ),
            build_commit=get_build_commit(),
            train_start_ms=self._train_start_ms,
            test_start_ms=self._test_start_ms,
            test_end_ms=self._end_ms,
        )
        
        dataset = InMemoryDataset(
            metadata=metadata,
            events=self._events,
            features=self._features,
            labels=self._labels,
        )
        
        logger.info(
            f"Dataset built: fingerprint={metadata.dataset_fingerprint}, "
            f"build_commit={metadata.build_commit}"
        )
        
        return dataset
