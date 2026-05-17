"""
Backtest Schemas - 回测相关模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class BacktestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BacktestConfig(BaseModel):
    """回测配置"""
    symbol: str = Field(default="BTC/USDT", description="交易品种")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(default=100000, description="初始资金")
    commission: float = Field(default=0.001, description="手续费率")
    slippage: float = Field(default=0.0005, description="滑点率")
    position_size: float = Field(default=0.1, description="仓位比例")
    stop_loss: float = Field(default=0.02, description="止损率")
    take_profit: float = Field(default=0.05, description="止盈率")
    strategy: str = Field(default="sma_crossover", description="策略类型")


class PerformanceMetrics(BaseModel):
    """绩效指标"""
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_trade_duration: float = 0.0


class TradeRecord(BaseModel):
    """交易记录"""
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    side: str


class BacktestResult(BaseModel):
    """回测结果"""
    id: str
    status: BacktestStatus
    config: BacktestConfig
    metrics: Optional[PerformanceMetrics] = None
    trades: List[TradeRecord] = []
    equity_curve: List[float] = []
    drawdown_curve: List[float] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class BacktestRequest(BaseModel):
    """回测请求"""
    config: BacktestConfig


class BacktestListResponse(BaseModel):
    """回测列表响应"""
    backtests: List[BacktestResult]
    total: int
