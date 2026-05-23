"""
Decision Gate - 决策门（集成审批服务）
"""

from enum import Enum
from typing import Optional, Callable, Any
from .main import ApprovalService, get_approval_service, ApprovalDecision
from infrastructure.config.manager import get_config_manager
from infrastructure.logging import get_logger

logger = get_logger("decision_gate")


class TradingMode(str, Enum):
    """交易模式"""
    AUTO = "auto"       # 全自动模式，直接执行
    MANUAL = "manual"   # 人工审批模式
    HYBRID = "hybrid"   # 混合模式：智能判断是否需要确认


class DecisionGate:
    """决策门"""
    
    def __init__(
        self,
        approval_service: Optional[ApprovalService] = None,
    ):
        self._approval_service = approval_service or get_approval_service()
        self._config = get_config_manager()
        self._mode = TradingMode.HYBRID
        self._initialized = False
    
    def initialize(self):
        """初始化决策门"""
        mode_str = self._config.get("approval.mode", "hybrid")
        self._mode = TradingMode(mode_str)
        self._initialized = True
        logger.info(f"Decision gate initialized, mode={self._mode.value}")
    
    def set_mode(self, mode: TradingMode):
        """设置交易模式"""
        self._mode = mode
        logger.info(f"Trading mode changed to: {mode.value}")
    
    @property
    def mode(self) -> TradingMode:
        """获取当前模式"""
        return self._mode
    
    async def process_signal(
        self,
        signal: dict,
        recalculation_handler: Optional[Callable] = None,
    ) -> dict:
        """
        处理信号
        
        Args:
            signal: 信号字典
            recalculation_handler: 重新计算处理器
        
        Returns:
            {
                "approved": bool,           # 是否批准执行
                "needs_approval": bool,     # 是否需要人工审批
                "approval_id": str,         # 审批请求ID（如果有）
                "message": str,              # 消息
                "recalculation_result": dict # 重新计算结果（如果有）
            }
        """
        if not self._initialized:
            self.initialize()
        
        if not self._needs_approval(signal):
            logger.info(
                f"Auto-approving signal: {signal.get('action')} {signal.get('symbol')}, "
                f"reason=auto_threshold"
            )
            return {
                "approved": True,
                "needs_approval": False,
                "approval_id": None,
                "message": "Auto-approved",
                "recalculation_result": None,
            }
        
        logger.info(
            f"Requiring approval for: {signal.get('action')} {signal.get('symbol')}, "
            f"reason=hybrid_mode"
        )
        
        if recalculation_handler:
            self._approval_service.register_recalculation_handler(
                f"pending_{signal.get('signal_id', 'unknown')}",
                recalculation_handler
            )
        
        request = await self._approval_service.create_request(
            signal=signal,
            symbol=signal.get("symbol"),
            action=signal.get("action"),
            price=signal.get("price", 0),
            quantity=signal.get("quantity", 0),
            reason=signal.get("reason", ""),
            risk_level=signal.get("risk_level", "MEDIUM"),
            confidence=signal.get("confidence", 0),
            signal_id=signal.get("signal_id"),
            signal_created_at=signal.get("signal_created_at"),
        )
        
        if recalculation_handler:
            self._approval_service.register_recalculation_handler(
                request.id,
                recalculation_handler
            )
        
        result = await self._approval_service.wait_for_decision(request.id)
        
        if isinstance(result, tuple) and result[0] == "resubmitted":
            new_approval_id = result[1]
            logger.info(f"Signal resubmitted as: {new_approval_id}")
            
            new_result = await self._approval_service.wait_for_decision(new_approval_id)
            
            return {
                "approved": bool(new_result),
                "needs_approval": True,
                "approval_id": new_approval_id,
                "message": "Resubmitted after recalculation",
                "recalculation_result": {"new_approval_id": new_approval_id},
            }
        
        return {
            "approved": bool(result),
            "needs_approval": True,
            "approval_id": request.id,
            "message": "Approval processed",
            "recalculation_result": None,
        }
    
    def _needs_approval(self, signal: dict) -> bool:
        """判断是否需要人工确认"""
        if self._mode == TradingMode.AUTO:
            return False
        
        if self._mode == TradingMode.MANUAL:
            return True
        
        estimated_value = signal.get("estimated_value", 0)
        auto_threshold = self._config.get("approval.auto_threshold_usd", 100)
        if estimated_value < auto_threshold:
            logger.debug(
                f"Auto-approving: estimated_value={estimated_value} < "
                f"auto_threshold={auto_threshold}"
            )
            return False
        
        risk_level = signal.get("risk_level", "MEDIUM")
        if risk_level in ["HIGH", "EXTREME"]:
            logger.debug(f"Requiring approval: risk_level={risk_level}")
            return True
        
        confidence = signal.get("confidence", 0)
        high_risk_threshold = self._config.get("approval.high_risk_threshold", 0.7)
        if confidence < high_risk_threshold:
            logger.debug(
                f"Requiring approval: confidence={confidence} < "
                f"high_risk_threshold={high_risk_threshold}"
            )
            return True
        
        return False
    
    async def force_approve(
        self,
        approval_id: str,
        approved_by: str = "system"
    ) -> bool:
        """强制批准（绕过信号时效性检查）"""
        result = await self._approval_service.approve(
            approval_id,
            approved_by=approved_by,
            force=True
        )
        return result.success
    
    async def force_reject(
        self,
        approval_id: str,
        reason: str = "",
        rejected_by: str = "system"
    ) -> bool:
        """强制拒绝"""
        return await self._approval_service.reject(
            approval_id,
            reason=reason,
            rejected_by=rejected_by
        )


_decision_gate: Optional[DecisionGate] = None


def get_decision_gate() -> DecisionGate:
    """获取决策门单例"""
    global _decision_gate
    if _decision_gate is None:
        _decision_gate = DecisionGate()
        _decision_gate.initialize()
    return _decision_gate


__all__ = [
    "DecisionGate",
    "TradingMode",
    "get_decision_gate",
]
