"""
Snapshot Module - 快照模块

提供完整的状态快照和恢复能力：
1. Portfolio Snapshot
2. Strategy Snapshot
3. Execution Snapshot
4. Risk Snapshot
5. Full System Snapshot
"""

from .manager import (
    SnapshotManager,
    SnapshotType,
    SnapshotMetadata,
    PortfolioSnapshot,
    StrategySnapshot,
    ExecutionSnapshot,
    RiskSnapshot,
    FullSnapshot,
    get_snapshot_manager,
)

__all__ = [
    "SnapshotManager",
    "SnapshotType",
    "SnapshotMetadata",
    "PortfolioSnapshot",
    "StrategySnapshot",
    "ExecutionSnapshot",
    "RiskSnapshot",
    "FullSnapshot",
    "get_snapshot_manager",
]
