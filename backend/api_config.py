"""
Configuration Management API - 统一配置管理 API
提供 RESTful API 给前端配置各层参数
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

router = APIRouter(prefix="/api/v1/config", tags=["配置管理"])


class ConfigCategory(str, Enum):
    RISK = "risk"
    EXCHANGE = "exchange"
    DATASOURCE = "datasource"
    ALERT = "alert"
    STRATEGY = "strategy"
    SYSTEM = "system"


class RiskConfig(BaseModel):
    max_position_value: float = 10000.0
    max_position_count: int = 10
    max_leverage: int = 3
    daily_loss_limit_pct: float = 5.0
    drawdown_limit_pct: float = 15.0
    order_size_limit: float = 1000.0
    cooldown_seconds: int = 60
    symbol_blacklist: List[str] = []
    stop_loss_default_pct: float = 2.0
    take_profit_default_pct: float = 5.0


class ExchangeConfig(BaseModel):
    exchange: str
    enabled: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    testnet: bool = False
    priority: int = 1
    symbols: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    timeout: int = 10


class DataSourceConfig(BaseModel):
    source: str
    enabled: bool = True
    interval_seconds: int = 60
    weight: float = 1.0
    timeout: int = 10
    retry_count: int = 3


class AlertConfig(BaseModel):
    enabled: bool = True
    channels: List[str] = ["log"]
    price_change_threshold_pct: float = 5.0
    risk_level_threshold: str = "high"
    lag_warning_threshold: int = 1000
    lag_critical_threshold: int = 10000


class StrategyConfig(BaseModel):
    trend_weight: float = 0.3
    flow_weight: float = 0.25
    sentiment_weight: float = 0.25
    macro_weight: float = 0.2
    signal_threshold: float = 0.6
    min_confidence: float = 0.5


class SystemConfig(BaseModel):
    log_level: str = "INFO"
    metrics_enabled: bool = True
    health_check_interval: int = 30
    replay_speed: float = 1.0


_config_store: Dict[str, Dict[str, Any]] = {
    "risk": RiskConfig().model_dump(),
    "exchange": {
        "binance": ExchangeConfig(exchange="binance").model_dump(),
        "okx": ExchangeConfig(exchange="okx").model_dump(),
    },
    "datasource": {
        "binance": DataSourceConfig(source="binance").model_dump(),
        "coingecko": DataSourceConfig(source="coingecko").model_dump(),
        "twitter": DataSourceConfig(source="twitter", enabled=False).model_dump(),
    },
    "alert": AlertConfig().model_dump(),
    "strategy": StrategyConfig().model_dump(),
    "system": SystemConfig().model_dump(),
}


@router.get("/categories")
async def get_categories() -> List[Dict[str, str]]:
    """获取所有配置分类"""
    return [
        {"id": cat.value, "name": _get_category_name(cat.value), "icon": _get_category_icon(cat.value)}
        for cat in ConfigCategory
    ]


@router.get("/{category}")
async def get_config(category: str) -> Dict[str, Any]:
    """获取指定分类的配置"""
    if category not in _config_store:
        raise HTTPException(status_code=404, detail=f"配置分类 '{category}' 不存在")
    
    return {
        "category": category,
        "name": _get_category_name(category),
        "config": _config_store[category],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/{category}")
async def update_config(category: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """更新指定分类的配置"""
    if category not in _config_store:
        raise HTTPException(status_code=404, detail=f"配置分类 '{category}' 不存在")
    
    _config_store[category] = config
    
    return {
        "success": True,
        "category": category,
        "config": _config_store[category],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/risk")
async def get_risk_config() -> Dict[str, Any]:
    """获取风控配置"""
    return {
        "category": "risk",
        "config": _config_store["risk"],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/risk")
async def update_risk_config(config: RiskConfig) -> Dict[str, Any]:
    """更新风控配置"""
    _config_store["risk"] = config.model_dump()
    
    return {
        "success": True,
        "message": "风控配置已更新",
        "config": _config_store["risk"],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/exchange")
async def get_exchange_configs() -> Dict[str, Any]:
    """获取所有交易所配置"""
    return {
        "category": "exchange",
        "exchanges": _config_store["exchange"],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/exchange/{exchange_name}")
async def update_exchange_config(exchange_name: str, config: ExchangeConfig) -> Dict[str, Any]:
    """更新指定交易所配置"""
    if exchange_name not in _config_store["exchange"]:
        _config_store["exchange"][exchange_name] = {}
    
    _config_store["exchange"][exchange_name] = config.model_dump()
    
    return {
        "success": True,
        "message": f"交易所 {exchange_name} 配置已更新",
        "config": _config_store["exchange"][exchange_name],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/datasource")
async def get_datasource_configs() -> Dict[str, Any]:
    """获取所有数据源配置"""
    return {
        "category": "datasource",
        "datasources": _config_store["datasource"],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/datasource/{source_name}")
async def update_datasource_config(source_name: str, config: DataSourceConfig) -> Dict[str, Any]:
    """更新指定数据源配置"""
    if source_name not in _config_store["datasource"]:
        _config_store["datasource"][source_name] = {}
    
    _config_store["datasource"][source_name] = config.model_dump()
    
    return {
        "success": True,
        "message": f"数据源 {source_name} 配置已更新",
        "config": _config_store["datasource"][source_name],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/alert")
async def get_alert_config() -> Dict[str, Any]:
    """获取告警配置"""
    return {
        "category": "alert",
        "config": _config_store["alert"],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/alert")
async def update_alert_config(config: AlertConfig) -> Dict[str, Any]:
    """更新告警配置"""
    _config_store["alert"] = config.model_dump()
    
    return {
        "success": True,
        "message": "告警配置已更新",
        "config": _config_store["alert"],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/strategy")
async def get_strategy_config() -> Dict[str, Any]:
    """获取策略配置"""
    return {
        "category": "strategy",
        "config": _config_store["strategy"],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/strategy")
async def update_strategy_config(config: StrategyConfig) -> Dict[str, Any]:
    """更新策略配置"""
    _config_store["strategy"] = config.model_dump()
    
    return {
        "success": True,
        "message": "策略配置已更新",
        "config": _config_store["strategy"],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/system")
async def get_system_config() -> Dict[str, Any]:
    """获取系统配置"""
    return {
        "category": "system",
        "config": _config_store["system"],
        "updated_at": datetime.now().isoformat(),
    }


@router.put("/system")
async def update_system_config(config: SystemConfig) -> Dict[str, Any]:
    """更新系统配置"""
    _config_store["system"] = config.model_dump()
    
    return {
        "success": True,
        "message": "系统配置已更新",
        "config": _config_store["system"],
        "updated_at": datetime.now().isoformat(),
    }


@router.post("/reset/{category}")
async def reset_config(category: str) -> Dict[str, Any]:
    """重置指定分类为默认配置"""
    if category not in _config_store:
        raise HTTPException(status_code=404, detail=f"配置分类 '{category}' 不存在")
    
    default_configs = {
        "risk": RiskConfig(),
        "exchange": {
            "binance": ExchangeConfig(exchange="binance"),
            "okx": ExchangeConfig(exchange="okx"),
        },
        "datasource": {
            "binance": DataSourceConfig(source="binance"),
            "coingecko": DataSourceConfig(source="coingecko"),
            "twitter": DataSourceConfig(source="twitter", enabled=False),
        },
        "alert": AlertConfig(),
        "strategy": StrategyConfig(),
        "system": SystemConfig(),
    }
    
    if category in default_configs:
        _config_store[category] = default_configs[category].model_dump()
    
    return {
        "success": True,
        "message": f"{category} 配置已重置为默认值",
        "config": _config_store[category],
        "updated_at": datetime.now().isoformat(),
    }


def _get_category_name(category: str) -> str:
    names = {
        "risk": "风控参数",
        "exchange": "交易所配置",
        "datasource": "数据源配置",
        "alert": "告警配置",
        "strategy": "策略参数",
        "system": "系统设置",
    }
    return names.get(category, category)


def _get_category_icon(category: str) -> str:
    icons = {
        "risk": "🛡️",
        "exchange": "💹",
        "datasource": "📊",
        "alert": "🔔",
        "strategy": "⚙️",
        "system": "⚡",
    }
    return icons.get(category, "📦")
