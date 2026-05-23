
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional, Tuple
import statistics

from infrastructure.logging import get_logger

logger = get_logger("research.stability")


@dataclass
class StabilityRegion:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_param: str
    y_param: str
    mean_sharpe: float = 0.0
    std_sharpe: float = 0.0
    num_samples: int = 0
    max_drawdown: float = 0.0
    win_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "x_param": self.x_param,
            "y_param": self.y_param,
            "mean_sharpe": self.mean_sharpe,
            "std_sharpe": self.std_sharpe,
            "num_samples": self.num_samples,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
        }


@dataclass
class ParameterSweepResult:
    param_name: str
    param_values: List[float]
    metric_values: List[float]
    best_param: float = 0.0
    best_metric: float = 0.0
    mean_metric: float = 0.0
    std_metric: float = 0.0

    @property
    def is_flat(self) -> bool:
        if len(self.metric_values) < 3:
            return False
        threshold = max(0.1, abs(self.mean_metric) * 0.2)
        return self.std_metric < threshold

    def to_dict(self) -> dict:
        return {
            "param_name": self.param_name,
            "param_values": self.param_values,
            "metric_values": self.metric_values,
            "best_param": self.best_param,
            "best_metric": self.best_metric,
            "mean_metric": self.mean_metric,
            "std_metric": self.std_metric,
            "is_flat": self.is_flat,
        }


@dataclass
class RegimePerformance:
    regime: str
    sharpe: float
    win_rate: float
    total_trades: int
    pnl: float
    max_drawdown: float
    avg_holding_hours: float

    def is_profitable(self) -> bool:
        return self.sharpe > 0.5

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "sharpe": self.sharpe,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "pnl": self.pnl,
            "max_drawdown": self.max_drawdown,
            "avg_holding_hours": self.avg_holding_hours,
            "is_profitable": self.is_profitable(),
        }


@dataclass
class CrossRegimeStabilityResult:
    """Cross-Regime Stability 检测结果"""
    regime_performance: Dict[str, RegimePerformance] = field(default_factory=dict)
    sharpe_by_regime: Dict[str, float] = field(default_factory=dict)
    profitable_regimes: List[str] = field(default_factory=list)
    losing_regimes: List[str] = field(default_factory=dict)
    regime_concentration: float = 0.0
    is_regime_diversified: bool = False
    
    @property
    def sharpe_mean(self) -> float:
        vals = list(self.sharpe_by_regime.values())
        return statistics.mean(vals) if vals else 0.0
    
    @property
    def sharpe_std(self) -> float:
        vals = list(self.sharpe_by_regime.values())
        return statistics.stdev(vals) if len(vals) > 1 else 0.0

    def to_dict(self) -> dict:
        return {
            "regime_performance": {k: v.to_dict() for k, v in self.regime_performance.items()},
            "sharpe_by_regime": self.sharpe_by_regime,
            "profitable_regimes": self.profitable_regimes,
            "losing_regimes": self.losing_regimes,
            "regime_concentration": self.regime_concentration,
            "is_regime_diversified": self.is_regime_diversified,
            "sharpe_mean": self.sharpe_mean,
            "sharpe_std": self.sharpe_std,
        }


@dataclass
class StabilityResult:
    stable_regions: List[StabilityRegion] = field(default_factory=list)
    param_sweeps: Dict[str, ParameterSweepResult] = field(default_factory=dict)
    needle_peaks: List[Dict[str, Any]] = field(default_factory=list)
    is_stable: bool = False
    overall_stability_score: float = 0.0
    heatmap_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "stable_regions": [r.to_dict() for r in self.stable_regions],
            "param_sweeps": {k: v.to_dict() for k, v in self.param_sweeps.items()},
            "needle_peaks": self.needle_peaks,
            "is_stable": self.is_stable,
            "overall_stability_score": self.overall_stability_score,
            "heatmap_data": self.heatmap_data,
        }


class StabilityAnalyzer:
    def __init__(self):
        self._results: Dict[str, Any] = {}

    def analyze_1d(
        self,
        param_name: str,
        param_values: List[float],
        metric_fn: Callable[[float], float],
    ) -> ParameterSweepResult:
        metric_values = []

        for value in param_values:
            try:
                metric = metric_fn(value)
                metric_values.append(metric)
            except Exception as e:
                logger.warning(f"Failed for {param_name}={value}: {e}")
                metric_values.append(float("nan"))

        valid_metrics = [m for m in metric_values if m == m]

        best_idx = None
        best_metric = -float("inf")
        for i, m in enumerate(metric_values):
            if m == m and m > best_metric:
                best_metric = m
                best_idx = i

        mean_metric = statistics.mean(valid_metrics) if valid_metrics else 0.0
        std_metric = statistics.stdev(valid_metrics) if len(valid_metrics) > 1 else 0.0

        result = ParameterSweepResult(
            param_name=param_name,
            param_values=param_values,
            metric_values=metric_values,
            best_param=param_values[best_idx] if best_idx is not None else 0.0,
            best_metric=best_metric,
            mean_metric=mean_metric,
            std_metric=std_metric,
        )

        return result

    def analyze_2d(
        self,
        x_param: str,
        y_param: str,
        x_values: List[float],
        y_values: List[float],
        metric_fn: Callable[[float, float], float],
    ) -> StabilityResult:
        heatmap = []
        all_metrics = []

        for y in y_values:
            row = []
            for x in x_values:
                try:
                    metric = metric_fn(x, y)
                    row.append(metric)
                    all_metrics.append(metric)
                except Exception as e:
                    logger.warning(f"Failed for {x_param}={x}, {y_param}={y}: {e}")
                    row.append(float("nan"))
            heatmap.append(row)

        valid_metrics = [m for m in all_metrics if m == m]
        mean_metric = statistics.mean(valid_metrics) if valid_metrics else 0.0
        std_metric = statistics.stdev(valid_metrics) if len(valid_metrics) > 1 else 0.0

        result = StabilityResult()

        result.heatmap_data = {
            "x_param": x_param,
            "y_param": y_param,
            "x_values": x_values,
            "y_values": y_values,
            "values": heatmap,
        }

        needle_peaks = self._detect_needle_peaks(heatmap, x_values, y_values)
        result.needle_peaks = needle_peaks

        stable_regions = self._find_stable_regions(heatmap, x_values, y_values, x_param, y_param)
        result.stable_regions = stable_regions

        stability_score = 1.0 - (std_metric / (mean_metric + 1e-8)) if mean_metric > 0 else 0.0
        stability_score = max(0.0, min(1.0, stability_score))
        result.overall_stability_score = stability_score

        result.is_stable = (
            stability_score > 0.7
            and len(needle_peaks) == 0
            and len(stable_regions) > 0
        )

        return result

    def _detect_needle_peaks(
        self,
        heatmap: List[List[float]],
        x_values: List[float],
        y_values: List[float],
        threshold_factor: float = 2.0,
    ) -> List[Dict[str, Any]]:
        peaks = []
        all_valid = [v for row in heatmap for v in row if v == v]

        if not all_valid:
            return peaks

        mean_val = statistics.mean(all_valid)
        std_val = statistics.stdev(all_valid) if len(all_valid) > 1 else 0.0
        threshold = mean_val + threshold_factor * std_val

        for j, row in enumerate(heatmap):
            for i, val in enumerate(row):
                if val == val and val > threshold:
                    neighbors = []
                    for dj in [-1, 0, 1]:
                        for di in [-1, 0, 1]:
                            if dj == 0 and di == 0:
                                continue
                            nj, ni = j + dj, i + di
                            if 0 <= nj < len(heatmap) and 0 <= ni < len(heatmap[0]):
                                n_val = heatmap[nj][ni]
                                if n_val == n_val:
                                    neighbors.append(n_val)

                    if neighbors:
                        mean_neighbors = statistics.mean(neighbors)
                        if val > mean_neighbors * 1.5:
                            peaks.append({
                                "x": x_values[i],
                                "y": y_values[j],
                                "value": val,
                                "mean_neighbors": mean_neighbors,
                            })

        return peaks

    def _find_stable_regions(
        self,
        heatmap: List[List[float]],
        x_values: List[float],
        y_values: List[float],
        x_param: str,
        y_param: str,
        metric_threshold: float = 0.5,
        max_std: float = 1.0,
    ) -> List[StabilityRegion]:
        regions = []

        if not heatmap:
            return regions

        all_valid = [v for row in heatmap for v in row if v == v]
        mean_val = statistics.mean(all_valid) if all_valid else 0.0

        def is_good(val: float) -> bool:
            if val != val:
                return False
            return val > max(metric_threshold, mean_val * 0.5)

        i = 0
        n_rows = len(heatmap)
        n_cols = len(heatmap[0]) if n_rows > 0 else 0

        for j in range(n_rows):
            current_start_i = None
            for i in range(n_cols):
                if is_good(heatmap[j][i]):
                    if current_start_i is None:
                        current_start_i = i
                else:
                    if current_start_i is not None:
                        region = StabilityRegion(
                            x_min=x_values[current_start_i],
                            x_max=x_values[i - 1],
                            y_min=y_values[j],
                            y_max=y_values[j],
                            x_param=x_param,
                            y_param=y_param,
                        )
                        regions.append(region)
                        current_start_i = None
            if current_start_i is not None:
                region = StabilityRegion(
                    x_min=x_values[current_start_i],
                    x_max=x_values[-1],
                    y_min=y_values[j],
                    y_max=y_values[j],
                    x_param=x_param,
                    y_param=y_param,
                )
                regions.append(region)

        return regions

    def analyze_cross_regime(
        self,
        regime_metrics: Dict[str, Dict[str, float]],
    ) -> CrossRegimeStabilityResult:
        """
        Cross-Regime Stability 检测
        
        regime_metrics: {
            "trend":    {"sharpe": 2.1, "win_rate": 0.62, ...},
            "squeeze":  {"sharpe": -1.8, "win_rate": 0.38, ...},
            "liquidation": {"sharpe": 4.2, "win_rate": 0.71, ...},
        }
        
        关键问题：
        整体 Sharpe 2.5 可能只是 liquidation regime 爆赚
        其它 regime 全亏 —— 这是过拟合信号
        """
        result = CrossRegimeStabilityResult()

        for regime, metrics in regime_metrics.items():
            perf = RegimePerformance(
                regime=regime,
                sharpe=metrics.get("sharpe", 0.0),
                win_rate=metrics.get("win_rate", 0.0),
                total_trades=int(metrics.get("total_trades", 0)),
                pnl=metrics.get("pnl", 0.0),
                max_drawdown=metrics.get("max_drawdown", 0.0),
                avg_holding_hours=metrics.get("avg_holding_hours", 0.0),
            )
            result.regime_performance[regime] = perf
            result.sharpe_by_regime[regime] = perf.sharpe

            if perf.is_profitable():
                result.profitable_regimes.append(regime)
            else:
                if not hasattr(result.losing_regimes, '__getitem__'):
                    result.losing_regimes = []
                result.losing_regimes.append(regime)

        valid_sharpes = [s for s in result.sharpe_by_regime.values() if s != 0]
        if len(valid_sharpes) > 1:
            std = statistics.stdev(valid_sharpes)
            mean = statistics.mean(valid_sharpes)
            if mean != 0:
                result.regime_concentration = min(1.0, std / abs(mean))
            result.is_regime_diversified = (
                len(result.profitable_regimes) >= 2
                and result.regime_concentration < 0.5
            )

        logger.info(
            f"Cross-regime analysis: "
            f"{len(result.profitable_regimes)} profitable, "
            f"{len(result.losing_regimes)} losing, "
            f"concentration={result.regime_concentration:.2f}"
        )

        return result
