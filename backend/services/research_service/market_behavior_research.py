"""
市场行为研究系统 (Market Behavior Research System)

核心功能：
1. Event Detection（事件检测）
2. Outcome Labeling（后续标签）
3. Duration Statistics（持续时间统计）
4. State Classification（市场状态分类）
5. Market Playbook Database（市场行为数据库）

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

logger = get_logger("market_behavior_research")


class EventType(str, Enum):
    """事件类型"""
    SPIKE_UP = "spike_up"
    SPIKE_DOWN = "spike_down"
    BREAKOUT_HIGH = "breakout_high"
    BREAKOUT_LOW = "breakout_low"
    PANIC_DUMP = "panic_dump"
    SQUEEZE = "squeeze"
    COMPRESSION = "compression"
    EXHAUSTION = "exhaustion"
    VOLUME_CLIMAX = "volume_climax"
    FUNDING_EXTREME = "funding_extreme"
    OI_DIVERGENCE = "oi_divergence"


class MarketState(str, Enum):
    """市场状态"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    BREAKOUT = "breakout"
    PANIC = "panic"
    RECOVERY = "recovery"
    COMPRESSION = "compression"
    DISTRIBUTION = "distribution"
    RANGING = "ranging"


@dataclass
class MarketEvent:
    """市场事件"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    symbol: str
    price: float
    intensity: float  # 事件强度 (0-1)
    
    # 事件详情
    returns_5m: float = 0.0
    returns_1h: float = 0.0
    volume_ratio: float = 1.0
    funding_rate: float = 0.0
    oi_change: float = 0.0
    
    # 上下文
    position_in_range: float = 0.5
    volatility: float = 0.0
    regime: str = "ranging"
    
    # 后续结果（Label）
    future_returns: Dict[str, float] = field(default_factory=dict)
    max_runup: float = 0.0
    max_drawdown: float = 0.0
    time_to_peak: int = 0
    time_to_reversal: int = 0
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0
    
    # 统计（统计结果）
    avg_duration: float = 0.0
    avg_max_runup: float = 0.0
    avg_max_drawdown: float = 0.0
    best_entry_delay: int = 0
    best_exit_delay: int = 0
    sample_count: int = 0


@dataclass
class MarketPlaybook:
    """市场行为手册"""
    playbook_id: str
    name: str
    description: str
    
    # 触发条件
    trigger_conditions: Dict[str, Any] = field(default_factory=dict)
    
    # 统计结果
    event_count: int = 0
    success_rate: float = 0.0
    avg_return: float = 0.0
    avg_duration: float = 0.0
    avg_max_runup: float = 0.0
    avg_max_drawdown: float = 0.0
    
    # 时间分布
    time_to_profitable: List[float] = field(default_factory=list)
    time_to_max_drawdown: List[float] = field(default_factory=list)
    
    # 条件分布
    conditions_distribution: Dict[str, float] = field(default_factory=dict)
    
    # 示例事件
    recent_events: List[MarketEvent] = field(default_factory=list)


class EventDetector:
    """事件检测器"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        logger.info(f"EventDetector initialized with config: {self.config}")
    
    def _default_config(self) -> Dict:
        return {
            "spike_threshold": 0.04,  # 4%
            "major_spike_threshold": 0.05,  # 5%
            "breakout_threshold": 0.02,  # 2%
            "volume_spike_threshold": 2.0,  # 2x average
            "funding_extreme_threshold": 0.001,  # 0.1%
            "compression_threshold": 0.01,  # 1%
        }
    
    def detect_events(self, df: pd.DataFrame) -> List[MarketEvent]:
        """
        检测所有事件
        
        Args:
            df: 市场数据（包含OHLCV, features等）
            
        Returns:
            事件列表
        """
        events = []
        df = df.copy()
        
        # 计算基础指标
        df["return_5m"] = df["close"].pct_change(5)
        df["return_1h"] = df["close"].pct_change(60)
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(24).mean()
        df["volatility"] = df["close"].pct_change().rolling(24).std()
        
        for i, row in df.iterrows():
            if i < 60:  # 需要足够历史数据
                continue
            
            # 检测各类事件
            detected = self._detect_single_bar(row, i, df)
            events.extend(detected)
        
        logger.info(f"Detected {len(events)} events")
        return events
    
    def _detect_single_bar(self, row: pd.Series, idx: int, df: pd.DataFrame) -> List[MarketEvent]:
        """检测单个bar的事件"""
        events = []
        
        # 1. Spike Up
        if row["return_5m"] > self.config["spike_threshold"]:
            event = self._create_event(
                EventType.SPIKE_UP, row, idx,
                intensity=row["return_5m"] / self.config["major_spike_threshold"]
            )
            events.append(event)
        
        # 2. Spike Down
        if row["return_5m"] < -self.config["spike_threshold"]:
            event = self._create_event(
                EventType.SPIKE_DOWN, row, idx,
                intensity=abs(row["return_5m"]) / self.config["major_spike_threshold"]
            )
            events.append(event)
        
        # 3. Breakout High
        rolling_high = df["high"].iloc[idx-60:idx].max()
        if row["high"] > rolling_high * (1 + self.config["breakout_threshold"]):
            event = self._create_event(
                EventType.BREAKOUT_HIGH, row, idx,
                intensity=(row["high"] - rolling_high) / rolling_high
            )
            events.append(event)
        
        # 4. Breakout Low
        rolling_low = df["low"].iloc[idx-60:idx].min()
        if row["low"] < rolling_low * (1 - self.config["breakout_threshold"]):
            event = self._create_event(
                EventType.BREAKOUT_LOW, row, idx,
                intensity=(rolling_low - row["low"]) / rolling_low
            )
            events.append(event)
        
        # 5. Volume Spike
        if row["volume_ratio"] > self.config["volume_spike_threshold"]:
            if row["return_5m"] > 0:
                event = self._create_event(
                    EventType.VOLUME_CLIMAX, row, idx,
                    intensity=row["volume_ratio"] / 3.0
                )
                events.append(event)
        
        # 6. Panic Dump (大跌 + 高volume)
        if row["return_1h"] < -0.03 and row["volume_ratio"] > 2.0:
            event = self._create_event(
                EventType.PANIC_DUMP, row, idx,
                intensity=abs(row["return_1h"]) * row["volume_ratio"]
            )
            events.append(event)
        
        return events
    
    def _create_event(self, event_type: EventType, row: pd.Series, idx: int, intensity: float = 1.0) -> MarketEvent:
        """创建事件对象"""
        return MarketEvent(
            event_id=f"{event_type.value}_{idx}",
            event_type=event_type,
            timestamp=row["timestamp"] if "timestamp" in row else datetime.now(),
            symbol=row.get("symbol", "BTCUSDT"),
            price=row["close"],
            intensity=min(1.0, intensity),
            returns_5m=row.get("return_5m", 0),
            returns_1h=row.get("return_1h", 0),
            volume_ratio=row.get("volume_ratio", 1.0),
            funding_rate=row.get("funding_rate", 0),
            oi_change=row.get("oi_change_1h", 0),
            position_in_range=row.get("position_in_range_24h", 0.5),
            volatility=row.get("volatility", 0),
            regime=row.get("regime", "ranging"),
        )


class OutcomeLabeler:
    """后续标签生成器"""
    
    def __init__(self):
        logger.info("OutcomeLabeler initialized")
    
    def label_outcomes(
        self,
        events: List[MarketEvent],
        df: pd.DataFrame
    ) -> List[MarketEvent]:
        """
        为每个事件标记后续结果
        
        Args:
            events: 事件列表
            df: 市场数据
            
        Returns:
            带标签的事件列表
        """
        # 创建时间索引
        df = df.set_index("timestamp").sort_index()
        
        for event in events:
            try:
                event = self._label_single_event(event, df)
            except Exception as e:
                logger.warning(f"Failed to label event {event.event_id}: {e}")
        
        logger.info(f"Labeled {len(events)} events")
        return events
    
    def _label_single_event(self, event: MarketEvent, df: pd.DataFrame) -> MarketEvent:
        """标记单个事件的后续"""
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
                
                # 跟踪最大值/最小值
                if future_price > max_price:
                    max_price = future_price
                    time_to_peak = bars
                if future_price < min_price:
                    min_price = future_price
                    time_to_trough = bars
                    
            except:
                pass
        
        # 计算最大涨幅和最大回撤
        event.max_runup = (max_price - entry_price) / entry_price
        event.max_drawdown = (entry_price - min_price) / entry_price
        event.time_to_peak = time_to_peak
        event.time_to_reversal = time_to_trough
        
        # 计算持续/反转概率
        if event.future_returns:
            ret_5m = event.future_returns.get("5m", 0)
            ret_15m = event.future_returns.get("15m", 0)
            ret_1h = event.future_returns.get("1h", 0)
            
            # 持续概率（同方向）
            continuation = (ret_5m * event.returns_5m >= 0)
            event.continuation_prob = 1.0 if continuation else 0.0
            
            # 反转概率（反向）
            reversal = (ret_5m * event.returns_5m < 0 and abs(ret_5m) > 0.005)
            event.reversal_prob = 1.0 if reversal else 0.0
        
        return event


class DurationStatistics:
    """持续时间统计"""
    
    def __init__(self):
        logger.info("DurationStatistics initialized")
    
    def calculate_duration_stats(
        self,
        events: List[MarketEvent],
        event_type: Optional[EventType] = None
    ) -> Dict[str, Any]:
        """
        计算事件的持续时间统计
        
        Args:
            events: 事件列表
            event_type: 可选，筛选特定事件类型
            
        Returns:
            统计结果字典
        """
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if not events:
            return {}
        
        # 时间分布统计
        time_to_peak = [e.time_to_peak for e in events if e.time_to_peak > 0]
        time_to_reversal = [e.time_to_reversal for e in events if e.time_to_reversal > 0]
        
        # 收益统计
        max_runups = [e.max_runup for e in events if e.max_runup > 0]
        max_drawdowns = [e.max_drawdown for e in events if e.max_drawdown > 0]
        
        # 按时间窗口统计
        time_windows = ["5m", "15m", "30m", "1h", "2h", "4h"]
        returns_by_window = defaultdict(list)
        
        for event in events:
            for window in time_windows:
                if window in event.future_returns:
                    returns_by_window[window].append(event.future_returns[window])
        
        stats = {
            "event_type": event_type.value if event_type else "all",
            "sample_count": len(events),
            
            # 持续时间统计
            "avg_duration_to_peak": np.mean(time_to_peak) if time_to_peak else 0,
            "median_duration_to_peak": np.median(time_to_peak) if time_to_peak else 0,
            "avg_duration_to_reversal": np.mean(time_to_reversal) if time_to_reversal else 0,
            
            # 收益统计
            "avg_max_runup": np.mean(max_runups) if max_runups else 0,
            "median_max_runup": np.median(max_runups) if max_runups else 0,
            "avg_max_drawdown": np.mean(max_drawdowns) if max_drawdowns else 0,
            
            # 时间窗口收益
            "returns_by_window": {
                window: {
                    "mean": np.mean(rets) if rets else 0,
                    "median": np.median(rets) if rets else 0,
                    "std": np.std(rets) if rets else 0,
                    "positive_rate": np.mean([r > 0 for r in rets]) if rets else 0,
                    "count": len(rets)
                }
                for window, rets in returns_by_window.items()
            },
        }
        
        # 计算最佳入场/出场时间
        stats["best_entry_window"] = self._find_best_entry(stats["returns_by_window"])
        stats["best_exit_window"] = self._find_best_exit(stats["returns_by_window"])
        
        return stats
    
    def _find_best_entry(self, returns_stats: Dict) -> str:
        """找到最佳入场时间窗口"""
        if not returns_stats:
            return "unknown"
        
        try:
            best_window = max(
                returns_stats.keys(),
                key=lambda w: returns_stats[w]["positive_rate"]
            )
            return best_window
        except:
            return "unknown"
    
    def _find_best_exit(self, returns_stats: Dict) -> str:
        """找到最佳出场时间窗口"""
        if not returns_stats:
            return "unknown"
        
        try:
            best_window = max(
                returns_stats.keys(),
                key=lambda w: returns_stats[w]["mean"]
            )
            return best_window
        except:
            return "unknown"


class MarketPlaybookGenerator:
    """市场行为手册生成器"""
    
    def __init__(self):
        logger.info("MarketPlaybookGenerator initialized")
    
    def generate_playbooks(
        self,
        events: List[MarketEvent],
        config: Optional[Dict] = None
    ) -> List[MarketPlaybook]:
        """
        生成市场行为手册
        
        Args:
            events: 事件列表
            config: 可选配置
            
        Returns:
            Playbook列表
        """
        playbooks = []
        
        # 1. Spike Continuation Playbook
        spike_up_events = [e for e in events if e.event_type == EventType.SPIKE_UP]
        if spike_up_events:
            playbook = self._generate_spike_playbook(spike_up_events, "continuation")
            playbooks.append(playbook)
        
        # 2. Panic Reversal Playbook
        panic_events = [e for e in events if e.event_type == EventType.PANIC_DUMP]
        if panic_events:
            playbook = self._generate_panic_playbook(panic_events)
            playbooks.append(playbook)
        
        # 3. Breakout Playbook
        breakout_events = [e for e in events if e.event_type == EventType.BREAKOUT_HIGH]
        if breakout_events:
            playbook = self._generate_breakout_playbook(breakout_events)
            playbooks.append(playbook)
        
        # 4. Volume Climax Playbook
        climax_events = [e for e in events if e.event_type == EventType.VOLUME_CLIMAX]
        if climax_events:
            playbook = self._generate_climax_playbook(climax_events)
            playbooks.append(playbook)
        
        logger.info(f"Generated {len(playbooks)} playbooks")
        return playbooks
    
    def _generate_spike_playbook(
        self,
        events: List[MarketEvent],
        playbook_type: str
    ) -> MarketPlaybook:
        """生成Spike行为手册"""
        stats = DurationStatistics().calculate_duration_stats(events)
        
        playbook = MarketPlaybook(
            playbook_id="spike_continuation",
            name="暴涨后惯性延续策略",
            description="研究暴涨后的持续性和最佳入场/出场时机",
            trigger_conditions={
                "return_5m": "> 4%",
                "volume_ratio": "> 1.5",
                "position_in_range": "< 0.8"
            },
            event_count=len(events),
            success_rate=stats.get("returns_by_window", {}).get("5m", {}).get("positive_rate", 0),
            avg_return=stats.get("returns_by_window", {}).get("15m", {}).get("mean", 0),
            avg_duration=stats.get("avg_duration_to_peak", 0),
            avg_max_runup=stats.get("avg_max_runup", 0),
            avg_max_drawdown=stats.get("avg_max_drawdown", 0),
            recent_events=events[:10]
        )
        
        return playbook
    
    def _generate_panic_playbook(
        self,
        events: List[MarketEvent]
    ) -> MarketPlaybook:
        """生成恐慌反转手册"""
        stats = DurationStatistics().calculate_duration_stats(events)
        
        playbook = MarketPlaybook(
            playbook_id="panic_reversal",
            name="恐慌后修复策略",
            description="研究暴跌/恐慌后的反弹修复规律",
            trigger_conditions={
                "return_1h": "< -3%",
                "volume_ratio": "> 2.0",
                "regime": "panic"
            },
            event_count=len(events),
            success_rate=stats.get("returns_by_window", {}).get("30m", {}).get("positive_rate", 0),
            avg_return=stats.get("returns_by_window", {}).get("1h", {}).get("mean", 0),
            avg_duration=stats.get("avg_duration_to_reversal", 0),
            avg_max_runup=stats.get("avg_max_runup", 0),
            avg_max_drawdown=stats.get("avg_max_drawdown", 0),
            recent_events=events[:10]
        )
        
        return playbook
    
    def _generate_breakout_playbook(
        self,
        events: List[MarketEvent]
    ) -> MarketPlaybook:
        """生成突破策略手册"""
        stats = DurationStatistics().calculate_duration_stats(events)
        
        playbook = MarketPlaybook(
            playbook_id="breakout_continuation",
            name="突破趋势策略",
            description="研究突破后的趋势延续性",
            trigger_conditions={
                "breakout_threshold": "> 2%",
                "volume_ratio": "> 1.5"
            },
            event_count=len(events),
            success_rate=stats.get("returns_by_window", {}).get("1h", {}).get("positive_rate", 0),
            avg_return=stats.get("returns_by_window", {}).get("2h", {}).get("mean", 0),
            avg_duration=stats.get("avg_duration_to_peak", 0),
            avg_max_runup=stats.get("avg_max_runup", 0),
            avg_max_drawdown=stats.get("avg_max_drawdown", 0),
            recent_events=events[:10]
        )
        
        return playbook
    
    def _generate_climax_playbook(
        self,
        events: List[MarketEvent]
    ) -> MarketPlaybook:
        """生成放量高潮手册"""
        stats = DurationStatistics().calculate_duration_stats(events)
        
        playbook = MarketPlaybook(
            playbook_id="volume_climax_fade",
            name="放量高潮衰竭策略",
            description="研究放量高潮后的回调/衰竭规律",
            trigger_conditions={
                "volume_ratio": "> 3.0",
                "return_5m": "> 3%",
                "position_in_range": "> 0.7"
            },
            event_count=len(events),
            success_rate=1 - stats.get("returns_by_window", {}).get("15m", {}).get("positive_rate", 0.5),
            avg_return=-stats.get("returns_by_window", {}).get("30m", {}).get("mean", 0),
            avg_duration=stats.get("avg_duration_to_reversal", 0),
            avg_max_runup=stats.get("avg_max_runup", 0),
            avg_max_drawdown=stats.get("avg_max_drawdown", 0),
            recent_events=events[:10]
        )
        
        return playbook


class MarketBehaviorResearchSystem:
    """市场行为研究系统"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # 初始化各模块
        self.event_detector = EventDetector(self.config.get("event_detector"))
        self.outcome_labeler = OutcomeLabeler()
        self.duration_stats = DurationStatistics()
        self.playbook_generator = MarketPlaybookGenerator()
        
        logger.info("MarketBehaviorResearchSystem initialized")
    
    def analyze(
        self,
        df: pd.DataFrame,
        event_types: Optional[List[EventType]] = None
    ) -> Dict[str, Any]:
        """
        完整分析流程
        
        Args:
            df: 市场数据
            event_types: 可选，筛选特定事件类型
            
        Returns:
            分析结果
        """
        logger.info(f"Starting analysis with {len(df)} rows")
        
        # Step 1: 事件检测
        logger.info("Step 1: Detecting events...")
        events = self.event_detector.detect_events(df)
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        # Step 2: 后续标签
        logger.info("Step 2: Labeling outcomes...")
        events = self.outcome_labeler.label_outcomes(events, df)
        
        # Step 3: 统计
        logger.info("Step 3: Calculating statistics...")
        all_stats = self.duration_stats.calculate_duration_stats(events)
        
        stats_by_type = {}
        for event_type in EventType:
            type_stats = self.duration_stats.calculate_duration_stats(events, event_type)
            if type_stats:
                stats_by_type[event_type.value] = type_stats
        
        # Step 4: 生成Playbook
        logger.info("Step 4: Generating playbooks...")
        playbooks = self.playbook_generator.generate_playbooks(events, self.config)
        
        result = {
            "total_events": len(events),
            "events_by_type": {
                et.value: len([e for e in events if e.event_type == et])
                for et in EventType
            },
            "overall_stats": all_stats,
            "stats_by_event_type": stats_by_type,
            "playbooks": [
                {
                    "id": p.playbook_id,
                    "name": p.name,
                    "description": p.description,
                    "event_count": p.event_count,
                    "success_rate": p.success_rate,
                    "avg_return": p.avg_return,
                    "avg_duration": p.avg_duration,
                }
                for p in playbooks
            ]
        }
        
        logger.info(f"Analysis complete: {len(events)} events, {len(playbooks)} playbooks")
        return result
    
    def print_report(self, result: Dict):
        """打印分析报告"""
        print("\n" + "="*70)
        print("📊 市场行为研究报告")
        print("="*70)
        
        print(f"\n📈 总事件数: {result['total_events']}")
        
        print(f"\n📋 事件分布:")
        for event_type, count in sorted(result["events_by_type"].items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"   {event_type}: {count}")
        
        print(f"\n📊 整体统计:")
        overall = result["overall_stats"]
        if overall:
            print(f"   平均持续时间: {overall.get('avg_duration_to_peak', 0):.1f} 分钟")
            print(f"   平均最大涨幅: {overall.get('avg_max_runup', 0)*100:.2f}%")
            print(f"   平均最大回撤: {overall.get('avg_max_drawdown', 0)*100:.2f}%")
        
        print(f"\n📖 Playbooks:")
        for playbook in result["playbooks"]:
            print(f"\n   【{playbook['name']}】")
            print(f"   描述: {playbook['description']}")
            print(f"   样本数: {playbook['event_count']}")
            print(f"   成功率: {playbook['success_rate']*100:.1f}%")
            print(f"   平均收益: {playbook['avg_return']*100:.2f}%")
            print(f"   平均持续: {playbook['avg_duration']:.1f} 分钟")
        
        print("\n" + "="*70)


# 便捷函数
def run_market_behavior_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """运行市场行为分析"""
    system = MarketBehaviorResearchSystem()
    result = system.analyze(df)
    system.print_report(result)
    return result
