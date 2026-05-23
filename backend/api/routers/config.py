"""
Config Router - Configuration Management Endpoints
配置管理路由 - 新闻源、API Keys、数据源CRUD、交易模式
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from ..schemas import (
    NewsSourceCreate,
    NewsSourceUpdate,
    NewsSourceResponse,
    NewsSourceListResponse,
    NewsSourceStatus,
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyResponse,
    ApiKeyListResponse,
    LlmConfigResponse,
    LlmProviderConfig,
    DataSourceConfig,
    DataSourceListResponse,
    TwitterCookieConfigResponse,
    TwitterAccountCreate,
    TwitterAccountUpdate,
    TwitterConfigUpdate,
    TelegramConfigResponse,
    TelegramChannelCreate,
    TelegramChannelUpdate,
    TelegramConfigUpdate,
)
from ..schemas.symbol_registry import (
    SymbolConfigItem,
    SymbolConfigsResponse,
    UpdateSymbolConfigRequest,
    OptimizationSuggestionItem,
)
from ..schemas.common import SuccessResponse
from ..services.config_service import ConfigService
from ..services import symbol_registry as sr_service

router = APIRouter()


# 交易模式相关的 Schema
class TradingModeInfo(BaseModel):
    """交易模式信息"""
    mode: str = Field(..., description="当前交易模式: demo, paper, prod")
    description: str = Field(..., description="模式描述")
    market_data_source: str = Field(..., description="市场数据源: real/testnet")
    order_execution: str = Field(..., description="订单执行方式: testnet/mock/real")
    show_warning: bool = Field(..., description="是否显示警告")
    config: Dict[str, Any] = Field(default_factory=dict, description="模式特定配置")


class SetTradingModeRequest(BaseModel):
    """设置交易模式请求"""
    mode: str = Field(..., description="要设置的交易模式")


async def get_service() -> ConfigService:
    service = ConfigService()
    await service.ensure_connection()
    return service


@router.get("/news-sources", response_model=NewsSourceListResponse)
async def list_news_sources():
    """获取所有新闻源"""
    service = await get_service()
    sources = await service.get_news_sources()
    return NewsSourceListResponse(
        sources=[NewsSourceResponse(**s) for s in sources],
        total=len(sources)
    )


@router.get("/news-sources/{source_id}", response_model=NewsSourceResponse)
async def get_news_source(source_id: str):
    """获取单个新闻源"""
    service = await get_service()
    source = await service.get_news_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="News source not found")
    return NewsSourceResponse(**source)


@router.post("/news-sources", response_model=NewsSourceResponse, status_code=201)
async def create_news_source(source: NewsSourceCreate):
    """创建新闻源"""
    service = await get_service()
    result = await service.create_news_source(source.model_dump())
    return NewsSourceResponse(**result)


@router.put("/news-sources/{source_id}", response_model=NewsSourceResponse)
async def update_news_source(source_id: str, updates: NewsSourceUpdate):
    """更新新闻源"""
    service = await get_service()
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    result = await service.update_news_source(source_id, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="News source not found")
    return NewsSourceResponse(**result)


@router.delete("/news-sources/{source_id}")
async def delete_news_source(source_id: str):
    """删除新闻源"""
    service = await get_service()
    success = await service.delete_news_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="News source not found")
    return {"success": True, "message": "News source deleted"}


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys():
    """获取所有API Keys"""
    service = await get_service()
    keys = await service.get_api_keys()
    return ApiKeyListResponse(
        keys=[ApiKeyResponse(**k) for k in keys],
        total=len(keys)
    )


@router.get("/api-keys/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(key_id: str):
    """获取单个API Key"""
    service = await get_service()
    key = await service.get_api_key(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return ApiKeyResponse(**key)


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(key: ApiKeyCreate):
    """创建API Key"""
    service = await get_service()
    result = await service.create_api_key(key.model_dump())
    return ApiKeyResponse(**result)


@router.put("/api-keys/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(key_id: str, updates: ApiKeyUpdate):
    """更新API Key"""
    service = await get_service()
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    result = await service.update_api_key(key_id, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")
    return ApiKeyResponse(**result)


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str):
    """删除API Key"""
    service = await get_service()
    success = await service.delete_api_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"success": True, "message": "API key deleted"}


@router.get("/llm-config", response_model=LlmConfigResponse)
async def get_llm_config():
    """获取LLM配置"""
    service = await get_service()
    config = await service.get_llm_config()
    return LlmConfigResponse(
        providers=[LlmProviderConfig(**p) for p in config.get("providers", [])],
        active_provider=config.get("active_provider"),
        fallback_chain=config.get("fallback_chain", [])
    )


@router.put("/llm-config")
async def update_llm_config(config: LlmConfigResponse):
    """更新LLM配置"""
    service = await get_service()
    config_dict = {
        "providers": [p.model_dump() for p in config.providers],
        "active_provider": config.active_provider,
        "fallback_chain": config.fallback_chain
    }
    result = await service.update_llm_config(config_dict)
    return {"success": True, "config": result}


@router.get("/data-sources", response_model=DataSourceListResponse)
async def list_data_sources():
    """获取所有数据源"""
    service = await get_service()
    sources = await service.get_data_sources()
    return DataSourceListResponse(
        sources=[DataSourceConfig(**s) for s in sources]
    )


@router.put("/data-sources")
async def update_data_sources(sources: List[DataSourceConfig]):
    """更新数据源配置"""
    service = await get_service()
    result = await service.update_data_sources([s.model_dump() for s in sources])
    return {"success": True, "sources": result}


@router.get("/exchanges/{exchange}")
async def get_exchange_config(exchange: str):
    """获取交易所配置"""
    service = await get_service()
    config = await service.get_exchange_config(exchange)
    if not config:
        raise HTTPException(status_code=404, detail="Exchange config not found")
    return {"exchange": exchange, "config": config}


@router.put("/exchanges/{exchange}")
async def update_exchange_config(exchange: str, config: dict):
    """更新交易所配置"""
    service = await get_service()
    result = await service.update_exchange_config(exchange, config)
    return {"success": True, "exchange": exchange, "config": result}


# ==================== 交易模式管理 ====================

@router.get("/trading-mode", response_model=TradingModeInfo)
async def get_trading_mode():
    """获取当前交易模式"""
    from application.queries.domain_queries import get_execution_trading_mode, get_execution_trading_mode_config

    TradingMode = get_execution_trading_mode()
    config = get_execution_trading_mode_config()
    mode = config.mode
    
    descriptions = {
        TradingMode.DEMO: "Binance Testnet / OKX Demo Trading - 适合初期开发和测试",
        TradingMode.PAPER: "真实市场数据 + 本地撮合引擎 - 最适合策略验证，机构首选",
        TradingMode.PROD: "真实交易 - 真实下单，谨慎使用",
    }
    
    mode_config = {}
    if mode == TradingMode.DEMO:
        mode_config = config.demo_config
    elif mode == TradingMode.PAPER:
        mode_config = config.paper_config
    elif mode == TradingMode.PROD:
        mode_config = config.prod_config
    
    return TradingModeInfo(
        mode=mode.value,
        description=descriptions.get(mode, "Unknown mode"),
        market_data_source=config.market_data_source,
        order_execution=config.order_execution,
        show_warning=config.show_paper_warning,
        config=mode_config,
    )


@router.get("/trading-mode/options")
async def get_trading_mode_options():
    """获取所有可用的交易模式选项"""
    from application.queries.domain_queries import get_execution_trading_mode

    TradingMode = get_execution_trading_mode()
    
    return {
        "options": [
            {
                "mode": TradingMode.DEMO.value,
                "name": "Demo / 测试网",
                "description": "Binance Testnet / OKX Demo Trading",
                "warning": None,
            },
            {
                "mode": TradingMode.PAPER.value,
                "name": "Paper Trading / 模拟交易",
                "description": "真实市场数据 + 本地撮合 (推荐用于策略验证)",
                "warning": "此模式不进行真实交易",
            },
            {
                "mode": TradingMode.PROD.value,
                "name": "Prod / 实盘交易",
                "description": "真实市场 + 真实交易",
                "warning": "警告：此模式将进行真实交易！",
            },
        ],
    }


@router.post("/trading-mode")
async def set_trading_mode(request: SetTradingModeRequest):
    """设置交易模式 (需要重启服务生效)"""
    from application.queries.domain_queries import get_execution_trading_mode

    TradingMode = get_execution_trading_mode()
    try:
        mode = TradingMode(request.mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {request.mode}. Must be one of: demo, paper, prod"
        )
    
    return {
        "success": True,
        "mode": mode.value,
        "message": "Mode setting updated. Please restart the service for changes to take effect.",
        "note": "To apply this change permanently, update the MODE variable in your .env file and restart the backend service.",
    }


# ==================== Twitter Cookie Monitor 配置 ====================

@router.get("/twitter", response_model=TwitterCookieConfigResponse)
async def get_twitter_config():
    """获取 Twitter Cookie Monitor 配置"""
    service = await get_service()
    config = await service.get_twitter_config()
    return TwitterCookieConfigResponse(**config)


@router.put("/twitter")
async def update_twitter_config(config: TwitterConfigUpdate):
    """更新 Twitter Cookie Monitor 配置"""
    service = await get_service()
    result = await service.update_twitter_config(config.model_dump(exclude_none=True))
    return {"success": True, "config": result}


@router.get("/twitter/accounts")
async def list_twitter_accounts():
    """获取 Twitter 监控账号列表"""
    service = await get_service()
    accounts = await service.get_twitter_accounts()
    return {"accounts": accounts, "total": len(accounts)}


@router.post("/twitter/accounts", status_code=201)
async def create_twitter_account(account: TwitterAccountCreate):
    """添加 Twitter 监控账号"""
    service = await get_service()
    result = await service.create_twitter_account(account.model_dump())
    return {"success": True, "account": result}


@router.put("/twitter/accounts/{username}")
async def update_twitter_account(username: str, updates: TwitterAccountUpdate):
    """更新 Twitter 监控账号"""
    service = await get_service()
    result = await service.update_twitter_account(username, updates.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "account": result}


@router.delete("/twitter/accounts/{username}")
async def delete_twitter_account(username: str):
    """删除 Twitter 监控账号"""
    service = await get_service()
    success = await service.delete_twitter_account(username)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "message": f"Account @{username} deleted"}


# ==================== Telegram 配置 ====================

@router.get("/telegram", response_model=TelegramConfigResponse)
async def get_telegram_config():
    """获取 Telegram 配置"""
    service = await get_service()
    config = await service.get_telegram_config()
    return TelegramConfigResponse(**config)


@router.put("/telegram")
async def update_telegram_config(config: TelegramConfigUpdate):
    """更新 Telegram 配置"""
    service = await get_service()
    result = await service.update_telegram_config(config.model_dump(exclude_none=True))
    return {"success": True, "config": result}


@router.get("/telegram/channels")
async def list_telegram_channels():
    """获取 Telegram 监控频道列表"""
    service = await get_service()
    channels = await service.get_telegram_channels()
    return {"channels": channels, "total": len(channels)}


@router.post("/telegram/channels", status_code=201)
async def create_telegram_channel(channel: TelegramChannelCreate):
    """添加 Telegram 监控频道"""
    service = await get_service()
    result = await service.create_telegram_channel(channel.model_dump())
    return {"success": True, "channel": result}


@router.put("/telegram/channels/{channel_id}")
async def update_telegram_channel(channel_id: str, updates: TelegramChannelUpdate):
    """更新 Telegram 监控频道"""
    service = await get_service()
    result = await service.update_telegram_channel(channel_id, updates.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"success": True, "channel": result}


@router.delete("/telegram/channels/{channel_id}")
async def delete_telegram_channel(channel_id: str):
    """删除 Telegram 监控频道"""
    service = await get_service()
    success = await service.delete_telegram_channel(channel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"success": True, "message": f"Channel {channel_id} deleted"}


# ==================== Symbol Strategy Registry ====================

@router.get("/symbols", response_model=SymbolConfigsResponse)
async def get_all_symbol_configs():
    """获取所有币种配置"""
    return sr_service.get_all_symbol_configs()


@router.get("/symbols/{symbol}", response_model=SymbolConfigItem)
async def get_symbol_config_endpoint(symbol: str):
    """获取单个币种配置"""
    return sr_service.get_symbol_config(symbol)


@router.put("/symbols/{symbol}", response_model=SuccessResponse)
async def update_symbol_config_endpoint(
    symbol: str,
    request: UpdateSymbolConfigRequest
):
    """更新币种配置"""
    success = sr_service.update_symbol_config(symbol, request)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update symbol config")
    return SuccessResponse(
        success=True,
        message=f"Config updated for {symbol}",
    )


@router.get("/symbols/{symbol}/suggestions", response_model=List[OptimizationSuggestionItem])
async def get_optimization_suggestions_endpoint(symbol: str):
    """获取币种优化建议"""
    return sr_service.get_optimization_suggestions(symbol)
