"""
Symbol Strategy Registry Schemas - Per-Symbol Configuration Models
"""
from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime


class StrategyPerformanceItem(BaseModel):
    """策略性能项"""
    strategy_id: str
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    last_updated: datetime = datetime.utcnow()


class OptimizationSuggestionItem(BaseModel):
    """优化建议项"""
    type: str
    feature: str
    current_value: float
    suggested_value: float
    reason: str
    expected_improvement: Optional[float] = None


class SymbolConfigItem(BaseModel):
    """币种配置项"""
    symbol: str
    weights: Dict[str, float] = {}
    thresholds: Dict[str, float] = {}
    enabled_strategies: List[str] = []
    performance: Optional[Dict[str, StrategyPerformanceItem]] = None
    optimization_suggestions: Optional[List[OptimizationSuggestionItem]] = None
    last_updated: datetime = datetime.utcnow()


class UpdateSymbolConfigRequest(BaseModel):
    """更新币种配置请求"""
    weights: Optional[Dict[str, float]] = None
    thresholds: Optional[Dict[str, float]] = None
    enabled_strategies: Optional[List[str]] = None


class SymbolConfigsResponse(BaseModel):
    """币种配置响应"""
    configs: Dict[str, SymbolConfigItem]
