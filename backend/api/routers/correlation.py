"""
Correlation Router - 相关性分析 API 端点
"""
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from infrastructure.logging import get_logger

logger = get_logger("correlation_service.api")

router = APIRouter()


class SignalInfo(BaseModel):
    feature: str
    direction: str
    confidence: float
    strength: float
    scores: dict


class CorrelationSummary(BaseModel):
    symbol: str
    timeframe: str
    available: bool
    timestamp: Optional[str]
    positive_count: int
    negative_count: int
    neutral_count: int
    strong_positive: int
    strong_negative: int


class SignalWeightInfo(BaseModel):
    feature: str
    weight: float
    direction: str
    confidence: float
    strength: float


class CorrelationDetail(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    positive_signals: List[str]
    negative_signals: List[str]
    neutral_signals: List[str]
    signal_assessments: dict
    summary: dict


class TriggerResponse(BaseModel):
    success: bool
    message: str
    symbol: str
    timeframe: str


@router.get("/summary", response_model=CorrelationSummary)
async def get_summary(
    symbol: str = Query("BTC"),
    timeframe: str = Query("1h"),
):
    """获取相关性分析摘要"""
    from services.correlation_service.strategy_adapter import get_correlation_adapter

    adapter = get_correlation_adapter()
    summary = adapter.get_summary(symbol, timeframe)

    return CorrelationSummary(**summary)


@router.get("/signals", response_model=List[SignalWeightInfo])
async def get_signals(
    symbol: str = Query("BTC"),
    timeframe: str = Query("1h"),
    min_confidence: float = Query(0.0),
    direction: Optional[str] = Query(None),
):
    """获取信号权重列表"""
    from services.correlation_service.strategy_adapter import get_correlation_adapter

    adapter = get_correlation_adapter()
    signals = adapter.get_strong_signals(
        symbol, timeframe,
        min_confidence=min_confidence,
        direction=direction,
    )

    return [
        SignalWeightInfo(
            feature=s.feature,
            weight=s.weight,
            direction=s.direction,
            confidence=s.confidence,
            strength=s.strength,
        )
        for s in signals
    ]


@router.get("/detail", response_model=CorrelationDetail)
async def get_detail(
    symbol: str = Query("BTC"),
    timeframe: str = Query("1h"),
):
    """获取完整分析结果"""
    from services.correlation_service.strategy_adapter import get_correlation_adapter

    adapter = get_correlation_adapter()
    adapter.refresh()

    cache_key = f"{symbol}:{timeframe}"
    result = adapter._cache.get(cache_key)

    if not result:
        raise HTTPException(status_code=404, detail=f"No correlation data for {symbol} {timeframe}")

    return CorrelationDetail(**result)


@router.get("/weight/{feature}", response_model=SignalWeightInfo)
async def get_signal_weight(
    feature: str,
    symbol: str = Query("BTC"),
    timeframe: str = Query("1h"),
):
    """获取单个信号的权重"""
    from services.correlation_service.strategy_adapter import get_correlation_adapter

    adapter = get_correlation_adapter()
    sw = adapter.get_signal_weight(feature, symbol, timeframe)

    return SignalWeightInfo(
        feature=sw.feature,
        weight=sw.weight,
        direction=sw.direction,
        confidence=sw.confidence,
        strength=sw.strength,
    )


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_analysis(
    symbol: str = Query("BTC"),
    timeframe: str = Query("1h"),
):
    """手动触发一次分析"""
    try:
        from services.correlation_service import get_correlation_service

        worker = await get_correlation_service()
        result = await worker.run_analysis(symbol, timeframe)

        if "error" in result:
            return TriggerResponse(
                success=False,
                message=result["error"],
                symbol=symbol,
                timeframe=timeframe,
            )

        return TriggerResponse(
            success=True,
            message=f"Analysis completed: +{len(result.get('positive_signals', []))} -{len(result.get('negative_signals', []))}",
            symbol=symbol,
            timeframe=timeframe,
        )

    except Exception as e:
        return TriggerResponse(
            success=False,
            message=str(e),
            symbol=symbol,
            timeframe=timeframe,
        )


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "correlation_service"}
