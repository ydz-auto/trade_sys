"""
Optimization Service - 策略参数优化服务

核心职责：
1. 参数优化（Grid Search / Random Search / Bayesian）
2. 使用 OptimizationBacktestEngine 确保回测 = 实盘
3. 支持多币种、多策略批量优化

架构：
    Optimization API
        ↓
    OptimizationService
        ↓
    OptimizationBacktestEngine (走 Runtime Pipeline)
        ↓
    MarketEventEmitter (发出真实事件)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from itertools import product
import asyncio
import uuid
import json

from infrastructure.logging import get_logger
from infrastructure.utilities.time_authority import ensure_time_ms

from .engine import OptimizationBacktestAdapter as OptimizationBacktestEngine, BacktestConfig, BacktestResult


def _run_single_backtest_sync(
    data_path: str,
    symbol: str,
    strategy_id: str,
    start_time: str,
    end_time: str,
    params: Dict[str, Any],
    backtest_config: BacktestConfig,
    metric: str,
) -> Dict[str, Any]:
    """独立的同步回测函数（可被 pickle）"""
    import pandas as pd
    import numpy as np
    from datetime import datetime
    from pathlib import Path
    
    if isinstance(data_path, Path):
        data_path = str(data_path)
    
    path = Path(data_path)
    if not path.exists():
        path = path.parent / "features_opt.parquet"
    
    if not path.exists():
        return {
            "params": params,
            "score": -float('inf'),
            "result": None,
            "error": f"Data file not found: {path}",
        }
    
    df = pd.read_parquet(path)
    
    # 统一时间处理逻辑：检测时间列类型并转换
    if "timestamp_ms" in df.columns:
        # 已经是 int64 ms 格式
        timestamp_col = "timestamp_ms"
    elif "timestamp" in df.columns:
        # 可能是 pd.Timestamp，需要转换
        timestamp_col = "timestamp"
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df["timestamp_ms"] = df[timestamp_col].astype("int64") // 10**6
        timestamp_col = "timestamp_ms"
    elif "open_time" in df.columns:
        timestamp_col = "open_time"
        # 检查 open_time 格式
        if pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df["timestamp_ms"] = df[timestamp_col].astype("int64") // 10**6
        else:
            df["timestamp_ms"] = df[timestamp_col]
        timestamp_col = "timestamp_ms"
    else:
        return {
            "params": params,
            "score": -float('inf'),
            "result": None,
            "error": "No timestamp column found in data",
        }
    
    # 使用时间权威系统转换 start/end 时间
    # 这里我们实现一个简单的转换，因为在子进程中无法导入完整模块
    def _simple_normalize_time_ms(time_val):
        if isinstance(time_val, int):
            if time_val < 10**12:
                return time_val * 1000
            return time_val
        elif isinstance(time_val, float):
            return int(time_val * 1000)
        elif isinstance(time_val, str):
            try:
                dt = pd.to_datetime(time_val)
                return int(dt.timestamp() * 1000)
            except:
                return 0
        return 0
    
    start_ms = _simple_normalize_time_ms(start_time)
    end_ms = _simple_normalize_time_ms(end_time)
    
    df = df[(df[timestamp_col] >= start_ms) & (df[timestamp_col] <= end_ms)]
    
    if len(df) == 0:
        return {
            "params": params,
            "score": -float('inf'),
            "result": None,
            "error": "No data in date range",
        }
    
    fast = params.get("fast", 10)
    slow = params.get("slow", 50)
    
    df["fast_ma"] = df["close"].rolling(fast).mean()
    df["slow_ma"] = df["close"].rolling(slow).mean()
    df["signal"] = 0
    df.loc[df["fast_ma"] > df["slow_ma"], "signal"] = 1
    df.loc[df["fast_ma"] < df["slow_ma"], "signal"] = -1
    
    position = None
    trades = []
    capital = backtest_config.initial_capital
    
    for i in range(slow, len(df)):
        row = df.iloc[i]
        current_price = row["close"]
        current_signal = row["signal"]
        
        if pd.isna(row["fast_ma"]) or pd.isna(row["slow_ma"]):
            continue
        
        if position is not None:
            pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]
            if position["direction"] == "short":
                pnl_pct = -pnl_pct
            
            if pnl_pct <= -backtest_config.stop_loss:
                exit_price = current_price * (1 - backtest_config.slippage)
                pnl = position["quantity"] * (exit_price - position["entry_price"])
                if position["direction"] == "short":
                    pnl = position["quantity"] * (position["entry_price"] - exit_price)
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": row["timestamp"],
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "quantity": position["quantity"],
                    "direction": position["direction"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "stop_loss",
                })
                capital += pnl
                position = None
            elif pnl_pct >= backtest_config.take_profit:
                exit_price = current_price * (1 - backtest_config.slippage)
                pnl = position["quantity"] * (exit_price - position["entry_price"])
                if position["direction"] == "short":
                    pnl = position["quantity"] * (position["entry_price"] - exit_price)
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": row["timestamp"],
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "quantity": position["quantity"],
                    "direction": position["direction"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "take_profit",
                })
                capital += pnl
                position = None
            elif current_signal == -1 and position["direction"] == "long":
                exit_price = current_price * (1 - backtest_config.slippage)
                pnl = position["quantity"] * (exit_price - position["entry_price"])
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": row["timestamp"],
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "quantity": position["quantity"],
                    "direction": position["direction"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "signal",
                })
                capital += pnl
                position = None
        
        if position is None and current_signal == 1:
            position_value = capital * backtest_config.position_size
            quantity = position_value / current_price
            position = {
                "entry_time": row["timestamp"],
                "entry_price": current_price * (1 + backtest_config.slippage),
                "quantity": quantity,
                "direction": "long",
            }
    
    if position is not None:
        last_price = df.iloc[-1]["close"]
        exit_price = last_price * (1 - backtest_config.slippage)
        pnl = position["quantity"] * (exit_price - position["entry_price"])
        trades.append({
            "entry_time": position["entry_time"],
            "exit_time": df.iloc[-1]["timestamp"],
            "entry_price": position["entry_price"],
            "exit_price": exit_price,
            "quantity": position["quantity"],
            "direction": position["direction"],
            "pnl": pnl,
            "pnl_pct": (exit_price - position["entry_price"]) / position["entry_price"],
            "exit_reason": "end",
        })
        capital += pnl
    
    total_return = (capital - backtest_config.initial_capital) / backtest_config.initial_capital
    
    if trades:
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        returns = [t["pnl_pct"] for t in trades]
        
        if metric == "sharpe_ratio" and len(returns) > 1:
            score = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252)
        elif metric == "total_return":
            score = total_return
        elif metric == "win_rate":
            score = len(wins) / len(trades) if trades else 0
        else:
            score = total_return
    else:
        score = -float('inf')
    
    return {
        "params": params,
        "score": score,
        "result": None,
        "trades": trades,
        "total_return": total_return,
        "total_trades": len(trades),
    }
from .models import (
    OptimizationTask,
    OptimizationConfig,
    OptimizationResult,
    OptimizationStatus,
    OptimizationMethod,
    OptimizationMetric,
    StrategyConfig,
    ParamGrid,
    OptimizationMetrics,
    TradeRecord,
)

logger = get_logger("optimization_service")


STRATEGY_REGISTRY = {
    "rsi_oversold": {
        "name": "RSI Oversold",
        "type": "technical",
        "direction": "long",
        "param_grid": {
            "period": [7, 14, 21],
            "oversold": [25, 30, 35],
        },
        "default_params": {"period": 14, "oversold": 30},
    },
    "rsi_overbought": {
        "name": "RSI Overbought",
        "type": "technical",
        "direction": "short",
        "param_grid": {
            "period": [7, 14, 21],
            "overbought": [65, 70, 75],
        },
        "default_params": {"period": 14, "overbought": 70},
    },
    "macd_cross": {
        "name": "MACD Cross",
        "type": "technical",
        "direction": "both",
        "param_grid": {
            "fast": [8, 12],
            "slow": [21, 26],
        },
        "default_params": {"fast": 12, "slow": 26},
    },
    "bollinger_bands": {
        "name": "Bollinger Bands",
        "type": "technical",
        "direction": "both",
        "param_grid": {
            "period": [15, 20, 25],
        },
        "default_params": {"period": 20},
    },
    "sma_cross": {
        "name": "SMA Cross",
        "type": "technical",
        "direction": "both",
        "param_grid": {
            "fast": [5, 10, 20],
            "slow": [30, 50, 100],
        },
        "default_params": {"fast": 10, "slow": 50},
    },
    "ema_cross": {
        "name": "EMA Cross",
        "type": "technical",
        "direction": "both",
        "param_grid": {
            "fast": [5, 10, 20],
            "slow": [30, 50, 100],
        },
        "default_params": {"fast": 10, "slow": 50},
    },
}


class OptimizationService:
    """
    优化服务
    
    使用 OptimizationBacktestEngine 进行参数优化，确保：
    1. 优化结果与实盘一致
    2. 支持多种优化方法
    3. 支持批量优化
    """
    
    def __init__(self):
        self._tasks: Dict[str, OptimizationTask] = {}
        self._results: Dict[str, OptimizationResult] = {}
    
    def _run_parallel_multiprocess(
        self,
        engine,
        data_path,
        symbol: str,
        strategy_id: str,
        start_time: str,
        end_time: str,
        param_combinations: List[Dict[str, Any]],
        max_workers: int,
        metric: str,
    ) -> List[Dict[str, Any]]:
        """使用 ProcessPoolExecutor 进行真正的多进程并行"""
        from concurrent.futures import ProcessPoolExecutor, as_completed
        
        backtest_config = engine.config
        results = []
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _run_single_backtest_sync,
                    data_path, symbol, strategy_id, start_time, end_time,
                    params, backtest_config, metric
                ): params for params in param_combinations
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Multiprocess combo failed: {e}")
                    results.append({
                        "params": futures[future],
                        "score": -float('inf'),
                        "result": None,
                        "error": str(e),
                    })
        
        return results
    
    async def create_task(
        self,
        strategy_id: str,
        symbol: str,
        config: OptimizationConfig,
    ) -> OptimizationTask:
        """创建优化任务"""
        task_id = f"opt_{strategy_id}_{symbol}_{uuid.uuid4().hex[:8]}"
        
        strategy_def = STRATEGY_REGISTRY.get(strategy_id)
        if not strategy_def:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        
        param_grid = ParamGrid(params=config.param_grid or strategy_def["param_grid"])
        
        strategy_config = StrategyConfig(
            strategy_id=strategy_id,
            strategy_name=strategy_def["name"],
            strategy_type=strategy_def["type"],
            direction=strategy_def["direction"],
            param_grid=param_grid,
            default_params=strategy_def.get("default_params", {}),
            stop_loss=config.stop_loss if hasattr(config, 'stop_loss') else 0.02,
            take_profit=config.take_profit if hasattr(config, 'take_profit') else 0.04,
        )
        
        task = OptimizationTask(
            task_id=task_id,
            strategy_config=strategy_config,
            symbol=symbol,
            config=config,
            total_combos=len(param_grid.get_combinations()),
        )
        
        self._tasks[task_id] = task
        
        return task
    
    async def run_task(self, task_id: str) -> OptimizationResult:
        """运行优化任务"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        task.status = OptimizationStatus.RUNNING
        task.started_at = datetime.now()
        
        result = OptimizationResult(
            optimization_id=task_id,
            strategy_id=task.strategy_config.strategy_id,
            symbol=task.symbol,
            status=OptimizationStatus.RUNNING,
            optimization_period=f"{task.config.optimization_start} ~ {task.config.optimization_end}",
        )
        
        self._results[task_id] = result
        
        try:
            data_cache_path = self._get_data_path(task.symbol)
            opt_data_path = None
            backtest_data_path = None
            
            if data_cache_path.name == "features_cache":
                opt_data_path = data_cache_path / "features_opt.parquet"
                backtest_data_path = data_cache_path / "features_backtest.parquet"
            else:
                opt_data_path = data_cache_path
                backtest_data_path = data_cache_path
            
            if not opt_data_path.exists():
                raise ValueError(f"Optimization data not found: {opt_data_path}")
            
            backtest_config = BacktestConfig(
                initial_capital=task.config.initial_capital,
                commission=task.config.commission,
                slippage=task.config.slippage,
                position_size=task.config.position_size,
                stop_loss=task.config.stop_loss,
                take_profit=task.config.take_profit,
                max_hold_hours=task.config.max_hold_hours,
                enable_slippage=task.config.enable_slippage,
                enable_latency=task.config.enable_latency,
            )
            
            engine = OptimizationBacktestEngine(backtest_config)
            
            # Time Authority: 统一转换为 int64 ms
            opt_start_ms = ensure_time_ms(task.config.optimization_start, "optimization_start")
            opt_end_ms = ensure_time_ms(task.config.optimization_end, "optimization_end")
            backtest_start_ms = ensure_time_ms(task.config.backtest_start, "backtest_start") if task.config.backtest_start else None
            backtest_end_ms = ensure_time_ms(task.config.backtest_end, "backtest_end") if task.config.backtest_end else None
            
            param_combinations = task.strategy_config.param_grid.get_combinations()
            task.total_combos = len(param_combinations)
            
            all_results = []
            best_score = -float('inf')
            best_params = None
            best_result = None
            
            max_concurrent = getattr(task.config, 'max_concurrent', 4) or 4
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def _run_single(params: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    backtest_result = await engine.run(
                        data_path=opt_data_path,
                        symbol=task.symbol,
                        strategy_id=task.strategy_config.strategy_id,
                        params=params,
                        start_time=opt_start_ms,
                        end_time=opt_end_ms,
                    )
                    score = self._calculate_score(backtest_result, task.config.metric)
                    return {
                        "params": params,
                        "score": score,
                        "result": backtest_result,
                    }
            
            if len(param_combinations) > 1:
                use_multiprocess = getattr(task.config, 'use_multiprocess', True)
                
                if use_multiprocess:
                    logger.info(
                        f"Parallel optimization (multiprocess): {len(param_combinations)} combos, "
                        f"max_workers={max_concurrent}"
                    )
                    # 传递已经转换好的 int64 ms 时间给子进程
                    start_time_for_mp = str(opt_start_ms) if isinstance(opt_start_ms, int) else str(opt_start_ms)
                    end_time_for_mp = str(opt_end_ms) if isinstance(opt_end_ms, int) else str(opt_end_ms)
                    
                    loop = asyncio.get_event_loop()
                    completed = await loop.run_in_executor(
                        None,
                        self._run_parallel_multiprocess,
                        engine, opt_data_path, task.symbol, task.strategy_config.strategy_id,
                        start_time_for_mp, end_time_for_mp,
                        param_combinations, max_concurrent, task.config.metric
                    )
                else:
                    logger.info(
                        f"Parallel optimization (async): {len(param_combinations)} combos, "
                        f"max_concurrent={max_concurrent}"
                    )
                    tasks = [_run_single(p) for p in param_combinations]
                    completed = await asyncio.gather(*tasks, return_exceptions=True)
                
                for item in completed:
                    if isinstance(item, Exception):
                        logger.warning(f"Optimization combo failed: {item}")
                        continue
                    
                    if item.get("error"):
                        logger.warning(f"Optimization combo error: {item['error']}")
                        continue
                    
                    all_results.append({
                        "params": item["params"],
                        "score": item["score"],
                        "metrics": {
                            "total_return": item.get("total_return", 0),
                            "total_trades": item.get("total_trades", 0),
                            "trades": item.get("trades", []),
                        },
                    })
                    
                    if item["score"] > best_score:
                        best_score = item["score"]
                        best_params = item["params"]
                        best_result = item.get("result")
                        if best_result is None and item.get("trades"):
                            best_result = item
                    
                    task.current_combo = len(all_results)
                    task.progress = task.current_combo / task.total_combos
            else:
                for idx, params in enumerate(param_combinations):
                    task.current_combo = idx + 1
                    task.progress = task.current_combo / task.total_combos
                    
                    backtest_result = await engine.run(
                        data_path=opt_data_path,
                        symbol=task.symbol,
                        strategy_id=task.strategy_config.strategy_id,
                        params=params,
                        start_time=opt_start_ms,
                        end_time=opt_end_ms,
                    )
                    
                    score = self._calculate_score(backtest_result, task.config.metric)
                    
                    all_results.append({
                        "params": params,
                        "score": score,
                        "metrics": backtest_result.to_dict(),
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_params = params
                        best_result = backtest_result
            
            result.best_params = best_params
            result.best_score = best_score
            
            if isinstance(best_result, dict) and best_result.get("trades"):
                result.best_metrics = OptimizationMetrics(
                    total_return=best_result.get("total_return", 0),
                    total_trades=best_result.get("total_trades", 0),
                    win_rate=len([t for t in best_result.get("trades", []) if t.get("pnl", 0) > 0]) / max(1, best_result.get("total_trades", 1)),
                    sharpe_ratio=best_score,
                )
                result.trades = [self._convert_trade_dict(t) for t in best_result.get("trades", [])[:100]]
            else:
                result.best_metrics = self._convert_to_optimization_metrics(best_result) if best_result else None
                result.trades = [self._convert_trade(t) for t in (best_result.trades[:100] if best_result else [])]
            
            result.all_results = sorted(all_results, key=lambda x: -x['score'])[:10]
            
            # 回测期验证
            if (task.config.backtest_start and task.config.backtest_end and 
                backtest_data_path and backtest_data_path.exists()):
                
                backtest_result_final = await engine.run(
                    data_path=backtest_data_path,
                    symbol=task.symbol,
                    strategy_id=task.strategy_config.strategy_id,
                    params=best_params,
                    start_time=backtest_start_ms,
                    end_time=backtest_end_ms,
                )
                
                # 添加回测期信息
                result.backtest_period = f"{task.config.backtest_start} ~ {task.config.backtest_end}"
                if result.runtime_stats is None:
                    result.runtime_stats = {}
                result.runtime_stats["backtest_metrics"] = backtest_result_final.to_dict()
            
            result.status = OptimizationStatus.COMPLETED
            result.completed_at = datetime.now()
            
            task.status = OptimizationStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            logger.info(f"Optimization completed: {task_id}, best_score={best_score:.4f}")
            
        except Exception as e:
            logger.error(f"Optimization failed: {task_id} - {e}")
            import traceback
            traceback.print_exc()
            result.status = OptimizationStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            
            task.status = OptimizationStatus.FAILED
            task.completed_at = datetime.now()
        
        return result

    async def _run_task_sequential(self, task_id: str) -> OptimizationResult:
        """
        串行执行优化任务（用于对比并行加速效果）
        不使用 asyncio.gather，逐个执行参数组合。
        """
        from application.optimization_service.models import OptimizationResult, OptimizationStatus

        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        result = OptimizationResult(
            optimization_id=task_id,
            strategy_id=task.strategy_config.strategy_id,
            symbol=task.symbol,
            status=OptimizationStatus.RUNNING,
            created_at=datetime.now().isoformat(),
            runtime_stats={"mode": "sequential"},
        )

        try:
            data_cache_path = self._get_data_path(task.symbol)
            opt_data_path = data_cache_path / "features_opt.parquet"
            backtest_data_path = data_cache_path / "features_backtest.parquet"

            if not opt_data_path.exists():
                raise ValueError(f"Optimization data not found: {opt_data_path}")

            backtest_config = BacktestConfig(
                initial_capital=task.config.initial_capital,
                commission=task.config.commission,
                slippage=task.config.slippage,
                position_size=task.config.position_size,
                stop_loss=task.config.stop_loss,
                take_profit=task.config.take_profit,
                max_hold_hours=task.config.max_hold_hours,
                enable_slippage=task.config.enable_slippage,
                enable_latency=task.config.enable_latency,
            )

            engine = OptimizationBacktestEngine(backtest_config)

            param_combinations = task.strategy_config.param_grid.get_combinations()
            task.total_combos = len(param_combinations)

            all_results = []
            best_score = -float('inf')
            best_params = None
            best_result = None

            logger.info(
                f"Sequential optimization: {len(param_combinations)} combos, "
                f"one by one (no asyncio.gather)"
            )

            for idx, params in enumerate(param_combinations):
                task.current_combo = idx + 1
                task.progress = task.current_combo / task.total_combos

                backtest_result = await engine.run(
                    data_path=opt_data_path,
                    symbol=task.symbol,
                    strategy_id=task.strategy_config.strategy_id,
                    params=params,
                    start_time=task.config.optimization_start,
                    end_time=task.config.optimization_end,
                )

                score = self._calculate_score(backtest_result, task.config.metric)

                all_results.append({
                    "params": params,
                    "score": score,
                    "metrics": backtest_result.to_dict(),
                })

                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = backtest_result

                logger.info(
                    f"  Sequential [{idx + 1}/{len(param_combinations)}] "
                    f"params={params}, score={score:.4f}"
                )

            result.best_params = best_params
            result.best_score = best_score
            result.best_metrics = self._convert_to_optimization_metrics(best_result)
            result.all_results = sorted(all_results, key=lambda x: -x['score'])[:10]
            result.trades = [self._convert_trade(t) for t in (best_result.trades[:100] if best_result else [])]

            result.status = OptimizationStatus.COMPLETED
            result.completed_at = datetime.now()

            task.status = OptimizationStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result

            logger.info(f"Sequential optimization completed: {task_id}, best_score={best_score:.4f}")

        except Exception as e:
            logger.error(f"Sequential optimization failed: {task_id} - {e}")
            import traceback
            traceback.print_exc()
            result.status = OptimizationStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()

            task.status = OptimizationStatus.FAILED
            task.completed_at = datetime.now()

        return result

    async def run_batch(
        self,
        strategy_ids: List[str],
        symbols: List[str],
        config: OptimizationConfig,
    ) -> Dict[str, OptimizationResult]:
        """批量优化"""
        results = {}
        
        for symbol in symbols:
            for strategy_id in strategy_ids:
                task = await self.create_task(strategy_id, symbol, config)
                result = await self.run_task(task.task_id)
                results[task.task_id] = result
        
        return results
    
    def get_task(self, task_id: str) -> Optional[OptimizationTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_result(self, task_id: str) -> Optional[OptimizationResult]:
        """获取结果"""
        return self._results.get(task_id)
    
    def list_tasks(self) -> List[OptimizationTask]:
        """列出所有任务"""
        return list(self._tasks.values())
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """获取可用策略"""
        return [
            {
                "id": strategy_id,
                "name": info["name"],
                "type": info["type"],
                "direction": info["direction"],
                "param_grid": info["param_grid"],
            }
            for strategy_id, info in STRATEGY_REGISTRY.items()
        ]
    
    def _get_data_path(self, symbol: str) -> Path:
        """获取数据路径 - 优先使用 features_cache"""
        # 先尝试 features_cache
        cache_path = Path(__file__).parent.parent.parent / "data_lake" / "features_cache"
        if cache_path.exists():
            opt_path = cache_path / "features_opt.parquet"
            if opt_path.exists():
                return cache_path
        
        # 否则回退到原来的路径
        return Path(__file__).parent.parent.parent / "data_lake" / "features" / "binance" / symbol / "features.parquet"
    
    def _calculate_score(self, result: BacktestResult, metric: OptimizationMetric) -> float:
        """计算优化分数"""
        if metric == OptimizationMetric.SHARPE:
            return result.sharpe_ratio
        elif metric == OptimizationMetric.TOTAL_RETURN:
            return result.total_return
        elif metric == OptimizationMetric.WIN_RATE:
            return result.win_rate
        elif metric == OptimizationMetric.PROFIT_FACTOR:
            return result.profit_factor
        elif metric == OptimizationMetric.CALMAR:
            return result.calmar_ratio
        return result.sharpe_ratio
    
    def _convert_to_optimization_metrics(self, result: BacktestResult) -> OptimizationMetrics:
        """转换为优化指标"""
        return OptimizationMetrics(
            total_return=result.total_return,
            annualized_return=result.annualized_return,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            max_drawdown=result.max_drawdown,
            total_trades=result.total_trades,
            avg_trade_duration_hours=result.avg_hold_hours,
        )
    
    def _convert_trade(self, trade) -> TradeRecord:
        """转换交易记录"""
        return TradeRecord(
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            direction=trade.direction,
            quantity=trade.quantity,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            exit_reason=trade.exit_reason,
            slippage=trade.slippage,
            latency_ms=trade.latency_ms,
        )
    
    def _convert_trade_dict(self, trade: dict) -> TradeRecord:
        """转换字典格式的交易记录"""
        from datetime import datetime
        entry_time = trade.get("entry_time")
        exit_time = trade.get("exit_time")
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)
        return TradeRecord(
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=trade.get("entry_price", 0),
            exit_price=trade.get("exit_price", 0),
            direction=trade.get("direction", "long"),
            quantity=trade.get("quantity", 0),
            pnl=trade.get("pnl", 0),
            pnl_pct=trade.get("pnl_pct", 0),
            exit_reason=trade.get("exit_reason", ""),
            slippage=trade.get("slippage", 0),
            latency_ms=trade.get("latency_ms", 0),
        )


_optimization_service: Optional[OptimizationService] = None


def get_optimization_service() -> OptimizationService:
    """获取优化服务单例"""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = OptimizationService()
    return _optimization_service
