"""
Trading Mode - 交易模式管理

统一管理 demo/paper/prod 三种交易模式
"""
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class TradingMode(str, Enum):
    """交易模式枚举"""
    DEMO = "demo"  # 测试环境: Binance Testnet + OKX Demo
    PAPER = "paper"  # 模拟交易: 真实行情 + 本地撮合 (最重要!)
    PROD = "prod"  # 真实交易: 真实行情 + 真实下单


class TradingModeConfig(BaseModel):
    """交易模式配置"""
    mode: TradingMode = Field(default=TradingMode.DEMO, description="当前交易模式")
    
    # 行情数据源
    market_data_source: str = Field(default="real", description="行情数据源: real/testnet")
    
    # 订单执行方式
    order_execution: str = Field(default="testnet", description="订单执行: testnet/mock/real")
    
    # 是否显示模拟警告
    show_paper_warning: bool = Field(default=True, description="Paper模式是否显示警告")
    
    # Paper Trading 专用配置
    paper_config: Dict = Field(default_factory=dict, description="Paper Trading配置")
    
    # Demo 配置
    demo_config: Dict = Field(default_factory=dict, description="Demo配置")
    
    # Prod 配置
    prod_config: Dict = Field(default_factory=dict, description="Prod配置")


def get_trading_mode_config(mode: Optional[TradingMode] = None) -> TradingModeConfig:
    """
    根据模式获取配置
    
    Args:
        mode: 交易模式，如果为None则从环境变量读取
        
    Returns:
        TradingModeConfig
    """
    import os
    
    if mode is None:
        mode_str = os.getenv("MODE", "demo")
        try:
            mode = TradingMode(mode_str)
        except ValueError:
            mode = TradingMode.DEMO
    
    if mode == TradingMode.DEMO:
        return TradingModeConfig(
            mode=TradingMode.DEMO,
            market_data_source="testnet",
            order_execution="testnet",
            show_paper_warning=False,
            demo_config={
                "description": "Binance Testnet / OKX Demo Trading",
                "testnet": True,
            }
        )
    elif mode == TradingMode.PAPER:
        return TradingModeConfig(
            mode=TradingMode.PAPER,
            market_data_source="real",
            order_execution="mock",
            show_paper_warning=True,
            paper_config={
                "description": "Real Market Data + Local Matching Engine",
                "initial_balance": {"USDT": 100000.0},
                "slippage": 0.001,  # 0.1% 滑点
                "fee": {"maker": 0.0002, "taker": 0.0004},  # 费率
                "match_real_depth": True,  # 是否模拟真实深度
            }
        )
    else:  # PROD
        return TradingModeConfig(
            mode=TradingMode.PROD,
            market_data_source="real",
            order_execution="real",
            show_paper_warning=False,
            prod_config={
                "description": "Live Trading - Real Execution",
                "require_approval": True,
            }
        )


def get_current_mode() -> TradingMode:
    """获取当前交易模式"""
    import os
    mode_str = os.getenv("MODE", "demo")
    try:
        return TradingMode(mode_str)
    except ValueError:
        return TradingMode.DEMO
