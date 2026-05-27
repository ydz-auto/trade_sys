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
    calculate_panic_reversal,
    calculate_oi_flush,
    calculate_short_squeeze,
    calculate_funding_exhaustion_trap,
    calculate_dead_cat_echo,
    calculate_imbalance_pressure,
    calculate_sweep_detection,
    calculate_liquidity_vacuum,
    calculate_aggressive_flow,
    calculate_volume_climax_fade,
    calculate_weak_bounce_short,
    calculate_breakout,
    calculate_volatility_expansion,
    calculate_momentum_ignition,
    calculate_sma_crossover,
    calculate_ema_crossover,
    calculate_bollinger_bands,
    calculate_momentum,
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
            'panic_reversal': self._calculate_using_panic_reversal_calculator,
            'oi_flush': self._calculate_using_oi_flush_calculator,
            'short_squeeze': self._calculate_using_short_squeeze_calculator,
            'funding_exhaustion_trap': self._calculate_using_funding_exhaustion_trap_calculator,
            'dead_cat_echo': self._calculate_using_dead_cat_echo_calculator,
            'imbalance_pressure': self._calculate_using_imbalance_pressure_calculator,
            'sweep_detection': self._calculate_using_sweep_detection_calculator,
            'liquidity_vacuum': self._calculate_using_liquidity_vacuum_calculator,
            'aggressive_flow': self._calculate_using_aggressive_flow_calculator,
            'volume_climax_fade': self._calculate_using_volume_climax_fade_calculator,
            'weak_bounce_short': self._calculate_using_weak_bounce_short_calculator,
            'breakout': self._calculate_using_breakout_calculator,
            'volatility_expansion': self._calculate_using_volatility_expansion_calculator,
            'momentum_ignition': self._calculate_using_momentum_ignition_calculator,
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
    
    def _calculate_using_panic_reversal_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用恐慌反转无状态计算器"""
        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')
        
        signal_dict, new_state = calculate_panic_reversal(
            return_1h=return_1h,
            volume_ratio=volume_ratio,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_oi_flush_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用OI清洗无状态计算器"""
        oi_delta = features.get('oi_delta')
        funding_delta = features.get('funding_delta')
        return_1h = features.get('return_1h')
        close = features.get('close')
        
        signal_dict, new_state = calculate_oi_flush(
            oi_delta=oi_delta,
            funding_delta=funding_delta,
            return_1h=return_1h,
            close=close,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_short_squeeze_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用空头挤压无状态计算器"""
        funding_zscore = features.get('funding_zscore')
        oi_delta = features.get('oi_delta')
        short_pressure = features.get('short_pressure')
        
        signal_dict, new_state = calculate_short_squeeze(
            funding_zscore=funding_zscore,
            oi_delta=oi_delta,
            short_pressure=short_pressure,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_funding_exhaustion_trap_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用资金费率耗尽陷阱无状态计算器"""
        funding_zscore = features.get('funding_zscore')
        funding_divergence = features.get('funding_divergence')
        
        signal_dict, new_state = calculate_funding_exhaustion_trap(
            funding_zscore=funding_zscore,
            funding_divergence=funding_divergence,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_dead_cat_echo_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用死猫回声无状态计算器"""
        return_4h = features.get('return_4h')
        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')
        
        signal_dict, new_state = calculate_dead_cat_echo(
            return_4h=return_4h,
            return_1h=return_1h,
            volume_ratio=volume_ratio,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_imbalance_pressure_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用订单簿失衡压力无状态计算器"""
        imbalance_5 = features.get('imbalance_5')
        microprice = features.get('microprice')
        mid_price = features.get('mid_price')
        
        signal_dict, new_state = calculate_imbalance_pressure(
            imbalance_5=imbalance_5,
            microprice=microprice,
            mid_price=mid_price,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_sweep_detection_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用扫单检测无状态计算器"""
        sweep_buy_score = features.get('sweep_buy_score')
        sweep_sell_score = features.get('sweep_sell_score')
        
        signal_dict, new_state = calculate_sweep_detection(
            sweep_buy_score=sweep_buy_score,
            sweep_sell_score=sweep_sell_score,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_liquidity_vacuum_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用流动性真空无状态计算器"""
        spread = features.get('spread')
        top5_depth = features.get('top5_depth')
        cancel_rate = features.get('cancel_rate')
        trade_delta = features.get('trade_delta')
        
        signal_dict, new_state = calculate_liquidity_vacuum(
            spread=spread,
            top5_depth=top5_depth,
            cancel_rate=cancel_rate,
            trade_delta=trade_delta,
            prev_avg_spread=state.avg_spread,
            prev_top5_depth=state.prev_top5_depth,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_aggressive_flow_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用激进流向无状态计算器"""
        cumulative_delta = features.get('cumulative_delta')
        aggressive_buy_volume = features.get('aggressive_buy_volume')
        aggressive_sell_volume = features.get('aggressive_sell_volume')
        
        signal_dict, new_state = calculate_aggressive_flow(
            cumulative_delta=cumulative_delta,
            aggressive_buy_volume=aggressive_buy_volume,
            aggressive_sell_volume=aggressive_sell_volume,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_volume_climax_fade_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用放量高潮衰竭无状态计算器"""
        volume_ratio = features.get('volume_ratio')
        upper_shadow_ratio = features.get('upper_shadow_ratio')
        return_1h = features.get('return_1h')
        
        signal_dict, new_state = calculate_volume_climax_fade(
            volume_ratio=volume_ratio,
            upper_shadow_ratio=upper_shadow_ratio,
            return_1h=return_1h,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_weak_bounce_short_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用弱反弹做空无状态计算器"""
        return_4h = features.get('return_4h')
        return_1h = features.get('return_1h')
        volume_ratio = features.get('volume_ratio')
        
        signal_dict, new_state = calculate_weak_bounce_short(
            return_4h=return_4h,
            return_1h=return_1h,
            volume_ratio=volume_ratio,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_breakout_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用突破无状态计算器"""
        close = features.get('close')
        high = features.get('high')
        low = features.get('low')
        volume_ratio = features.get('volume_ratio')
        range_high = features.get('range_high')
        range_low = features.get('range_low')
        
        signal_dict, new_state = calculate_breakout(
            close=close,
            high=high,
            low=low,
            volume_ratio=volume_ratio,
            range_high=range_high,
            range_low=range_low,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_volatility_expansion_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用波动率扩张无状态计算器"""
        atr_ratio = features.get('atr_ratio')
        price_position = features.get('price_position')
        close = features.get('close')
        
        signal_dict, new_state = calculate_volatility_expansion(
            atr_ratio=atr_ratio,
            price_position=price_position,
            close=close,
            params=params
        )
        
        return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
    
    def _calculate_using_momentum_ignition_calculator(
        self,
        strategy_id: str,
        symbol: str,
        features: Dict[str, Any],
        state: StrategyInstanceState,
        params: Dict[str, Any]
    ):
        """使用动量点火无状态计算器"""
        volume_ratio = features.get('volume_ratio')
        return_1h = features.get('return_1h')
        
        signal_dict, new_state = calculate_momentum_ignition(
            volume_ratio=volume_ratio,
            return_1h=return_1h,
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
