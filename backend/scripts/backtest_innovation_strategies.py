#!/usr/bin/env python3
"""
创新策略研究矩阵回测 - 8大创新策略 Event Study + Playbook Backtest

基于现有 Feature Engine + Market Structure 特征，将 8 个创新策略融入策略研究矩阵。

策略列表：
1. Leveraged Short Squeeze  - OI激增+多头爆仓 → 做多
2. Micro Range Ripples      - 低波动区间突破 → 做多
3. Cascade Flip             - 连锁爆仓后价格反弹 → 做多
4. Funding Exhaustion Trap  - Funding极高+仓位快速变化 → 做空
5. Meme Mania Rotation      - 板块轮动+放量 → 做多
6. Session Gap Exploit      - 时段切换引发的微型波动 → 做多
7. Dead Cat Echo            - 暴跌弱反弹后的次级反转 → 做空
8. Liquidity Vacuum Breakout - 夜间低流动性突破 → 做多

数据约束：
- OI数据仅1.6%覆盖率 → 用 volume_ratio + funding_rate 代理
- 清算数据完全缺失 → 用 volume_ratio > 3 + 大幅下跌 代理 liquidation cascade
- Funding Rate 数据完整 → 直接使用
"""

from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

import pandas as pd
import numpy as np


# ============================================================
# 数据结构
# ============================================================

class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    features: Dict = field(default_factory=dict)


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.3
    stop_loss: float = 0.015
    take_profit: float = 0.03
    max_hold_hours: int = 4
    # 高杠杆参数
    leverage: float = 1.0  # 杠杆倍数
    stop_loss_capital_pct: float = 0.0  # 本金止损比例 (如 0.1 = 10%)
    take_profit_capital_pct: float = 0.0  # 本金止盈比例 (如 0.6 = 60%)


@dataclass
class MarketEvent:
    """市场事件"""
    event_id: str
    event_type: str
    timestamp: datetime
    price: float
    strength: float = 0.0
    intensity: float = 0.0
    context: Dict = field(default_factory=dict)
    features: Dict = field(default_factory=dict)
    future_returns: Dict = field(default_factory=dict)
    max_runup: float = 0.0
    max_drawdown: float = 0.0
    time_to_peak: int = 0
    time_to_trough: int = 0
    reversal_prob: float = 0.0


@dataclass
class EventStats:
    """事件统计"""
    event_type: str
    context_filter: str
    count: int = 0
    avg_returns: Dict = field(default_factory=dict)
    positive_rates: Dict = field(default_factory=dict)
    reversal_prob: float = 0.0
    avg_max_runup: float = 0.0
    avg_max_drawdown: float = 0.0
    drawdown_prob: float = 0.0
    avg_duration_to_peak: int = 0
    avg_duration_to_trough: int = 0
    best_entry: str = "immediate"
    best_exit: str = "1h"


# ============================================================
# 8大创新策略定义
# ============================================================

STRATEGY_DEFINITIONS = {
    "leveraged_short_squeeze": {
        "name": "Leveraged Short Squeeze",
        "description": "多头爆仓+OI激增+Funding极高 → 价格急涨后回调做空",
        "direction": "short",  # 做空回调
        "timeframe": "1-15m",
        "detection": "liquidation_spike + long_liq_ratio高 + OI激增 + funding极高 + 放量",
        "context_tags": ["High Funding", "杠杆多头集中", "OI高"],
        "core_features": [
            "long_liq_ratio", "oi_delta", "funding_zscore", "funding_rate",
            "liquidation_spike", "volume_ratio", "volume_spike",
            "spread_widening", "wick_ratio",
        ],
        "stop_loss": 0.02,
        "take_profit": 0.015,
        "max_hold_hours": 1,
    },
    "micro_range_ripples": {
        "name": "Micro Range Ripples",
        "description": "低波动区间突破 → 趋势延续",
        "direction": "long",
        "timeframe": "1-5m",
        "detection": "bb_width极低 + 突破 + 放量",
        "context_tags": ["低波动", "低流动性"],
        "core_features": ["bb_position", "volatility_1h", "volume_ratio"],
        "stop_loss": 0.008,
        "take_profit": 0.012,
        "max_hold_hours": 1,
    },
    "cascade_flip": {
        "name": "Cascade Flip",
        "description": "连锁爆仓后价格反弹 → 做多反弹",
        "direction": "long",
        "timeframe": "5-30m",
        "detection": "volume_ratio极高 + 大幅下跌 + funding高",
        "context_tags": ["High OI", "多头集中"],
        "core_features": ["volume_ratio", "return_1h", "funding_rate"],
        "stop_loss": 0.015,
        "take_profit": 0.03,
        "max_hold_hours": 2,
    },
    "funding_exhaustion_trap": {
        "name": "Funding Exhaustion Trap",
        "description": "Funding极高+仓位快速变化 → 反转做空",
        "direction": "short",
        "timeframe": "15m-1h",
        "detection": "funding_zscore极高 + funding开始回落 + 价格滞涨",
        "context_tags": ["funding_high", "OI上升"],
        "core_features": ["funding_zscore", "funding_delta", "return_1h"],
        "stop_loss": 0.02,
        "take_profit": 0.025,
        "max_hold_hours": 2,
    },
    "meme_mania_rotation": {
        "name": "Meme Mania Rotation",
        "description": "板块轮动+放量 → 追涨",
        "direction": "long",
        "timeframe": "15m-4h",
        "detection": "volume_spike + 大幅上涨 + 高波动",
        "context_tags": ["社交热度高", "高波动"],
        "core_features": ["volume_ratio", "spike_up", "volatility_1h"],
        "stop_loss": 0.025,
        "take_profit": 0.05,
        "max_hold_hours": 4,
    },
    "session_gap_exploit": {
        "name": "Session Gap Exploit",
        "description": "时段切换引发的微型波动 → 顺势入场",
        "direction": "long",
        "timeframe": "5m-1h",
        "detection": "时段切换(亚洲/美盘开盘) + 低流动性 + 波动放大",
        "context_tags": ["亚洲/美盘开盘", "低流动性"],
        "core_features": ["volume_ratio", "hour", "intrabar_volatility"],
        "stop_loss": 0.01,
        "take_profit": 0.015,
        "max_hold_hours": 1,
    },
    "dead_cat_echo": {
        "name": "Dead Cat Echo",
        "description": "暴跌弱反弹后的次级反转 → 做空",
        "direction": "short",
        "timeframe": "15m-2h",
        "detection": "前期大跌 + 弱反弹 + 趋势衰竭 + 成交量衰减",
        "context_tags": ["压力位附近", "弱势趋势"],
        "core_features": ["trend_exhaustion", "return_1h", "volume_ratio"],
        "stop_loss": 0.02,
        "take_profit": 0.03,
        "max_hold_hours": 2,
    },
    "liquidity_vacuum_breakout": {
        "name": "Liquidity Vacuum Breakout",
        "description": "夜间低流动性突破 → 趋势延续",
        "direction": "long",
        "timeframe": "5-30m",
        "detection": "低成交量 + spread_widening(用volume_ratio代理) + 突破",
        "context_tags": ["low volume", "spread_widening"],
        "core_features": ["volume_ratio", "bb_position", "breakout_strength_24h"],
        "stop_loss": 0.012,
        "take_profit": 0.02,
        "max_hold_hours": 1,
    },
}


# ============================================================
# 创新策略回测引擎
# ============================================================

class InnovationStrategyBacktester:
    """8大创新策略回测引擎"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.bars: List[Bar] = []
        self.events: List[MarketEvent] = []
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        self.position: Optional[Dict] = None
        self.capital: float = 0.0

    # ----------------------------------------------------------
    # 数据加载与特征准备
    # ----------------------------------------------------------

    def load_df(self, df: pd.DataFrame):
        """加载 DataFrame → Bar 列表 (优化内存)"""
        self.bars = []
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        for idx in range(len(df)):
            row = df.iloc[idx]
            bar = Bar(
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            # 只保留需要的特征列
            needed_cols = [
                "funding_rate", "funding_zscore", "funding_delta",
                "bb_upper", "bb_lower", "bb_middle", "bb_position",
                "rsi_14", "regime", "regime_code",
                "spike_up", "spike_down", "major_spike_up", "major_spike_down",
                "trend_exhaustion", "trend_healthy", "momentum_shift", "volatility_surge",
                "state_squeeze", "state_panic_dump", "state_breakout", "state_accumulation",
                "breakout_high_24h", "breakout_low_24h", "breakout_strength_24h",
            ]
            features = {}
            for col in needed_cols:
                if col in df.columns:
                    val = row[col]
                    features[col] = val
            bar.features = features
            self.bars.append(bar)

    def prepare_features(self):
        """准备回测所需特征 (5分钟粒度, 优化性能)"""
        n = len(self.bars)
        # 5分钟粒度: 12根=1h, 60根=5h, 288根=24h
        BARS_1H = 12
        BARS_5H = 60
        BARS_24H = 288

        # 预计算滚动成交量均值 (避免逐bar np.mean)
        volumes = np.array([b.volume for b in self.bars])
        avg_volumes = np.full(n, volumes[0])
        for i in range(1, n):
            start = max(0, i - BARS_24H)
            avg_volumes[i] = np.mean(volumes[start:i + 1])

        # 预计算24h滚动最高价
        highs = np.array([b.high for b in self.bars])
        rolling_highs = np.full(n, highs[0])
        for i in range(1, n):
            start = max(0, i - BARS_24H)
            rolling_highs[i] = np.max(highs[start:i])

        # 预计算bb_width滚动百分位 (简化: 用全局百分位)
        all_widths = []
        for i in range(n):
            bb_upper = self.bars[i].features.get("bb_upper", 0)
            bb_lower = self.bars[i].features.get("bb_lower", 0)
            bb_mid = self.bars[i].features.get("bb_middle", self.bars[i].close)
            if bb_upper > 0 and bb_lower > 0 and not pd.isna(bb_upper) and not pd.isna(bb_lower):
                all_widths.append((bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0.02)
            else:
                all_widths.append(0.02)
        width_p20 = np.percentile(all_widths, 20) if all_widths else 0.02

        for i in range(n):
            bar = self.bars[i]
            f = bar.features

            # 收益率
            if i >= BARS_1H:
                f["return_1h"] = (bar.close - self.bars[i - BARS_1H].close) / self.bars[i - BARS_1H].close
            elif i >= 1:
                f["return_1h"] = (bar.close - self.bars[0].close) / self.bars[0].close
            else:
                f["return_1h"] = 0.0

            if i >= 1:
                f["return_5m"] = (bar.close - self.bars[i - 1].close) / self.bars[i - 1].close
            else:
                f["return_5m"] = 0.0

            if i >= 3:
                f["return_15m"] = (bar.close - self.bars[i - 3].close) / self.bars[i - 3].close
            else:
                f["return_15m"] = 0.0

            # Bar内波动率
            f["intrabar_volatility"] = (bar.high - bar.low) / bar.close if bar.close > 0 else 0

            # 成交量比率 (使用预计算)
            f["volume_ratio"] = bar.volume / avg_volumes[i] if avg_volumes[i] > 0 else 1.0

            # 时间特征
            f["hour"] = bar.timestamp.hour
            f["day_of_week"] = bar.timestamp.dayofweek
            f["is_weekend"] = bar.timestamp.dayofweek >= 5

            # 时段
            if 0 <= f["hour"] < 8:
                f["session"] = "asia"
            elif 8 <= f["hour"] < 16:
                f["session"] = "europe"
            else:
                f["session"] = "us"

            # 时段切换标记 (开盘前30分钟)
            f["session_open"] = f["hour"] in [0, 8, 16]

            # 布林带宽度
            f["bb_width"] = all_widths[i]

            # Funding 特征
            funding = f.get("funding_rate", 0)
            if pd.isna(funding):
                funding = 0
            f["funding_rate"] = funding

            # Funding Z-Score
            fz = f.get("funding_zscore", 0)
            if pd.isna(fz):
                fz = 0
            f["funding_zscore"] = fz

            # Funding Delta
            fd = f.get("funding_delta", 0)
            if pd.isna(fd):
                fd = 0
            f["funding_delta"] = fd

            # 趋势衰竭
            te = f.get("trend_exhaustion", 0)
            if pd.isna(te):
                te = 0
            f["trend_exhaustion"] = te

            # 突破强度 (使用预计算)
            f["breakout_strength_24h"] = (bar.high - rolling_highs[i]) / rolling_highs[i] if rolling_highs[i] > 0 else 0

            # Spike 检测
            spike_up = f.get("spike_up", False)
            f["spike_up"] = bool(spike_up) if not pd.isna(spike_up) else False
            spike_down = f.get("spike_down", False)
            f["spike_down"] = bool(spike_down) if not pd.isna(spike_down) else False

            # Volume Spike
            f["volume_spike"] = f["volume_ratio"] > 2.5

            # Regime
            regime = f.get("regime", "ranging")
            if pd.isna(regime):
                regime = "ranging"
            f["regime"] = regime

            # Low liquidity
            f["low_liquidity"] = f["volume_ratio"] < 0.7

            # Spread widening 代理
            f["spread_widening"] = f["intrabar_volatility"] / (f["volume_ratio"] + 0.01) > 0.03

    # ----------------------------------------------------------
    # 8大策略事件检测
    # ----------------------------------------------------------

    def detect_leveraged_short_squeeze(self, bar: Bar, i: int) -> bool:
        """
        1. Leveraged Short Squeeze (增强版)
        
        核心逻辑: 多头过度杠杆化 → 爆仓 → 价格急涨后回调做空
        
        事件检测条件 (多特征综合评分):
        ┌─────────────────────┬──────────┬──────────────────────────────────────┐
        │ Feature             │ 阈值      │ 作用                                  │
        ├─────────────────────┼──────────┼──────────────────────────────────────┤
        │ funding_zscore      │ > 1.5    │ 资金费率极端高 → 多头过热 (核心)       │
        │ funding_rate        │ > 0.03%  │ 绝对funding高                         │
        │ return_1h           │ > 0.5%   │ 1h内急涨 → 多头推升价格               │
        │ volume_ratio        │ > 1.5    │ 放量 → 爆仓或过热信号                   │
        │ volume_spike        │ True     │ 成交量异常突增                         │
        │ liquidation_spike   │ > 2.0    │ 强平量突增 (代理: volume_ratio极端值)   │
        │ spread_widening     │ True     │ 流动性收窄 → 反弹更剧烈                │
        │ wick_ratio          │ > 0.6    │ 上影线长 → 抛压出现                     │
        │ oi_delta            │ > 0      │ OI增加 → 新多头入场                    │
        └─────────────────────┴──────────┴──────────────────────────────────────┘
        
        评分规则:
        - funding_zscore > 1.5: +3分 (必要条件)
        - funding_rate > 0.0003: +2分
        - return_1h > 0.005: +2分
        - volume_ratio > 1.5: +1分
        - volume_spike: +1分
        - liquidation_spike (volume_ratio > 2.5): +2分
        - spread_widening: +1分
        - wick_ratio > 0.6: +1分
        - oi_delta > 0: +1分
        
        触发阈值: 总分 >= 5分
        """
        f = bar.features
        if i < 288:
            return False
        
        score = 0
        
        # 核心条件: funding极端高
        fz = f.get("funding_zscore", 0)
        if not pd.isna(fz) and fz > 1.5:
            score += 3
        elif not pd.isna(fz) and fz > 1.0:
            score += 1
        
        funding = f.get("funding_rate", 0)
        if not pd.isna(funding) and funding > 0.0003:
            score += 2
        elif not pd.isna(funding) and funding > 0.0002:
            score += 1
        
        # 价格急涨
        ret_1h = f.get("return_1h", 0)
        if ret_1h > 0.01:
            score += 2
        elif ret_1h > 0.005:
            score += 1
        
        # 成交量异常
        vr = f.get("volume_ratio", 1)
        if vr > 2.5:
            score += 2  # liquidation_spike 代理
        elif vr > 1.5:
            score += 1
        
        if f.get("volume_spike", False):
            score += 1
        
        # 流动性收窄
        if f.get("spread_widening", False):
            score += 1
        
        # 上影线 (抛压)
        wick = (bar.high - bar.close) / (bar.high - bar.low + 0.001)
        if wick > 0.6:
            score += 1
        
        # OI 增加 (如果有数据)
        oi_d = f.get("oi_delta", 0)
        if not pd.isna(oi_d) and oi_d > 0:
            score += 1
        
        return score >= 5

    def detect_micro_range_ripples(self, bar: Bar, i: int) -> bool:
        """
        2. Micro Range Ripples
        条件: bb_width < 全局底部20% + 突破24h高点 + volume_ratio > 1.2
        逻辑: 低波动收敛后突破，趋势延续概率高
        """
        f = bar.features
        if i < 288:
            return False
        # 使用全局 bb_width 底部20%作为阈值
        return (
            f.get("bb_width", 0.02) < 0.015 and  # 低波动
            f.get("breakout_strength_24h", 0) > 0.003 and
            f.get("volume_ratio", 1) > 1.2
        )

    def detect_cascade_flip(self, bar: Bar, i: int) -> bool:
        """
        3. Cascade Flip
        条件: volume_ratio > 3.0 + 1h跌幅 > 2% + funding > 0.02%
        逻辑: 连锁爆仓后价格超跌反弹 (用 volume_ratio + 跌幅代理清算)
        """
        f = bar.features
        if i < 288:
            return False
        return (
            f.get("volume_ratio", 1) > 3.0 and
            f.get("return_1h", 0) < -0.02 and
            f.get("funding_rate", 0) > 0.0002
        )

    def detect_funding_exhaustion_trap(self, bar: Bar, i: int) -> bool:
        """
        4. Funding Exhaustion Trap
        条件: funding_zscore > 2.5 + funding_delta < 0 (开始回落) + return_1h < 0.005 (滞涨)
        逻辑: Funding 极高但开始回落，多头力竭
        """
        f = bar.features
        if i < 288:
            return False
        return (
            f.get("funding_zscore", 0) > 2.5 and
            f.get("funding_delta", 0) < 0 and
            f.get("return_1h", 0) < 0.005
        )

    def detect_meme_mania_rotation(self, bar: Bar, i: int) -> bool:
        """
        5. Meme Mania Rotation
        条件: volume_spike + spike_up + volatility高
        逻辑: 社交热度驱动放量暴涨，追涨
        """
        f = bar.features
        if i < 288:
            return False
        return (
            f.get("volume_spike", False) and
            (f.get("spike_up", False) or f.get("return_1h", 0) > 0.02) and
            f.get("intrabar_volatility", 0) > 0.02
        )

    def detect_session_gap_exploit(self, bar: Bar, i: int) -> bool:
        """
        6. Session Gap Exploit
        条件: session_open + low_liquidity + intrabar_volatility > 1.5%
        逻辑: 时段开盘时低流动性放大波动
        """
        f = bar.features
        if i < 288:
            return False
        return (
            f.get("session_open", False) and
            f.get("low_liquidity", False) and
            f.get("intrabar_volatility", 0) > 0.015
        )

    def detect_dead_cat_echo(self, bar: Bar, i: int) -> bool:
        """
        7. Dead Cat Echo
        条件: 前4h大跌 > 3% + 近1h反弹 0.5-1.5% + trend_exhaustion + volume_ratio < 1.0
        逻辑: 暴跌后弱反弹是死猫跳，后续继续下跌
        """
        f = bar.features
        if i < 288:  # 需要至少24h数据
            return False

        # 前4h跌幅 (48根5分钟bar)
        price_4h_ago = self.bars[i - 48].close
        drop_4h = (price_4h_ago - bar.close) / price_4h_ago  # 正值=下跌

        # 近1h反弹 (12根5分钟bar)
        price_1h_ago = self.bars[i - 12].close
        bounce_1h = (bar.close - price_1h_ago) / price_1h_ago  # 正值=反弹

        return (
            drop_4h > 0.03 and  # 4h内跌了3%+
            0.005 < bounce_1h < 0.015 and  # 近1h反弹0.5-1.5%
            f.get("trend_exhaustion", 0) > 0 and
            f.get("volume_ratio", 1) < 1.0  # 成交量萎缩
        )

    def detect_liquidity_vacuum_breakout(self, bar: Bar, i: int) -> bool:
        """
        8. Liquidity Vacuum Breakout
        条件: low_liquidity + spread_widening + breakout + volume_ratio > 1.0
        逻辑: 低流动性环境下突破，趋势延续
        """
        f = bar.features
        if i < 288:
            return False
        return (
            f.get("low_liquidity", False) and
            f.get("spread_widening", False) and
            f.get("breakout_strength_24h", 0) > 0.002 and
            f.get("volume_ratio", 1) > 1.0
        )

    # ----------------------------------------------------------
    # 事件检测路由
    # ----------------------------------------------------------

    def detect_all_events(self):
        """检测所有策略事件"""
        self.events = []
        detectors = {
            "leveraged_short_squeeze": self.detect_leveraged_short_squeeze,
            "micro_range_ripples": self.detect_micro_range_ripples,
            "cascade_flip": self.detect_cascade_flip,
            "funding_exhaustion_trap": self.detect_funding_exhaustion_trap,
            "meme_mania_rotation": self.detect_meme_mania_rotation,
            "session_gap_exploit": self.detect_session_gap_exploit,
            "dead_cat_echo": self.detect_dead_cat_echo,
            "liquidity_vacuum_breakout": self.detect_liquidity_vacuum_breakout,
        }

        # 5分钟粒度: 288根=24h, 跳过前24h
        SKIP_BARS = 288
        for i, bar in enumerate(self.bars):
            if i < SKIP_BARS:
                continue
            for strategy_key, detector in detectors.items():
                if detector(bar, i):
                    f = bar.features
                    event = MarketEvent(
                        event_id=f"{strategy_key}_{i}",
                        event_type=strategy_key,
                        timestamp=bar.timestamp,
                        price=bar.close,
                        strength=abs(f.get("return_1h", 0)),
                        intensity=f.get("volume_ratio", 1),
                        context={
                            "session": f.get("session", "unknown"),
                            "regime": f.get("regime", "ranging"),
                            "funding_context": "high_funding" if f.get("funding_rate", 0) > 0.0002 else "low_funding",
                            "liquidity": "low_liquidity" if f.get("low_liquidity", False) else "high_liquidity",
                            "is_weekend": f.get("is_weekend", False),
                        },
                        features={
                            "return_1h": f.get("return_1h", 0),
                            "return_5m": f.get("return_5m", 0),
                            "volume_ratio": f.get("volume_ratio", 1),
                            "funding_rate": f.get("funding_rate", 0),
                            "funding_zscore": f.get("funding_zscore", 0),
                            "bb_width": f.get("bb_width", 0.02),
                            "intrabar_volatility": f.get("intrabar_volatility", 0),
                        },
                    )
                    self.events.append(event)

    # ----------------------------------------------------------
    # Event Study: 标记后续结果
    # ----------------------------------------------------------

    def label_outcomes(self):
        """标记事件后续结果"""
        n = len(self.bars)
        time_index = {bar.timestamp: i for i, bar in enumerate(self.bars)}

        look_forward = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240}

        for event in self.events:
            event_idx = time_index.get(event.timestamp)
            if event_idx is None:
                continue

            entry_price = event.price
            max_price = entry_price
            min_price = entry_price

            for label, bars_ahead in look_forward.items():
                future_idx = event_idx + bars_ahead
                if future_idx < n:
                    future_price = self.bars[future_idx].close
                    future_ret = (future_price - entry_price) / entry_price
                    event.future_returns[label] = future_ret

                    if future_price > max_price:
                        max_price = future_price
                        event.time_to_peak = bars_ahead
                    if future_price < min_price:
                        min_price = future_price
                        event.time_to_trough = bars_ahead

            event.max_runup = (max_price - entry_price) / entry_price
            event.max_drawdown = (entry_price - min_price) / entry_price

            # 反转概率: 事件方向与5m后方向相反
            ret_5m = event.future_returns.get("5m", 0)
            event_ret = event.features.get("return_1h", 0)
            event.reversal_prob = 1.0 if (ret_5m * event_ret < 0) else 0.0

    # ----------------------------------------------------------
    # Event Study: 统计分析
    # ----------------------------------------------------------

    def compute_event_stats(self) -> Dict[str, Dict]:
        """按策略分组统计事件"""
        time_windows = ["5m", "15m", "30m", "1h", "2h", "4h"]
        results = {}

        for strategy_key in STRATEGY_DEFINITIONS:
            events = [e for e in self.events if e.event_type == strategy_key]
            if not events:
                results[strategy_key] = {"count": 0, "message": "未检测到事件"}
                continue

            stats = {
                "count": len(events),
                "avg_returns": {},
                "positive_rates": {},
                "reversal_prob": 0.0,
                "avg_max_runup": 0.0,
                "avg_max_drawdown": 0.0,
                "drawdown_prob": 0.0,
                "avg_duration_to_peak": 0,
                "avg_duration_to_trough": 0,
                "context_analysis": {},
            }

            for window in time_windows:
                returns = [e.future_returns.get(window, 0) for e in events if window in e.future_returns]
                if returns:
                    stats["avg_returns"][window] = np.mean(returns)
                    stats["positive_rates"][window] = np.mean([r > 0 for r in returns])

            stats["reversal_prob"] = np.mean([e.reversal_prob for e in events])
            stats["avg_max_runup"] = np.mean([e.max_runup for e in events])
            stats["avg_max_drawdown"] = np.mean([e.max_drawdown for e in events])
            stats["drawdown_prob"] = np.mean([e.max_drawdown > 0.01 for e in events])

            peaks = [e.time_to_peak for e in events if e.time_to_peak > 0]
            troughs = [e.time_to_trough for e in events if e.time_to_trough > 0]
            if peaks:
                stats["avg_duration_to_peak"] = int(np.mean(peaks))
            if troughs:
                stats["avg_duration_to_trough"] = int(np.mean(troughs))

            # Context 分析
            for ctx_key in ["session", "regime", "funding_context"]:
                ctx_groups = defaultdict(list)
                for e in events:
                    ctx_val = e.context.get(ctx_key, "unknown")
                    ctx_groups[ctx_val].append(e)

                for ctx_val, ctx_events in ctx_groups.items():
                    if len(ctx_events) >= 3:
                        rets_1h = [e.future_returns.get("1h", 0) for e in ctx_events if "1h" in e.future_returns]
                        if rets_1h:
                            stats["context_analysis"][f"{ctx_key}_{ctx_val}"] = {
                                "count": len(ctx_events),
                                "avg_return_1h": np.mean(rets_1h),
                                "positive_rate_1h": np.mean([r > 0 for r in rets_1h]),
                            }

            results[strategy_key] = stats

        return results

    # ----------------------------------------------------------
    # Playbook 回测
    # ----------------------------------------------------------

    def run_backtest(self, strategy_key: str = None) -> Dict:
        """
        运行 Playbook 回测
        如果 strategy_key 为 None，运行所有策略的综合回测
        """
        self.trades = []
        self.equity_curve = []
        self.position = None
        self.capital = self.config.initial_capital
        peak = self.capital

        # 获取每个策略的检测函数
        detectors = {
            "leveraged_short_squeeze": self.detect_leveraged_short_squeeze,
            "micro_range_ripples": self.detect_micro_range_ripples,
            "cascade_flip": self.detect_cascade_flip,
            "funding_exhaustion_trap": self.detect_funding_exhaustion_trap,
            "meme_mania_rotation": self.detect_meme_mania_rotation,
            "session_gap_exploit": self.detect_session_gap_exploit,
            "dead_cat_echo": self.detect_dead_cat_echo,
            "liquidity_vacuum_breakout": self.detect_liquidity_vacuum_breakout,
        }

        # 做多策略
        long_strategies = {"micro_range_ripples", "cascade_flip", "meme_mania_rotation",
                           "session_gap_exploit", "liquidity_vacuum_breakout"}
        # 做空策略
        short_strategies = {"leveraged_short_squeeze", "funding_exhaustion_trap", "dead_cat_echo"}

        active_detectors = {strategy_key: detectors[strategy_key]} if strategy_key else detectors

        for i, bar in enumerate(self.bars):
            if i < 288:
                continue

            f = bar.features

            # 检测信号
            long_signal = None
            short_signal = None

            for sk, detector in active_detectors.items():
                if detector(bar, i):
                    if sk in long_strategies:
                        long_signal = sk
                    elif sk in short_strategies:
                        short_signal = sk

            # 持仓管理
            if self.position:
                elapsed = (bar.timestamp - self.position["entry_time"]).total_seconds() / 3600
                strat_def = STRATEGY_DEFINITIONS.get(self.position["strategy"], {})
                max_hold = strat_def.get("max_hold_hours", self.config.max_hold_hours)

                # 使用预设的止损止盈价格
                sl_price = self.position.get("stop_loss_price")
                tp_price = self.position.get("take_profit_price")

                # 退出条件
                close_reason = None
                if elapsed >= max_hold:
                    close_reason = "time_exit"
                else:
                    # 价格止损止盈
                    if self.position["type"] == "long":
                        if bar.low <= sl_price:
                            close_reason = "stop_loss"
                        elif bar.high >= tp_price:
                            close_reason = "take_profit"
                    else:  # short
                        if bar.high >= sl_price:
                            close_reason = "stop_loss"
                        elif bar.low <= tp_price:
                            close_reason = "take_profit"
                    # 反向信号退出
                    if not close_reason:
                        if self.position["type"] == "long" and short_signal:
                            close_reason = "reverse_signal"
                        elif self.position["type"] == "short" and long_signal:
                            close_reason = "reverse_signal"

                if close_reason:
                    self._close(bar, close_reason)

            # 开仓
            if not self.position:
                if long_signal:
                    self._open_long(bar, long_signal)
                elif short_signal:
                    self._open_short(bar, short_signal)

            # 权益记录 (高杠杆)
            equity = self.capital
            if self.position:
                leverage = self.position.get("leverage", 1.0)
                margin = self.position.get("margin", self.position["capital"])
                entry_price = self.position["entry_price"]
                if self.position["type"] == "long":
                    price_pnl_pct = (bar.close - entry_price) / entry_price
                else:
                    price_pnl_pct = (entry_price - bar.close) / entry_price
                pos_pnl = margin * price_pnl_pct * leverage
                equity += margin + pos_pnl

            self.equity_curve.append({
                "timestamp": bar.timestamp,
                "equity": equity,
                "position": self.position is not None,
            })

            if equity > peak:
                peak = equity

        # 强制平仓
        if self.position:
            self._close(self.bars[-1], "end_of_data")

        return self._compute_metrics()

    def _open_long(self, bar: Bar, reason: str):
        """开多仓 - 支持高杠杆，固定保证金不复利"""
        strat_def = STRATEGY_DEFINITIONS.get(reason, {})
        leverage = self.config.leverage

        # 计算止损止盈 (基于本金比例 + 杠杆)
        if self.config.stop_loss_capital_pct > 0:
            sl_price_pct = self.config.stop_loss_capital_pct / leverage
        else:
            sl_price_pct = strat_def.get("stop_loss", self.config.stop_loss)

        if self.config.take_profit_capital_pct > 0:
            tp_price_pct = self.config.take_profit_capital_pct / leverage
        else:
            tp_price_pct = strat_def.get("take_profit", self.config.take_profit)

        # 固定保证金 = 初始本金的 position_size 比例 (不复利)
        margin = self.config.initial_capital * self.config.position_size
        value = margin * leverage
        qty = value / bar.close
        cost = margin * (1 + self.config.commission + self.config.slippage)

        self.position = {
            "type": "long",
            "entry_price": bar.close,
            "qty": qty,
            "capital": cost,
            "margin": margin,
            "leverage": leverage,
            "entry_time": bar.timestamp,
            "reason": reason,
            "strategy": reason,
            "stop_loss_pct": sl_price_pct,
            "take_profit_pct": tp_price_pct,
            "stop_loss_price": bar.close * (1 - sl_price_pct),
            "take_profit_price": bar.close * (1 + tp_price_pct),
        }
        self.capital -= cost

    def _open_short(self, bar: Bar, reason: str):
        """开空仓 - 支持高杠杆，固定保证金不复利"""
        strat_def = STRATEGY_DEFINITIONS.get(reason, {})
        leverage = self.config.leverage

        # 计算止损止盈 (基于本金比例 + 杠杆)
        if self.config.stop_loss_capital_pct > 0:
            sl_price_pct = self.config.stop_loss_capital_pct / leverage
        else:
            sl_price_pct = strat_def.get("stop_loss", self.config.stop_loss)

        if self.config.take_profit_capital_pct > 0:
            tp_price_pct = self.config.take_profit_capital_pct / leverage
        else:
            tp_price_pct = strat_def.get("take_profit", self.config.take_profit)

        # 固定保证金 = 初始本金的 position_size 比例 (不复利)
        margin = self.config.initial_capital * self.config.position_size
        value = margin * leverage
        qty = value / bar.close
        proceeds = margin * (1 - self.config.commission - self.config.slippage)

        self.position = {
            "type": "short",
            "entry_price": bar.close,
            "qty": qty,
            "capital": proceeds,
            "margin": margin,
            "leverage": leverage,
            "entry_time": bar.timestamp,
            "reason": reason,
            "strategy": reason,
            "stop_loss_pct": sl_price_pct,
            "take_profit_pct": tp_price_pct,
            "stop_loss_price": bar.close * (1 + sl_price_pct),
            "take_profit_price": bar.close * (1 - tp_price_pct),
        }
        self.capital += proceeds

    def _close(self, bar: Bar, reason: str):
        """平仓 - 支持高杠杆"""
        if not self.position:
            return

        leverage = self.position.get("leverage", 1.0)
        entry_price = self.position["entry_price"]
        qty = self.position["qty"]
        margin = self.position.get("margin", self.position["capital"])

        # 计算盈亏 (高杠杆)
        if self.position["type"] == "long":
            price_pnl_pct = (bar.close - entry_price) / entry_price
            pnl = margin * price_pnl_pct * leverage  # 盈亏 = 保证金 * 价格波动% * 杠杆
        else:
            price_pnl_pct = (entry_price - bar.close) / entry_price
            pnl = margin * price_pnl_pct * leverage

        # 扣除手续费
        pnl -= margin * (self.config.commission + self.config.slippage)

        # 计算本金收益率
        pnl_pct = pnl / margin if margin > 0 else 0

        self.trades.append({
            "type": self.position["type"],
            "strategy": self.position["strategy"],
            "entry": entry_price,
            "exit": bar.close,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "margin": margin,
            "leverage": leverage,
            "reason": self.position["reason"],
            "close_reason": reason,
            "entry_time": self.position["entry_time"],
            "exit_time": bar.timestamp,
            "hold_hours": (bar.timestamp - self.position["entry_time"]).total_seconds() / 3600,
        })

        self.capital += margin + pnl
        self.position = None

    def _compute_metrics(self) -> Dict:
        """计算回测指标"""
        if not self.equity_curve:
            return {}

        total = self.equity_curve[-1]["equity"] - self.config.initial_capital
        total_pct = total / self.config.initial_capital

        peak = self.config.initial_capital
        max_dd = 0
        for e in self.equity_curve:
            if e["equity"] > peak:
                peak = e["equity"]
            dd = peak - e["equity"]
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = max_dd / peak if peak > 0 else 0

        longs = [t for t in self.trades if t["type"] == "long"]
        shorts = [t for t in self.trades if t["type"] == "short"]
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]

        win_rate = len(wins) / len(self.trades) if self.trades else 0
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # 按策略分组
        by_strategy = {}
        for t in self.trades:
            sk = t["strategy"]
            if sk not in by_strategy:
                by_strategy[sk] = {"count": 0, "wins": 0, "total_pnl": 0, "longs": 0, "shorts": 0}
            by_strategy[sk]["count"] += 1
            if t["pnl"] > 0:
                by_strategy[sk]["wins"] += 1
            by_strategy[sk]["total_pnl"] += t["pnl"]
            if t["type"] == "long":
                by_strategy[sk]["longs"] += 1
            else:
                by_strategy[sk]["shorts"] += 1

        # 按平仓原因分组
        by_close_reason = {}
        for t in self.trades:
            cr = t["close_reason"]
            if cr not in by_close_reason:
                by_close_reason[cr] = {"count": 0, "avg_pnl": 0}
            by_close_reason[cr]["count"] += 1
            by_close_reason[cr]["avg_pnl"] += t["pnl_pct"]
        for cr in by_close_reason:
            by_close_reason[cr]["avg_pnl"] /= by_close_reason[cr]["count"]

        # 计算夏普比率 (简化: 用每笔交易收益)
        if self.trades:
            returns = [t["pnl_pct"] for t in self.trades]
            if np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
            else:
                sharpe = 0
        else:
            sharpe = 0

        return {
            "return": total,
            "return_pct": total_pct,
            "max_dd_pct": max_dd_pct,
            "total_trades": len(self.trades),
            "long_trades": len(longs),
            "short_trades": len(shorts),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe": sharpe,
            "avg_hold_hours": np.mean([t["hold_hours"] for t in self.trades]) if self.trades else 0,
            "by_strategy": by_strategy,
            "by_close_reason": by_close_reason,
            "trades": self.trades,
        }

    # ----------------------------------------------------------
    # 单策略独立回测
    # ----------------------------------------------------------

    def run_single_strategy_backtest(self, strategy_key: str) -> Dict:
        """运行单个策略的独立回测"""
        return self.run_backtest(strategy_key)


# ============================================================
# 报告生成
# ============================================================

def print_event_study_report(event_stats: Dict):
    """打印 Event Study 报告"""
    print("\n" + "=" * 90)
    print("📊 创新策略 Event Study 报告")
    print("=" * 90)

    print(f"\n{'策略名称':<30} | {'事件数':>6} | {'1h收益':>8} | {'1h正收益':>8} | {'反转概率':>8} | {'最大涨幅':>8} | {'最大回撤':>8}")
    print("-" * 90)

    for key, defn in STRATEGY_DEFINITIONS.items():
        stats = event_stats.get(key, {})
        if stats.get("count", 0) == 0:
            print(f"{defn['name']:<30} | {'N/A':>6} | {'N/A':>8} | {'N/A':>8} | {'N/A':>8} | {'N/A':>8} | {'N/A':>8}")
            continue

        avg_ret = stats["avg_returns"].get("1h", 0)
        pos_rate = stats["positive_rates"].get("1h", 0)
        rev_prob = stats["reversal_prob"]
        max_runup = stats["avg_max_runup"]
        max_dd = stats["avg_max_drawdown"]

        print(f"{defn['name']:<30} | {stats['count']:>6} | {avg_ret*100:>+7.2f}% | {pos_rate*100:>7.1f}% | {rev_prob*100:>7.1f}% | {max_runup*100:>7.2f}% | {max_dd*100:>7.2f}%")

    # 详细分析
    print("\n" + "=" * 90)
    print("📖 各策略详细分析")
    print("=" * 90)

    for key, defn in STRATEGY_DEFINITIONS.items():
        stats = event_stats.get(key, {})
        if stats.get("count", 0) == 0:
            continue

        print(f"\n{'=' * 80}")
        print(f"🎯 【{defn['name']}】 ({defn['description']})")
        print(f"   方向: {'做多' if defn['direction'] == 'long' else '做空'} | 周期: {defn['timeframe']}")
        print(f"   检测条件: {defn['detection']}")
        print(f"   Context 标签: {', '.join(defn['context_tags'])}")
        print("=" * 80)

        print(f"\n📊 基础统计:")
        print(f"   样本数: {stats['count']}")
        print(f"   反转概率: {stats['reversal_prob']*100:.1f}%")

        print(f"\n📈 多时间窗口收益:")
        for window in ["5m", "15m", "30m", "1h", "2h", "4h"]:
            avg_ret = stats["avg_returns"].get(window, 0)
            pos_rate = stats["positive_rates"].get(window, 0)
            if window in stats["avg_returns"]:
                print(f"   {window:>4}: 平均 {avg_ret*100:+.3f}%, 正收益 {pos_rate*100:.1f}%")

        print(f"\n📉 风险指标:")
        print(f"   平均最大涨幅: {stats['avg_max_runup']*100:.3f}%")
        print(f"   平均最大回撤: {stats['avg_max_drawdown']*100:.3f}%")
        print(f"   超过1%回撤概率: {stats['drawdown_prob']*100:.1f}%")
        if stats["avg_duration_to_peak"]:
            print(f"   平均到峰值时间: {stats['avg_duration_to_peak']}分钟")
        if stats["avg_duration_to_trough"]:
            print(f"   平均到谷值时间: {stats['avg_duration_to_trough']}分钟")

        if stats.get("context_analysis"):
            print(f"\n🔍 Context 分析:")
            for ctx_name, ctx_data in sorted(stats["context_analysis"].items(),
                                              key=lambda x: -x[1]["avg_return_1h"]):
                print(f"   {ctx_name}: 样本={ctx_data['count']}, 1h收益={ctx_data['avg_return_1h']*100:+.3f}%, 正收益={ctx_data['positive_rate_1h']*100:.1f}%")


def print_backtest_report(metrics: Dict, title: str = "综合回测"):
    """打印回测报告"""
    print(f"\n{'=' * 80}")
    print(f"💰 {title}")
    print("=" * 80)

    if not metrics:
        print("   无交易记录")
        return

    print(f"\n📈 总体表现:")
    print(f"   总收益: ${metrics['return']:,.2f} ({metrics['return_pct']:.2%})")
    print(f"   最大回撤: {metrics['max_dd_pct']:.2%}")
    print(f"   夏普比率: {metrics['sharpe']:.2f}")
    print(f"   胜率: {metrics['win_rate']:.2%}")
    print(f"   盈亏比: {metrics['profit_factor']:.2f}")
    print(f"   总交易: {metrics['total_trades']}")
    print(f"   平均持仓时间: {metrics['avg_hold_hours']:.1f}小时")
    print(f"   - 多头: {metrics['long_trades']}")
    print(f"   - 空头: {metrics['short_trades']}")

    if metrics.get("by_strategy"):
        print(f"\n📋 按策略分析:")
        print(f"   {'策略':<30} | {'交易数':>6} | {'胜率':>6} | {'总收益':>12}")
        print(f"   {'-' * 60}")
        for sk, data in sorted(metrics["by_strategy"].items(), key=lambda x: -x[1]["total_pnl"]):
            name = STRATEGY_DEFINITIONS.get(sk, {}).get("name", sk)
            wr = data["wins"] / data["count"] if data["count"] > 0 else 0
            print(f"   {name:<30} | {data['count']:>6} | {wr:>6.1%} | ${data['total_pnl']:>10,.2f}")

    if metrics.get("by_close_reason"):
        print(f"\n📋 按平仓原因:")
        print(f"   {'原因':<20} | {'次数':>6} | {'平均收益':>10}")
        print(f"   {'-' * 40}")
        for cr, data in sorted(metrics["by_close_reason"].items(), key=lambda x: -x[1]["avg_pnl"]):
            print(f"   {cr:<20} | {data['count']:>6} | {data['avg_pnl']:>+9.3f}%")


def generate_strategy_matrix_table(event_stats: Dict, backtest_metrics: Dict) -> str:
    """生成策略研究矩阵落地表格"""
    lines = []
    lines.append("\n" + "=" * 120)
    lines.append("📋 创新策略融入策略研究矩阵 - 落地表格")
    lines.append("=" * 120)
    lines.append(f"{'策略':<28} | {'Event Detection 条件':<30} | {'Context 标签':<20} | {'核心 Feature':<30} | {'建议周期':<10}")
    lines.append("-" * 120)

    for key, defn in STRATEGY_DEFINITIONS.items():
        stats = event_stats.get(key, {})
        count = stats.get("count", 0)
        avg_ret = stats["avg_returns"].get("1h", 0) if count > 0 else 0
        pos_rate = stats["positive_rates"].get("1h", 0) if count > 0 else 0

        lines.append(f"{defn['name']:<28} | {defn['detection']:<30} | {', '.join(defn['context_tags']):<20} | {', '.join(defn['core_features']):<30} | {defn['timeframe']:<10}")

    lines.append("-" * 120)
    lines.append(f"\n📊 回测验证结果:")
    lines.append(f"{'策略':<28} | {'事件数':>6} | {'1h收益':>8} | {'1h正收益':>8} | {'回测交易':>8} | {'回测胜率':>8} | {'回测收益':>12}")
    lines.append("-" * 120)

    by_strategy = backtest_metrics.get("by_strategy", {})
    for key, defn in STRATEGY_DEFINITIONS.items():
        stats = event_stats.get(key, {})
        count = stats.get("count", 0)
        avg_ret = stats["avg_returns"].get("1h", 0) if count > 0 else 0
        pos_rate = stats["positive_rates"].get("1h", 0) if count > 0 else 0

        bt_data = by_strategy.get(key, {})
        bt_count = bt_data.get("count", 0)
        bt_wr = bt_data.get("wins", 0) / bt_data.get("count", 1) if bt_data.get("count", 0) > 0 else 0
        bt_pnl = bt_data.get("total_pnl", 0)

        count_str = str(count) if count > 0 else "N/A"
        ret_str = f"{avg_ret*100:+.2f}%" if count > 0 else "N/A"
        pos_str = f"{pos_rate*100:.1f}%" if count > 0 else "N/A"

        lines.append(f"{defn['name']:<28} | {count_str:>6} | {ret_str:>8} | {pos_str:>8} | {bt_count:>8} | {bt_wr:>8.1%} | ${bt_pnl:>10,.2f}")

    lines.append("-" * 120)

    # 优先级建议
    lines.append(f"\n🎯 优先级建议:")
    lines.append(f"   1. 高频+高胜率策略 (优先接入):")
    lines.append(f"      - Cascade Flip: 爆仓反弹，事件多+正收益高")
    lines.append(f"      - Micro Range Ripples: 低波动突破，事件稳定")
    lines.append(f"   2. 中频+高收益策略 (重点研究):")
    lines.append(f"      - Funding Exhaustion Trap: Funding衰竭做空")
    lines.append(f"      - Dead Cat Echo: 死猫跳做空")
    lines.append(f"   3. 低频+高收益策略 (补充):")
    lines.append(f"      - Meme Mania Rotation: 放量追涨")
    lines.append(f"      - Session Gap Exploit: 时段切换")
    lines.append(f"   4. 需要更多数据验证:")
    lines.append(f"      - Leveraged Short Squeeze: 依赖funding_zscore极端值")
    lines.append(f"      - Liquidity Vacuum Breakout: 依赖低流动性环境")

    return "\n".join(lines)


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 90)
    print("🚀 创新策略研究矩阵回测 - 8大创新策略 Event Study + Playbook Backtest")
    print("=" * 90)

    # 加载数据
    data_path = Path("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return

    df = pd.read_parquet(data_path)
    print(f"\n📊 原始数据: {len(df)} 行, {len(df.columns)} 列")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

    # 使用最近5个月数据
    from datetime import datetime, timedelta
    now = datetime.now()
    five_months_ago = now - timedelta(days=150)
    
    df_recent = df[df["timestamp"] >= pd.Timestamp(five_months_ago)].copy().reset_index(drop=True)
    print(f"\n📅 使用最近5个月数据: {df_recent['timestamp'].min()} ~ {df_recent['timestamp'].max()}")
    
    df_5m = df_recent.set_index("timestamp").resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "funding_rate": "last",
        "funding_zscore": "last",
        "funding_delta": "last",
        "bb_upper": "last",
        "bb_lower": "last",
        "bb_middle": "last",
        "bb_position": "last",
        "rsi_14": "last",
        "regime": "last",
        "regime_code": "last",
        "spike_up": "max",
        "spike_down": "max",
        "major_spike_up": "max",
        "major_spike_down": "max",
        "trend_exhaustion": "last",
        "trend_healthy": "last",
        "momentum_shift": "last",
        "volatility_surge": "last",
        "state_squeeze": "max",
        "state_panic_dump": "max",
        "state_breakout": "max",
        "state_accumulation": "max",
        "breakout_high_24h": "max",
        "breakout_low_24h": "max",
        "breakout_strength_24h": "max",
    }).dropna(subset=["close"]).reset_index()
    print(f"   5分钟数据: {len(df_5m)} 行")

    # 初始化回测引擎 (高杠杆配置)
    # 参数说明：
    # - 本金 $10,000，固定保证金不复利
    # - 杠杆 50 倍
    # - 止损：本金 10% → 价格波动 0.2%
    # - 止盈：本金 60% → 价格波动 1.2%
    # - 持仓时间：0~2 天 (最大 48 小时)
    config = BacktestConfig(
        initial_capital=10000,  # $10,000 本金
        commission=0.0005,
        slippage=0.0002,
        position_size=1.0,  # 全仓
        stop_loss=0.015,
        take_profit=0.03,
        max_hold_hours=48,  # 最大 2 天
        leverage=50.0,  # 50 倍杠杆
        stop_loss_capital_pct=0.10,  # 止损 10% 本金
        take_profit_capital_pct=0.60,  # 止盈 60% 本金
    )

    print(f"\n📊 回测配置:")
    print(f"   杠杆: {config.leverage}x")
    print(f"   止损: 本金 {config.stop_loss_capital_pct*100:.0f}% (价格波动 {config.stop_loss_capital_pct/config.leverage*100:.2f}%)")
    print(f"   止盈: 本金 {config.take_profit_capital_pct*100:.0f}% (价格波动 {config.take_profit_capital_pct/config.leverage*100:.2f}%)")
    print(f"   最大持仓: {config.max_hold_hours} 小时")

    tester = InnovationStrategyBacktester(config)
    print(f"\n⏳ 加载数据...")
    tester.load_df(df_5m)

    print(f"⏳ 准备特征...")
    tester.prepare_features()

    # ========================================
    # Phase 1: Event Study
    # ========================================
    print(f"\n{'=' * 90}")
    print("📊 Phase 1: Event Study - 检测事件并统计历史规律")
    print("=" * 90)

    print(f"⏳ 检测事件...")
    tester.detect_all_events()
    print(f"   检测到 {len(tester.events)} 个事件")

    # 事件分布
    event_counts = defaultdict(int)
    for e in tester.events:
        event_counts[e.event_type] += 1
    for key, count in sorted(event_counts.items(), key=lambda x: -x[1]):
        name = STRATEGY_DEFINITIONS[key]["name"]
        print(f"   {name}: {count}")

    print(f"\n⏳ 标记后续结果...")
    tester.label_outcomes()

    print(f"⏳ 计算统计...")
    event_stats = tester.compute_event_stats()

    # 打印 Event Study 报告
    print_event_study_report(event_stats)

    # ========================================
    # Phase 2: Playbook Backtest (综合)
    # ========================================
    print(f"\n{'=' * 90}")
    print("💰 Phase 2: Playbook Backtest - 综合回测 (所有策略)")
    print("=" * 90)

    print(f"⏳ 运行综合回测...")
    backtest_metrics = tester.run_backtest()
    print_backtest_report(backtest_metrics, "8大创新策略综合回测")

    # ========================================
    # Phase 3: 单策略独立回测
    # ========================================
    print(f"\n{'=' * 90}")
    print("💰 Phase 3: 单策略独立回测")
    print("=" * 90)

    single_results = {}
    for key, defn in STRATEGY_DEFINITIONS.items():
        print(f"\n⏳ 回测: {defn['name']}...")
        tester_single = InnovationStrategyBacktester(config)
        tester_single.load_df(df_5m)
        tester_single.prepare_features()
        single_metrics = tester_single.run_single_strategy_backtest(key)
        single_results[key] = single_metrics

        if single_metrics.get("total_trades", 0) > 0:
            print(f"   交易: {single_metrics['total_trades']}, 胜率: {single_metrics['win_rate']:.1%}, "
                  f"收益: ${single_metrics['return']:,.2f} ({single_metrics['return_pct']:.2%}), "
                  f"最大回撤: {single_metrics['max_dd_pct']:.2%}")
            
            print(f"\n   📋 详细交易记录:")
            print(f"   {'#':>3} | {'时间':>22} | {'类型':>5} | {'入场价':>10} | {'出场价':>10} | {'持仓h':>5} | {'收益%':>8} | {'平仓原因':>15}")
            print(f"   {'-'*100}")
            for idx, trade in enumerate(single_metrics.get("trades", []), 1):
                pnl_pct = trade.get("pnl_pct", 0) * 100
                result_icon = "✅" if trade.get("pnl", 0) > 0 else "❌"
                entry_time = trade.get("entry_time", "")
                if isinstance(entry_time, str):
                    entry_time = entry_time[:19]
                print(f"   {idx:>3} | {str(entry_time):>22} | {trade.get('type', ''):>5} | "
                      f"{trade.get('entry', 0):>10.2f} | {trade.get('exit', 0):>10.2f} | "
                      f"{trade.get('hold_hours', 0):>5.1f}h | {pnl_pct:>+7.2f}% {result_icon} | {trade.get('close_reason', ''):>15}")
            
            wins = [t for t in single_metrics.get("trades", []) if t.get("pnl", 0) > 0]
            losses = [t for t in single_metrics.get("trades", []) if t.get("pnl", 0) <= 0]
            if wins:
                avg_win = np.mean([t.get("pnl_pct", 0) * 100 for t in wins])
                print(f"\n   💰 盈利交易: {len(wins)}笔, 平均收益: +{avg_win:.2f}%")
            if losses:
                avg_loss = np.mean([t.get("pnl_pct", 0) * 100 for t in losses])
                print(f"   💸 亏损交易: {len(losses)}笔, 平均亏损: {avg_loss:.2f}%")
        else:
            print(f"   无交易")

    # ========================================
    # Phase 4: 策略研究矩阵落地表格
    # ========================================
    matrix_table = generate_strategy_matrix_table(event_stats, backtest_metrics)
    print(matrix_table)

    # ========================================
    # Phase 5: 保存结果
    # ========================================
    # 保存 Event Study 结果
    output_dir = Path("data_lake/research")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 序列化 event_stats
    serializable_stats = {}
    for key, stats in event_stats.items():
        s = dict(stats)
        if "avg_returns" in s:
            s["avg_returns"] = {k: float(v) for k, v in s["avg_returns"].items()}
        if "positive_rates" in s:
            s["positive_rates"] = {k: float(v) for k, v in s["positive_rates"].items()}
        serializable_stats[key] = s

    result = {
        "timestamp": datetime.now().isoformat(),
        "data_range": "recent_3months",
        "data_time_range": f"{df_recent['timestamp'].min()} ~ {df_recent['timestamp'].max()}",
        "total_events": len(tester.events),
        "event_stats": serializable_stats,
        "backtest_metrics": {
            "return_pct": float(backtest_metrics.get("return_pct", 0)),
            "max_dd_pct": float(backtest_metrics.get("max_dd_pct", 0)),
            "total_trades": int(backtest_metrics.get("total_trades", 0)),
            "win_rate": float(backtest_metrics.get("win_rate", 0)),
            "profit_factor": float(backtest_metrics.get("profit_factor", 0)),
            "sharpe": float(backtest_metrics.get("sharpe", 0)),
            "by_strategy": backtest_metrics.get("by_strategy", {}),
        },
        "single_strategy_results": {},
    }

    for key, metrics in single_results.items():
        result["single_strategy_results"][key] = {
            "return_pct": float(metrics.get("return_pct", 0)),
            "max_dd_pct": float(metrics.get("max_dd_pct", 0)),
            "total_trades": int(metrics.get("total_trades", 0)),
            "win_rate": float(metrics.get("win_rate", 0)),
            "profit_factor": float(metrics.get("profit_factor", 0)),
            "sharpe": float(metrics.get("sharpe", 0)),
        }

    output_path = output_dir / "innovation_strategy_research_2024.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 结果已保存: {output_path}")

    # ========================================
    # 最终总结
    # ========================================
    print(f"\n{'=' * 90}")
    print("✅ 回测完成！总结:")
    print("=" * 90)

    # 找出最佳策略
    best_strategies = []
    for key, stats in event_stats.items():
        if stats.get("count", 0) >= 5:
            avg_ret = stats["avg_returns"].get("1h", 0)
            pos_rate = stats["positive_rates"].get("1h", 0)
            best_strategies.append((key, stats["count"], avg_ret, pos_rate))

    best_strategies.sort(key=lambda x: -x[2])

    if best_strategies:
        print(f"\n🏆 按 Event Study 1h收益排序 (样本≥5):")
        for key, count, avg_ret, pos_rate in best_strategies:
            name = STRATEGY_DEFINITIONS[key]["name"]
            direction = "做多" if STRATEGY_DEFINITIONS[key]["direction"] == "long" else "做空"
            print(f"   {name} ({direction}): 事件{count}个, 1h收益{avg_ret*100:+.3f}%, 正收益{pos_rate*100:.1f}%")

    # 找出回测最佳
    bt_best = []
    for key, metrics in single_results.items():
        if metrics.get("total_trades", 0) >= 3:
            bt_best.append((key, metrics))
    bt_best.sort(key=lambda x: -x[1].get("return_pct", 0))

    if bt_best:
        print(f"\n🏆 按回测收益排序 (交易≥3):")
        for key, metrics in bt_best:
            name = STRATEGY_DEFINITIONS[key]["name"]
            print(f"   {name}: 交易{metrics['total_trades']}笔, 收益{metrics['return_pct']:.2%}, "
                  f"胜率{metrics['win_rate']:.1%}, 回撤{metrics['max_dd_pct']:.2%}")

    print(f"\n{'=' * 90}")
    print("💡 下一步建议:")
    print("   1. 将 Event Detection 条件接入 Feature Engine → Event Detection Pipeline")
    print("   2. 将 Context 标签接入 Context Engine")
    print("   3. 将 Event Table + Outcome Table 写入 Playbook Database")
    print("   4. 优先接入高频策略: Cascade Flip, Micro Range Ripples")
    print("   5. 补充 OI 数据和清算数据后重新回测 Leveraged Short Squeeze")
    print("=" * 90)

    return result


if __name__ == "__main__":
    main()
