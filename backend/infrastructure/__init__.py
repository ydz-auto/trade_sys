"""
Infrastructure - 交易系统基础设施模块

核心原则：
1. 单一时间源：所有模块必须使用 get_clock() 获取时间
2. 严格 Label 隔离：特征和 Label 物理分离
3. 系统化特征可用性：所有特征必须注册并检查可用性
4. 不可变特征快照：一旦创建，特征不可修改
5. 统一事件处理：Replay 和 Live 使用相同路径
6. 统一 GPU 后端：所有计算通过 shared.acceleration
"""

# GPU 加速统一后端
from shared.acceleration import (
    torch,
    device,
    is_gpu,
    to_gpu,
    to_cpu,
    zeros,
    ones,
    tensor,
    from_numpy,
    get_device_info,
    get_backend_info,
    get_accelerator_info,
    clear_cache,
    synchronize
)

# Runtime Clock - 统一时间源
from infrastructure.runtime_clock import (
    RuntimeClock,
    ClockMode,
    TimeSnapshot,
    get_clock,
    set_clock_mode,
    now_ms,
    exchange_now_ms
)

# Systematic Feature Availability - 系统化特征可用性
from infrastructure.feature_availability import (
    FeatureRule,
    AvailabilityStatus,
    SystematicAvailabilityGuard,
    enforce_availability,
    get_systematic_guard,
    register_feature_rule
)

# Strict Label Isolation - 严格 Label 隔离
from infrastructure.label_isolation import (
    LabelType,
    LabelRecord,
    StrictLabelStore,
    get_label_store,
    set_label_store_mode,
    safe_dataframe,
    assert_safe_dataframe
)

# Point-in-Time Store - 时点特征存储
from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    PointInTimeFeatureRecord,
    PointInTimeSnapshot,
    FeatureSourceType,
    get_point_in_time_store,
    clear_all_stores
)

# Immutable Snapshots - 不可变特征快照
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    ImmutableSnapshotStore,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)

# Partial Candle Handler - 未完成 K 线处理
from infrastructure.feature.partial_candle_handler import (
    CandleState,
    CandlePeriod,
    PartialCandleData,
    PartialCandleHandler,
    get_partial_candle_handler
)

# Warmup Determinism - 预热确定性
from infrastructure.feature.warmup_determinism import (
    WarmupState,
    WarmupConfig,
    WarmupDeterminismManager,
    get_warmup_manager
)

# Feature Lineage - 特征血缘
from infrastructure.feature.feature_lineage import (
    FeatureType,
    FeatureNode,
    FeatureLineageSystem,
    get_feature_lineage,
    register_feature_lineage
)

# Event Time - 事件时间语义
from infrastructure.event.event_time import (
    EventSource,
    EventTimeRecord,
    EventTimeConfig,
    EventTimeManager,
    get_event_time_manager,
    record_event_time
)

# Unified Event Schema - 统一事件格式
from infrastructure.event.unified_schema import (
    EventType,
    UnifiedEvent,
    UnifiedEventConverter,
    EventSchemaValidator,
    get_event_converter,
    validate_event
)

# Unified Event Processor - 统一事件处理
from infrastructure.event.unified_event_processor import (
    EventContext,
    ProcessingResult,
    EventProcessor,
    UnifiedEventProcessor,
    CandleEventProcessor,
    TradeEventProcessor,
    get_unified_event_processor
)

# Cross-Symbol Semantics - 跨品种语义
from infrastructure.event.cross_symbol_semantics import (
    SymbolAvailability,
    CrossSymbolAvailability,
    CrossSymbolEventSemantics,
    get_cross_symbol_semantics
)

# Event Ordering - 事件排序
from infrastructure.event.event_ordering import (
    EventPriority,
    OrderedEvent,
    EventOrderingDeterminism,
    get_event_ordering,
    create_deterministic_event
)

# Replay-Live Consistency - Replay 与 Live 一致性验证
from infrastructure.verification.replay_live_verifier import (
    ConsistencyLevel,
    FeatureComparison,
    TimePointComparison,
    ConsistencyReport,
    ReplayLiveConsistencyVerifier,
    create_consistency_verifier,
    verify_replay_live_consistency
)

__all__ = [
    # === GPU 加速 ===
    "torch",
    "device",
    "is_gpu",
    "to_gpu",
    "to_cpu",
    "zeros",
    "ones",
    "tensor",
    "from_numpy",
    "get_device_info",
    "get_backend_info",
    "get_accelerator_info",
    "clear_cache",
    "synchronize",
    
    # === Runtime Clock ===
    "RuntimeClock",
    "ClockMode",
    "TimeSnapshot",
    "get_clock",
    "set_clock_mode",
    "now_ms",
    "exchange_now_ms",
    
    # === Feature Availability ===
    "FeatureRule",
    "AvailabilityStatus",
    "SystematicAvailabilityGuard",
    "enforce_availability",
    "get_systematic_guard",
    "register_feature_rule",
    
    # === Label Isolation ===
    "LabelType",
    "LabelRecord",
    "StrictLabelStore",
    "get_label_store",
    "set_label_store_mode",
    "safe_dataframe",
    "assert_safe_dataframe",
    
    # === Point-in-Time Store ===
    "PointInTimeFeatureStore",
    "PointInTimeFeatureRecord",
    "PointInTimeSnapshot",
    "FeatureSourceType",
    "get_point_in_time_store",
    "clear_all_stores",
    
    # === Immutable Snapshots ===
    "ImmutableFeatureSnapshot",
    "ImmutableSnapshotStore",
    "get_immutable_snapshot_store",
    "create_immutable_snapshot",
    
    # === Partial Candle Handler ===
    "CandleState",
    "CandlePeriod",
    "PartialCandleData",
    "PartialCandleHandler",
    "get_partial_candle_handler",
    
    # === Warmup Determinism ===
    "WarmupState",
    "WarmupConfig",
    "WarmupDeterminismManager",
    "get_warmup_manager",
    
    # === Feature Lineage ===
    "FeatureType",
    "FeatureNode",
    "FeatureLineageSystem",
    "get_feature_lineage",
    "register_feature_lineage",
    
    # === Event Time ===
    "EventSource",
    "EventTimeRecord",
    "EventTimeConfig",
    "EventTimeManager",
    "get_event_time_manager",
    "record_event_time",
    
    # === Unified Event Schema ===
    "EventType",
    "UnifiedEvent",
    "UnifiedEventConverter",
    "EventSchemaValidator",
    "get_event_converter",
    "validate_event",
    
    # === Unified Event Processor ===
    "EventContext",
    "ProcessingResult",
    "EventProcessor",
    "UnifiedEventProcessor",
    "CandleEventProcessor",
    "TradeEventProcessor",
    "get_unified_event_processor",
    
    # === Cross-Symbol Semantics ===
    "SymbolAvailability",
    "CrossSymbolAvailability",
    "CrossSymbolEventSemantics",
    "get_cross_symbol_semantics",
    
    # === Event Ordering ===
    "EventPriority",
    "OrderedEvent",
    "EventOrderingDeterminism",
    "get_event_ordering",
    "create_deterministic_event",
    
    # === Replay-Live Consistency ===
    "ConsistencyLevel",
    "FeatureComparison",
    "TimePointComparison",
    "ConsistencyReport",
    "ReplayLiveConsistencyVerifier",
    "create_consistency_verifier",
    "verify_replay_live_consistency"
]
