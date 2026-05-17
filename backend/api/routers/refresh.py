"""
Refresh Router - 数据刷新 API 端点
"""
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from infrastructure.logging import get_logger

logger = get_logger("api.refresh")

router = APIRouter(prefix="/refresh", tags=["Refresh"])


class RefreshResult(BaseModel):
    success: bool
    message: str
    data_type: str
    timestamp: str


class RefreshAllResponse(BaseModel):
    success: bool
    message: str
    results: List[RefreshResult]
    timestamp: str


@router.post("/prices", response_model=RefreshResult)
async def refresh_prices(
    symbol: Optional[str] = Query(None, description="指定交易对，如 BTC，不指定则刷新全部"),
):
    """
    刷新价格数据
    
    触发从交易所重新获取最新价格
    """
    from ..services.refresh_service import refresh_prices_data
    
    try:
        result = await refresh_prices_data(symbol)
        return RefreshResult(
            success=True,
            message=f"价格数据刷新成功: {result.get('count', 0)} 条",
            data_type="prices",
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to refresh prices: {e}")
        return RefreshResult(
            success=False,
            message=f"刷新失败: {str(e)}",
            data_type="prices",
            timestamp=datetime.utcnow().isoformat(),
        )


@router.post("/signals", response_model=RefreshResult)
async def refresh_signals(
    symbol: Optional[str] = Query(None, description="指定交易对，如 BTC"),
):
    """
    刷新信号数据
    
    触发信号重新计算
    """
    from ..services.refresh_service import refresh_signals_data
    
    try:
        result = await refresh_signals_data(symbol)
        return RefreshResult(
            success=True,
            message=f"信号数据刷新成功",
            data_type="signals",
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to refresh signals: {e}")
        return RefreshResult(
            success=False,
            message=f"刷新失败: {str(e)}",
            data_type="signals",
            timestamp=datetime.utcnow().isoformat(),
        )


@router.post("/factors", response_model=RefreshResult)
async def refresh_factors():
    """
    刷新因子数据
    
    触发因子重新计算
    """
    from ..services.refresh_service import refresh_factors_data
    
    try:
        result = await refresh_factors_data()
        return RefreshResult(
            success=True,
            message=f"因子数据刷新成功: {result.get('count', 0)} 个因子",
            data_type="factors",
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to refresh factors: {e}")
        return RefreshResult(
            success=False,
            message=f"刷新失败: {str(e)}",
            data_type="factors",
            timestamp=datetime.utcnow().isoformat(),
        )


@router.post("/news", response_model=RefreshResult)
async def refresh_news():
    """
    刷新新闻数据
    
    触发从新闻源重新获取最新资讯
    """
    from ..services.refresh_service import refresh_news_data
    
    try:
        result = await refresh_news_data()
        return RefreshResult(
            success=True,
            message=f"新闻数据刷新成功: {result.get('count', 0)} 条",
            data_type="news",
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to refresh news: {e}")
        return RefreshResult(
            success=False,
            message=f"刷新失败: {str(e)}",
            data_type="news",
            timestamp=datetime.utcnow().isoformat(),
        )


@router.post("/correlation", response_model=RefreshResult)
async def refresh_correlation(
    symbol: str = Query("BTC", description="交易对"),
    timeframe: str = Query("1h", description="时间周期"),
):
    """
    刷新相关性分析
    
    触发相关性分析重新计算
    """
    from ..services.refresh_service import refresh_correlation_data
    
    try:
        result = await refresh_correlation_data(symbol, timeframe)
        return RefreshResult(
            success=True,
            message=f"相关性分析刷新成功",
            data_type="correlation",
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to refresh correlation: {e}")
        return RefreshResult(
            success=False,
            message=f"刷新失败: {str(e)}",
            data_type="correlation",
            timestamp=datetime.utcnow().isoformat(),
        )


@router.post("/all", response_model=RefreshAllResponse)
async def refresh_all():
    """
    刷新所有数据
    
    触发价格、信号、因子、新闻等所有数据的刷新
    """
    from ..services.refresh_service import refresh_all_data
    
    try:
        results = await refresh_all_data()
        
        success_count = sum(1 for r in results if r.get("success"))
        total_count = len(results)
        
        return RefreshAllResponse(
            success=success_count == total_count,
            message=f"刷新完成: {success_count}/{total_count} 成功",
            results=[
                RefreshResult(
                    success=r.get("success", False),
                    message=r.get("message", ""),
                    data_type=r.get("data_type", "unknown"),
                    timestamp=datetime.utcnow().isoformat(),
                )
                for r in results
            ],
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to refresh all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_refresh_status():
    """
    获取刷新状态
    
    返回各数据源的最近刷新时间
    """
    from ..services.refresh_service import get_refresh_status as get_status
    
    return await get_status()
