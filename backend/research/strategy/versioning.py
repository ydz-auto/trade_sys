"""
Strategy Versioning & Alpha Pipeline - 策略版本管理与 Alpha 生产流水线

功能：
1. 策略版本管理
2. Alpha Pipeline 完整闭环
3. 自动部署与下线
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger

logger = get_logger("research.strategy.versioning")


class DeploymentStatus(str, Enum):
    """部署状态"""
    PENDING = "pending"
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE = "live"
    STOPPED = "stopped"


@dataclass
class StrategyVersion:
    """策略版本"""
    version_id: str
    strategy_id: str
    
    version: str
    name: str
    
    factors: List[str]
    parameters: Dict[str, Any]
    
    sharpe: float
    ir: float
    max_drawdown: float
    
    created_at: datetime
    
    status: str
    tags: List[str] = field(default_factory=list)
    
    source_code_hash: Optional[str] = None
    parent_version_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "name": self.name,
            "factors": self.factors,
            "parameters": self.parameters,
            "sharpe": self.sharpe,
            "ir": self.ir,
            "max_drawdown": self.max_drawdown,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "tags": self.tags,
        }


@dataclass
class AlphaDeployment:
    """Alpha 部署"""
    deployment_id: str
    strategy_id: str
    version_id: str
    status: DeploymentStatus
    capital_allocation: float
    started_at: datetime
    current_pnl: float = 0.0
    stopped_at: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    auto_stop_conditions: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "version_id": self.version_id,
            "status": self.status.value,
            "capital_allocation": self.capital_allocation,
            "current_pnl": self.current_pnl,
            "started_at": self.started_at.isoformat(),
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "metrics": self.metrics,
        }


class AlphaPipeline:
    """Alpha 生产流水线
    
    完整的 Alpha 生命周期管理：
    Research → Validation → Backtest → Paper → Live → Monitor → Retire
    """
    
    def __init__(self):
        self._strategy_versions: Dict[str, List[StrategyVersion]] = {}
        self._deployments: Dict[str, AlphaDeployment] = {}
        self._current_deployments: List[AlphaDeployment] = []
        
        self._auto_stop_enabled = True
        self._monitoring_interval = 60
    
    def register_strategy_version(
        self,
        strategy_id: str,
        name: str,
        factors: List[str],
        parameters: Dict[str, Any],
        sharpe: float,
        ir: float,
        max_drawdown: float,
        tags: Optional[List[str]] = None,
        parent_version_id: Optional[str] = None,
    ) -> StrategyVersion:
        """注册策略版本"""
        if strategy_id not in self._strategy_versions:
            self._strategy_versions[strategy_id] = []
        
        version_num = len(self._strategy_versions[strategy_id]) + 1
        version = f"v{version_num}"
        
        version_id = f"{strategy_id}_{version}"
        
        strategy_version = StrategyVersion(
            version_id=version_id,
            strategy_id=strategy_id,
            version=version,
            name=name,
            factors=factors,
            parameters=parameters,
            sharpe=sharpe,
            ir=ir,
            max_drawdown=max_drawdown,
            created_at=datetime.utcnow(),
            status="validated",
            tags=tags or [],
            parent_version_id=parent_version_id,
        )
        
        self._strategy_versions[strategy_id].append(strategy_version)
        
        logger.info(f"Strategy version registered: {version_id}")
        return strategy_version
    
    async def deploy_to_shadow(
        self,
        version_id: str,
        capital_allocation: float = 0.0,
    ) -> AlphaDeployment:
        """部署到 Shadow 模式"""
        strategy_id = version_id.rsplit("_", 1)[0]
        
        deployment = AlphaDeployment(
            deployment_id=f"deploy_{uuid.uuid4().hex[:12]}",
            strategy_id=strategy_id,
            version_id=version_id,
            status=DeploymentStatus.SHADOW,
            capital_allocation=capital_allocation,
            started_at=datetime.utcnow(),
            auto_stop_conditions={
                "max_drawdown": 0.05,
                "min_daily_return": -0.02,
            },
        )
        
        self._deployments[deployment.deployment_id] = deployment
        self._current_deployments.append(deployment)
        
        logger.info(f"Deployed to shadow: {deployment.deployment_id}")
        return deployment
    
    async def promote_to_paper(
        self,
        deployment_id: str,
        capital_allocation: float,
    ) -> bool:
        """升级到 Paper Trading"""
        if deployment_id not in self._deployments:
            return False
        
        deployment = self._deployments[deployment_id]
        
        if deployment.status != DeploymentStatus.SHADOW:
            return False
        
        deployment.status = DeploymentStatus.PAPER
        deployment.capital_allocation = capital_allocation
        
        logger.info(f"Promoted to paper: {deployment_id}")
        return True
    
    async def promote_to_live(
        self,
        deployment_id: str,
        capital_allocation: float,
    ) -> bool:
        """升级到 Live Trading"""
        if deployment_id not in self._deployments:
            return False
        
        deployment = self._deployments[deployment_id]
        
        if deployment.status != DeploymentStatus.PAPER:
            return False
        
        if not self._validate_for_live(deployment):
            logger.warning(f"Deployment {deployment_id} not ready for live")
            return False
        
        deployment.status = DeploymentStatus.LIVE
        deployment.capital_allocation = capital_allocation
        
        logger.info(f"Promoted to live: {deployment_id}")
        return True
    
    async def stop_deployment(
        self,
        deployment_id: str,
        reason: str = "",
    ) -> bool:
        """停止部署"""
        if deployment_id not in self._deployments:
            return False
        
        deployment = self._deployments[deployment_id]
        deployment.status = DeploymentStatus.STOPPED
        deployment.stopped_at = datetime.utcnow()
        
        if deployment in self._current_deployments:
            self._current_deployments.remove(deployment)
        
        logger.info(f"Deployment stopped: {deployment_id} ({reason})")
        return True
    
    async def auto_stop_check(self) -> List[str]:
        """自动停止检查"""
        if not self._auto_stop_enabled:
            return []
        
        stopped = []
        
        for deployment in self._current_deployments:
            if deployment.status not in [DeploymentStatus.PAPER, DeploymentStatus.LIVE]:
                continue
            
            should_stop = False
            reason = ""
            
            conditions = deployment.auto_stop_conditions
            
            if "max_drawdown" in conditions:
                if deployment.metrics.get("max_drawdown", 0) > conditions["max_drawdown"]:
                    should_stop = True
                    reason = f"Max drawdown exceeded: {deployment.metrics.get('max_drawdown', 0):.2%}"
            
            if "min_daily_return" in conditions:
                if deployment.metrics.get("daily_return", 0) < conditions["min_daily_return"]:
                    should_stop = True
                    reason = f"Daily return below threshold: {deployment.metrics.get('daily_return', 0):.2%}"
            
            if should_stop:
                await self.stop_deployment(deployment.deployment_id, reason)
                stopped.append(deployment.deployment_id)
        
        return stopped
    
    def _validate_for_live(self, deployment: AlphaDeployment) -> bool:
        """验证是否可以进入 Live"""
        min_paper_days = 7
        min_paper_trades = 10
        
        paper_duration = datetime.utcnow() - deployment.started_at
        if paper_duration < timedelta(days=min_paper_days):
            return False
        
        if deployment.metrics.get("total_trades", 0) < min_paper_trades:
            return False
        
        required_sharpe = 1.0
        if deployment.metrics.get("sharpe", 0) < required_sharpe:
            return False
        
        return True
    
    def update_metrics(
        self,
        deployment_id: str,
        metrics: Dict[str, float],
    ) -> None:
        """更新指标"""
        if deployment_id in self._deployments:
            self._deployments[deployment_id].metrics.update(metrics)
    
    def get_active_deployments(self) -> List[AlphaDeployment]:
        """获取活跃部署"""
        return [
            d for d in self._current_deployments
            if d.status in [DeploymentStatus.SHADOW, DeploymentStatus.PAPER, DeploymentStatus.LIVE]
        ]
    
    def get_deployment(self, deployment_id: str) -> Optional[AlphaDeployment]:
        """获取部署"""
        return self._deployments.get(deployment_id)
    
    def get_strategy_versions(self, strategy_id: str) -> List[StrategyVersion]:
        """获取策略版本"""
        return self._strategy_versions.get(strategy_id, [])
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计"""
        total = len(self._deployments)
        by_status = {}
        total_pnl = 0.0
        
        for d in self._deployments.values():
            status_name = d.status.value
            by_status[status_name] = by_status.get(status_name, 0) + 1
            total_pnl += d.current_pnl
        
        return {
            "total_deployments": total,
            "active_deployments": len(self.get_active_deployments()),
            "by_status": by_status,
            "total_pnl": total_pnl,
            "total_strategies": len(self._strategy_versions),
        }


_pipeline: Optional[AlphaPipeline] = None


def get_alpha_pipeline() -> AlphaPipeline:
    """获取 Alpha Pipeline 实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = AlphaPipeline()
    return _pipeline
