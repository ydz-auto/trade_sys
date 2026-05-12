"""
Intelligence Hub - 情报中心
整合所有情报源，为 LLM 和交易系统提供统一的情报接口

数据流：
Raw Data Layer (RSS/API/Crawl)
    ↓
Semantic Intelligence Layer
    ↓
Factor Engine

功能：
- 整合 Odaily Skill / 新闻 / Twitter / 链上数据
- LLM 总结
- 事件提取
- Regime 标记
- 情绪分析
- Narrative 聚类
- 风险事件检测
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)

logger = get_logger("intelligence.hub")


@dataclass
class MarketContext:
    """市场上下文"""
    regime: str  # bull/bear/neutral/volatile
    regime_confidence: float
    narratives: List[str]
    risk_level: str  # low/medium/high
    fear_greed_index: int
    dominant_sentiment: str
    key_events: List[Dict]
    whale_signals: List[Dict]
    recommended_exposure: Dict[str, str]


@dataclass
class EnrichedNews:
    """增强后的新闻"""
    id: str
    title: str
    summary: str
    sentiment: str
    sentiment_score: float
    affected_symbols: List[str]
    importance: str  # critical/high/medium/low
    regime_relevance: float  # 0-1, 与当前市场状态的相关性
    event_type: str  # regulatory/technical/fundamental/social
    narratives: List[str]
    raw_data: Dict


@dataclass
class IntelligenceReport:
    """情报报告"""
    timestamp: int
    market_context: MarketContext
    enriched_news: List[EnrichedNews]
    event_signals: List[Dict]
    whale_activity: List[Dict]
    tomorrow_events: List[Dict]
    regime_changes: List[str]
    risk_alerts: List[str]


class IntelligenceHub:
    """情报中心
    
    作为 Semantic Intelligence Layer，整合所有数据源
    """
    
    def __init__(self):
        # 组件
        self._components: Dict[str, Any] = {}
        
        # 熔断器
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="intelligence_hub_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        
        # 缓存
        self._cache: Dict = {}
        self._cache_ttl = 300  # 5分钟
        
        # LLM 客户端（待初始化）
        self._llm_client = None
        
        logger.info("IntelligenceHub initialized")
    
    def register_component(self, name: str, component: Any):
        """注册组件"""
        self._components[name] = component
        logger.info(f"Registered intelligence component: {name}")
    
    async def get_intelligence_report(self) -> IntelligenceReport:
        """获取完整情报报告"""
        now = int(datetime.now().timestamp())
        
        try:
            # 并行获取所有数据
            context_task = self._get_market_context()
            news_task = self._get_enriched_news()
            signals_task = self._get_event_signals()
            
            context, news, signals = await asyncio.gather(
                context_task, news_task, signals_task
            )
            
            return IntelligenceReport(
                timestamp=now,
                market_context=context,
                enriched_news=news,
                event_signals=signals.get("events", []),
                whale_activity=signals.get("whales", []),
                tomorrow_events=signals.get("tomorrow", []),
                regime_changes=signals.get("regime_changes", []),
                risk_alerts=signals.get("risk_alerts", [])
            )
            
        except Exception as e:
            logger.error(f"Failed to generate intelligence report: {e}")
            return IntelligenceReport(
                timestamp=now,
                market_context=MarketContext(
                    regime="unknown",
                    regime_confidence=0,
                    narratives=[],
                    risk_level="unknown",
                    fear_greed_index=50,
                    dominant_sentiment="neutral",
                    key_events=[],
                    whale_signals=[],
                    recommended_exposure={}
                ),
                enriched_news=[],
                event_signals=[],
                whale_activity=[],
                tomorrow_events=[],
                regime_changes=[],
                risk_alerts=["情报获取失败"]
            )
    
    async def _get_market_context(self) -> MarketContext:
        """获取市场上下文"""
        # 获取 Odaily Skill 数据
        odaily = self._components.get("odaily")
        
        if odaily:
            try:
                regime_context = await odaily.get_regime_context()
                analysis = await odaily.get_market_analysis()
                
                return MarketContext(
                    regime=regime_context.get("current_regime", "unknown"),
                    regime_confidence=regime_context.get("regime_confidence", 0),
                    narratives=regime_context.get("narratives", []),
                    risk_level=regime_context.get("risk_level", "medium"),
                    fear_greed_index=analysis.fear_greed_index if analysis else 50,
                    dominant_sentiment=self._get_sentiment_from_regime(
                        regime_context.get("current_regime", "unknown")
                    ),
                    key_events=[],
                    whale_signals=[],
                    recommended_exposure=regime_context.get("recommended_exposure", {})
                )
            except Exception as e:
                logger.warning(f"Failed to get Odaily context: {e}")
        
        # 默认返回
        return MarketContext(
            regime="neutral",
            regime_confidence=0.5,
            narratives=["观察中"],
            risk_level="medium",
            fear_greed_index=50,
            dominant_sentiment="neutral",
            key_events=[],
            whale_signals=[],
            recommended_exposure={}
        )
    
    async def _get_enriched_news(self) -> List[EnrichedNews]:
        """获取增强后的新闻"""
        news_collector = self._components.get("news")
        
        if not news_collector:
            return []
        
        try:
            result = await news_collector.collect_with_resilience()
            
            if not result.success or not result.data:
                return []
            
            enriched = []
            for news in result.data[:10]:
                enriched.append(EnrichedNews(
                    id=news.get("id", ""),
                    title=news.get("title", ""),
                    summary=news.get("content", "")[:200],
                    sentiment=news.get("sentiment", "neutral"),
                    sentiment_score=news.get("sentiment_score", 0.5),
                    affected_symbols=news.get("affected_symbols", []),
                    importance=self._assess_importance(news),
                    regime_relevance=self._assess_regime_relevance(news),
                    event_type=self._classify_event_type(news),
                    narratives=self._extract_narratives(news),
                    raw_data=news
                ))
            
            return enriched
            
        except Exception as e:
            logger.error(f"Failed to enrich news: {e}")
            return []
    
    async def _get_event_signals(self) -> Dict:
        """获取事件信号"""
        odaily = self._components.get("odaily")
        
        signals = {
            "events": [],
            "whales": [],
            "tomorrow": [],
            "regime_changes": [],
            "risk_alerts": []
        }
        
        if odaily:
            try:
                # 获取巨鲸信号
                whales = await odaily.get_whale_alerts()
                signals["whales"] = [
                    {
                        "symbol": w.symbol,
                        "type": w.activity_type,
                        "value_usd": w.value_usd,
                        "exchange": w.exchange
                    }
                    for w in whales if w.value_usd > 1000000
                ]
                
                # 获取明日事件
                tomorrow = await odaily.get_tomorrow_events()
                signals["tomorrow"] = [
                    {
                        "event": e.event_name,
                        "time": e.event_time,
                        "impact": e.expected_impact,
                        "symbols": e.symbols_affected,
                        "importance": e.importance.value
                    }
                    for e in tomorrow
                ]
                
                # 获取事件信号
                events = await odaily.get_event_signals()
                signals["events"] = events
                
                # 检测风险
                risk_alerts = self._detect_risk_alerts(events, whales)
                signals["risk_alerts"] = risk_alerts
                
            except Exception as e:
                logger.warning(f"Failed to get event signals: {e}")
        
        return signals
    
    def _get_sentiment_from_regime(self, regime: str) -> str:
        """从 Regime 获取情绪"""
        sentiment_map = {
            "bull": "bullish",
            "bear": "bearish",
            "neutral": "neutral",
            "volatile": "cautious"
        }
        return sentiment_map.get(regime, "neutral")
    
    def _assess_importance(self, news: Dict) -> str:
        """评估新闻重要性"""
        score = news.get("sentiment_confidence", 0.5)
        
        if score > 0.9:
            return "critical"
        elif score > 0.7:
            return "high"
        elif score > 0.5:
            return "medium"
        else:
            return "low"
    
    def _assess_regime_relevance(self, news: Dict) -> float:
        """评估与当前 Regime 的相关性"""
        # 简化版本
        keywords = ["breakout", "crash", "ETF", "regulation", "bull", "bear"]
        content = f"{news.get('title', '')} {news.get('content', '')}".lower()
        
        matches = sum(1 for kw in keywords if kw.lower() in content)
        return min(1.0, matches / 3)
    
    def _classify_event_type(self, news: Dict) -> str:
        """分类事件类型"""
        content = f"{news.get('title', '')} {news.get('content', '')}".lower()
        
        if any(kw in content for kw in ["sec", "regulation", "law", "ban"]):
            return "regulatory"
        elif any(kw in content for kw in ["technical", "breakout", "resistance", "support"]):
            return "technical"
        elif any(kw in content for kw in ["launch", "upgrade", "partnership", "adoption"]):
            return "fundamental"
        else:
            return "social"
    
    def _extract_narratives(self, news: Dict) -> List[str]:
        """提取叙事"""
        narratives = []
        content = f"{news.get('title', '')} {news.get('content', '')}".lower()
        
        narrative_keywords = {
            "ETF": ["etf", "spot", "approval"],
            "DeFi": ["defi", "lending", "dex"],
            "NFT": ["nft", "collection", "opensea"],
            "Layer2": ["layer2", "rollup", "arbitrum", "optimism"],
            "Institutional": ["institutional", "bank", "fund"]
        }
        
        for narrative, keywords in narrative_keywords.items():
            if any(kw in content for kw in keywords):
                narratives.append(narrative)
        
        return narratives
    
    def _detect_risk_alerts(
        self,
        events: List[Dict],
        whales: List
    ) -> List[str]:
        """检测风险告警"""
        alerts = []
        
        # 检测高重要性事件
        critical_events = [e for e in events if e.get("importance") == "critical"]
        if critical_events:
            alerts.append(f"发现 {len(critical_events)} 个关键事件需要关注")
        
        # 检测大额卖出
        large_sells = [w for w in whales if w.activity_type == "sell" and w.value_usd > 50000000]
        if large_sells:
            alerts.append(f"检测到大额卖出信号: {len(large_sells)} 笔 >$50M")
        
        # 检测情绪极端
        bearish_count = sum(1 for e in events if e.get("sentiment") == "bearish")
        if bearish_count > 3:
            alerts.append("市场情绪偏空，注意风险")
        
        return alerts
    
    async def generate_trading_context(self) -> Dict:
        """生成交易上下文（用于 LLM 决策）"""
        report = await self.get_intelligence_report()
        
        context = {
            "timestamp": datetime.now().isoformat(),
            "market_regime": report.market_context.regime,
            "regime_confidence": report.market_context.regime_confidence,
            "risk_level": report.market_context.risk_level,
            "fear_greed": report.market_context.fear_greed_index,
            "dominant_narratives": report.market_context.narratives,
            "recommended_exposure": report.market_context.recommended_exposure,
            
            "top_events": [
                {
                    "title": e.title,
                    "sentiment": e.sentiment,
                    "symbols": e.affected_symbols,
                    "importance": e.importance
                }
                for e in report.enriched_news[:5]
            ],
            
            "whale_alerts": report.whale_activity[:5],
            
            "tomorrow_events": report.tomorrow_events[:3],
            
            "risk_alerts": report.risk_alerts,
            
            "actionable_insights": self._generate_insights(report)
        }
        
        return context
    
    def _generate_insights(self, report: IntelligenceReport) -> List[str]:
        """生成可操作的洞察"""
        insights = []
        
        # 基于 Regime
        if report.market_context.regime == "bull":
            insights.append("当前处于牛市，建议逢低买入")
        elif report.market_context.regime == "bear":
            insights.append("当前处于熊市，建议观望或做空")
        
        # 基于叙事
        narratives = report.market_context.narratives
        if "ETF" in narratives:
            insights.append("ETF 叙事持续，关注获批预期")
        if "Institutional" in narratives:
            insights.append("机构叙事，关注大资金动向")
        
        # 基于巨鲸
        if len(report.whale_activity) > 3:
            insights.append("近期巨鲸活动频繁，关注方向")
        
        return insights


# 全局实例
_hub: Optional[IntelligenceHub] = None

def get_intelligence_hub() -> IntelligenceHub:
    """获取情报中心"""
    global _hub
    if _hub is None:
        _hub = IntelligenceHub()
    return _hub
