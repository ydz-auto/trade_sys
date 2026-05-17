"""
Projection Router - Runtime State API

暴露 Projection 状态给前端
"""

from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from api.services.projection_reader import get_projection_reader


router = APIRouter(prefix="/projection", tags=["projection"])


class TimelineEvent(BaseModel):
    event_id: str
    event_type: str
    symbol: str
    timestamp: str
    title: str
    description: str
    severity: str


class DecisionItem(BaseModel):
    decision_id: str
    symbol: str
    action: str
    quantity: float
    confidence: float
    reason: str
    status: str
    approved: Optional[bool] = None
    timestamp: str


class PositionItem(BaseModel):
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: int


class RiskState(BaseModel):
    level: str
    score: int
    components: dict
    warnings: List[str]


@router.get("/dashboard")
async def get_dashboard_state():
    """获取 Dashboard 状态"""
    reader = await get_projection_reader()
    return await reader.get_dashboard_state()


@router.get("/prices")
async def get_prices():
    """获取价格列表"""
    reader = await get_projection_reader()
    return await reader.get_prices()


@router.get("/signals")
async def get_signals(symbol: Optional[str] = None):
    """获取信号"""
    reader = await get_projection_reader()
    return await reader.get_signals(symbol)


@router.get("/decision/latest")
async def get_decision_latest(symbol: Optional[str] = None):
    """获取最新决策"""
    reader = await get_projection_reader()
    return await reader.get_decision_latest(symbol)


@router.get("/decision/history")
async def get_decision_history(
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """获取决策历史"""
    reader = await get_projection_reader()
    return await reader.get_decision_history(symbol, limit)


@router.get("/decision/stats")
async def get_decision_stats():
    """获取决策统计"""
    reader = await get_projection_reader()
    return await reader.get_decision_stats()


@router.get("/risk/state")
async def get_risk_state():
    """获取风控状态"""
    reader = await get_projection_reader()
    return await reader.get_risk_state()


@router.get("/risk/level")
async def get_risk_level():
    """获取风险等级"""
    reader = await get_projection_reader()
    return {"level": await reader.get_risk_level()}


@router.get("/risk/daily")
async def get_risk_daily():
    """获取每日风控指标"""
    reader = await get_projection_reader()
    return await reader.get_risk_daily_metrics()


@router.get("/position/current")
async def get_positions():
    """获取当前持仓"""
    reader = await get_projection_reader()
    return await reader.get_positions()


@router.get("/position/{symbol}")
async def get_position(symbol: str):
    """获取单个持仓"""
    reader = await get_projection_reader()
    return await reader.get_position(symbol)


@router.get("/position/pnl")
async def get_position_pnl():
    """获取持仓盈亏"""
    reader = await get_projection_reader()
    return await reader.get_position_pnl()


@router.get("/timeline")
async def get_timeline(
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """获取事件时间线"""
    reader = await get_projection_reader()
    events = await reader.get_timeline(symbol, limit)
    return {"events": events, "count": len(events)}


@router.get("/metrics")
async def get_metrics():
    """获取系统指标"""
    reader = await get_projection_reader()
    return await reader.get_metrics()
