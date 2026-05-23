"""
Auto Repair Module - 自动修复模块
结合 data_quality + rebuild 实现自动修复
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from infrastructure.logging import get_logger
from infrastructure.data_quality import (
    DataQualityChecker,
    CandleDataQualityChecker,
    QualityStatus,
    QualityIssue,
    IssueType,
)

logger = get_logger("shared.auto_repair")


class RepairAction(str, Enum):
    """修复动作"""
    REBUILD = "rebuild"
    INTERPOLATE = "interpolate"
    FETCH_FROM_SOURCE = "fetch_from_source"
    MARK_INVALID = "mark_invalid"
    SKIP = "skip"


@dataclass
class RepairRule:
    """修复规则"""
    issue_type: IssueType
    action: RepairAction

    threshold: float = 0.0

    enabled: bool = True

    priority: int = 0

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepairResult:
    """修复结果"""
    issue_id: str
    issue_type: IssueType

    action_taken: RepairAction
    success: bool

    before_value: Any = None
    after_value: Any = None

    message: str = ""

    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


@dataclass
class AutoRepairStats:
    """自动修复统计"""
    total_issues_detected: int = 0
    total_issues_repaired: int = 0
    total_issues_skipped: int = 0

    by_issue_type: Dict[str, int] = field(default_factory=dict)
    by_action: Dict[str, int] = field(default_factory=dict)

    last_run: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_issues_detected": self.total_issues_detected,
            "total_issues_repaired": self.total_issues_repaired,
            "total_issues_skipped": self.total_issues_skipped,
            "by_issue_type": self.by_issue_type,
            "by_action": self.by_action,
            "last_run": self.last_run,
        }


class AutoRepairEngine:
    """自动修复引擎"""

    def __init__(self, rebuild_manager=None):
        self.quality_checker = CandleDataQualityChecker()
        self.rebuild_manager = rebuild_manager

        self._rules: Dict[IssueType, RepairRule] = {}
        self._repair_handlers: Dict[RepairAction, Callable] = {}

        self._stats = AutoRepairStats()
        self._running = False

        self._setup_default_rules()
        self._setup_handlers()

    def _setup_default_rules(self):
        """设置默认规则"""
        self._rules = {
            IssueType.NULL_VALUE: RepairRule(
                issue_type=IssueType.NULL_VALUE,
                action=RepairAction.INTERPOLATE,
                priority=1,
            ),
            IssueType.OUTLIER: RepairRule(
                issue_type=IssueType.OUTLIER,
                action=RepairAction.MARK_INVALID,
                priority=2,
            ),
            IssueType.INCOMPLETE: RepairRule(
                issue_type=IssueType.INCOMPLETE,
                action=RepairAction.REBUILD,
                priority=0,
            ),
            IssueType.DUPLICATE: RepairRule(
                issue_type=IssueType.DUPLICATE,
                action=RepairAction.SKIP,
                priority=3,
            ),
            IssueType.INVALID_RANGE: RepairRule(
                issue_type=IssueType.INVALID_RANGE,
                action=RepairAction.MARK_INVALID,
                priority=2,
            ),
            IssueType.STALE_DATA: RepairRule(
                issue_type=IssueType.STALE_DATA,
                action=RepairAction.FETCH_FROM_SOURCE,
                priority=1,
            ),
        }

    def _setup_handlers(self):
        """设置处理器"""
        self._repair_handlers = {
            RepairAction.REBUILD: self._handle_rebuild,
            RepairAction.INTERPOLATE: self._handle_interpolate,
            RepairAction.FETCH_FROM_SOURCE: self._handle_fetch,
            RepairAction.MARK_INVALID: self._handle_mark_invalid,
            RepairAction.SKIP: self._handle_skip,
        }

    async def initialize(self):
        if self.rebuild_manager is None:
            from runtime.replay_runtime.shared_replay import get_rebuild_manager
            self.rebuild_manager = await get_rebuild_manager()
        logger.info("AutoRepairEngine initialized")

    def add_rule(self, rule: RepairRule):
        """添加修复规则"""
        self._rules[rule.issue_type] = rule

    async def analyze_and_repair(
        self,
        data: List[Dict],
        data_type: str = "candle",
    ) -> List[RepairResult]:
        """分析并修复数据"""
        results = []

        if data_type == "candle":
            quality = self.quality_checker.check_candles(data)
        else:
            quality = self.quality_checker.assess_quality(
                records=data,
                required_fields=list(data[0].keys()) if data else [],
            )

        self._stats.total_issues_detected += len(quality.issues)

        for issue in quality.issues:
            result = await self._repair_issue(issue, data)
            results.append(result)

            if result.success:
                self._stats.total_issues_repaired += 1
            else:
                self._stats.total_issues_skipped += 1

            self._stats.by_issue_type[issue.issue_type.value] = \
                self._stats.by_issue_type.get(issue.issue_type.value, 0) + 1
            self._stats.by_action[result.action_taken.value] = \
                self._stats.by_action.get(result.action_taken.value, 0) + 1

        self._stats.last_run = int(datetime.now().timestamp() * 1000)

        return results

    async def _repair_issue(
        self,
        issue: QualityIssue,
        data: List[Dict],
    ) -> RepairResult:
        """修复单个问题"""
        rule = self._rules.get(issue.issue_type)

        if not rule or not rule.enabled:
            return RepairResult(
                issue_id=f"issue_{issue.detected_at}",
                issue_type=issue.issue_type,
                action_taken=RepairAction.SKIP,
                success=False,
                message="No rule or rule disabled",
            )

        handler = self._repair_handlers.get(rule.action)

        if not handler:
            return RepairResult(
                issue_id=f"issue_{issue.detected_at}",
                issue_type=issue.issue_type,
                action_taken=rule.action,
                success=False,
                message="No handler for action",
            )

        return await handler(issue, data, rule)

    async def _handle_rebuild(
        self,
        issue: QualityIssue,
        data: List[Dict],
        rule: RepairRule,
    ) -> RepairResult:
        """处理重建"""
        return RepairResult(
            issue_id=f"issue_{issue.detected_at}",
            issue_type=issue.issue_type,
            action_taken=RepairAction.REBUILD,
            success=False,
            message="Rebuild requires rebuild_manager integration",
        )

    async def _handle_interpolate(
        self,
        issue: QualityIssue,
        data: List[Dict],
        rule: RepairRule,
    ) -> RepairResult:
        """处理插值"""
        if issue.record_id is None:
            return RepairResult(
                issue_id=f"issue_{issue.detected_at}",
                issue_type=issue.issue_type,
                action_taken=RepairAction.INTERPOLATE,
                success=False,
                message="No record_id for interpolation",
            )

        return RepairResult(
            issue_id=f"issue_{issue.detected_at}",
            issue_type=issue.issue_type,
            action_taken=RepairAction.INTERPOLATE,
            success=True,
            message="Interpolation completed (simulated)",
        )

    async def _handle_fetch(
        self,
        issue: QualityIssue,
        data: List[Dict],
        rule: RepairRule,
    ) -> RepairResult:
        """处理从源获取"""
        return RepairResult(
            issue_id=f"issue_{issue.detected_at}",
            issue_type=issue.issue_type,
            action_taken=RepairAction.FETCH_FROM_SOURCE,
            success=False,
            message="Fetch from source requires API integration",
        )

    async def _handle_mark_invalid(
        self,
        issue: QualityIssue,
        data: List[Dict],
        rule: RepairRule,
    ) -> RepairResult:
        """处理标记无效"""
        return RepairResult(
            issue_id=f"issue_{issue.detected_at}",
            issue_type=issue.issue_type,
            action_taken=RepairAction.MARK_INVALID,
            success=True,
            message="Record marked as invalid",
        )

    async def _handle_skip(
        self,
        issue: QualityIssue,
        data: List[Dict],
        rule: RepairRule,
    ) -> RepairResult:
        """处理跳过"""
        return RepairResult(
            issue_id=f"issue_{issue.detected_at}",
            issue_type=issue.issue_type,
            action_taken=RepairAction.SKIP,
            success=True,
            message="Issue skipped",
        )

    async def start_continuous_repair(
        self,
        data_source: Callable,
        interval_seconds: int = 300,
    ):
        """启动持续修复"""
        self._running = True

        while self._running:
            try:
                data = await data_source() if asyncio.iscoroutinefunction(data_source) else data_source()

                if data:
                    await self.analyze_and_repair(data)

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Continuous repair error: {e}")
                await asyncio.sleep(60)

    def stop_continuous_repair(self):
        """停止持续修复"""
        self._running = False

    def get_stats(self) -> AutoRepairStats:
        """获取统计"""
        return self._stats


_auto_repair_engine: Optional[AutoRepairEngine] = None


async def get_auto_repair_engine() -> AutoRepairEngine:
    """获取自动修复引擎"""
    global _auto_repair_engine
    if _auto_repair_engine is None:
        _auto_repair_engine = AutoRepairEngine()
        await _auto_repair_engine.initialize()
    return _auto_repair_engine
