"""
Approval Status - 审批状态枚举和模型
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """审批状态"""
    PENDING = "pending"           # 等待确认
    APPROVED = "approved"         # 已批准
    REJECTED = "rejected"         # 已拒绝
    TIMEOUT = "timeout"           # 超时
    CANCELLED = "cancelled"       # 已取消
    RECALCULATING = "recalculating"  # 重新计算中
    RESUBMITTED = "resubmitted"   # 重新提交
    EXPIRED = "expired"           # 已过期（重试次数用完）
    SIGNAL_STALE = "signal_stale"  # 信号已过期


class ApprovalType(str, Enum):
    """审批类型"""
    TRADE = "trade"               # 交易审批
    ADJUST_POSITION = "adjust_position"  # 仓位调整
    CLOSE_POSITION = "close_position"    # 平仓审批
    CHANGE_RISK = "change_risk"  # 风控参数变更


class ApprovalRequest(BaseModel):
    """审批请求"""
    id: str = Field(..., description="审批请求ID")
    type: ApprovalType = Field(default=ApprovalType.TRADE, description="审批类型")
    action: str = Field(..., description="操作: BUY/SELL/CLOSE")
    
    # 交易信息
    symbol: str = Field(..., description="交易对")
    price: float = Field(..., description="价格")
    quantity: float = Field(..., description="数量")
    estimated_value: float = Field(default=0, description="估算价值（美元）")
    
    # 信号信息
    signal_id: Optional[str] = Field(default=None, description="信号ID")
    signal_created_at: datetime = Field(default_factory=datetime.now, description="信号生成时间")
    signal_expires_at: datetime = Field(..., description="信号过期时间")
    original_signal_id: Optional[str] = Field(default=None, description="原信号ID（重新计算时）")
    
    # 审批配置
    approval_delayed_threshold: int = Field(default=60, description="审批延迟阈值（秒）")
    timeout_seconds: int = Field(default=300, description="超时时间（秒）")
    
    # 审批状态
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="审批状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    expires_at: datetime = Field(..., description="过期时间")
    approved_at: Optional[datetime] = Field(default=None, description="批准时间")
    rejected_at: Optional[datetime] = Field(default=None, description="拒绝时间")
    
    # 重试信息
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=2, description="最大重试次数")
    recalculated_from: Optional[str] = Field(default=None, description="重新计算来源ID")
    
    # 原因
    reason: str = Field(default="", description="信号理由")
    risk_level: str = Field(default="MEDIUM", description="风险等级")
    confidence: float = Field(default=0.0, description="置信度")
    rejection_reason: str = Field(default="", description="拒绝原因")
    
    # 元数据
    created_by: str = Field(default="system", description="创建者")
    approved_by: Optional[str] = Field(default=None, description="批准者")
    notified_channels: list[str] = Field(default_factory=list, description="通知渠道")
    
    class Config:
        use_enum_values = True
    
    @property
    def signal_age(self) -> float:
        """信号年龄（秒）"""
        return (datetime.now() - self.signal_created_at).total_seconds()
    
    @property
    def approval_delay(self) -> float:
        """审批延迟（秒）"""
        if self.approved_at:
            return (self.approved_at - self.created_at).total_seconds()
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return datetime.now() > self.expires_at
    
    @property
    def is_signal_stale(self) -> bool:
        """信号是否过期"""
        return datetime.now() > self.signal_expires_at
    
    @property
    def needs_reapproval_after_delay(self) -> bool:
        """批准延迟后是否需要重新审批"""
        return self.approval_delay > self.approval_delayed_threshold
    
    @property
    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.retry_count < self.max_retries
    
    @property
    def is_pending(self) -> bool:
        """是否处于待审批状态"""
        return self.status in [
            ApprovalStatus.PENDING,
            ApprovalStatus.RECALCULATING,
        ]
    
    def extend_timeout(self, additional_seconds: int = 600):
        """延长超时时间"""
        from datetime import timedelta
        self.expires_at = datetime.now() + timedelta(seconds=additional_seconds)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "action": self.action,
            "symbol": self.symbol,
            "price": self.price,
            "quantity": self.quantity,
            "estimated_value": self.estimated_value,
            "signal_id": self.signal_id,
            "signal_created_at": self.signal_created_at.isoformat() if self.signal_created_at else None,
            "signal_expires_at": self.signal_expires_at.isoformat() if self.signal_expires_at else None,
            "original_signal_id": self.original_signal_id,
            "approval_delayed_threshold": self.approval_delayed_threshold,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "recalculated_from": self.recalculated_from,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "rejection_reason": self.rejection_reason,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "notified_channels": self.notified_channels,
            # 计算属性
            "signal_age": self.signal_age,
            "approval_delay": self.approval_delay,
            "is_expired": self.is_expired,
            "is_signal_stale": self.is_signal_stale,
            "needs_reapproval_after_delay": self.needs_reapproval_after_delay,
            "can_retry": self.can_retry,
        }


class ApprovalDecision(BaseModel):
    """审批决策结果"""
    success: bool = Field(..., description="是否成功")
    needs_recalculation: bool = Field(default=False, description="是否需要重新计算")
    message: str = Field(default="", description="消息")
    price_change: Optional[float] = Field(default=None, description="价格变化比例")
    original_request: Optional[dict] = Field(default=None, description="原审批请求")
    new_request: Optional[dict] = Field(default=None, description="新审批请求（重新计算后）")
    recalculated_signal: Optional[dict] = Field(default=None, description="重新计算的信号")


__all__ = [
    "ApprovalStatus",
    "ApprovalType",
    "ApprovalRequest",
    "ApprovalDecision",
]
