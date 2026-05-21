#!/usr/bin/env python3
"""
策略研究矩阵 - Event Study Framework

核心思想：
- 不是"预测未来"，而是"统计历史行为规律"
- Contextual Event Study：同样是事件，不同上下文，结果完全不同

研究流程：
Step 1: 检测事件 (spike, panic, breakout, liquidation)
Step 2: 记录后续收益 (5m, 15m, 1h, 2h, 4h)
Step 3: 按Context分组统计
Step 4: 生成Playbook Database
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
import json

from infrastructure.logging import get_logger

logger = get_logger("strategy_research_matrix")


class EventType(str, Enum):
    """事件类型"""
    VOLUME_CLIMAX = "volume_climax"
    FAKE_BREAKOUT = "fake_breakout"
    LIQUIDATION_CASCADE = "liquidation_cascade"
    OI_FLUSH = "oi_flush"
    PANIC_REVERSAL = "panic_reversal"
    WEEKEND_BREAKOUT = "weekend_breakout"
    TREND_EXHAUSTION = "trend_exhaustion"
    SQUEEZE = "squeeze"
    FUNDING_TRAP = "funding_trap"
    BLOWOFF_TOP = "blowoff_top"


class MarketContext(str, Enum):
    """市场上下文"""
    HIGH_FUNDING = "high_funding"
    LOW_FUNDING = "low_funding"
    HIGH_OI = "high_oi"
    LOW_OI = "low_oi"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    VOLATILE = "volatile"
    RANGING = "ranging"
    HIGH_LIQUIDITY = "high_liquidity"
    LOW_LIQUIDITY = "low_liquidity"
    SESSION_ASIA = "session_asia"
    SESSION_EUROPE = "session_europe"
    SESSION_US = "session_us"
    WEEKEND = "weekend"


@dataclass
class MarketEvent:
    """市场事件"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    
    symbol: str
    price: float
    
    strength: float
    intensity: float
    
    context: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, Any] = field(default_factory=dict)
    
    future_returns: Dict[str, float] = field(default_factory=dict)
    max_runup: float = 0.0
    max_drawdown: float = 0.0
    time_to_peak: int = 0
    time_to_trough: int = 0
    
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0


@dataclass
class EventStats:
    """事件统计"""
    event_type: EventType
    context_filter: str
    
    count: int = 0
    
    avg_return_5m: float = 0.0
    avg_return_15m: float = 0.0
    avg_return_30m: float = 0.0
    avg_return_1h: float = 0.0
    avg_return_2h: float = 0.0
    avg_return_4h: float = 0.0
    
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0
    
    positive_rate_5m: float = 0.0
    positive_rate_1h: float = 0.0
    
    avg_duration_to_peak: float = 0.0
    avg_duration_to_trough: float = 0.0
    
    best_entry_delay: str = "immediate"
    best_exit_window: str = "1h"
    
    avg_max_runup: float = 0.0
    avg_max_drawdown: float = 0.0
    drawdown_prob: float = 0.0


@dataclass
class PlaybookStep:
    """Playbook步骤"""
    phase: str
    description: str
    action: str
    entry_condition: str
    exit_condition: str
    risk_notes: str = ""


@dataclass
class Playbook:
    """Playbook"""
    name: str
    event_type: EventType
    description: str
    
    market: str
    timeframe: str
    
    context_requirements: List[str] = field(default_factory=list)
    
    steps: List[PlaybookStep] = field(default_factory=list)
    
    stats: Optional[EventStats] = None
    
    notes: str = ""


class StrategyResearchMatrix:
    """
    策略研究矩阵 - Event Study Framework
    
    核心研究方法：
    1. 检测事件
    2. 记录后续结果
    3. 按Context分组统计
    4. 生成Playbook Database
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.events: List[MarketEvent] = []
        self.playbooks: Dict[str, Playbook] = {}
        
        logger.info("StrategyResearchMatrix initialized")
    
    def _default_config(self) -> Dict:
        return {
            # Volume Climax
            "climax_volume_ratio": 2.5,
            "climax_return_threshold": 0.02,
            
            # Fake Breakout
            "breakout_threshold": 0.01,
            "fake_breakout_confirm_bars": 3,
            
            # Liquidation Cascade
            "cascade_volume_ratio": 3.0,
            "cascade_price_drop": 0.02,
            
            # OI Flush
            "oi_flush_threshold": -0.05,
            "oi_price_stable": 0.02,
            
            # Panic Reversal
            "panic_drop_threshold": -0.015,
            "panic_volume_ratio": 1.5,
            
            # Weekend
            "weekend_volume_ratio": 0.7,
            
            # Squeeze
            "squeeze_funding_threshold": 0.0003,
            "squeeze_oi_threshold": 0.02,
            
            # Context thresholds
            "funding_high_threshold": 0.0002,
            "oi_high_threshold": 0.03,
            "volatility_high_quantile": 0.8,
        }
    
    def analyze(self, df: pd.DataFrame, symbols: List[str] = None) -> Dict[str, Any]:
        """
        完整分析流程
        """
        logger.info(f"Starting Strategy Research Matrix with {len(df)} rows")
        
        if symbols:
            df = df[df["symbol"].isin(symbols)] if "symbol" in df.columns else df
        
        df = self._prepare_features(df)
        
        self._detect_all_events(df)
        
        self._label_outcomes(df)
        
        self._generate_playbooks()
        
        result = self._compile_results()
        
        logger.info(f"Analysis complete: {len(self.events)} events")
        
        return result
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备特征"""
        df = df.copy()
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        cfg = self.config
        
        df["return_5m"] = df["close"].pct_change(5)
        df["return_15m"] = df["close"].pct_change(15)
        df["return_1h"] = df["close"].pct_change(60)
        df["return_4h"] = df["close"].pct_change(240)
        
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(24).mean()
        
        if "open_interest" in df.columns:
            df["oi_change_1h"] = df["open_interest"].pct_change(12)
        
        df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
        
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        def get_session(hour):
            if 0 <= hour < 8: return "asia"
            elif 8 <= hour < 16: return "europe"
            else: return "us"
        df["session"] = df["hour"].apply(get_session)
        
        volatility = df["close"].pct_change().rolling(60).std()
        trend = df["close"].pct_change(60)
        
        df["regime"] = "ranging"
        df.loc[trend > 0.01, "regime"] = "trending_up"
        df.loc[trend < -0.01, "regime"] = "trending_down"
        volatility_threshold = volatility.rolling(window=288, min_periods=20).quantile(cfg["volatility_high_quantile"])
        df.loc[volatility > volatility_threshold, "regime"] = "volatile"
        
        funding_high = df["funding_rate"] > cfg["funding_high_threshold"]
        df["funding_context"] = np.where(funding_high, "high_funding", "low_funding")
        
        oi_high = df.get("oi_change_1h", 0) > cfg["oi_high_threshold"]
        df["oi_context"] = np.where(oi_high, "high_oi", "low_oi")
        
        volume_low = df["volume_ratio"] < 0.7
        df["liquidity_context"] = np.where(volume_low, "low_liquidity", "high_liquidity")
        
        return df
    
    def _detect_all_events(self, df: pd.DataFrame):
        """检测所有事件"""
        self.events = []
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            self.events.extend(self._detect_volume_climax(df, i, row))
            self.events.extend(self._detect_fake_breakout(df, i, row))
            self.events.extend(self._detect_liquidation_cascade(df, i, row))
            self.events.extend(self._detect_oi_flush(df, i, row))
            self.events.extend(self._detect_panic_reversal(df, i, row))
            self.events.extend(self._detect_weekend_breakout(df, i, row))
            self.events.extend(self._detect_squeeze(df, i, row))
        
        logger.info(f"Detected {len(self.events)} total events")
    
    def _detect_volume_climax(self, df, i, row) -> List[MarketEvent]:
        """检测 Volume Climax Fade"""
        events = []
        cfg = self.config
        
        if (row["volume_ratio"] > cfg["climax_volume_ratio"] and 
            abs(row["return_5m"]) > cfg["climax_return_threshold"]):
            
            is_up = row["return_5m"] > 0
            
            context = {
                "direction": "up" if is_up else "down",
                "funding_context": row.get("funding_context", "unknown"),
                "regime": row.get("regime", "ranging"),
                "session": row.get("session", "unknown"),
            }
            
            events.append(MarketEvent(
                event_id=f"climax_{i}",
                event_type=EventType.VOLUME_CLIMAX,
                timestamp=row["timestamp"],
                symbol=row.get("symbol", "BTCUSDT"),
                price=row["close"],
                strength=abs(row["return_5m"]),
                intensity=row["volume_ratio"] / cfg["climax_volume_ratio"],
                context=context,
                features={
                    "volume_ratio": row["volume_ratio"],
                    "return_5m": row["return_5m"],
                    "wick_ratio": row.get("wick_ratio", 0),
                    "funding_rate": row.get("funding_rate", 0),
                }
            ))
        
        return events
    
    def _detect_fake_breakout(self, df, i, row) -> List[MarketEvent]:
        """检测 Fake Breakout Trap"""
        events = []
        cfg = self.config
        
        if i < 65:
            return events
        
        rolling_high = df["high"].iloc[max(0,i-24):i].max()
        rolling_low = df["low"].iloc[max(0,i-24):i].min()
        
        breakout_up = row["high"] > rolling_high * (1 + cfg["breakout_threshold"])
        breakout_down = row["low"] < rolling_low * (1 - cfg["breakout_threshold"])
        
        confirm_window = cfg["fake_breakout_confirm_bars"]
        
        if i + confirm_window < len(df):
            future_low = df["low"].iloc[i+1:i+1+confirm_window].min()
            future_high = df["high"].iloc[i+1:i+1+confirm_window].max()
            
            if breakout_up and future_low < rolling_high:
                context = {
                    "direction": "up_then_down",
                    "funding_context": row.get("funding_context", "unknown"),
                    "oi_context": row.get("oi_context", "unknown"),
                    "regime": row.get("regime", "ranging"),
                }
                
                events.append(MarketEvent(
                    event_id=f"fake_breakout_{i}",
                    event_type=EventType.FAKE_BREAKOUT,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    strength=(row["high"] - rolling_high) / rolling_high,
                    intensity=min(1.0, (row["high"] - rolling_high) / rolling_high / cfg["breakout_threshold"]),
                    context=context,
                    features={
                        "breakout_strength": (row["high"] - rolling_high) / rolling_high,
                        "volume_ratio": row["volume_ratio"],
                        "oi_change": row.get("oi_change_1h", 0),
                    }
                ))
            
            if breakout_down and future_high > rolling_low:
                context = {
                    "direction": "down_then_up",
                    "funding_context": row.get("funding_context", "unknown"),
                    "oi_context": row.get("oi_context", "unknown"),
                    "regime": row.get("regime", "ranging"),
                }
                
                events.append(MarketEvent(
                    event_id=f"fake_breakdown_{i}",
                    event_type=EventType.FAKE_BREAKOUT,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    strength=(rolling_low - row["low"]) / rolling_low,
                    intensity=min(1.0, (rolling_low - row["low"]) / rolling_low / cfg["breakout_threshold"]),
                    context=context,
                    features={
                        "breakdown_strength": (rolling_low - row["low"]) / rolling_low,
                        "volume_ratio": row["volume_ratio"],
                        "oi_change": row.get("oi_change_1h", 0),
                    }
                ))
        
        return events
    
    def _detect_liquidation_cascade(self, df, i, row) -> List[MarketEvent]:
        """检测 Liquidation Cascade"""
        events = []
        cfg = self.config
        
        if (row["volume_ratio"] > cfg["cascade_volume_ratio"] and 
            row["return_5m"] < -cfg["cascade_price_drop"]):
            
            events.append(MarketEvent(
                event_id=f"cascade_{i}",
                event_type=EventType.LIQUIDATION_CASCADE,
                timestamp=row["timestamp"],
                symbol=row.get("symbol", "BTCUSDT"),
                price=row["close"],
                strength=abs(row["return_5m"]),
                intensity=row["volume_ratio"] / cfg["cascade_volume_ratio"],
                context={
                    "funding_context": row.get("funding_context", "unknown"),
                    "regime": row.get("regime", "ranging"),
                    "session": row.get("session", "unknown"),
                },
                features={
                    "volume_ratio": row["volume_ratio"],
                    "return_5m": row["return_5m"],
                    "wick_ratio": row.get("wick_ratio", 0),
                }
            ))
        
        return events
    
    def _detect_oi_flush(self, df, i, row) -> List[MarketEvent]:
        """检测 OI Flush Recovery"""
        events = []
        cfg = self.config
        
        oi_change = row.get("oi_change_1h", 0)
        if pd.isna(oi_change):
            return events
        
        if oi_change < cfg["oi_flush_threshold"]:
            price_change = abs(row.get("return_1h", 0))
            
            if price_change < cfg["oi_price_stable"]:
                events.append(MarketEvent(
                    event_id=f"oi_flush_{i}",
                    event_type=EventType.OI_FLUSH,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    strength=abs(oi_change),
                    intensity=min(1.0, abs(oi_change) / 0.15),
                    context={
                        "funding_context": row.get("funding_context", "unknown"),
                        "regime": row.get("regime", "ranging"),
                    },
                    features={
                        "oi_change": oi_change,
                        "price_change": price_change,
                        "funding_rate": row.get("funding_rate", 0),
                    }
                ))
        
        return events
    
    def _detect_panic_reversal(self, df, i, row) -> List[MarketEvent]:
        """检测 Panic Reversal"""
        events = []
        cfg = self.config
        
        if (row.get("return_1h", 0) < cfg["panic_drop_threshold"] and 
            row["volume_ratio"] > cfg["panic_volume_ratio"]):
            
            events.append(MarketEvent(
                event_id=f"panic_{i}",
                event_type=EventType.PANIC_REVERSAL,
                timestamp=row["timestamp"],
                symbol=row.get("symbol", "BTCUSDT"),
                price=row["close"],
                strength=abs(row.get("return_1h", 0)),
                intensity=min(1.0, abs(row.get("return_1h", 0)) / 0.05),
                context={
                    "funding_context": row.get("funding_context", "unknown"),
                    "regime": row.get("regime", "ranging"),
                    "session": row.get("session", "unknown"),
                    "is_weekend": row.get("is_weekend", False),
                },
                features={
                    "return_1h": row.get("return_1h", 0),
                    "volume_ratio": row["volume_ratio"],
                    "funding_rate": row.get("funding_rate", 0),
                }
            ))
        
        return events
    
    def _detect_weekend_breakout(self, df, i, row) -> List[MarketEvent]:
        """检测 Weekend Breakout"""
        events = []
        cfg = self.config
        
        if row.get("is_weekend", False):
            breakout_high = df["high"].iloc[max(0,i-24):i].max()
            breakout_low = df["low"].iloc[max(0,i-24):i].min()
            
            if row["high"] > breakout_high * 1.005:
                events.append(MarketEvent(
                    event_id=f"weekend_up_{i}",
                    event_type=EventType.WEEKEND_BREAKOUT,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    strength=(row["high"] - breakout_high) / breakout_high,
                    intensity=row["volume_ratio"] / cfg["weekend_volume_ratio"],
                    context={
                        "direction": "up",
                        "session": row.get("session", "unknown"),
                        "liquidity_context": row.get("liquidity_context", "unknown"),
                    },
                    features={
                        "breakout_strength": (row["high"] - breakout_high) / breakout_high,
                        "volume_ratio": row["volume_ratio"],
                    }
                ))
            
            if row["low"] < breakout_low * 0.995:
                events.append(MarketEvent(
                    event_id=f"weekend_down_{i}",
                    event_type=EventType.WEEKEND_BREAKOUT,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    strength=(breakout_low - row["low"]) / breakout_low,
                    intensity=row["volume_ratio"] / cfg["weekend_volume_ratio"],
                    context={
                        "direction": "down",
                        "session": row.get("session", "unknown"),
                        "liquidity_context": row.get("liquidity_context", "unknown"),
                    },
                    features={
                        "breakdown_strength": (breakout_low - row["low"]) / breakout_low,
                        "volume_ratio": row["volume_ratio"],
                    }
                ))
        
        return events
    
    def _detect_squeeze(self, df, i, row) -> List[MarketEvent]:
        """检测 Squeeze"""
        events = []
        cfg = self.config
        
        funding = row.get("funding_rate", 0)
        oi_change = row.get("oi_change_1h", 0)
        
        if (funding > cfg["squeeze_funding_threshold"] and 
            not pd.isna(oi_change) and 
            oi_change > cfg["squeeze_oi_threshold"]):
            
            events.append(MarketEvent(
                event_id=f"squeeze_{i}",
                event_type=EventType.SQUEEZE,
                timestamp=row["timestamp"],
                symbol=row.get("symbol", "BTCUSDT"),
                price=row["close"],
                strength=funding,
                intensity=min(1.0, funding / 0.001),
                context={
                    "regime": row.get("regime", "ranging"),
                    "session": row.get("session", "unknown"),
                },
                features={
                    "funding_rate": funding,
                    "oi_change": oi_change,
                    "volume_ratio": row["volume_ratio"],
                    "return_5m": row.get("return_5m", 0),
                }
            ))
        
        return events
    
    def _label_outcomes(self, df: pd.DataFrame):
        """标记后续结果"""
        df = df.set_index("timestamp").sort_index()
        
        for event in self.events:
            event_time = event.timestamp
            
            look_forward = {
                "5m": 5,
                "15m": 15,
                "30m": 30,
                "1h": 60,
                "2h": 120,
                "4h": 240,
            }
            
            entry_price = event.price
            max_price = entry_price
            min_price = entry_price
            time_to_peak = 0
            time_to_trough = 0
            
            for label, bars in look_forward.items():
                future_time = event_time + timedelta(minutes=bars)
                try:
                    future_data = df.loc[:future_time].iloc[-1]
                    future_price = future_data["close"]
                    future_ret = (future_price - entry_price) / entry_price
                    event.future_returns[label] = future_ret
                    
                    if future_price > max_price:
                        max_price = future_price
                        time_to_peak = bars
                    if future_price < min_price:
                        min_price = future_price
                        time_to_trough = bars
                except:
                    pass
            
            event.max_runup = (max_price - entry_price) / entry_price
            event.max_drawdown = (entry_price - min_price) / entry_price
            event.time_to_peak = time_to_peak
            event.time_to_trough = time_to_trough
            
            ret_5m = event.future_returns.get("5m", 0)
            
            if event.features.get("return_5m", 0) > 0:
                event.continuation_prob = 1.0 if ret_5m > 0 else 0.0
            else:
                event.continuation_prob = 1.0 if ret_5m < 0 else 0.0
            
            event.reversal_prob = 1.0 if (ret_5m * event.features.get("return_5m", 0) < 0) else 0.0
    
    def _generate_playbooks(self):
        """生成Playbook Database"""
        
        playbook_templates = {
            EventType.VOLUME_CLIMAX: Playbook(
                name="Volume Climax Fade",
                event_type=EventType.VOLUME_CLIMAX,
                description="放量高潮后退潮",
                market="Meme/BTC",
                timeframe="15m-2h",
                context_requirements=["高波动", "高成交量"],
                steps=[
                    PlaybookStep("Phase 1: Detection", "检测到放量高潮", "观察", "volume_ratio > 2.5", "无"),
                    PlaybookStep("Phase 2: Entry", "等待反转信号", "做空", "第二根K收阴且缩量", "wick_ratio > 0.5"),
                    PlaybookStep("Phase 3: Exit", "分批止盈", "平仓", "目标1-2%", "时间超过2h"),
                ],
                notes="成功率随funding升高而升高"
            ),
            EventType.FAKE_BREAKOUT: Playbook(
                name="Fake Breakout Trap",
                event_type=EventType.FAKE_BREAKOUT,
                description="突破失败后快速反杀",
                market="BTC/主流币",
                timeframe="15m-1h",
                context_requirements=["高OI增加", "低成交量"],
                steps=[
                    PlaybookStep("Phase 1: Watch", "关注突破", "观察", "突破前高/低", "volume_ratio < 1.0"),
                    PlaybookStep("Phase 2: Confirm", "确认假突破", "准备做空/多", "3根K内跌回区间", "无"),
                    PlaybookStep("Phase 3: Entry", "快速入场", "做空/多", "确认假突破", "超过5根K不入场"),
                    PlaybookStep("Phase 4: Exit", "快进快出", "平仓", "目标1-2%", "超过1h强制平"),
                ],
                notes="OI增加时fake breakout概率最高"
            ),
            EventType.LIQUIDATION_CASCADE: Playbook(
                name="Liquidation Cascade",
                event_type=EventType.LIQUIDATION_CASCADE,
                description="连锁爆仓后反弹",
                market="合约/高杠杆",
                timeframe="5m-1h",
                context_requirements=["高OI", "高funding"],
                steps=[
                    PlaybookStep("Phase 1: Spike", "检测强平脉冲", "观察", "volume_ratio > 3.0 且下跌", "无"),
                    PlaybookStep("Phase 2: Wait", "等待衰竭", "观察", "成交量萎缩", "超过30min"),
                    PlaybookStep("Phase 3: Entry", "低位入场", "做多", "止跌信号", "继续放量不入场"),
                    PlaybookStep("Phase 4: Exit", "快速止盈", "平仓", "目标2-3%", "超过1h强制平"),
                ],
                notes="Cascade后反弹概率高，但需确认OI已清"
            ),
            EventType.OI_FLUSH: Playbook(
                name="OI Flush Recovery",
                event_type=EventType.OI_FLUSH,
                description="清杠杆后趋势恢复",
                market="BTC",
                timeframe="15m-4h",
                context_requirements=["OI大跌", "价格稳定"],
                steps=[
                    PlaybookStep("Phase 1: Detect Flush", "检测OI清洗", "观察", "OI下跌 > 5%", "无"),
                    PlaybookStep("Phase 2: Confirm Stability", "确认价格稳定", "观察", "价格波动 < 2%", "超过4h不启动"),
                    PlaybookStep("Phase 3: Entry", "趋势启动入场", "顺势", "出现方向K", "追涨杀跌"),
                    PlaybookStep("Phase 4: Exit", "跟踪止盈", "平仓", "OI恢复或逆转", "超过4h"),
                ],
                notes="Flush后恢复趋势概率高"
            ),
            EventType.PANIC_REVERSAL: Playbook(
                name="Panic Reversal",
                event_type=EventType.PANIC_REVERSAL,
                description="恐慌性下跌后修复",
                market="BTC",
                timeframe="15m-4h",
                context_requirements=["大跌", "高成交量"],
                steps=[
                    PlaybookStep("Phase 1: Panic", "检测恐慌", "观察", "1h下跌 > 1.5% 且放量", "无"),
                    PlaybookStep("Phase 2: Wait Bottom", "等待止跌", "观察", "出现缩量十字星", "超过2h不止跌不入场"),
                    PlaybookStep("Phase 3: Entry", "左侧或右侧入场", "分批买入", "止跌K确认", "继续放量下跌不入场"),
                    PlaybookStep("Phase 4: Exit", "目标止盈", "分批平仓", "目标3-5%", "超过4h强制平"),
                ],
                notes="US会话反弹概率最高"
            ),
            EventType.WEEKEND_BREAKOUT: Playbook(
                name="Weekend Liquidity Trap",
                event_type=EventType.WEEKEND_BREAKOUT,
                description="周末低流动性假突破",
                market="BTC",
                timeframe="15m-4h",
                context_requirements=["周末", "低成交量"],
                steps=[
                    PlaybookStep("Phase 1: Watch", "关注周末", "观察", "is_weekend = True", "无"),
                    PlaybookStep("Phase 2: Detect Breakout", "检测突破", "观察", "突破24h高/低", "无"),
                    PlaybookStep("Phase 3: Wait Trap", "等待陷阱", "观察", "3根K内跌回", "超过5根K不陷阱"),
                    PlaybookStep("Phase 4: Counter", "反向操作", "反手", "确认假突破", "超过1h不操作"),
                ],
                notes="周末假突破失败率极高"
            ),
            EventType.SQUEEZE: Playbook(
                name="Squeeze Detection",
                event_type=EventType.SQUEEZE,
                description="逼空/逼多信号",
                market="合约",
                timeframe="5m-1h",
                context_requirements=["高funding", "OI增加"],
                steps=[
                    PlaybookStep("Phase 1: Detect", "检测挤仓", "观察", "funding > 0.03% 且 OI增加", "无"),
                    PlaybookStep("Phase 2: Direction", "判断方向", "观察", "价格快速移动", "无"),
                    PlaybookStep("Phase 3: Follow", "顺势操作", "顺势", "确认方向", "反转超过50%止损"),
                    PlaybookStep("Phase 4: Exit", "快速止盈", "平仓", "目标2-3%", "超过1h"),
                ],
                notes="Squeeze后趋势延续概率高"
            ),
        }
        
        for event_type, template in playbook_templates.items():
            events = [e for e in self.events if e.event_type == event_type]
            if events:
                stats = self._calculate_stats(events, "all")
                template.stats = stats
                
                context_stats = {}
                for ctx_key in ["funding_context", "regime", "session"]:
                    for ctx_val in set(e.context.get(ctx_key, "unknown") for e in events):
                        ctx_events = [e for e in events if e.context.get(ctx_key) == ctx_val]
                        if ctx_events:
                            ctx_stats = self._calculate_stats(ctx_events, f"{ctx_key}={ctx_val}")
                            context_stats[f"{ctx_key}_{ctx_val}"] = ctx_stats
                
                template.context_stats = context_stats
                
                self.playbooks[event_type.value] = template
    
    def _calculate_stats(self, events: List[MarketEvent], context_filter: str) -> EventStats:
        """计算统计"""
        event_type = events[0].event_type if events else None
        
        stats = EventStats(
            event_type=event_type,
            context_filter=context_filter,
            count=len(events)
        )
        
        if not events:
            return stats
        
        time_windows = ["5m", "15m", "30m", "1h", "2h", "4h"]
        returns_by_window = defaultdict(list)
        
        for event in events:
            for window in time_windows:
                if window in event.future_returns:
                    returns_by_window[window].append(event.future_returns[window])
        
        if returns_by_window["5m"]:
            stats.avg_return_5m = np.mean(returns_by_window["5m"])
            stats.positive_rate_5m = np.mean([r > 0 for r in returns_by_window["5m"]])
        
        if returns_by_window["15m"]:
            stats.avg_return_15m = np.mean(returns_by_window["15m"])
        
        if returns_by_window["30m"]:
            stats.avg_return_30m = np.mean(returns_by_window["30m"])
        
        if returns_by_window["1h"]:
            stats.avg_return_1h = np.mean(returns_by_window["1h"])
            stats.positive_rate_1h = np.mean([r > 0 for r in returns_by_window["1h"]])
        
        if returns_by_window["2h"]:
            stats.avg_return_2h = np.mean(returns_by_window["2h"])
        
        if returns_by_window["4h"]:
            stats.avg_return_4h = np.mean(returns_by_window["4h"])
        
        if returns_by_window["5m"] and returns_by_window["1h"]:
            if stats.positive_rate_1h > stats.positive_rate_5m:
                stats.best_entry_delay = "immediate"
                stats.best_exit_window = "1h"
            else:
                stats.best_entry_delay = "wait_15m"
                stats.best_exit_window = "15m"
        
        stats.continuation_prob = np.mean([e.continuation_prob for e in events])
        stats.reversal_prob = np.mean([e.reversal_prob for e in events])
        
        stats.avg_max_runup = np.mean([e.max_runup for e in events])
        stats.avg_max_drawdown = np.mean([e.max_drawdown for e in events])
        stats.drawdown_prob = np.mean([e.max_drawdown > 0.01 for e in events])
        
        durations_to_peak = [e.time_to_peak for e in events if e.time_to_peak > 0]
        if durations_to_peak:
            stats.avg_duration_to_peak = np.mean(durations_to_peak)
        
        durations_to_trough = [e.time_to_trough for e in events if e.time_to_trough > 0]
        if durations_to_trough:
            stats.avg_duration_to_trough = np.mean(durations_to_trough)
        
        return stats
    
    def _compile_results(self) -> Dict[str, Any]:
        """编译结果"""
        return {
            "total_events": len(self.events),
            "events_by_type": {
                et.value: len([e for e in self.events if e.event_type == et])
                for et in EventType
            },
            "playbooks": {
                name: {
                    "name": pb.name,
                    "event_type": pb.event_type.value,
                    "description": pb.description,
                    "market": pb.market,
                    "timeframe": pb.timeframe,
                    "steps": [
                        {
                            "phase": s.phase,
                            "description": s.description,
                            "action": s.action,
                            "entry_condition": s.entry_condition,
                            "exit_condition": s.exit_condition,
                            "risk_notes": s.risk_notes,
                        }
                        for s in pb.steps
                    ],
                    "stats": {
                        "count": pb.stats.count if pb.stats else 0,
                        "avg_return_1h": pb.stats.avg_return_1h if pb.stats else 0,
                        "positive_rate_1h": pb.stats.positive_rate_1h if pb.stats else 0,
                        "continuation_prob": pb.stats.continuation_prob if pb.stats else 0,
                        "reversal_prob": pb.stats.reversal_prob if pb.stats else 0,
                        "best_entry_delay": pb.stats.best_entry_delay if pb.stats else "unknown",
                        "best_exit_window": pb.stats.best_exit_window if pb.stats else "unknown",
                        "avg_max_runup": pb.stats.avg_max_runup if pb.stats else 0,
                        "avg_max_drawdown": pb.stats.avg_max_drawdown if pb.stats else 0,
                        "drawdown_prob": pb.stats.drawdown_prob if pb.stats else 0,
                    } if pb.stats else {},
                    "context_analysis": {
                        ctx_name: {
                            "count": ctx_stats.count,
                            "avg_return_1h": ctx_stats.avg_return_1h,
                            "positive_rate_1h": ctx_stats.positive_rate_1h,
                        }
                        for ctx_name, ctx_stats in getattr(pb, "context_stats", {}).items()
                    } if hasattr(pb, "context_stats") else {},
                    "notes": pb.notes,
                }
                for name, pb in self.playbooks.items()
            }
        }
    
    def print_report(self, result: Dict):
        """打印报告"""
        print("\n" + "="*80)
        print("📊 策略研究矩阵报告")
        print("="*80)
        
        print(f"\n📈 总事件数: {result['total_events']}")
        
        print(f"\n📋 事件分布:")
        for et, count in sorted(result["events_by_type"].items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"   {et}: {count}")
        
        print("\n" + "="*80)
        print("📖 PLAYBOOK DATABASE")
        print("="*80)
        
        for name, pb_data in sorted(result["playbooks"].items(), key=lambda x: -x[1]["stats"]["count"]):
            stats = pb_data["stats"]
            
            print(f"\n{'='*70}")
            print(f"🎯 【{pb_data['name']}】")
            print(f"   市场: {pb_data['market']} | 周期: {pb_data['timeframe']}")
            print(f"   描述: {pb_data['description']}")
            print("="*70)
            
            print(f"\n📊 基础统计:")
            print(f"   样本数: {stats['count']}")
            print(f"   1h平均收益: {stats['avg_return_1h']*100:+.2f}%")
            print(f"   1h正收益概率: {stats['positive_rate_1h']*100:.1f}%")
            
            print(f"\n⏱️ 最佳时机:")
            print(f"   最佳入场延迟: {stats['best_entry_delay']}")
            print(f"   最佳退出窗口: {stats['best_exit_window']}")
            
            print(f"\n📈 收益分布:")
            print(f"   5分钟:  {stats.get('avg_return_5m', 0)*100:+.2f}%")
            print(f"   15分钟: {stats.get('avg_return_15m', 0)*100:+.2f}%")
            print(f"   30分钟: {stats.get('avg_return_30m', 0)*100:+.2f}%")
            print(f"   1小时:  {stats['avg_return_1h']*100:+.2f}%")
            print(f"   2小时:  {stats.get('avg_return_2h', 0)*100:+.2f}%")
            print(f"   4小时:  {stats.get('avg_return_4h', 0)*100:+.2f}%")
            
            print(f"\n⚡ 概率:")
            print(f"   延续概率: {stats['continuation_prob']*100:.1f}%")
            print(f"   反转概率: {stats['reversal_prob']*100:.1f}%")
            
            print(f"\n📉 风险:")
            print(f"   平均最大涨幅: {stats['avg_max_runup']*100:.2f}%")
            print(f"   平均最大回撤: {stats['avg_max_drawdown']*100:.2f}%")
            print(f"   超过1%回撤概率: {stats['drawdown_prob']*100:.1f}%")
            
            if pb_data.get("context_analysis"):
                print(f"\n🔍 Context分析:")
                for ctx_name, ctx_stats in pb_data["context_analysis"].items():
                    ctx_label = ctx_name.replace("_", " ").title()
                    print(f"   {ctx_label}: 样本={ctx_stats['count']}, 1h收益={ctx_stats['avg_return_1h']*100:+.2f}%, 正收益概率={ctx_stats['positive_rate_1h']*100:.1f}%")
            
            print(f"\n📝 操作步骤:")
            for step in pb_data["steps"]:
                print(f"   [{step['phase']}]")
                print(f"   描述: {step['description']}")
                print(f"   动作: {step['action']}")
                print(f"   入场条件: {step['entry_condition']}")
                print(f"   出场条件: {step['exit_condition']}")
                if step.get("risk_notes"):
                    print(f"   风险提示: {step['risk_notes']}")
            
            if pb_data.get("notes"):
                print(f"\n💡 要点: {pb_data['notes']}")
        
        print("\n" + "="*80)
        print("✅ 研究完成！")
        print("="*80)


def run_research(df: pd.DataFrame) -> Dict[str, Any]:
    """运行完整研究"""
    matrix = StrategyResearchMatrix()
    result = matrix.analyze(df)
    matrix.print_report(result)
    return result
