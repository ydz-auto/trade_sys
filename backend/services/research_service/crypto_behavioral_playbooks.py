#!/usr/bin/env python3
"""
Crypto Behavioral Playbooks - 完整版

包含所有顶级Crypto市场行为策略：

1. Panic Reversal（恐慌修复）
2. Fake Breakout（假突破反杀）
3. OI Flush（OI清洗后趋势）
4. Weekend Manipulation（周末操纵）
5. Short Squeeze（逼空）
6. Liquidation Cascade（清算连锁）
7. Volume Climax Fade（放量高潮衰竭）

这个系统不是"预测未来"，而是"统计历史行为规律"
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("crypto_behavioral_playbooks")


class PlaybookType(str, Enum):
    """Playbook类型"""
    PANIC_REVERSAL = "panic_reversal"
    FAKE_BREAKOUT = "fake_breakout"
    OI_FLUSH = "oi_flush"
    WEEKEND_MANIPULATION = "weekend_manipulation"
    SHORT_SQUEEZE = "short_squeeze"
    LIQUIDATION_CASCADE = "liquidation_cascade"
    VOLUME_CLIMAX = "volume_climax"


class MarketRegime(str, Enum):
    """市场状态"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"


@dataclass
class PlaybookEvent:
    """Playbook事件"""
    playbook_id: str
    playbook_type: PlaybookType
    timestamp: datetime
    
    # 基础信息
    symbol: str
    price: float
    intensity: float  # 事件强度 0-1
    
    # 条件详情
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # 市场上下文
    regime: str = "ranging"
    session: str = "unknown"
    is_weekend: bool = False
    
    # 后续标签
    future_returns: Dict[str, float] = field(default_factory=dict)
    max_runup: float = 0.0
    max_drawdown: float = 0.0
    time_to_peak: int = 0
    time_to_reversal: int = 0
    
    # 统计结果
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0
    avg_duration: float = 0.0


@dataclass
class PlaybookStats:
    """Playbook统计"""
    playbook_type: PlaybookType
    playbook_name: str
    description: str
    
    # 基础统计
    total_events: int = 0
    
    # 收益统计
    avg_return_5m: float = 0.0
    avg_return_15m: float = 0.0
    avg_return_30m: float = 0.0
    avg_return_1h: float = 0.0
    avg_return_2h: float = 0.0
    avg_return_4h: float = 0.0
    
    # 最佳时机
    best_entry_window: str = "unknown"
    best_exit_window: str = "unknown"
    avg_duration_to_profitable: float = 0.0
    
    # 概率
    positive_rate_5m: float = 0.0
    positive_rate_15m: float = 0.0
    positive_rate_1h: float = 0.0
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0
    
    # 风险
    avg_max_runup: float = 0.0
    avg_max_drawdown: float = 0.0
    max_drawdown_prob: float = 0.0
    
    # 条件分组统计
    by_regime: Dict[str, Any] = field(default_factory=dict)
    by_session: Dict[str, Any] = field(default_factory=dict)
    by_intensity: Dict[str, Any] = field(default_factory=dict)
    
    # 时段分布
    by_hour: Dict[int, int] = field(default_factory=dict)
    by_day: Dict[int, int] = field(default_factory=dict)


class CryptoBehavioralPlaybooks:
    """
    Crypto Behavioral Playbooks 完整实现
    
    这不是预测未来，而是统计历史行为规律
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        logger.info("CryptoBehavioralPlaybooks initialized")
    
    def _default_config(self) -> Dict:
        return {
            # Panic Reversal - 暴跌后反弹
            "panic_return_threshold": -0.015,
            "panic_volume_ratio": 1.3,
            
            # Fake Breakout - 假突破
            "breakout_threshold": 0.005,
            "fake_breakout_volume_ratio": 0.8,
            
            # OI Flush - OI清洗后趋势（使用替代指标）
            "oi_flush_threshold": -0.03,
            "oi_flush_volume_ratio": 1.5,  # 高成交量（强平信号）
            "oi_flush_volatility_ratio": 2.0,  # 高波动
            
            # Weekend - 周末操纵
            "weekend_volume_ratio": 0.9,
            "weekend_return_threshold": 0.005,
            
            # Short Squeeze - 逼空（使用替代指标）
            "squeeze_funding_threshold": 0.0003,  # 正funding（多头主导）
            "squeeze_oi_increase_required": False,
            "squeeze_price_threshold": 0.01,  # 价格快速拉升
            "squeeze_volume_ratio": 1.5,  # 成交量放大
            
            # Volume Climax - 放量高潮
            "climax_volume_ratio": 1.8,
            "climax_return_threshold": 0.015,
            
            # Time Windows
            "time_windows": ["5m", "15m", "30m", "1h", "2h", "4h"],
        }
    
    def analyze(self, df: pd.DataFrame, symbols: List[str] = None) -> Dict[str, Any]:
        """
        完整分析流程
        
        Args:
            df: 市场数据（包含K线、features等）
            symbols: 可选，筛选特定交易对
            
        Returns:
            所有Playbook的统计结果
        """
        logger.info(f"Starting Crypto Behavioral Analysis with {len(df)} rows")
        
        if symbols:
            df = df[df["symbol"].isin(symbols)] if "symbol" in df.columns else df
        
        # 添加基础特征
        df = self._prepare_features(df)
        
        # 检测所有Playbook事件
        events = []
        events.extend(self._detect_panic_reversal_events(df))
        events.extend(self._detect_fake_breakout_events(df))
        events.extend(self._detect_oi_flush_events(df))
        events.extend(self._detect_weekend_manipulation_events(df))
        events.extend(self._detect_short_squeeze_events(df))
        events.extend(self._detect_volume_climax_events(df))
        
        logger.info(f"Detected {len(events)} total playbook events")
        
        # 标记后续结果
        events = self._label_outcomes(events, df)
        
        # 生成各Playbook统计
        playbooks = {}
        
        for playbook_type in PlaybookType:
            playbook_events = [e for e in events if e.playbook_type == playbook_type]
            if playbook_events:
                stats = self._calculate_playbook_stats(playbook_events, playbook_type)
                playbooks[playbook_type.value] = stats
        
        # 跨Playbook分析
        cross_analysis = self._cross_playbook_analysis(events)
        
        result = {
            "total_events": len(events),
            "events_by_playbook": {
                pt.value: len([e for e in events if e.playbook_type == pt])
                for pt in PlaybookType
            },
            "playbooks": playbooks,
            "cross_analysis": cross_analysis,
        }
        
        logger.info(f"Analysis complete: {len(events)} events, {len(playbooks)} playbooks")
        return result
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备特征"""
        df = df.copy()
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        # 计算收益率
        df["return_5m"] = df["close"].pct_change(5)
        df["return_15m"] = df["close"].pct_change(15)
        df["return_1h"] = df["close"].pct_change(60)
        df["return_4h"] = df["close"].pct_change(240)
        
        # 计算成交量比率
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(24).mean()
        
        # 计算OI变化
        if "open_interest" in df.columns:
            df["oi_change_1h"] = df["open_interest"].pct_change(12)  # 1h变化
        
        # 添加时段特征
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        # 会话分类
        def get_session(hour):
            if 0 <= hour < 8:
                return "asia"
            elif 8 <= hour < 16:
                return "europe"
            else:
                return "us"
        
        df["session"] = df["hour"].apply(get_session)
        
        # 计算市场状态
        volatility = df["close"].pct_change().rolling(60).std()
        trend = df["close"].pct_change(60)
        
        df["regime"] = "ranging"
        df.loc[trend > 0.01, "regime"] = "trending_up"
        df.loc[trend < -0.01, "regime"] = "trending_down"
        df.loc[volatility > volatility.quantile(0.9), "regime"] = "volatile"
        
        return df
    
    # ========== Event Detection ==========
    
    def _detect_panic_reversal_events(self, df: pd.DataFrame) -> List[PlaybookEvent]:
        """检测Panic Reversal事件"""
        events = []
        cfg = self.config
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            # Panic条件：大跌 + 高成交量
            is_panic = (
                row.get("return_1h", 0) < cfg["panic_return_threshold"] and
                row.get("volume_ratio", 1) > cfg["panic_volume_ratio"]
            )
            
            if is_panic:
                event = PlaybookEvent(
                    playbook_id=f"panic_{i}",
                    playbook_type=PlaybookType.PANIC_REVERSAL,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    intensity=min(1.0, abs(row.get("return_1h", 0)) / 0.1),
                    conditions={
                        "return_1h": row.get("return_1h", 0),
                        "volume_ratio": row.get("volume_ratio", 1),
                        "funding_rate": row.get("funding_rate", 0),
                        "oi_change": row.get("oi_change_1h", 0),
                    },
                    regime=row.get("regime", "ranging"),
                    session=row.get("session", "unknown"),
                    is_weekend=row.get("is_weekend", False),
                )
                events.append(event)
        
        logger.info(f"Detected {len(events)} Panic Reversal events")
        return events
    
    def _detect_fake_breakout_events(self, df: pd.DataFrame) -> List[PlaybookEvent]:
        """检测Fake Breakout事件"""
        events = []
        cfg = self.config
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            # 计算rolling high
            rolling_high = df["high"].iloc[i-60:i].max()
            
            # 突破条件
            is_breakout = row["high"] > rolling_high * (1 + cfg["breakout_threshold"])
            
            # 假突破条件：突破后快速回落
            if i + 5 < len(df):
                future_price = df["close"].iloc[i+5]
                is_fake = future_price < rolling_high
                
                if is_breakout and is_fake:
                    event = PlaybookEvent(
                        playbook_id=f"fake_breakout_{i}",
                        playbook_type=PlaybookType.FAKE_BREAKOUT,
                        timestamp=row["timestamp"],
                        symbol=row.get("symbol", "BTCUSDT"),
                        price=row["close"],
                        intensity=(row["high"] - rolling_high) / rolling_high,
                        conditions={
                            "breakout_strength": (row["high"] - rolling_high) / rolling_high,
                            "volume_ratio": row.get("volume_ratio", 1),
                            "oi_change": row.get("oi_change_1h", 0),
                            "return_5m": row.get("return_5m", 0),
                        },
                        regime=row.get("regime", "ranging"),
                        session=row.get("session", "unknown"),
                        is_weekend=row.get("is_weekend", False),
                    )
                    events.append(event)
        
        logger.info(f"Detected {len(events)} Fake Breakout events")
        return events
    
    def _detect_oi_flush_events(self, df: pd.DataFrame) -> List[PlaybookEvent]:
        """检测OI Flush事件（使用替代指标）"""
        events = []
        cfg = self.config
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            funding = row.get("funding_rate", 0)
            volume_ratio = row.get("volume_ratio", 1)
            return_5m = abs(row.get("return_5m", 0))
            regime = row.get("regime", "ranging")
            
            is_flush = (
                funding > 0.0002 and
                volume_ratio > 1.5 and
                return_5m > 0.01 and
                regime == "volatile"
            )
            
            if is_flush:
                event = PlaybookEvent(
                    playbook_id=f"oi_flush_{i}",
                    playbook_type=PlaybookType.OI_FLUSH,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    intensity=min(1.0, funding / 0.001),
                    conditions={
                        "funding_rate": funding,
                        "return_5m": return_5m,
                        "volume_ratio": volume_ratio,
                        "regime": regime,
                    },
                    regime=row.get("regime", "ranging"),
                    session=row.get("session", "unknown"),
                    is_weekend=row.get("is_weekend", False),
                )
                events.append(event)
        
        logger.info(f"Detected {len(events)} OI Flush events")
        return events
    
    def _detect_weekend_manipulation_events(self, df: pd.DataFrame) -> List[PlaybookEvent]:
        """检测Weekend Manipulation事件"""
        events = []
        cfg = self.config
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            is_weekend_spike = (
                row.get("is_weekend", False) and
                row.get("volume_ratio", 1) < cfg["weekend_volume_ratio"] and
                abs(row.get("return_5m", 0)) > cfg.get("weekend_return_threshold", 0.01)
            )
            
            if is_weekend_spike:
                event = PlaybookEvent(
                    playbook_id=f"weekend_{i}",
                    playbook_type=PlaybookType.WEEKEND_MANIPULATION,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    intensity=min(1.0, abs(row.get("return_5m", 0)) / 0.1),
                    conditions={
                        "return_5m": row.get("return_5m", 0),
                        "volume_ratio": row.get("volume_ratio", 1),
                        "hour": row.get("hour", 0),
                    },
                    regime=row.get("regime", "ranging"),
                    session=row.get("session", "unknown"),
                    is_weekend=True,
                )
                events.append(event)
        
        logger.info(f"Detected {len(events)} Weekend Manipulation events")
        return events
    
    def _detect_short_squeeze_events(self, df: pd.DataFrame) -> List[PlaybookEvent]:
        """检测Short Squeeze事件（使用替代指标）"""
        events = []
        cfg = self.config
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            funding = row.get("funding_rate", 0)
            
            price_up = row.get("return_5m", 0) > cfg.get("squeeze_price_threshold", 0.01)
            volume_up = row.get("volume_ratio", 1) > cfg.get("squeeze_volume_ratio", 1.5)
            
            is_squeeze = (
                funding > cfg["squeeze_funding_threshold"] and
                price_up and
                volume_up
            )
            
            if is_squeeze:
                event = PlaybookEvent(
                    playbook_id=f"squeeze_{i}",
                    playbook_type=PlaybookType.SHORT_SQUEEZE,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    intensity=min(1.0, funding / 0.001),
                    conditions={
                        "funding_rate": funding,
                        "return_5m": row.get("return_5m", 0),
                        "volume_ratio": row.get("volume_ratio", 1),
                    },
                    regime=row.get("regime", "ranging"),
                    session=row.get("session", "unknown"),
                    is_weekend=row.get("is_weekend", False),
                )
                events.append(event)
        
        logger.info(f"Detected {len(events)} Short Squeeze events")
        return events
    
    def _detect_volume_climax_events(self, df: pd.DataFrame) -> List[PlaybookEvent]:
        """检测Volume Climax事件"""
        events = []
        cfg = self.config
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            is_climax = (
                row.get("volume_ratio", 1) > cfg["climax_volume_ratio"] and
                abs(row.get("return_5m", 0)) > cfg.get("climax_return_threshold", 0.02)
            )
            
            if is_climax:
                event = PlaybookEvent(
                    playbook_id=f"climax_{i}",
                    playbook_type=PlaybookType.VOLUME_CLIMAX,
                    timestamp=row["timestamp"],
                    symbol=row.get("symbol", "BTCUSDT"),
                    price=row["close"],
                    intensity=min(1.0, row.get("volume_ratio", 1) / 5.0),
                    conditions={
                        "return_5m": row.get("return_5m", 0),
                        "volume_ratio": row.get("volume_ratio", 1),
                        "rsi_14": row.get("rsi_14", 50),
                        "funding_rate": row.get("funding_rate", 0),
                    },
                    regime=row.get("regime", "ranging"),
                    session=row.get("session", "unknown"),
                    is_weekend=row.get("is_weekend", False),
                )
                events.append(event)
        
        logger.info(f"Detected {len(events)} Volume Climax events")
        return events
    
    # ========== Outcome Labeling ==========
    
    def _label_outcomes(
        self,
        events: List[PlaybookEvent],
        df: pd.DataFrame
    ) -> List[PlaybookEvent]:
        """标记后续结果"""
        df = df.set_index("timestamp").sort_index()
        
        for event in events:
            event_time = event.timestamp
            
            # 获取后续数据
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
            event.time_to_reversal = time_to_trough
            
            # 计算概率
            ret_5m = event.future_returns.get("5m", 0)
            ret_1h = event.future_returns.get("1h", 0)
            
            # 延续/反转概率
            if event.conditions.get("return_5m", 0) > 0:
                event.continuation_prob = 1.0 if ret_5m > 0 else 0.0
            else:
                event.continuation_prob = 1.0 if ret_5m < 0 else 0.0
            
            event.reversal_prob = 1.0 if (ret_5m * event.conditions.get("return_5m", 0) < 0) else 0.0
        
        return events
    
    # ========== Statistics ==========
    
    def _calculate_playbook_stats(
        self,
        events: List[PlaybookEvent],
        playbook_type: PlaybookType
    ) -> PlaybookStats:
        """计算Playbook统计"""
        
        # Playbook名称映射
        playbook_names = {
            PlaybookType.PANIC_REVERSAL: ("Panic Reversal", "暴跌/恐慌后修复策略"),
            PlaybookType.FAKE_BREAKOUT: ("Fake Breakout", "假突破反杀策略"),
            PlaybookType.OI_FLUSH: ("OI Flush", "OI清洗后趋势策略"),
            PlaybookType.WEEKEND_MANIPULATION: ("Weekend Manipulation", "周末低流动性操纵"),
            PlaybookType.SHORT_SQUEEZE: ("Short Squeeze", "逼空策略"),
            PlaybookType.LIQUIDATION_CASCADE: ("Liquidation Cascade", "清算连锁策略"),
            PlaybookType.VOLUME_CLIMAX: ("Volume Climax", "放量高潮衰竭策略"),
        }
        
        name, description = playbook_names.get(playbook_type, (playbook_type.value, ""))
        
        stats = PlaybookStats(
            playbook_type=playbook_type,
            playbook_name=name,
            description=description,
            total_events=len(events),
        )
        
        if not events:
            return stats
        
        # 计算各时间窗口收益
        time_windows = ["5m", "15m", "30m", "1h", "2h", "4h"]
        returns_by_window = defaultdict(list)
        
        for event in events:
            for window in time_windows:
                if window in event.future_returns:
                    returns_by_window[window].append(event.future_returns[window])
        
        # 填充统计
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
        
        # 最佳时机
        if returns_by_window["5m"] and returns_by_window["1h"]:
            rate_5m = stats.positive_rate_5m
            rate_1h = stats.positive_rate_1h
            
            if rate_1h > rate_5m:
                stats.best_entry_window = "immediate"
                stats.best_exit_window = "1h"
            else:
                stats.best_entry_window = "wait_15m"
                stats.best_exit_window = "15m"
        
        # 风险统计
        runups = [e.max_runup for e in events if e.max_runup > 0]
        drawdowns = [e.max_drawdown for e in events if e.max_drawdown > 0]
        
        if runups:
            stats.avg_max_runup = np.mean(runups)
        if drawdowns:
            stats.avg_max_drawdown = np.mean(drawdowns)
            stats.max_drawdown_prob = np.mean([e.max_drawdown > 0.01 for e in events])
        
        # 概率统计
        stats.continuation_prob = np.mean([e.continuation_prob for e in events])
        stats.reversal_prob = np.mean([e.reversal_prob for e in events])
        
        # 按市场状态分组
        by_regime = defaultdict(list)
        for event in events:
            by_regime[event.regime].append(event)
        
        stats.by_regime = {
            regime: {
                "count": len(evts),
                "avg_return_1h": np.mean([e.future_returns.get("1h", 0) for e in evts]) if evts else 0,
                "continuation_prob": np.mean([e.continuation_prob for e in evts]) if evts else 0,
            }
            for regime, evts in by_regime.items()
        }
        
        # 按会话分组
        by_session = defaultdict(list)
        for event in events:
            by_session[event.session].append(event)
        
        stats.by_session = {
            session: {
                "count": len(evts),
                "avg_return_1h": np.mean([e.future_returns.get("1h", 0) for e in evts]) if evts else 0,
            }
            for session, evts in by_session.items()
        }
        
        # 按强度分组
        low_intensity = [e for e in events if e.intensity < 0.3]
        mid_intensity = [e for e in events if 0.3 <= e.intensity < 0.7]
        high_intensity = [e for e in events if e.intensity >= 0.7]
        
        stats.by_intensity = {
            "low": {
                "count": len(low_intensity),
                "avg_return_1h": np.mean([e.future_returns.get("1h", 0) for e in low_intensity]) if low_intensity else 0,
            },
            "medium": {
                "count": len(mid_intensity),
                "avg_return_1h": np.mean([e.future_returns.get("1h", 0) for e in mid_intensity]) if mid_intensity else 0,
            },
            "high": {
                "count": len(high_intensity),
                "avg_return_1h": np.mean([e.future_returns.get("1h", 0) for e in high_intensity]) if high_intensity else 0,
            },
        }
        
        # 时段分布
        hour_counts = defaultdict(int)
        day_counts = defaultdict(int)
        
        for event in events:
            hour_counts[event.timestamp.hour] += 1
            day_counts[event.timestamp.dayofweek] += 1
        
        stats.by_hour = dict(hour_counts)
        stats.by_day = dict(day_counts)
        
        return stats
    
    def _cross_playbook_analysis(self, events: List[PlaybookEvent]) -> Dict:
        """跨Playbook分析"""
        
        # 按时间排序事件
        events = sorted(events, key=lambda e: e.timestamp)
        
        # 分析连续事件
        consecutive_analysis = {
            "panic_then_squeeze": 0,
            "breakout_then_climax": 0,
            "flush_then_breakout": 0,
        }
        
        for i in range(len(events) - 1):
            e1, e2 = events[i], events[i + 1]
            time_diff = (e2.timestamp - e1.timestamp).total_seconds() / 60
            
            if time_diff < 60:  # 1小时内
                if (e1.playbook_type == PlaybookType.PANIC_REVERSAL and 
                    e2.playbook_type == PlaybookType.SHORT_SQUEEZE):
                    consecutive_analysis["panic_then_squeeze"] += 1
                
                if (e1.playbook_type == PlaybookType.FAKE_BREAKOUT and 
                    e2.playbook_type == PlaybookType.VOLUME_CLIMAX):
                    consecutive_analysis["breakout_then_climax"] += 1
                
                if (e1.playbook_type == PlaybookType.OI_FLUSH and 
                    e2.playbook_type == PlaybookType.FAKE_BREAKOUT):
                    consecutive_analysis["flush_then_breakout"] += 1
        
        return {
            "consecutive_patterns": consecutive_analysis,
            "total_unique_hours": len(set([e.timestamp.replace(minute=0) for e in events])),
        }
    
    def print_report(self, result: Dict):
        """打印报告"""
        print("\n" + "="*80)
        print("📊 CRYPTO BEHAVIORAL PLAYBOOKS 研究报告")
        print("="*80)
        
        print(f"\n📈 总事件数: {result['total_events']}")
        
        print(f"\n📋 事件分布:")
        for playbook_type, count in sorted(result["events_by_playbook"].items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"   {playbook_type}: {count}")
        
        print("\n" + "="*80)
        print("📖 PLAYBOOKS 详细分析")
        print("="*80)
        
        for playbook_type, stats in result["playbooks"].items():
            print(f"\n{'='*80}")
            print(f"🎯 【{stats.playbook_name}】")
            print(f"   描述: {stats.description}")
            print("="*80)
            
            print(f"\n📊 基础统计:")
            print(f"   样本数: {stats.total_events}")
            print(f"   后续1小时平均收益: {stats.avg_return_1h*100:+.2f}%")
            print(f"   后续1小时正收益概率: {stats.positive_rate_1h*100:.1f}%")
            
            print(f"\n⏱️ 最佳时机:")
            print(f"   最佳入场: {stats.best_entry_window}")
            print(f"   最佳出场: {stats.best_exit_window}")
            
            print(f"\n📈 收益分布:")
            print(f"   5分钟:  {stats.avg_return_5m*100:+.2f}%")
            print(f"   15分钟: {stats.avg_return_15m*100:+.2f}%")
            print(f"   30分钟: {stats.avg_return_30m*100:+.2f}%")
            print(f"   1小时:  {stats.avg_return_1h*100:+.2f}%")
            print(f"   2小时:  {stats.avg_return_2h*100:+.2f}%")
            print(f"   4小时:  {stats.avg_return_4h*100:+.2f}%")
            
            print(f"\n⚡ 概率:")
            print(f"   延续概率: {stats.continuation_prob*100:.1f}%")
            print(f"   反转概率: {stats.reversal_prob*100:.1f}%")
            
            print(f"\n📉 风险:")
            print(f"   平均最大涨幅: {stats.avg_max_runup*100:.2f}%")
            print(f"   平均最大回撤: {stats.avg_max_drawdown*100:.2f}%")
            print(f"   超过1%回撤概率: {stats.max_drawdown_prob*100:.1f}%")
            
            if stats.by_regime:
                print(f"\n🌍 按市场状态:")
                for regime, data in stats.by_regime.items():
                    print(f"   {regime}: {data['count']}次, 平均1h收益: {data['avg_return_1h']*100:+.2f}%")
            
            if stats.by_session:
                print(f"\n🕐 按会话:")
                for session, data in stats.by_session.items():
                    print(f"   {session}: {data['count']}次, 平均1h收益: {data['avg_return_1h']*100:+.2f}%")
            
            if stats.by_intensity:
                print(f"\n💪 按强度:")
                for intensity, data in stats.by_intensity.items():
                    print(f"   {intensity}: {data['count']}次, 平均1h收益: {data['avg_return_1h']*100:+.2f}%")
        
        print("\n" + "="*80)
        print("✅ 研究完成！")
        print("="*80)


def run_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """运行完整分析"""
    system = CryptoBehavioralPlaybooks()
    result = system.analyze(df)
    system.print_report(result)
    return result
