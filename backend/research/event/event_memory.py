"""
Event Memory Database - 事件记忆库

记录并学习：
- 什么事件
- 市场通常怎么反应
- 因子表现如何变化
- regime如何转移

这是Quantified Narrative System的核心数据结构。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json


class EventType(str, Enum):
    """事件类型"""
    ETF_FLOW = "etf_flow"
    FED_POLICY = "fed_policy"
    REGULATION = "regulation"
    MACRO_DATA = "macro_data"
    EXCHANGE_NEWS = "exchange_news"
    ON_CHAIN_EVENT = "on_chain_event"
    SOCIAL_TREND = "social_trend"
    MARKET_CRASH = "market_crash"
    BLACK_SWAN = "black_swan"
    UNKNOWN = "unknown"


class Sentiment(str, Enum):
    """事件情绪"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class Urgency(str, Enum):
    """事件紧急程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class StructuredEvent:
    """结构化事件"""
    event_id: str
    event_type: EventType
    source: str  # 来源：Bloomberg, Twitter, Glassnode等
    raw_text: str
    
    # LLM理解后的结构
    sentiment: Sentiment
    urgency: Urgency
    confidence: float
    entities: List[str]  # 相关实体：["BTC", "NASDAQ", "FED"]
    narrative: str  # 事件叙事："institutional_accumulation", "regulatory_crackdown"
    
    # 时间
    event_timestamp: datetime
    ingestion_timestamp: datetime
    
    # 市场状态快照（事件前）
    pre_event_market_snapshot: Dict[str, float] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketReaction:
    """市场反应"""
    event_id: str
    event_timestamp: datetime
    
    # 多时间维度反应
    returns_5m: Optional[float]
    returns_30m: Optional[float]
    returns_1h: Optional[float]
    returns_4h: Optional[float]
    returns_1d: Optional[float]
    
    volatility_5m: Optional[float]
    volatility_1h: Optional[float]
    
    # 衍生品反应
    funding_rate_change: Optional[float]
    oi_change: Optional[float]
    liquidation_volume: Optional[float]
    basis_spread_change: Optional[float]
    
    # 市场结构变化
    spread_widening: Optional[float]
    depth_change: Optional[float]
    
    # 综合反应评分
    reaction_score: Optional[float]
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorPerformanceChange:
    """因子表现变化"""
    event_id: str
    factor_name: str
    
    # 事件前
    ic_pre: float
    rank_ic_pre: float
    turnover_pre: float
    sharpe_pre: float
    
    # 事件后
    ic_post: float
    rank_ic_post: float
    turnover_post: float
    sharpe_post: float
    
    # 变化
    ic_change: float
    effectiveness_change: float


@dataclass
class RegimeTransition:
    """市场状态转移"""
    event_id: str
    
    pre_event_regime: str
    post_event_regime: str
    transition_probability: float
    
    transition_duration: timedelta


@dataclass
class EventMemory:
    """完整事件记忆"""
    event: StructuredEvent
    reaction: MarketReaction
    factor_changes: List[FactorPerformanceChange]
    regime_transition: Optional[RegimeTransition]
    
    learned_insights: List[str] = field(default_factory=list)
    is_validated: bool = False
    is_used_for_decision: bool = False


class EventMemoryDatabase:
    """
    事件记忆数据库
    
    核心功能：
    1. 存储事件记忆
    2. 查询相似事件
    3. 学习市场反应模式
    4. 生成叙事理解
    """
    
    def __init__(self):
        self.memories: List[EventMemory] = []
        self.event_index: Dict[str, EventMemory] = {}
        self.event_type_index: Dict[EventType, List[EventMemory]] = {}
        self.narrative_index: Dict[str, List[EventMemory]] = {}
    
    def record_event_memory(
        self,
        memory: EventMemory
    ):
        """记录事件记忆"""
        self.memories.append(memory)
        self.event_index[memory.event.event_id] = memory
        
        # 按类型索引
        if memory.event.event_type not in self.event_type_index:
            self.event_type_index[memory.event.event_type] = []
        self.event_type_index[memory.event.event_type].append(memory)
        
        # 按叙事索引
        if memory.event.narrative not in self.narrative_index:
            self.narrative_index[memory.event.narrative] = []
        self.narrative_index[memory.event.narrative].append(memory)
    
    def find_similar_events(
        self,
        event_type: Optional[EventType] = None,
        narrative: Optional[str] = None,
        sentiment: Optional[Sentiment] = None,
        min_similarity: float = 0.7
    ) -> List[EventMemory]:
        """
        查找相似事件
        
        简化实现，实际可以用向量相似度
        """
        candidates = []
        
        # 筛选
        for memory in self.memories:
            match = True
            
            if event_type and memory.event.event_type != event_type:
                match = False
            if narrative and memory.event.narrative != narrative:
                match = False
            if sentiment and memory.event.sentiment != sentiment:
                match = False
            
            if match:
                candidates.append(memory)
        
        return candidates
    
    def learn_from_event(
        self,
        memory: EventMemory
    ) -> Dict[str, Any]:
        """
        从事件中学习
        
        输出学习到的洞见
        """
        insights = []
        
        # 1. 情绪 vs 真实反应
        sentiment_match = self._analyze_sentiment_match(memory)
        if sentiment_match:
            insights.append(sentiment_match)
        
        # 2. 因子表现变化
        factor_insight = self._analyze_factor_changes(memory)
        if factor_insight:
            insights.append(factor_insight)
        
        # 3. Regime转移
        if memory.regime_transition:
            insights.append(
                f"事件导致regime转移: {memory.regime_transition.pre_event_regime} → {memory.regime_transition.post_event_regime}"
            )
        
        # 存储洞见
        memory.learned_insights = insights
        
        return {
            "insights": insights,
            "event_id": memory.event.event_id,
            "reaction_score": memory.reaction.reaction_score
        }
    
    def _analyze_sentiment_match(
        self,
        memory: EventMemory
    ) -> Optional[str]:
        """分析情绪与真实反应是否一致"""
        sentiment = memory.event.sentiment
        reaction = memory.reaction
        
        if sentiment == Sentiment.BULLISH and reaction.returns_1h and reaction.returns_1h > 0:
            return f"情绪预测正确: bullish情绪对应 {reaction.returns_1h:.2%} 上涨"
        elif sentiment == Sentiment.BEARISH and reaction.returns_1h and reaction.returns_1h < 0:
            return f"情绪预测正确: bearish情绪对应 {reaction.returns_1h:.2%} 下跌"
        elif sentiment == Sentiment.BULLISH and reaction.returns_1h and reaction.returns_1h < 0:
            return f"情绪与反应背离: bullish但下跌 {reaction.returns_1h:.2%} - 可能是buy the rumor sell the news"
        elif sentiment == Sentiment.BEARISH and reaction.returns_1h and reaction.returns_1h > 0:
            return f"情绪与反应背离: bearish但上涨 {reaction.returns_1h:.2%} - 可能是利空出尽"
        
        return None
    
    def _analyze_factor_changes(
        self,
        memory: EventMemory
    ) -> Optional[str]:
        """分析因子表现变化"""
        if not memory.factor_changes:
            return None
        
        # 找出表现提升最大的因子
        best_factor = max(
            memory.factor_changes,
            key=lambda f: f.effectiveness_change
        )
        
        if best_factor.effectiveness_change > 0.1:
            return f"事件后 {best_factor.factor_name} 因子表现提升 {best_factor.effectiveness_change:.2%} - 可以考虑增加权重"
        elif best_factor.effectiveness_change < -0.1:
            return f"事件后 {best_factor.factor_name} 因子表现下降 {abs(best_factor.effectiveness_change):.2%} - 可以考虑降低权重"
        
        return None
    
    def get_narrative_insights(
        self,
        narrative: str
    ) -> Dict[str, Any]:
        """获取特定叙事的洞见"""
        if narrative not in self.narrative_index:
            return {"count": 0}
        
        memories = self.narrative_index[narrative]
        
        # 统计平均反应
        avg_return_1h = np.mean([m.reaction.returns_1h for m in memories if m.reaction.returns_1h is not None])
        avg_reaction_score = np.mean([m.reaction.reaction_score for m in memories if m.reaction.reaction_score is not None])
        
        # 常见regime转移
        regime_transitions = {}
        for m in memories:
            if m.regime_transition:
                key = f"{m.regime_transition.pre_event_regime}→{m.regime_transition.post_event_regime}"
                regime_transitions[key] = regime_transitions.get(key, 0) + 1
        
        return {
            "narrative": narrative,
            "count": len(memories),
            "avg_return_1h": avg_return_1h,
            "avg_reaction_score": avg_reaction_score,
            "common_regime_transitions": regime_transitions,
            "learned_insights": [insight for m in memories for insight in m.learned_insights]
        }
    
    def export_database(self, filepath: str):
        """导出数据库"""
        data = {
            "memories_count": len(self.memories),
            "memories": [
                {
                    "event_id": m.event.event_id,
                    "event_type": m.event.event_type.value,
                    "narrative": m.event.narrative,
                    "sentiment": m.event.sentiment.value,
                    "reaction_score": m.reaction.reaction_score,
                    "learned_insights": m.learned_insights
                }
                for m in self.memories
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)


# 示例使用
if __name__ == "__main__":
    print("="*80)
    print("  Event Memory Database - 示例")
    print("="*80)
    
    # 1. 创建数据库
    db = EventMemoryDatabase()
    
    # 2. 创建示例事件
    print("\n创建示例事件...")
    event = StructuredEvent(
        event_id="evt_001",
        event_type=EventType.ETF_FLOW,
        source="Bloomberg",
        raw_text="BlackRock ETF inflow hits record high with $500M inflow in 24h",
        sentiment=Sentiment.BULLISH,
        urgency=Urgency.MEDIUM,
        confidence=0.82,
        entities=["BTC", "BlackRock", "ETF"],
        narrative="institutional_accumulation",
        event_timestamp=datetime.now() - timedelta(hours=1),
        ingestion_timestamp=datetime.now(),
        pre_event_market_snapshot={"btc_price": 50000}
    )
    
    # 3. 创建市场反应
    reaction = MarketReaction(
        event_id="evt_001",
        event_timestamp=datetime.now() - timedelta(hours=1),
        returns_5m=0.002,
        returns_30m=0.008,
        returns_1h=0.015,
        returns_4h=0.025,
        returns_1d=0.032,
        volatility_5m=0.005,
        volatility_1h=0.008,
        funding_rate_change=0.0002,
        oi_change=0.05,
        liquidation_volume=200000,
        basis_spread_change=0.001,
        reaction_score=0.75
    )
    
    # 4. 创建因子变化
    factor_change_mom = FactorPerformanceChange(
        event_id="evt_001",
        factor_name="momentum",
        ic_pre=0.02,
        rank_ic_pre=0.018,
        turnover_pre=0.35,
        sharpe_pre=1.2,
        ic_post=0.04,
        rank_ic_post=0.035,
        turnover_post=0.4,
        sharpe_post=1.8,
        ic_change=0.02,
        effectiveness_change=0.5
    )
    
    factor_change_mr = FactorPerformanceChange(
        event_id="evt_001",
        factor_name="mean_reversion",
        ic_pre=0.025,
        rank_ic_pre=0.02,
        turnover_pre=0.45,
        sharpe_pre=1.1,
        ic_post=0.01,
        rank_ic_post=0.008,
        turnover_post=0.35,
        sharpe_post=0.8,
        ic_change=-0.015,
        effectiveness_change=-0.27
    )
    
    # 5. 创建regime转移
    regime_trans = RegimeTransition(
        event_id="evt_001",
        pre_event_regime="range_bound",
        post_event_regime="trend",
        transition_probability=0.78,
        transition_duration=timedelta(hours=4)
    )
    
    # 6. 存入记忆
    memory = EventMemory(
        event=event,
        reaction=reaction,
        factor_changes=[factor_change_mom, factor_change_mr],
        regime_transition=regime_trans
    )
    
    # 7. 学习
    print("从事件中学习...")
    learning = db.learn_from_event(memory)
    print(f"  学到洞见: {len(learning['insights'])}个")
    for insight in learning['insights']:
        print(f"    - {insight}")
    
    # 8. 记录到数据库
    db.record_event_memory(memory)
    
    # 9. 查询叙事洞见
    print("\n查询叙事洞见...")
    narrative_insights = db.get_narrative_insights("institutional_accumulation")
    print(f"  叙事: {narrative_insights['narrative']}")
    print(f"  事件数: {narrative_insights['count']}")
    print(f"  平均1h收益: {narrative_insights['avg_return_1h']:.2%}")
    
    print("\n" + "="*80)
    print("  事件记忆库系统示例完成")
    print("="*80)
    print("""
    这个系统的价值：
    
    1. 长期积累市场对什么事件怎么反应
    2. 自动学习因子表现如何随事件变化
    3. 形成narrative库，可以快速查找相似历史情况
    4. 为动态调整因子权重提供数据支撑
    """)

