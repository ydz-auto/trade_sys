"""
Quality Module - 质量控制模块
统一的质量管理：去重、打分、溯源、审核
"""
from .content_dedup import (
    ContentDeduplicator,
    ContentFingerprint,
    SimHash,
    MinHash,
    DedupResult,
    DuplicateCandidate,
    get_deduplicator
)
from .quality_scorer import (
    QualityScorer,
    QualityScore,
    SourceTrustLevel,
    SourceConfig,
    get_scorer
)
from .source_tracking import (
    SourceTracker,
    SourceRecord,
    SourceSnapshot,
    SourceTrace,
    SnapshotStatus,
    get_tracker
)
from .human_review import (
    HumanReviewer,
    ReviewItem,
    ReviewResult,
    ReviewStatus,
    ReviewPriority,
    ReviewDecision,
    get_reviewer
)

__all__ = [
    # 去重
    "ContentDeduplicator",
    "ContentFingerprint",
    "SimHash",
    "MinHash",
    "DedupResult",
    "DuplicateCandidate",
    "get_deduplicator",
    # 打分
    "QualityScorer",
    "QualityScore",
    "SourceTrustLevel",
    "SourceConfig",
    "get_scorer",
    # 溯源
    "SourceTracker",
    "SourceRecord",
    "SourceSnapshot",
    "SourceTrace",
    "SnapshotStatus",
    "get_tracker",
    # 审核
    "HumanReviewer",
    "ReviewItem",
    "ReviewResult",
    "ReviewStatus",
    "ReviewPriority",
    "ReviewDecision",
    "get_reviewer",
]
