"""
Approval Service - HITL 审批服务核心
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List, Any
from .status import ApprovalRequest, ApprovalStatus, ApprovalType, ApprovalDecision
from shared.config.manager import get_config_manager
from infrastructure.logging import get_logger

logger = get_logger("approval_service")


class ApprovalService:
    """审批服务核心类"""
    
    def __init__(self):
        self._config = get_config_manager()
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._callbacks: Dict[str, asyncio.Future] = {}
        self._recalculation_handlers: Dict[str, Callable] = {}
        self._notification_handlers: List[Callable] = []
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
    
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
        
        signal_created = signal_created_at or datetime.now()
        signal_expires = signal_created + timedelta(
            seconds=config.get("signal_expires_seconds", 60)
        )
        expires_at = datetime.now() + timedelta(
            seconds=config.get("timeout_seconds", 300)
        )
        
        estimated_value = price * quantity
        
        request = ApprovalRequest(
            id=f"apr_{int(datetime.now().timestamp() * 1000)}",
            type=ApprovalType.TRADE,
            action=action,
            symbol=symbol,
            price=price,
            quantity=quantity,
            estimated_value=estimated_value,
            signal_id=signal_id,
            signal_created_at=signal_created,
            signal_expires_at=signal_expires,
            original_signal_id=None,
            approval_delayed_threshold=config.get("delayed_threshold_seconds", 60),
            timeout_seconds=config.get("timeout_seconds", 300),
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(),
            expires_at=expires_at,
            approved_at=None,
            rejected_at=None,
            retry_count=0,
            max_retries=config.get("max_retries", 2),
            recalculated_from=None,
            reason=reason,
            risk_level=risk_level,
            confidence=confidence,
            rejection_reason="",
            created_by=created_by,
            approved_by=None,
            notified_channels=[],
        )
        
        self._pending_approvals[request.id] = request
        self._callbacks[request.id] = asyncio.get_event_loop().create_future()
        
        self._monitoring_tasks[request.id] = asyncio.create_task(
            self._monitor_timeout(request.id)
        )
        
        await self._send_notifications(request)
        
        logger.info(
            f"Created approval request: {request.id}, "
            f"action={action}, symbol={symbol}, "
            f"price={price}, quantity={quantity}, "
            f"signal_age_threshold={config.get('delayed_threshold_seconds', 60)}s"
        )
        
        return request
    
    async def approve(
        self,
        approval_id: str,
        approved_by: str = "telegram",
        force: bool = False,
    ) -> ApprovalDecision:
        """批准交易"""
        request = self._get_request(approval_id)
        if not request:
            return ApprovalDecision(
                success=False,
                message=f"Approval request not found: {approval_id}"
            )
        
        if not request.is_pending:
            return ApprovalDecision(
                success=False,
                message=f"Approval request already processed: {request.status}"
            )
        
        request.approved_at = datetime.now()
        
        if force:
            logger.info(f"Force approving: {approval_id}")
            request.status = ApprovalStatus.APPROVED
            request.approved_by = approved_by
            return ApprovalDecision(
                success=True,
                message="Approved (forced)"
            )
        
        if request.is_signal_stale:
            request.status = ApprovalStatus.SIGNAL_STALE
            logger.warning(
                f"Signal expired for approval: {approval_id}, "
                f"signal_age={request.signal_age:.1f}s"
            )
            return ApprovalDecision(
                success=False,
                needs_recalculation=True,
                message="Signal expired, needs recalculation",
                original_request=request.to_dict()
            )
        
        if request.needs_reapproval_after_delay:
            price_change = await self._check_price_change(request)
            
            if abs(price_change) > self._get_price_change_threshold():
                request.status = ApprovalStatus.SIGNAL_STALE
                logger.warning(
                    f"Price changed too much: {approval_id}, "
                    f"change={price_change*100:.2f}%, "
                    f"approval_delay={request.approval_delay:.1f}s"
                )
                return ApprovalDecision(
                    success=False,
                    needs_recalculation=True,
                    message=f"Price changed {price_change*100:.2f}%, approval delay {request.approval_delay:.1f}s, needs recalculation",
                    price_change=price_change,
                    original_request=request.to_dict()
                )
        
        request.status = ApprovalStatus.APPROVED
        request.approved_by = approved_by
        
        if approval_id in self._callbacks:
            self._callbacks[approval_id].set_result(True)
            del self._callbacks[approval_id]
        
        if approval_id in self._monitoring_tasks:
            self._monitoring_tasks[approval_id].cancel()
            del self._monitoring_tasks[approval_id]
        
        logger.info(f"Approved: {approval_id}")
        
        return ApprovalDecision(
            success=True,
            needs_recalculation=False,
            message="Approved successfully"
        )
    
    async def reject(
        self,
        approval_id: str,
        reason: str = "",
        rejected_by: str = "telegram",
    ) -> bool:
        """拒绝交易"""
        request = self._get_request(approval_id)
        if not request:
            return False
        
        if not request.is_pending:
            return False
        
        request.status = ApprovalStatus.REJECTED
        request.rejected_at = datetime.now()
        request.rejection_reason = reason
        request.approved_by = rejected_by
        
        if approval_id in self._callbacks:
            self._callbacks[approval_id].set_result(False)
            del self._callbacks[approval_id]
        
        if approval_id in self._monitoring_tasks:
            self._monitoring_tasks[approval_id].cancel()
            del self._monitoring_tasks[approval_id]
        
        logger.info(f"Rejected: {approval_id}, reason={reason}")
        
        return True
    
    async def delay(
        self,
        approval_id: str,
        additional_seconds: int = 600,
    ) -> bool:
        """延长审批时间"""
        request = self._get_request(approval_id)
        if not request or not request.is_pending:
            return False
        
        request.extend_timeout(additional_seconds)
        logger.info(f"Extended timeout for: {approval_id}, +{additional_seconds}s")
        
        return True
    
    async def recalculate_and_resubmit(
        self,
        original_id: str,
    ) -> Optional[ApprovalRequest]:
        """重新计算信号并创建新审批"""
        original = self._get_request(original_id)
        if not original:
            return None
        
        logger.info(f"Recalculating signal for: {original_id}")
        
        original.status = ApprovalStatus.RECALCULATING
        
        new_signal = None
        if original_id in self._recalculation_handlers:
            try:
                handler = self._recalculation_handlers[original_id]
                new_signal = await handler(original.symbol, original.action)
            except Exception as e:
                logger.error(f"Recalculation handler failed: {e}")
        
        if not new_signal:
            latest_price = await self._get_current_price(original.symbol)
            new_signal = {
                "action": original.action,
                "symbol": original.symbol,
                "price": latest_price or original.price,
                "quantity": original.quantity,
                "reason": f"[重新计算] {original.reason}",
                "risk_level": original.risk_level,
                "confidence": original.confidence * 0.8,
            }
        
        latest_price = new_signal.get("price", original.price)
        new_quantity = self._adjust_quantity_for_new_price(
            original.quantity,
            original.price,
            latest_price
        )
        
        config = self._get_approval_config(original.symbol)
        signal_created = datetime.now()
        signal_expires = signal_created + timedelta(
            seconds=config.get("new_signal_expires_seconds", 30)
        )
        expires_at = signal_created + timedelta(
            seconds=config.get("timeout_seconds", 300)
        )
        
        new_request = ApprovalRequest(
            id=f"apr_{int(datetime.now().timestamp() * 1000)}",
            type=ApprovalType.TRADE,
            action=new_signal.get("action", original.action),
            symbol=original.symbol,
            price=latest_price,
            quantity=new_quantity,
            estimated_value=latest_price * new_quantity,
            signal_id=None,
            signal_created_at=signal_created,
            signal_expires_at=signal_expires,
            original_signal_id=None,
            approval_delayed_threshold=config.get("delayed_threshold_seconds", 60),
            timeout_seconds=config.get("timeout_seconds", 300),
            status=ApprovalStatus.PENDING,
            created_at=signal_created,
            expires_at=expires_at,
            approved_at=None,
            rejected_at=None,
            retry_count=original.retry_count + 1,
            max_retries=original.max_retries,
            recalculated_from=original_id,
            reason=new_signal.get("reason", original.reason),
            risk_level=new_signal.get("risk_level", original.risk_level),
            confidence=new_signal.get("confidence", original.confidence),
            rejection_reason="",
            created_by="system",
            approved_by=None,
            notified_channels=[],
        )
        
        original.status = ApprovalStatus.RESUBMITTED
        
        self._pending_approvals[new_request.id] = new_request
        self._callbacks[new_request.id] = asyncio.get_event_loop().create_future()
        
        self._monitoring_tasks[new_request.id] = asyncio.create_task(
            self._monitor_timeout(new_request.id)
        )
        
        if original_id in self._callbacks:
            self._callbacks[original_id].set_result(("resubmitted", new_request.id))
            del self._callbacks[original_id]
        
        await self._send_notifications(new_request, is_recalculated=True)
        
        logger.info(
            f"Resubmitted approval: {new_request.id} "
            f"(from {original_id}), new_price={latest_price}"
        )
        
        return new_request
    
    async def wait_for_decision(self, approval_id: str) -> Any:
        """异步等待用户决策"""
        if approval_id not in self._callbacks:
            return False
        
        try:
            return await asyncio.wait_for(
                self._callbacks[approval_id],
                timeout=3600
            )
        except asyncio.TimeoutError:
            return False
    
    def get_pending(self) -> List[ApprovalRequest]:
        """获取所有待审批请求"""
        return [
            r for r in self._pending_approvals.values()
            if r.is_pending
        ]
    
    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self._get_request(approval_id)
    
    def get_history(self, limit: int = 100) -> List[dict]:
        """获取审批历史"""
        approvals = sorted(
            self._pending_approvals.values(),
            key=lambda x: x.created_at,
            reverse=True
        )[:limit]
        
        return [r.to_dict() for r in approvals]
    
    def _get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """内部方法：获取审批请求"""
        return self._pending_approvals.get(approval_id)
    
    def _get_approval_config(self, symbol: str) -> Dict[str, Any]:
        """获取交易对审批配置"""
        from shared.config.defaults.business.approval import SYMBOL_APPROVAL_CONFIGS
        
        symbol_config = SYMBOL_APPROVAL_CONFIGS.get(symbol, {})
        
        if not symbol_config:
            default_config = SYMBOL_APPROVAL_CONFIGS.get("_default", {})
            symbol_config = default_config.copy()
            symbol_config["mode"] = self._config.get("approval.mode", "hybrid")
            symbol_config["timeout_seconds"] = self._config.get("approval.timeout_seconds", 300)
            symbol_config["max_retries"] = self._config.get("approval.max_retries", 2)
            symbol_config["delayed_threshold_seconds"] = self._config.get("approval.delayed_threshold_seconds", 60)
            symbol_config["signal_expires_seconds"] = self._config.get("approval.signal_expires_seconds", 60)
            symbol_config["new_signal_expires_seconds"] = self._config.get("approval.new_signal_expires_seconds", 30)
            symbol_config["auto_threshold_usd"] = self._config.get("approval.auto_threshold_usd", 100)
        
        return symbol_config
    
    def _get_price_change_threshold(self) -> float:
        """获取价格变化阈值"""
        return self._config.get("approval.price_change_threshold", 0.01)
    
    async def _check_price_change(self, request: ApprovalRequest) -> float:
        """检查价格变化"""
        try:
            current_price = await self._get_current_price(request.symbol)
            if current_price and request.price > 0:
                change = (current_price - request.price) / request.price
                return change
        except Exception as e:
            logger.error(f"Failed to check price: {e}")
        return 0.0
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前价格"""
        try:
            from services.data_service.collectors.exchange_collector import ExchangeCollector
            collector = ExchangeCollector()
            prices = await collector.collect(symbols=[symbol])
            if symbol in prices:
                return prices[symbol].prices.get("binance", {}).get("price")
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
        return None
    
    def _adjust_quantity_for_new_price(
        self,
        original_quantity: float,
        original_price: float,
        new_price: float
    ) -> float:
        """根据新价格调整数量（保持总价值不变）"""
        if new_price and original_price > 0:
            original_value = original_quantity * original_price
            return round(original_value / new_price, 8)
        return original_quantity
    
    async def _monitor_timeout(self, approval_id: str):
        """监控超时"""
        while True:
            request = self._get_request(approval_id)
            if not request:
                return
            
            if not request.is_pending:
                return
            
            if request.is_expired:
                await self._handle_timeout(approval_id)
                return
            
            await asyncio.sleep(10)
    
    async def _handle_timeout(self, approval_id: str):
        """处理超时"""
        request = self._get_request(approval_id)
        if not request:
            return
        
        logger.warning(f"Timeout for approval: {approval_id}")
        
        if request.can_retry:
            await self.recalculate_and_resubmit(approval_id)
        else:
            request.status = ApprovalStatus.EXPIRED
            if approval_id in self._callbacks:
                self._callbacks[approval_id].set_result(False)
                del self._callbacks[approval_id]
            
            logger.warning(f"Approval expired (max retries reached): {approval_id}")
    
    async def _send_notifications(
        self,
        request: ApprovalRequest,
        is_recalculated: bool = False
    ):
        """发送通知"""
        for handler in self._notification_handlers:
            try:
                await handler(request, is_recalculated)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")
    
    def needs_approval(self, signal: dict) -> bool:
        """判断是否需要人工确认"""
        mode = self._config.get("approval.mode", "hybrid")
        
        if mode == "auto":
            return False
        
        if mode == "manual":
            return True
        
        estimated_value = signal.get("estimated_value", 0)
        auto_threshold = self._config.get("approval.auto_threshold_usd", 100)
        if estimated_value < auto_threshold:
            return False
        
        risk_level = signal.get("risk_level", "MEDIUM")
        if risk_level in ["HIGH", "EXTREME"]:
            return True
        
        confidence = signal.get("confidence", 0)
        high_risk_threshold = self._config.get("approval.high_risk_threshold", 0.7)
        if confidence < high_risk_threshold:
            return True
        
        return False


_approval_service: Optional[ApprovalService] = None


def get_approval_service() -> ApprovalService:
    """获取审批服务单例"""
    global _approval_service
    if _approval_service is None:
        _approval_service = ApprovalService()
    return _approval_service


__all__ = [
    "ApprovalService",
    "ApprovalStatus",
    "ApprovalType",
    "ApprovalRequest",
    "ApprovalDecision",
    "get_approval_service",
]
