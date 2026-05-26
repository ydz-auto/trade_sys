"""
Parallel Executor - 通用并行执行器

提供通用的多进程/多线程并行执行能力，供：
- OptimizationService (API 层)
- WalkForwardRunner (脚本层)

统一使用，避免重复代码
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
import logging
from itertools import product

logger = logging.getLogger(__name__)


@dataclass
class BacktestTaskResult:
    """回测任务结果"""
    params: Dict[str, Any]
    score: float
    trades: int = 0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    error: Optional[str] = None


class ParallelExecutor:
    """
    并行执行器
    
    支持多种执行器：
    - process: 多进程（CPU密集型，推荐用于参数优化）
    - thread: 多线程（I/O密集型）
    - sequential: 串行（调试用）
    
    注意：传递给 execute() 的函数必须是模块级别的，不能是局部函数
    """
    
    def __init__(
        self,
        executor_type: str = "process",
        max_workers: Optional[int] = None
    ):
        self.executor_type = executor_type
        
        if max_workers is None:
            self.max_workers = max(1, mp.cpu_count() - 1)
        else:
            self.max_workers = max_workers
        
        logger.info(f"ParallelExecutor initialized: type={executor_type}, max_workers={self.max_workers}")
    
    def execute(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行并行任务
        
        Args:
            func: 执行函数，接收 tuple 参数，返回 dict 结果
                  注意：必须是模块级别的函数，不能是 lambda 或局部函数
            tasks: 任务参数列表
            progress_callback: 进度回调函数 callback(completed, total)
        
        Returns:
            List[Dict[str, Any]]: 结果列表
        """
        results = []
        num_tasks = len(tasks)
        
        if self.executor_type == "sequential" or num_tasks <= 1:
            return self._execute_sequential(func, tasks, progress_callback)
        
        return self._execute_parallel(func, tasks, progress_callback)
    
    def _execute_sequential(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[Dict[str, Any]]:
        """串行执行"""
        logger.info(f"Sequential execution: {len(tasks)} tasks")
        
        results = []
        for i, task in enumerate(tasks):
            try:
                result = func(task)
                results.append(result)
            except Exception as e:
                logger.warning(f"Task failed: {e}")
                results.append({"error": str(e)})
            
            if progress_callback and (i + 1) % 10 == 0:
                progress_callback(i + 1, len(tasks))
        
        if progress_callback:
            progress_callback(len(tasks), len(tasks))
        
        return results
    
    def _execute_parallel(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[Dict[str, Any]]:
        """并行执行"""
        max_workers = min(self.max_workers, len(tasks))
        logger.info(f"Parallel execution: {len(tasks)} tasks, workers={max_workers}")
        
        if self.executor_type == "process":
            executor_class = ProcessPoolExecutor
        elif self.executor_type == "thread":
            executor_class = ThreadPoolExecutor
        else:
            return self._execute_sequential(func, tasks, progress_callback)
        
        results_dict: Dict[int, Dict[str, Any]] = {}
        
        with executor_class(max_workers=max_workers) as executor:
            futures = {
                executor.submit(func, task): i
                for i, task in enumerate(tasks)
            }
            
            completed = 0
            for future in as_completed(futures):
                task_idx = futures[future]
                try:
                    result = future.result()
                    results_dict[task_idx] = result
                except Exception as e:
                    logger.warning(f"Task {task_idx} failed: {e}")
                    results_dict[task_idx] = {"error": str(e)}
                
                completed += 1
                if progress_callback and completed % 10 == 0:
                    progress_callback(completed, len(tasks))
        
        if progress_callback:
            progress_callback(len(tasks), len(tasks))
        
        return [results_dict[i] for i in sorted(results_dict.keys())]
    
    @staticmethod
    def create_default_executor(
        enable_multiprocess: bool = True,
        max_workers: Optional[int] = None
    ) -> 'ParallelExecutor':
        """
        创建默认执行器
        
        Args:
            enable_multiprocess: 是否启用多进程
            max_workers: 最大工作进程数
        
        Returns:
            ParallelExecutor 实例
        """
        if enable_multiprocess:
            return ParallelExecutor(
                executor_type="process",
                max_workers=max_workers
            )
        else:
            return ParallelExecutor(
                executor_type="sequential",
                max_workers=1
            )


def _grid_search_backtest_wrapper(args: tuple) -> Dict[str, Any]:
    """
    Grid Search 回测包装器（模块级别函数，可被 pickle）
    
    这个函数作为 GridSearchOptimizer 内部的默认回测函数
    """
    params, strategy_id, bars_data, config_dict, enable_gpu, funding_data, oi_data = args
    
    try:
        import os
        import sys
        import pandas as pd
        
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        sys.path.insert(0, backend_path)
        
        from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, SignalType, Bar
        from engines.compute.strategy.strategies import (
            RSIStrategy, MACDStrategy, SMACrossoverStrategy, EMACrossoverStrategy,
            BollingerBandsStrategy, MomentumStrategy, PanicReversalStrategy,
            LongLiquidationBounceStrategy, VolumeClimaxFadeStrategy,
            WeakBounceShortStrategy, OIFlushStrategy, ShortSqueezeStrategy,
            FundingExhaustionTrapStrategy, DeadCatEchoStrategy,
            ImbalancePressureStrategy, SweepDetectionStrategy,
            LiquidityVacuumStrategy, AggressiveFlowStrategy, BreakoutStrategy,
            TrendFollowingStrategy, VolatilityExpansionStrategy,
            BBCompressionBreakoutStrategy, MomentumIgnitionStrategy,
            LeadLagStrategy, PremiumDivergenceStrategy
        )
        
        STRATEGY_CLASS_MAP = {
            "rsi_oversold": RSIStrategy, "rsi_overbought": RSIStrategy,
            "macd_cross": MACDStrategy, "sma_cross": SMACrossoverStrategy,
            "ema_cross": EMACrossoverStrategy, "bollinger_bands": BollingerBandsStrategy,
            "momentum": MomentumStrategy, "panic_reversal": PanicReversalStrategy,
            "long_liquidation_bounce": LongLiquidationBounceStrategy,
            "volume_climax_fade": VolumeClimaxFadeStrategy,
            "weak_bounce_short": WeakBounceShortStrategy,
            "oi_flush": OIFlushStrategy, "short_squeeze": ShortSqueezeStrategy,
            "funding_exhaustion_trap": FundingExhaustionTrapStrategy,
            "dead_cat_echo": DeadCatEchoStrategy,
            "imbalance_pressure": ImbalancePressureStrategy,
            "sweep_detection": SweepDetectionStrategy,
            "liquidity_vacuum": LiquidityVacuumStrategy,
            "aggressive_flow": AggressiveFlowStrategy, "breakout": BreakoutStrategy,
            "trend_following": TrendFollowingStrategy,
            "volatility_expansion": VolatilityExpansionStrategy,
            "bb_compression_breakout": BBCompressionBreakoutStrategy,
            "momentum_ignition": MomentumIgnitionStrategy,
            "lead_lag": LeadLagStrategy, "premium_divergence": PremiumDivergenceStrategy
        }
        
        strategy_cls = STRATEGY_CLASS_MAP.get(strategy_id)
        if not strategy_cls:
            return {"params": params, "score": -float('inf'), "error": f"Unknown strategy: {strategy_id}"}
        
        strategy = strategy_cls(strategy_id=strategy_id, **params)
        
        class StrategyAdapter:
            def __init__(self, strategy):
                self.strategy = strategy
                self._closes = []
            
            def __call__(self, bar, position=None):
                self._closes.append(bar.close)
                if len(self._closes) > 600:
                    self._closes = self._closes[-600:]
                
                from engines.compute.strategy.strategies import ActionType
                try:
                    signal = self.strategy.calculate({
                        "close_prices": self._closes,
                        "high_prices": self._closes,
                        "low_prices": self._closes,
                        "volumes": self._closes,
                        "symbol": "BTCUSDT",
                        "timestamp": bar.timestamp
                    })
                    if signal:
                        if signal.action == ActionType.LONG:
                            return SignalType.BUY
                        elif signal.action == ActionType.SHORT:
                            return SignalType.SELL
                except:
                    pass
                return SignalType.HOLD
        
        config = BacktestConfig(**config_dict)
        adapter = StrategyAdapter(strategy)
        bars = [Bar(**b) for b in bars_data]
        
        engine = BacktestEngine(config=config, enable_gpu=enable_gpu)
        engine.load_data(bars)
        result = engine.run(adapter)
        
        if result:
            return {
                "params": params,
                "score": result.metrics.sharpe_ratio,
                "sharpe": result.metrics.sharpe_ratio,
                "trades": result.metrics.total_trades,
                "total_return": result.metrics.total_return,
                "max_drawdown": result.metrics.max_drawdown_pct,
                "win_rate": result.metrics.win_rate,
                "profit_factor": result.metrics.profit_factor
            }
        return {"params": params, "score": -float('inf'), "error": "No result"}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"params": params, "score": -float('inf'), "error": str(e)}


class GridSearchOptimizer:
    """
    Grid Search 参数优化器
    
    封装并行执行逻辑，专门用于参数网格搜索
    使用模块级别的 _grid_search_backtest_wrapper 函数确保可以被 pickle
    
    Example:
        optimizer = GridSearchOptimizer(
            executor=ParallelExecutor(executor_type="process", max_workers=15)
        )
        
        result = optimizer.optimize(
            strategy_id="long_liquidation_bounce",
            param_grid={"period": [14, 21], "threshold": [0.02, 0.03]},
            bars_data=bars_data,
            config_dict=config_dict
        )
    """
    
    def __init__(self, executor: Optional[ParallelExecutor] = None):
        self.executor = executor or ParallelExecutor.create_default_executor()
    
    def optimize(
        self,
        strategy_id: str,
        param_grid: Dict[str, List[Any]],
        bars_data: List[Dict],
        config_dict: Optional[Dict] = None,
        funding_data: Optional[List] = None,
        oi_data: Optional[List] = None,
        objective: str = "sharpe",
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        运行参数优化
        
        Args:
            strategy_id: 策略ID
            param_grid: 参数网格
            bars_data: K线数据（序列化后的列表）
            config_dict: 回测配置字典
            funding_data: 资金费率数据
            oi_data: OI数据
            objective: 优化目标
            verbose: 是否打印进度
        
        Returns:
            Dict: 优化结果，包含 best_params, best_score, all_results
        """
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        param_combinations = [dict(zip(keys, combo)) for combo in product(*values)]
        
        logger.info(f"GridSearchOptimizer: {strategy_id}, {len(param_combinations)} combinations")
        
        default_config = {
            "initial_capital": 10000.0,
            "commission": 0.0004,
            "slippage": 0.0005,
            "position_size": 0.1,
            "stop_loss": 0.10,
            "take_profit": 0.20,
            "leverage": 5.0,
            "use_realistic_fees": True,
        }
        config_dict = config_dict or default_config
        
        def progress_callback(done, total):
            if verbose:
                logger.info(f"  Progress: {done}/{total}")
        
        tasks = [
            (params, strategy_id, bars_data, config_dict, False, funding_data, oi_data)
            for params in param_combinations
        ]
        
        all_results = self.executor.execute(
            func=_grid_search_backtest_wrapper,
            tasks=tasks,
            progress_callback=progress_callback if verbose else None
        )
        
        best_score = -float('inf')
        best_params = None
        best_result = None
        
        for result in all_results:
            if result.get("error"):
                continue
            
            score = result.get("score", result.get("sharpe", -float('inf')))
            if score > best_score:
                best_score = score
                best_params = result.get("params")
                best_result = result
        
        return {
            "best_params": best_params or {},
            "best_score": best_score,
            "best_result": best_result,
            "all_results": all_results,
            "num_combinations": len(param_combinations)
        }
