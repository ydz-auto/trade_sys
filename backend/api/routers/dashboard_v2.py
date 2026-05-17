"""
Dashboard V2 Router - 拆分后的独立接口

设计原则：
1. 每个模块独立接口
2. 支持分页（新闻、社交帖子）
3. 不同刷新频率
4. 兼容旧的汇总接口
"""

from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from datetime import datetime

from api.services.projection_reader import get_projection_reader
from api.services.dashboard import get_dashboard_data
from infrastructure.cache import get_redis_client
from infrastructure.logging import get_logger
import json
import os

logger = get_logger("api.dashboard_v2")
router = APIRouter(prefix="/dashboard", tags=["dashboard-v2"])


def _is_mock_mode() -> bool:
    return os.getenv("DASHBOARD_MOCK", "false").lower() == "true"


# ============ Response Models ============

class PriceResponse(BaseModel):
    symbol: str
    price: float
    change24h: float
    volume_24h: float = 0
    exchange: str


class RegimeResponse(BaseModel):
    state: str
    confidence: float
    trendStrength: float = 0


class RiskResponse(BaseModel):
    total: float
    level: str
    components: dict


class SignalResponse(BaseModel):
    action: str
    confidence: float
    riskLevel: str
    reason: str
    leverage: int = 1
    stop_loss_pct: float = 0
    take_profit_pct: float = 0


class PositionResponse(BaseModel):
    symbol: str
    side: str
    size: float
    entryPrice: float
    currentPrice: float = 0
    leverage: int = 1
    pnl: float
    pnlPct: float = 0
    stopLoss: Optional[float] = None
    takeProfit: Optional[float] = None
    liquidationPrice: Optional[float] = None
    liquidationDistancePct: Optional[float] = None
    margin: float = 0
    marginRatio: float = 0
    riskLevel: str = "SAFE"
    fundingRate: float = 0
    fundingFeeEstimate: float = 0


class NewsResponse(BaseModel):
    id: str
    title: str
    content: str
    source: str
    sentiment: str
    sentiment_score: float
    published: int
    url: Optional[str] = None


class SocialPostResponse(BaseModel):
    id: str
    platform: str
    author: str
    authorAvatar: Optional[str] = None
    content: str
    sentiment: float
    likes: int = 0
    time: str = ""
    symbols: List[str] = []


class PaginatedNewsResponse(BaseModel):
    items: List[NewsResponse]
    total: int
    page: int
    pageSize: int
    hasMore: bool


class PaginatedSocialResponse(BaseModel):
    items: List[SocialPostResponse]
    total: int
    page: int
    pageSize: int
    hasMore: bool


class FactorResponse(BaseModel):
    type: str
    name: str
    nameEn: Optional[str] = None
    weight: float
    value: float
    confidence: float
    color: Optional[str] = None


class DataSourceResponse(BaseModel):
    name: str
    status: str
    delay: Optional[str] = None
    lastUpdate: Optional[str] = None
    recordsCount: Optional[int] = None


class TraderResponse(BaseModel):
    id: Optional[str] = None
    name: str
    platform: Optional[str] = None
    followers: int
    sentiment: Optional[float] = None
    recentPosition: Optional[str] = None
    symbol: Optional[str] = None
    winRate: float


class MacroResponse(BaseModel):
    gold: dict
    usd_index: dict
    oil: dict


class FearGreedResponse(BaseModel):
    value: int
    classification: str
    timestamp: str


class EtfResponse(BaseModel):
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    confidence: float


# ============ API Endpoints ============

@router.get("/prices", response_model=List[PriceResponse])
async def get_prices():
    """获取价格列表（高频刷新：每秒）"""
    reader = await get_projection_reader()
    state = await reader.get_dashboard_state()
    prices_data = state.get("prices", {})
    
    if prices_data:
        return [
            PriceResponse(
                symbol=data.get("symbol", symbol),
                price=data.get("price", 0),
                change24h=data.get("change24h", 0),
                volume_24h=data.get("volume_24h", 0),
                exchange=data.get("exchange", "binance"),
            )
            for symbol, data in prices_data.items()
        ]
    
    redis = get_redis_client()
    if redis:
        try:
            result = []
            for symbol in ["BTC", "ETH", "SOL", "DOGE"]:
                for exchange in ["binance", "coingecko"]:
                    price_data = await redis.get(f"price:{symbol}:{exchange}")
                    if price_data:
                        if isinstance(price_data, str):
                            price_data = json.loads(price_data)
                        result.append(PriceResponse(
                            symbol=f"{symbol}/USDT",
                            price=price_data.get("price", 0),
                            change24h=price_data.get("change_24h", 0) / 100 if price_data.get("change_24h") else 0,
                            volume_24h=price_data.get("volume_24h", 0) / 1e6 if price_data.get("volume_24h") else 0,
                            exchange=exchange.capitalize()
                        ))
                        break
            if result:
                return result
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    return []


@router.get("/regime", response_model=RegimeResponse)
async def get_regime(symbol: str = Query("BTC", description="交易对")):
    """获取市场状态（中频刷新：每分钟）"""
    reader = await get_projection_reader()
    state = await reader.get_dashboard_state()
    regime_data = state.get("regime", {}).get(symbol, {})
    
    return RegimeResponse(
        state=regime_data.get("state", "neutral"),
        confidence=regime_data.get("confidence", 0.5),
        trendStrength=regime_data.get("trendStrength", 0.5),
    )


@router.get("/risk", response_model=RiskResponse)
async def get_risk():
    """获取风险指标（中频刷新：每分钟）"""
    reader = await get_projection_reader()
    risk_state = await reader.get_risk_state()
    
    return RiskResponse(
        total=float(risk_state.get("score", 0) or 0),
        level=risk_state.get("level", "unknown"),
        components=risk_state.get("components", {}),
    )


@router.get("/signal", response_model=SignalResponse)
async def get_signal(symbol: str = Query("BTC", description="交易对")):
    """获取信号（中频刷新：每分钟）"""
    reader = await get_projection_reader()
    state = await reader.get_dashboard_state()
    signals = state.get("signals", {})
    
    sig = signals.get(f"{symbol}/USDT") or signals.get(f"{symbol}USDT") or signals.get(symbol)
    
    if sig:
        direction = sig.get("direction", "neutral")
        action = "long" if direction == "bullish" else "short" if direction == "bearish" else "hold"
        return SignalResponse(
            action=action,
            confidence=sig.get("confidence", 0.5),
            riskLevel="low",
            reason=f"Signal: {sig.get('signal_name', 'Unknown')}",
            leverage=sig.get("leverage", 1),
            stop_loss_pct=sig.get("stop_loss_pct", 0),
            take_profit_pct=sig.get("take_profit_pct", 0),
        )
    
    return SignalResponse(
        action="hold",
        confidence=0.0,
        riskLevel="unknown",
        reason="No signal data"
    )


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions():
    """获取持仓列表（高频刷新：每秒）"""
    reader = await get_projection_reader()
    positions_data = await reader.get_positions()
    
    if positions_data:
        result = []
        for symbol, data in positions_data.items():
            if data.get("size", 0) != 0:
                result.append(PositionResponse(
                    symbol=symbol,
                    side=data.get("side", "long"),
                    size=abs(data.get("size", 0)),
                    entryPrice=data.get("entry_price", 0),
                    currentPrice=data.get("current_price", 0),
                    leverage=data.get("leverage", 1),
                    pnl=data.get("unrealized_pnl", 0) + data.get("realized_pnl", 0),
                    pnlPct=data.get("pnl_pct", 0),
                    stopLoss=data.get("stop_loss"),
                    takeProfit=data.get("take_profit"),
                    liquidationPrice=data.get("liquidation_price"),
                    liquidationDistancePct=data.get("liquidation_distance_pct"),
                    margin=data.get("margin", 0),
                    marginRatio=data.get("margin_ratio", 0),
                    riskLevel=data.get("risk_level", "SAFE"),
                    fundingRate=data.get("funding_rate", 0),
                    fundingFeeEstimate=data.get("funding_fee_estimate", 0),
                ))
        return result
    
    return []


@router.get("/news", response_model=PaginatedNewsResponse)
async def get_news(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=50, description="每页数量"),
    source: Optional[str] = Query(None, description="来源过滤"),
    sentiment: Optional[str] = Query(None, description="情绪过滤"),
):
    """获取新闻列表（分页，低频刷新：每5分钟）"""
    redis = get_redis_client()
    all_news = []
    
    if redis:
        try:
            news_items = await redis.lrange("news:latest", 0, pageSize - 1)
            if news_items:
                all_news = []
                for item in news_items:
                    if isinstance(item, str):
                        all_news.append(json.loads(item))
                    else:
                        all_news.append(item)
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    if not all_news:
        reader = await get_projection_reader()
        state = await reader.get_dashboard_state()
        all_news = state.get("news", [])
    
    if source:
        all_news = [n for n in all_news if n.get("source") == source]
    if sentiment:
        all_news = [n for n in all_news if n.get("sentiment") == sentiment]
    
    total = len(all_news)
    start = (page - 1) * pageSize
    end = start + pageSize
    page_items = all_news[start:end]
    
    items = [
        NewsResponse(
            id=n.get("id", ""),
            title=n.get("title", ""),
            content=n.get("content", ""),
            source=n.get("source", "unknown"),
            sentiment=n.get("sentiment", "neutral"),
            sentiment_score=n.get("sentiment_score", 0.5),
            published=n.get("published_at", n.get("published", int(datetime.utcnow().timestamp()))),
            url=n.get("url"),
        )
        for n in page_items
    ]
    
    return PaginatedNewsResponse(
        items=items,
        total=total,
        page=page,
        pageSize=pageSize,
        hasMore=end < total,
    )


@router.get("/social", response_model=PaginatedSocialResponse)
async def get_social_posts(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=50, description="每页数量"),
    platform: Optional[str] = Query(None, description="平台过滤"),
):
    """获取社交帖子列表（分页，低频刷新：每5分钟）"""
    redis = get_redis_client()
    all_posts = []
    
    if redis:
        try:
            posts_data = await redis.get("social:posts:all")
            if posts_data:
                if isinstance(posts_data, str):
                    posts_data = json.loads(posts_data)
                all_posts = posts_data
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    if platform:
        all_posts = [p for p in all_posts if p.get("platform") == platform]
    
    total = len(all_posts)
    start = (page - 1) * pageSize
    end = start + pageSize
    page_items = all_posts[start:end]
    
    items = [
        SocialPostResponse(
            id=p.get("id", ""),
            platform=p.get("platform", ""),
            author=p.get("author", ""),
            authorAvatar=p.get("author_avatar"),
            content=p.get("content", ""),
            sentiment=p.get("sentiment", 0.5),
            likes=p.get("likes", 0),
            time=p.get("time", ""),
            symbols=p.get("symbols", []),
        )
        for p in page_items
    ]
    
    return PaginatedSocialResponse(
        items=items,
        total=total,
        page=page,
        pageSize=pageSize,
        hasMore=end < total,
    )


@router.get("/factors", response_model=List[FactorResponse])
async def get_factors():
    """获取因子列表（中频刷新：每分钟）"""
    reader = await get_projection_reader()
    state = await reader.get_dashboard_state()
    factors_data = state.get("factors", {})
    
    if factors_data:
        result = []
        for name, f in factors_data.items():
            if isinstance(f, dict):
                result.append(FactorResponse(
                    type=f.get("type", "unknown"),
                    name=f.get("name", name),
                    nameEn=f.get("nameEn", name),
                    weight=f.get("weight", 0.2),
                    value=f.get("value", 0.5),
                    confidence=f.get("confidence", 50),
                    color=f.get("color", "blue"),
                ))
        return result
    
    return []


@router.get("/data-sources", response_model=List[DataSourceResponse])
async def get_data_sources():
    """获取数据源状态（低频刷新：每5分钟）"""
    redis = get_redis_client()
    
    if redis:
        try:
            sources_data = await redis.get("data_sources:status")
            if sources_data:
                if isinstance(sources_data, str):
                    sources_data = json.loads(sources_data)
                return [
                    DataSourceResponse(
                        name=s.get("name", ""),
                        status=s.get("status", "unknown"),
                        delay=s.get("delay"),
                        lastUpdate=s.get("last_update"),
                        recordsCount=s.get("records_count"),
                    )
                    for s in sources_data
                ]
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    return []


@router.get("/traders", response_model=List[TraderResponse])
async def get_traders(limit: int = Query(10, ge=1, le=50)):
    """获取交易者列表（低频刷新：每5分钟）"""
    redis = get_redis_client()
    
    if redis:
        try:
            traders_data = await redis.get("traders:top")
            if traders_data:
                if isinstance(traders_data, str):
                    traders_data = json.loads(traders_data)
                return [
                    TraderResponse(
                        id=t.get("id"),
                        name=t.get("name", ""),
                        platform=t.get("platform"),
                        followers=t.get("followers", 0),
                        sentiment=t.get("sentiment"),
                        recentPosition=t.get("recent_position"),
                        symbol=t.get("symbol"),
                        winRate=t.get("win_rate", 0.0),
                    )
                    for t in traders_data[:limit]
                ]
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    return []


@router.get("/macro", response_model=Optional[MacroResponse])
async def get_macro():
    """获取宏观数据（低频刷新：每5分钟）"""
    redis = get_redis_client()
    
    if redis:
        try:
            macro_data = await redis.get("macro:data")
            if macro_data:
                if isinstance(macro_data, str):
                    macro_data = json.loads(macro_data)
                return MacroResponse(
                    gold=macro_data.get("gold", {"price": 0, "change": 0}),
                    usd_index=macro_data.get("usd_index", {"value": 0, "change": 0}),
                    oil=macro_data.get("oil", {"price": 0, "change": 0}),
                )
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    return None


@router.get("/fear-greed", response_model=Optional[FearGreedResponse])
async def get_fear_greed():
    """获取恐慌贪婪指数（低频刷新：每小时）"""
    redis = get_redis_client()
    
    if redis:
        try:
            fg_data = await redis.get("fear_greed:index")
            if fg_data:
                if isinstance(fg_data, str):
                    fg_data = json.loads(fg_data)
                return FearGreedResponse(
                    value=fg_data.get("value", 0),
                    classification=fg_data.get("classification", "Unknown"),
                    timestamp=fg_data.get("timestamp", ""),
                )
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    return None


@router.get("/etf", response_model=Optional[EtfResponse])
async def get_etf():
    """获取 ETF 数据（低频刷新：每小时）"""
    redis = get_redis_client()
    
    if redis:
        try:
            etf_data = await redis.get("etf:flow")
            if etf_data:
                if isinstance(etf_data, str):
                    etf_data = json.loads(etf_data)
                return EtfResponse(
                    symbol=etf_data.get("symbol", ""),
                    net_flow=etf_data.get("net_flow", 0),
                    inflow=etf_data.get("inflow", 0),
                    outflow=etf_data.get("outflow", 0),
                    confidence=etf_data.get("confidence", 0.0),
                )
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    return None


@router.get("/composite-score")
async def get_composite_score():
    """获取综合得分（中频刷新：每分钟）"""
    reader = await get_projection_reader()
    state = await reader.get_dashboard_state()
    return {"score": state.get("compositeScore", 0.5)}


# ============ 兼容旧接口 ============

@router.get("", include_in_schema=False)
@router.get("/")
async def get_dashboard_all():
    """
    汇总接口（兼容旧的 /trading/dashboard）
    
    返回所有 Dashboard 数据，用于前端轮询
    """
    return await get_dashboard_data()
