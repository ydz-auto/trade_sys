#!/usr/bin/env python3
"""
综合策略回测系统
================

回测所有策略：
1. BTC Swing (RSI+MACD+EMA)
2. 技术指标策略 (布林带, 均线交叉, RSI+MACD)
3. 创新策略 (8个)
4. Behavioral Playbooks (7个)
5. 做空策略 (6个)

统计维度：
- 全部历史数据
- 近5个月 (2024-12 ~ 2025-04)
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
import pandas as pd
import numpy as np
import pyarrow.parquet as pq
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import gc

# ============================================================
# 配置
# ============================================================

class Config:
    initial_capital: float = 10000.0
    leverage: float = 50.0
    stop_loss_capital_pct: float = 0.10  # 本金10%止损
    trailing_tp_start: float = 500.0
    trailing_tp_max: float = 3000.0
    trailing_tp_step: float = 500.0
    max_hold_hours: int = 48
    commission: float = 0.0005
    slippage: float = 0.0002
    cooldown_bars: int = 6


# ============================================================
# 特征提取器
# ============================================================

class FeatureExtractor:
    def __init__(self, df: pd.DataFrame):
        self.n = len(df)
        self.df = df
        self.timestamps = df["timestamp"].values
        self.opens = df["open"].values.astype(np.float64)
        self.highs = df["high"].values.astype(np.float64)
        self.lows = df["low"].values.astype(np.float64)
        self.closes = df["close"].values.astype(np.float64)
        self.volumes = df["volume"].values.astype(np.float64)
        
        # 提取所有特征列
        self._extract_features()
        
    def _extract_features(self):
        """提取所有可能的特征"""
        df = self.df
        
        # 基础特征
        self.volume_ratio = self._get_col(df, "volume_ratio", 1.0)
        self.return_1h = self._get_col(df, "returns_1h", 0.0)
        # return_5m - handle column name variations
        if "returns_5m" in df.columns:
            self.return_5m = df["returns_5m"].fillna(0.0).values.astype(np.float64)
        elif "return_5m" in df.columns:
            self.return_5m = df["return_5m"].fillna(0.0).values.astype(np.float64)
        else:
            self.return_5m = np.zeros(self.n, dtype=np.float64)
        
        # Funding相关
        self.funding_rate = self._get_col(df, "funding_rate", 0.0)
        self.funding_zscore = self._get_col(df, "funding_zscore", 0.0)
        self.funding_delta = self._get_col(df, "funding_delta", 0.0)
        
        # OI相关
        self.oi_change = self._get_col(df, "oi_change", 0.0)
        self.oi_acceleration = self._get_col(df, "oi_acceleration", 0.0)
        
        # 波动率
        self.volatility_1h = self._get_col(df, "volatility_1h", 0.0)
        self.volatility_surge = self._get_bool_col(df, "volatility_surge")
        
        # 状态标记
        self.state_squeeze = self._get_bool_col(df, "state_squeeze")
        self.state_panic_dump = self._get_bool_col(df, "state_panic_dump")
        self.state_breakout = self._get_bool_col(df, "state_breakout")
        self.state_accumulation = self._get_bool_col(df, "state_accumulation")
        
        # Spike检测
        self.spike_up = self._get_bool_col(df, "spike_up")
        self.spike_down = self._get_bool_col(df, "spike_down")
        self.major_spike_up = self._get_bool_col(df, "major_spike_up")
        self.major_spike_down = self._get_bool_col(df, "major_spike_down")
        
        # 趋势相关
        self.trend_exhaustion = self._get_bool_col(df, "trend_exhaustion")
        self.trend_healthy = self._get_bool_col(df, "trend_healthy")
        self.momentum_shift = self._get_bool_col(df, "momentum_shift")
        
        # 突破强度
        self.breakout_strength_24h = self._get_col(df, "breakout_strength_24h", 0.0)
        
        # Regime
        self.regime = df["regime"].values if "regime" in df.columns else np.array(["ranging"] * self.n)
        
        # 计算技术指标
        self._calculate_indicators()
        
    def _get_col(self, df: pd.DataFrame, col: str, default: float) -> np.ndarray:
        if col in df.columns:
            return df[col].fillna(default).values.astype(np.float64)
        return np.full(len(df), default, dtype=np.float64)
    
    def _get_bool_col(self, df: pd.DataFrame, col: str) -> np.ndarray:
        if col in df.columns:
            arr = df[col].fillna(False).values
            return arr.astype(bool) if arr.dtype != bool else arr
        return np.zeros(len(df), dtype=bool)
    
    def _calculate_indicators(self):
        """计算技术指标"""
        closes = self.closes
        
        # RSI (14)
        self.rsi = self._calculate_rsi(closes, 14)
        
        # MACD
        macd = self._calculate_macd(closes, 12, 26, 9)
        self.macd_line = macd["macd"]
        self.macd_signal = macd["signal"]
        self.macd_histogram = macd["histogram"]
        
        # EMA
        self.ema_20 = self._calculate_ema(closes, 20)
        self.ema_50 = self._calculate_ema(closes, 50)
        
        # Bollinger Bands
        bb = self._calculate_bollinger_bands(closes, 20, 2.0)
        self.bb_upper = bb["upper"]
        self.bb_lower = bb["lower"]
        self.bb_middle = bb["middle"]
        self.bb_width = (self.bb_upper - self.bb_lower) / self.bb_middle
        
        # 均线
        self.sma_50 = self._calculate_sma(closes, 50)
        self.sma_200 = self._calculate_sma(closes, 200)
        
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        rsi = np.zeros_like(prices)
        rsi[:] = 50.0
        deltas = np.diff(prices)
        for i in range(period + 1, len(prices)):
            delta_window = deltas[i-period:i]
            gains = delta_window[delta_window > 0]
            losses = -delta_window[delta_window < 0]
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray, fast: int, slow: int, signal: int) -> Dict:
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        k = 2 / (period + 1)
        for i in range(1, len(prices)):
            ema[i] = ema[i-1] * (1 - k) + prices[i] * k
        return ema
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> np.ndarray:
        sma = np.zeros_like(prices)
        for i in range(period, len(prices)):
            sma[i] = np.mean(prices[i-period:i])
        return sma
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int, std_dev: float) -> Dict:
        middle = self._calculate_sma(prices, period)
        upper = np.zeros_like(prices)
        lower = np.zeros_like(prices)
        for i in range(period, len(prices)):
            std = np.std(prices[i-period:i])
            upper[i] = middle[i] + std_dev * std
            lower[i] = middle[i] - std_dev * std
        return {"upper": upper, "lower": lower, "middle": middle}


# ============================================================
# 策略定义
# ============================================================

class Strategy:
    def __init__(self, name: str, direction: str):
        self.name = name
        self.direction = direction
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        raise NotImplementedError


# ========== 1. BTC Swing策略 ==========

class BTCSwingStrategy(Strategy):
    """BTC Swing: RSI≤30 + MACD金叉做多, RSI≥70出场"""
    def __init__(self):
        super().__init__("BTC Swing", "long")
        self._prev_macd = None
        self._prev_signal = None
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 50:
            return False, 0
        
        rsi = fe.rsi[i]
        macd = fe.macd_line[i]
        signal = fe.macd_signal[i]
        
        # MACD金叉检测
        macd_cross = (fe.macd_line[i-1] <= fe.macd_signal[i-1]) and (macd > signal)
        
        if rsi <= 30 and macd_cross:
            return True, 1.0
        return False, 0


# ========== 2. 技术指标策略 ==========

class BollingerBandsStrategy(Strategy):
    """布林带: 跌破下轨做多, 突破上轨做空"""
    def __init__(self):
        super().__init__("Bollinger Bands", "both")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 20:
            return False, 0
        
        price = fe.closes[i]
        prev_price = fe.closes[i-1]
        lower = fe.bb_lower[i]
        upper = fe.bb_upper[i]
        
        # 跌破下轨做多
        if prev_price >= fe.bb_lower[i-1] and price < lower:
            self.direction = "long"
            return True, 0.7
        
        # 突破上轨做空
        if prev_price <= fe.bb_upper[i-1] and price > upper:
            self.direction = "short"
            return True, 0.7
        
        return False, 0


class MovingAverageCrossStrategy(Strategy):
    """均线交叉: 50MA上穿200MA做多, 下穿做空"""
    def __init__(self):
        super().__init__("MA Cross", "both")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 200:
            return False, 0
        
        fast = fe.sma_50[i]
        slow = fe.sma_200[i]
        prev_fast = fe.sma_50[i-1]
        prev_slow = fe.sma_200[i-1]
        
        # 金叉
        if prev_fast <= prev_slow and fast > slow:
            self.direction = "long"
            return True, 0.75
        
        # 死叉
        if prev_fast >= prev_slow and fast < slow:
            self.direction = "short"
            return True, 0.75
        
        return False, 0


class RSIMACDStrategy(Strategy):
    """RSI+MACD: RSI超卖+MACD金叉做多, RSI超买+MACD死叉做空"""
    def __init__(self):
        super().__init__("RSI+MACD", "both")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 26:
            return False, 0
        
        rsi = fe.rsi[i]
        macd = fe.macd_line[i]
        signal = fe.macd_signal[i]
        prev_macd = fe.macd_line[i-1]
        prev_signal = fe.macd_signal[i-1]
        
        # RSI超卖 + MACD金叉
        if rsi <= 30 and prev_macd <= prev_signal and macd > signal:
            self.direction = "long"
            return True, 0.85
        
        # RSI超买 + MACD死叉
        if rsi >= 70 and prev_macd >= prev_signal and macd < signal:
            self.direction = "short"
            return True, 0.85
        
        return False, 0


# ========== 3. 创新策略 ==========

class LeveragedShortSqueezeStrategy(Strategy):
    """杠杆空头挤压: funding_zscore>2 + 涨>1% + volume_ratio>1.5"""
    def __init__(self):
        super().__init__("Leveraged Short Squeeze", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        score = 0
        if fe.funding_zscore[i] > 2:
            score += 3
        if fe.return_1h[i] > 0.01:
            score += 2
        if fe.volume_ratio[i] > 1.5:
            score += 2
        if fe.volatility_surge[i]:
            score += 1
            
        return score >= 5, score


class MicroRangeRipplesStrategy(Strategy):
    """微区间波纹: bb_width极低 + 突破 + 放量"""
    def __init__(self):
        super().__init__("Micro Range Ripples", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 20:
            return False, 0
        
        bb_width_low = fe.bb_width[i] < 0.02
        price_breakout = fe.closes[i] > fe.bb_upper[i-1]
        volume_spike = fe.volume_ratio[i] > 1.5
        
        if bb_width_low and price_breakout and volume_spike:
            return True, 1.0
        return False, 0


class CascadeFlipStrategy(Strategy):
    """爆仓翻转: volume_ratio>3 + 跌>2% + funding高"""
    def __init__(self):
        super().__init__("Cascade Flip", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        score = 0
        if fe.volume_ratio[i] > 3:
            score += 3
        if fe.return_1h[i] < -0.02:
            score += 2
        if fe.funding_rate[i] > 0.0002:
            score += 1
        if fe.state_panic_dump[i]:
            score += 2
            
        return score >= 5, score


class FundingExhaustionTrapStrategy(Strategy):
    """Funding枯竭陷阱: funding_zscore>2.5 + funding回落 + 滞涨"""
    def __init__(self):
        super().__init__("Funding Exhaustion Trap", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 24:
            return False, 0
        
        score = 0
        if fe.funding_zscore[i] > 2.5:
            score += 3
        if fe.funding_delta[i] < 0:
            score += 2
        if abs(fe.return_1h[i]) < 0.005:
            score += 2
        if fe.trend_exhaustion[i]:
            score += 1
            
        return score >= 5, score


class MemeManiaRotationStrategy(Strategy):
    """Meme狂热轮动: volume_spike + 大涨 + 高波动"""
    def __init__(self):
        super().__init__("Meme Mania Rotation", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        score = 0
        if fe.volume_ratio[i] > 2.5:
            score += 2
        if fe.return_1h[i] > 0.03:
            score += 3
        if fe.volatility_surge[i]:
            score += 2
        if fe.spike_up[i]:
            score += 1
            
        return score >= 5, score


class SessionGapExploitStrategy(Strategy):
    """时段切换缺口: 时段切换 + 低流动性 + 波动放大"""
    def __init__(self):
        super().__init__("Session Gap Exploit", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 6:
            return False, 0
        
        # 简化为高波动 + 低成交量组合
        score = 0
        if fe.volatility_surge[i]:
            score += 2
        if fe.volume_ratio[i] < 0.8:
            score += 2
        if abs(fe.return_5m[i]) > 0.005:
            score += 2
            
        return score >= 4, score


class DeadCatEchoStrategy(Strategy):
    """死猫回声: 前期大跌 + 弱反弹 + 趋势衰竭"""
    def __init__(self):
        super().__init__("Dead Cat Echo", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 48:
            return False, 0
        
        score = 0
        # 前期大跌
        if fe.return_1h[i-12] < -0.02:
            score += 2
        # 弱反弹
        if 0 < fe.return_5m[i] < 0.005:
            score += 2
        # 趋势衰竭
        if fe.trend_exhaustion[i]:
            score += 3
        if fe.volume_ratio[i] < 1.0:
            score += 1
            
        return score >= 5, score


class LiquidityVacuumBreakoutStrategy(Strategy):
    """流动性真空突破: 低流动性 + 突破"""
    def __init__(self):
        super().__init__("Liquidity Vacuum Breakout", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 20:
            return False, 0
        
        score = 0
        if fe.volume_ratio[i] < 0.7:
            score += 3
        if fe.closes[i] > fe.bb_upper[i]:
            score += 2
        if fe.volatility_surge[i]:
            score += 2
            
        return score >= 4, score


# ========== 4. Behavioral Playbooks ==========

class PanicReversalStrategy(Strategy):
    """恐慌反转: 暴跌后反弹"""
    def __init__(self):
        super().__init__("Panic Reversal", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        # 1小时跌>1.5% + 成交量>1.3倍
        if fe.return_1h[i] < -0.015 and fe.volume_ratio[i] > 1.3:
            return True, 0.8
        return False, 0


class FakeBreakoutStrategy(Strategy):
    """假突破: 突破后反杀"""
    def __init__(self):
        super().__init__("Fake Breakout", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 24:
            return False, 0
        
        # 突破阈值0.5%但成交量<0.8倍
        breakout = abs(fe.breakout_strength_24h[i]) > 0.005
        low_volume = fe.volume_ratio[i] < 0.8
        
        if breakout and low_volume:
            return True, 0.75
        return False, 0


class OIFlushStrategy(Strategy):
    """OI清洗: OI下降后趋势延续"""
    def __init__(self):
        super().__init__("OI Flush", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        # OI下降 + 价格反弹
        if fe.oi_change[i] < -0.01 and fe.return_5m[i] > 0.002:
            return True, 0.7
        return False, 0


class WeekendManipulationStrategy(Strategy):
    """周末操纵: 周末低流动性异动"""
    def __init__(self):
        super().__init__("Weekend Manipulation", "both")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 6:
            return False, 0
        
        # 低流动性 + 异常波动
        if fe.volume_ratio[i] < 0.6 and abs(fe.return_5m[i]) > 0.008:
            self.direction = "long" if fe.return_5m[i] > 0 else "short"
            return True, 0.6
        return False, 0


class ShortSqueezeStrategy(Strategy):
    """空头挤压"""
    def __init__(self):
        super().__init__("Short Squeeze", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        score = 0
        if fe.funding_rate[i] < 0:
            score += 2
        if fe.oi_acceleration[i] > 0.01:
            score += 2
        if fe.return_1h[i] > 0.008:
            score += 2
            
        return score >= 4, score


class LiquidationCascadeStrategy(Strategy):
    """清算连锁"""
    def __init__(self):
        super().__init__("Liquidation Cascade", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        score = 0
        if fe.volume_ratio[i] > 3:
            score += 3
        if fe.return_1h[i] < -0.015:
            score += 2
        if fe.spike_down[i]:
            score += 2
        if fe.state_panic_dump[i]:
            score += 1
            
        return score >= 5, score


class VolumeClimaxStrategy(Strategy):
    """放量高潮衰竭"""
    def __init__(self):
        super().__init__("Volume Climax", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 6:
            return False, 0
        
        # 放量 + 长上影线 + 上涨
        volume_spike = fe.volume_ratio[i] > 2.0
        upper_wick = (fe.highs[i] - fe.closes[i]) / (fe.highs[i] - fe.lows[i] + 0.001) > 0.3
        price_up = fe.return_5m[i] > 0
        
        if volume_spike and upper_wick and price_up:
            return True, 0.8
        return False, 0


# ========== 5. 做空策略V2 ==========

class VolumeClimaxFadeV2Strategy(Strategy):
    """放量高潮衰竭V2"""
    def __init__(self):
        super().__init__("Volume Climax Fade V2", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 6:
            return False, 0
        
        score = 0
        if fe.volume_ratio[i] > 2.0:
            score += 3
        upper_wick = (fe.highs[i] - fe.closes[i]) / (fe.highs[i] - fe.lows[i] + 0.001)
        if upper_wick > 0.3:
            score += 2
        if fe.return_5m[i] > 0:
            score += 1
            
        return score >= 4, score


class WeakBounceShortV2Strategy(Strategy):
    """弱反弹做空V2"""
    def __init__(self):
        super().__init__("Weak Bounce Short V2", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 48:
            return False, 0
        
        score = 0
        if fe.return_1h[i-12] < -0.02:
            score += 2
        bounce = fe.closes[i] / fe.closes[i-12] - 1
        if 0.003 < bounce < 0.015:
            score += 3
        if fe.volume_ratio[i] > 1.5:
            score += 1
            
        return score >= 4, score


class FakeBreakoutTrapV2Strategy(Strategy):
    """假突破陷阱V2"""
    def __init__(self):
        super().__init__("Fake Breakout Trap V2", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 24:
            return False, 0
        
        score = 0
        if abs(fe.breakout_strength_24h[i]) > 0.005:
            score += 2
        if fe.volume_ratio[i] < 1.0:
            score += 3
        if fe.return_5m[i] < -0.001:
            score += 1
            
        return score >= 4, score


class WeekendLiquidityTrapV2Strategy(Strategy):
    """周末流动性陷阱V2"""
    def __init__(self):
        super().__init__("Weekend Liquidity Trap V2", "both")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 6:
            return False, 0
        
        if fe.volume_ratio[i] < 0.7 and abs(fe.return_5m[i]) > 0.005:
            self.direction = "long" if fe.return_5m[i] > 0 else "short"
            return True, 0.65
        return False, 0


class ShortSqueezeHuntV2Strategy(Strategy):
    """空头挤压狩猎V2"""
    def __init__(self):
        super().__init__("Short Squeeze Hunt V2", "long")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 12:
            return False, 0
        
        score = 0
        if fe.funding_rate[i] < 0:
            score += 2
        if fe.oi_change[i] > 0.01:
            score += 2
        if fe.return_1h[i] > 0.008:
            score += 2
            
        return score >= 4, score


class FundingResetV2Strategy(Strategy):
    """Funding重置V2"""
    def __init__(self):
        super().__init__("Funding Reset V2", "short")
        
    def detect(self, fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
        if i < 24:
            return False, 0
        
        score = 0
        if fe.funding_rate[i] > 0.0003:
            score += 2
        if fe.funding_delta[i] < 0:
            score += 3
        if fe.trend_exhaustion[i]:
            score += 1
            
        return score >= 4, score


# ============================================================
# 回测引擎
# ============================================================

def run_backtest(
    fe: FeatureExtractor,
    config: Config,
    strategy: Strategy,
    start_idx: int = 0,
    end_idx: int = None
) -> List[Dict]:
    """运行回测"""
    price_sl_pct = config.stop_loss_capital_pct / config.leverage
    n = fe.n if end_idx is None else end_idx
    trades = []
    capital = config.initial_capital
    
    last_signal_bar = -999
    i = max(288, start_idx)  # 预热期
    
    while i < n:
        if i - last_signal_bar < config.cooldown_bars:
            i += 1
            continue
        
        triggered, score = strategy.detect(fe, i)
        if not triggered:
            i += 1
            continue
        
        last_signal_bar = i
        entry_price = fe.closes[i]
        entry_time = fe.timestamps[i]
        direction = strategy.direction if strategy.direction != "both" else "long"
        margin = capital
        
        # 止损价
        if direction == "long":
            sl_price = entry_price * (1 - price_sl_pct)
        else:
            sl_price = entry_price * (1 + price_sl_pct)
        
        # 移动止盈
        trailing_tp_points = config.trailing_tp_start
        if direction == "long":
            trailing_tp_price = entry_price + trailing_tp_points
        else:
            trailing_tp_price = entry_price - trailing_tp_points
        
        max_favorable = 0.0
        max_adverse = 0.0
        
        exit_price = None
        exit_reason = None
        j = i + 1
        max_bars = int(config.max_hold_hours * 60)
        
        while j < n and (j - i) < max_bars:
            h = fe.highs[j]
            l = fe.lows[j]
            
            if direction == "long":
                favorable = h - entry_price
                adverse = entry_price - l
            else:
                favorable = entry_price - l
                adverse = h - entry_price
            
            if favorable > max_favorable:
                max_favorable = favorable
            if adverse > max_adverse:
                max_adverse = adverse
            
            # 更新移动止盈
            new_tp_points = int(max_favorable / config.trailing_tp_step) * config.trailing_tp_step + config.trailing_tp_start
            new_tp_points = min(new_tp_points, config.trailing_tp_max)
            if new_tp_points > trailing_tp_points:
                trailing_tp_points = new_tp_points
                if direction == "long":
                    trailing_tp_price = entry_price + trailing_tp_points
                else:
                    trailing_tp_price = entry_price - trailing_tp_points
            
            # 检查止损
            if direction == "long":
                if l <= sl_price:
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
                if l <= trailing_tp_price:
                    exit_price = trailing_tp_price
                    exit_reason = "trailing_tp"
                    break
            else:
                if h >= sl_price:
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
                if h >= trailing_tp_price:
                    exit_price = trailing_tp_price
                    exit_reason = "trailing_tp"
                    break
            
            j += 1
        
        if exit_price is None:
            exit_price = fe.closes[min(j, n-1)]
            exit_reason = "time_exit"
            j = min(j, n-1)
        
        # 计算盈亏
        if direction == "long":
            price_pnl_pct = (exit_price - entry_price) / entry_price
        else:
            price_pnl_pct = (entry_price - exit_price) / entry_price
        
        leveraged_pnl_pct = price_pnl_pct * config.leverage
        fee_pct = (config.commission + config.slippage) * 2 * config.leverage
        leveraged_pnl_pct -= fee_pct
        
        pnl = margin * leveraged_pnl_pct
        new_capital = margin + pnl
        
        trades.append({
            "entry_time": str(entry_time),
            "exit_time": str(fe.timestamps[j]),
            "entry_price": round(float(entry_price), 1),
            "exit_price": round(float(exit_price), 1),
            "direction": direction,
            "pnl_pct": round(float(leveraged_pnl_pct), 4),
            "capital_before": round(float(capital), 2),
            "capital_after": round(float(new_capital), 2),
            "exit_reason": exit_reason,
            "hold_bars": int(j - i),
            "max_favorable": round(float(max_favorable), 1),
            "max_adverse": round(float(max_adverse), 1),
            "trailing_tp_hit": float(trailing_tp_points),
        })
        
        capital = new_capital
        
        if capital <= 0:
            break
        
        i = j + 1
    
    return trades


def analyze_trades(trades: List[Dict], initial_capital: float) -> Dict:
    """分析交易结果"""
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "total_return_pct": 0, "max_drawdown_pct": 0,
            "avg_win_pct": 0, "avg_loss_pct": 0, "profit_factor": 0,
        }
    
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    
    peak = trades[0]["capital_before"]
    max_dd = 0
    for t in trades:
        eq = t["capital_before"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    final_eq = trades[-1]["capital_after"]
    if final_eq < peak:
        dd = (peak - final_eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    total_pnl = sum((t["capital_after"] - t["capital_before"]) for t in trades)
    final = trades[-1]["capital_after"]
    total_return_pct = (final - initial_capital) / initial_capital if initial_capital > 0 else 0
    
    total_wins = sum((t["capital_after"] - t["capital_before"]) for t in wins)
    total_losses = abs(sum((t["capital_after"] - t["capital_before"]) for t in losses))
    
    return {
        "total_trades": len(trades),
        "win_rate": len(wins) / len(trades) if trades else 0,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd,
        "avg_win_pct": float(np.mean([t["pnl_pct"] for t in wins])) if wins else 0,
        "avg_loss_pct": float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0,
        "profit_factor": total_wins / total_losses if total_losses > 0 else 999,
        "sl_count": sum(1 for t in trades if t["exit_reason"] == "stop_loss"),
        "tp_count": sum(1 for t in trades if t["exit_reason"] == "trailing_tp"),
        "time_count": sum(1 for t in trades if t["exit_reason"] == "time_exit"),
        "initial_capital": initial_capital,
        "final_capital": final,
    }


# ============================================================
# 主函数
# ============================================================

def main():
    print("="*120)
    print("  综合策略回测系统")
    print("  包含: BTC Swing + 技术指标 + 创新策略 + Playbooks + 做空策略")
    print("="*120)
    
    config = Config()
    
    # 加载数据
    data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return
    
    print(f"\n📥 加载数据...")
    schema = pq.read_schema(data_path)
    existing_cols = schema.names
    
    usecols = [
        "timestamp", "open", "high", "low", "close", "volume",
        "volume_ratio", "returns_1h", "returns_5m", "return_5m",
        "funding_rate", "funding_zscore", "funding_delta",
        "oi_change", "oi_acceleration",
        "volatility_1h", "volatility_surge",
        "state_squeeze", "state_panic_dump", "state_breakout", "state_accumulation",
        "spike_up", "spike_down", "major_spike_up", "major_spike_down",
        "trend_exhaustion", "trend_healthy", "momentum_shift",
        "breakout_strength_24h", "regime",
    ]
    load_cols = [c for c in usecols if c in existing_cols]
    
    df = pd.read_parquet(data_path, columns=load_cols)
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # 转换timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print(f"   数据量: {len(df)} 行")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    
    # 找到近5个月的起始索引
    cutoff_date = df['timestamp'].max() - pd.Timedelta(days=150)  # 约5个月
    recent_start_idx = df[df['timestamp'] >= cutoff_date].index[0]
    print(f"   近5个月起始: {df.loc[recent_start_idx, 'timestamp']} (索引 {recent_start_idx})")
    
    # 提取特征
    print(f"\n⏳ 提取特征...")
    fe = FeatureExtractor(df)
    print(f"   特征提取完成")
    
    # 定义所有策略
    strategies = [
        # 1. BTC Swing
        BTCSwingStrategy(),
        
        # 2. 技术指标
        BollingerBandsStrategy(),
        MovingAverageCrossStrategy(),
        RSIMACDStrategy(),
        
        # 3. 创新策略
        LeveragedShortSqueezeStrategy(),
        MicroRangeRipplesStrategy(),
        CascadeFlipStrategy(),
        FundingExhaustionTrapStrategy(),
        MemeManiaRotationStrategy(),
        SessionGapExploitStrategy(),
        DeadCatEchoStrategy(),
        LiquidityVacuumBreakoutStrategy(),
        
        # 4. Playbooks
        PanicReversalStrategy(),
        FakeBreakoutStrategy(),
        OIFlushStrategy(),
        WeekendManipulationStrategy(),
        ShortSqueezeStrategy(),
        LiquidationCascadeStrategy(),
        VolumeClimaxStrategy(),
        
        # 5. 做空策略V2
        VolumeClimaxFadeV2Strategy(),
        WeakBounceShortV2Strategy(),
        FakeBreakoutTrapV2Strategy(),
        WeekendLiquidityTrapV2Strategy(),
        ShortSqueezeHuntV2Strategy(),
        FundingResetV2Strategy(),
    ]
    
    print(f"\n📊 共 {len(strategies)} 个策略待回测")
    
    # 存储结果
    all_results = {}
    recent_results = {}
    
    output_dir = backend_path / "data_lake/research"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for idx, strategy in enumerate(strategies, 1):
        print(f"\n{'='*100}")
        print(f"  [{idx}/{len(strategies)}] 回测: {strategy.name}")
        print(f"{'='*100}")
        
        # 全部历史
        trades_all = run_backtest(fe, config, strategy, start_idx=0)
        stats_all = analyze_trades(trades_all, config.initial_capital)
        
        # 近5个月
        trades_recent = run_backtest(fe, config, strategy, start_idx=recent_start_idx)
        stats_recent = analyze_trades(trades_recent, config.initial_capital)
        
        all_results[strategy.name] = {"stats": stats_all, "trades": trades_all}
        recent_results[strategy.name] = {"stats": stats_recent, "trades": trades_recent}
        
        # 打印结果
        print(f"\n  📊 全部历史:")
        if stats_all["total_trades"] > 0:
            print(f"     交易: {stats_all['total_trades']} | 胜率: {stats_all['win_rate']*100:.1f}% | "
                  f"收益: {stats_all['total_return_pct']*100:+.1f}% | 回撤: {stats_all['max_drawdown_pct']*100:.1f}%")
        else:
            print(f"     无交易")
        
        print(f"\n  📊 近5个月:")
        if stats_recent["total_trades"] > 0:
            print(f"     交易: {stats_recent['total_trades']} | 胜率: {stats_recent['win_rate']*100:.1f}% | "
                  f"收益: {stats_recent['total_return_pct']*100:+.1f}% | 回撤: {stats_recent['max_drawdown_pct']*100:.1f}%")
        else:
            print(f"     无交易")
        
        # 保存交易记录
        if trades_all:
            tmp_file = output_dir / f"_comprehensive_{strategy.name.replace(' ', '_')}_trades.json"
            with open(tmp_file, "w") as f:
                json.dump(trades_all, f, ensure_ascii=False, default=str)
        
        del trades_all, trades_recent
        gc.collect()
    
    # 汇总报告
    print(f"\n{'='*120}")
    print("  📈 综合回测报告")
    print(f"{'='*120}")
    
    print(f"\n{'策略':<35} | {'全部-交易':>8} | {'全部-胜率':>8} | {'全部-收益':>10} | {'近5月-交易':>8} | {'近5月-胜率':>8} | {'近5月-收益':>10}")
    print(f"{'-'*120}")
    
    for name in all_results:
        all_stats = all_results[name]["stats"]
        recent_stats = recent_results[name]["stats"]
        
        all_trades = all_stats["total_trades"]
        all_win = all_stats["win_rate"]*100 if all_stats["total_trades"] > 0 else 0
        all_ret = all_stats["total_return_pct"]*100 if all_stats["total_trades"] > 0 else 0
        
        recent_trades = recent_stats["total_trades"]
        recent_win = recent_stats["win_rate"]*100 if recent_stats["total_trades"] > 0 else 0
        recent_ret = recent_stats["total_return_pct"]*100 if recent_stats["total_trades"] > 0 else 0
        
        if all_stats["total_trades"] > 0 or recent_stats["total_trades"] > 0:
            print(f"{name:<35} | {all_trades:>8} | {all_win:>7.1f}% | {all_ret:>+9.1f}% | {recent_trades:>8} | {recent_win:>7.1f}% | {recent_ret:>+9.1f}%")
    
    # 保存汇总结果
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "leverage": config.leverage,
            "stop_loss_capital_pct": config.stop_loss_capital_pct,
            "trailing_tp_start": config.trailing_tp_start,
            "data_range": f"{df['timestamp'].min()} ~ {df['timestamp'].max()}",
            "recent_cutoff": str(cutoff_date),
        },
        "all_history": {k: v["stats"] for k, v in all_results.items()},
        "recent_5months": {k: v["stats"] for k, v in recent_results.items()},
    }
    
    output_path = output_dir / "comprehensive_strategy_backtest.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n💾 结果已保存: {output_path}")
    print("\n✅ 回测完成！")


if __name__ == "__main__":
    main()
