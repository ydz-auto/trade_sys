"""
Parallel Backtest Engine - 并行回测引擎

支持：
1. 多进程并行（CPU）
2. GPU 加速特征计算
3. 参数网格并行优化

用法：
    from application.optimization_service.parallel_engine import ParallelBacktestEngine
    
    engine = ParallelBacktestEngine(config)
    
    # 并行优化
    results = await engine.optimize_parallel(
        symbol="BTCUSDT",
        strategy_id="rsi_oversold",
        param_grid=[{"period": 14}, {"period": 21}],
        start_time=...,
        end_time=...,
        n_workers=8,
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import asyncio
import pandas as pd
import numpy as np
import time

from infrastructure.logging import get_logger
from shared.acceleration import is_gpu_available, get_backend_info
from shared.progress import ProgressTracker, ProgressType, ProgressBar, get_progress_tracker

logger = get_logger("parallel_backtest_engine")


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    latency_ms: float = 50.0
    position_size: float = 0.3
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_hold_hours: int = 48
    leverage: float = 1.0
    
    enable_slippage: bool = True
    enable_latency: bool = True
    enable_partial_fill: bool = True
    enable_feature_guard: bool = True
    use_gpu: bool = True


@dataclass
class BacktestTrade:
    """回测交易记录"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    direction: str
    pnl: float
    pnl_pct: float
    exit_reason: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    strategy_id: str
    params: Dict[str, Any]
    
    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_hold_hours: float = 0.0
    
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    compute_time_ms: float = 0.0


def run_single_backtest(
    data_path: str,
    symbol: str,
    strategy_id: str,
    params: Dict[str, Any],
    config: BacktestConfig,
    start_time: int,
    end_time: int,
) -> BacktestResult:
    """
    单次回测（用于多进程）
    
    这个函数在子进程中运行，所以必须是独立的。
    """
    import pandas as pd
    import numpy as np
    from datetime import datetime
    
    start_compute = time.time()
    
    df = pd.read_parquet(data_path)
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    elif 'open_time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    start_dt = pd.Timestamp(start_time, unit='ms') if isinstance(start_time, int) else pd.Timestamp(start_time)
    end_dt = pd.Timestamp(end_time, unit='ms') if isinstance(end_time, int) else pd.Timestamp(end_time)
    
    df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
    
    capital = config.initial_capital
    position = None
    trades = []
    equity_curve = [config.initial_capital]
    
    def get_signal(row, params, strategy_id):
        if strategy_id == "rsi_oversold":
            period = params.get("period", 14)
            oversold = params.get("oversold", 30)
            rsi = row.get(f"rsi_{period}", 50)
            return 1 if rsi < oversold else 0
        elif strategy_id == "rsi_overbought":
            period = params.get("period", 14)
            overbought = params.get("overbought", 70)
            rsi = row.get(f"rsi_{period}", 50)
            return -1 if rsi > overbought else 0
        elif strategy_id == "sma_cross":
            fast = params.get("fast", 10)
            slow = params.get("slow", 50)
            sma_fast = row.get(f"sma_{fast}", 0)
            sma_slow = row.get(f"sma_{slow}", 0)
            if sma_fast > sma_slow:
                return 1
            elif sma_fast < sma_slow:
                return -1
        elif strategy_id == "ema_cross":
            fast = params.get("fast", 10)
            slow = params.get("slow", 50)
            ema_fast = row.get(f"ema_{fast}", 0)
            ema_slow = row.get(f"ema_{slow}", 0)
            if ema_fast > ema_slow:
                return 1
            elif ema_fast < ema_slow:
                return -1
        elif strategy_id == "bollinger_bands":
            bb_upper = row.get("bb_upper", 0)
            bb_lower = row.get("bb_lower", 0)
            close = row.get("close", 0)
            if close < bb_lower:
                return 1
            elif close > bb_upper:
                return -1
        elif strategy_id == "macd_cross":
            macd = row.get("macd", 0)
            macd_signal = row.get("macd_signal", 0)
            if macd > macd_signal:
                return 1
            elif macd < macd_signal:
                return -1
        return 0
    
    def apply_slippage(price, direction, config):
        if not config.enable_slippage:
            return price
        slippage = config.slippage * (1 + np.random.uniform(-0.5, 0.5))
        if direction > 0:
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)
    
    for idx, row in df.iterrows():
        current_price = float(row.get('close', 0))
        current_time = row.get('timestamp')
        
        if position:
            entry_price = position["entry_price"]
            direction = position["direction"]
            
            if direction == "long":
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            exit_reason = None
            
            if pnl_pct <= -config.stop_loss:
                exit_reason = "stop_loss"
            elif pnl_pct >= config.take_profit:
                exit_reason = "take_profit"
            else:
                hold_hours = (current_time - position["entry_time"]).total_seconds() / 3600
                if hold_hours >= config.max_hold_hours:
                    exit_reason = "time"
            
            if exit_reason:
                exit_price = apply_slippage(current_price, -1 if direction == "long" else 1, config)
                
                if direction == "long":
                    final_pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    final_pnl_pct = (entry_price - exit_price) / entry_price
                
                pnl = position["quantity"] * entry_price * final_pnl_pct
                capital += position["quantity"] * entry_price + pnl
                
                trades.append(BacktestTrade(
                    entry_time=position["entry_time"],
                    exit_time=current_time,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=position["quantity"],
                    direction=direction,
                    pnl=pnl,
                    pnl_pct=final_pnl_pct,
                    exit_reason=exit_reason,
                    params=params,
                ))
                
                position = None
        
        if position is None:
            signal = get_signal(row, params, strategy_id)
            
            if signal != 0:
                entry_price = apply_slippage(current_price, signal, config)
                position_size = capital * config.position_size
                
                position = {
                    "entry_time": current_time,
                    "entry_price": entry_price,
                    "quantity": position_size / entry_price,
                    "direction": "long" if signal > 0 else "short",
                }
                
                capital -= position_size
        
        equity = capital
        if position:
            if position["direction"] == "long":
                unrealized_pnl = (current_price - position["entry_price"]) / position["entry_price"]
            else:
                unrealized_pnl = (position["entry_price"] - current_price) / position["entry_price"]
            equity += position["quantity"] * position["entry_price"] * unrealized_pnl
        
        equity_curve.append(equity)
    
    if position:
        last_price = float(df.iloc[-1]['close'])
        exit_price = apply_slippage(last_price, -1 if position["direction"] == "long" else 1, config)
        
        if position["direction"] == "long":
            final_pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"]
        else:
            final_pnl_pct = (position["entry_price"] - exit_price) / exit_price
        
        pnl = position["quantity"] * position["entry_price"] * final_pnl_pct
        
        trades.append(BacktestTrade(
            entry_time=position["entry_time"],
            exit_time=df.iloc[-1]['timestamp'],
            entry_price=position["entry_price"],
            exit_price=exit_price,
            quantity=position["quantity"],
            direction=position["direction"],
            pnl=pnl,
            pnl_pct=final_pnl_pct,
            exit_reason="end",
            params=params,
        ))
    
    total_return = (capital - config.initial_capital) / config.initial_capital
    
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    
    win_rate = len(wins) / len(trades) if trades else 0
    
    total_wins = sum(t.pnl_pct for t in wins)
    total_losses = abs(sum(t.pnl_pct for t in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    returns = [t.pnl_pct for t in trades]
    sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if returns else 0
    
    negative_returns = [r for r in returns if r < 0]
    sortino = np.mean(returns) / (np.std(negative_returns) + 1e-10) * np.sqrt(252) if negative_returns else sharpe
    
    peak = config.initial_capital
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    
    calmar = (total_return * 252 / 365) / max_dd if max_dd > 0 else 0
    
    avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
    avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
    avg_hold = np.mean([(t.exit_time - t.entry_time).total_seconds() / 3600 for t in trades]) if trades else 0
    
    compute_time = (time.time() - start_compute) * 1000
    
    return BacktestResult(
        symbol=symbol,
        strategy_id=strategy_id,
        params=params,
        total_return=total_return,
        annualized_return=total_return * 252 / 365,
        win_rate=win_rate,
        profit_factor=profit_factor,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_dd,
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        avg_win=avg_win,
        avg_loss=avg_loss,
        avg_hold_hours=avg_hold,
        trades=trades,
        equity_curve=equity_curve,
        compute_time_ms=compute_time,
    )


class ParallelBacktestEngine:
    """
    并行回测引擎
    
    支持：
    - 多进程并行优化
    - 自动检测 CPU 核心数
    - GPU 特征计算加速
    """
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.is_gpu = is_gpu_available()
        
        backend_info = get_backend_info()
        logger.info(f"ParallelBacktestEngine initialized: {backend_info}")
    
    async def optimize_parallel(
        self,
        symbol: str,
        strategy_id: str,
        param_grid: List[Dict[str, Any]],
        start_time: int,
        end_time: int,
        data_path: Optional[Path] = None,
        n_workers: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[BacktestResult]:
        """
        并行优化参数
        
        Args:
            symbol: 交易对
            strategy_id: 策略 ID
            param_grid: 参数组合列表
            start_time: 开始时间戳
            end_time: 结束时间戳
            data_path: 数据路径
            n_workers: 并行进程数（默认自动检测）
            progress_callback: 进度回调函数 (current, total, message)
        
        Returns:
            回测结果列表
        """
        data_path = data_path or self._get_default_data_path(symbol)
        
        if not data_path.exists():
            logger.error(f"Data not found: {data_path}")
            return []
        
        if n_workers is None:
            import os
            n_workers = min(os.cpu_count() or 4, len(param_grid), 16)
        
        tracker = get_progress_tracker()
        task_id = tracker.create_task(
            ProgressType.OPTIMIZATION,
            total=len(param_grid),
            message=f"Optimizing {strategy_id} for {symbol}",
            metadata={"symbol": symbol, "strategy_id": strategy_id, "n_workers": n_workers},
        )
        
        bar = ProgressBar(total=len(param_grid), desc=f"Optimizing {strategy_id}")
        
        logger.info(f"Starting parallel optimization: {len(param_grid)} params, {n_workers} workers")
        
        start_time_total = time.time()
        
        loop = asyncio.get_event_loop()
        
        results = []
        completed = 0
        
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {}
            for i, params in enumerate(param_grid):
                future = loop.run_in_executor(
                    executor,
                    run_single_backtest,
                    str(data_path),
                    symbol,
                    strategy_id,
                    params,
                    self.config,
                    start_time,
                    end_time,
                )
                futures[future] = (i, params)
            
            for future in asyncio.as_completed(futures.keys()):
                try:
                    result = await future
                    results.append(result)
                    completed += 1
                    
                    tracker.update(
                        task_id,
                        current=completed,
                        message=f"Completed {completed}/{len(param_grid)}",
                    )
                    bar.update(1, message=f"Sharpe={result.sharpe_ratio:.2f}")
                    
                    if progress_callback:
                        progress_callback(completed, len(param_grid), f"Sharpe={result.sharpe_ratio:.2f}")
                
                except Exception as e:
                    logger.error(f"Backtest failed: {e}")
                    completed += 1
                    tracker.update(task_id, current=completed, message=f"Failed: {e}")
        
        total_time = time.time() - start_time_total
        
        results = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
        
        if results:
            best = results[0]
            tracker.complete(
                task_id,
                result={
                    "best_sharpe": best.sharpe_ratio,
                    "best_return": best.total_return,
                    "best_params": best.params,
                    "total_time": total_time,
                },
                message=f"Best Sharpe={best.sharpe_ratio:.2f}",
            )
        else:
            tracker.fail(task_id, error="No results")
        
        logger.info(
            f"Optimization completed: {len(results)} results in {total_time:.2f}s "
            f"({len(results)/total_time:.1f} runs/sec)"
        )
        
        if results:
            best = results[0]
            logger.info(
                f"Best result: Sharpe={best.sharpe_ratio:.2f}, "
                f"Return={best.total_return*100:.1f}%, "
                f"Params={best.params}"
            )
        
        return results
    
    async def run_single(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start_time: int,
        end_time: int,
        data_path: Optional[Path] = None,
    ) -> BacktestResult:
        """单次回测"""
        data_path = data_path or self._get_default_data_path(symbol)
        
        return await asyncio.get_event_loop().run_in_executor(
            None,
            run_single_backtest,
            str(data_path),
            symbol,
            strategy_id,
            params,
            self.config,
            start_time,
            end_time,
        )
    
    def _get_default_data_path(self, symbol: str) -> Path:
        """获取默认数据路径"""
        return Path(__file__).parent.parent.parent / "data_lake" / "features" / "binance" / symbol / "features.parquet"


def generate_param_grid(
    strategy_id: str,
    ranges: Optional[Dict[str, List]] = None,
) -> List[Dict[str, Any]]:
    """
    生成参数网格
    
    Args:
        strategy_id: 策略 ID
        ranges: 参数范围（可选）
    
    Returns:
        参数组合列表
    """
    if strategy_id == "rsi_oversold" or strategy_id == "rsi_overbought":
        periods = ranges.get("period", [7, 14, 21]) if ranges else [7, 14, 21]
        thresholds = ranges.get("threshold", [20, 25, 30, 35]) if ranges else [20, 25, 30, 35]
        
        if strategy_id == "rsi_oversold":
            return [{"period": p, "oversold": t} for p in periods for t in thresholds]
        else:
            return [{"period": p, "overbought": 100 - t} for p in periods for t in thresholds]
    
    elif strategy_id == "sma_cross" or strategy_id == "ema_cross":
        fast_periods = ranges.get("fast", [5, 10, 20]) if ranges else [5, 10, 20]
        slow_periods = ranges.get("slow", [30, 50, 100]) if ranges else [30, 50, 100]
        
        grid = []
        for fast in fast_periods:
            for slow in slow_periods:
                if fast < slow:
                    grid.append({"fast": fast, "slow": slow})
        return grid
    
    elif strategy_id == "macd_cross":
        fast_periods = ranges.get("fast", [12]) if ranges else [12]
        slow_periods = ranges.get("slow", [26]) if ranges else [26]
        signal_periods = ranges.get("signal", [9]) if ranges else [9]
        
        return [
            {"fast": f, "slow": s, "signal": sig}
            for f in fast_periods
            for s in slow_periods
            for sig in signal_periods
            if f < s
        ]
    
    elif strategy_id == "bollinger_bands":
        windows = ranges.get("window", [10, 20, 30]) if ranges else [10, 20, 30]
        std_devs = ranges.get("std_dev", [1.5, 2.0, 2.5]) if ranges else [1.5, 2.0, 2.5]
        
        return [{"window": w, "std_dev": s} for w in windows for s in std_devs]
    
    return [{}]
