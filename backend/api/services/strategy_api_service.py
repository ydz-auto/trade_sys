"""
Strategy API Service - 策略管理 API 服务

职责：
- 策略发现
- 策略回测
- 策略配置管理
- 策略启用/停用
- 活跃策略查询
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from infrastructure.logging import get_logger

logger = get_logger("strategy_api_service")


class StrategyAPIService:
    """策略管理 API 服务"""

    def __init__(self):
        self._discovered_strategies: Dict[str, List[Dict]] = {}
        self._strategy_configs: Dict[str, Dict] = {}
        self._backtest_results: Dict[str, Dict] = {}
        self._active_strategies: Dict[str, Dict] = {}

    async def discover_strategies(self, symbol: str) -> Dict[str, Any]:
        """
        发现策略

        Args:
            symbol: 币种，如 BTCUSDT

        Returns:
            发现结果
        """
        from services.strategy_service.strategy_discovery import StrategyDiscoveryEngine

        try:
            engine = StrategyDiscoveryEngine(
                symbols=[symbol],
                min_win_rate=0.52,
                min_sample_size=50,
                min_avg_return=0.0001,
            )
            df = engine.load_market_data(symbol)
            
            if df.empty:
                return {
                    "symbol": symbol,
                    "strategies_found": 0,
                    "strategies": [],
                    "error": "No market data available",
                    "timestamp": datetime.now().isoformat(),
                }
            
            patterns = engine.discover_patterns(df, symbol)

            discovered = []
            for pattern in patterns:
                strategy_id = f"discovered_{symbol}_{pattern.pattern_id}"
                discovered.append({
                    "id": strategy_id,
                    "name": pattern.name,
                    "description": pattern.description,
                    "direction": pattern.direction,
                    "win_rate": pattern.win_rate,
                    "avg_return": pattern.avg_return,
                    "sample_size": pattern.sample_size,
                    "confidence": pattern.confidence,
                    "strength": pattern.strength.value,
                    "features": pattern.features,
                    "conditions": pattern.conditions,
                    "created_at": pattern.created_at.isoformat(),
                    "status": "discovered",
                })

            self._discovered_strategies[symbol] = discovered

            return {
                "symbol": symbol,
                "strategies_found": len(discovered),
                "strategies": discovered,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Strategy discovery error: {e}")
            return {
                "symbol": symbol,
                "strategies_found": 0,
                "strategies": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def get_discovered_strategies(self, symbol: str) -> List[Dict[str, Any]]:
        """获取已发现的策略"""
        return self._discovered_strategies.get(symbol, [])

    async def add_to_watchlist(self, strategy_id: str) -> Dict[str, Any]:
        """添加到观察列表"""
        for symbol_strategies in self._discovered_strategies.values():
            for strategy in symbol_strategies:
                if strategy["id"] == strategy_id:
                    strategy["in_watchlist"] = True
                    return {"success": True, "strategy_id": strategy_id}

        return {"success": False, "error": "Strategy not found"}

    async def remove_from_watchlist(self, strategy_id: str) -> Dict[str, Any]:
        """从观察列表移除"""
        for symbol_strategies in self._discovered_strategies.values():
            for strategy in symbol_strategies:
                if strategy["id"] == strategy_id:
                    strategy["in_watchlist"] = False
                    return {"success": True, "strategy_id": strategy_id}

        return {"success": False, "error": "Strategy not found"}

    async def run_backtest(
        self,
        strategy_id: str,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000,
    ) -> Dict[str, Any]:
        """
        运行回测

        Args:
            strategy_id: 策略ID
            symbol: 币种
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金

        Returns:
            回测结果
        """
        from services.strategy_service.strategy_discovery import StrategyDiscoveryEngine
        import pandas as pd

        backtest_id = f"bt_{uuid.uuid4().hex[:8]}"

        try:
            engine = StrategyDiscoveryEngine(
                symbols=[symbol],
                min_win_rate=0.52,
                min_sample_size=50,
                min_avg_return=0.0001,
            )
            df = engine.load_market_data(symbol)
            
            if df.empty:
                return {
                    "id": backtest_id,
                    "status": "failed",
                    "error_message": "No market data available for backtest",
                    "created_at": datetime.now().isoformat(),
                }
            
            if "future_ret_1h" not in df.columns:
                df["future_ret_1h"] = df["close"].pct_change(-12).shift(-12)
            
            patterns = engine.discover_patterns(df, symbol)
            
            target_pattern = None
            for pattern in patterns:
                strategy_prefix = f"discovered_{symbol}_{pattern.pattern_id}"
                if strategy_id == strategy_prefix or strategy_id == pattern.pattern_id:
                    target_pattern = pattern
                    break
            
            if target_pattern is None:
                return {
                    "id": backtest_id,
                    "status": "failed",
                    "error_message": f"Strategy {strategy_id} not found",
                    "created_at": datetime.now().isoformat(),
                }
            
            result = engine.backtest_pattern(df, target_pattern)

            backtest_result = {
                "id": backtest_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "status": "completed",
                "config": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "initial_capital": initial_capital,
                },
                "metrics": {
                    "total_return": result.get("total_return", 0.0),
                    "sharpe_ratio": result.get("sharpe", 0.0),
                    "max_drawdown": 0.0,
                    "win_rate": result.get("win_rate", 0.0),
                    "total_trades": result.get("sample_size", 0),
                },
                "trades": [],
                "equity_curve": [],
                "drawdown_curve": [],
                "start_date": start_date,
                "end_date": end_date,
                "duration_days": result.get("sample_size", 0),
                "created_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
            }

            self._backtest_results[backtest_id] = backtest_result
            return backtest_result

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return {
                "id": backtest_id,
                "status": "failed",
                "error_message": str(e),
                "created_at": datetime.now().isoformat(),
            }

    async def get_backtest(self, backtest_id: str) -> Optional[Dict[str, Any]]:
        """获取回测结果"""
        return self._backtest_results.get(backtest_id)

    async def list_backtests(self) -> List[Dict[str, Any]]:
        """列出所有回测"""
        return list(self._backtest_results.values())

    async def get_strategy_configs(self) -> List[Dict[str, Any]]:
        """获取所有策略配置"""
        return list(self._strategy_configs.values())

    async def get_strategy_config(self, strategy_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """获取策略配置"""
        key = f"{strategy_id}_{symbol}"
        return self._strategy_configs.get(key)

    async def update_strategy_config(
        self,
        strategy_id: str,
        symbol: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """更新策略配置"""
        key = f"{strategy_id}_{symbol}"
        self._strategy_configs[key] = {
            "strategy_id": strategy_id,
            "symbol": symbol,
            **config,
            "updated_at": datetime.now().isoformat(),
        }
        return {"success": True, "config": self._strategy_configs[key]}

    async def enable_strategy(self, strategy_id: str, symbol: str) -> Dict[str, Any]:
        """启用策略"""
        key = f"{strategy_id}_{symbol}"
        self._active_strategies[key] = {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "enabled": True,
            "enabled_at": datetime.now().isoformat(),
        }
        return {"success": True, "strategy_id": strategy_id, "symbol": symbol}

    async def disable_strategy(self, strategy_id: str, symbol: str) -> Dict[str, Any]:
        """停用策略"""
        key = f"{strategy_id}_{symbol}"
        if key in self._active_strategies:
            self._active_strategies[key]["enabled"] = False
            self._active_strategies[key]["disabled_at"] = datetime.now().isoformat()
        return {"success": True, "strategy_id": strategy_id, "symbol": symbol}

    async def get_strategy_performance(self, strategy_id: str, symbol: str) -> Dict[str, Any]:
        """获取策略表现"""
        key = f"{strategy_id}_{symbol}"
        return self._active_strategies.get(key, {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "enabled": False,
            "performance": {
                "total_return": 0.0,
                "daily_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
            },
        })

    async def get_active_strategies(self) -> List[Dict[str, Any]]:
        """获取活跃策略"""
        return [
            {"id": k, **v}
            for k, v in self._active_strategies.items()
            if v.get("enabled", False)
        ]


_strategy_api_service: Optional[StrategyAPIService] = None


def get_strategy_api_service() -> StrategyAPIService:
    """获取策略 API 服务实例"""
    global _strategy_api_service
    if _strategy_api_service is None:
        _strategy_api_service = StrategyAPIService()
    return _strategy_api_service
