"""
Approval Service - HITL 审批服务

业务逻辑：审批请求管理、状态跟踪
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List, Any

from infrastructure.logging import get_logger
from shared.config import get_config_manager
from .status import ApprovalRequest, ApprovalStatus, ApprovalType, ApprovalDecision

logger = get_logger("approval_service")


class ApprovalService:
    """审批服务 - 纯业务逻辑"""

    def __init__(self):
        self._config = get_config_manager()
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._callbacks: Dict[str, asyncio.Future] = {}
        self._recalculation_handlers: Dict[str, Callable] = {}
        self._notification_handlers: List[Callable] = []

    def register_recalculation_handler(self, approval_id: str, handler: Callable):
        """注册重新计算处理器"""
        self._recalculation_handlers[approval_id] = handler

    def register_notification_handler(self, handler: Callable):
        """注册通知处理器"""
        self._notification_handlers.append(handler)

    async def create_request(
        self,
        signal: dict,
        symbol: str,
        action: str,
        price: float,
        quantity: float,
        reason: str,
        risk_level: str = "MEDIUM",
        confidence: float = 0.0,
        signal_id: Optional[str] = None,
        signal_created_at: Optional[datetime] = None,
        created_by: str = "system",
    ) -> ApprovalRequest:
        """创建审批请求"""
        config = self._get_approval_config(symbol)
        
        request = ApprovalRequest(
            signal=signal,
            symbol=symbol,
            action=action,
            price=price,
            quantity=quantity,
            reason=reason,
            risk_level=risk_level,
            confidence=confidence,
            signal_id=signal_id,
            signal_created_at=signal_created_at,
            created_by=created_by,
            timeout_seconds=config.get("timeout_seconds", 300),
        )
        
        self._pending_approvals[request.approval_id] = request
        
        self._callbacks[request.approval_id] = asyncio.Future()
        
        logger.info(f"Created approval request: {request.approval_id} for {symbol} {action}")
        
        return request

    async def process_decision(
        self,
        approval_id: str,
        decision: ApprovalDecision,
        user_id: str,
        comment: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """处理审批决策"""
        request = self._pending_approvals.get(approval_id)
        if not request:
            logger.warning(f"Approval request not found: {approval_id}")
            return None

        request.status = ApprovalStatus.APPROVED if decision == ApprovalDecision.APPROVE else ApprovalStatus.REJECTED
        request.decision = decision
        request.decided_by = user_id
        request.decided_at = datetime.utcnow()
        request.comment = comment

        if approval_id in self._callbacks:
            future = self._callbacks[approval_id]
            if not future.done():
                future.set_result(request)

        logger.info(f"Processed decision for {approval_id}: {decision} by {user_id}")

        del self._pending_approvals[approval_id]
        del self._callbacks[approval_id]

        return request

    async def wait_for_decision(
        self,
        approval_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[ApprovalRequest]:
        """等待审批决策"""
        if approval_id not in self._callbacks:
            return None

        future = self._callbacks[approval_id]
        request = self._pending_approvals.get(approval_id)
        
        if not request:
            return None

        timeout = timeout or request.timeout_seconds

        try:
            await asyncio.wait_for(future, timeout=timeout)
            return future.result()
        except asyncio.TimeoutError:
            request.status = ApprovalStatus.TIMEOUT
            logger.warning(f"Approval request timed out: {approval_id}")
            return request

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """获取待审批列表"""
        return list(self._pending_approvals.values())

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self._pending_approvals.get(approval_id)

    def _get_approval_config(self, symbol: str) -> Dict[str, Any]:
        """获取审批配置"""
        return self._config.get("approval", {})


def get_approval_service() -> ApprovalService:
    """获取审批服务实例"""
    return ApprovalService()
