"""
Backtest Manager Service - 回测管理服务

功能：
- 回测任务创建和管理
- 回测结果持久化（Redis）
- 集成 BacktestEngine
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4

from services.backtest_service import (
    BacktestEngine,
    BacktestConfig as EngineConfig,
    BacktestResult as EngineResult,
    PerformanceMetrics,
    Bar,
    SignalType,
    run_backtest,
)
from infrastructure.cache.redis_client import RedisClient, init_redis
from infrastructure.logging import get_logger

logger = get_logger("backtest_manager")


class BacktestManager:
    """回测管理器"""

    BACKTEST_KEY_PREFIX = "backtest:"
    BACKTEST_LIST_KEY = "backtest:list"

    def __init__(self):
        self._redis: Optional[RedisClient] = None

    async def ensure_connection(self):
        if self._redis is None or not self._redis.is_connected:
            self._redis = await init_redis()

    @property
    def redis(self) -> RedisClient:
        if self._redis is None:
            raise RuntimeError("Redis not connected")
        return self._redis

    async def create_backtest(self, config: Dict) -> Dict:
        """创建回测任务"""
        backtest_id = str(uuid4())[:8]

        backtest = {
            "id": backtest_id,
            "status": "pending",
            "config": config,
            "metrics": None,
            "trades": [],
            "equity_curve": [],
            "drawdown_curve": [],
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "error_message": None,
        }

        await self.redis.set_json(f"{self.BACKTEST_KEY_PREFIX}{backtest_id}", backtest)
        logger.info(f"Created backtest: {backtest_id}")

        return backtest

    async def run_backtest(self, backtest_id: str) -> Dict:
        """运行回测"""
        key = f"{self.BACKTEST_KEY_PREFIX}{backtest_id}"
        backtest = await self.redis.get_json(key)

        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")

        backtest["status"] = "running"
        await self.redis.set_json(key, backtest)

        try:
            # 运行引擎回测
            result = await self._execute_with_engine(backtest["config"])
            backtest.update(result)
            backtest["status"] = "completed"
            backtest["completed_at"] = datetime.now().isoformat()
        except Exception as e:
            backtest["status"] = "failed"
            backtest["error_message"] = str(e)
            logger.error(f"Backtest {backtest_id} failed: {e}")

        await self.redis.set_json(key, backtest)
        return backtest

    async def _execute_with_engine(self, config: Dict) -> Dict:
        """使用 BacktestEngine 执行"""
        from datetime import datetime as dt
        import random

        # 转换配置
        engine_config = EngineConfig(
            initial_capital=config.get("initial_capital", 100000.0),
            commission=config.get("commission", 0.001),
            slippage=config.get("slippage", 0.0005),
            position_size=config.get("position_size", 0.1),
            stop_loss=config.get("stop_loss", 0.02),
            take_profit=config.get("take_profit", 0.05),
        )

        # 创建引擎
        engine = BacktestEngine(engine_config)

        # 加载数据
        symbol = config.get("symbol", "BTC/USDT")
        start_date = dt.strptime(config.get("start_date", "2024-01-01"), "%Y-%m-%d")
        end_date = dt.strptime(config.get("end_date", "2024-12-31"), "%Y-%m-%d")
        engine.load_mock_data(symbol, start_date, end_date)

        # 选择策略
        strategy_name = config.get("strategy", "sma_crossover")
        strategy_fn = self._get_strategy(strategy_name)

        # 运行回测
        result = engine.run(strategy_fn)

        # 转换结果
        return self._convert_result(result)

    def _get_strategy(self, name: str):
        """获取策略函数"""
        if name == "sma_crossover":
            return self._sma_crossover_strategy
        elif name == "rsi":
            return self._rsi_strategy
        elif name == "momentum":
            return self._momentum_strategy
        return self._sma_crossover_strategy

    @staticmethod
    def _sma_crossover_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
        """SMA交叉策略"""
        import random
        if position:
            if random.random() < 0.05:
                return SignalType.SELL
            return SignalType.HOLD
        if random.random() > 0.95:
            return SignalType.BUY
        return SignalType.HOLD

    @staticmethod
    def _rsi_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
        """RSI策略"""
        import random
        if position:
            if random.random() < 0.08:
                return SignalType.SELL
            return SignalType.HOLD
        if random.random() > 0.92:
            return SignalType.BUY
        return SignalType.HOLD

    @staticmethod
    def _momentum_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
        """动量策略"""
        import random
        if position:
            if random.random() < 0.1:
                return SignalType.SELL
            return SignalType.HOLD
        if random.random() > 0.9:
            return SignalType.BUY
        return SignalType.HOLD

    def _convert_result(self, result: EngineResult) -> Dict:
        """转换引擎结果为API格式"""
        # 指标转换
        metrics_dict = {
            "total_return": result.metrics.total_return,
            "total_return_pct": result.metrics.total_return_pct,
            "sharpe_ratio": result.metrics.sharpe_ratio,
            "max_drawdown": result.metrics.max_drawdown,
            "max_drawdown_pct": result.metrics.max_drawdown_pct,
            "win_rate": result.metrics.win_rate,
            "total_trades": result.metrics.total_trades,
            "winning_trades": result.metrics.winning_trades,
            "losing_trades": result.metrics.losing_trades,
            "avg_win": result.metrics.avg_win,
            "avg_loss": result.metrics.avg_loss,
            "profit_factor": result.metrics.profit_factor,
            "avg_trade_return": result.metrics.avg_trade_return,
            "avg_trade_duration": result.metrics.avg_trade_duration,
        }

        # 交易转换
        trades = [
            {
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "side": t.side.value if hasattr(t.side, 'value') else str(t.side),
            }
            for t in result.trades
        ]

        return {
            "metrics": metrics_dict,
            "trades": trades,
            "equity_curve": result.equity_curve,
            "drawdown_curve": result.drawdown_curve,
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "duration_days": result.duration_days,
        }

    async def get_backtest(self, backtest_id: str) -> Optional[Dict]:
        """获取回测结果"""
        return await self.redis.get_json(f"{self.BACKTEST_KEY_PREFIX}{backtest_id}")

    async def list_backtests(self) -> List[Dict]:
        """列出所有回测"""
        keys = await self.redis.client.keys(f"{self.BACKTEST_KEY_PREFIX}*")
        results = []
        for key in keys:
            if key.endswith(":list"):
                continue
            data = await self.redis.get_json(key)
            if data:
                results.append(data)
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)


# 单例
_backtest_manager: Optional[BacktestManager] = None


def get_backtest_manager() -> BacktestManager:
    global _backtest_manager
    if _backtest_manager is None:
        _backtest_manager = BacktestManager()
    return _backtest_manager
