"""
Optimization Models - 优化数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import json


class OptimizationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationMethod(str, Enum):
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"


class OptimizationMetric(str, Enum):
    SHARPE = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR = "calmar_ratio"


@dataclass
class ParamGrid:
    """参数网格"""
    params: Dict[str, List[Any]]
    
    def get_combinations(self) -> List[Dict[str, Any]]:
        """生成所有参数组合"""
        from itertools import product
        
        param_names = list(self.params.keys())
        param_values = list(self.params.values())
        
        combinations = []
        for combo in product(*param_values):
            combinations.append(dict(zip(param_names, combo)))
        
        return combinations
    
    def to_dict(self) -> Dict[str, Any]:
        return {"params": self.params}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParamGrid":
        return cls(params=data.get("params", {}))


@dataclass
class StrategyConfig:
    """策略配置"""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    direction: str
    
    param_grid: ParamGrid
    default_params: Dict[str, Any] = field(default_factory=dict)
    
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_hold_hours: int = 48
    leverage: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "direction": self.direction,
            "param_grid": self.param_grid.to_dict(),
            "default_params": self.default_params,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_hold_hours": self.max_hold_hours,
            "leverage": self.leverage,
        }


@dataclass
class OptimizationConfig:
    """优化配置"""
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.3
    
    optimization_start: str = "2024-01-01"
    optimization_end: str = "2024-12-31"
    
    backtest_start: Optional[str] = None
    backtest_end: Optional[str] = None
    
    method: OptimizationMethod = OptimizationMethod.GRID_SEARCH
    metric: OptimizationMetric = OptimizationMetric.SHARPE
    
    param_grid: Optional[dict] = None
    n_trials: int = 50
    max_concurrent: int = 3
    use_multiprocess: bool = True
    
    use_runtime: bool = True
    enable_slippage: bool = True
    enable_latency: bool = True
    enable_partial_fill: bool = True
    
    # 策略参数
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_hold_hours: int = 48
    
    # 数据重采样
    resample_freq: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_capital": self.initial_capital,
            "commission": self.commission,
            "slippage": self.slippage,
            "position_size": self.position_size,
            "optimization_start": self.optimization_start,
            "optimization_end": self.optimization_end,
            "backtest_start": self.backtest_start,
            "backtest_end": self.backtest_end,
            "method": self.method.value,
            "metric": self.metric.value,
            "n_trials": self.n_trials,
            "max_concurrent": self.max_concurrent,
            "use_runtime": self.use_runtime,
            "enable_slippage": self.enable_slippage,
            "enable_latency": self.enable_latency,
            "enable_partial_fill": self.enable_partial_fill,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_hold_hours": self.max_hold_hours,
            "resample_freq": self.resample_freq,
        }


@dataclass
class TradeRecord:
    """交易记录"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: str
    quantity: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    slippage: float = 0.0
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "direction": self.direction,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "exit_reason": self.exit_reason,
            "slippage": self.slippage,
            "latency_ms": self.latency_ms,
        }


@dataclass
class OptimizationMetrics:
    """优化指标"""
    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    avg_trade_duration_hours: float = 0.0
    avg_pnl_pct: float = 0.0
    avg_slippage: float = 0.0
    avg_latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "avg_trade_duration_hours": self.avg_trade_duration_hours,
            "avg_pnl_pct": self.avg_pnl_pct,
            "avg_slippage": self.avg_slippage,
            "avg_latency_ms": self.avg_latency_ms,
        }


@dataclass
class OptimizationResult:
    """优化结果"""
    optimization_id: str
    strategy_id: str
    symbol: str
    status: OptimizationStatus
    
    best_params: Optional[Dict[str, Any]] = None
    best_score: Optional[float] = None
    best_metrics: Optional[OptimizationMetrics] = None
    
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[TradeRecord] = field(default_factory=list)
    
    optimization_period: str = ""
    backtest_period: str = ""
    
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    error: Optional[str] = None
    
    runtime_stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "optimization_id": self.optimization_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "status": self.status.value,
            "best_params": self.best_params,
            "best_score": self.best_score,
            "best_metrics": self.best_metrics.to_dict() if self.best_metrics else None,
            "all_results": self.all_results,
            "trades": [t.to_dict() for t in self.trades],
            "optimization_period": self.optimization_period,
            "backtest_period": self.backtest_period,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "runtime_stats": self.runtime_stats,
        }


@dataclass
class OptimizationTask:
    """优化任务"""
    task_id: str
    strategy_config: StrategyConfig
    symbol: str
    config: OptimizationConfig
    
    status: OptimizationStatus = OptimizationStatus.PENDING
    progress: float = 0.0
    current_combo: int = 0
    total_combos: int = 0
    
    result: Optional[OptimizationResult] = None
    
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "strategy_config": self.strategy_config.to_dict(),
            "symbol": self.symbol,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "progress": self.progress,
            "current_combo": self.current_combo,
            "total_combos": self.total_combos,
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
