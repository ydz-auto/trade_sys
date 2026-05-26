"""
Behavioral and Event-Driven Strategies Module

第一梯队（优先）：
1. Open Interest Behavior Strategy - OI行为策略
2. Funding Extreme Reversal Strategy - Funding极端反转
3. Liquidation Cascade Strategy - 爆仓连锁策略

第二梯队：
4. CVD Divergence Strategy - CVD背离策略
5. Whale Trade Strategy - 大单策略
6. Funding Settlement Strategy - 资金费率结算事件
"""
import numpy as np
from typing import Any, Dict, Optional
from .strategies import StrategySignal, ActionType, StrategyType, BaseStrategy


class OpenInterestBehaviorStrategy(BaseStrategy):
    """
    第一梯队：Open Interest 行为策略
    
    核心逻辑（基于真实仓位变化）：
    - 价格↑ + OI↑ = 新多进场 → 趋势确认做多
    - 价格↑ + OI↓ = 空头回补 → 谨慎或做空
    - 价格↓ + OI↑ = 新空进场 → 趋势确认做空
    - 价格↓ + OI↓ = 多头离场 → 谨慎或做多
    
    优先级：比单纯技术指标更有信息量
    """

    def __init__(
        self,
        strategy_id: str = "oi_behavior",
        lookback_periods: int = 12,  # 1小时
        min_oi_change_threshold: float = 0.01,
        min_price_change_threshold: float = 0.005,
        volume_confidence_factor: float = 1.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.lookback_periods = lookback_periods
        self.min_oi_change_threshold = min_oi_change_threshold
        self.min_price_change_threshold = min_price_change_threshold
        self.volume_confidence_factor = volume_confidence_factor
        self.default_quantity = default_quantity

    def generate_signal(self, features: Dict) -> Optional[Dict]:
        """从特征数据直接生成交易信号"""
        if not self._enabled:
            return None

        close_prices = features.get('close_prices', [])
        oi_history = features.get('oi_history', [])
        oi_delta = features.get('oi_delta', 0.0)
        volumes = features.get('volumes', [])
        symbol = features.get('symbol', 'BTCUSDT')
        oi_zscore = features.get('oi_zscore', 0.0)

        required_length = self.lookback_periods + 1
        if len(close_prices) < required_length or len(oi_history) < required_length:
            return None

        current_price = close_prices[-1]
        past_price = close_prices[-required_length]
        price_change = (current_price - past_price) / past_price

        current_oi = oi_history[-1]
        past_oi = oi_history[-required_length] if len(oi_history) >= required_length else oi_history[0]
        oi_change = oi_delta if oi_delta != 0 else ((current_oi - past_oi) / past_oi if past_oi > 0 else 0.0)

        volume_surge = 1.0
        if len(volumes) >= self.lookback_periods:
            avg_volume = np.mean(volumes[-self.lookback_periods:-1]) if self.lookback_periods > 1 else volumes[-2]
            current_volume = volumes[-1]
            volume_surge = current_volume / avg_volume if avg_volume > 0 else 1.0

        if abs(oi_change) < self.min_oi_change_threshold or abs(price_change) < self.min_price_change_threshold:
            return None

        if price_change > 0:
            if oi_change > 0:
                confidence = min(0.9, (
                    0.4 +
                    (price_change / self.min_price_change_threshold) * 0.2 +
                    (oi_change / self.min_oi_change_threshold) * 0.2 +
                    min(0.2, volume_surge / self.volume_confidence_factor * 0.2)
                ))
                return {
                    "strategy_id": self.strategy_id,
                    "symbol": symbol,
                    "action": "LONG",
                    "quantity": self.default_quantity,
                    "price": current_price,
                    "confidence": confidence,
                    "reason": f"OI行为做多: 价格↑{price_change*100:.2f}% + OI↑{oi_change*100:.2f}% = 新多进场",
                    "metadata": {
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "new_long_confirmation"
                    },
                }
            else:
                confidence = min(0.8, (
                    0.3 +
                    (price_change / self.min_price_change_threshold) * 0.2 +
                    (abs(oi_change) / self.min_oi_change_threshold) * 0.2
                ))
                return {
                    "strategy_id": self.strategy_id,
                    "symbol": symbol,
                    "action": "SHORT",
                    "quantity": self.default_quantity * 0.7,
                    "price": current_price,
                    "confidence": confidence,
                    "reason": f"OI行为做空: 价格↑{price_change*100:.2f}% + OI↓{oi_change*100:.2f}% = 空头回补",
                    "metadata": {
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "short_covering"
                    },
                }
        else:
            if oi_change > 0:
                confidence = min(0.9, (
                    0.4 +
                    (abs(price_change) / self.min_price_change_threshold) * 0.2 +
                    (oi_change / self.min_oi_change_threshold) * 0.2 +
                    min(0.2, volume_surge / self.volume_confidence_factor * 0.2)
                ))
                return {
                    "strategy_id": self.strategy_id,
                    "symbol": symbol,
                    "action": "SHORT",
                    "quantity": self.default_quantity,
                    "price": current_price,
                    "confidence": confidence,
                    "reason": f"OI行为做空: 价格↓{price_change*100:.2f}% + OI↑{oi_change*100:.2f}% = 新空进场",
                    "metadata": {
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "new_short_confirmation"
                    },
                }
            else:
                confidence = min(0.8, (
                    0.3 +
                    (abs(price_change) / self.min_price_change_threshold) * 0.2 +
                    (abs(oi_change) / self.min_oi_change_threshold) * 0.2
                ))
                return {
                    "strategy_id": self.strategy_id,
                    "symbol": symbol,
                    "action": "LONG",
                    "quantity": self.default_quantity * 0.7,
                    "price": current_price,
                    "confidence": confidence,
                    "reason": f"OI行为做多: 价格↓{price_change*100:.2f}% + OI↓{oi_change*100:.2f}% = 多头离场",
                    "metadata": {
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "long_exiting"
                    },
                }


class FundingExtremeReversalStrategy(BaseStrategy):
    """
    第一梯队：Funding Rate 极端反转策略
    
    核心逻辑：
    - 当市场极度一致看多时（Funding > 0.05% + OI新高 + 价格滞涨）→ 做空
    - 当市场极度一致看空时（Funding < -0.05% + OI新高 + 价格滞涨）→ 做多
    
    这是很多机构都在监控的因子
    """

    def __init__(
        self,
        strategy_id: str = "funding_extreme_reversal",
        funding_zscore_threshold: float = 2.5,
        oi_new_high_threshold: float = 1.5,
        price_stagnation_threshold: float = 0.005,
        lookback_periods: int = 24,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.funding_zscore_threshold = funding_zscore_threshold
        self.oi_new_high_threshold = oi_new_high_threshold
        self.price_stagnation_threshold = price_stagnation_threshold
        self.lookback_periods = lookback_periods
        self.default_quantity = default_quantity

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None

        funding_zscore = features.get('funding_zscore')
        oi_funding_divergence = features.get('oi_funding_divergence')
        funding_extreme_reversal = features.get('funding_extreme_reversal')

        if funding_zscore is None:
            return None

        signal_data = None

        if funding_zscore < -self.funding_zscore_threshold:
            if oi_funding_divergence is not None and oi_funding_divergence < 0:
                signal_data = {
                    "action": ActionType.LONG,
                    "confidence": min(0.9, 0.4 + abs(funding_zscore) / self.funding_zscore_threshold * 0.3),
                    "reason": f"Funding极端反转做多: funding_zscore={funding_zscore:.2f}, oi_funding_divergence={oi_funding_divergence:.2f}",
                    "metadata": {
                        "funding_zscore": funding_zscore,
                        "oi_funding_divergence": oi_funding_divergence,
                        "funding_extreme_reversal": funding_extreme_reversal
                    }
                }
            elif funding_extreme_reversal is not None and funding_extreme_reversal > 0:
                signal_data = {
                    "action": ActionType.LONG,
                    "confidence": min(0.9, 0.4 + abs(funding_zscore) / self.funding_zscore_threshold * 0.3),
                    "reason": f"Funding极端反转做多: funding_zscore={funding_zscore:.2f}, funding_extreme_reversal={funding_extreme_reversal:.2f}",
                    "metadata": {
                        "funding_zscore": funding_zscore,
                        "oi_funding_divergence": oi_funding_divergence,
                        "funding_extreme_reversal": funding_extreme_reversal
                    }
                }

        elif funding_zscore > self.funding_zscore_threshold:
            if oi_funding_divergence is not None and oi_funding_divergence > 0:
                signal_data = {
                    "action": ActionType.SHORT,
                    "confidence": min(0.9, 0.4 + funding_zscore / self.funding_zscore_threshold * 0.3),
                    "reason": f"Funding极端反转做空: funding_zscore={funding_zscore:.2f}, oi_funding_divergence={oi_funding_divergence:.2f}",
                    "metadata": {
                        "funding_zscore": funding_zscore,
                        "oi_funding_divergence": oi_funding_divergence,
                        "funding_extreme_reversal": funding_extreme_reversal
                    }
                }
            elif funding_extreme_reversal is not None and funding_extreme_reversal < 0:
                signal_data = {
                    "action": ActionType.SHORT,
                    "confidence": min(0.9, 0.4 + funding_zscore / self.funding_zscore_threshold * 0.3),
                    "reason": f"Funding极端反转做空: funding_zscore={funding_zscore:.2f}, funding_extreme_reversal={funding_extreme_reversal:.2f}",
                    "metadata": {
                        "funding_zscore": funding_zscore,
                        "oi_funding_divergence": oi_funding_divergence,
                        "funding_extreme_reversal": funding_extreme_reversal
                    }
                }

        if signal_data:
            signal_data["strategy_id"] = self.strategy_id
            signal_data["strategy_type"] = StrategyType.BEHAVIORAL
            signal_data["quantity"] = self.default_quantity

        return signal_data


class LiquidationCascadeStrategy(BaseStrategy):
    """
    第一梯队：Liquidation Cascade（爆仓连锁）策略
    
    核心逻辑：
    - 大量多头被强平（>1000万美元） + OI下降>5% + 价格下跌>3%（5分钟内）→ 做反弹
    - 大量空头被强平 + OI下降 + 价格上涨 → 继续上涨
    
    数据要求：Binance Liquidation Stream（已有特征框架支持）
    """

    def __init__(
        self,
        strategy_id: str = "liquidation_cascade",
        long_liq_spike_threshold: float = 1000000.0,  # 100万美元
        short_liq_spike_threshold: float = 1000000.0,
        oi_drop_threshold: float = -0.05,
        price_drop_threshold: float = -0.03,
        lookback_periods: int = 5,  # 5个5分钟周期 = 25分钟
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.long_liq_spike_threshold = long_liq_spike_threshold
        self.short_liq_spike_threshold = short_liq_spike_threshold
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.lookback_periods = lookback_periods
        self.default_quantity = default_quantity

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于特征数据生成交易信号

        多头爆仓 > 阈值 且 OI↓ 且 价格↓ -> 买入
        空头爆仓 > 阈值 且 OI↓ 且 价格↑ -> 买入
        """
        if not self._enabled:
            return None

        liquidation_long = features.get('liquidation_long', 0.0)
        liquidation_short = features.get('liquidation_short', 0.0)
        liquidation_reversal_signal = features.get('liquidation_reversal_signal', 0.0)
        oi_delta = features.get('oi_delta', 0.0)
        price_change = features.get('price_change', 0.0)

        signal = None

        if (liquidation_long > self.long_liq_spike_threshold and
            oi_delta < self.oi_drop_threshold and
            price_change < self.price_drop_threshold and
            liquidation_reversal_signal > 0):

            confidence = min(0.95, (
                0.3 +
                (min(1.0, liquidation_long / (self.long_liq_spike_threshold * 2))) * 0.3 +
                (min(1.0, abs(oi_delta) / abs(self.oi_drop_threshold * 2))) * 0.2 +
                (min(1.0, abs(price_change) / abs(self.price_drop_threshold * 2))) * 0.2
            ))

            signal = {
                'strategy_id': self.strategy_id,
                'action': ActionType.LONG.value,
                'quantity': self.default_quantity,
                'confidence': confidence,
                'reason': f"LiquidationCascade做多: 长爆=${liquidation_long/1000000:.1f}M OI↓{oi_delta*100:.2f}% 价格↓{price_change*100:.2f}%",
                'metadata': {
                    'liquidation_long': liquidation_long,
                    'liquidation_short': liquidation_short,
                    'liquidation_reversal_signal': liquidation_reversal_signal,
                    'oi_delta': oi_delta,
                    'price_change': price_change,
                    'signal_type': 'long_liquidation_rebound'
                }
            }

        elif (liquidation_short > self.short_liq_spike_threshold and
              oi_delta < self.oi_drop_threshold and
              price_change > abs(self.price_drop_threshold)):

            confidence = min(0.95, (
                0.3 +
                (min(1.0, liquidation_short / (self.short_liq_spike_threshold * 2))) * 0.3 +
                (min(1.0, abs(oi_delta) / abs(self.oi_drop_threshold * 2))) * 0.2 +
                (min(1.0, price_change / (abs(self.price_drop_threshold) * 2))) * 0.2
            ))

            signal = {
                'strategy_id': self.strategy_id,
                'action': ActionType.LONG.value,
                'quantity': self.default_quantity,
                'confidence': confidence,
                'reason': f"LiquidationCascade做多: 空爆=${liquidation_short/1000000:.1f}M OI↓{oi_delta*100:.2f}% 价格↑{price_change*100:.2f}%",
                'metadata': {
                    'liquidation_long': liquidation_long,
                    'liquidation_short': liquidation_short,
                    'liquidation_reversal_signal': liquidation_reversal_signal,
                    'oi_delta': oi_delta,
                    'price_change': price_change,
                    'signal_type': 'short_liquidation_continuation'
                }
            }

        return signal


class CVDDivergenceStrategy(BaseStrategy):
    """
    第二梯队：CVD（Cumulative Volume Delta）背离策略
    
    核心逻辑：
    - 价格创新高但CVD不创新高 → 买盘衰竭 → 做空
    - 价格创新低但CVD不创新低 → 卖盘衰竭 → 做多
    
    注意：需要更细粒度的订单流数据
    """

    def __init__(
        self,
        strategy_id: str = "cvd_divergence",
        lookback_periods: int = 24,
        divergence_threshold: float = 0.1,
        default_quantity: float = 0.01,
        params: Dict = None,
    ):
        super().__init__(strategy_id)
        self.lookback_periods = lookback_periods
        self.divergence_threshold = divergence_threshold
        self.default_quantity = default_quantity
        self.params = params or {}

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """基于特征生成信号"""
        if not self._enabled:
            return None

        close = features.get('close')
        cvd = features.get('cvd')

        if close is None or cvd is None:
            return None

        lookback_periods = self.params.get('lookback_periods', self.lookback_periods)
        divergence_threshold = self.params.get('divergence_threshold', self.divergence_threshold)

        close_prices = features.get('close_prices', [close])
        cvd_history = features.get('cvd_history', [cvd])

        if len(close_prices) < lookback_periods + 1 or len(cvd_history) < lookback_periods + 1:
            return None

        current_price = close
        current_cvd = cvd

        price_new_high = current_price >= np.max(close_prices[-lookback_periods:-1]) * 0.999
        price_new_low = current_price <= np.min(close_prices[-lookback_periods:-1]) * 1.001

        cvd_window = cvd_history[-lookback_periods:]
        cvd_high = np.max(cvd_window[:-1]) if len(cvd_window) > 1 else current_cvd
        cvd_low = np.min(cvd_window[:-1]) if len(cvd_window) > 1 else current_cvd
        cvd_new_high = current_cvd > cvd_high
        cvd_new_low = current_cvd < cvd_low

        if price_new_high and not cvd_new_high:
            price_high = np.max(close_prices[-lookback_periods:])
            divergence = (price_high - current_price) / price_high if price_high > 0 else 0
            if divergence < divergence_threshold:
                confidence = min(0.85, 0.5 + (cvd_high - current_cvd) / max(abs(cvd_high), 1e-10) * 0.3)
                return {
                    'signal_type': 'sell',
                    'action': 'short',
                    'confidence': confidence,
                    'reason': 'CVD顶背离: 价格新高但CVD不新高 = 买盘衰竭',
                    'metadata': {
                        'price_new_high': price_new_high,
                        'cvd_new_high': cvd_new_high,
                        'current_cvd': current_cvd,
                        'cvd_high': cvd_high,
                        'price_high': price_high,
                        'strategy': 'cvd_divergence'
                    },
                }

        if price_new_low and not cvd_new_low:
            price_low = np.min(close_prices[-lookback_periods:])
            divergence = (current_price - price_low) / price_low if price_low > 0 else 0
            if divergence > -divergence_threshold:
                confidence = min(0.85, 0.5 + (current_cvd - cvd_low) / max(abs(cvd_low), 1e-10) * 0.3)
                return {
                    'signal_type': 'buy',
                    'action': 'long',
                    'confidence': confidence,
                    'reason': 'CVD底背离: 价格新低但CVD不新低 = 卖盘衰竭',
                    'metadata': {
                        'price_new_low': price_new_low,
                        'cvd_new_low': cvd_new_low,
                        'current_cvd': current_cvd,
                        'cvd_low': cvd_low,
                        'price_low': price_low,
                        'strategy': 'cvd_divergence'
                    },
                }

        return None


class WhaleTradeStrategy(BaseStrategy):
    """
    第二梯队：Whale Trade（大单）策略
    
    监控单笔大额交易（如 > 100 BTC）
    - 连续大额主动买入 + OI上升 → 跟随做多
    - 连续大额主动卖出 + OI下降 → 跟随做空
    """

    def __init__(
        self,
        strategy_id: str = "whale_trade",
        whale_threshold_btc: float = 100.0,
        lookback_trades: int = 5,
        oi_change_threshold: float = 0.01,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.whale_threshold_btc = whale_threshold_btc
        self.lookback_trades = lookback_trades
        self.oi_change_threshold = oi_change_threshold
        self.default_quantity = default_quantity

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于特征数据生成交易信号

        大单买入 + OI上升 -> 买入
        大单卖出 + OI下降 -> 卖出
        """
        if not self._enabled:
            return None

        whale_buy_count = features.get('whale_buy_count', 0)
        whale_sell_count = features.get('whale_sell_count', 0)
        oi_delta = features.get('oi_delta', 0.0)
        aggressive_flow = features.get('aggressive_flow', 0.0)
        symbol = features.get('symbol', 'BTCUSDT')
        close = features.get('close')

        whale_buy_volume = features.get('whale_buy_volume', 0.0)
        whale_sell_volume = features.get('whale_sell_volume', 0.0)

        if whale_buy_count is None and whale_sell_count is None:
            return None

        signal = None

        if (whale_buy_count >= self.lookback_trades or
            whale_buy_volume > self.whale_threshold_btc * self.lookback_trades * 0.5):

            if oi_delta > self.oi_change_threshold or aggressive_flow > 0:
                confidence = min(0.9, (
                    0.4 +
                    (whale_buy_volume / (self.whale_threshold_btc * self.lookback_trades)) * 0.3 +
                    (max(0.0, min(0.3, oi_delta / self.oi_change_threshold)) * 0.3)
                ))
                signal = {
                    'strategy_id': self.strategy_id,
                    'symbol': symbol,
                    'action': ActionType.LONG.value,
                    'quantity': self.default_quantity,
                    'price': close,
                    'confidence': confidence,
                    'reason': f"Whale策略做多: {whale_buy_count}笔大单买入 OI变化={oi_delta*100:.2f}% aggressive_flow={aggressive_flow:.4f}",
                    'metadata': {
                        'whale_buy_count': whale_buy_count,
                        'whale_sell_count': whale_sell_count,
                        'whale_buy_volume': whale_buy_volume,
                        'whale_sell_volume': whale_sell_volume,
                        'aggressive_flow': aggressive_flow,
                        'oi_delta': oi_delta,
                        'signal_type': 'whale_buy_oi_rising'
                    },
                }

        elif (whale_sell_count >= self.lookback_trades or
              whale_sell_volume > self.whale_threshold_btc * self.lookback_trades * 0.5):

            if oi_delta < -self.oi_change_threshold or aggressive_flow < 0:
                confidence = min(0.9, (
                    0.4 +
                    (whale_sell_volume / (self.whale_threshold_btc * self.lookback_trades)) * 0.3 +
                    (max(0.0, min(0.3, abs(oi_delta) / self.oi_change_threshold)) * 0.3)
                ))
                signal = {
                    'strategy_id': self.strategy_id,
                    'symbol': symbol,
                    'action': ActionType.SHORT.value,
                    'quantity': self.default_quantity,
                    'price': close,
                    'confidence': confidence,
                    'reason': f"Whale策略做空: {whale_sell_count}笔大单卖出 OI变化={oi_delta*100:.2f}% aggressive_flow={aggressive_flow:.4f}",
                    'metadata': {
                        'whale_buy_count': whale_buy_count,
                        'whale_sell_count': whale_sell_count,
                        'whale_buy_volume': whale_buy_volume,
                        'whale_sell_volume': whale_sell_volume,
                        'aggressive_flow': aggressive_flow,
                        'oi_delta': oi_delta,
                        'signal_type': 'whale_sell_oi_falling'
                    },
                }

        return signal


class FundingSettlementStrategy(BaseStrategy):
    """
    第二梯队：Funding Settlement Event（资金费率结算）策略
    
    Binance永续合约每8小时结算一次（07:50、15:50、23:50）
    常出现：插针、平仓、套利资金调仓
    """

    def __init__(
        self,
        strategy_id: str = "funding_settlement",
        minutes_before_settlement: int = 30,
        minutes_after_settlement: int = 60,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.minutes_before_settlement = minutes_before_settlement
        self.minutes_after_settlement = minutes_after_settlement
        self.default_quantity = default_quantity

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """基于特征数据生成交易信号

        核心逻辑：
        - 接近结算时间且高费率 -> 做空
        - 接近结算时间且低费率 -> 做多
        """
        if not self._enabled:
            return None

        timestamp = features.get('timestamp')
        funding_rate = features.get('funding_rate')

        if timestamp is None or funding_rate is None:
            return None

        minutes_before = self.params.get('minutes_before_settlement', self.minutes_before_settlement)
        minutes_after = self.params.get('minutes_after_settlement', self.minutes_after_settlement)

        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp / 1000)
        hour = dt.hour
        minute = dt.minute

        settlement_hours = [7, 15, 23]
        settlement_minute = 50

        near_settlement = False
        direction = 0

        for settle_hour in settlement_hours:
            minutes_diff = (settle_hour * 60 + settlement_minute) - (hour * 60 + minute)
            if -minutes_after <= minutes_diff <= minutes_before:
                near_settlement = True
                if minutes_diff > 0:
                    direction = -1 if funding_rate > 0 else 1
                else:
                    direction = 1 if funding_rate > 0 else -1

        if not near_settlement:
            return None

        confidence = min(0.75, 0.4 + abs(funding_rate) / 0.001 * 0.2 + 0.15)

        return {
            'strategy_id': self.strategy_id,
            'strategy_type': StrategyType.EVENT_DRIVEN,
            'action': ActionType.LONG if direction > 0 else ActionType.SHORT,
            'quantity': self.default_quantity * 0.8,
            'confidence': confidence,
            'reason': f"Funding结算策略: 费率={funding_rate*100:.4f}% 时间={hour:02d}:{minute:02d}",
            'metadata': {
                'funding_rate': funding_rate,
                'hour': hour,
                'minute': minute,
                'near_settlement': near_settlement
            },
        }


# 导出策略类
__all__ = [
    'OpenInterestBehaviorStrategy',
    'FundingExtremeReversalStrategy',
    'LiquidationCascadeStrategy',
    'CVDDivergenceStrategy',
    'WhaleTradeStrategy',
    'FundingSettlementStrategy',
]
