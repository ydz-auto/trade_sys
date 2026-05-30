"""
State Capture - 状态捕获系统

职责:
- 在关键点捕获系统完整状态
- 在 Replay 模式下进行逐状态比对
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import json
import hashlib
from pathlib import Path
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    snapshot_id: str
    timestamp_ms: int
    clock_time_ms: int
    sequence_number: int
    event_id: Optional[str]

    state_data: Dict[str, Any]

    capture_point: str
    metadata: Dict[str, Any]

    def compute_hash(self) -> str:
        content = json.dumps(self.state_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp_ms": self.timestamp_ms,
            "clock_time_ms": self.clock_time_ms,
            "sequence_number": self.sequence_number,
            "event_id": self.event_id,
            "state_data": self.state_data,
            "capture_point": self.capture_point,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateSnapshot':
        return cls(**data)


class StateCapture:

    CAPTURE_POINTS = {
        "EVENT_BEFORE": "Before processing event",
        "EVENT_AFTER": "After processing event",
        "CANDLE_CLOSE": "Candle closed",
        "ORDER_SUBMIT": "Order submitted",
        "ORDER_FILL": "Order filled",
        "PORTFOLIO_CHANGE": "Portfolio changed",
        "RISK_CHECK": "Risk check",
    }

    def __init__(
        self,
        name: str = "state_capture",
        storage_path: Optional[Path] = None,
        auto_capture: bool = True,
    ):
        self.name = name
        self.storage_path = storage_path
        self.auto_capture = auto_capture

        self._snapshots: List[StateSnapshot] = []
        self._snapshot_map: Dict[str, StateSnapshot] = {}
        self._snapshot_counter = 0

    @property
    def count(self) -> int:
        return len(self._snapshots)

    def capture(
        self,
        capture_point: str,
        clock_time_ms: int,
        sequence_number: int,
        state_data: Dict[str, Any],
        event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StateSnapshot:
        snapshot_id = f"snapshot_{self._snapshot_counter:08d}"
        self._snapshot_counter += 1

        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            timestamp_ms=int(datetime.utcnow().timestamp() * 1000),
            clock_time_ms=clock_time_ms,
            sequence_number=sequence_number,
            event_id=event_id,
            state_data=state_data,
            capture_point=capture_point,
            metadata=metadata or {},
        )

        self._snapshots.append(snapshot)
        self._snapshot_map[snapshot_id] = snapshot

        logger.debug(
            f"Captured state: {snapshot_id}, "
            f"point={capture_point}, "
            f"seq={sequence_number}"
        )

        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        return self._snapshot_map.get(snapshot_id)

    def get_snapshots(
        self,
        capture_point: Optional[str] = None,
        start_seq: int = 0,
        end_seq: Optional[int] = None,
    ) -> List[StateSnapshot]:
        results = self._snapshots

        if capture_point:
            results = [s for s in results if s.capture_point == capture_point]

        if end_seq is not None:
            results = [
                s for s in results
                if start_seq <= s.sequence_number <= end_seq
            ]
        else:
            results = [
                s for s in results
                if s.sequence_number >= start_seq
            ]

        return results

    @staticmethod
    def compare_states(
        snapshot_a: StateSnapshot,
        snapshot_b: StateSnapshot,
        include_metadata: bool = False,
    ) -> tuple[bool, Dict[str, Any]]:
        differences = {}

        if snapshot_a.sequence_number != snapshot_b.sequence_number:
            differences["sequence_number"] = {
                "a": snapshot_a.sequence_number,
                "b": snapshot_b.sequence_number,
            }

        if snapshot_a.clock_time_ms != snapshot_b.clock_time_ms:
            differences["clock_time_ms"] = {
                "a": snapshot_a.clock_time_ms,
                "b": snapshot_b.clock_time_ms,
            }

        state_diff = StateCapture._deep_diff(
            snapshot_a.state_data,
            snapshot_b.state_data,
        )
        if state_diff:
            differences["state_data"] = state_diff

        if include_metadata:
            meta_diff = StateCapture._deep_diff(
                snapshot_a.metadata,
                snapshot_b.metadata,
            )
            if meta_diff:
                differences["metadata"] = meta_diff

        is_consistent = len(differences) == 0
        return is_consistent, differences

    @staticmethod
    def _deep_diff(a: Any, b: Any, path: str = "") -> Dict[str, Any]:
        diff = {}

        if type(a) != type(b):
            diff[path or "root"] = {
                "type_a": type(a).__name__,
                "type_b": type(b).__name__,
                "value_a": a,
                "value_b": b,
            }
            return diff

        if isinstance(a, dict):
            all_keys = set(a.keys()).union(set(b.keys()))
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                if key not in a:
                    diff[new_path] = {"missing_in_a": True, "value_b": b[key]}
                elif key not in b:
                    diff[new_path] = {"missing_in_b": True, "value_a": a[key]}
                else:
                    sub_diff = StateCapture._deep_diff(a[key], b[key], new_path)
                    if sub_diff:
                        diff.update(sub_diff)

        elif isinstance(a, list):
            if len(a) != len(b):
                diff[path or "root"] = {
                    "length_a": len(a),
                    "length_b": len(b),
                }
            else:
                for i, (item_a, item_b) in enumerate(zip(a, b)):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    sub_diff = StateCapture._deep_diff(item_a, item_b, new_path)
                    if sub_diff:
                        diff.update(sub_diff)

        else:
            if a != b:
                diff[path or "root"] = {
                    "value_a": a,
                    "value_b": b,
                }

        return diff

    def save(self, file_path: Optional[Path] = None) -> Path:
        path = file_path or self.storage_path
        if path is None:
            raise ValueError("No storage path specified")

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "snapshots": [s.to_dict() for s in self._snapshots],
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved StateCapture to {path}, {len(self._snapshots)} snapshots")
        return path

    @classmethod
    def load(cls, file_path: Path) -> 'StateCapture':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        capture = cls(name=data["name"], storage_path=file_path)

        for s_data in data["snapshots"]:
            snapshot = StateSnapshot.from_dict(s_data)
            capture._snapshots.append(snapshot)
            capture._snapshot_map[snapshot.snapshot_id] = snapshot
            capture._snapshot_counter = max(
                capture._snapshot_counter,
                int(snapshot.snapshot_id.split('_')[1]) + 1
            )

        logger.info(f"Loaded StateCapture from {file_path}, {len(capture._snapshots)} snapshots")
        return capture

    def reset(self) -> None:
        self._snapshots = []
        self._snapshot_map = {}
        self._snapshot_counter = 0

    def __repr__(self) -> str:
        return f"StateCapture(name={self.name}, snapshots={len(self._snapshots)})"
