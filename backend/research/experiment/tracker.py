"""
Experiment Tracker - 实验追踪系统

功能：
1. 实验参数追踪
2. 实验结果对比
3. 超参数优化
4. 实验可视化

这是 Alpha 研究的核心工具。
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("research.experiment.tracker")


class ExperimentStatus(str, Enum):
    """实验状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentType(str, Enum):
    """实验类型"""
    BACKTEST = "backtest"
    WALK_FORWARD = "walk_forward"
    HYPERPARAMETER = "hyperparameter"
    FEATURE_IMPORTANCE = "feature_importance"
    REGIME_ANALYSIS = "regime_analysis"


@dataclass
class ExperimentConfig:
    """实验配置"""
    experiment_id: str
    name: str
    experiment_type: ExperimentType
    
    strategy_id: Optional[str] = None
    factor_ids: List[str] = field(default_factory=list)
    
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def compute_hash(self) -> str:
        data = {
            "name": self.name,
            "experiment_type": self.experiment_type.value,
            "parameters": self.parameters,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class ExperimentResult:
    """实验结果"""
    experiment_id: str
    
    status: ExperimentStatus
    
    metrics: Dict[str, float]
    
    returns: List[float] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    error_message: Optional[str] = None
    
    artifacts: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "status": self.status.value,
            "metrics": self.metrics,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


@dataclass
class HyperparameterTrial:
    """超参数试验"""
    trial_id: str
    experiment_id: str
    
    parameters: Dict[str, Any]
    
    objective_value: float
    
    metrics: Dict[str, float]
    
    status: ExperimentStatus
    
    trial_number: int
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "experiment_id": self.experiment_id,
            "parameters": self.parameters,
            "objective_value": self.objective_value,
            "metrics": self.metrics,
            "status": self.status.value,
            "trial_number": self.trial_number,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ExperimentTracker:
    """实验追踪器
    
    管理实验的创建、运行、结果追踪和对比
    """
    
    def __init__(self):
        self._experiments: Dict[str, ExperimentConfig] = {}
        self._results: Dict[str, ExperimentResult] = {}
        self._trials: Dict[str, List[HyperparameterTrial]] = {}
        
        self._experiment_runs: Dict[str, List[Callable]] = {}
    
    def create_experiment(
        self,
        name: str,
        experiment_type: ExperimentType,
        strategy_id: Optional[str] = None,
        factor_ids: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExperimentConfig:
        """创建实验"""
        experiment_id = f"exp_{uuid.uuid4().hex[:12]}"
        
        config = ExperimentConfig(
            experiment_id=experiment_id,
            name=name,
            experiment_type=experiment_type,
            strategy_id=strategy_id,
            factor_ids=factor_ids or [],
            parameters=parameters or {},
            tags=tags or [],
            metadata=metadata or {},
        )
        
        self._experiments[experiment_id] = config
        
        result = ExperimentResult(
            experiment_id=experiment_id,
            status=ExperimentStatus.PENDING,
            metrics={},
        )
        self._results[experiment_id] = result
        
        logger.info(f"Experiment created: {experiment_id} ({name})")
        return config
    
    def register_run(
        self,
        experiment_id: str,
        run_function: Callable[[ExperimentConfig], ExperimentResult],
    ) -> None:
        """注册实验运行函数"""
        if experiment_id not in self._experiment_runs:
            self._experiment_runs[experiment_id] = []
        self._experiment_runs[experiment_id].append(run_function)
    
    async def run_experiment(
        self,
        experiment_id: str,
        run_function: Optional[Callable[[ExperimentConfig], ExperimentResult]] = None,
    ) -> ExperimentResult:
        """运行实验"""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        config = self._experiments[experiment_id]
        result = self._results[experiment_id]
        
        result.status = ExperimentStatus.RUNNING
        result.started_at = datetime.utcnow()
        
        logger.info(f"Running experiment: {experiment_id}")
        
        try:
            func = run_function or self._experiment_runs.get(experiment_id, [None])[0]
            
            if func is None:
                raise ValueError("No run function registered")
            
            experiment_result = func(config)
            
            if asyncio.iscoroutine(experiment_result):
                experiment_result = await experiment_result
            
            result = experiment_result
            result.experiment_id = experiment_id
            result.status = ExperimentStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            
            self._results[experiment_id] = result
            
            logger.info(
                f"Experiment completed: {experiment_id} "
                f"(Sharpe={result.sharpe:.2f}, DD={result.max_drawdown:.2%})"
            )
            
        except Exception as e:
            result.status = ExperimentStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.utcnow()
            
            logger.error(f"Experiment failed: {experiment_id} - {e}")
        
        return result
    
    def create_hyperparameter_experiment(
        self,
        name: str,
        parameter_space: Dict[str, List[Any]],
        objective_metric: str = "sharpe",
        max_trials: int = 100,
    ) -> ExperimentConfig:
        """创建超参数优化实验"""
        experiment_id = f"hpo_{uuid.uuid4().hex[:12]}"
        
        config = ExperimentConfig(
            experiment_id=experiment_id,
            name=name,
            experiment_type=ExperimentType.HYPERPARAMETER,
            parameters={
                "parameter_space": parameter_space,
                "objective_metric": objective_metric,
                "max_trials": max_trials,
            },
        )
        
        self._experiments[experiment_id] = config
        self._trials[experiment_id] = []
        
        logger.info(f"Hyperparameter experiment created: {experiment_id}")
        return config
    
    async def run_hyperparameter_search(
        self,
        experiment_id: str,
        objective_function: Callable[[Dict[str, Any]], Dict[str, float]],
    ) -> List[HyperparameterTrial]:
        """运行超参数搜索"""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        config = self._experiments[experiment_id]
        param_space = config.parameters.get("parameter_space", {})
        max_trials = config.parameters.get("max_trials", 100)
        
        trials = []
        
        for trial_num in range(max_trials):
            parameters = {
                key: np.random.choice(values)
                for key, values in param_space.items()
            }
            
            trial_id = f"trial_{uuid.uuid4().hex[:12]}"
            
            trial = HyperparameterTrial(
                trial_id=trial_id,
                experiment_id=experiment_id,
                parameters=parameters,
                objective_value=0.0,
                metrics={},
                status=ExperimentStatus.RUNNING,
                trial_number=trial_num,
            )
            
            try:
                metrics = objective_function(parameters)
                objective_metric = config.parameters.get("objective_metric", "sharpe")
                objective_value = metrics.get(objective_metric, 0.0)
                
                trial.objective_value = objective_value
                trial.metrics = metrics
                trial.status = ExperimentStatus.COMPLETED
                
            except Exception as e:
                trial.status = ExperimentStatus.FAILED
                logger.error(f"Trial {trial_num} failed: {e}")
            
            trial.completed_at = datetime.utcnow()
            trials.append(trial)
            self._trials[experiment_id].append(trial)
            
            logger.debug(f"Trial {trial_num}: objective={trial.objective_value:.4f}")
        
        best_trial = max(trials, key=lambda t: t.objective_value)
        logger.info(
            f"Hyperparameter search completed: {experiment_id} "
            f"(best trial: {best_trial.trial_id}, value={best_trial.objective_value:.4f})"
        )
        
        return trials
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """获取实验"""
        return self._experiments.get(experiment_id)
    
    def get_result(self, experiment_id: str) -> Optional[ExperimentResult]:
        """获取实验结果"""
        return self._results.get(experiment_id)
    
    def get_all_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
        experiment_type: Optional[ExperimentType] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ExperimentConfig]:
        """获取所有实验"""
        results = []
        
        for config in self._experiments.values():
            if status and self._results.get(config.experiment_id, ExperimentResult("", ExperimentStatus.PENDING)).status != status:
                continue
            
            if experiment_type and config.experiment_type != experiment_type:
                continue
            
            if tags and not any(t in config.tags for t in tags):
                continue
            
            results.append(config)
        
        return sorted(results, key=lambda c: c.created_at, reverse=True)
    
    def compare_experiments(
        self,
        experiment_ids: List[str],
    ) -> Dict[str, Any]:
        """对比实验"""
        results = []
        
        for exp_id in experiment_ids:
            result = self._results.get(exp_id)
            config = self._experiments.get(exp_id)
            
            if result and config:
                results.append({
                    "experiment_id": exp_id,
                    "name": config.name,
                    "status": result.status.value,
                    "sharpe": result.sharpe,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "profit_factor": result.profit_factor,
                    "total_trades": result.total_trades,
                    "created_at": config.created_at.isoformat(),
                })
        
        if not results:
            return {"experiments": [], "best": None}
        
        sorted_results = sorted(results, key=lambda x: x["sharpe"], reverse=True)
        
        return {
            "experiments": sorted_results,
            "best": sorted_results[0] if sorted_results else None,
        }
    
    def get_best_parameters(
        self,
        experiment_id: str,
        top_n: int = 10,
    ) -> List[HyperparameterTrial]:
        """获取最佳参数"""
        trials = self._trials.get(experiment_id, [])
        completed_trials = [t for t in trials if t.status == ExperimentStatus.COMPLETED]
        
        return sorted(
            completed_trials,
            key=lambda t: t.objective_value,
            reverse=True,
        )[:top_n]
    
    def get_experiment_history(
        self,
        experiment_id: str,
    ) -> List[ExperimentResult]:
        """获取实验历史"""
        result = self._results.get(experiment_id)
        if result:
            return [result]
        return []
    
    def delete_experiment(self, experiment_id: str) -> bool:
        """删除实验"""
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
        
        if experiment_id in self._results:
            del self._results[experiment_id]
        
        if experiment_id in self._trials:
            del self._trials[experiment_id]
        
        if experiment_id in self._experiment_runs:
            del self._experiment_runs[experiment_id]
        
        logger.info(f"Experiment deleted: {experiment_id}")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._experiments)
        completed = sum(1 for r in self._results.values() if r.status == ExperimentStatus.COMPLETED)
        failed = sum(1 for r in self._results.values() if r.status == ExperimentStatus.FAILED)
        
        by_type = {}
        for config in self._experiments.values():
            type_name = config.experiment_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        total_trials = sum(len(trials) for trials in self._trials.values())
        
        return {
            "total_experiments": total,
            "completed": completed,
            "failed": failed,
            "running": total - completed - failed,
            "by_type": by_type,
            "total_trials": total_trials,
        }


_tracker: Optional[ExperimentTracker] = None


def get_experiment_tracker() -> ExperimentTracker:
    """获取实验追踪器实例"""
    global _tracker
    if _tracker is None:
        _tracker = ExperimentTracker()
    return _tracker
