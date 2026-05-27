"""
Strategy Runtime - 策略运行时

负责策略的执行、状态管理和信号生成。
"""
from typing import Dict, Any, Optional, List
import logging

from .strategy_state import StrategyStateManager, StrategyInstanceState
from .models import StrategySignal, StrategyAction
from engines.compute.strategy.calculators import (
    calculate_rsi_signal,
    calculate_macd_signal,
    calculate_trend_following_signal,
    calculate_bb_compression_signal,
)
from engines.compute.strategy.strategies import (
    RSIStrategy,
    MACDStrategy,
    PanicReversalStrategy,
    LongLiquidationBounceStrategy,
    VolumeClimaxFadeStrategy,
    WeakBounceShortStrategy,
    DeadCatEchoStrategy,
    OIFlushStrategy,
    ShortSqueezeStrategy,
    FundingExhaustionTrapStrategy,
    ImbalancePressureStrategy,
    SweepDetectionStrategy,
    LiquidityVacuumStrategy,
    AggressiveFlowStrategy,
    BreakoutStrategy,
    TrendFollowingStrategy,
    VolatilityExpansionStrategy,
    BBCompressionBreakoutStrategy,
    MomentumIgnitionStrategy,
)

logger = logging.getLogger(__name__)


class StrategyRuntime:
    """策略运行时 - 管理策略执行和状态"""
    
    def __init__(self):
        self.state_manager = StrategyStateManager()
        self._strategy_classes = {
            'rsi': RSIStrategy,
            'macd': MACDStrategy,
            'panic_reversal': PanicReversalStrategy,
            'long_liquidation_bounce': LongLiquidationBounceStrategy,
            'volume_climax_fade': VolumeClimaxFadeStrategy,
            'weak_bounce_short': WeakBounceShortStrategy,
            'dead_cat_echo': DeadCatEchoStrategy,
            'oi_flush': OIFlushStrategy,
            'short_squeeze': ShortSqueezeStrategy,
            'funding_exhaustion_trap': FundingExhaustionTrapStrategy,
            'imbalance_pressure': ImbalancePressureStrategy,
            'sweep_detection': SweepDetectionStrategy,
            'liquidity_vacuum': LiquidityVacuumStrategy,
            'aggressive_flow': AggressiveFlowStrategy,
            'breakout': BreakoutStrategy,
            'trend_following': TrendFollowingStrategy,
            'volatility_expansion': VolatilityExpansionStrategy,
            'bb_compression_breakout': BBCompressionBreakoutStrategy,
            'momentum_ignition': MomentumIgnitionStrategy,
        }
        # 新的无状态计算器映射
        self._calculator_map = {
            'rsi': self._calculate_using_rsi_calculator,
            'macd': self._calculate_using_macd_calculator,
            'trend_following': self._calculate_using_trend_calculator,
            'bb_compression_breakout': self._calculate_using_bollinger_calculator,
        }
    
    def process_strategy(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategySignal]:
        """
        处理单个策略，生成信号
        
        Args:
            strategy_id: 策略ID
            symbol: 交易对
            features: 特征数据
            params: 策略参数（可选）
            
        Returns:
            策略信号，没有信号则返回 None
        """
        params = params or {}
        
        # 获取或创建状态
        state = self.state_manager.get_or_create_state(strategy_id, symbol)
        
        if not state.enabled:
            return None
        
        # 优先使用无状态计算器
        if strategy_id in self._calculator_map:
            try:
                calculator_func = self._calculator_map[strategy_id]
                signal, new_state_data = calculator_func(strategy_id, symbol, features, state, params)
                
                # 更新状态
                if new_state_data:
                    self.state_manager.update_state(strategy_id, symbol, **new_state_data)
                
                return signal
            except Exception as e:
                logger.error(f"Error processing strategy {strategy_id} with calculator: {e}")
                # 降级到旧方法
                pass
        
        # 回退到旧的策略类方法（保持兼容性）
        strategy_class = self._strategy_classes.get(strategy_id)
        if not strategy_class:
            logger.warning(f"Unknown strategy: {strategy_id}")
            return None
        
        try:
            signal, new_state_data = self._calculate_strategy_signal(
                strategy_class,
                strategy_id,
                symbol,
                features,
                state,
                params
            )
            
            # 更新状态
            if new_state_data:
                self.state_manager.update_state(strategy_id, symbol, **new_state_data)
            
            return signal
        except Exception as e:
            logger.error(f"Error processing strategy {strategy_id}: {e}")
            return None
    
    def _calculate_using_rsi_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用新的 RSI 无状态计算器"""
        rsi_value = features.get('rsi_14')
        if rsi_value is None:
            return None, {}
        
        signal_dict, new_state = calculate_rsi_signal(
            rsi_value=rsi_value,
            prev_rsi=state.prev_rsi,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_macd_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用新的 MACD 无状态计算器"""
        macd_value = features.get('macd')
        signal_value = features.get('macd_signal')
        if macd_value is None or signal_value is None:
            return None, {}
        
        signal_dict, new_state = calculate_macd_signal(
            macd_value=macd_value,
            signal_value=signal_value,
            prev_macd=state.prev_macd,
            prev_signal=state.prev_signal,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_trend_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用新的趋势跟踪无状态计算器"""
        ema_fast = features.get('ema_fast') or features.get('ema_10')
        ema_slow = features.get('ema_slow') or features.get('ema_50')
        if ema_fast is None or ema_slow is None:
            return None, {}
        
        signal_dict, new_state = calculate_trend_following_signal(
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            prev_ema_fast=state.prev_ema_fast,
            prev_ema_slow=state.prev_ema_slow,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_bollinger_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用新的布林带无状态计算器"""
        bb_upper = features.get('bb_upper')
        bb_lower = features.get('bb_lower')
        bb_middle = features.get('bb_middle')
        close = features.get('close')
        
        if None in (bb_upper, bb_lower, bb_middle, close):
            return None, {}
        
        signal_dict, new_state = calculate_bb_compression_signal(
            bb_upper=bb_upper,
            bb_lower=bb_lower,
            bb_middle=bb_middle,
            close=close,
            prev_above_middle=state.prev_above_middle,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _build_signal(
        self,
        signal_dict: Optional[Dict[str, Any]],
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any]
    ) -> Optional[StrategySignal]:
        """从信号字典构建标准信号对象"""
        if not signal_dict:
            return None
        
        action_map = {
            'buy': StrategyAction.LONG,
            'sell': StrategyAction.SHORT,
            'close': StrategyAction.CLOSE,
        }
        
        return StrategySignal(
            strategy_id=strategy_id,
            strategy_name=strategy_id,
            strategy_type='technical',
            symbol=symbol,
            action=action_map.get(signal_dict.get('signal_type', 'do_nothing'), StrategyAction.DO_NOTHING),
            confidence=signal_dict.get('confidence', 0.5),
            reason=signal_dict.get('reason', ''),
            timestamp_ms=int(__import__('datetime').datetime.now().timestamp() * 1000),
            price=features.get('close'),
            quantity=None,
            metadata={}
        )
    
    def _calculate_strategy_signal(
        self,
        strategy_class,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """
        根据策略类型调用相应的计算方法（旧方法，保持兼容性）
        
        返回 (signal, new_state_data)
        """
        # 创建策略实例（临时，后续会移除）
        strategy = strategy_class(strategy_id=strategy_id, **params)
        
        # 调用生成信号方法
        try:
            signal_dict = strategy.generate_signal(features)
        except Exception as e:
            logger.error(f"Error in strategy {strategy_id} generate_signal: {e}")
            return None, {}
        
        if not signal_dict:
            return None, {}
        
        # 转换为标准信号格式
        action_map = {
            'buy': StrategyAction.LONG,
            'sell': StrategyAction.SHORT,
            'close': StrategyAction.CLOSE,
        }
        
        signal = StrategySignal(
            strategy_id=strategy_id,
            strategy_name=strategy_id,
            strategy_type=getattr(strategy, 'strategy_type', 'technical'),
            symbol=symbol,
            action=action_map.get(signal_dict.get('signal_type', 'do_nothing'), StrategyAction.DO_NOTHING),
            confidence=signal_dict.get('confidence', 0.5),
            reason=signal_dict.get('reason', ''),
            timestamp_ms=int(__import__('datetime').datetime.now().timestamp() * 1000),
            price=features.get('close'),
            quantity=getattr(strategy, 'default_quantity', None),
            metadata={}
        )
        
        # 尝试提取新状态数据（临时方案）
        new_state_data = {}
        if hasattr(strategy, '_rsi_prev'):
            new_state_data['prev_rsi'] = strategy._rsi_prev
        if hasattr(strategy, '_macd_prev'):
            new_state_data['prev_macd'] = strategy._macd_prev
        if hasattr(strategy, '_signal_prev'):
            new_state_data['prev_signal'] = strategy._signal_prev
        if hasattr(strategy, '_ema_fast_prev'):
            new_state_data['prev_ema_fast'] = strategy._ema_fast_prev
        if hasattr(strategy, '_ema_slow_prev'):
            new_state_data['prev_ema_slow'] = strategy._ema_slow_prev
        if hasattr(strategy, '_prev_above_middle'):
            new_state_data['prev_above_middle'] = strategy._prev_above_middle
        
        return signal, new_state_data
    
    def enable_strategy(self, strategy_id: str, symbol: str):
        """启用策略"""
        self.state_manager.update_state(strategy_id, symbol, enabled=True)
    
    def disable_strategy(self, strategy_id: str, symbol: str):
        """禁用策略"""
        self.state_manager.update_state(strategy_id, symbol, enabled=False)
    
    def get_strategy_state(self, strategy_id: str, symbol: str) -> Optional[StrategyInstanceState]:
        """获取策略状态"""
        return self.state_manager.get_state(strategy_id, symbol)
    
    def list_all_states(self) -> List[StrategyInstanceState]:
        """列出所有策略状态"""
        return self.state_manager.list_all_states()


# 全局单例
_strategy_runtime: Optional[StrategyRuntime] = None


def get_strategy_runtime() -> StrategyRuntime:
    """获取策略运行时单例"""
    global _strategy_runtime
    if _strategy_runtime is None:
        _strategy_runtime = StrategyRuntime()
    return _strategy_runtime
