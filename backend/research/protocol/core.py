
from typing import Iterator, List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from types import MappingProxyType
from types import SimpleNamespace
from enum import Enum
import hashlib
import json
from datetime import datetime

from infrastructure.logging import get_logger

logger = get_logger("research.protocol")

SCHEMA_VERSION = "3.0"


class Timepoint:
    """
    多阶段时间链 —— 嵌套在 snapshot.timeline 中，非顶层字段
    
    完整链路：
    exchange_ms    → 交易所撮合时间
    gateway_ms     → 交易所网关收到时间
    receive_ms     → 本地网络层收到时间
    decode_ms      → 解码完成时间
    feature_ready_ms → 特征计算完成时间
    available_ms   → 策略真正可见时间
    
    铁律：Research 只用 available_ms 做决策
    """
    __slots__ = (
        "exchange_ms", "gateway_ms", "receive_ms", 
        "decode_ms", "feature_ready_ms", "available_ms",
    )
    
    def __init__(
        self,
        exchange_ms: int,
        receive_ms: Optional[int] = None,
        available_ms: Optional[int] = None,
        gateway_ms: Optional[int] = None,
        decode_ms: Optional[int] = None,
        feature_ready_ms: Optional[int] = None,
    ):
        self.exchange_ms = exchange_ms
        self.gateway_ms = gateway_ms or receive_ms or exchange_ms
        self.receive_ms = receive_ms or exchange_ms
        self.decode_ms = decode_ms or self.receive_ms
        self.feature_ready_ms = feature_ready_ms or self.receive_ms
        self.available_ms = available_ms or self.feature_ready_ms
    
    @property
    def network_latency_ms(self) -> int:
        return self.receive_ms - self.exchange_ms
    
    @property
    def processing_delay_ms(self) -> int:
        return self.available_ms - self.receive_ms
    
    @property
    def total_latency_ms(self) -> int:
        return self.available_ms - self.exchange_ms
    
    def is_valid(self) -> bool:
        return (
            self.exchange_ms <= self.gateway_ms <= self.receive_ms 
            <= self.available_ms
        )
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "exchange_ms": self.exchange_ms,
            "gateway_ms": self.gateway_ms,
            "receive_ms": self.receive_ms,
            "decode_ms": self.decode_ms,
            "feature_ready_ms": self.feature_ready_ms,
            "available_ms": self.available_ms,
        }
    
    def __repr__(self) -> str:
        return (
            f"Timepoint(exchange={self.exchange_ms}, "
            f"available={self.available_ms}, "
            f"latency={self.total_latency_ms}ms)"
        )


def deep_freeze(obj: Any) -> Any:
    """
    结构化深冻结
    
    原始          转换
    list          tuple
    dict          MappingProxyType
    set           frozenset
    dataclass     frozen dataclass
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    
    if isinstance(obj, tuple):
        return tuple(deep_freeze(i) for i in obj)
    
    if isinstance(obj, list):
        return tuple(deep_freeze(i) for i in obj)
    
    if isinstance(obj, set):
        return frozenset(deep_freeze(i) for i in obj)
    
    if isinstance(obj, dict):
        return MappingProxyType({k: deep_freeze(v) for k, v in obj.items()})
    
    if hasattr(obj, "__dict__"):
        try:
            return obj.model_copy(deep=True)
        except Exception:
            pass
    
    return obj


@dataclass(frozen=True)
class EventSnapshot:
    """
    事件只读快照
    
    timeline 嵌套 Timepoint，非顶层字段
    """
    event_id: str
    symbol: str
    event_type: str
    timeline: Timepoint
    payload: MappingProxyType
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class FeatureSnapshot:
    """
    特征只读快照
    
    注意：label 不参与 available semantics
    """
    feature_name: str
    symbol: str
    value: float
    timeline: Timepoint
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class LabelSnapshot:
    """
    收益标签只读快照
    
    关键：label 只用于训练，不属于 runtime observable world
    因此：
    - target_time_ms = label 对齐的 bar 时间
    - horizon_ms = 预测周期（1h/4h/1d）
    - 不存在 available_time_ms
    """
    label_type: str
    symbol: str
    target_time_ms: int
    horizon_ms: int
    direction: int
    value: float
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class ResearchMetadata:
    """
    研究元数据 + 版本指纹
    """
    dataset_id: str
    schema_version: str
    
    symbol: str
    timeframe: str
    data_start_ms: int
    data_end_ms: int
    
    num_events: int
    num_features: int
    num_labels: int
    
    dataset_fingerprint: str
    feature_fingerprint: str
    label_fingerprint: str
    build_commit: str
    
    train_start_ms: int = 0
    test_start_ms: int = 0
    test_end_ms: int = 0


class FeatureVector:
    """时刻点特征向量（用于 ML 输入）"""
    __slots__ = ("symbol", "available_time_ms", "values", "names")
    
    def __init__(
        self,
        symbol: str,
        available_time_ms: int,
        values: Dict[str, float],
    ):
        self.symbol = symbol
        self.available_time_ms = available_time_ms
        self.values = values
        self.names = tuple(values.keys())
    
    def __getitem__(self, name: str) -> float:
        return self.values.get(name, float("nan"))
    
    def as_array(self) -> tuple:
        return tuple(self.values.get(n, float("nan")) for n in self.names)
    
    def __len__(self) -> int:
        return len(self.names)


class ResearchDataset:
    """
    量化研究操作系统的「内核 ABI」
    
    铁律：
    1. 这是 Protocol（只读访问协议），不是数据容器
    2. 所有数据通过 Iterator 惰性读取，不全量加载到内存
    3. Research 不认识 Runtime
    
    实现类：
    - InMemoryDataset（测试/小数据）
    - ParquetDataset（大规模研究）
    - ReplayDataset（回放/live 对齐）
    """
    
    def __init__(self, metadata: ResearchMetadata):
        self._metadata = metadata
    
    @property
    def metadata(self) -> ResearchMetadata:
        return self._metadata
    
    def iter_events(
        self,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> Iterator[EventSnapshot]:
        raise NotImplementedError
    
    def iter_features(
        self,
        symbol: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> Iterator[FeatureSnapshot]:
        raise NotImplementedError
    
    def iter_labels(
        self,
        symbol: Optional[str] = None,
        label_type: Optional[str] = None,
    ) -> Iterator[LabelSnapshot]:
        raise NotImplementedError
    
    def get_feature_vector(
        self,
        symbol: str,
        available_time_ms: int,
    ) -> Optional[FeatureVector]:
        raise NotImplementedError
    
    def get_features_at(
        self,
        symbol: str,
        available_time_ms: int,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        raise NotImplementedError
    
    def iter_feature_vectors(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> Iterator[FeatureVector]:
        raise NotImplementedError


class InMemoryDataset(ResearchDataset):
    """内存数据集（测试/小数据）"""
    
    def __init__(
        self,
        metadata: ResearchMetadata,
        events: List[EventSnapshot],
        features: List[FeatureSnapshot],
        labels: List[LabelSnapshot],
    ):
        super().__init__(metadata)
        self._events = events
        self._features = features
        self._labels = labels
        
        self._build_indices()
    
    def _build_indices(self) -> None:
        self._feature_index: Dict[str, FeatureSnapshot] = {}
        for f in self._features:
            key = (f.symbol, f.feature_name, f.timeline.available_ms)
            self._feature_index[key] = f
    
    def iter_events(self, start_ms=None, end_ms=None):
        for e in self._events:
            if start_ms and e.timeline.available_ms < start_ms:
                continue
            if end_ms and e.timeline.available_ms >= end_ms:
                break
            yield e
    
    def iter_features(self, symbol=None, feature_names=None, start_ms=None, end_ms=None):
        for f in self._features:
            if symbol and f.symbol != symbol:
                continue
            if feature_names and f.feature_name not in feature_names:
                continue
            if start_ms and f.timeline.available_ms < start_ms:
                continue
            if end_ms and f.timeline.available_ms >= end_ms:
                break
            yield f
    
    def iter_labels(self, symbol=None, label_type=None):
        for l in self._labels:
            if symbol and l.symbol != symbol:
                continue
            if label_type and l.label_type != label_type:
                continue
            yield l
    
    def get_feature_vector(
        self, symbol: str, available_time_ms: int
    ) -> Optional[FeatureVector]:
        features = self.get_features_at(symbol, available_time_ms)
        if not features:
            return None
        return FeatureVector(symbol, available_time_ms, features)
    
    def get_features_at(
        self,
        symbol: str,
        available_time_ms: int,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        result = {}
        for f in self._features:
            if f.symbol != symbol:
                continue
            if f.timeline.available_ms != available_time_ms:
                continue
            if feature_names and f.feature_name not in feature_names:
                continue
            result[f.feature_name] = f.value
        return result
    
    def iter_feature_vectors(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> Iterator[FeatureVector]:
        current_time = None
        current_features = {}
        
        for f in self.iter_features(symbol=symbol, start_ms=start_ms, end_ms=end_ms):
            t = f.timeline.available_ms
            if current_time is None:
                current_time = t
            if t != current_time:
                if current_features:
                    yield FeatureVector(symbol, current_time, dict(current_features))
                current_time = t
                current_features = {}
            current_features[f.feature_name] = f.value
        
        if current_features:
            yield FeatureVector(symbol, current_time, dict(current_features))
