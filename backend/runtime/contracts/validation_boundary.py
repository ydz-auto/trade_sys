"""
Validation Boundary - Research → Runtime 隔离层

核心职责：
1. 隔离 Research Domain 和 Runtime Domain
2. 确保只有通过验证的 Proposal 才能进入 Runtime
3. 管理 Alpha Proposal 的生命周期
4. 提供确定性执行保证

架构：
    Research Domain          Validation Boundary          Runtime Domain
    ┌─────────────┐          ┌─────────────────┐          ┌─────────────┐
    │ LLM Factor  │──Proposal──▶│  Validation      │──Approved──▶│ Strategy    │
    │ Generator   │          │  Boundary        │   Signal    │ Runtime     │
    │             │          │                  │             │             │
    │ Evaluator   │──Factor──▶│  Registry        │──Deployed──▶│ Execution   │
    │             │          │                  │   Factor    │ Runtime     │
    │ Walk Forward│──Alpha───▶│  Alpha Pipeline  │─────────────▶│ Projection  │
    └─────────────┘          └─────────────────┘             └─────────────┘
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


class ValidationStage(str, Enum):
    """验证阶段"""
    PROPOSED = "proposed"
    VALIDATING = "validating"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    MONITORING = "monitoring"
    DEGRADED = "degraded"
    REJECTED = "rejected"
    ROLLBACK = "rollback"


class ValidationResult(str, Enum):
    """验证结果"""
    PASSED = "passed"
    FAILED = "failed"
    CONDITIONAL = "conditional"
    PENDING = "pending"


@dataclass
class ValidationCriteria:
    """验证标准"""
    min_ic: float = 0.02
    min_sharpe: float = 0.5
    max_drawdown: float = 0.2
    min_trades: int = 100
    regime_coverage: float = 0.6
    decay_threshold: float = 0.3


@dataclass
class ValidationReport:
    """验证报告"""
    report_id: str
    proposal_id: str
    timestamp: datetime

    result: ValidationResult

    criteria: ValidationCriteria

    ic_score: float
    sharpe_score: float
    drawdown_score: float
    regime_coverage_score: float
    decay_score: float

    overall_score: float

    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    passed_regimes: List[str] = field(default_factory=list)
    failed_regimes: List[str] = field(default_factory=list)

    recommendation: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovedSignal:
    """
    已批准信号 - Runtime 唯一接受的形式

    这是 Research → Runtime 的唯一接口
    """
    signal_id: str
    proposal_id: str

    source: str

    symbol: str
    timeframe: str

    action: str
    confidence: float
    quantity: float

    validation_report_id: str
    approved_at: datetime

    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """检查信号是否有效"""
        if self.approved_at.timestamp() < (datetime.utcnow().timestamp() - 3600):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "proposal_id": self.proposal_id,
            "source": self.source,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "action": self.action,
            "confidence": self.confidence,
            "quantity": self.quantity,
            "validation_report_id": self.validation_report_id,
            "approved_at": self.approved_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DeployedFactor:
    """
    已部署因子 - Runtime 唯一接受的形式

    这是 Research → Runtime 的因子接口
    """
    factor_id: str
    factor_name: str

    version: int

    weights: Dict[str, float]

    validation_report_id: str

    deployed_at: datetime

    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """检查因子是否过期"""
        age_hours = (datetime.utcnow() - self.deployed_at).total_seconds() / 3600
        return age_hours > max_age_hours


class ValidationBoundary:
    """
    Validation Boundary - Research 和 Runtime 之间的隔离层

    核心职责：
    1. 接收 Research 生成的 Proposal
    2. 验证 Proposal 是否满足标准
    3. 将通过的 Proposal 转换为 Runtime Signal
    4. 管理部署和监控
    """

    def __init__(self):
        self._proposals: Dict[str, Dict[str, Any]] = {}
        self._validation_reports: Dict[str, ValidationReport] = {}
        self._approved_signals: Dict[str, ApprovedSignal] = {}
        self._deployed_factors: Dict[str, DeployedFactor] = {}

        self._criteria = ValidationCriteria()

        self._stats = {
            "proposals_received": 0,
            "proposals_approved": 0,
            "proposals_rejected": 0,
            "signals_generated": 0,
            "factors_deployed": 0,
        }

    def set_validation_criteria(self, criteria: ValidationCriteria) -> None:
        """设置验证标准"""
        self._criteria = criteria
        logger.info(f"Validation criteria updated: {criteria}")

    def receive_proposal(
        self,
        proposal_id: str,
        proposal_data: Dict[str, Any],
    ) -> ValidationStage:
        """
        接收 Research 生成的 Proposal

        Args:
            proposal_id: Proposal ID
            proposal_data: Proposal 数据

        Returns:
            ValidationStage: 当前阶段
        """
        self._proposals[proposal_id] = {
            "proposal_id": proposal_id,
            "data": proposal_data,
            "stage": ValidationStage.PROPOSED,
            "received_at": datetime.utcnow(),
        }

        self._stats["proposals_received"] += 1
        logger.info(f"Proposal received: {proposal_id}")

        return ValidationStage.PROPOSED

    def validate_proposal(
        self,
        proposal_id: str,
        validation_results: Dict[str, Any],
    ) -> ValidationReport:
        """
        验证 Proposal

        Args:
            proposal_id: Proposal ID
            validation_results: 验证结果

        Returns:
            ValidationReport: 验证报告
        """
        if proposal_id not in self._proposals:
            raise ValueError(f"Proposal not found: {proposal_id}")

        proposal = self._proposals[proposal_id]
        proposal["stage"] = ValidationStage.VALIDATING

        report_id = f"rpt_{proposal_id}"

        ic_score = validation_results.get("ic", 0)
        sharpe_score = validation_results.get("sharpe", 0)
        drawdown_score = validation_results.get("max_drawdown", 0)
        regime_coverage_score = validation_results.get("regime_coverage", 0)
        decay_score = validation_results.get("decay", 0)

        warnings = []
        errors = []

        if ic_score < self._criteria.min_ic:
            errors.append(f"IC score {ic_score:.4f} below minimum {self._criteria.min_ic}")

        if sharpe_score < self._criteria.min_sharpe:
            errors.append(f"Sharpe score {sharpe_score:.4f} below minimum {self._criteria.min_sharpe}")

        if drawdown_score > self._criteria.max_drawdown:
            errors.append(f"Drawdown {drawdown_score:.2%} exceeds maximum {self._criteria.max_drawdown:.2%}")

        if regime_coverage_score < self._criteria.regime_coverage:
            warnings.append(
                f"Regime coverage {regime_coverage_score:.2%} below target {self._criteria.regime_coverage:.2%}"
            )

        if decay_score > self._criteria.decay_threshold:
            warnings.append(f"Decay rate {decay_score:.2%} above threshold {self._criteria.decay_threshold:.2%}")

        passed_regimes = validation_results.get("passed_regimes", [])
        failed_regimes = validation_results.get("failed_regimes", [])

        overall_score = self._calculate_overall_score(
            ic_score, sharpe_score, drawdown_score,
            regime_coverage_score, decay_score
        )

        if len(errors) > 0:
            result = ValidationResult.FAILED
            recommendation = "Rejected: Below minimum criteria"
        elif len(warnings) > 2:
            result = ValidationResult.CONDITIONAL
            recommendation = "Conditional: Requires review"
        else:
            result = ValidationResult.PASSED
            recommendation = "Approved: Ready for deployment"

        report = ValidationReport(
            report_id=report_id,
            proposal_id=proposal_id,
            timestamp=datetime.utcnow(),
            result=result,
            criteria=self._criteria,
            ic_score=ic_score,
            sharpe_score=sharpe_score,
            drawdown_score=drawdown_score,
            regime_coverage_score=regime_coverage_score,
            decay_score=decay_score,
            overall_score=overall_score,
            warnings=warnings,
            errors=errors,
            passed_regimes=passed_regimes,
            failed_regimes=failed_regimes,
            recommendation=recommendation,
        )

        self._validation_reports[report_id] = report

        if result == ValidationResult.PASSED:
            proposal["stage"] = ValidationStage.VALIDATED
            self._stats["proposals_approved"] += 1
        else:
            proposal["stage"] = ValidationStage.REJECTED
            self._stats["proposals_rejected"] += 1

        logger.info(
            f"Validation complete: {proposal_id} -> {result.value} "
            f"(score={overall_score:.2f})"
        )

        return report

    def _calculate_overall_score(
        self,
        ic: float,
        sharpe: float,
        drawdown: float,
        regime_coverage: float,
        decay: float,
    ) -> float:
        """计算综合评分"""
        weights = {
            "ic": 0.30,
            "sharpe": 0.25,
            "drawdown": 0.20,
            "regime": 0.15,
            "decay": 0.10,
        }

        ic_norm = min(max(ic / 0.1, 0), 1)
        sharpe_norm = min(max(sharpe / 2.0, 0), 1)
        drawdown_norm = max(1 - drawdown / 0.3, 0)
        regime_norm = regime_coverage
        decay_norm = max(1 - decay / 0.5, 0)

        score = (
            weights["ic"] * ic_norm +
            weights["sharpe"] * sharpe_norm +
            weights["drawdown"] * drawdown_norm +
            weights["regime"] * regime_norm +
            weights["decay"] * decay_norm
        )

        return min(max(score, 0), 1)

    def deploy_proposal(
        self,
        proposal_id: str,
        report_id: str,
        runtime_config: Dict[str, Any],
    ) -> Optional[ApprovedSignal]:
        """
        部署 Proposal 到 Runtime

        Args:
            proposal_id: Proposal ID
            report_id: 验证报告 ID
            runtime_config: Runtime 配置

        Returns:
            ApprovedSignal: Runtime 可接受的信号
        """
        if proposal_id not in self._proposals:
            raise ValueError(f"Proposal not found: {proposal_id}")

        proposal = self._proposals[proposal_id]
        report = self._validation_reports.get(report_id)

        if not report or report.result != ValidationResult.PASSED:
            raise ValueError(f"Proposal not validated or failed: {report_id}")

        proposal["stage"] = ValidationStage.DEPLOYED

        signal_id = f"sig_{proposal_id}"

        signal = ApprovedSignal(
            signal_id=signal_id,
            proposal_id=proposal_id,
            source="validation_boundary",
            symbol=runtime_config.get("symbol", "BTCUSDT"),
            timeframe=runtime_config.get("timeframe", "4h"),
            action=runtime_config.get("action", "LONG"),
            confidence=report.overall_score,
            quantity=runtime_config.get("quantity", 0.01),
            validation_report_id=report_id,
            approved_at=datetime.utcnow(),
            metadata={
                "runtime_config": runtime_config,
                "report_score": report.overall_score,
            },
        )

        self._approved_signals[signal_id] = signal
        self._stats["signals_generated"] += 1

        logger.info(f"Proposal deployed: {proposal_id} -> Signal: {signal_id}")

        return signal

    def deploy_factor(
        self,
        factor_id: str,
        factor_name: str,
        weights: Dict[str, float],
        report_id: str,
    ) -> DeployedFactor:
        """
        部署因子到 Runtime

        Args:
            factor_id: 因子 ID
            factor_name: 因子名称
            weights: 因子权重
            report_id: 验证报告 ID

        Returns:
            DeployedFactor: Runtime 可接受的因子
        """
        deployed = DeployedFactor(
            factor_id=factor_id,
            factor_name=factor_name,
            version=1,
            weights=weights,
            validation_report_id=report_id,
            deployed_at=datetime.utcnow(),
        )

        self._deployed_factors[factor_id] = deployed
        self._stats["factors_deployed"] += 1

        logger.info(f"Factor deployed: {factor_id} -> {factor_name}")

        return deployed

    def get_approved_signal(self, signal_id: str) -> Optional[ApprovedSignal]:
        """获取已批准信号"""
        return self._approved_signals.get(signal_id)

    def get_latest_signal_for_symbol(
        self,
        symbol: str,
        timeframe: str = "4h"
    ) -> Optional[ApprovedSignal]:
        """获取最新的有效信号"""
        valid_signals = [
            s for s in self._approved_signals.values()
            if s.symbol == symbol
            and s.timeframe == timeframe
            and s.is_valid()
        ]

        if not valid_signals:
            return None

        return max(valid_signals, key=lambda s: s.approved_at)

    def get_deployed_factor(self, factor_id: str) -> Optional[DeployedFactor]:
        """获取已部署因子"""
        return self._deployed_factors.get(factor_id)

    def check_signal_validity(self, signal_id: str) -> bool:
        """检查信号是否有效"""
        signal = self._approved_signals.get(signal_id)
        if not signal:
            return False
        return signal.is_valid()

    def rollback_proposal(self, proposal_id: str, reason: str) -> bool:
        """
        回滚 Proposal

        Args:
            proposal_id: Proposal ID
            reason: 回滚原因

        Returns:
            bool: 是否成功
        """
        if proposal_id not in self._proposals:
            return False

        proposal = self._proposals[proposal_id]
        proposal["stage"] = ValidationStage.ROLLBACK
        proposal["rollback_reason"] = reason
        proposal["rolled_back_at"] = datetime.utcnow()

        signals_to_remove = [
            sid for sid, s in self._approved_signals.items()
            if s.proposal_id == proposal_id
        ]

        for sid in signals_to_remove:
            del self._approved_signals[sid]

        logger.warning(f"Proposal rolled back: {proposal_id} - {reason}")

        return True

    def monitor_degradation(self, proposal_id: str, metrics: Dict[str, Any]) -> bool:
        """
        监控 Proposal 性能衰减

        Args:
            proposal_id: Proposal ID
            metrics: 当前性能指标

        Returns:
            bool: 是否需要回滚
        """
        if proposal_id not in self._proposals:
            return False

        proposal = self._proposals[proposal_id]

        current_ic = metrics.get("ic", 0)
        current_sharpe = metrics.get("sharpe", 0)

        if current_ic < self._criteria.min_ic * 0.5:
            proposal["stage"] = ValidationStage.DEGRADED
            logger.warning(
                f"Proposal degraded: {proposal_id} - "
                f"IC dropped to {current_ic:.4f}"
            )
            return True

        if current_sharpe < self._criteria.min_sharpe * 0.5:
            proposal["stage"] = ValidationStage.DEGRADED
            logger.warning(
                f"Proposal degraded: {proposal_id} - "
                f"Sharpe dropped to {current_sharpe:.4f}"
            )
            return True

        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "active_proposals": sum(
                1 for p in self._proposals.values()
                if p["stage"] in [
                    ValidationStage.VALIDATED,
                    ValidationStage.DEPLOYED,
                    ValidationStage.MONITORING,
                ]
            ),
            "active_signals": sum(
                1 for s in self._approved_signals.values()
                if s.is_valid()
            ),
            "deployed_factors": len(self._deployed_factors),
        }


_validation_boundary: Optional[ValidationBoundary] = None


def get_validation_boundary() -> ValidationBoundary:
    """获取 Validation Boundary 单例"""
    global _validation_boundary
    if _validation_boundary is None:
        _validation_boundary = ValidationBoundary()
    return _validation_boundary
