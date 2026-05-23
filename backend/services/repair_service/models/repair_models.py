"""
Repair Service Models - 修复服务数据模型
统一从 shared.contracts 导入基础类型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from domain.contracts import Timeframe


class GapStatus(str, Enum):
    """间隙状态"""
    DETECTED = "detected"
    PENDING = "pending"
    REPAIRING = "repairing"
    REPAIRED = "repaired"
    FAILED = "failed"


class RepairStrategy(str, Enum):
    """修复策略"""
    RESTORE = "restore"
    REBUILD = "rebuild"
    INTERPOLATE = "interpolate"
    MARK_DIRTY = "mark_dirty"


@dataclass
class GapInfo:
    """间隙信息"""
    exchange: str
    symbol: str
    timeframe: Timeframe
    gap_start: int
    gap_end: int
    missing_count: int

    status: GapStatus = GapStatus.DETECTED

    detected_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    repaired_at: Optional[int] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "gap_start": self.gap_start,
            "gap_end": self.gap_end,
            "missing_count": self.missing_count,
            "status": self.status.value,
            "detected_at": self.detected_at,
            "repaired_at": self.repaired_at,
            "metadata": self.metadata,
        }

    @property
    def gap_duration_ms(self) -> int:
        return self.gap_end - self.gap_start

    @property
    def bucket_size(self) -> int:
        return self.timeframe.seconds * 1000

    def get_missing_buckets(self) -> List[int]:
        buckets = []
        current = self.gap_start
        while current < self.gap_end:
            buckets.append(current)
            current += self.bucket_size
        return buckets


@dataclass
class RepairTask:
    """修复任务"""
    task_id: str
    gap: GapInfo

    strategy: RepairStrategy = RepairStrategy.RESTORE
    priority: int = 0

    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    started_at: Optional[int] = None
    completed_at: Optional[int] = None

    status: GapStatus = GapStatus.PENDING

    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "gap": self.gap.to_dict(),
            "strategy": self.strategy.value,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
        }


@dataclass
class IntegrityReport:
    """完整性报告"""
    exchange: str
    symbol: str
    timeframe: Timeframe
    start_time: int
    end_time: int

    total_buckets: int
    missing_count: int
    complete_count: int

    completeness: float

    gaps: List[GapInfo]

    generated_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_buckets": self.total_buckets,
            "missing_count": self.missing_count,
            "complete_count": self.complete_count,
            "completeness": self.completeness,
            "gaps": [g.to_dict() for g in self.gaps],
            "generated_at": self.generated_at,
        }
