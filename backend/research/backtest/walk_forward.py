"""
Walk-Forward Engine - 滚动回测引擎

功能：
1. 滚动窗口训练与验证
2. Out-of-sample 测试
3. 在线 Paper Trading 验证
4. Progressive Deployment

这是防止过拟合的关键工具。
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("research.backtest.walkforward")


class WindowStatus(str, Enum):
    """窗口状态"""
    TRAIN = "train"
    VALIDATE = "validate"
    TEST = "test"
    DEPLOYED = "deployed"


@dataclass
class WindowConfig:
    """窗口配置"""
    train_period: timedelta
    validate_period: timedelta
    test_period: timedelta
    
    step_size: timedelta
    
    min_train_periods: int = 1
    min_validate_periods: int = 1
    
    required_sharpe: float = 1.0
    required_ir: float = 0.5
    max_drawdown_threshold: float = 0.2


@dataclass
class WindowResult:
    """窗口结果"""
    window_id: str
    
    train_start: datetime
    train_end: datetime
    validate_start: datetime
    validate_end: datetime
    test_start: datetime
    test_end: datetime
    
    status: WindowStatus
    
    train_metrics: Dict[str, float]
    validate_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    
    sharpe: float
    ir: float
    max_drawdown: float
    
    in_sample_score: float
    out_of_sample_score: float
    
    slippage: float = 0.0
    fees: float = 0.0
    
    deployed: bool = False
    deployment_score: float = 0.0
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validate_start": self.validate_start.isoformat(),
            "validate_end": self.validate_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "status": self.status.value,
            "train_metrics": self.train_metrics,
            "validate_metrics": self.validate_metrics,
            "test_metrics": self.test_metrics,
            "sharpe": self.sharpe,
            "ir": self.ir,
            "max_drawdown": self.max_drawdown,
            "in_sample_score": self.in_sample_score,
            "out_of_sample_score": self.out_of_sample_score,
            "deployed": self.deployed,
            "deployment_score": self.deployment_score,
            "metadata": self.metadata,
        }


@dataclass
class WalkForwardReport:
    """滚动回测报告"""
    report_id: str
    
    start_date: datetime
    end_date: datetime
    
    total_windows: int
    passed_windows: int
    failed_windows: int
    
    deployed_count: int
    
    average_sharpe: float
    average_ir: float
    average_oos_score: float
    
    consistency_score: float
    
    windows: List[WindowResult]
    
    best_window: Optional[WindowResult] = None
    worst_window: Optional[WindowResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_windows": self.total_windows,
            "passed_windows": self.passed_windows,
            "failed_windows": self.failed_windows,
            "deployed_count": self.deployed_count,
            "average_sharpe": self.average_sharpe,
            "average_ir": self.average_ir,
            "average_oos_score": self.average_oos_score,
            "consistency_score": self.consistency_score,
            "best_window": self.best_window.to_dict() if self.best_window else None,
            "worst_window": self.worst_window.to_dict() if self.worst_window else None,
        }


class WalkForwardEngine:
    """滚动回测引擎
    
    提供完整的 walk-forward 分析能力
    """
    
    def __init__(self, config: Optional[WindowConfig] = None):
        self.config = config or WindowConfig(
            train_period=timedelta(days=90),
            validate_period=timedelta(days=30),
            test_period=timedelta(days=30),
            step_size=timedelta(days=7),
        )
        
        self._windows: List[WindowResult] = []
        self._current_window: Optional[WindowResult] = None
    
    async def run_walk_forward(
        self,
        start_date: datetime,
        end_date: datetime,
        train_function: Callable[[datetime, datetime], Dict[str, float]],
        validate_function: Callable[[datetime, datetime], Dict[str, float]],
        test_function: Callable[[datetime, datetime], Dict[str, float]],
        deploy_function: Optional[Callable[[WindowResult], bool]] = None,
    ) -> WalkForwardReport:
        """运行滚动回测"""
        windows = []
        
        current_date = start_date + self.config.train_period
        
        while current_date + self.config.validate_period + self.config.test_period <= end_date:
            train_start = current_date - self.config.train_period
            train_end = current_date
            
            validate_start = current_date
            validate_end = current_date + self.config.validate_period
            
            test_start = validate_end
            test_end = test_start + self.config.test_period
            
            logger.info(f"Processing window: train={train_start.date()} to {train_end.date()}")
            
            try:
                train_metrics = await self._safe_execute(
                    train_function, train_start, train_end
                )
                
                validate_metrics = await self._safe_execute(
                    validate_function, validate_start, validate_end
                )
                
                test_metrics = await self._safe_execute(
                    test_function, test_start, test_end
                )
                
                window = await self._create_window(
                    train_start, train_end,
                    validate_start, validate_end,
                    test_start, test_end,
                    train_metrics, validate_metrics, test_metrics,
                )
                
                if deploy_function and self._should_deploy(window):
                    deployed = await self._safe_deploy(deploy_function, window)
                    if deployed:
                        window.deployed = True
                        window.deployment_score = self._compute_deployment_score(window)
                
                windows.append(window)
                
            except Exception as e:
                logger.error(f"Window processing failed: {e}")
            
            current_date += self.config.step_size
        
        report = self._generate_report(start_date, end_date, windows)
        
        logger.info(
            f"Walk-forward complete: {len(windows)} windows, "
            f"{sum(1 for w in windows if w.deployed)} deployed"
        )
        
        return report
    
    async def run_expanding_window(
        self,
        start_date: datetime,
        end_date: datetime,
        train_function: Callable[[datetime, datetime], Dict[str, float]],
        test_function: Callable[[datetime, datetime], Dict[str, float]],
    ) -> WalkForwardReport:
        """运行扩展窗口回测"""
        windows = []
        
        current_date = start_date + self.config.train_period
        
        while current_date + self.config.test_period <= end_date:
            train_start = start_date
            train_end = current_date
            
            test_start = current_date
            test_end = current_date + self.config.test_period
            
            logger.info(f"Processing expanding window: train={train_start.date()} to {train_end.date()}")
            
            try:
                train_metrics = await self._safe_execute(
                    train_function, train_start, train_end
                )
                
                test_metrics = await self._safe_execute(
                    test_function, test_start, test_end
                )
                
                window = await self._create_window(
                    train_start, train_end,
                    test_start, test_start,
                    test_start, test_end,
                    train_metrics,
                    validate_metrics={"placeholder": 0},
                    test_metrics=test_metrics,
                )
                
                windows.append(window)
                
            except Exception as e:
                logger.error(f"Window processing failed: {e}")
            
            current_date += self.config.step_size
        
        report = self._generate_report(start_date, end_date, windows)
        return report
    
    async def validate_online(
        self,
        strategy_id: str,
        period: timedelta,
        paper_trade_function: Callable[[], Dict[str, float]],
    ) -> Dict[str, Any]:
        """在线 Paper Trading 验证"""
        start_time = datetime.utcnow()
        end_time = start_time + period
        
        logger.info(f"Starting online validation for {strategy_id}")
        
        results = []
        
        while datetime.utcnow() < end_time:
            try:
                result = await paper_trade_function()
                results.append({
                    "timestamp": datetime.utcnow(),
                    "result": result,
                })
                
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Online validation error: {e}")
        
        avg_metrics = self._aggregate_results(results)
        
        return {
            "strategy_id": strategy_id,
            "start_time": start_time.isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "period": str(period),
            "samples": len(results),
            "average_metrics": avg_metrics,
            "passed": self._check_online_validation(avg_metrics),
        }
    
    def get_windows(self) -> List[WindowResult]:
        """获取所有窗口"""
        return self._windows.copy()
    
    def get_latest_window(self) -> Optional[WindowResult]:
        """获取最新窗口"""
        return self._windows[-1] if self._windows else None
    
    def get_deployed_windows(self) -> List[WindowResult]:
        """获取已部署窗口"""
        return [w for w in self._windows if w.deployed]
    
    async def _create_window(
        self,
        train_start: datetime,
        train_end: datetime,
        validate_start: datetime,
        validate_end: datetime,
        test_start: datetime,
        test_end: datetime,
        train_metrics: Dict[str, float],
        validate_metrics: Dict[str, float],
        test_metrics: Dict[str, float],
    ) -> WindowResult:
        """创建窗口结果"""
        sharpe = test_metrics.get("sharpe", 0)
        ir = test_metrics.get("ir", 0)
        max_drawdown = test_metrics.get("max_drawdown", 0)
        
        in_sample_score = self._compute_in_sample_score(train_metrics)
        out_of_sample_score = self._compute_oos_score(test_metrics)
        
        passed = self._check_window_passed(train_metrics, validate_metrics, test_metrics)
        
        window = WindowResult(
            window_id=f"wf_{uuid.uuid4().hex[:12]}",
            train_start=train_start,
            train_end=train_end,
            validate_start=validate_start,
            validate_end=validate_end,
            test_start=test_start,
            test_end=test_end,
            status=WindowStatus.DEPLOYED if passed else WindowStatus.TEST,
            train_metrics=train_metrics,
            validate_metrics=validate_metrics,
            test_metrics=test_metrics,
            sharpe=sharpe,
            ir=ir,
            max_drawdown=max_drawdown,
            in_sample_score=in_sample_score,
            out_of_sample_score=out_of_sample_score,
        )
        
        self._windows.append(window)
        self._current_window = window
        
        return window
    
    def _should_deploy(self, window: WindowResult) -> bool:
        """判断是否应该部署"""
        if window.sharpe < self.config.required_sharpe:
            return False
        
        if window.ir < self.config.required_ir:
            return False
        
        if window.max_drawdown > self.config.max_drawdown_threshold:
            return False
        
        consistency = self._check_consistency()
        if consistency < 0.5:
            return False
        
        return True
    
    def _check_window_passed(
        self,
        train_metrics: Dict[str, float],
        validate_metrics: Dict[str, float],
        test_metrics: Dict[str, float],
    ) -> bool:
        """检查窗口是否通过"""
        sharpe = test_metrics.get("sharpe", 0)
        ir = test_metrics.get("ir", 0)
        max_drawdown = test_metrics.get("max_drawdown", 0)
        
        if sharpe < self.config.required_sharpe:
            return False
        
        if ir < self.config.required_ir:
            return False
        
        if max_drawdown > self.config.max_drawdown_threshold:
            return False
        
        return True
    
    def _compute_in_sample_score(self, metrics: Dict[str, float]) -> float:
        """计算样本内评分"""
        sharpe = metrics.get("sharpe", 0)
        win_rate = metrics.get("win_rate", 0.5)
        
        return sharpe * 0.7 + win_rate * 0.3
    
    def _compute_oos_score(self, metrics: Dict[str, float]) -> float:
        """计算样本外评分"""
        sharpe = metrics.get("sharpe", 0)
        max_drawdown = metrics.get("max_drawdown", 0)
        
        drawdown_penalty = max(0, max_drawdown - 0.1) * 5
        
        return sharpe - drawdown_penalty
    
    def _compute_deployment_score(self, window: WindowResult) -> float:
        """计算部署评分"""
        sharpe_weight = 0.3
        ir_weight = 0.3
        oos_weight = 0.2
        consistency_weight = 0.2
        
        sharpe_score = min(window.sharpe / 2.0, 1.0)
        ir_score = min(window.ir / 1.0, 1.0)
        oos_score = min(max(window.out_of_sample_score, 0), 1.0)
        consistency_score = self._check_consistency()
        
        return (
            sharpe_weight * sharpe_score +
            ir_weight * ir_score +
            oos_weight * oos_score +
            consistency_weight * consistency_score
        )
    
    def _check_consistency(self) -> float:
        """检查一致性"""
        if len(self._windows) < 2:
            return 1.0
        
        sharpes = [w.sharpe for w in self._windows[-5:]]
        
        sharpe_std = np.std(sharpes)
        sharpe_mean = np.mean(sharpes)
        
        if sharpe_mean == 0:
            return 0.0
        
        cv = sharpe_std / sharpe_mean
        
        return max(0, 1.0 - cv)
    
    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """聚合结果"""
        if not results:
            return {}
        
        metrics_list = [r["result"] for r in results]
        
        aggregated = {}
        for key in metrics_list[0].keys():
            values = [m.get(key, 0) for m in metrics_list]
            aggregated[key] = float(np.mean(values))
        
        return aggregated
    
    def _check_online_validation(self, metrics: Dict[str, float]) -> bool:
        """检查在线验证是否通过"""
        sharpe = metrics.get("sharpe", 0)
        max_drawdown = metrics.get("max_drawdown", 0)
        
        return sharpe > 0.5 and max_drawdown < 0.15
    
    async def _safe_execute(
        self,
        func: Callable,
        *args,
    ) -> Dict[str, float]:
        """安全执行"""
        try:
            result = func(*args)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "sharpe": 0,
                "ir": 0,
                "max_drawdown": 0,
                "returns": 0,
                "win_rate": 0,
            }
    
    async def _safe_deploy(
        self,
        func: Callable,
        window: WindowResult,
    ) -> bool:
        """安全部署"""
        try:
            result = func(window)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False
    
    def _generate_report(
        self,
        start_date: datetime,
        end_date: datetime,
        windows: List[WindowResult],
    ) -> WalkForwardReport:
        """生成报告"""
        if not windows:
            return WalkForwardReport(
                report_id=f"wf_report_{uuid.uuid4().hex[:12]}",
                start_date=start_date,
                end_date=end_date,
                total_windows=0,
                passed_windows=0,
                failed_windows=0,
                deployed_count=0,
                average_sharpe=0,
                average_ir=0,
                average_oos_score=0,
                consistency_score=0,
                windows=[],
            )
        
        sharpes = [w.sharpe for w in windows]
        irs = [w.ir for w in windows]
        oos_scores = [w.out_of_sample_score for w in windows]
        
        deployed_count = sum(1 for w in windows if w.deployed)
        
        best_window = max(windows, key=lambda w: w.out_of_sample_score)
        worst_window = min(windows, key=lambda w: w.out_of_sample_score)
        
        return WalkForwardReport(
            report_id=f"wf_report_{uuid.uuid4().hex[:12]}",
            start_date=start_date,
            end_date=end_date,
            total_windows=len(windows),
            passed_windows=sum(1 for w in windows if w.status == WindowStatus.DEPLOYED),
            failed_windows=len(windows) - sum(1 for w in windows if w.status == WindowStatus.DEPLOYED),
            deployed_count=deployed_count,
            average_sharpe=float(np.mean(sharpes)),
            average_ir=float(np.mean(irs)),
            average_oos_score=float(np.mean(oos_scores)),
            consistency_score=self._check_consistency(),
            windows=windows,
            best_window=best_window,
            worst_window=worst_window,
        )


_walk_forward_engine: Optional[WalkForwardEngine] = None


def get_walk_forward_engine(config: Optional[WindowConfig] = None) -> WalkForwardEngine:
    """获取滚动回测引擎实例"""
    global _walk_forward_engine
    if _walk_forward_engine is None:
        _walk_forward_engine = WalkForwardEngine(config)
    return _walk_forward_engine
