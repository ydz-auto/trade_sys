#!/usr/bin/env python3
"""
Walk-Forward 参数优化脚本 - 使用 BacktestEngine - 所有21种策略版本

使用真实 BTCUSDT 历史数据运行 Walk-Forward 参数优化：
- 2022 优化 → 2023 验证 → 2024 测试

策略列表：
1. rsi_oversold
2. rsi_overbought
3. macd_cross
4. sma_cross
5. ema_cross
6. bollinger_bands
7. panic_reversal
8. long_liquidation_bounce
9. volume_climax_fade
10. weak_bounce_short
11. dead_cat_echo
12. oi_flush
13. short_squeeze
14. funding_exhaustion_trap
15. imbalance_pressure
16. sweep_detection
17. liquidity_vacuum
18. aggressive_flow
19. breakout
20. trend_following
21. bb_compression_breakout

生成标准回测报告：
- Sharpe Ratio
- Profit Factor
- Win Rate
- Max Drawdown
- Overfitting 指标
"""
import sys
import os

# 添加后端路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from itertools import product
import json
import numpy as np

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from runtimes.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
)

logger = get_logger("walk_forward")


@dataclass
class WalkForwardResult:
    """Walk-Forward 结果"""
    strategy_id: str
    optimize_year: int
    validation_year: int
    test_year: int
    best_params: Dict[str, Any]
    optimize_sharpe: float
    validation_sharpe: float
    test_sharpe: float
    optimize_trades: int
    validation_trades: int
    test_trades: int
    optimize_return: float
    validation_return: float
    test_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    overfitting_score: float


# ==============================================================================
# 策略基类和实现
# ==============================================================================

class BaseStrategyImpl:
    """策略基类实现"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.params = params
        self._closes = []
        self._highs = []
        self._lows = []
        self._volumes = []
        self._position = None
        self._entry_price = 0.0
    
    def on_bar(self, bar: Bar):
        """处理新Bar"""
        self._closes.append(bar.close)
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._volumes.append(bar.volume)
        
        if len(self._closes) > 600:
            self._closes = self._closes[-600:]
            self._highs = self._highs[-600:]
            self._lows = self._lows[-600:]
            self._volumes = self._volumes[-600:]
    
    def calculate(self, bar: Bar) -> SignalType:
        """生成信号 - 子类实现"""
        raise NotImplementedError
    
    def __call__(self, bar: Bar, position=None) -> SignalType:
        """生成信号"""
        self.on_bar(bar)
        return self.calculate(bar)
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """计算 EMA"""
        if len(prices) < period:
            return 0.0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        return ema
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算 RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        
        avg_gain = sum(gains[-period:]) / period if gains else 0.0
        avg_loss = sum(losses[-period:]) / period if losses else 0.0
        
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


class RSIOversoldStrategy(BaseStrategyImpl):
    """RSI 超卖策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
        self._rsi_prev = None
    
    def calculate(self, bar: Bar) -> SignalType:
        period = self.params.get("period", 14)
        oversold = self.params.get("oversold", 30)
        
        rsi = self.calculate_rsi(self._closes, period)
        
        signal = SignalType.HOLD
        
        if self._rsi_prev is not None:
            if self._position is None:
                if rsi <= oversold and self._rsi_prev > oversold:
                    self._position = "long"
                    signal = SignalType.BUY
            elif self._position == "long":
                if rsi >= 70 and self._rsi_prev < 70:
                    self._position = None
                    signal = SignalType.SELL
        
        self._rsi_prev = rsi
        return signal


class RSIOverboughtStrategy(BaseStrategyImpl):
    """RSI 超买策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
        self._rsi_prev = None
    
    def calculate(self, bar: Bar) -> SignalType:
        period = self.params.get("period", 14)
        overbought = self.params.get("overbought", 70)
        
        rsi = self.calculate_rsi(self._closes, period)
        
        signal = SignalType.HOLD
        
        if self._rsi_prev is not None:
            if self._position is None:
                if rsi >= overbought and self._rsi_prev < overbought:
                    self._position = "short"
                    signal = SignalType.SELL
            elif self._position == "short":
                if rsi <= 30 and self._rsi_prev > 30:
                    self._position = None
                    signal = SignalType.BUY
        
        self._rsi_prev = rsi
        return signal


class MACDCrossStrategy(BaseStrategyImpl):
    """MACD 交叉策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
        self._macd_line = []
        self._signal_line = []
        self._histogram = []
    
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 12)
        slow_period = self.params.get("slow_period", 26)
        signal_period = self.params.get("signal_period", 9)
        
        if len(self._closes) < slow_period + signal_period:
            return SignalType.HOLD
        
        ema_fast = self.calculate_ema(self._closes, fast_period)
        ema_slow = self.calculate_ema(self._closes, slow_period)
        macd_line = ema_fast - ema_slow
        
        self._macd_line.append(macd_line)
        if len(self._macd_line) >= signal_period:
            signal_line = self.calculate_ema(self._macd_line[-signal_period:], signal_period)
        else:
            signal_line = 0.0
        
        self._signal_line.append(signal_line)
        
        signal = SignalType.HOLD
        
        if len(self._signal_line) >= 2:
            prev_macd = self._macd_line[-2]
            prev_signal = self._signal_line[-2]
            
            if self._position is None:
                if prev_macd <= prev_signal and macd_line > signal_line:
                    self._position = "long"
                    signal = SignalType.BUY
                elif prev_macd >= prev_signal and macd_line < signal_line:
                    self._position = "short"
                    signal = SignalType.SELL
            elif self._position == "long":
                if prev_macd >= prev_signal and macd_line < signal_line:
                    self._position = None
                    signal = SignalType.SELL
            elif self._position == "short":
                if prev_macd <= prev_signal and macd_line > signal_line:
                    self._position = None
                    signal = SignalType.BUY
        
        return signal


class SMACrossStrategy(BaseStrategyImpl):
    """SMA 交叉策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate_sma(self, period: int) -> float:
        if len(self._closes) < period:
            return 0.0
        return sum(self._closes[-period:]) / period
    
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 10)
        slow_period = self.params.get("slow_period", 50)
        
        sma_fast = self.calculate_sma(fast_period)
        sma_slow = self.calculate_sma(slow_period)
        
        if sma_fast == 0 or sma_slow == 0:
            return SignalType.HOLD
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if sma_fast > sma_slow:
                self._position = "long"
                signal = SignalType.BUY
            elif sma_fast < sma_slow:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if sma_fast < sma_slow:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if sma_fast > sma_slow:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class EMACrossStrategy(BaseStrategyImpl):
    """EMA 交叉策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 10)
        slow_period = self.params.get("slow_period", 50)
        
        ema_fast = self.calculate_ema(self._closes, fast_period)
        ema_slow = self.calculate_ema(self._closes, slow_period)
        
        if ema_fast == 0 or ema_slow == 0:
            return SignalType.HOLD
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if ema_fast > ema_slow:
                self._position = "long"
                signal = SignalType.BUY
            elif ema_fast < ema_slow:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if ema_fast < ema_slow:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if ema_fast > ema_slow:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class BollingerBandsStrategy(BaseStrategyImpl):
    """布林带策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate_bb(self, period: int, num_std: float):
        if len(self._closes) < period:
            return 0, 0, 0
        
        sma = sum(self._closes[-period:]) / period
        squared_diffs = [(x - sma) ** 2 for x in self._closes[-period:]]
        std_dev = (sum(squared_diffs) / period) ** 0.5
        
        upper = sma + num_std * std_dev
        lower = sma - num_std * std_dev
        
        return upper, sma, lower
    
    def calculate(self, bar: Bar) -> SignalType:
        period = self.params.get("period", 20)
        num_std = self.params.get("num_std", 2.0)
        
        upper, middle, lower = self.calculate_bb(period, num_std)
        
        if upper == 0:
            return SignalType.HOLD
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if bar.close < lower:
                self._position = "long"
                signal = SignalType.BUY
            elif bar.close > upper:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if bar.close > upper:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if bar.close < lower:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class PanicReversalStrategy(BaseStrategyImpl):
    """恐慌反转策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        drop_threshold = self.params.get("drop_threshold", -0.015)
        volume_ratio_threshold = self.params.get("volume_ratio_threshold", 1.5)
        
        if len(self._closes) < 12:
            return SignalType.HOLD
        
        price_1h_ago = self._closes[-12]
        return_1h = (bar.close - price_1h_ago) / price_1h_ago
        
        volume_ratio = 1.0
        if len(self._volumes) >= 288:
            avg_volume = sum(self._volumes[-288:]) / 288
            if avg_volume > 0:
                volume_ratio = self._volumes[-1] / avg_volume
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if return_1h <= drop_threshold and volume_ratio >= volume_ratio_threshold:
                self._position = "long"
                signal = SignalType.BUY
        elif self._position == "long":
            if return_1h >= 0.02:
                self._position = None
                signal = SignalType.SELL
        
        return signal


class LongLiquidationBounceStrategy(BaseStrategyImpl):
    """多头踩踏反弹策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        drop_threshold = self.params.get("drop_threshold", -0.02)
        rsi_threshold = self.params.get("rsi_threshold", 25.0)
        volume_ratio_threshold = self.params.get("volume_ratio_threshold", 2.0)
        
        if len(self._closes) < 14:
            return SignalType.HOLD
        
        return_1h = 0.0
        if len(self._closes) >= 12:
            price_1h_ago = self._closes[-12]
            return_1h = (bar.close - price_1h_ago) / price_1h_ago
        
        rsi = self.calculate_rsi(self._closes, 14)
        
        volume_ratio = 1.0
        if len(self._volumes) >= 288:
            avg_volume = sum(self._volumes[-288:]) / 288
            if avg_volume > 0:
                volume_ratio = self._volumes[-1] / avg_volume
        
        conditions_met = 0
        if return_1h <= drop_threshold:
            conditions_met += 1
        if rsi <= rsi_threshold:
            conditions_met += 1
        if volume_ratio >= volume_ratio_threshold:
            conditions_met += 1
        
        signal = SignalType.HOLD
        
        if self._position is None and conditions_met >= 2:
            self._position = "long"
            signal = SignalType.BUY
        elif self._position == "long":
            if return_1h >= 0.03 or rsi >= 70:
                self._position = None
                signal = SignalType.SELL
        
        return signal


class VolumeClimaxFadeStrategy(BaseStrategyImpl):
    """放量高潮衰竭策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        volume_ratio_threshold = self.params.get("volume_ratio_threshold", 2.0)
        upper_shadow_threshold = self.params.get("upper_shadow_threshold", 0.3)
        
        if len(self._closes) < 12 or len(self._highs) < 1:
            return SignalType.HOLD
        
        candle_range = self._highs[-1] - self._lows[-1] if self._highs[-1] - self._lows[-1] > 0 else 1e-10
        upper_shadow = self._highs[-1] - bar.close
        upper_shadow_ratio = upper_shadow / candle_range
        
        volume_ratio = 1.0
        if len(self._volumes) >= 288:
            avg_volume = sum(self._volumes[-288:]) / 288
            if avg_volume > 0:
                volume_ratio = self._volumes[-1] / avg_volume
        
        return_1h = 0.0
        if len(self._closes) >= 12:
            price_1h_ago = self._closes[-12]
            return_1h = (bar.close - price_1h_ago) / price_1h_ago
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if volume_ratio >= volume_ratio_threshold and upper_shadow_ratio >= upper_shadow_threshold and return_1h >= 0.003:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "short":
            if return_1h <= -0.02:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class WeakBounceShortStrategy(BaseStrategyImpl):
    """弱反弹做空策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        drop_threshold_4h = self.params.get("drop_threshold_4h", -0.02)
        bounce_max = self.params.get("bounce_max", 0.015)
        
        if len(self._closes) < 60:
            return SignalType.HOLD
        
        price_4h_ago = self._closes[-48]
        price_1h_ago = self._closes[-12]
        drop_4h = (price_4h_ago - price_1h_ago) / price_4h_ago
        bounce = (bar.close - price_1h_ago) / price_1h_ago
        
        volume_ratio = 1.0
        if len(self._volumes) >= 288:
            avg_volume = sum(self._volumes[-288:]) / 288
            if avg_volume > 0:
                volume_ratio = self._volumes[-1] / avg_volume
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if drop_4h <= drop_threshold_4h and 0.003 <= bounce <= bounce_max and volume_ratio >= 1.5:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "short":
            if bounce <= -0.02:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class DeadCatEchoStrategy(BaseStrategyImpl):
    """死猫回声策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        drop_threshold_4h = self.params.get("drop_threshold_4h", -0.02)
        bounce_ratio_max = self.params.get("bounce_ratio_max", 0.30)
        
        if len(self._closes) < 48:
            return SignalType.HOLD
        
        price_4h_ago = self._closes[-48]
        drop_low = min(self._closes[-48:])
        drop_4h = (price_4h_ago - drop_low) / price_4h_ago if price_4h_ago > 0 else 0
        bounce_from_low = (bar.close - drop_low) / drop_low if drop_low > 0 else 0
        bounce_ratio = bounce_from_low / drop_4h if drop_4h > 0 else 0
        
        volume_ratio = 1.0
        if len(self._volumes) >= 48:
            avg_first = sum(self._volumes[-48:-24]) / 24
            avg_second = sum(self._volumes[-24:]) / 24
            if avg_first > 0:
                volume_ratio = avg_second / avg_first
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if drop_4h >= abs(drop_threshold_4h) and bounce_ratio <= bounce_ratio_max and volume_ratio <= 0.8:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "short":
            if bounce_from_low <= -0.02:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class OIFlushStrategy(BaseStrategyImpl):
    """OI清洗策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 48:
            return SignalType.HOLD
        
        price_24h_ago = self._closes[-48]
        price_drop = (bar.close - price_24h_ago) / price_24h_ago
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if price_drop < -0.05:
                self._position = "long"
                signal = SignalType.BUY
            elif price_drop > 0.05:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if price_drop > -0.01:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if price_drop < 0.01:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class ShortSqueezeStrategy(BaseStrategyImpl):
    """空头挤压策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 12:
            return SignalType.HOLD
        
        price_1h_ago = self._closes[-12]
        price_momentum = (bar.close - price_1h_ago) / price_1h_ago
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if price_momentum > 0.02:
                self._position = "long"
                signal = SignalType.BUY
        elif self._position == "long":
            if price_momentum > 0.05 or price_momentum < -0.01:
                self._position = None
                signal = SignalType.SELL
        
        return signal


class FundingExhaustionTrapStrategy(BaseStrategyImpl):
    """资金费率耗尽陷阱策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 14:
            return SignalType.HOLD
        
        rsi = self.calculate_rsi(self._closes, 14)
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if rsi > 80:
                self._position = "short"
                signal = SignalType.SELL
            elif rsi < 20:
                self._position = "long"
                signal = SignalType.BUY
        elif self._position == "long":
            if rsi > 60:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if rsi < 40:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class ImbalancePressureStrategy(BaseStrategyImpl):
    """订单簿失衡压力策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 12:
            return SignalType.HOLD
        
        return_1h = 0.0
        if len(self._closes) >= 12:
            price_1h_ago = self._closes[-12]
            return_1h = (bar.close - price_1h_ago) / price_1h_ago
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if return_1h > 0.015:
                self._position = "long"
                signal = SignalType.BUY
            elif return_1h < -0.015:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if return_1h < -0.005:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if return_1h > 0.005:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class SweepDetectionStrategy(BaseStrategyImpl):
    """大单扫盘检测策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 5:
            return SignalType.HOLD
        
        price_change = (bar.close - self._closes[-2]) / self._closes[-2]
        volume_ratio = 1.0
        if len(self._volumes) >= 48:
            avg_volume = sum(self._volumes[-48:]) / 48
            if avg_volume > 0:
                volume_ratio = self._volumes[-1] / avg_volume
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if price_change > 0.01 and volume_ratio > 2.0:
                self._position = "long"
                signal = SignalType.BUY
            elif price_change < -0.01 and volume_ratio > 2.0:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if price_change < -0.005:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if price_change > 0.005:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class LiquidityVacuumStrategy(BaseStrategyImpl):
    """流动性真空策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 20:
            return SignalType.HOLD
        
        recent_max = max(self._closes[-20:])
        recent_min = min(self._closes[-20:])
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if bar.close > recent_max:
                self._position = "long"
                signal = SignalType.BUY
            elif bar.close < recent_min:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if bar.close < recent_min:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if bar.close > recent_max:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class AggressiveFlowStrategy(BaseStrategyImpl):
    """主动成交流策略（简化版）"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        if len(self._closes) < 10:
            return SignalType.HOLD
        
        momentum = (bar.close - self._closes[-10]) / self._closes[-10]
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if momentum > 0.02:
                self._position = "long"
                signal = SignalType.BUY
            elif momentum < -0.02:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if momentum < -0.005:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if momentum > 0.005:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class BreakoutStrategy(BaseStrategyImpl):
    """突破策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        lookback = self.params.get("lookback", 48)
        
        if len(self._closes) < lookback + 1 or len(self._highs) < lookback or len(self._lows) < lookback:
            return SignalType.HOLD
        
        range_high = max(self._highs[-lookback:-1])
        range_low = min(self._lows[-lookback:-1])
        
        volume_ratio = 1.0
        if len(self._volumes) >= 288:
            avg_volume = sum(self._volumes[-288:]) / 288
            if avg_volume > 0:
                volume_ratio = self._volumes[-1] / avg_volume
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if bar.close > range_high and volume_ratio >= 1.5:
                self._position = "long"
                signal = SignalType.BUY
            elif bar.close < range_low and volume_ratio >= 1.5:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if bar.close < range_low:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if bar.close > range_high:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class TrendFollowingStrategy(BaseStrategyImpl):
    """趋势跟踪策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate(self, bar: Bar) -> SignalType:
        fast_period = self.params.get("fast_period", 10)
        slow_period = self.params.get("slow_period", 50)
        
        if len(self._closes) < slow_period + 2:
            return SignalType.HOLD
        
        ema_fast = self.calculate_ema(self._closes, fast_period)
        ema_slow = self.calculate_ema(self._closes, slow_period)
        ema_fast_prev = self.calculate_ema(self._closes[:-1], fast_period) if len(self._closes) > 1 else ema_fast
        ema_slow_prev = self.calculate_ema(self._closes[:-1], slow_period) if len(self._closes) > 1 else ema_slow
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if ema_fast > ema_slow and ema_fast > ema_fast_prev and ema_slow > ema_slow_prev:
                self._position = "long"
                signal = SignalType.BUY
            elif ema_fast < ema_slow and ema_fast < ema_fast_prev and ema_slow < ema_slow_prev:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if ema_fast < ema_slow:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if ema_fast > ema_slow:
                self._position = None
                signal = SignalType.BUY
        
        return signal


class BBCompressionBreakoutStrategy(BaseStrategyImpl):
    """布林压缩突破策略"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any]):
        super().__init__(strategy_id, params)
    
    def calculate_bb(self, period: int, num_std: float):
        if len(self._closes) < period:
            return 0, 0, 0
        
        sma = sum(self._closes[-period:]) / period
        squared_diffs = [(x - sma) ** 2 for x in self._closes[-period:]]
        std_dev = (sum(squared_diffs) / period) ** 0.5
        
        upper = sma + num_std * std_dev
        lower = sma - num_std * std_dev
        
        return upper, sma, lower
    
    def calculate(self, bar: Bar) -> SignalType:
        compression_threshold = self.params.get("compression_threshold", 0.02)
        
        if len(self._closes) < 20:
            return SignalType.HOLD
        
        upper, middle, lower = self.calculate_bb(20, 2.0)
        
        if upper == 0 or middle == 0:
            return SignalType.HOLD
        
        bb_width = (upper - lower) / middle
        is_compressed = bb_width < compression_threshold
        
        signal = SignalType.HOLD
        
        if self._position is None:
            if is_compressed and bar.close > upper:
                self._position = "long"
                signal = SignalType.BUY
            elif is_compressed and bar.close < lower:
                self._position = "short"
                signal = SignalType.SELL
        elif self._position == "long":
            if bar.close < lower:
                self._position = None
                signal = SignalType.SELL
        elif self._position == "short":
            if bar.close > upper:
                self._position = None
                signal = SignalType.BUY
        
        return signal


# ==============================================================================
# 策略注册表
# ==============================================================================

STRATEGY_IMPLEMENTATIONS = {
    "rsi_oversold": {
        "class": RSIOversoldStrategy,
        "param_grid": {
            "period": [7, 14, 21],
            "oversold": [20, 25, 30, 35],
        }
    },
    "rsi_overbought": {
        "class": RSIOverboughtStrategy,
        "param_grid": {
            "period": [7, 14, 21],
            "overbought": [65, 70, 75, 80],
        }
    },
    "macd_cross": {
        "class": MACDCrossStrategy,
        "param_grid": {
            "fast_period": [8, 12, 16],
            "slow_period": [20, 26, 32],
            "signal_period": [7, 9, 11],
        }
    },
    "sma_cross": {
        "class": SMACrossStrategy,
        "param_grid": {
            "fast_period": [5, 10, 20],
            "slow_period": [30, 50, 100],
        }
    },
    "ema_cross": {
        "class": EMACrossStrategy,
        "param_grid": {
            "fast_period": [5, 10, 20],
            "slow_period": [30, 50, 100],
        }
    },
    "bollinger_bands": {
        "class": BollingerBandsStrategy,
        "param_grid": {
            "period": [10, 20, 30],
            "num_std": [1.5, 2.0, 2.5],
        }
    },
    "panic_reversal": {
        "class": PanicReversalStrategy,
        "param_grid": {
            "drop_threshold": [-0.01, -0.015, -0.02],
            "volume_ratio_threshold": [1.3, 1.5, 1.8],
        }
    },
    "long_liquidation_bounce": {
        "class": LongLiquidationBounceStrategy,
        "param_grid": {
            "drop_threshold": [-0.015, -0.02, -0.025],
            "rsi_threshold": [20, 25, 30],
            "volume_ratio_threshold": [1.5, 2.0, 2.5],
        }
    },
    "volume_climax_fade": {
        "class": VolumeClimaxFadeStrategy,
        "param_grid": {
            "volume_ratio_threshold": [1.5, 2.0, 2.5],
            "upper_shadow_threshold": [0.2, 0.3, 0.4],
        }
    },
    "weak_bounce_short": {
        "class": WeakBounceShortStrategy,
        "param_grid": {
            "drop_threshold_4h": [-0.015, -0.02, -0.025],
            "bounce_max": [0.01, 0.015, 0.02],
        }
    },
    "dead_cat_echo": {
        "class": DeadCatEchoStrategy,
        "param_grid": {
            "drop_threshold_4h": [-0.015, -0.02, -0.025],
            "bounce_ratio_max": [0.2, 0.3, 0.4],
        }
    },
    "oi_flush": {
        "class": OIFlushStrategy,
        "param_grid": {
            "lookback_period": [12, 24, 48],
        }
    },
    "short_squeeze": {
        "class": ShortSqueezeStrategy,
        "param_grid": {
            "lookback_period": [12, 24, 48],
        }
    },
    "funding_exhaustion_trap": {
        "class": FundingExhaustionTrapStrategy,
        "param_grid": {
            "rsi_low": [15, 20, 25],
            "rsi_high": [75, 80, 85],
        }
    },
    "imbalance_pressure": {
        "class": ImbalancePressureStrategy,
        "param_grid": {
            "threshold": [0.01, 0.015, 0.02],
        }
    },
    "sweep_detection": {
        "class": SweepDetectionStrategy,
        "param_grid": {
            "price_change": [0.008, 0.01, 0.012],
            "volume_ratio": [1.8, 2.0, 2.2],
        }
    },
    "liquidity_vacuum": {
        "class": LiquidityVacuumStrategy,
        "param_grid": {
            "lookback": [15, 20, 25],
        }
    },
    "aggressive_flow": {
        "class": AggressiveFlowStrategy,
        "param_grid": {
            "momentum": [0.015, 0.02, 0.025],
        }
    },
    "breakout": {
        "class": BreakoutStrategy,
        "param_grid": {
            "lookback": [24, 48, 72],
        }
    },
    "trend_following": {
        "class": TrendFollowingStrategy,
        "param_grid": {
            "fast_period": [5, 10, 15],
            "slow_period": [30, 50, 75],
        }
    },
    "bb_compression_breakout": {
        "class": BBCompressionBreakoutStrategy,
        "param_grid": {
            "compression_threshold": [0.015, 0.02, 0.025],
        }
    },
}

ALL_STRATEGIES = list(STRATEGY_IMPLEMENTATIONS.keys())


# ==============================================================================
# Walk-Forward Runner
# ==============================================================================

class WalkForwardRunner:
    """Walk-Forward 参数优化运行器"""

    DATA_LAKE_PATH = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"

    def __init__(self, enable_gpu: bool = True):
        self._results: List[WalkForwardResult] = []
        self._all_data: Dict[int, List[Bar]] = {}
        self._enable_gpu = enable_gpu

    def load_year_data(self, year: int) -> List[Bar]:
        """加载指定年份的真实数据"""
        if year in self._all_data:
            return self._all_data[year]

        year_path = self.DATA_LAKE_PATH / f"year={year}"
        if not year_path.exists():
            logger.warning(f"Year {year} data not found at {year_path}")
            return []

        bars = []
        for month_dir in sorted(year_path.iterdir()):
            if month_dir.is_dir() and month_dir.name.startswith("month="):
                parquet_file = month_dir / "data.parquet"
                if parquet_file.exists():
                    df = read_parquet_safe(parquet_file)
                    if df is not None and len(df) > 0:
                        for _, row in df.iterrows():
                            try:
                                if 'timestamp' in df.columns:
                                    ts = pd.to_datetime(row['timestamp']).tz_localize('UTC')
                                elif 'open_time' in df.columns:
                                    ts = pd.to_datetime(row['open_time'], unit='ms').tz_localize('UTC')
                                else:
                                    continue
                                bar = Bar(
                                    timestamp=ts,
                                    open=float(row.get('open', 0)),
                                    high=float(row.get('high', 0)),
                                    low=float(row.get('low', 0)),
                                    close=float(row.get('close', 0)),
                                    volume=float(row.get('volume', 0)),
                                )
                                bars.append(bar)
                            except Exception as e:
                                continue

        bars = sorted(bars, key=lambda x: x.timestamp)
        self._all_data[year] = bars
        logger.info(f"Loaded {year} data: {len(bars)} bars")
        return bars

    def run_single_backtest(
        self,
        strategy_id: str,
        params: Dict[str, Any],
        year: int,
        initial_capital: float = 10000.0,
    ):
        """运行单次回测"""
        strategy_config = STRATEGY_IMPLEMENTATIONS.get(strategy_id)
        if not strategy_config:
            return None
        
        bars = self.load_year_data(year)
        if not bars:
            return None
        
        config = BacktestConfig(
            initial_capital=initial_capital,
            commission=0.0004,
            slippage=0.0005,
            position_size=0.1,
            stop_loss=0.10,
            take_profit=0.20,
            leverage=5.0,
            use_realistic_fees=True,
        )
        
        engine = BacktestEngine(config=config, enable_gpu=self._enable_gpu)
        engine.load_data(bars)
        
        strategy_impl = strategy_config["class"](strategy_id, params)
        result = engine.run(strategy_impl)
        
        return result

    def generate_param_grid(self, strategy_id: str) -> List[Dict[str, Any]]:
        """生成参数网格"""
        strategy_config = STRATEGY_IMPLEMENTATIONS.get(strategy_id)
        if not strategy_config:
            return []
        
        param_grid = strategy_config["param_grid"]
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in product(*values)]

    def optimize_params(
        self,
        strategy_id: str,
        optimize_year: int,
    ):
        """在优化年份搜索最佳参数"""
        param_combinations = self.generate_param_grid(strategy_id)
        
        logger.info(
            f"Optimizing {strategy_id} on {optimize_year} "
            f"({len(param_combinations)} combinations)"
        )

        best_params = None
        best_sharpe = -float('inf')
        best_result = None

        for i, params in enumerate(param_combinations):
            if i % 10 == 0:
                logger.info(f"  Testing {i+1}/{len(param_combinations)}")
            result = self.run_single_backtest(strategy_id, params, optimize_year)
            if result is not None:
                sharpe = result.metrics.sharpe_ratio
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
                    best_result = result

        logger.info(
            f"Optimization complete: best_params={best_params}, "
            f"sharpe={best_sharpe:.4f}"
        )

        return best_params, best_result

    def run_walk_forward(
        self,
        strategy_id: str,
        optimize_year: int = 2022,
        validation_year: int = 2023,
        test_year: int = 2024,
    ) -> WalkForwardResult:
        """运行完整的 Walk-Forward"""
        logger.info(
            f"\n{'='*60}\n"
            f"Walk-Forward: {strategy_id}\n"
            f"  Optimize: {optimize_year}\n"
            f"  Validation: {validation_year}\n"
            f"  Test: {test_year}\n"
            f"{'='*60}"
        )

        best_params, optimize_result = self.optimize_params(
            strategy_id=strategy_id,
            optimize_year=optimize_year,
        )
        
        if best_params is None:
            logger.error(f"Failed to find good params for {strategy_id}")
            return None

        logger.info(f"Validating on {validation_year}...")
        validation_result = self.run_single_backtest(
            strategy_id=strategy_id,
            params=best_params,
            year=validation_year,
        )

        logger.info(f"Testing on {test_year}...")
        test_result = self.run_single_backtest(
            strategy_id=strategy_id,
            params=best_params,
            year=test_year,
        )

        if optimize_result is None or validation_result is None or test_result is None:
            logger.error("One of the backtests failed")
            return None

        overfitting_score = self._compute_overfitting(
            optimize_result.metrics,
            validation_result.metrics,
            test_result.metrics,
        )

        result = WalkForwardResult(
            strategy_id=strategy_id,
            optimize_year=optimize_year,
            validation_year=validation_year,
            test_year=test_year,
            best_params=best_params,
            optimize_sharpe=optimize_result.metrics.sharpe_ratio,
            validation_sharpe=validation_result.metrics.sharpe_ratio,
            test_sharpe=test_result.metrics.sharpe_ratio,
            optimize_trades=optimize_result.metrics.total_trades,
            validation_trades=validation_result.metrics.total_trades,
            test_trades=test_result.metrics.total_trades,
            optimize_return=optimize_result.metrics.total_return,
            validation_return=validation_result.metrics.total_return,
            test_return=test_result.metrics.total_return,
            max_drawdown=test_result.metrics.max_drawdown_pct,
            win_rate=test_result.metrics.win_rate,
            profit_factor=test_result.metrics.profit_factor,
            overfitting_score=overfitting_score,
        )

        self._results.append(result)
        return result

    def _compute_overfitting(
        self,
        optimize_metrics,
        validation_metrics,
        test_metrics,
    ) -> float:
        """计算过拟合分数"""
        if optimize_metrics.sharpe_ratio <= 0:
            return 0.0

        decay_opt_to_test = (optimize_metrics.sharpe_ratio - test_metrics.sharpe_ratio) / optimize_metrics.sharpe_ratio

        if validation_metrics.sharpe_ratio > 0:
            decay_val_to_test = (validation_metrics.sharpe_ratio - test_metrics.sharpe_ratio) / validation_metrics.sharpe_ratio
            return max(decay_opt_to_test, decay_val_to_test)

        return decay_opt_to_test

    def generate_report(self) -> str:
        """生成标准回测报告"""
        report = []
        report.append("\n" + "="*80)
        report.append("Walk-Forward 参数优化报告 - 所有21种策略 (GPU加速)")
        report.append("="*80)
        report.append(f"\n数据: BTCUSDT 真实历史数据")
        report.append(f"优化集: 2022")
        report.append(f"验证集: 2023")
        report.append(f"测试集: 2024")
        report.append(f"策略数: {len(self._results)}")
        report.append("\n" + "-"*80)

        for result in self._results:
            report.append(f"\n策略: {result.strategy_id}")
            report.append(f"  最佳参数: {result.best_params}")
            report.append(f"\n  优化集 ({result.optimize_year}):")
            report.append(f"    Sharpe Ratio: {result.optimize_sharpe:.4f}")
            report.append(f"    Total Return: ${result.optimize_return:.2f}")
            report.append(f"    Trades: {result.optimize_trades}")
            report.append(f"\n  验证集 ({result.validation_year}):")
            report.append(f"    Sharpe Ratio: {result.validation_sharpe:.4f}")
            report.append(f"    Total Return: ${result.validation_return:.2f}")
            report.append(f"    Trades: {result.validation_trades}")
            report.append(f"\n  测试集 ({result.test_year}):")
            report.append(f"    Sharpe Ratio: {result.test_sharpe:.4f}")
            report.append(f"    Total Return: ${result.test_return:.2f}")
            report.append(f"    Max Drawdown: {result.max_drawdown:.2%}")
            report.append(f"    Win Rate: {result.win_rate:.2%}")
            report.append(f"    Profit Factor: {result.profit_factor:.4f}")
            report.append(f"    Trades: {result.test_trades}")
            report.append(f"\n  过拟合指标:")
            report.append(f"    Sharpe 衰减: {result.overfitting_score:.2%}")

            if result.overfitting_score > 0.5:
                report.append(f"    ⚠️  严重过拟合！不建议上 paper trading")
            elif result.overfitting_score > 0.3:
                report.append(f"    ⚠️  中度过拟合，需要谨慎")
            else:
                report.append(f"    ✅ 过拟合风险较低，可以考虑 paper trading")

            report.append("-"*80)

        report.append("\n" + "="*80)
        report.append("策略排行榜 (按测试集 Sharpe 排序)")
        report.append("="*80)
        
        sorted_results = sorted(self._results, key=lambda x: x.test_sharpe, reverse=True)
        for i, result in enumerate(sorted_results, 1):
            status = "✅ PASS" if result.overfitting_score <= 0.3 else "⚠️ WARN" if result.overfitting_score <=0.5 else "❌ FAIL"
            report.append(
                f"{i:2d}. {result.strategy_id:<30s} "
                f"Sharpe: {result.test_sharpe:7.4f} "
                f"Return: ${result.test_return:10.2f} "
                f"Overfit: {result.overfitting_score:6.2%} {status}"
            )

        return "\n".join(report)

    def save_results(self, output_path: str = "all_strategies_results.json"):
        """保存结果到 JSON"""
        results_dict = []
        for r in self._results:
            results_dict.append({
                "strategy_id": r.strategy_id,
                "optimize_year": r.optimize_year,
                "validation_year": r.validation_year,
                "test_year": r.test_year,
                "best_params": r.best_params,
                "optimize_sharpe": r.optimize_sharpe,
                "validation_sharpe": r.validation_sharpe,
                "test_sharpe": r.test_sharpe,
                "optimize_trades": r.optimize_trades,
                "validation_trades": r.validation_trades,
                "test_trades": r.test_trades,
                "optimize_return": r.optimize_return,
                "validation_return": r.validation_return,
                "test_return": r.test_return,
                "max_drawdown": r.max_drawdown,
                "win_rate": r.win_rate,
                "profit_factor": r.profit_factor,
                "overfitting_score": r.overfitting_score,
            })

        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        logger.info(f"Results saved to {output_path}")


def main():
    """主函数"""
    print("="*80)
    print("Walk-Forward 参数优化 - 所有21种策略 (GPU加速)")
    print("="*80)
    print(f"\n使用真实 BTCUSDT 历史数据")
    print(f"时间划分: 2022优化 → 2023验证 → 2024测试")
    print(f"策略列表 ({len(ALL_STRATEGIES)}):")
    for i, strategy in enumerate(ALL_STRATEGIES, 1):
        print(f"  {i:2d}. {strategy}")

    runner = WalkForwardRunner(enable_gpu=True)

    for strategy_id in ALL_STRATEGIES:
        try:
            print(f"\n{'='*80}")
            print(f"处理策略: {strategy_id}")
            print('='*80)
            result = runner.run_walk_forward(
                strategy_id=strategy_id,
                optimize_year=2022,
                validation_year=2023,
                test_year=2024,
            )
        except Exception as e:
            logger.error(f"Failed to run walk-forward for {strategy_id}: {e}")
            import traceback
            traceback.print_exc()

    report = runner.generate_report()
    print(report)

    runner.save_results("all_strategies_results.json")

    print("\n" + "="*80)
    print("Walk-Forward 完成！")
    print("="*80)


if __name__ == "__main__":
    main()
