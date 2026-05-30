
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional, Tuple
from collections import deque
import statistics

from infrastructure.logging import get_logger
from infrastructure.acceleration.acceleration_service import AccelerationService

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
        if self.std_metric < threshold:
            return True
        valid = [v for v in self.metric_values if v == v]
        if valid and min(valid) > 1.0:
            return True
        return False

    @property
    def is_stable(self) -> bool:
        return self.is_flat

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
            "is_stable": self.is_stable,
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
    losing_regimes: List[str] = field(default_factory=list)
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
    profitable_area_ratio: float = 0.0
    stable_area_ratio: float = 0.0
    largest_region_ratio: float = 0.0
    needle_peak_ratio: float = 0.0
    score_decomposition: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stable_regions": [r.to_dict() for r in self.stable_regions],
            "param_sweeps": {k: v.to_dict() for k, v in self.param_sweeps.items()},
            "needle_peaks": self.needle_peaks,
            "is_stable": self.is_stable,
            "overall_stability_score": self.overall_stability_score,
            "heatmap_data": self.heatmap_data,
            "profitable_area_ratio": self.profitable_area_ratio,
            "stable_area_ratio": self.stable_area_ratio,
            "largest_region_ratio": self.largest_region_ratio,
            "needle_peak_ratio": self.needle_peak_ratio,
            "score_decomposition": self.score_decomposition,
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
        enable_parallel: bool = True,
    ) -> StabilityResult:
        heatmap = []
        all_metrics = []

        # 准备任务列表
        tasks = []
        for j, y in enumerate(y_values):
            for i, x in enumerate(x_values):
                tasks.append({"i": i, "j": j, "x": x, "y": y})

        # 执行任务（并行或串行）
        if enable_parallel and len(tasks) > 1:
            service = AccelerationService()
            
            def wrap_task(kwargs):
                i, j, x, y = kwargs["i"], kwargs["j"], kwargs["x"], kwargs["y"]
                try:
                    metric = metric_fn(x, y)
                    return {"i": i, "j": j, "x": x, "y": y, "metric": metric, "error": None}
                except Exception as e:
                    logger.warning(f"Failed for {x_param}={x}, {y_param}={y}: {e}")
                    return {"i": i, "j": j, "x": x, "y": y, "metric": float("nan"), "error": str(e)}
            
            results = service.parallel_map(
                func=wrap_task,
                tasks=[(task,) for task in tasks],
                executor="thread"
            )
            
            # 重新组装 heatmap
            heatmap = [[float("nan") for _ in x_values] for _ in y_values]
            for res in results:
                if res:
                    heatmap[res["j"]][res["i"]] = res["metric"]
                    if res["metric"] == res["metric"]:
                        all_metrics.append(res["metric"])
        else:
            # 串行执行
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

        area_metrics = self._compute_area_metrics(heatmap)
        result.profitable_area_ratio = area_metrics["profitable_area_ratio"]
        result.stable_area_ratio = area_metrics["stable_area_ratio"]
        result.largest_region_ratio = area_metrics["largest_region_ratio"]

        total_cells = len(heatmap) * len(heatmap[0]) if heatmap and heatmap[0] else 1
        result.needle_peak_ratio = round(len(needle_peaks) / total_cells, 4)

        cv = std_metric / (mean_metric + 1e-8) if mean_metric > 0 else float("inf")
        stability_score = 1.0 - cv if mean_metric > 0 else 0.0
        stability_score = max(0.0, min(1.0, stability_score))
        result.overall_stability_score = stability_score

        result.score_decomposition = {
            "cv": round(cv, 4),
            "mean_sharpe": round(mean_metric, 4),
            "std_sharpe": round(std_metric, 4),
            "needle_peak_count": len(needle_peaks),
            "needle_peak_ratio": result.needle_peak_ratio,
            "stable_region_count": len(stable_regions),
            "profitable_area_ratio": result.profitable_area_ratio,
            "stable_area_ratio": result.stable_area_ratio,
            "largest_region_ratio": result.largest_region_ratio,
        }

        score_stable = (
            stability_score > 0.7
            and len(needle_peaks) == 0
            and len(stable_regions) > 0
        )

        region_override = False
        if not score_stable and stable_regions:
            large_regions = [r for r in stable_regions if r.num_samples >= 3]
            if large_regions:
                region_metrics = []
                for r in large_regions:
                    if r.mean_sharpe > 0:
                        region_metrics.append(r.mean_sharpe)
                if region_metrics and min(region_metrics) > 1.5:
                    region_override = True

        result.is_stable = score_stable or region_override

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

    def _compute_area_metrics(
        self,
        heatmap: List[List[float]],
        profitable_threshold: float = 0.0,
        stable_threshold: float = 1.5,
    ) -> Dict[str, float]:
        n_rows = len(heatmap)
        if n_rows == 0:
            return {
                "profitable_area_ratio": 0.0,
                "stable_area_ratio": 0.0,
                "largest_region_ratio": 0.0,
            }
        n_cols = len(heatmap[0])
        total_cells = n_rows * n_cols
        if total_cells == 0:
            return {
                "profitable_area_ratio": 0.0,
                "stable_area_ratio": 0.0,
                "largest_region_ratio": 0.0,
            }

        profitable_count = 0
        stable_count = 0
        profitable_mask = [[False] * n_cols for _ in range(n_rows)]

        for j in range(n_rows):
            for i in range(n_cols):
                val = heatmap[j][i]
                if val == val:
                    if val > profitable_threshold:
                        profitable_count += 1
                        profitable_mask[j][i] = True
                    if val > stable_threshold:
                        stable_count += 1

        visited = [[False] * n_cols for _ in range(n_rows)]
        largest_component = 0

        for j in range(n_rows):
            for i in range(n_cols):
                if profitable_mask[j][i] and not visited[j][i]:
                    component_size = 0
                    queue = deque()
                    queue.append((j, i))
                    visited[j][i] = True
                    while queue:
                        cj, ci = queue.popleft()
                        component_size += 1
                        for dj, di in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nj, ni = cj + dj, ci + di
                            if (
                                0 <= nj < n_rows
                                and 0 <= ni < n_cols
                                and not visited[nj][ni]
                                and profitable_mask[nj][ni]
                            ):
                                visited[nj][ni] = True
                                queue.append((nj, ni))
                    largest_component = max(largest_component, component_size)

        return {
            "profitable_area_ratio": round(profitable_count / total_cells, 4),
            "stable_area_ratio": round(stable_count / total_cells, 4),
            "largest_region_ratio": round(largest_component / total_cells, 4),
        }

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


@dataclass
class StabilityReport:
    profitable_area_ratio: float
    stable_area_ratio: float
    largest_region_ratio: float
    needle_peak_ratio: float
    mean_sharpe: float
    std_sharpe: float
    cv: float
    stability_score: float
    is_stable: bool
    needle_peak_count: int
    stable_region_count: int

    def to_dict(self) -> dict:
        return {
            "profitable_area_ratio": self.profitable_area_ratio,
            "stable_area_ratio": self.stable_area_ratio,
            "largest_region_ratio": self.largest_region_ratio,
            "needle_peak_ratio": self.needle_peak_ratio,
            "mean_sharpe": self.mean_sharpe,
            "std_sharpe": self.std_sharpe,
            "cv": self.cv,
            "stability_score": self.stability_score,
            "is_stable": self.is_stable,
            "needle_peak_count": self.needle_peak_count,
            "stable_region_count": self.stable_region_count,
        }

    def format_text(self, symbol: str = "", strategy: str = "") -> str:
        header = "2D Stability Report"
        if symbol:
            header += f" | {symbol}"
        if strategy:
            header += f" | {strategy}"

        par_pct = f"{self.profitable_area_ratio:.0%}"
        sar_pct = f"{self.stable_area_ratio:.0%}"
        lrr_pct = f"{self.largest_region_ratio:.0%}"
        npr_pct = f"{self.needle_peak_ratio:.1%}"

        stable_tag = "STABLE" if self.is_stable else "UNSTABLE"

        lines = [
            f"  {header}",
            f"  {'=' * 50}",
            f"  profitable_area_ratio  {par_pct:>8}   Sharpe > 0 占比",
            f"  stable_area_ratio      {sar_pct:>8}   Sharpe > 1.5 占比",
            f"  largest_region_ratio   {lrr_pct:>8}   最大连通盈利区域占比",
            f"  needle_peak_ratio      {npr_pct:>8}   尖峰区域占比",
            f"  {'-' * 50}",
            f"  mean_sharpe            {self.mean_sharpe:>8.3f}   平均 Sharpe",
            f"  std_sharpe             {self.std_sharpe:>8.3f}   Sharpe 标准差",
            f"  cv                     {self.cv:>8.4f}   std / mean",
            f"  stability_score        {self.stability_score:>8.3f}   1 - cv",
            f"  {'-' * 50}",
            f"  needle_peak_count      {self.needle_peak_count:>8d}",
            f"  stable_region_count    {self.stable_region_count:>8d}",
            f"  is_stable              {stable_tag:>8}",
        ]
        return "\n".join(lines)


def generate_stability_report(result: StabilityResult) -> StabilityReport:
    decomp = result.score_decomposition
    return StabilityReport(
        profitable_area_ratio=result.profitable_area_ratio,
        stable_area_ratio=result.stable_area_ratio,
        largest_region_ratio=result.largest_region_ratio,
        needle_peak_ratio=result.needle_peak_ratio,
        mean_sharpe=decomp.get("mean_sharpe", 0.0),
        std_sharpe=decomp.get("std_sharpe", 0.0),
        cv=decomp.get("cv", 0.0),
        stability_score=result.overall_stability_score,
        is_stable=result.is_stable,
        needle_peak_count=decomp.get("needle_peak_count", 0),
        stable_region_count=decomp.get("stable_region_count", 0),
    )
