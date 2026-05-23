
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from research.protocol.core import Timepoint, SCHEMA_VERSION


class ExecutionMode(Enum):
    BACKTEST = "backtest"
    REPLAY = "replay"
    LIVE = "live"
    PAPER = "paper"


@dataclass(frozen=True)
class TimeRange:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def contains(self, ts_ms: int) -> bool:
        return self.start_ms <= ts_ms < self.end_ms

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start_ms < other.end_ms and other.start_ms < self.end_ms

    def to_dict(self) -> Dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms}


@dataclass(frozen=True)
class RegimeFilter:
    regimes: tuple
    min_regime_duration_ms: int = 86400000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regimes": list(self.regimes),
            "min_regime_duration_ms": self.min_regime_duration_ms,
        }


@dataclass(frozen=True)
class ExecutionModels:
    slippage_bps: float = 1.0
    taker_fee_bps: float = 0.1
    maker_fee_bps: float = 0.1
    funding_rate: float = 0.0001
    latency_mean_ms: float = 50.0
    latency_std_ms: float = 20.0
    liquidation_impact_scalar: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slippage_bps": self.slippage_bps,
            "taker_fee_bps": self.taker_fee_bps,
            "maker_fee_bps": self.maker_fee_bps,
            "funding_rate": self.funding_rate,
            "latency_mean_ms": self.latency_mean_ms,
            "latency_std_ms": self.latency_std_ms,
            "liquidation_impact_scalar": self.liquidation_impact_scalar,
        }


@dataclass(frozen=True)
class ResearchContext:
    """
    量化研究执行上下文 —— 所有研究模块共享的「只读契约」
    
    铁律：
    1. frozen=True，不可变
    2. 所有字段都有默认值
    3. Future replay/ML/optimization/distributed compute 都依赖它
    
    使用场景：
    - WalkForwardEngine
    - StabilityAnalyzer  
    - (Future) RegimeEngine
    - (Future) MLTraining
    - (Future) DistributedCompute
    """
    dataset_id: str
    
    symbol: str
    timeframe: str
    
    train_range: TimeRange
    test_range: TimeRange
    
    feature_schema_hash: str
    label_schema_hash: str
    build_commit: str
    
    regime_filter: Optional[RegimeFilter] = None
    
    execution_models: ExecutionModels = field(default_factory=ExecutionModels)
    
    mode: ExecutionMode = ExecutionMode.BACKTEST
    
    random_seed: int = 42
    
    metadata: tuple = field(default_factory=tuple)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "train_range": self.train_range.to_dict(),
            "test_range": self.test_range.to_dict(),
            "feature_schema_hash": self.feature_schema_hash,
            "label_schema_hash": self.label_schema_hash,
            "build_commit": self.build_commit,
            "regime_filter": self.regime_filter.to_dict() if self.regime_filter else None,
            "execution_models": self.execution_models.to_dict(),
            "mode": self.mode.value,
            "random_seed": self.random_seed,
            "metadata": list(self.metadata),
        }


@dataclass(frozen=True)
class WindowSpec:
    """
    研究窗口规格
    """
    name: str
    train_range: TimeRange
    test_range: TimeRange
    
    purge_gap_ms: int = 0
    embargo_ms: int = 0
    
    window_index: int = 0
    
    metadata: tuple = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "train_range": self.train_range.to_dict(),
            "test_range": self.test_range.to_dict(),
            "purge_gap_ms": self.purge_gap_ms,
            "embargo_ms": self.embargo_ms,
            "window_index": self.window_index,
            "metadata": list(self.metadata),
        }


@dataclass(frozen=True)
class WindowResult:
    """
    单个窗口的执行结果
    """
    window: WindowSpec
    
    sharpe: float
    sortino: float
    win_rate: float
    total_trades: int
    total_pnl: float
    max_drawdown: float
    annual_return: float
    profit_factor: float
    
    feature_decay: float = 0.0
    regime_stability: float = 0.0
    
    errors: tuple = field(default_factory=tuple)
    warnings: tuple = field(default_factory=tuple)
    
    execution_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "window": self.window.to_dict(),
            "metrics": {
                "sharpe": self.sharpe,
                "sortino": self.sortino,
                "win_rate": self.win_rate,
                "total_trades": self.total_trades,
                "total_pnl": self.total_pnl,
                "max_drawdown": self.max_drawdown,
                "annual_return": self.annual_return,
                "profit_factor": self.profit_factor,
                "feature_decay": self.feature_decay,
                "regime_stability": self.regime_stability,
            },
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass(frozen=True)
class WalkForwardReport:
    """
    Walk-Forward 完整报告
    """
    context: ResearchContext
    
    windows: tuple
    
    overall_sharpe_mean: float
    overall_sharpe_std: float
    overall_pnl: float
    overall_trades: int
    
    feature_decay_rate: float
    regime_stability_score: float
    
    best_window_index: int
    worst_window_index: int
    
    execution_time_ms: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context.to_dict(),
            "windows": [w.to_dict() for w in self.windows],
            "overall": {
                "sharpe_mean": self.overall_sharpe_mean,
                "sharpe_std": self.overall_sharpe_std,
                "pnl": self.overall_pnl,
                "trades": self.overall_trades,
                "feature_decay_rate": self.feature_decay_rate,
                "regime_stability_score": self.regime_stability_score,
                "best_window": self.best_window_index,
                "worst_window": self.worst_window_index,
            },
            "execution_time_ms": self.execution_time_ms,
        }
