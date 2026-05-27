"""
Multi-Strategy Orchestrator (多策略编排器)

核心功能：
1. Regime-based 策略分配：根据当前 Market State 激活/停用策略
2. Signal 组合与优先级管理：处理多个信号冲突
3. 风险预算分配：基于当前状态控制总风险
4. 执行时序管理：策略信号不是同时发的，有合理的时间窗口

配合 V2 策略和 MarketStateMachine 使用，真正实现“组合使用而非单打独斗”。
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import logging

from .v2_base import (
    StateAwareStrategy,
    StrategySignalV2,
    SignalDirection,
)
from .v2_core_strategies import (
    OpenInterestBehaviorV2,
    TradePressureExhaustionV2,
    FundingExtremeReversalV2,
    LiquidationCascadeV2,
    MomentumIgnitionV2,
    create_v2_configs,
)
from domain.market_state.state import MarketState, RegimeType
from domain.event.base_event import BaseEvent
from domain.config.strategy_config import StrategyConfigV2
from infrastructure.logging import get_logger

logger = get_logger("strategy_orchestrator")


class StrategyPriority(Enum):
    """策略优先级（数字越小优先级越高）"""
    HIGHEST = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class RegimeStrategyMapping:
    """策略在不同 Regime 下的激活规则"""
    strategy_id: str
    
    # 这个策略在哪些 Regime 下激活
    active_regimes: List[RegimeType] = field(default_factory=list)
    
    # 优先级
    priority: StrategyPriority = StrategyPriority.NORMAL
    
    # 权重（用于多信号组合时）
    weight: float = 1.0
    
    # 最大单策略仓位占比
    max_position_pct: float = 0.2


@dataclass
class OrchestratorDecision:
    """编排器的最终决定"""
    timestamp: datetime
    symbol: str
    
    # 最终决定
    final_signal: Optional[StrategySignalV2] = None
    
    # 所有策略信号（用于debug）
    all_signals: List[StrategySignalV2] = field(default_factory=list)
    
    # 决定的理由
    reason: str = ""
    
    # 风险预算使用情况
    risk_budget_used: float = 0.0


class MultiStrategyOrchestrator:
    """
    多策略编排器 - 真正的“交易大脑”
    
    核心设计原则：
    1. 不是每个策略都同时工作，而是根据 Regime 决定谁工作
    2. 有清晰的信号冲突解决机制
    3. 有集中的风险预算管理
    """
    
    def __init__(
        self,
        symbol: str,
        strategy_classes: Optional[Dict] = None,
        strategy_configs: Optional[Dict[str, StrategyConfigV2]] = None,
    ):
        self.symbol = symbol
        
        # 策略实例
        self.strategies: Dict[str, StateAwareStrategy] = {}
        
        # 策略在不同 Regime 下的激活规则（可配置）
        self.regime_mappings: Dict[str, RegimeStrategyMapping] = {}
        
        # 风险预算
        self.total_risk_budget: float = 1.0  # 总风险预算
        self.used_risk_budget: float = 0.0
        
        # 初始化策略
        if strategy_classes is None:
            strategy_classes = {
                'open_interest_behavior_v2': OpenInterestBehaviorV2,
                'trade_pressure_exhaustion_v2': TradePressureExhaustionV2,
                'funding_extreme_reversal_v2': FundingExtremeReversalV2,
                'liquidation_cascade_v2': LiquidationCascadeV2,
                'momentum_ignition_v2': MomentumIgnitionV2,
            }
        
        if strategy_configs is None:
            strategy_configs = create_v2_configs()
        
        # 创建策略实例
        for strat_id, strat_class in strategy_classes.items():
            if strat_id in strategy_configs:
                config = strategy_configs[strat_id]
                self.strategies[strat_id] = strat_class(config)
                logger.info(f"Loaded strategy: {strat_id}")
        
        # 设置默认 Regime 激活规则（可优化）
        self._setup_default_regime_mappings()
    
    def _setup_default_regime_mappings(self):
        """设置默认的策略-Regime 激活映射"""
        
        # 1. OI Behavior: 在大部分状态下都工作
        self.regime_mappings['open_interest_behavior_v2'] = RegimeStrategyMapping(
            strategy_id='open_interest_behavior_v2',
            active_regimes=[
                RegimeType.TRENDING_UP,
                RegimeType.TRENDING_DOWN,
                RegimeType.MEAN_REVERTING,
                RegimeType.QUIET,
            ],
            priority=StrategyPriority.NORMAL,
            weight=1.0,
            max_position_pct=0.2,
        )
        
        # 2. Pressure Exhaustion: 在大部分状态下工作，特别是 Crash/Squeeze
        self.regime_mappings['trade_pressure_exhaustion_v2'] = RegimeStrategyMapping(
            strategy_id='trade_pressure_exhaustion_v2',
            active_regimes=[
                RegimeType.TRENDING_UP,
                RegimeType.TRENDING_DOWN,
                RegimeType.MEAN_REVERTING,
                RegimeType.CRASH,
                RegimeType.SQUEEZE,
            ],
            priority=StrategyPriority.HIGH,
            weight=1.2,
            max_position_pct=0.25,
        )
        
        # 3. Funding Reversal: 在大部分状态下工作，但更适合在极端状况
        self.regime_mappings['funding_extreme_reversal_v2'] = RegimeStrategyMapping(
            strategy_id='funding_extreme_reversal_v2',
            active_regimes=[
                RegimeType.TRENDING_UP,
                RegimeType.TRENDING_DOWN,
                RegimeType.CRASH,
                RegimeType.SQUEEZE,
            ],
            priority=StrategyPriority.HIGH,
            weight=1.1,
            max_position_pct=0.2,
        )
        
        # 4. Liquidation Cascade: 只在 Crash/Squeeze 激活
        self.regime_mappings['liquidation_cascade_v2'] = RegimeStrategyMapping(
            strategy_id='liquidation_cascade_v2',
            active_regimes=[
                RegimeType.CRASH,
                RegimeType.SQUEEZE,
            ],
            priority=StrategyPriority.HIGHEST,
            weight=1.5,
            max_position_pct=0.3,
        )
        
        # 5. Momentum Ignition: 只在趋势和突破状态激活
        self.regime_mappings['momentum_ignition_v2'] = RegimeStrategyMapping(
            strategy_id='momentum_ignition_v2',
            active_regimes=[
                RegimeType.TRENDING_UP,
                RegimeType.TRENDING_DOWN,
                RegimeType.BREAKOUT,
            ],
            priority=StrategyPriority.NORMAL,
            weight=1.0,
            max_position_pct=0.2,
        )
        
        logger.info("Default Regime-Strategy mappings initialized")
    
    def is_strategy_active(
        self,
        strategy_id: str,
        market_state: MarketState,
    ) -> bool:
        """检查策略在当前 State 下是否激活"""
        mapping = self.regime_mappings.get(strategy_id)
        if not mapping:
            return False
        
        return market_state.regime in mapping.active_regimes
    
    def process(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent] = None,
        current_features: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorDecision:
        """
        核心编排逻辑
        
        步骤：
        1. 获取当前 Regime
        2. 激活对应策略
        3. 收集所有信号
        4. 解决冲突（优先级、权重、方向一致性等）
        5. 考虑风险预算
        6. 返回最终决定
        """
        current_features = current_features or {}
        decision = OrchestratorDecision(
            timestamp=market_state.timestamp,
            symbol=market_state.symbol,
        )
        
        logger.debug(f"Processing in Regime: {market_state.regime}")
        
        # Step 1: 收集所有激活策略的信号
        all_signals = []
        for strat_id, strategy in self.strategies.items():
            if not strategy.is_enabled:
                continue
            
            if not self.is_strategy_active(strat_id, market_state):
                continue
            
            # 生成信号
            signal = strategy.generate_signal_v2(
                market_state=market_state,
                triggering_event=triggering_event,
                current_features=current_features,
            )
            
            if signal:
                all_signals.append(signal)
                logger.debug(f"Signal from {strat_id}: {signal.direction}, conf={signal.confidence:.2f}")
        
        decision.all_signals = all_signals
        
        if not all_signals:
            decision.reason = "No signals from active strategies"
            return decision
        
        # Step 2: 按优先级排序，解决冲突
        final_signal = self._resolve_signal_conflicts(all_signals, market_state)
        
        if final_signal:
            decision.final_signal = final_signal
            decision.reason = (
                f"Selected: {final_signal.strategy_name}, "
                f"dir={final_signal.direction}, "
                f"conf={final_signal.confidence:.2f}"
            )
            logger.info(decision.reason)
        else:
            decision.reason = "Conflicting signals or no strong consensus"
        
        return decision
    
    def _resolve_signal_conflicts(
        self,
        signals: List[StrategySignalV2],
        market_state: MarketState,
    ) -> Optional[StrategySignalV2]:
        """解决多个信号之间的冲突"""
        if not signals:
            return None
        
        # Step 1: 按策略优先级分组
        signals_by_priority = {}
        for signal in signals:
            mapping = self.regime_mappings.get(signal.strategy_id)
            priority = mapping.priority if mapping else StrategyPriority.NORMAL
            if priority not in signals_by_priority:
                signals_by_priority[priority] = []
            signals_by_priority[priority].append(signal)
        
        # Step 2: 从高优先级开始处理
        sorted_priorities = sorted(signals_by_priority.keys(), key=lambda p: p.value)
        
        for priority in sorted_priorities:
            prio_signals = signals_by_priority[priority]
            
            if not prio_signals:
                continue
            
            # 同一个优先级内，检查方向一致性
            long_signals = [s for s in prio_signals if s.direction in [SignalDirection.LONG]]
            short_signals = [s for s in prio_signals if s.direction in [SignalDirection.SHORT]]
            
            # 优先处理方向一致的情况
            if len(long_signals) > len(short_signals) + 1:  # 大多数看多
                return self._select_best_signal(long_signals)
            elif len(short_signals) > len(long_signals) + 1:  # 大多数看空
                return self._select_best_signal(short_signals)
            elif len(prio_signals) == 1:  # 只有一个信号
                return prio_signals[0]
        
        # 如果有冲突但没有明显一致，选择信心度最高的
        return self._select_best_signal(signals)
    
    def _select_best_signal(self, signals: List[StrategySignalV2]) -> StrategySignalV2:
        """在一组信号中选最好的（基于策略权重 + 信心度）"""
        if not signals:
            return None
        
        best_score = -1.0
        best_signal = None
        
        for signal in signals:
            mapping = self.regime_mappings.get(signal.strategy_id)
            weight = mapping.weight if mapping else 1.0
            
            score = signal.confidence * weight
            
            if score > best_score:
                best_score = score
                best_signal = signal
        
        return best_signal
    
    def get_active_strategies(self, market_state: MarketState) -> List[str]:
        """获取当前激活的策略列表"""
        active_strategies = []
        for strat_id, strategy in self.strategies.items():
            if self.is_strategy_active(strat_id, market_state):
                active_strategies.append(strat_id)
        return active_strategies
    
    def enable_strategy(self, strategy_id: str):
        if strategy_id in self.strategies:
            self.strategies[strategy_id].enable()
    
    def disable_strategy(self, strategy_id: str):
        if strategy_id in self.strategies:
            self.strategies[strategy_id].disable()


def create_orchestrator(
    symbol: str = "BTCUSDT",
) -> MultiStrategyOrchestrator:
    """工厂函数：创建默认配置的编排器"""
    strategy_configs = create_v2_configs()
    return MultiStrategyOrchestrator(
        symbol=symbol,
        strategy_configs=strategy_configs,
    )
