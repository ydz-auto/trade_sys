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
from typing import Dict, Optional
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

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        oi_history = data.get("oi_history", [])
        oi_delta = data.get("oi_delta", 0.0)
        oi_zscore = data.get("oi_zscore", 0.0)
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        required_length = self.lookback_periods + 1
        if len(close_prices) < required_length or len(oi_history) < required_length:
            return None

        current_price = close_prices[-1]
        past_price = close_prices[-required_length]
        price_change = (current_price - past_price) / past_price

        current_oi = oi_history[-1]
        past_oi = oi_history[-required_length] if len(oi_history) >= required_length else oi_history[0]
        oi_change = (current_oi - past_oi) / past_oi if past_oi > 0 else 0.0

        volume_surge = 0.0
        if len(volumes) >= self.lookback_periods:
            avg_volume = np.mean(volumes[-self.lookback_periods:-1]) if self.lookback_periods > 1 else volumes[-2]
            current_volume = volumes[-1]
            volume_surge = current_volume / avg_volume if avg_volume > 0 else 1.0

        signal = None

        # 只有变化足够大时才触发
        if abs(oi_change) < self.min_oi_change_threshold or abs(price_change) < self.min_price_change_threshold:
            return None

        # 情境判断
        if price_change > 0:
            # 价格上涨
            if oi_change > 0:
                # 价格↑ + OI↑ = 新多进场 → 趋势确认做多
                confidence = min(0.9, (
                    0.4 + 
                    (price_change / self.min_price_change_threshold) * 0.2 + 
                    (oi_change / self.min_oi_change_threshold) * 0.2 + 
                    min(0.2, volume_surge / self.volume_confidence_factor * 0.2)
                ))
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.BEHAVIORAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"OI行为做多: 价格↑{price_change*100:.2f}% + OI↑{oi_change*100:.2f}% = 新多进场",
                    metadata={
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "new_long_confirmation"
                    },
                )
            else:
                # 价格↑ + OI↓ = 空头回补 → 谨慎
                confidence = min(0.8, (
                    0.3 + 
                    (price_change / self.min_price_change_threshold) * 0.2 + 
                    (abs(oi_change) / self.min_oi_change_threshold) * 0.2
                ))
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.BEHAVIORAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity * 0.7,
                    price=current_price,
                    confidence=confidence,
                    reason=f"OI行为做空: 价格↑{price_change*100:.2f}% + OI↓{oi_change*100:.2f}% = 空头回补",
                    metadata={
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "short_covering"
                    },
                )
        else:
            # 价格下跌
            if oi_change > 0:
                # 价格↓ + OI↑ = 新空进场 → 趋势确认做空
                confidence = min(0.9, (
                    0.4 + 
                    (abs(price_change) / self.min_price_change_threshold) * 0.2 + 
                    (oi_change / self.min_oi_change_threshold) * 0.2 + 
                    min(0.2, volume_surge / self.volume_confidence_factor * 0.2)
                ))
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.BEHAVIORAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=confidence,
                    reason=f"OI行为做空: 价格↓{price_change*100:.2f}% + OI↑{oi_change*100:.2f}% = 新空进场",
                    metadata={
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "new_short_confirmation"
                    },
                )
            else:
                # 价格↓ + OI↓ = 多头离场 → 谨慎
                confidence = min(0.8, (
                    0.3 + 
                    (abs(price_change) / self.min_price_change_threshold) * 0.2 + 
                    (abs(oi_change) / self.min_oi_change_threshold) * 0.2
                ))
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.BEHAVIORAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity * 0.7,
                    price=current_price,
                    confidence=confidence,
                    reason=f"OI行为做多: 价格↓{price_change*100:.2f}% + OI↓{oi_change*100:.2f}% = 多头离场",
                    metadata={
                        "price_change": price_change,
                        "oi_change": oi_change,
                        "oi_zscore": oi_zscore,
                        "volume_surge": volume_surge,
                        "signal_type": "long_exiting"
                    },
                )

        return signal


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

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        oi_history = data.get("oi_history", [])
        funding_rate = data.get("funding_rate", 0.0)
        funding_zscore = data.get("funding_zscore", 0.0)
        oi_funding_divergence = data.get("oi_funding_divergence", 0.0)
        funding_extreme_reversal = data.get("funding_extreme_reversal", 0.0)
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.lookback_periods or len(oi_history) < self.lookback_periods:
            return None

        current_price = close_prices[-1]
        current_oi = oi_history[-1] if oi_history else 0

        # 检查OI是否新高
        oi_new_high = False
        if len(oi_history) >= self.lookback_periods:
            max_oi_past = np.max(oi_history[-self.lookback_periods:-1])
            if max_oi_past > 0 and current_oi > max_oi_past * (1.0 + 0.01):
                oi_new_high = True

        # 检查价格滞涨/滞跌（最近几个周期的动量减弱）
        price_stagnation = False
        if len(close_prices) >= 12:
            recent_trend = np.polyfit(range(6), close_prices[-6:], 1)[0] / close_prices[-7] if close_prices[-7] > 0 else 0
            earlier_trend = np.polyfit(range(6), close_prices[-12:-6], 1)[0] / close_prices[-13] if close_prices[-13] > 0 else 0
            if (funding_zscore > 0 and recent_trend < earlier_trend * 0.5) or (funding_zscore < 0 and recent_trend > earlier_trend * 0.5):
                price_stagnation = True

        signal = None

        # 极端看空转多信号
        if (funding_zscore < -self.funding_zscore_threshold and 
            (oi_new_high or oi_funding_divergence < 0) and
            (price_stagnation or funding_extreme_reversal > 0)):
            
            confidence = min(0.95, (
                0.3 +
                (abs(funding_zscore) / self.funding_zscore_threshold) * 0.3 +
                (0.2 if oi_new_high else 0.1) +
                (0.2 if price_stagnation else 0.1)
            ))
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.BEHAVIORAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"Funding极端反转做多: Z={funding_zscore:.2f} OI新高={oi_new_high} 价格滞涨={price_stagnation}",
                metadata={
                    "funding_rate": funding_rate,
                    "funding_zscore": funding_zscore,
                    "oi_new_high": oi_new_high,
                    "price_stagnation": price_stagnation,
                    "oi_funding_divergence": oi_funding_divergence,
                    "funding_extreme_reversal": funding_extreme_reversal
                },
            )
        
        # 极端看空转多信号
        elif (funding_zscore > self.funding_zscore_threshold and 
              (oi_new_high or oi_funding_divergence > 0) and
              (price_stagnation or funding_extreme_reversal < 0)):
            
            confidence = min(0.95, (
                0.3 +
                (funding_zscore / self.funding_zscore_threshold) * 0.3 +
                (0.2 if oi_new_high else 0.1) +
                (0.2 if price_stagnation else 0.1)
            ))
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.BEHAVIORAL,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"Funding极端反转做空: Z={funding_zscore:.2f} OI新高={oi_new_high} 价格滞涨={price_stagnation}",
                metadata={
                    "funding_rate": funding_rate,
                    "funding_zscore": funding_zscore,
                    "oi_new_high": oi_new_high,
                    "price_stagnation": price_stagnation,
                    "oi_funding_divergence": oi_funding_divergence,
                    "funding_extreme_reversal": funding_extreme_reversal
                },
            )

        return signal


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

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        oi_history = data.get("oi_history", [])
        liquidation_long = data.get("liquidation_long", 0.0)
        liquidation_short = data.get("liquidation_short", 0.0)
        liquidation_spike = data.get("liquidation_spike", 0.0)
        liquidation_reversal_signal = data.get("liquidation_reversal_signal", 0.0)
        liquidation_chain_probability = data.get("liquidation_chain_probability", 0.0)
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.lookback_periods + 1:
            return None

        current_price = close_prices[-1]
        past_price = close_prices[-self.lookback_periods - 1]
        price_change = (current_price - past_price) / past_price

        current_oi = oi_history[-1] if oi_history else 0
        past_oi = oi_history[-self.lookback_periods - 1] if len(oi_history) >= self.lookback_periods + 1 else current_oi
        oi_change = (current_oi - past_oi) / past_oi if past_oi > 0 else 0.0

        signal = None

        # 多头被爆仓 → 超跌反弹
        if (liquidation_long > self.long_liq_spike_threshold and
            oi_change < self.oi_drop_threshold and
            price_change < self.price_drop_threshold and
            liquidation_reversal_signal > 0):
            
            confidence = min(0.95, (
                0.3 +
                (min(1.0, liquidation_long / (self.long_liq_spike_threshold * 2))) * 0.3 +
                (min(1.0, abs(oi_change) / abs(self.oi_drop_threshold * 2))) * 0.2 +
                (min(1.0, abs(price_change) / abs(self.price_drop_threshold * 2))) * 0.2
            ))
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"LiquidationCascade做多: 长爆=${liquidation_long/1000000:.1f}M OI↓{oi_change*100:.2f}% 价格↓{price_change*100:.2f}%",
                metadata={
                    "liquidation_long": liquidation_long,
                    "liquidation_short": liquidation_short,
                    "liquidation_spike": liquidation_spike,
                    "liquidation_reversal_signal": liquidation_reversal_signal,
                    "liquidation_chain_probability": liquidation_chain_probability,
                    "oi_change": oi_change,
                    "price_change": price_change
                },
            )
        
        # 空头被爆仓 → 继续上涨
        elif (liquidation_short > self.short_liq_spike_threshold and
              oi_change < self.oi_drop_threshold and  # OI也下降（空头被强平）
              price_change > abs(self.price_drop_threshold)):
            
            confidence = min(0.95, (
                0.3 +
                (min(1.0, liquidation_short / (self.short_liq_spike_threshold * 2))) * 0.3 +
                (min(1.0, abs(oi_change) / abs(self.oi_drop_threshold * 2))) * 0.2 +
                (min(1.0, price_change / (abs(self.price_drop_threshold) * 2))) * 0.2
            ))
            signal = StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=confidence,
                reason=f"LiquidationCascade做多: 空爆=${liquidation_short/1000000:.1f}M OI↓{oi_change*100:.2f}% 价格↑{price_change*100:.2f}%",
                metadata={
                    "liquidation_long": liquidation_long,
                    "liquidation_short": liquidation_short,
                    "liquidation_spike": liquidation_spike,
                    "liquidation_reversal_signal": liquidation_reversal_signal,
                    "liquidation_chain_probability": liquidation_chain_probability,
                    "oi_change": oi_change,
                    "price_change": price_change
                },
            )

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
    ):
        super().__init__(strategy_id)
        self.lookback_periods = lookback_periods
        self.divergence_threshold = divergence_threshold
        self.default_quantity = default_quantity

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        cvd_history = data.get("cvd_history", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < self.lookback_periods + 1 or len(cvd_history) < self.lookback_periods + 1:
            return None

        current_price = close_prices[-1]
        current_cvd = cvd_history[-1] if cvd_history else 0

        # 检查价格新高
        price_high_window = close_prices[-self.lookback_periods:]
        price_high = np.max(price_high_window)
        price_new_high = current_price >= price_high * 0.999  # 允许一点点误差

        # 检查价格新低
        price_low_window = close_prices[-self.lookback_periods:]
        price_low = np.min(price_low_window)
        price_new_low = current_price <= price_low * 1.001

        # 检查CVD新高/新低
        cvd_window = cvd_history[-self.lookback_periods:]
        cvd_high = np.max(cvd_window[:-1]) if len(cvd_window) > 1 else current_cvd
        cvd_low = np.min(cvd_window[:-1]) if len(cvd_window) > 1 else current_cvd
        cvd_new_high = current_cvd > cvd_high
        cvd_new_low = current_cvd < cvd_low

        signal = None

        # 顶背离：价格新高，CVD不新高 → 买盘衰竭
        if price_new_high and not cvd_new_high:
            divergence = (price_high - current_price) / price_high if price_high > 0 else 0
            if divergence < self.divergence_threshold:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.BEHAVIORAL,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=min(0.85, 0.5 + (cvd_high - current_cvd) / max(abs(cvd_high), 1e-10) * 0.3),
                    reason=f"CVD顶背离: 价格新高但CVD不新高 = 买盘衰竭",
                    metadata={
                        "price_new_high": price_new_high,
                        "cvd_new_high": cvd_new_high,
                        "current_cvd": current_cvd,
                        "cvd_high": cvd_high,
                        "price_high": price_high
                    },
                )
        
        # 底背离：价格新低，CVD不新低 → 卖盘衰竭
        elif price_new_low and not cvd_new_low:
            divergence = (current_price - price_low) / price_low if price_low > 0 else 0
            if divergence > -self.divergence_threshold:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.BEHAVIORAL,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=min(0.85, 0.5 + (current_cvd - cvd_low) / max(abs(cvd_low), 1e-10) * 0.3),
                    reason=f"CVD底背离: 价格新低但CVD不新低 = 卖盘衰竭",
                    metadata={
                        "price_new_low": price_new_low,
                        "cvd_new_low": cvd_new_low,
                        "current_cvd": current_cvd,
                        "cvd_low": cvd_low,
                        "price_low": price_low
                    },
                )

        return signal


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

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        oi_history = data.get("oi_history", [])
        whale_buy_count = data.get("whale_buy_count", 0)
        whale_sell_count = data.get("whale_sell_count", 0)
        whale_buy_volume = data.get("whale_buy_volume", 0.0)
        whale_sell_volume = data.get("whale_sell_volume", 0.0)
        aggressive_flow = data.get("aggressive_flow", 0.0)
        symbol = data.get("symbol", "BTCUSDT")

        if not close_prices:
            return None

        current_price = close_prices[-1]

        oi_change = 0.0
        if len(oi_history) >= 2:
            oi_change = (oi_history[-1] - oi_history[-2]) / oi_history[-2] if oi_history[-2] > 0 else 0.0

        signal = None

        # 大单买入 + OI上升 → 跟随做多
        if (whale_buy_count >= self.lookback_trades or
            whale_buy_volume > self.whale_threshold_btc * self.lookback_trades * 0.5):
            
            if oi_change > self.oi_change_threshold or aggressive_flow > 0:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.EVENT_DRIVEN,
                    symbol=symbol,
                    action=ActionType.LONG,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=min(0.9, (
                        0.4 +
                        (whale_buy_volume / (self.whale_threshold_btc * self.lookback_trades)) * 0.3 +
                        (max(0.0, min(0.3, oi_change / self.oi_change_threshold)) * 0.3)
                    )),
                    reason=f"Whale策略做多: {whale_buy_count}笔大单买入 量={whale_buy_volume:.1f}BTC OI变化={oi_change*100:.2f}%",
                    metadata={
                        "whale_buy_count": whale_buy_count,
                        "whale_sell_count": whale_sell_count,
                        "whale_buy_volume": whale_buy_volume,
                        "whale_sell_volume": whale_sell_volume,
                        "aggressive_flow": aggressive_flow,
                        "oi_change": oi_change
                    },
                )
        
        # 大单卖出 + OI下降 → 跟随做空
        elif (whale_sell_count >= self.lookback_trades or
              whale_sell_volume > self.whale_threshold_btc * self.lookback_trades * 0.5):
            
            if oi_change < -self.oi_change_threshold or aggressive_flow < 0:
                signal = StrategySignal(
                    strategy_id=self.strategy_id,
                    strategy_type=StrategyType.EVENT_DRIVEN,
                    symbol=symbol,
                    action=ActionType.SHORT,
                    quantity=self.default_quantity,
                    price=current_price,
                    confidence=min(0.9, (
                        0.4 +
                        (whale_sell_volume / (self.whale_threshold_btc * self.lookback_trades)) * 0.3 +
                        (max(0.0, min(0.3, abs(oi_change) / self.oi_change_threshold)) * 0.3)
                    )),
                    reason=f"Whale策略做空: {whale_sell_count}笔大单卖出 量={whale_sell_volume:.1f}BTC OI变化={oi_change*100:.2f}%",
                    metadata={
                        "whale_buy_count": whale_buy_count,
                        "whale_sell_count": whale_sell_count,
                        "whale_buy_volume": whale_buy_volume,
                        "whale_sell_volume": whale_sell_volume,
                        "aggressive_flow": aggressive_flow,
                        "oi_change": oi_change
                    },
                )

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

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        timestamp = data.get("timestamp", 0)
        funding_rate = data.get("funding_rate", 0.0)
        symbol = data.get("symbol", "BTCUSDT")

        if not close_prices:
            return None

        current_price = close_prices[-1]

        # 判断是否接近结算时间
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp / 1000)
        hour = dt.hour
        minute = dt.minute

        # Binance结算时间：07:50、15:50、23:50
        settlement_hours = [7, 15, 23]
        settlement_minute = 50

        near_settlement = False
        direction = 0

        for settle_hour in settlement_hours:
            minutes_diff = (settle_hour * 60 + settlement_minute) - (hour * 60 + minute)
            if -self.minutes_after_settlement <= minutes_diff <= self.minutes_before_settlement:
                near_settlement = True
                # 结算前还是后
                if minutes_diff > 0:
                    direction = -1 if funding_rate > 0 else 1  # 结算前：高费率做空，低费率做多
                else:
                    direction = 1 if funding_rate > 0 else -1  # 结算后：反向（套利平仓）

        if not near_settlement:
            return None

        confidence = min(0.75, 0.4 + abs(funding_rate) / 0.001 * 0.2 + 0.15)
        
        signal = StrategySignal(
            strategy_id=self.strategy_id,
            strategy_type=StrategyType.EVENT_DRIVEN,
            symbol=symbol,
            action=ActionType.LONG if direction > 0 else ActionType.SHORT,
            quantity=self.default_quantity * 0.8,
            price=current_price,
            confidence=confidence,
            reason=f"Funding结算策略: 费率={funding_rate*100:.4f}% 时间={hour:02d}:{minute:02d}",
            metadata={
                "funding_rate": funding_rate,
                "hour": hour,
                "minute": minute,
                "near_settlement": near_settlement
            },
        )

        return signal


# 导出策略类
__all__ = [
    'OpenInterestBehaviorStrategy',
    'FundingExtremeReversalStrategy',
    'LiquidationCascadeStrategy',
    'CVDDivergenceStrategy',
    'WhaleTradeStrategy',
    'FundingSettlementStrategy',
]
