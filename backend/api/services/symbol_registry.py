"""
Symbol Strategy Registry API Service - Symbol Registry API Logic
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

from application.queries.service_queries import get_symbol_registry
from ..schemas.symbol_registry import (
    SymbolConfigItem,
    StrategyPerformanceItem,
    OptimizationSuggestionItem,
    UpdateSymbolConfigRequest,
    SymbolConfigsResponse,
)

logger = logging.getLogger(__name__)


def _convert_to_symbol_config(
    symbol: str,
    registry_config: Dict
) -> SymbolConfigItem:
    """转换注册表配置为 API 响应格式"""
    performance_items = {}
    if "performance" in registry_config:
        for strat_id, perf in registry_config["performance"].items():
            performance_items[strat_id] = StrategyPerformanceItem(
                strategy_id=strat_id,
                win_rate=perf.get("win_rate", 0.0),
                avg_return=perf.get("avg_return", 0.0),
                max_drawdown=perf.get("max_drawdown", 0.0),
                total_trades=perf.get("total_trades", 0),
                last_updated=perf.get("last_updated", datetime.utcnow()),
            )
    
    suggestion_items = []
    if "suggestions" in registry_config:
        for suggestion in registry_config["suggestions"]:
            suggestion_items.append(OptimizationSuggestionItem(
                type=suggestion.get("type", "weight"),
                feature=suggestion.get("feature", ""),
                current_value=suggestion.get("current_value", 0.0),
                suggested_value=suggestion.get("suggested_value", 0.0),
                reason=suggestion.get("reason", ""),
                expected_improvement=suggestion.get("expected_improvement"),
            ))
    
    return SymbolConfigItem(
        symbol=symbol,
        weights=registry_config.get("weights", {}),
        thresholds=registry_config.get("thresholds", {}),
        enabled_strategies=registry_config.get("enabled_strategies", []),
        performance=performance_items if performance_items else None,
        optimization_suggestions=suggestion_items if suggestion_items else None,
        last_updated=registry_config.get("last_updated", datetime.utcnow()),
    )


def get_all_symbol_configs() -> SymbolConfigsResponse:
    """获取所有币种配置"""
    registry = get_symbol_registry()
    configs = {}
    
    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        config_dict = registry.get_config(symbol)
        configs[symbol] = _convert_to_symbol_config(symbol, config_dict)
    
    return SymbolConfigsResponse(configs=configs)


def get_symbol_config(symbol: str) -> SymbolConfigItem:
    """获取单个币种配置"""
    registry = get_symbol_registry()
    config_dict = registry.get_config(symbol)
    return _convert_to_symbol_config(symbol, config_dict)


def update_symbol_config(
    symbol: str,
    request: UpdateSymbolConfigRequest
) -> bool:
    """更新币种配置"""
    registry = get_symbol_registry()
    
    if request.weights is not None:
        registry.update_config(symbol, {"weights": request.weights})
    
    if request.thresholds is not None:
        registry.update_config(symbol, {"thresholds": request.thresholds})
    
    if request.enabled_strategies is not None:
        registry.update_config(symbol, {"enabled_strategies": request.enabled_strategies})
    
    return True


def get_optimization_suggestions(symbol: str) -> List[OptimizationSuggestionItem]:
    """获取优化建议"""
    registry = get_symbol_registry()
    suggestions = registry.get_optimization_suggestions(symbol)
    
    items = []
    for suggestion in suggestions:
        items.append(OptimizationSuggestionItem(
            type=suggestion.get("type", "weight"),
            feature=suggestion.get("feature", ""),
            current_value=suggestion.get("current_value", 0.0),
            suggested_value=suggestion.get("suggested_value", 0.0),
            reason=suggestion.get("reason", ""),
            expected_improvement=suggestion.get("expected_improvement"),
        ))
    
    return items


def update_strategy_performance(
    symbol: str,
    strategy_id: str,
    performance: Dict
) -> bool:
    """更新策略性能"""
    registry = get_symbol_registry()
    registry.record_performance(symbol, strategy_id, performance)
    return True
