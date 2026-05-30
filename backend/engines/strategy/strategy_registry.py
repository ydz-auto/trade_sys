"""
Strategy Registry - 策略注册中心

管理所有策略的定义和初始化
"""
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass
import logging

from domain.strategy.models import StrategyDefinition, StrategyType, StrategySignal
from engines.compute.strategy.strategies import BaseStrategy as OldBaseStrategy
from engines.compute.strategy.behavioral_strategies import (
    OpenInterestBehaviorStrategy,
    FundingExtremeReversalStrategy,
    LiquidationCascadeStrategy,
)

logger = logging.getLogger(__name__)


@dataclass
class RegisteredStrategy:
    """已注册的策略"""
    definition: StrategyDefinition
    strategy_class: Optional[Type] = None
    instance: Optional[Any] = None


class StrategyRegistry:
    """策略注册中心"""
    
    def __init__(self):
        self._strategies: Dict[str, RegisteredStrategy] = {}
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self):
        """初始化默认策略 - 按照用户提供的优先级梯队"""
        
        # ===== 第一梯队：爆仓行为策略 =====
        self._register_panic_reversal()
        self._register_liquidation_cascade()
        self._register_oi_flush()
        self._register_short_squeeze()
        self._register_funding_exhaustion()
        
        # ===== 第一梯队：Microstructure 策略 =====
        self._register_imbalance_breakout()
        self._register_sweep_reversal()
        self._register_liquidity_vacuum()
        
        # ===== 第二梯队：其他策略 =====
        self._register_other_strategies()
        
        logger.info(f"StrategyRegistry initialized with {len(self._strategies)} strategies")
    
    def _register_panic_reversal(self):
        """注册 Panic Reversal 策略"""
        definition = StrategyDefinition(
            strategy_id="panic_reversal",
            name="Panic Reversal",
            description="恐慌踩踏后反弹 - 检测 1h 下跌 + 成交量激增",
            strategy_type=StrategyType.BEHAVIORAL,
            priority=100,
            required_features=["liquidation_spike", "return_1h", "volume_ratio"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_liquidation_cascade(self):
        """注册 Liquidation Cascade 策略"""
        definition = StrategyDefinition(
            strategy_id="liquidation_cascade",
            name="Liquidation Cascade",
            description="连锁爆仓延续 - 检测爆仓压力 + OI 变化 + 波动率",
            strategy_type=StrategyType.BEHAVIORAL,
            priority=99,
            required_features=["liquidation_pressure", "oi_delta", "volatility_1h"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_oi_flush(self):
        """注册 OI Flush 策略"""
        definition = StrategyDefinition(
            strategy_id="oi_flush",
            name="OI Flush",
            description="杠杆清洗后趋势重启 - OI 变化 + 资金费率回归",
            strategy_type=StrategyType.BEHAVIORAL,
            priority=98,
            required_features=["oi_delta", "oi_zscore", "funding_delta"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_short_squeeze(self):
        """注册 Short Squeeze 策略"""
        definition = StrategyDefinition(
            strategy_id="short_squeeze",
            name="Short Squeeze",
            description="空头挤压 - 资金费率极端 + 空头压力",
            strategy_type=StrategyType.BEHAVIORAL,
            priority=97,
            required_features=["funding_zscore", "short_pressure", "liquidation_short"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_funding_exhaustion(self):
        """注册 Funding Exhaustion 策略"""
        definition = StrategyDefinition(
            strategy_id="funding_exhaustion",
            name="Funding Exhaustion",
            description="资金费率过热反转 - 资金费率极端值",
            strategy_type=StrategyType.BEHAVIORAL,
            priority=96,
            required_features=["funding_zscore", "funding_delta", "oi_growth"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_imbalance_breakout(self):
        """注册 Imbalance Breakout 策略"""
        definition = StrategyDefinition(
            strategy_id="imbalance_breakout",
            name="Imbalance Breakout",
            description="订单簿失衡突破",
            strategy_type=StrategyType.MICROSTRUCTURE,
            priority=95,
            required_features=["imbalance_5", "depth_ratio", "trade_delta"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_sweep_reversal(self):
        """注册 Sweep Reversal 策略"""
        definition = StrategyDefinition(
            strategy_id="sweep_reversal",
            name="Sweep Reversal",
            description="大单扫盘后反转",
            strategy_type=StrategyType.MICROSTRUCTURE,
            priority=94,
            required_features=["sweep_buy_score", "sweep_sell_score"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_liquidity_vacuum(self):
        """注册 Liquidity Vacuum 策略"""
        definition = StrategyDefinition(
            strategy_id="liquidity_vacuum",
            name="Liquidity Vacuum",
            description="流动性真空突破",
            strategy_type=StrategyType.MICROSTRUCTURE,
            priority=93,
            required_features=["spread", "spread_volatility"],
            tier=1,
        )
        self._strategies[definition.strategy_id] = RegisteredStrategy(
            definition=definition
        )
    
    def _register_other_strategies(self):
        """注册其他策略 - 第二梯队"""
        # Dead Cat Echo
        self._strategies["dead_cat_echo"] = RegisteredStrategy(
            definition=StrategyDefinition(
                strategy_id="dead_cat_echo",
                name="Dead Cat Echo",
                description="暴跌弱反弹后继续下跌",
                strategy_type=StrategyType.TECHNICAL,
                priority=80,
                required_features=["trend_exhaustion", "volume_ratio"],
                tier=2,
            )
        )
        
        # RSI
        self._strategies["rsi"] = RegisteredStrategy(
            definition=StrategyDefinition(
                strategy_id="rsi",
                name="RSI",
                description="RSI 超买超卖策略",
                strategy_type=StrategyType.TECHNICAL,
                priority=50,
                required_features=["rsi_14"],
                tier=2,
            )
        )
        
        # MACD
        self._strategies["macd"] = RegisteredStrategy(
            definition=StrategyDefinition(
                strategy_id="macd",
                name="MACD",
                description="MACD 交叉策略",
                strategy_type=StrategyType.TECHNICAL,
                priority=50,
                required_features=["macd", "macd_signal"],
                tier=2,
            )
        )
