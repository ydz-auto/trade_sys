"""
LLM 增强模块 - 情感趋势分析、因果推断、预测评分
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("research.correlation.llm")


@dataclass
class SentimentTrend:
    """情感趋势结果"""
    timestamp: datetime
    aggregated_sentiment: float
    sentiment_volatility: float
    news_count: int
    dominant_topics: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "aggregated_sentiment": self.aggregated_sentiment,
            "sentiment_volatility": self.sentiment_volatility,
            "news_count": self.news_count,
            "dominant_topics": self.dominant_topics,
        }


@dataclass
class CausalInferenceResult:
    """因果推断结果"""
    event_type: str
    cause: str
    effect: str
    confidence: float
    time_lag_minutes: int
    supporting_evidence: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "cause": self.cause,
            "effect": self.effect,
            "confidence": self.confidence,
            "time_lag_minutes": self.time_lag_minutes,
            "supporting_evidence": self.supporting_evidence,
        }


@dataclass
class LLMPrediction:
    """LLM预测结果"""
    timestamp: datetime
    predicted_direction: str  # "up", "down", "neutral"
    confidence: float
    reasoning: str
    time_horizon: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "predicted_direction": self.predicted_direction,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "time_horizon": self.time_horizon,
        }


class LLMEnhancement:
    """
    LLM 增强分析器
    
    功能：
    1. 情感趋势分析（时间序列聚合）
    2. LLM 因果推断
    3. LLM 预测评分
    """
    
    def __init__(self):
        self.llm_pool = None
        self._init_llm_pool()
    
    def _init_llm_pool(self):
        """初始化 LLM Pool"""
        try:
            from infrastructure.llm import get_llm_pool
            self.llm_pool = get_llm_pool()
            logger.info("LLM Pool initialized for enhancement")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM Pool: {e}")
            self.llm_pool = None
    
    async def analyze_sentiment_trend(
        self,
        news_data: List[Dict],
        window_minutes: int = 60
    ) -> List[SentimentTrend]:
        """
        分析情感趋势
        
        将新闻情感聚合为时间序列趋势
        """
        if not news_data:
            return []
        
        # 按时间窗口聚合
        trends = []
        
        # 转换为 DataFrame
        df = pd.DataFrame(news_data)
        if 'published' not in df.columns:
            logger.warning("No 'published' field in news data")
            return []
        
        df['timestamp'] = pd.to_datetime(df['published'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        # 按窗口重采样
        for start_time, group in df.resample(f'{window_minutes}min'):
            if len(group) == 0:
                continue
            
            # 计算加权情感得分
            sentiments = group.get('sentiment_score', pd.Series([0.5] * len(group)))
            confidences = group.get('sentiment_confidence', pd.Series([0.5] * len(group)))
            
            weighted_sentiment = np.average(sentiments, weights=confidences)
            sentiment_std = np.std(sentiments)
            
            # 提取主要话题
            topics = self._extract_topics(group.to_dict('records'))
            
            trends.append(SentimentTrend(
                timestamp=start_time,
                aggregated_sentiment=weighted_sentiment,
                sentiment_volatility=sentiment_std,
                news_count=len(group),
                dominant_topics=topics[:5]
            ))
        
        logger.info(f"Generated {len(trends)} sentiment trend points")
        return trends
    
    def _extract_topics(self, news_items: List[Dict]) -> List[str]:
        """提取主要话题（基于关键词频率）"""
        topic_counts = defaultdict(int)
        
        for item in news_items:
            title = item.get('title', '').lower()
            
            # 简单关键词提取（实际可用更复杂的NLP）
            keywords = [
                'bitcoin', 'ethereum', 'etf', 'regulation', 'hack',
                'adoption', 'mining', 'defi', 'nft', 'cbdc',
                'federal reserve', 'inflation', 'interest rate'
            ]
            
            for kw in keywords:
                if kw in title:
                    topic_counts[kw] += 1
        
        # 按频率排序
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_topics]
    
    async def causal_inference(
        self,
        news_data: List[Dict],
        feature_matrix: Any,
        max_events: int = 10
    ) -> List[CausalInferenceResult]:
        """
        LLM 因果推断
        
        分析新闻事件与价格变动的因果关系
        """
        if not self.llm_pool or not news_data:
            logger.warning("LLM not available or no news data, skipping causal inference")
            return []
        
        results = []
        
        # 选择重要新闻（黑天鹅或高情感强度）
        important_news = self._select_important_news(news_data, max_events)
        
        for news in important_news:
            try:
                causal_result = await self._analyze_single_causality(news)
                if causal_result:
                    results.append(causal_result)
            except Exception as e:
                logger.warning(f"Causal analysis failed for news: {e}")
        
        logger.info(f"Generated {len(results)} causal inferences")
        return results
    
    def _select_important_news(
        self,
        news_data: List[Dict],
        max_events: int
    ) -> List[Dict]:
        """选择重要新闻事件"""
        scored_news = []
        
        for news in news_data:
            score = 0
            # 黑天鹅得分
            if news.get('is_black_swan'):
                score += 10
            # 情感极端度
            sentiment_score = news.get('sentiment_score', 0.5)
            score += abs(sentiment_score - 0.5) * 10
            # 置信度
            score *= news.get('sentiment_confidence', 0.5)
            
            scored_news.append((score, news))
        
        # 按重要性排序
        scored_news.sort(key=lambda x: x[0], reverse=True)
        return [n[1] for n in scored_news[:max_events]]
    
    async def _analyze_single_causality(self, news: Dict) -> Optional[CausalInferenceResult]:
        """分析单条新闻的因果性"""
        title = news.get('title', '')
        sentiment = news.get('sentiment', 'neutral')
        
        # 构建 prompt
        prompt = f"""
分析以下加密货币新闻的因果影响：

新闻标题: {title}
情感倾向: {sentiment}

请分析：
1. 这则新闻可能直接影响什么（价格/情绪/交易量）？
2. 影响的方向是正面还是负面？
3. 影响可能在多长时间后显现？
4. 置信度如何（0-1）？

请以JSON格式返回：
{{
  "cause": "新闻事件描述",
  "effect": "预期影响",
  "direction": "positive/negative/neutral",
  "time_lag_minutes": 数字,
  "confidence": 0.0-1.0
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_pool.chat(messages, temperature=0.3, max_tokens=300)
            
            if response.success:
                import json
                result = json.loads(response.text)
                
                return CausalInferenceResult(
                    event_type="news_impact",
                    cause=result.get('cause', title),
                    effect=result.get('effect', 'unknown'),
                    confidence=result.get('confidence', 0.5),
                    time_lag_minutes=result.get('time_lag_minutes', 60),
                    supporting_evidence=[title]
                )
        
        except Exception as e:
            logger.debug(f"LLM causal analysis failed: {e}")
        
        # 降级到关键词分析
        return self._keyword_causal_analysis(news)
    
    def _keyword_causal_analysis(self, news: Dict) -> CausalInferenceResult:
        """关键词因果分析（降级方案）"""
        title = news.get('title', '').lower()
        sentiment = news.get('sentiment', 'neutral')
        
        # 根据情感判断影响方向
        direction_map = {
            'bullish': 'positive',
            'bearish': 'negative',
            'neutral': 'neutral'
        }
        
        # 判断时间延迟
        if any(kw in title for kw in ['breaking', 'urgent', 'just', 'now']):
            lag = 5
        elif any(kw in title for kw in ['today', 'announced', 'released']):
            lag = 30
        else:
            lag = 60
        
        return CausalInferenceResult(
            event_type="news_impact",
            cause=news.get('title', ''),
            effect=f"price_{sentiment}",
            confidence=news.get('sentiment_confidence', 0.5),
            time_lag_minutes=lag,
            supporting_evidence=[title]
        )
    
    async def generate_predictions(
        self,
        news_data: List[Dict],
        time_horizons: List[str] = ['1h', '4h', '1d']
    ) -> Dict[str, List[LLMPrediction]]:
        """
        生成 LLM 预测评分
        
        对每个时间 horizon 生成方向预测
        """
        if not self.llm_pool or not news_data:
            return {h: [] for h in time_horizons}
        
        predictions = {h: [] for h in time_horizons}
        
        # 聚合最近的新闻
        recent_news = news_data[-20:] if len(news_data) > 20 else news_data
        news_summary = self._summarize_news(recent_news)
        
        for horizon in time_horizons:
            try:
                prediction = await self._generate_horizon_prediction(
                    news_summary, horizon
                )
                predictions[horizon].append(prediction)
            except Exception as e:
                logger.warning(f"Prediction generation failed for {horizon}: {e}")
        
        return predictions
    
    def _summarize_news(self, news_data: List[Dict]) -> str:
        """汇总新闻内容"""
        summaries = []
        for news in news_data[-10:]:  # 最近10条
            title = news.get('title', '')
            sentiment = news.get('sentiment', 'neutral')
            summaries.append(f"- [{sentiment}] {title}")
        
        return "\n".join(summaries)
    
    async def _generate_horizon_prediction(
        self,
        news_summary: str,
        horizon: str
    ) -> LLMPrediction:
        """生成特定时间 horizon 的预测"""
        prompt = f"""
基于以下加密货币新闻汇总，预测未来 {horizon} 的价格方向：

新闻汇总：
{news_summary}

请给出：
1. 预测方向（上涨/下跌/横盘）
2. 置信度（0-1）
3. 简要理由

以JSON格式返回：
{{
  "direction": "up/down/neutral",
  "confidence": 0.0-1.0,
  "reasoning": "简要理由"
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_pool.chat(messages, temperature=0.3, max_tokens=200)
            
            if response.success:
                import json
                result = json.loads(response.text)
                
                return LLMPrediction(
                    timestamp=datetime.now(),
                    predicted_direction=result.get('direction', 'neutral'),
                    confidence=result.get('confidence', 0.5),
                    reasoning=result.get('reasoning', ''),
                    time_horizon=horizon
                )
        
        except Exception as e:
            logger.debug(f"LLM prediction failed: {e}")
        
        # 默认中性预测
        return LLMPrediction(
            timestamp=datetime.now(),
            predicted_direction='neutral',
            confidence=0.5,
            reasoning='Insufficient data for prediction',
            time_horizon=horizon
        )
