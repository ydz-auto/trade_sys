from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class StrategyAPIService:

    def __init__(self):
        self._discovered_strategies: Dict[str, List[Dict]] = {}
        self._backtest_results: Dict[str, Dict] = {}
        self._active_strategies: Dict[str, Dict] = {}
        self._param_store = None

    def _get_param_store(self):
        if self._param_store is None:
            from application.queries.service_queries import get_strategy_param_store
            self._param_store = get_strategy_param_store()
        return self._param_store

    async def discover_strategies(self, symbol: str) -> Dict[str, Any]:
        from application.queries.service_queries import discover_strategies as _discover

        try:
            result = await _discover(symbol)

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
        return self._discovered_strategies.get(symbol, [])

    async def add_to_watchlist(self, strategy_id: str) -> Dict[str, Any]:
        for symbol_strategies in self._discovered_strategies.values():
            for strategy in symbol_strategies:
                if strategy["id"] == strategy_id:
                    strategy["in_watchlist"] = True
                    return {"success": True, "strategy_id": strategy_id}

        return {"success": False, "error": "Strategy not found"}

    async def remove_from_watchlist(self, strategy_id: str) -> Dict[str, Any]:
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
        from application.queries.service_queries import get_strategy_discovery_engine

        backtest_id = f"bt_{uuid.uuid4().hex[:8]}"

        try:
            engine = get_strategy_discovery_engine(
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
                df["future_ret_1h"] = df["close"].shift(-12) / df["close"] - 1

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
        return self._backtest_results.get(backtest_id)

    async def list_backtests(self) -> List[Dict[str, Any]]:
        return list(self._backtest_results.values())

    async def get_strategy_configs(self) -> List[Dict[str, Any]]:
        params_list = await self._get_param_store().get_all_params()
        return [p.to_dict() for p in params_list]

    async def get_strategy_config(self, strategy_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        params = await self._get_param_store().get_param(symbol, strategy_id)
        if params:
            return params.to_dict()
        from application.queries.domain_queries import get_feature_range_class
        FeatureRange = get_feature_range_class()
        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "weight": 1.0,
            "enabled": False,
            "entry_params": {},
            "exit_params": {},
            "risk_params": {},
            "feature_range": FeatureRange().to_dict(),
            "source": "default",
            "version": 1,
        }

    async def update_strategy_config(
        self,
        strategy_id: str,
        symbol: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        from application.queries.domain_queries import get_strategy_parameters_class, get_feature_range_class
        StrategyParameters = get_strategy_parameters_class()
        FeatureRange = get_feature_range_class()
        store = self._get_param_store()

        params = await store.get_param(symbol, strategy_id)

        if params is None:
            params = StrategyParameters(
                strategy_id=strategy_id,
                symbol=symbol
            )

        for key, value in config.items():
            if hasattr(params, key):
                if key == "feature_range" and isinstance(value, dict):
                    params.feature_range = FeatureRange.from_dict(value)
                else:
                    setattr(params, key, value)

        params.version += 1

        success = await store.set_param(params)

        return {"success": success, "config": params.to_dict()}

    async def update_feature_range(
        self,
        strategy_id: str,
        symbol: str,
        feature_range: Dict[str, Any],
    ) -> Dict[str, Any]:
        from application.queries.domain_queries import get_feature_range_class
        FeatureRange = get_feature_range_class()
        store = self._get_param_store()

        fr = FeatureRange(
            start_date=feature_range.get("start_date", ""),
            end_date=feature_range.get("end_date", ""),
            volatility_range=feature_range.get("volatility_range", "all"),
            trend_range=feature_range.get("trend_range", "all"),
            volume_profile=feature_range.get("volume_profile", "all"),
            funding_range=feature_range.get("funding_range", "all"),
            custom_filters=feature_range.get("custom_filters", {}),
        )

        params = await store.update_feature_range(symbol, strategy_id, fr)

        if params:
            return {"success": True, "config": params.to_dict()}
        return {"success": False, "error": "Failed to update feature range"}

    async def get_symbol_params(self, symbol: str) -> List[Dict[str, Any]]:
        params_list = await self._get_param_store().get_symbol_params(symbol)
        return [p.to_dict() for p in params_list]

    async def batch_update_params(
        self,
        updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return await self._get_param_store().batch_update_params(updates)

    async def get_param_history(
        self,
        strategy_id: str,
        symbol: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        return await self._get_param_store().get_param_history(symbol, strategy_id, limit)

    async def restore_version(
        self,
        strategy_id: str,
        symbol: str,
        version: int
    ) -> Dict[str, Any]:
        params = await self._get_param_store().restore_version(symbol, strategy_id, version)
        if params:
            return {"success": True, "config": params.to_dict()}
        return {"success": False, "error": f"Failed to restore version {version}"}

    async def enable_strategy(self, strategy_id: str, symbol: str) -> Dict[str, Any]:
        key = f"{strategy_id}_{symbol}"
        self._active_strategies[key] = {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "enabled": True,
            "enabled_at": datetime.now().isoformat(),
        }
        return {"success": True, "strategy_id": strategy_id, "symbol": symbol}

    async def disable_strategy(self, strategy_id: str, symbol: str) -> Dict[str, Any]:
        key = f"{strategy_id}_{symbol}"
        if key in self._active_strategies:
            self._active_strategies[key]["enabled"] = False
            self._active_strategies[key]["disabled_at"] = datetime.now().isoformat()
        return {"success": True, "strategy_id": strategy_id, "symbol": symbol}

    async def get_strategy_performance(self, strategy_id: str, symbol: str) -> Dict[str, Any]:
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
        return [
            {"id": k, **v}
            for k, v in self._active_strategies.items()
            if v.get("enabled", False)
        ]


_strategy_api_service: Optional[StrategyAPIService] = None


def _get_service() -> StrategyAPIService:
    global _strategy_api_service
    if _strategy_api_service is None:
        _strategy_api_service = StrategyAPIService()
    return _strategy_api_service


async def discover_strategies(symbol: str) -> Dict[str, Any]:
    return await _get_service().discover_strategies(symbol)


async def get_discovered_strategies(symbol: str) -> List[Dict[str, Any]]:
    return await _get_service().get_discovered_strategies(symbol)


async def add_to_watchlist(strategy_id: str) -> Dict[str, Any]:
    return await _get_service().add_to_watchlist(strategy_id)


async def remove_from_watchlist(strategy_id: str) -> Dict[str, Any]:
    return await _get_service().remove_from_watchlist(strategy_id)


async def run_backtest(
    strategy_id: str,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000,
) -> Dict[str, Any]:
    return await _get_service().run_backtest(
        strategy_id=strategy_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )


async def get_backtest(backtest_id: str) -> Optional[Dict[str, Any]]:
    return await _get_service().get_backtest(backtest_id)


async def list_backtests() -> List[Dict[str, Any]]:
    return await _get_service().list_backtests()


async def get_strategy_configs() -> List[Dict[str, Any]]:
    return await _get_service().get_strategy_configs()


async def get_strategy_config(strategy_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    return await _get_service().get_strategy_config(strategy_id, symbol)


async def update_strategy_config(
    strategy_id: str,
    symbol: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    return await _get_service().update_strategy_config(strategy_id, symbol, config)


async def enable_strategy(strategy_id: str, symbol: str) -> Dict[str, Any]:
    return await _get_service().enable_strategy(strategy_id, symbol)


async def disable_strategy(strategy_id: str, symbol: str) -> Dict[str, Any]:
    return await _get_service().disable_strategy(strategy_id, symbol)


async def get_strategy_performance(strategy_id: str, symbol: str) -> Dict[str, Any]:
    return await _get_service().get_strategy_performance(strategy_id, symbol)


async def get_active_strategies() -> List[Dict[str, Any]]:
    return await _get_service().get_active_strategies()


async def get_symbol_params(symbol: str) -> List[Dict[str, Any]]:
    return await _get_service().get_symbol_params(symbol)


async def update_feature_range(
    strategy_id: str,
    symbol: str,
    feature_range: Dict[str, Any],
) -> Dict[str, Any]:
    return await _get_service().update_feature_range(strategy_id, symbol, feature_range)


async def batch_update_params(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    return await _get_service().batch_update_params(updates)


async def get_param_history(
    strategy_id: str,
    symbol: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    return await _get_service().get_param_history(strategy_id, symbol, limit)


async def restore_version(
    strategy_id: str,
    symbol: str,
    version: int,
) -> Dict[str, Any]:
    return await _get_service().restore_version(strategy_id, symbol, version)
