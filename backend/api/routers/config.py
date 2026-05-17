"""
Config Router - Configuration Management Endpoints
配置管理路由 - 新闻源、API Keys、数据源CRUD
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

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
)
from ..services.config_service import ConfigService

router = APIRouter()


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
