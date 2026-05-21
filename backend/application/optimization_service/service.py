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

from .engine import OptimizationBacktestEngine, BacktestConfig, BacktestResult
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
            data_path = self._get_data_path(task.symbol)
            
            if not data_path.exists():
                raise ValueError(f"Data not found: {data_path}")
            
            backtest_config = BacktestConfig(
                initial_capital=task.config.initial_capital,
                commission=task.config.commission,
                slippage=task.config.slippage,
                position_size=task.config.position_size,
                stop_loss=task.strategy_config.stop_loss,
                take_profit=task.strategy_config.take_profit,
                max_hold_hours=task.strategy_config.max_hold_hours,
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
            
            for idx, params in enumerate(param_combinations):
                task.current_combo = idx + 1
                task.progress = task.current_combo / task.total_combos
                
                backtest_result = await engine.run(
                    parquet_path=data_path,
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
            
            logger.info(f"Optimization completed: {task_id}, best_score={best_score:.4f}")
            
        except Exception as e:
            logger.error(f"Optimization failed: {task_id} - {e}")
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
        """获取数据路径"""
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


_optimization_service: Optional[OptimizationService] = None


def get_optimization_service() -> OptimizationService:
    """获取优化服务单例"""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = OptimizationService()
    return _optimization_service
