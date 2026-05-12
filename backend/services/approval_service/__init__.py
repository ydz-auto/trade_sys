"""
Approval Service - HITL 审批服务

包含：
- ApprovalService: 审批服务核心
- DecisionGate: 决策门
- TelegramApprovalBot: Telegram 通知 Bot
"""

from .status import (
    ApprovalStatus,
    ApprovalType,
    ApprovalRequest,
    ApprovalDecision,
)
from .main import (
    ApprovalService,
    get_approval_service,
)
from .telegram_bot import (
    TelegramApprovalBot,
    get_telegram_bot,
)
from .decision_gate import (
    DecisionGate,
    TradingMode,
    get_decision_gate,
)

__all__ = [
    # Status
    "ApprovalStatus",
    "ApprovalType",
    "ApprovalRequest",
    "ApprovalDecision",
    # Main
    "ApprovalService",
    "get_approval_service",
    # Telegram Bot
    "TelegramApprovalBot",
    "get_telegram_bot",
    # Decision Gate
    "DecisionGate",
    "TradingMode",
    "get_decision_gate",
]
