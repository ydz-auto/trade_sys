"""
AI-assisted Research Framework - AI辅助研究框架

核心架构：
LLM → Proposal → Validation → Approval → Runtime

LLM只做研究，绝不直接控制执行。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class ProposalStatus(str, Enum):
    """提案状态"""
    PENDING = "pending"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class ProposalType(str, Enum):
    """提案类型"""
    FACTOR_WEIGHT = "factor_weight"
    FACTOR_GENERATION = "factor_generation"
    PARAMETER_ADJUSTMENT = "parameter_adjustment"
    REGIME_CHANGE = "regime_change"
    RISK_ADJUSTMENT = "risk_adjustment"
    NARRATIVE_ANALYSIS = "narrative_analysis"


class ApprovalLevel(str, Enum):
    """审批级别"""
    FULL_AUTO = "full_auto"  # 完全自动（仅用于paper）
    SEMI_AUTO = "semi_auto"  # 半自动，需要系统确认
    HUMAN_REQUIRED = "human_required"  # 必须人工审批


@dataclass
class ConfidenceScore:
    """置信度评分"""
    overall: float  # 总置信度
    data_support: float  # 数据支持度
    logical_coherence: float  # 逻辑一致性
    risk_level: float  # 风险等级（0-1）
    
    reasoning: str  # 推理说明


@dataclass
class Proposal:
    """LLM提案"""
    proposal_id: str
    proposal_type: ProposalType
    title: str
    description: str
    
    # 置信度
    confidence: ConfidenceScore
    
    # 具体变更
    changes: Dict[str, Any]
    
    # 验证要求
    validation_requirements: List[str]
    
    # 风险评估
    risk_assessment: Dict[str, float]
    
    # 提案来源
    proposed_by: str
    proposed_at: datetime
    
    # 状态
    status: ProposalStatus = ProposalStatus.PENDING
    approval_level: ApprovalLevel = ApprovalLevel.HUMAN_REQUIRED
    
    # 验证结果（后面填充）
    validation_results: Optional[Dict[str, Any]] = None
    approved: Optional[bool] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


@dataclass
class ValidationResult:
    """验证结果"""
    validation_id: str
    proposal_id: str
    
    # 各个验证阶段的结果
    backtest_passed: bool
    walk_forward_passed: bool
    oos_passed: bool
    risk_check_passed: bool
    
    # 详细指标
    metrics: Dict[str, float]
    issues_found: List[str]
    
    passed: bool


class SafetyConstraints:
    """
    安全约束系统
    
    即使LLM提议，系统也必须遵守这些硬限制。
    """
    
    # 因子权重限制
    MAX_FACTOR_WEIGHT = 0.4
    MIN_FACTOR_WEIGHT = 0.05
    
    # 最大仓位限制
    MAX_POSITION_SIZE = 0.3
    MAX_PORTFOLIO_EXPOSURE = 1.0
    
    # 风险限制
    MAX_DRAWDOWN_LIMIT = 0.20
    MAX_DAILY_LOSS = 0.03
    
    # 变更限制
    MAX_WEIGHT_CHANGE_PER_UPDATE = 0.15  # 每次调整权重变化不超过15%
    MIN_TIME_BETWEEN_UPDATES = 3600  # 至少1小时才能再次调整
    
    def check_factor_weights(
        self,
        proposed_weights: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """检查因子权重是否安全"""
        issues = []
        
        for factor, weight in proposed_weights.items():
            if weight > self.MAX_FACTOR_WEIGHT:
                issues.append(
                    f"因子 {factor} 权重 {weight:.2%} 超过最大限制 {self.MAX_FACTOR_WEIGHT:.2%}"
                )
            if weight < self.MIN_FACTOR_WEIGHT:
                issues.append(
                    f"因子 {factor} 权重 {weight:.2%} 低于最小限制 {self.MIN_FACTOR_WEIGHT:.2%}"
                )
        
        total_weight = sum(proposed_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            issues.append(
                f"总权重 {total_weight:.2%} 偏离100%超过1%"
            )
        
        return len(issues) == 0, issues
    
    def check_weight_change(
        self,
        old_weights: Dict[str, float],
        new_weights: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """检查权重变化是否过大"""
        issues = []
        
        for factor in set(old_weights.keys()) | set(new_weights.keys()):
            old_w = old_weights.get(factor, 0)
            new_w = new_weights.get(factor, 0)
            change = abs(new_w - old_w)
            
            if change > self.MAX_WEIGHT_CHANGE_PER_UPDATE:
                issues.append(
                    f"因子 {factor} 权重变化 {change:.2%} 超过最大单次变化 {self.MAX_WEIGHT_CHANGE_PER_UPDATE:.2%}"
                )
        
        return len(issues) == 0, issues


class ProposalValidator:
    """
    提案验证器
    
    所有LLM提案必须经过验证才能执行。
    """
    
    def __init__(
        self,
        safety_constraints: SafetyConstraints
    ):
        self.safety = safety_constraints
        self.validation_history: List[ValidationResult] = []
    
    def validate_proposal(
        self,
        proposal: Proposal,
        historical_data: pd.DataFrame,
        current_weights: Dict[str, float]
    ) -> ValidationResult:
        """完整验证流程"""
        print(f"\n[Validation] 开始验证提案 {proposal.proposal_id}...")
        
        issues = []
        metrics = {}
        
        # 1. 安全检查
        print("[1/5] 安全检查...")
        safety_passed, safety_issues = self._check_safety(proposal, current_weights)
        if not safety_passed:
            issues.extend(safety_issues)
        
        # 2. 回测验证
        print("[2/5] 回测验证...")
        backtest_passed, backtest_metrics = self._backtest_proposal(proposal, historical_data)
        if not backtest_passed:
            issues.append("回测未通过")
        metrics.update(backtest_metrics)
        
        # 3. OOS验证
        print("[3/5] 样本外验证...")
        oos_passed, oos_metrics = self._oos_validation(proposal, historical_data)
        if not oos_passed:
            issues.append("样本外验证未通过")
        metrics.update(oos_metrics)
        
        # 4. Walk Forward验证
        print("[4/5] Walk Forward验证...")
        wf_passed, wf_metrics = self._walk_forward_validation(proposal, historical_data)
        if not wf_passed:
            issues.append("Walk Forward验证未通过")
        metrics.update(wf_metrics)
        
        # 5. 风险检查
        print("[5/5] 风险检查...")
        risk_passed, risk_issues = self._check_risk(proposal, historical_data)
        if not risk_passed:
            issues.append("风险检查未通过")
        
        passed = safety_passed and backtest_passed and oos_passed and wf_passed and risk_passed
        
        result = ValidationResult(
            validation_id=str(uuid.uuid4()),
            proposal_id=proposal.proposal_id,
            backtest_passed=backtest_passed,
            walk_forward_passed=wf_passed,
            oos_passed=risk_passed,
            risk_check_passed=len(risk_issues) == 0,
            metrics=metrics,
            issues_found=issues,
            passed=len(issues) == 0
        )
        
        if result.passed:
            print("✅ 验证通过")
        else:
            print(f"❌ 验证失败: {issues}")
        
        self.validation_history.append(result)
        return result
    
    def _check_safety(
        self,
        proposal: Proposal,
        current_weights: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """安全检查"""
        issues = []
        
        # 检查置信度
        if proposal.confidence.overall < 0.5:
            issues.append(f"置信度 {proposal.confidence.overall:.2f} 过低，低于0.5")
        
        # 检查风险等级
        if proposal.confidence.risk_level > 0.7:
            issues.append(f"风险等级 {proposal.confidence.risk_level:.2f} 过高")
        
        # 因子权重检查
        if proposal.proposal_type == ProposalType.FACTOR_WEIGHT:
            proposed_weights = proposal.changes.get("new_weights", {})
            weights_ok, weight_issues = self.safety.check_factor_weights(proposed_weights)
            if not weights_ok:
                issues.extend(weight_issues)
            
            change_ok, change_issues = self.safety.check_weight_change(current_weights, proposed_weights)
            if not change_ok:
                issues.extend(change_issues)
        
        return len(issues) == 0, issues
    
    def _backtest_proposal(
        self,
        proposal: Proposal,
        data: pd.DataFrame
    ) -> Tuple[bool, Dict[str, float]]:
        """简化版回测验证"""
        # 实际应该运行完整回测，这里演示逻辑
        metrics = {
            "backtest_sharpe": 1.2 + np.random.normal(0, 0.3),
            "backtest_max_drawdown": 0.15 + np.random.normal(0, 0.05),
            "backtest_win_rate": 0.55 + np.random.normal(0, 0.05)
        }
        
        passed = metrics["backtest_sharpe"] > 0.8 and metrics["backtest_max_drawdown"] < 0.25
        return passed, metrics
    
    def _oos_validation(
        self,
        proposal: Proposal,
        data: pd.DataFrame
    ) -> Tuple[bool, Dict[str, float]]:
        """样本外验证"""
        metrics = {
            "oos_sharpe": 1.0 + np.random.normal(0, 0.4),
            "oos_ic": 0.025 + np.random.normal(0, 0.01)
        }
        passed = metrics["oos_sharpe"] > 0.6
        return passed, metrics
    
    def _walk_forward_validation(
        self,
        proposal: Proposal,
        data: pd.DataFrame
    ) -> Tuple[bool, Dict[str, float]]:
        """Walk Forward验证"""
        metrics = {
            "wf_avg_sharpe": 1.1 + np.random.normal(0, 0.35),
            "wf_stability": 0.8 + np.random.normal(0, 0.15)
        }
        passed = metrics["wf_avg_sharpe"] > 0.7
        return passed, metrics
    
    def _check_risk(
        self,
        proposal: Proposal,
        data: pd.DataFrame
    ) -> Tuple[bool, List[str]]:
        """风险检查"""
        issues = []
        
        if proposal.confidence.risk_level > 0.6:
            issues.append("风险等级过高")
        
        return len(issues) == 0, issues


class ProposalManager:
    """
    提案管理系统
    
    核心流程：
    1. LLM生成Proposal
    2. Validation验证
    3. Approval审批
    4. （可选）人工审批
    5. （如果通过）Runtime执行（仅用于paper）
    """
    
    def __init__(
        self,
        validator: ProposalValidator,
        safety_constraints: SafetyConstraints
    ):
        self.validator = validator
        self.safety = safety_constraints
        self.proposals: Dict[str, Proposal] = {}
        self.pending_proposals: List[Proposal] = []
        self.approved_proposals: List[Proposal] = []
    
    def submit_proposal(
        self,
        proposal: Proposal
    ) -> str:
        """提交提案"""
        self.proposals[proposal.proposal_id] = proposal
        self.pending_proposals.append(proposal)
        print(f"✅ 提案 {proposal.proposal_id} 已提交: {proposal.title}")
        return proposal.proposal_id
    
    def validate_proposal(
        self,
        proposal_id: str,
        historical_data: pd.DataFrame,
        current_weights: Dict[str, float]
    ) -> Optional[ValidationResult]:
        """验证提案"""
        if proposal_id not in self.proposals:
            print(f"❌ 提案 {proposal_id} 不存在")
            return None
        
        proposal = self.proposals[proposal_id]
        proposal.status = ProposalStatus.VALIDATING
        
        result = self.validator.validate_proposal(proposal, historical_data, current_weights)
        
        # 更新提案
        proposal.validation_results = {
            "passed": result.passed,
            "metrics": result.metrics,
            "issues": result.issues_found
        }
        
        if result.passed:
            if proposal.approval_level == ApprovalLevel.FULL_AUTO:
                proposal.status = ProposalStatus.APPROVED
                proposal.approved = True
                self.approved_proposals.append(proposal)
                print(f"✅ 提案 {proposal_id} 自动批准")
            else:
                print(f"⏳ 提案 {proposal_id} 验证通过，等待审批")
        else:
            proposal.status = ProposalStatus.REJECTED
            proposal.approved = False
            print(f"❌ 提案 {proposal_id} 验证失败: {result.issues_found}")
        
        return result
    
    def approve_proposal(
        self,
        proposal_id: str,
        approved_by: str
    ) -> bool:
        """人工批准提案"""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        
        if proposal.status == ProposalStatus.VALIDATING:
            return False
        
        proposal.approved = True
        proposal.approved_by = approved_by
        proposal.approved_at = datetime.now()
        proposal.status = ProposalStatus.APPROVED
        self.approved_proposals.append(proposal)
        
        print(f"✅ 提案 {proposal_id} 已由 {approved_by} 批准")
        return True
    
    def get_implemented_proposals(
        self,
        limit: int = 10
    ) -> List[Proposal]:
        """获取已实施的提案"""
        return [p for p in self.approved_proposals if p.status == ProposalStatus.IMPLEMENTED][:limit]


def create_llm_proposal(
    proposal_type: ProposalType,
    title: str,
    description: str,
    changes: Dict[str, Any],
    confidence_score: float = 0.7
) -> Proposal:
    """
    模拟LLM生成提案
    
    实际使用时应该调用LLM API
    """
    confidence = ConfidenceScore(
        overall=confidence_score,
        data_support=0.6 + np.random.normal(0, 0.15),
        logical_coherence=0.75 + np.random.normal(0, 0.1),
        risk_level=0.3 + np.random.normal(0, 0.15),
        reasoning="基于历史数据和市场分析"
    )
    
    return Proposal(
        proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
        proposal_type=proposal_type,
        title=title,
        description=description,
        confidence=confidence,
        changes=changes,
        validation_requirements=["backtest", "walk_forward", "risk_check"],
        risk_assessment={"max_drawdown_risk": 0.12, "volatility_risk": 0.18},
        proposed_by="AI_Researcher",
        proposed_at=datetime.now(),
        approval_level=ApprovalLevel.SEMI_AUTO
    )


# 示例使用
if __name__ == "__main__":
    print("="*80)
    print("  AI-assisted Research Framework - 示例")
    print("="*80)
    
    # 1. 初始化系统
    print("\n[1/5] 初始化系统...")
    safety = SafetyConstraints()
    validator = ProposalValidator(safety)
    manager = ProposalManager(validator, safety)
    
    # 2. 模拟数据
    print("[2/5] 准备数据...")
    dates = pd.date_range(end=datetime.now(), periods=1000, freq="1H")
    data = pd.DataFrame({
        "close": 50000 * (1 + np.random.normal(0, 0.02, 1000)).cumprod(),
        "volume": np.random.lognormal(10, 0.5, 1000)
    }, index=dates)
    
    # 3. 当前权重
    current_weights = {
        "momentum": 0.3,
        "funding": 0.25,
        "oi": 0.2,
        "volatility": 0.15,
        "mean_reversion": 0.1
    }
    
    # 4. LLM生成提案
    print("\n[3/5] LLM生成提案...")
    proposal = create_llm_proposal(
        proposal_type=ProposalType.FACTOR_WEIGHT,
        title="调整momentum权重以应对趋势市场",
        description="根据当前市场状态，建议提高momentum权重，降低mean_reversion权重",
        changes={
            "new_weights": {
                "momentum": 0.38,
                "funding": 0.25,
                "oi": 0.2,
                "volatility": 0.1,
                "mean_reversion": 0.07
            }
        },
        confidence_score=0.72
    )
    print(f"    提案ID: {proposal.proposal_id}")
    print(f"    置信度: {proposal.confidence.overall:.2f}")
    print(f"    风险等级: {proposal.confidence.risk_level:.2f}")
    
    # 5. 提交提案
    print("\n[4/5] 提交提案...")
    manager.submit_proposal(proposal)
    
    # 6. 验证提案
    print("\n[5/5] 验证提案...")
    result = manager.validate_proposal(proposal.proposal_id, data, current_weights)
    
    print("\n" + "="*80)
    print("  框架说明")
    print("="*80)
    print("""
    架构分层：
    
    LLM层
      ↓（生成Proposal）
    Proposal层
      ↓（验证）
    Validation层
      ↓（检查安全约束）
    Approval层
      ↓（人工/自动审批）
    Runtime层（仅Paper）
    
    关键设计原则：
    
    1. LLM只做研究，绝不直接控制执行
    2. 所有提案必须经过验证
    3. 安全约束是硬限制
    4. 置信度低于阈值的提案自动拒绝
    5. 高风险变更必须人工审批
    """)

