"""
Human Review - 人工复审流程
支持热点审核、质量抽检、争议内容复核
"""
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict

from infrastructure.logging import get_logger

logger = get_logger("quality.review")


class ReviewStatus(Enum):
    """审核状态"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_NEEDED = "revision_needed"
    EXPIRED = "expired"


class ReviewPriority(Enum):
    """审核优先级"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class ReviewDecision(Enum):
    """审核决定"""
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"
    ESCALATE = "escalate"
    SKIP = "skip"


@dataclass
class ReviewItem:
    """待审核项目"""
    content_id: str
    title: str
    content: str
    source: str
    url: str
    submitted_at: float
    priority: ReviewPriority
    reason: str
    metadata: Dict = field(default_factory=dict)
    status: ReviewStatus = ReviewStatus.PENDING
    assigned_to: Optional[str] = None
    assigned_at: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "content_id": self.content_id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "submitted_at": self.submitted_at,
            "priority": self.priority.name,
            "reason": self.reason,
            "status": self.status.value,
            "assigned_to": self.assigned_to
        }


@dataclass
class ReviewResult:
    """审核结果"""
    content_id: str
    decision: ReviewDecision
    reviewer_id: str
    reviewed_at: float
    notes: str
    changes: Dict = field(default_factory=dict)
    feedback: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "content_id": self.content_id,
            "decision": self.decision.value,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at,
            "notes": self.notes,
            "changes": self.changes,
            "feedback": self.feedback
        }


@dataclass
class ReviewQueue:
    """审核队列"""
    name: str
    items: List[ReviewItem] = field(default_factory=list)
    max_size: int = 100
    auto_assignment: bool = True
    
    def add(self, item: ReviewItem) -> bool:
        """添加审核项"""
        if len(self.items) >= self.max_size:
            return False
        
        self.items.append(item)
        self.items.sort(key=lambda x: (x.priority.value, x.submitted_at))
        return True
    
    def get_next(self, reviewer_id: str) -> Optional[ReviewItem]:
        """获取下一个待审核项"""
        for item in self.items:
            if item.status == ReviewStatus.PENDING:
                item.status = ReviewStatus.IN_REVIEW
                item.assigned_to = reviewer_id
                item.assigned_at = time.time()
                return item
        return None
    
    def complete(
        self,
        content_id: str,
        result: ReviewResult
    ) -> bool:
        """完成审核"""
        for i, item in enumerate(self.items):
            if item.content_id == content_id:
                self.items.pop(i)
                return True
        return False
    
    def peek(self, count: int = 10) -> List[ReviewItem]:
        """查看待审核项"""
        pending = [item for item in self.items if item.status == ReviewStatus.PENDING]
        return pending[:count]


class HumanReviewer:
    """人工审核器
    
    功能：
    - 多队列管理（热点、争议、抽检）
    - 自动分配
    - 审核结果记录
    - 统计分析
    - Webhook 回调
    """
    
    def __init__(
        self,
        max_queue_size: int = 100,
        auto_escalate_threshold: int = 10
    ):
        self.max_queue_size = max_queue_size
        self.auto_escalate_threshold = auto_escalate_threshold
        
        self._queues: Dict[str, ReviewQueue] = {
            "hot": ReviewQueue("hot", max_size=max_queue_size),
            "controversial": ReviewQueue("controversial", max_size=max_queue_size),
            "sampling": ReviewQueue("sampling", max_size=max_queue_size),
            "reported": ReviewQueue("reported", max_size=max_queue_size)
        }
        
        self._review_results: Dict[str, ReviewResult] = {}
        self._reviewers: Dict[str, Dict] = {}
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        self._stats = {
            "total_submitted": 0,
            "total_reviewed": 0,
            "approved": 0,
            "rejected": 0,
            "revised": 0
        }
        
        self._hot_keywords = [
            "breaking", "breaking news", "突发",
            "urgent", "紧急", "alert",
            "crash", "暴跌", "紧急",
            "bullish", "bearish"
        ]
    
    def register_reviewer(
        self,
        reviewer_id: str,
        name: str,
        expertise: List[str] = None,
        max_items: int = 10
    ):
        """注册审核员"""
        self._reviewers[reviewer_id] = {
            "id": reviewer_id,
            "name": name,
            "expertise": expertise or [],
            "max_items": max_items,
            "current_items": 0,
            "total_reviewed": 0,
            "joined_at": time.time()
        }
        
        logger.info(f"Registered reviewer: {name} ({reviewer_id})")
    
    def should_review(
        self,
        title: str,
        content: str,
        source: str,
        is_breaking: bool = False
    ) -> bool:
        """判断是否需要人工审核"""
        title_lower = title.lower()
        content_lower = content.lower()
        
        if is_breaking:
            return True
        
        for keyword in self._hot_keywords:
            if keyword.lower() in title_lower or keyword.lower() in content_lower:
                return True
        
        if any(word in content_lower for word in ["sec ", "sec's", "lawsuit", "ban", "regulation"]):
            return True
        
        if len(content) < 200:
            return True
        
        return False
    
    def submit_for_review(
        self,
        content_id: str,
        title: str,
        content: str,
        source: str,
        url: str,
        queue: str = "normal",
        priority: ReviewPriority = ReviewPriority.NORMAL,
        reason: str = "",
        metadata: Dict = None
    ) -> bool:
        """提交审核"""
        if queue == "normal":
            if self.should_review(title, content, source):
                queue = "hot"
                priority = ReviewPriority.HIGH
                reason = reason or "Hot topic"
            else:
                return False
        
        if queue not in self._queues:
            queue = "hot"
        
        item = ReviewItem(
            content_id=content_id,
            title=title,
            content=content[:500],
            source=source,
            url=url,
            submitted_at=time.time(),
            priority=priority,
            reason=reason or "Auto-submitted",
            metadata=metadata or {}
        )
        
        success = self._queues[queue].add(item)
        
        if success:
            self._stats["total_submitted"] += 1
            logger.info(f"Submitted {content_id} to {queue} queue")
            
            self._notify_callbacks("submit", item)
        
        return success
    
    def get_next_item(self, reviewer_id: str, queue: str = "hot") -> Optional[ReviewItem]:
        """获取下一个待审核项"""
        if queue not in self._queues:
            queue = "hot"
        
        item = self._queues[queue].get_next(reviewer_id)
        
        if item:
            if reviewer_id in self._reviewers:
                self._reviewers[reviewer_id]["current_items"] += 1
            
            self._notify_callbacks("assign", item, reviewer_id)
        
        return item
    
    def submit_result(
        self,
        content_id: str,
        decision: ReviewDecision,
        reviewer_id: str,
        notes: str = "",
        changes: Dict = None,
        feedback: str = ""
    ) -> bool:
        """提交审核结果"""
        result = ReviewResult(
            content_id=content_id,
            decision=decision,
            reviewer_id=reviewer_id,
            reviewed_at=time.time(),
            notes=notes,
            changes=changes or {},
            feedback=feedback
        )
        
        self._review_results[content_id] = result
        
        for queue in self._queues.values():
            queue.complete(content_id, result)
        
        if reviewer_id in self._reviewers:
            self._reviewers[reviewer_id]["current_items"] -= 1
            self._reviewers[reviewer_id]["total_reviewed"] += 1
        
        self._stats["total_reviewed"] += 1
        
        if decision == ReviewDecision.APPROVE:
            self._stats["approved"] += 1
        elif decision == ReviewDecision.REJECT:
            self._stats["rejected"] += 1
        elif decision == ReviewDecision.REVISE:
            self._stats["revised"] += 1
        
        self._notify_callbacks("complete", result)
        
        logger.info(f"Review completed for {content_id}: {decision.value}")
        
        return True
    
    def get_pending_count(self, queue: str = None) -> int:
        """获取待审核数量"""
        if queue:
            return len(self._queues.get(queue, ReviewQueue(queue)).peek())
        else:
            return sum(
                len(q.peek())
                for q in self._queues.values()
            )
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return {
            name: {
                "size": len(queue.items),
                "pending": len(queue.peek()),
                "in_review": sum(
                    1 for item in queue.items
                    if item.status == ReviewStatus.IN_REVIEW
                )
            }
            for name, queue in self._queues.items()
        }
    
    def get_result(self, content_id: str) -> Optional[ReviewResult]:
        """获取审核结果"""
        return self._review_results.get(content_id)
    
    def get_reviewer_stats(self, reviewer_id: str) -> Optional[Dict]:
        """获取审核员统计"""
        if reviewer_id not in self._reviewers:
            return None
        
        reviewer = self._reviewers[reviewer_id]
        
        return {
            **reviewer,
            "approval_rate": self._stats["approved"] / max(self._stats["total_reviewed"], 1)
        }
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调"""
        self._callbacks[event].append(callback)
    
    def _notify_callbacks(self, event: str, *args):
        """触发回调"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def on_approved(self, callback: Callable):
        """审核通过回调"""
        def wrapper(result: ReviewResult):
            if result.decision == ReviewDecision.APPROVE:
                callback(result)
        self.register_callback("complete", wrapper)
    
    def on_rejected(self, callback: Callable):
        """审核拒绝回调"""
        def wrapper(result: ReviewResult):
            if result.decision == ReviewDecision.REJECT:
                callback(result)
        self.register_callback("complete", wrapper)
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "approval_rate": self._stats["approved"] / max(self._stats["total_reviewed"], 1),
            "rejection_rate": self._stats["rejected"] / max(self._stats["total_reviewed"], 1),
            "revision_rate": self._stats["revised"] / max(self._stats["total_reviewed"], 1),
            "reviewer_count": len(self._reviewers),
            "queue_status": self.get_queue_status()
        }


# 全局审核器
_reviewer: Optional[HumanReviewer] = None

def get_reviewer() -> HumanReviewer:
    """获取审核器单例"""
    global _reviewer
    if _reviewer is None:
        _reviewer = HumanReviewer()
    return _reviewer
