import asyncio
import statistics
import time
from typing import List, Optional, Dict, Any

from infrastructure.logging import get_logger
from infrastructure.runtime_clock import now_ms

from research.protocol.core import ResearchDataset, FeatureVector
from research.walk_forward.context import (
    ResearchContext,
    TimeRange,
    WindowSpec,
    WindowResult,
    WalkForwardReport,
    ExecutionModels,
)
from research.walk_forward.strategy import (
    ResearchStrategy,
    TradeSignal,
    BacktestTrade,
    SignalDirection,
    WindowMetrics,
)
from research.walk_forward.splitters import WindowSplitter
from research.reality_engine import RealityExecutionLayer

logger = get_logger("research.execution_engine")


class ResearchExecutionEngine:
    """
    量化研究执行引擎 —— Research Runtime 的核心调度器
    
    数据流：
    Dataset → WindowSplitter → FeatureResolver → StrategyRunner → RealityLayer → MetricsCollector
    
    铁律：
    1. 只接受 ResearchDataset（协议化输入）
    2. 不持有任何 Runtime 引用
    3. 所有模块通过 ResearchContext 共享配置
    """

    def __init__(self):
        self._reality_layer: Optional[RealityExecutionLayer] = None

    def run(
        self,
        dataset: ResearchDataset,
        strategy: ResearchStrategy,
        splitter: WindowSplitter,
        context: ResearchContext,
    ) -> WalkForwardReport:
        """
        执行研究流程
        
        Args:
            dataset: ResearchDataset（只读数据访问协议）
            strategy: ResearchStrategy（策略实现）
            splitter: WindowSplitter（窗口切分器）
            context: ResearchContext（执行上下文）
        
        Returns:
            WalkForwardReport（完整报告）
        """
        start_time = now_ms()
        
        strategy.setup(context)
        
        self._init_reality_layer(context)
        
        total_range = TimeRange(
            start_ms=context.train_range.start_ms,
            end_ms=context.test_range.end_ms,
        )
        
        windows = splitter.split(total_range)
        
        logger.info(
            f"ResearchExecutionEngine: starting {len(windows)} windows "
            f"for {context.dataset_id}"
        )
        
        window_results: List[WindowResult] = []
        
        for window_spec in windows:
            try:
                result = self._run_window(
                    dataset=dataset,
                    strategy=strategy,
                    window=window_spec,
                    context=context,
                )
                window_results.append(result)
                
                logger.info(
                    f"Window {window_spec.window_index}: "
                    f"Sharpe={result.sharpe:.2f}, "
                    f"PnL={result.total_pnl:.2f}, "
                    f"Trades={result.total_trades}"
                )
            except Exception as e:
                logger.error(f"Window {window_spec.window_index} failed: {e}")
                window_results.append(WindowResult(
                    window=window_spec,
                    sharpe=0.0, sortino=0.0, win_rate=0.0,
                    total_trades=0, total_pnl=0.0, max_drawdown=0.0,
                    annual_return=0.0, profit_factor=0.0,
                    errors=(str(e),),
                ))
        
        report = self._build_report(
            context=context,
            window_results=window_results,
            start_time_ms=start_time,
        )
        
        logger.info(
            f"ResearchExecutionEngine complete: "
            f"{len(window_results)} windows, "
            f"Sharpe={report.overall_sharpe_mean:.2f}±{report.overall_sharpe_std:.2f}, "
            f"PnL={report.overall_pnl:.2f}"
        )
        
        return report

    def _run_window(
        self,
        dataset: ResearchDataset,
        strategy: ResearchStrategy,
        window: WindowSpec,
        context: ResearchContext,
    ) -> WindowResult:
        window_start = now_ms()
        
        trades: List[BacktestTrade] = []
        current_position = None
        entry_price = 0.0
        entry_time_ms = 0
        entry_direction = SignalDirection.NEUTRAL
        
        for fv in dataset.iter_feature_vectors(
            symbol=context.symbol,
            start_ms=window.test_range.start_ms,
            end_ms=window.test_range.end_ms,
        ):
            features = fv.values
            
            signal = strategy.on_bar(fv.available_time_ms, features)
            
            if not signal.is_actionable():
                if current_position is not None:
                    exit_trade = self._close_trade(
                        entry_time_ms=entry_time_ms,
                        exit_time_ms=fv.available_time_ms,
                        direction=entry_direction,
                        entry_price=entry_price,
                        exit_price=features.get("close", fv.values.get("price", entry_price)),
                        quantity=1.0,
                        context=context,
                    )
                    if exit_trade:
                        trades.append(exit_trade)
                    current_position = None
                continue
            
            if current_position is None:
                entry_price = features.get("close", features.get("price", 100000))
                entry_time_ms = fv.available_time_ms
                entry_direction = signal.direction
                current_position = True
            else:
                if signal.direction != entry_direction:
                    exit_trade = self._close_trade(
                        entry_time_ms=entry_time_ms,
                        exit_time_ms=fv.available_time_ms,
                        direction=entry_direction,
                        entry_price=entry_price,
                        exit_price=features.get("close", features.get("price", entry_price)),
                        quantity=1.0,
                        context=context,
                    )
                    if exit_trade:
                        trades.append(exit_trade)
                    
                    entry_price = features.get("close", features.get("price", 100000))
                    entry_time_ms = fv.available_time_ms
                    entry_direction = signal.direction
        
        if current_position is not None:
            last_features = {}
            for fv in dataset.iter_feature_vectors(
                symbol=context.symbol,
                start_ms=window.test_range.end_ms - 3600000,
                end_ms=window.test_range.end_ms,
            ):
                last_features = fv.values
            
            exit_trade = self._close_trade(
                entry_time_ms=entry_time_ms,
                exit_time_ms=window.test_range.end_ms,
                direction=entry_direction,
                entry_price=entry_price,
                exit_price=last_features.get("close", last_features.get("price", entry_price)),
                quantity=1.0,
                context=context,
            )
            if exit_trade:
                trades.append(exit_trade)
        
        metrics = strategy.compute_metrics(trades)
        
        execution_time_ms = now_ms() - window_start
        
        return WindowResult(
            window=window,
            sharpe=metrics.sharpe,
            sortino=metrics.sortino,
            win_rate=metrics.win_rate,
            total_trades=len(trades),
            total_pnl=metrics.total_pnl,
            max_drawdown=metrics.max_drawdown,
            annual_return=metrics.annual_return,
            profit_factor=metrics.profit_factor,
            execution_time_ms=execution_time_ms,
        )

    def _close_trade(
        self,
        entry_time_ms: int,
        exit_time_ms: int,
        direction: SignalDirection,
        entry_price: float,
        exit_price: float,
        quantity: float,
        context: ResearchContext,
    ) -> Optional[BacktestTrade]:
        if entry_price <= 0 or exit_price <= 0:
            return None
        
        if direction == SignalDirection.LONG:
            raw_pnl = (exit_price - entry_price) / entry_price
        elif direction == SignalDirection.SHORT:
            raw_pnl = (entry_price - exit_price) / entry_price
        else:
            return None
        
        pnl_bps = raw_pnl * 10000
        
        if self._reality_layer:
            cost_result = self._reality_layer.simulate_entry(
                notional=entry_price * quantity,
                mid_price=entry_price,
                is_buy=(direction == SignalDirection.LONG),
                volatility=0.02,
                relative_volume=0.01,
                is_taker=True,
            )
            pnl_bps -= cost_result.total_entry_cost_bps
        
        hold_hours = (exit_time_ms - entry_time_ms) / 3600000
        
        return BacktestTrade(
            entry_time_ms=entry_time_ms,
            exit_time_ms=exit_time_ms,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl_bps,
            pnl_bps=pnl_bps,
            hold_hours=hold_hours,
        )

    def _build_report(
        self,
        context: ResearchContext,
        window_results: List[WindowResult],
        start_time_ms: int,
    ) -> WalkForwardReport:
        valid = [r for r in window_results if not r.errors]
        
        sharpe_values = [r.sharpe for r in valid]
        pnl_values = [r.total_pnl for r in valid]
        
        sharpe_mean = statistics.mean(sharpe_values) if sharpe_values else 0.0
        sharpe_std = statistics.stdev(sharpe_values) if len(sharpe_values) > 1 else 0.0
        total_pnl = sum(pnl_values)
        total_trades = sum(r.total_trades for r in window_results)
        
        best_idx = window_results.index(max(valid, key=lambda r: r.sharpe)) if valid else 0
        worst_idx = window_results.index(min(valid, key=lambda r: r.sharpe)) if valid else 0
        
        feature_decay_rate = self._compute_feature_decay(window_results)
        regime_stability = self._compute_regime_stability(window_results)
        
        return WalkForwardReport(
            context=context,
            windows=tuple(window_results),
            overall_sharpe_mean=sharpe_mean,
            overall_sharpe_std=sharpe_std,
            overall_pnl=total_pnl,
            overall_trades=total_trades,
            feature_decay_rate=feature_decay_rate,
            regime_stability_score=regime_stability,
            best_window_index=best_idx,
            worst_window_index=worst_idx,
            execution_time_ms=now_ms() - start_time_ms,
        )

    def _compute_feature_decay(self, results: List[WindowResult]) -> float:
        if len(results) < 2:
            return 0.0
        
        sharpes = [r.sharpe for r in results]
        if sharpes[0] == 0:
            return 0.0
        
        decay = (sharpes[-1] - sharpes[0]) / abs(sharpes[0])
        return decay

    def _compute_regime_stability(self, results: List[WindowResult]) -> float:
        if len(results) < 2:
            return 1.0
        
        sharpes = [r.sharpe for r in results]
        std = statistics.stdev(sharpes)
        mean = abs(statistics.mean(sharpes))
        
        if mean == 0:
            return 0.0
        
        cv = std / mean
        stability = max(0.0, 1.0 - cv)
        return stability

    def _init_reality_layer(self, context: ResearchContext) -> None:
        models = context.execution_models
        
        self._reality_layer = RealityExecutionLayer(
            slippage_model=None,
            latency_model=None,
            fee_model=None,
        )
