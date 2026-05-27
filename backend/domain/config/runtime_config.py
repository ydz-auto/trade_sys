"""
运行时配置类型
Runtime Configuration Types

定义运行时系统的配置，确保回放和实盘的一致性。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class RuntimeMode(str, Enum):
    LIVE = "live"
    REPLAY = "replay"
    BACKTEST = "backtest"
    DRY_RUN = "dry_run"


class ClockAuthority(str, Enum):
    SYSTEM = "system"
    EVENT = "event"
    MANUAL = "manual"


class EventProcessingMode(str, Enum):
    SEQUENTIAL = "sequential"
    BATCH = "batch"
    PARALLEL = "parallel"


@dataclass
class ClockConfig:
    """时钟配置"""
    clock_authority: ClockAuthority = ClockAuthority.EVENT
    tick_interval_ms: int = 100
    allow_time_travel: bool = False


@dataclass
class EventConfig:
    """事件处理配置"""
    processing_mode: EventProcessingMode = EventProcessingMode.SEQUENTIAL
    max_queue_size: int = 10000
    enable_dedup: bool = True
    dedup_window_ms: int = 100
    enable_fault_tolerance: bool = True


@dataclass
class SnapshotConfig:
    """状态快照配置"""
    enabled: bool = True
    interval_seconds: int = 300
    max_snapshots: int = 100
    compress: bool = True


@dataclass(frozen=True)
class RuntimeConfig:
    """
    运行时配置
    
    核心特性：
    - 模式配置（live/replay/backtest）
    - 时钟权威配置
    - 事件处理配置
    - 状态快照配置
    """
    runtime_id: str
    runtime_name: str
    mode: RuntimeMode
    
    version: str = "1.0.0"
    
    # 时钟配置
    clock_config: ClockConfig = field(default_factory=ClockConfig)
    
    # 事件配置
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # 快照配置
    snapshot_config: SnapshotConfig = field(default_factory=SnapshotConfig)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    
    # 扩展配置
    extra_config: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_live(self) -> bool:
        return self.mode == RuntimeMode.LIVE
    
    @property
    def is_replay(self) -> bool:
        return self.mode == RuntimeMode.REPLAY
    
    @property
    def is_backtest(self) -> bool:
        return self.mode == RuntimeMode.BACKTEST
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "runtime_name": self.runtime_name,
            "mode": self.mode.value,
            "version": self.version,
            "clock_config": {
                "clock_authority": self.clock_config.clock_authority.value,
                "tick_interval_ms": self.clock_config.tick_interval_ms,
                "allow_time_travel": self.clock_config.allow_time_travel,
            },
            "event_config": {
                "processing_mode": self.event_config.processing_mode.value,
                "max_queue_size": self.event_config.max_queue_size,
                "enable_dedup": self.event_config.enable_dedup,
                "dedup_window_ms": self.event_config.dedup_window_ms,
                "enable_fault_tolerance": self.event_config.enable_fault_tolerance,
            },
            "snapshot_config": {
                "enabled": self.snapshot_config.enabled,
                "interval_seconds": self.snapshot_config.interval_seconds,
                "max_snapshots": self.snapshot_config.max_snapshots,
                "compress": self.snapshot_config.compress,
            },
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "extra_config": self.extra_config,
        }


@dataclass(frozen=True)
class RuntimeExecutionConfig:
    """运行时执行配置（更详细的执行级配置）"""
    runtime_config: RuntimeConfig
    
    # 执行控制
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    speed_factor: float = 1.0
    
    # 验证
    enable_validation: bool = True
    enable_metrics: bool = True
    enable_tracing: bool = True
    
    @property
    def is_time_bounded(self) -> bool:
        return self.start_time is not None and self.end_time is not None
