"""
Trading Mode - 交易模式领域定义

核心组件:
- TradingMode: 模式枚举 (BACKTEST/PAPER/LIVE)
- ModeTransition: 模式转换枚举
- ModeConfig: 模式配置
- MODE_CONFIGS: 模式配置表
- ModeState: 模式状态枚举
- ModeStatus: 模式状态数据
- ModeTransitionRequest: 模式转换请求

注意:
- get_trading_mode_manager() 定义在 runtime/trading_mode_manager.py
- 通过 lazy import 在本模块 re-export，保持向后兼容
"""
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

from pydantic import BaseModel, Field


class TradingMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class ModeTransition(str, Enum):
    BACKTEST_TO_PAPER = "backtest->paper"
    BACKTEST_TO_LIVE = "backtest->live"
    PAPER_TO_BACKTEST = "paper->backtest"
    PAPER_TO_LIVE = "paper->live"
    LIVE_TO_BACKTEST = "live->backtest"
    LIVE_TO_PAPER = "live->paper"


@dataclass
class ModeConfig:
    market_data_source: str
    order_execution: str
    risk_engine: str
    portfolio_isolated: bool
    require_confirmation: bool
    color: str
    warning: Optional[str] = None


MODE_CONFIGS: Dict[TradingMode, ModeConfig] = {
    TradingMode.BACKTEST: ModeConfig(
        market_data_source="historical",
        order_execution="simulated",
        risk_engine="simulated",
        portfolio_isolated=True,
        require_confirmation=False,
        color="#3B82F6",
        warning=None,
    ),
    TradingMode.PAPER: ModeConfig(
        market_data_source="real",
        order_execution="simulated",
        risk_engine="real",
        portfolio_isolated=True,
        require_confirmation=False,
        color="#F59E0B",
        warning="Paper Trading: 真实行情 + 模拟下单",
    ),
    TradingMode.LIVE: ModeConfig(
        market_data_source="real",
        order_execution="real",
        risk_engine="real",
        portfolio_isolated=True,
        require_confirmation=True,
        color="#EF4444",
        warning="⚠️ LIVE MODE: 真实交易，请谨慎操作！",
    ),
}


class ModeState(str, Enum):
    IDLE = "idle"
    TRANSITIONING = "transitioning"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class ModeStatus:
    mode: TradingMode
    state: ModeState
    previous_mode: Optional[TradingMode] = None
    transition_time: Optional[str] = None
    error: Optional[str] = None
    confirmed: bool = False


class ModeTransitionRequest(BaseModel):
    target_mode: TradingMode
    reason: str = ""
    confirmed: bool = False
    force: bool = False


def get_trading_mode_manager():
    from runtime.trading_mode_manager import TradingModeManager
    return TradingModeManager()
