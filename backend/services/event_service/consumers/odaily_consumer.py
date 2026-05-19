"""
Odaily Consumer - 消费 raw.odaily topic 并进行增强理解

数据流：
raw.odaily (Kafka)
    ↓
OdailyConsumer (LLM增强)
    ↓
Redis (news:all:20) → API
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.messaging import Topics
from infrastructure.cache import get_redis_client
from shared.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

logger = get_logger("event_service.odaily_consumer")

try:
    from faststream import FastStream
    from faststream.kafka import KafkaBroker, KafkaMessage
    FASTSTREAM_AVAILABLE = True
except ImportError:
    FASTSTREAM_AVAILABLE = False
    logger.warning("FastStream not available")


class OdailyConsumer:
    """Odaily 数据消费者
    
    消费 raw.odaily topic，使用 LLM 进行语义增强理解和智能打分
    """
    
    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        understanding_hub: Optional[Any] = None,
        llm_pool: Optional[Any] = None
    ):
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self._hub: Optional[Any] = understanding_hub
        self._llm_pool = llm_pool
        self._redis: Optional[Any] = None  # Redis 客户端
        
        # 导入 LLM 打分引擎
        try:
            from services.event_service.scoring.llm_scorer import get_llm_scorer
            self._scorer = get_llm_scorer(llm_pool)
            logger.info("LLM Scorer integrated into OdailyConsumer")
        except Exception as e:
            logger.warning(f"Failed to load LLM scorer: {e}")
            self._scorer = None
        
        self._broker: Optional[KafkaBroker] = None
        self._app: Optional[FastStream] = None
        self._running = False
        self._processed_count = 0
    
    async def initialize(self):
        """初始化"""
        # 初始化 Redis 连接
        try:
            from infrastructure.cache import init_redis
            self._redis = await init_redis()
            logger.info("Redis client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
            self._redis = None
        
        logger.info("OdailyConsumer initialized")
    
    async def connect(self) -> None:
        if not FASTSTREAM_AVAILABLE:
            logger.warning("FastStream not available")
            return
        
        try:
            self._broker = KafkaBroker(self.bootstrap_servers)
            self._app = FastStream(self._broker)
            self._running = True
            
            # 注册消费者
            @self._broker.subscriber(Topics.raw_odaily())
            async def process_odaily_message(msg: Dict[str, Any]):
                await self._handle_message(msg)
            
            logger.info("OdailyConsumer connected to Kafka topic: raw.odaily")
        except Exception as e:
            logger.error(f"Failed to connect Odaily consumer: {e}")
            self._running = False
    
    async def disconnect(self) -> None:
        self._running = False
        if self._app:
            await self._app.stop()
        logger.info("OdailyConsumer disconnected")
    
    async def start_consuming(self) -> None:
        if not self._running or not self._broker or not self._app:
            logger.warning("Consumer not connected")
            return
        
        logger.info("Starting Odaily consumer...")
        
        try:
            await self._app.start()
        except Exception as e:
            logger.error(f"Odaily consumer error: {e}")
    
    async def _handle_message(self, msg: Dict[str, Any]) -> None:
        """处理 Odaily 消息"""
        try:
            self._processed_count += 1
            
            logger.debug(f"Processing Odaily message #{self._processed_count}: {msg.get('event_id', 'unknown')}")
            
            data = msg.get("data", {})
            
            enriched = await self._enrich_odaily_data(data)
            
            if enriched:
                logger.info(f"Successfully enriched Odaily event: {enriched.get('title', '')[:50]}...")
                
                await self._store_to_redis(enriched)
                
        except Exception as e:
            logger.error(f"Error handling Odaily message: {e}")
    
    async def _store_to_redis(self, enriched: Dict[str, Any]) -> None:
        """将增强后的数据存储到 Redis (使用 List 原子操作 + 去重)"""
        try:
            if not self._redis:
                logger.warning("Redis client not available")
                return
            
            if not self._redis._connected:
                logger.warning("Redis client disconnected, reconnecting...")
                await self._redis.connect()
            
            title = enriched.get("title", "")
            if not title or not title.strip():
                logger.warning("Skipping news with empty title")
                return
            
            news_id = enriched.get("original_id", "") or f"odaily_{hash(title)}"
            
            dedup_key = f"news:dedup:{news_id}"
            exists = await self._redis.exists(dedup_key)
            if exists:
                logger.debug(f"Skipping duplicate news: {title[:30]}...")
                return
            
            news_item = {
                "id": news_id,
                "title": title,
                "content": enriched.get("content", ""),
                "source": "Odaily",
                "sentiment": enriched.get("sentiment", "neutral"),
                "sentiment_score": enriched.get("confidence", 0.5),
                "importance": enriched.get("importance", 0.5),
                "symbols": enriched.get("symbols", []),
                "narratives": enriched.get("narratives", []),
                "published": int(datetime.now().timestamp()),
                "url": enriched.get("metadata", {}).get("url"),
            }
            
            news_json = json.dumps(news_item, ensure_ascii=False)
            
            existing_news = await self._redis.lrange("news:latest", 0, -1)
            for existing in existing_news:
                try:
                    existing_data = json.loads(existing) if isinstance(existing, str) else existing
                    if existing_data.get("title") == title:
                        logger.debug(f"Skipping duplicate by title: {title[:30]}...")
                        return
                except:
                    pass
            
            await self._redis.lpush("news:latest", news_json)
            
            await self._redis.ltrim("news:latest", 0, 19)
            
            await self._redis.setex(dedup_key, 86400, "1")
            
            logger.info(f"Stored enriched news to Redis: {title[:30]}...")
            
        except Exception as e:
            logger.error(f"Failed to store to Redis: {e}")
    
    async def _enrich_odaily_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用 LLM 进行增强 + 智能打分"""
        try:
            title = data.get("title", "")
            content = data.get("content", "")
            source = data.get("source", "odaily")
            
            # 如果有 LLM 打分引擎，使用它
            if self._scorer:
                analysis_result = await self._scorer.analyze({
                    "title": title,
                    "content": content,
                    "source": source
                })
                
                # 使用 LLM 分析结果
                enriched = {
                    "original_id": data.get("id", ""),
                    "title": title,
                    "content": content,
                    "sentiment": analysis_result.sentiment,
                    "importance": analysis_result.importance,
                    "relevance": analysis_result.relevance,
                    "confidence": analysis_result.confidence,
                    "symbols": analysis_result.symbols,
                    "narratives": analysis_result.narratives,
                    "actionable": analysis_result.actionable,
                    "source_quality": analysis_result.source_quality,
                    "content_quality": analysis_result.content_quality,
                    "timeliness": analysis_result.timeliness,
                    "reasoning": analysis_result.reasoning,
                    "scored_by": analysis_result.scored_by,
                    
                    # 黑天鹅检测
                    "is_black_swan": self._detect_black_swan(title + " " + content),
                    "enriched_at": datetime.now().isoformat(),
                    "metadata": data.get("metadata", {})
                }
                
                logger.info(f"Enhanced with LLM: sentiment={analysis_result.sentiment}, "
                          f"importance={analysis_result.importance:.2f}, "
                          f"symbols={analysis_result.symbols}")
            else:
                # 降级到关键词规则
                enriched = self._enrich_with_keywords(data)
            
            return enriched
            
        except Exception as e:
            logger.error(f"Error enriching Odaily data: {e}")
            return self._enrich_with_keywords(data)
    
    def _enrich_with_keywords(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """使用关键词规则进行增强（降级方案）"""
        title = data.get("title", "")
        content = data.get("content", "")
        
        narratives = self._extract_narratives(title + " " + content)
        symbols = self._extract_symbols(title + " " + content)
        importance = self._calculate_importance(title + " " + content)
        
        return {
            "original_id": data.get("id", ""),
            "title": title,
            "content": content,
            "sentiment": self._detect_sentiment(title + " " + content),
            "importance": importance,
            "symbols": symbols,
            "narratives": narratives,
            "actionable": importance > 0.7 and len(symbols) > 0,
            "source_quality": 0.5,
            "content_quality": 0.5,
            "timeliness": 0.5,
            "reasoning": "Keyword-based scoring (fallback)",
            "scored_by": "keyword",
            "is_black_swan": self._detect_black_swan(title + " " + content),
            "enriched_at": datetime.now().isoformat(),
            "metadata": data.get("metadata", {})
        }
    
    def _extract_symbols(self, text: str) -> List[str]:
        """提取币种"""
        symbols = []
        text_upper = text.upper()
        
        symbol_map = {
            "BTC": ["BTC", "BITCOIN"],
            "ETH": ["ETH", "ETHEREUM"],
            "SOL": ["SOL", "SOLANA"],
            "XRP": ["XRP"],
            "BNB": ["BNB"],
            "DOGE": ["DOGE"],
            "ADA": ["ADA"],
            "DOT": ["DOT"],
            "AVAX": ["AVAX"],
            "LINK": ["LINK"],
        }
        
        for symbol, keywords in symbol_map.items():
            if any(kw in text_upper for kw in keywords):
                symbols.append(symbol)
        
        return symbols[:5]
    
    def _detect_sentiment(self, text: str) -> str:
        """检测情绪"""
        text_lower = text.lower()
        
        bullish_keywords = ["surge", "rally", "bullish", "上涨", "利好", "突破"]
        bearish_keywords = ["crash", "plunge", "bearish", "下跌", "利空", "暴跌"]
        
        bullish_count = sum(1 for kw in bullish_keywords if kw in text_lower)
        bearish_count = sum(1 for kw in bearish_keywords if kw in text_lower)
        
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        return "neutral"
    
    def _calculate_importance(self, text: str) -> float:
        """计算重要性"""
        text_lower = text.lower()
        
        high_importance = ["sec", "etf", "hack", "批准", "重大", "暴跌", "崩盘"]
        medium_importance = ["update", "launch", "合作", "升级"]
        
        if any(kw in text_lower for kw in high_importance):
            return 0.85
        elif any(kw in text_lower for kw in medium_importance):
            return 0.65
        return 0.5
    
    def _extract_narratives(self, text: str) -> List[str]:
        """从文本中提取叙事"""
        narratives = []
        text_lower = text.lower()
        
        narrative_keywords = {
            "ETF": ["etf", "approval", "sec", "blackrock"],
            "DeFi": ["defi", "lending", "dex", "uniswap"],
            "Regulation": ["regulation", "sec", "ban", "compliance"],
            "Institutional": ["institutional", "bank", "fund", "hedge"],
            "NFT": ["nft", "opensea"],
            "Layer2": ["layer2", "l2", "optimism", "arbitrum"],
            "Bitcoin": ["bitcoin", "btc", "halving"],
            "Ethereum": ["ethereum", "eth", "merge", "upgrade"],
        }
        
        for narrative, keywords in narrative_keywords.items():
            if any(kw in text_lower for kw in keywords):
                narratives.append(narrative)
        
        return narratives[:3]
    
    def _calculate_actionability(self, importance: float, tags: List[str], symbols: List[str]) -> float:
        """计算事件的可操作性分数"""
        score = importance * 0.5
        
        # 高优先标签
        high_priority_tags = ["etf", "sec", "hack", "critical", "high"]
        for tag in tags:
            if any(pt in tag.lower() for pt in high_priority_tags):
                score += 0.2
        
        # 有明确的符号
        if len(symbols) > 0:
            score += 0.2
        
        return min(score, 1.0)
    
    def _detect_black_swan(self, text: str) -> bool:
        """检测黑天鹅信号"""
        black_swan_keywords = [
            "hack", "exploit", "depeg", "crash", "collapse",
            "bankruptcy", "fraud", "stolen", "liquidation cascade"
        ]
        
        text_lower = text.lower()
        return any(kw in text_lower for kw in black_swan_keywords)
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def processed_count(self) -> int:
        return self._processed_count


_odaily_consumer: Optional[OdailyConsumer] = None


async def get_odaily_consumer(
    bootstrap_servers: Optional[str] = None,
    understanding_hub: Optional[Any] = None
) -> OdailyConsumer:
    """获取 Odaily Consumer 实例"""
    global _odaily_consumer
    if _odaily_consumer is None:
        _odaily_consumer = OdailyConsumer(bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS, understanding_hub)
        await _odaily_consumer.initialize()
    return _odaily_consumer
