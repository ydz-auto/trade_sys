"""
Backtest Service - 统一回测服务

替代以下脚本：
- scripts/run_backtest.py
- scripts/run_full_backtest.py
- scripts/run_quick_backtest.py
- scripts/backtest_all_strategies.py
- scripts/backtest_strategies.py
- scripts/strategy_optimization_backtest.py
- scripts/strategy_optimization_backtest_fast.py

用法：
    # 命令行
    python -m application.backtest_service run --symbol BTCUSDT --strategy rsi_oversold
    
    # 代码
    from application.backtest_service import BacktestService
    service = BacktestService()
    result = await service.run_backtest(symbol, strategy_id, params)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
import pandas as pd
import numpy as np
import json

from infrastructure.logging import get_logger

logger = get_logger("backtest_service")


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.3
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_hold_hours: int = 48
    
    enable_slippage: bool = True
    enable_latency: bool = True
    enable_feature_guard: bool = True


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    strategy_id: str
    params: Dict[str, Any]
    
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    
    total_trades: int = 0
    trades: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "params": self.params,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
        }


STRATEGY_REGISTRY = {
    "rsi_oversold": {
        "name": "RSI Oversold",
        "direction": "long",
        "default_params": {"period": 14, "oversold": 30},
        "param_grid": {"period": [7, 14, 21], "oversold": [25, 30, 35]},
    },
    "rsi_overbought": {
        "name": "RSI Overbought",
        "direction": "short",
        "default_params": {"period": 14, "overbought": 70},
        "param_grid": {"period": [7, 14, 21], "overbought": [65, 70, 75]},
    },
    "macd_cross": {
        "name": "MACD Cross",
        "direction": "both",
        "default_params": {},
        "param_grid": {},
    },
    "sma_cross": {
        "name": "SMA Cross",
        "direction": "both",
        "default_params": {"fast": 10, "slow": 50},
        "param_grid": {"fast": [5, 10, 20], "slow": [30, 50, 100]},
    },
    "ema_cross": {
        "name": "EMA Cross",
        "direction": "both",
        "default_params": {"fast": 10, "slow": 50},
        "param_grid": {"fast": [5, 10, 20], "slow": [30, 50, 100]},
    },
    "bollinger_bands": {
        "name": "Bollinger Bands",
        "direction": "both",
        "default_params": {},
        "param_grid": {},
    },
}


class BacktestService:
    """
    统一回测服务
    
    替代多个回测脚本，确保：
    1. 走 Runtime Pipeline
    2. 使用 shared/replay/ 架构
    3. 防止数据泄漏
    """
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._engine = None
    
    async def initialize(self):
        """初始化回测引擎"""
        from application.optimization_service.engine import OptimizationBacktestEngine, BacktestConfig as EngineConfig
        
        engine_config = EngineConfig(
            initial_capital=self.config.initial_capital,
            commission=self.config.commission,
            slippage=self.config.slippage,
            position_size=self.config.position_size,
            stop_loss=self.config.stop_loss,
            take_profit=self.config.take_profit,
            max_hold_hours=self.config.max_hold_hours,
            enable_slippage=self.config.enable_slippage,
            enable_latency=self.config.enable_latency,
            enable_feature_guard=self.config.enable_feature_guard,
        )
        
        self._engine = OptimizationBacktestEngine(engine_config)
        await self._engine.initialize()
    
    async def run_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> BacktestResult:
        """
        运行回测
        
        替代 run_backtest.py, run_full_backtest.py
        """
        if self._engine is None:
            await self.initialize()
        
        strategy = STRATEGY_REGISTRY.get(strategy_id)
        if not strategy:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        
        params = params or strategy["default_params"]
        
        result = await self._engine.run(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
            start_time=start_time,
            end_time=end_time,
        )
        
        return BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
            total_return=result.total_return,
            sharpe_ratio=result.sharpe_ratio,
            win_rate=result.win_rate,
            max_drawdown=result.max_drawdown,
            total_trades=result.total_trades,
            trades=[t.__dict__ if hasattr(t, '__dict__') else t for t in result.trades],
        )
    
    async def run_batch(
        self,
        symbols: List[str],
        strategy_ids: List[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict[str, BacktestResult]:
        """
        批量回测
        
        替代 backtest_all_strategies.py
        """
        if self._engine is None:
            await self.initialize()
        
        results = {}
        
        for symbol in symbols:
            for strategy_id in strategy_ids:
                try:
                    result = await self.run_backtest(
                        symbol=symbol,
                        strategy_id=strategy_id,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    results[f"{symbol}_{strategy_id}"] = result
                except Exception as e:
                    logger.error(f"Backtest failed for {symbol}_{strategy_id}: {e}")
        
        return results
    
    async def optimize(
        self,
        symbol: str,
        strategy_id: str,
        start_time: int,
        end_time: int,
    ) -> Dict[str, Any]:
        """
        参数优化
        
        替代 strategy_optimization_backtest.py
        """
        if self._engine is None:
            await self.initialize()
        
        strategy = STRATEGY_REGISTRY.get(strategy_id)
        if not strategy:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        
        param_grid = strategy.get("param_grid", {})
        
        if not param_grid:
            return await self.run_backtest(symbol, strategy_id, start_time=start_time, end_time=end_time)
        
        from itertools import product
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        best_result = None
        best_score = -float('inf')
        all_results = []
        
        for combo in product(*param_values):
            params = dict(zip(param_names, combo))
            
            result = await self.run_backtest(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                start_time=start_time,
                end_time=end_time,
            )
            
            score = result.sharpe_ratio
            all_results.append({
                "params": params,
                "score": score,
                "result": result.to_dict(),
            })
            
            if score > best_score:
                best_score = score
                best_result = result
        
        return {
            "best_params": best_result.params if best_result else None,
            "best_score": best_score,
            "best_result": best_result.to_dict() if best_result else None,
            "all_results": sorted(all_results, key=lambda x: -x['score'])[:10],
        }
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """获取可用策略列表"""
        return [
            {
                "id": strategy_id,
                "name": info["name"],
                "direction": info["direction"],
                "default_params": info["default_params"],
                "param_grid": info["param_grid"],
            }
            for strategy_id, info in STRATEGY_REGISTRY.items()
        ]


async def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backtest Service")
    parser.add_argument("command", choices=["run", "batch", "optimize", "strategies"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--strategy", default="rsi_oversold")
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--strategies", nargs="+", default=["rsi_oversold", "macd_cross"])
    
    args = parser.parse_args()
    
    service = BacktestService()
    
    if args.command == "run":
        result = await service.run_backtest(
            symbol=args.symbol,
            strategy_id=args.strategy,
            start_time=args.start,
            end_time=args.end,
        )
        print(json.dumps(result.to_dict(), indent=2))
    
    elif args.command == "batch":
        results = await service.run_batch(
            symbols=args.symbols,
            strategy_ids=args.strategies,
            start_time=args.start,
            end_time=args.end,
        )
        for key, result in results.items():
            print(f"{key}: return={result.total_return:.2%}, sharpe={result.sharpe_ratio:.2f}")
    
    elif args.command == "optimize":
        result = await service.optimize(
            symbol=args.symbol,
            strategy_id=args.strategy,
            start_time=args.start,
            end_time=args.end,
        )
        print(json.dumps(result, indent=2, default=str))
    
    elif args.command == "strategies":
        strategies = service.get_available_strategies()
        print(json.dumps(strategies, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
