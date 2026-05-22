"""
Backtest Service - 统一回测服务（Application 层）

职责边界（Application 层）：
- use-case orchestration（多个 Service 组合）
- 不维护任何 state
- 不直接执行回测，委托 ReplayRuntime

禁止在 Application 层：
- 直接创建 ReplayRuntime 实例
- 直接读取 parquet 文件
- 维护 equity curve / trades / metrics state
- asyncio.gather() 直接调度多个回测

执行流程：
    API Router
      ↓
    RuntimeBus.publish_command(run_backtest)
      ↓
    BacktestService (Application 层，orchestration)
      ↓
    BacktestManager (Service 层，task persistence)
      ↓
    ReplayRuntime (Runtime 层，唯一 execution source)
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from infrastructure.logging import get_logger

logger = get_logger("backtest_service")


@dataclass
class BacktestConfig:
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
    "rsi_oversold": {"name": "RSI Oversold", "direction": "long", "default_params": {"period": 14, "oversold": 30}},
    "rsi_overbought": {"name": "RSI Overbought", "direction": "short", "default_params": {"period": 14, "overbought": 70}},
    "macd_cross": {"name": "MACD Cross", "direction": "both", "default_params": {}},
    "sma_cross": {"name": "SMA Cross", "direction": "both", "default_params": {"fast": 10, "slow": 50}},
    "ema_cross": {"name": "EMA Cross", "direction": "both", "default_params": {"fast": 10, "slow": 50}},
    "bollinger_bands": {"name": "Bollinger Bands", "direction": "both", "default_params": {}},
}


class BacktestService:

    def __init__(self):
        pass

    async def run_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> BacktestResult:
        from runtime.bus.runtime_bus import get_runtime_bus

        strategy = STRATEGY_REGISTRY.get(strategy_id)
        if not strategy:
            raise ValueError(f"Unknown strategy: {strategy_id}")

        params = params or strategy["default_params"]

        bus = get_runtime_bus()
        await bus.publish_command(
            command="run_backtest",
            target="replay_runtime",
            params={
                "symbol": symbol,
                "strategy_id": strategy_id,
                "params": params,
                "start_time": start_time,
                "end_time": end_time,
            },
            source="application.backtest_service",
        )

        from api.services.backtest_service import get_backtest_manager
        manager = get_backtest_manager()
        await manager.ensure_connection()

        backtest_id = f"bt_{strategy_id}_{symbol}_{datetime.now().timestamp():.0f}"
        config = {
            "symbol": symbol,
            "strategy_id": strategy_id,
            "params": params,
            "start_time": start_time,
            "end_time": end_time,
        }
        await manager.start(backtest_id, config)

        return BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
        )

    async def run_batch(
        self,
        symbols: List[str],
        strategy_ids: List[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict[str, BacktestResult]:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        results = {}

        for symbol in symbols:
            for strategy_id in strategy_ids:
                backtest_id = f"bt_{strategy_id}_{symbol}_{datetime.now().timestamp():.0f}"
                config = {
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "start_time": start_time,
                    "end_time": end_time,
                }

                await bus.publish_command(
                    command="run_backtest",
                    target="replay_runtime",
                    params=config,
                    source="application.backtest_service",
                )

                from api.services.backtest_service import get_backtest_manager
                manager = get_backtest_manager()
                await manager.ensure_connection()
                await manager.start(backtest_id, config)

                results[f"{symbol}_{strategy_id}"] = BacktestResult(
                    symbol=symbol,
                    strategy_id=strategy_id,
                    params={},
                )

        return results

    def get_available_strategies(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": strategy_id,
                "name": info["name"],
                "direction": info["direction"],
                "default_params": info["default_params"],
            }
            for strategy_id, info in STRATEGY_REGISTRY.items()
        ]
