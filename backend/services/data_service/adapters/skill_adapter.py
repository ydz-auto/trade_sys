"""
Skill Adapter Layer - Skill 适配器层

功能：
- 将各种 Skill（Odaily/PANews/金十等）输出转换为 StandardEvent
- 统一的数据格式
- 标准化处理

事件流向：
Odaily Skill ─┐
PANews Skill ─┼─→ SkillAdapter ─→ Normalization ─→ StandardEvent ─→ EventBus
金十 Skill ───┘
"""

import json
import subprocess
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import asyncio

from shared.contracts import (
    StandardEvent,
    EventType,
    Sentiment,
    Source,
    create_news_event,
    create_tweet_event,
    create_whale_event
)
from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)

logger = get_logger("skill.adapter")


class ClawHubModule(Enum):
    """ClawHub Odaily Skill 模块枚举"""
    M1_TODAY_WATCH = "get_today_watch"
    M2_MARKET_ANALYSIS = "get_crypto_market_analysis"
    M3_TOMORROW_WATCH = "get_tomorrow_watch"
    M4_WHALE_TRACKING = "scan_whale_tail_trades"
    M5_API_MODULE = "get_api_module"


@dataclass
class AdapterConfig:
    """适配器配置"""
    name: str
    source_type: str
    enabled: bool = True
    priority: int = 0
    cache_ttl: int = 300
    retry_count: int = 2


class SkillAdapter(ABC):
    """Skill 适配器基类
    
    所有 Skill 适配器都必须继承这个类。
    """
    
    def __init__(self, config: AdapterConfig = None):
        self.config = config or AdapterConfig(
            name=self.__class__.__name__,
            source_type="unknown"
        )
        
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name=f"{self.config.name}_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=config.retry_count if config else 2,
            initial_delay=1.0
        ))
        
        self._cache: Dict = {}
        self._last_fetch: int = 0
        
        logger.info(f"SkillAdapter '{self.config.name}' initialized")
    
    @abstractmethod
    async def fetch_raw_data(self) -> Any:
        """获取原始数据（由子类实现）"""
        pass
    
    @abstractmethod
    def normalize(self, raw_data: Any) -> List[StandardEvent]:
        """将原始数据转换为标准事件（由子类实现）"""
        pass
    
    async def collect(self) -> List[StandardEvent]:
        """采集并转换数据"""
        try:
            raw_data = await self.retry_policy.execute(self.fetch_raw_data)
            
            events = self.normalize(raw_data)
            logger.info(f"{self.config.name}: Fetched {len(events)} events")
            return events
            
        except Exception as e:
            logger.error(f"{self.config.name} failed: {e}")
            return []
    
    def _parse_sentiment(self, sentiment_str: str) -> str:
        """解析情绪"""
        if not sentiment_str:
            return Sentiment.NEUTRAL.value
        
        sentiment_str = sentiment_str.lower()
        
        bullish_keywords = ["bullish", "看涨", "利好", "上涨", "多头", "buy", "long", "多"]
        bearish_keywords = ["bearish", "看跌", "利空", "下跌", "空头", "sell", "short", "空"]
        
        if any(kw in sentiment_str for kw in bullish_keywords):
            return Sentiment.BULLISH.value
        if any(kw in sentiment_str for kw in bearish_keywords):
            return Sentiment.BEARISH.value
        
        return Sentiment.NEUTRAL.value
    
    def _parse_importance(self, importance_str: str) -> float:
        """解析重要性"""
        if not importance_str:
            return 0.5
        
        importance_str = importance_str.lower()
        
        critical_keywords = ["critical", "紧急", "重大", "关键", "高", "🔴"]
        high_keywords = ["high", "重要", "关注", "🟡"]
        medium_keywords = ["medium", "中等", "一般"]
        low_keywords = ["low", "低", "小", "🟢"]
        
        if any(kw in importance_str for kw in critical_keywords):
            return 1.0
        if any(kw in importance_str for kw in high_keywords):
            return 0.75
        if any(kw in importance_str for kw in medium_keywords):
            return 0.5
        if any(kw in importance_str for kw in low_keywords):
            return 0.25
        
        try:
            return float(importance_str)
        except:
            return 0.5


class ClawHubRunner:
    """ClawHub Skill 命令行执行器"""
    
    SKILL_NAME = "odaily-skill"
    
    @staticmethod
    def find_skill_dir() -> Optional[str]:
        """查找 Skill 安装目录"""
        possible_paths = [
            "/tmp/odaily-skill",
            os.path.expanduser("~/.openclaw/skills/odaily-skill"),
            os.path.expanduser("~/.claude/skills/odaily-skill"),
            os.path.expanduser("~/.openclaw/odaily-skill"),
            os.path.expanduser("~/.claude/odaily-skill"),
        ]
        
        for path in possible_paths:
            run_py = os.path.join(path, "run.py")
            if os.path.exists(run_py):
                logger.info(f"Found skill at: {path}")
                return path
        
        cmd = 'find ~/.openclaw ~/.claude -name "run.py" -path "*odai*" 2>/dev/null | head -1'
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.stdout.strip():
                skill_dir = os.path.dirname(result.stdout.strip())
                logger.info(f"Found skill via find: {skill_dir}")
                return skill_dir
        except Exception as e:
            logger.warning(f"Failed to find skill via find: {e}")
        
        return None
    
    @staticmethod
    def call_module(module: str, params: Dict = None) -> Optional[Dict]:
        """调用 ClawHub Skill 模块"""
        skill_dir = ClawHubRunner.find_skill_dir()
        
        if not skill_dir:
            logger.error("Odaily skill not found. Please install: openclaw skills install odaily-skill")
            return None
        
        params = params or {}
        params_json = json.dumps(params, ensure_ascii=False)
        
        cmd = f'cd "{skill_dir}" && python3 run.py {module} \'{params_json}\''
        
        logger.debug(f"Executing: {cmd}")
        
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Skill command failed: {result.stderr}")
                return None
            
            output = result.stdout.strip()
            if not output:
                return None
            
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                logger.debug(f"Output is not JSON, parsing as structured text")
                return ClawHubRunner._parse_markdown_output(module, output)
            
        except subprocess.TimeoutExpired:
            logger.error(f"Skill command timed out")
            return None
        except Exception as e:
            logger.error(f"Failed to execute skill: {e}")
            return None
    
    @staticmethod
    def _parse_markdown_output(module: str, text: str) -> Dict:
        """解析 Skill 输出的 Markdown 文本为结构化数据"""
        data = {"module": module, "raw": text, "articles": [], "flash_news": [], "trades": []}
        
        lines = text.split("\n")
        current_section = None
        current_items = []
        
        for line in lines:
            line = line.strip()
            
            if "📰 重点文章" in line or "📰 最新文章" in line:
                current_section = "articles"
                continue
            elif "⚡ 重要快讯" in line or "⚡ 最新快讯" in line:
                current_section = "flash_news"
                continue
            elif "Top 10 高确定性尾盘交易" in line:
                current_section = "trades"
                continue
            elif line.startswith("##") or line.startswith("---"):
                continue
            
            if current_section == "articles" and line.startswith(tuple("123456789")):
                title = line.split(". ", 1)[1] if ". " in line else line
                current_items.append({"title": title, "type": "article"})
            elif current_section == "flash_news" and line.startswith("•"):
                content = line[1:].strip()
                if content:
                    current_items.append({"title": content, "type": "flash"})
            elif current_section == "trades" and any(c.isdigit() for c in line[:3]):
                parts = line.split()
                if len(parts) >= 3:
                    data["trades"].append({"raw": line})
        
        if current_section:
            if current_section == "articles":
                data["articles"] = current_items
            elif current_section == "flash_news":
                data["flash_news"] = current_items
        
        data["has_data"] = len(data["articles"]) > 0 or len(data["flash_news"]) > 0 or len(data["trades"]) > 0
        
        return data
    
    @staticmethod
    def call_module_async(module: str, params: Dict = None) -> asyncio.Future:
        """异步调用 ClawHub Skill 模块"""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, ClawHubRunner.call_module, module, params)


class OdailySkillAdapter(SkillAdapter):
    """Odaily Skill 适配器 (ClawHub)
    
    支持 M1-M5 五个核心模块：
    - M1: 今日必关注 (get_today_watch)
    - M2: 加密市场分析 (get_crypto_market_analysis)
    - M3: 明日关注 (get_tomorrow_watch)
    - M4: 巨鲸尾盘追踪 (scan_whale_tail_trades)
    - M5: API原始数据 (get_api_module)
    """
    
    def __init__(self, config: AdapterConfig = None, modules: List[str] = None):
        if not config:
            config = AdapterConfig(
                name="OdailySkillAdapter",
                source_type="clawhub_odaily"
            )
        super().__init__(config)
        
        self.modules = modules or ["M1", "M2", "M3", "M4", "M5"]
        self.skill_available = ClawHubRunner.find_skill_dir() is not None
        
        if not self.skill_available:
            logger.warning("Odaily skill not found. Install with: openclaw skills install odaily-skill")
    
    async def fetch_raw_data(self) -> Dict:
        """获取 Odaily Skill 所有模块数据"""
        if not self.skill_available:
            return self._generate_mock_data()
        
        raw_data = {
            "source": "clawhub_odaily",
            "timestamp": int(datetime.now().timestamp()),
            "modules": {}
        }
        
        async def call_m1():
            return ("M1", ClawHubRunner.call_module(ClawHubModule.M1_TODAY_WATCH.value, {"limit": 10}))
        
        async def call_m2():
            return ("M2", ClawHubRunner.call_module(ClawHubModule.M2_MARKET_ANALYSIS.value, {"focus": "overview"}))
        
        async def call_m3():
            return ("M3", ClawHubRunner.call_module(ClawHubModule.M3_TOMORROW_WATCH.value, {}))
        
        async def call_m4():
            return ("M4", ClawHubRunner.call_module(ClawHubModule.M4_WHALE_TRACKING.value, {"min_size": 10000, "min_price": 0.95}))
        
        async def call_m5():
            return ("M5", ClawHubRunner.call_module(ClawHubModule.M5_API_MODULE.value, {}))
        
        tasks = []
        if "M1" in self.modules:
            tasks.append(call_m1())
        if "M2" in self.modules:
            tasks.append(call_m2())
        if "M3" in self.modules:
            tasks.append(call_m3())
        if "M4" in self.modules:
            tasks.append(call_m4())
        if "M5" in self.modules:
            tasks.append(call_m5())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, tuple):
                module_name, module_data = result
                if module_data:
                    raw_data["modules"][module_name] = module_data
        
        return raw_data
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        modules = raw_data.get("modules", {})
        
        if "M1" in modules:
            events.extend(self._normalize_m1(modules["M1"]))
        
        if "M2" in modules:
            events.extend(self._normalize_m2(modules["M2"]))
        
        if "M3" in modules:
            events.extend(self._normalize_m3(modules["M3"]))
        
        if "M4" in modules:
            events.extend(self._normalize_m4(modules["M4"]))
        
        if "M5" in modules:
            events.extend(self._normalize_m5(modules["M5"]))
        
        if not events:
            events.extend(self._generate_mock_events())
        
        return events
    
    def _normalize_m1(self, data: Any) -> List[StandardEvent]:
        """M1 今日必关注"""
        events = []
        
        if not data or not isinstance(data, dict):
            return events
        
        articles = data.get("articles", [])
        flash_news = data.get("flash_news", [])
        
        for item in articles[:5]:
            if isinstance(item, dict):
                title = item.get("title", "")
                content = item.get("summary", "") or item.get("description", "") or item.get("content", "")
                url = item.get("url", "") or item.get("link", "")
                time_str = item.get("time", "") or item.get("published_at", "")
                
                event = create_news_event(
                    source=Source.CLAWHUB_ODAILY.value,
                    title=title,
                    content=content,
                    sentiment=self._parse_sentiment(content),
                    importance=0.8,
                    symbols=self._extract_symbols(title + " " + content),
                    tags=["odaily", "m1_article"],
                    url=url
                )
                if time_str:
                    event.metadata["published_at"] = time_str
                events.append(event)
        
        for item in flash_news[:10]:
            if isinstance(item, dict):
                title = item.get("title", "")
                content = item.get("content", "") or item.get("description", "")
                
                event = create_news_event(
                    source=Source.CLAWHUB_ODAILY.value,
                    title=title[:100],
                    content=content[:500],
                    sentiment=self._parse_sentiment(title + " " + content),
                    importance=0.7,
                    symbols=self._extract_symbols(title + " " + content),
                    tags=["odaily", "m1_flash"],
                    url=item.get("url", "")
                )
                events.append(event)
        
        return events
    
    def _normalize_m2(self, data: Any) -> List[StandardEvent]:
        """M2 加密市场分析"""
        events = []
        
        if isinstance(data, dict):
            regime = data.get("regime", "") or data.get("market_regime", "")
            sentiment_text = data.get("sentiment", "")
            analysis = data.get("analysis", "") or data.get("summary", "")
            btc_price = data.get("btc_price", "") or data.get("BTC", "")
            eth_price = data.get("eth_price", "") or data.get("ETH", "")
        else:
            regime = ""
            sentiment_text = ""
            analysis = str(data)[:200]
            btc_price = ""
            eth_price = ""
        
        if regime:
            if regime.lower() in ["bull", "bullish", "牛市", "多头"]:
                sentiment = Sentiment.BULLISH.value
                importance = 0.85
            elif regime.lower() in ["bear", "bearish", "熊市", "空头"]:
                sentiment = Sentiment.BEARISH.value
                importance = 0.85
            else:
                sentiment = Sentiment.NEUTRAL.value
                importance = 0.6
            
            event = create_news_event(
                source=Source.CLAWHUB_ODAILY.value,
                title=f"市场状态: {regime}",
                content=analysis,
                sentiment=sentiment,
                importance=importance,
                symbols=["BTC", "ETH"],
                tags=["odaily", "m2_market_analysis", "regime"]
            )
            events.append(event)
        
        if btc_price:
            event = create_news_event(
                source=Source.CLAWHUB_ODAILY.value,
                title=f"BTC 当前价格: {btc_price}",
                content="",
                sentiment=Sentiment.NEUTRAL.value,
                importance=0.7,
                symbols=["BTC"],
                tags=["odaily", "m2_market_analysis", "price"]
            )
            events.append(event)
        
        return events
    
    def _normalize_m3(self, data: Any) -> List[StandardEvent]:
        """M3 明日关注"""
        events = []
        
        if isinstance(data, dict):
            items = data.get("events", []) or data.get("tomorrow_events", []) or data.get("data", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []
        
        for item in items:
            if isinstance(item, dict):
                title = item.get("title", "") or item.get("event", "")
                time_str = item.get("time", "") or item.get("datetime", "")
                impact = item.get("impact", "") or item.get("importance", "")
                
                event = create_news_event(
                    source=Source.CLAWHUB_ODAILY.value,
                    title=f"【明日关注】{title}",
                    content=item.get("description", "") or "",
                    sentiment=Sentiment.NEUTRAL.value,
                    importance=self._parse_importance(impact),
                    symbols=self._extract_symbols(title),
                    tags=["odaily", "m3_tomorrow_watch", "calendar"]
                )
                
                if time_str:
                    event.metadata["event_time"] = time_str
                
                events.append(event)
        
        return events
    
    def _normalize_m4(self, data: Any) -> List[StandardEvent]:
        """M4 巨鲸尾盘追踪"""
        events = []
        
        if isinstance(data, dict):
            trades = data.get("trades", []) or data.get("whale_trades", []) or data.get("data", [])
        elif isinstance(data, list):
            trades = data
        else:
            trades = []
        
        for trade in trades[:10]:
            if isinstance(trade, dict):
                symbol = trade.get("symbol", "") or trade.get("asset", "BTC")
                amount = trade.get("amount", 0) or trade.get("size", 0)
                value_usd = trade.get("value_usd", 0) or trade.get("value", 0)
                side = trade.get("side", "") or trade.get("direction", "unknown")
                price = trade.get("price", 0)
                confidence = trade.get("confidence", 0.9)
                
                if side.lower() in ["yes", "buy", "long", "多", "看涨"]:
                    action = "buy"
                    sentiment = Sentiment.BULLISH.value
                elif side.lower() in ["no", "sell", "short", "空", "看跌"]:
                    action = "sell"
                    sentiment = Sentiment.BEARISH.value
                else:
                    action = "unknown"
                    sentiment = Sentiment.NEUTRAL.value
                
                event = create_whale_event(
                    wallet=trade.get("trader", "") or trade.get("address", "") or "",
                    action=action,
                    symbol=symbol,
                    amount=float(amount),
                    value_usd=float(value_usd),
                    exchange=trade.get("platform", "") or trade.get("exchange", "Polymarket")
                )
                
                event.source = Source.CLAWHUB_ODAILY.value
                event.sentiment = sentiment
                event.importance = min(float(confidence), 1.0)
                event.tags = ["odaily", "m4_whale_tracking", "polymarket", "whale"]
                
                if price:
                    event.metadata["price"] = price
                
                events.append(event)
        
        return events
    
    def _normalize_m5(self, data: Any) -> List[StandardEvent]:
        """M5 API原始数据"""
        events = []
        
        if isinstance(data, dict):
            articles = data.get("articles", []) or data.get("news", []) or []
            flash_news = data.get("flash_news", []) or data.get("快讯", []) or []
        elif isinstance(data, list):
            articles = data
            flash_news = []
        else:
            articles = []
            flash_news = []
        
        for article in articles[:5]:
            if isinstance(article, dict):
                event = create_news_event(
                    source=Source.CLAWHUB_ODAILY.value,
                    title=article.get("title", ""),
                    content=article.get("content", "") or article.get("summary", ""),
                    sentiment=self._parse_sentiment(str(article)),
                    importance=0.75,
                    symbols=self._extract_symbols(str(article)),
                    tags=["odaily", "m5_api", "article"],
                    url=article.get("url", "")
                )
                events.append(event)
        
        for news in flash_news[:5]:
            if isinstance(news, dict):
                event = create_news_event(
                    source=Source.CLAWHUB_ODAILY.value,
                    title=news.get("title", ""),
                    content=news.get("content", ""),
                    sentiment=self._parse_sentiment(str(news)),
                    importance=0.65,
                    symbols=self._extract_symbols(str(news)),
                    tags=["odaily", "m5_api", "flash"],
                    url=news.get("url", "")
                )
                events.append(event)
        
        return events
    
    def _extract_symbols(self, text: str) -> List[str]:
        """从文本中提取交易对/币种"""
        symbols = []
        
        crypto_patterns = [
            r'\bBTC\b', r'\bETH\b', r'\bSOL\b', r'\bBNB\b', r'\bXRP\b',
            r'\bADA\b', r'\bDOGE\b', r'\bDOT\b', r'\bAVAX\b', r'\bLINK\b',
            r'\bMATIC\b', r'\bUNI\b', r'\bATOM\b', r'\bLTC\b', r'\bBCH\b',
            r'\bBTC[UEST]?\b', r'\bETH[2]?\b', r'\bFIL\b', r'\bNEAR\b',
            r'\bAPT\b', r'\bARB\b', r'\bOP\b', r'\bSUI\b', r'\bSEI\b'
        ]
        
        for pattern in crypto_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized = match.upper()
                if normalized not in symbols:
                    symbols.append(normalized)
        
        return symbols[:5]
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据（当 Skill 不可用时）"""
        now = int(datetime.now().timestamp())
        
        return {
            "source": "clawhub_odaily",
            "timestamp": now,
            "modules": {
                "M1": {
                    "articles": [
                        {"title": "BTC ETF 获批引发市场热议", "summary": "BlackRock BTC ETF 获批，市场情绪高涨", "url": "https://www.odaily.news/article/123"},
                        {"title": "以太坊升级时间表确定", "summary": "ETH 升级预计在 Q2 进行", "url": "https://www.odaily.news/article/124"}
                    ]
                },
                "M2": {
                    "regime": "bull",
                    "analysis": "市场多头趋势明显，机构资金持续流入",
                    "btc_price": "$105,000"
                },
                "M3": {
                    "events": [
                        {"title": "美联储利率决议", "time": "02:00", "impact": "high"}
                    ]
                },
                "M4": {
                    "trades": [
                        {"symbol": "BTC", "side": "yes", "amount": 500, "value_usd": 52500000, "confidence": 0.95}
                    ]
                },
                "M5": {
                    "articles": [
                        {"title": "测试文章", "content": "这是测试内容"}
                    ]
                }
            }
        }
    
    def _generate_mock_events(self) -> List[StandardEvent]:
        """生成模拟事件"""
        now = int(datetime.now().timestamp())
        
        return [
            create_news_event(
                source=Source.CLAWHUB_ODAILY.value,
                title="【模拟】BTC ETF 获批引发市场热议",
                content="BlackRock BTC ETF 正式获批，市场情绪高涨",
                sentiment=Sentiment.BULLISH.value,
                importance=0.85,
                symbols=["BTC"],
                tags=["odaily", "mock", "etf"]
            ),
            create_news_event(
                source=Source.CLAWHUB_ODAILY.value,
                title="【模拟】市场状态: BULL",
                content="市场多头趋势明显，机构资金持续流入",
                sentiment=Sentiment.BULLISH.value,
                importance=0.8,
                symbols=["BTC", "ETH"],
                tags=["odaily", "mock", "market_regime"]
            )
        ]


class TwitterAdapter(SkillAdapter):
    """Twitter/X 适配器"""
    
    def __init__(self, config: AdapterConfig = None):
        if not config:
            config = AdapterConfig(
                name="TwitterAdapter",
                source_type="twitter"
            )
        super().__init__(config)
        
        self.watch_accounts = [
            "elonmusk",
            "cz_binance",
            "VitalikButerin",
            "saylor",
            "BarrySilbert"
        ]
    
    async def fetch_raw_data(self) -> Dict:
        """获取 Twitter 数据"""
        return self._generate_mock_data()
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        for tweet in raw_data.get("tweets", []):
            event = create_tweet_event(
                author=tweet.get("author", ""),
                content=tweet.get("content", ""),
                likes=tweet.get("likes", 0),
                retweets=tweet.get("retweets", 0),
                symbols=tweet.get("symbols", [])
            )
            event.tags = ["twitter"] + tweet.get("tags", [])
            events.append(event)
        
        return events
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据"""
        return {
            "tweets": [
                {
                    "id": "123456",
                    "author": "elonmusk",
                    "content": "Bitcoin looks interesting",
                    "likes": 50000,
                    "retweets": 10000,
                    "symbols": ["BTC"]
                }
            ]
        }


class NewsAdapter(SkillAdapter):
    """新闻适配器（RSS/API）"""
    
    def __init__(self, config: AdapterConfig = None):
        if not config:
            config = AdapterConfig(
                name="NewsAdapter",
                source_type="news"
            )
        super().__init__(config)
    
    async def fetch_raw_data(self) -> Dict:
        """获取新闻数据"""
        return self._generate_mock_data()
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        for news in raw_data.get("news", []):
            event = create_news_event(
                source=news.get("source", "unknown"),
                title=news.get("title", ""),
                content=news.get("content", ""),
                sentiment=self._parse_sentiment(news.get("sentiment", "")),
                importance=news.get("importance", 0.5),
                symbols=news.get("symbols", []),
                tags=["news"] + news.get("tags", []),
                url=news.get("url", "")
            )
            events.append(event)
        
        return events
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据"""
        return {
            "news": [
                {
                    "title": "BlackRock Bitcoin ETF 获得批准",
                    "content": "BlackRock 的比特币 ETF 正式获得 SEC 批准...",
                    "source": "coindesk",
                    "sentiment": "bullish",
                    "importance": 0.95,
                    "symbols": ["BTC"],
                    "tags": ["etf", "blackrock"]
                }
            ]
        }


class PANewsAdapter(SkillAdapter):
    """PANews 适配器"""
    
    def __init__(self, config: AdapterConfig = None):
        if not config:
            config = AdapterConfig(
                name="PANewsAdapter",
                source_type="panews"
            )
        super().__init__(config)
    
    async def fetch_raw_data(self) -> Dict:
        """获取 PANews 数据"""
        return self._generate_mock_data()
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        for news in raw_data.get("news", []):
            event = create_news_event(
                source="panews",
                title=news.get("title", ""),
                content=news.get("content", ""),
                sentiment=self._parse_sentiment(news.get("sentiment", "")),
                importance=news.get("importance", 0.5),
                symbols=news.get("symbols", []),
                tags=["panews"] + news.get("tags", []),
                url=news.get("url", "")
            )
            events.append(event)
        
        return events
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据"""
        return {
            "news": []
        }


class AdapterRegistry:
    """适配器注册表"""
    
    def __init__(self):
        self._adapters: Dict[str, SkillAdapter] = {}
        self._enabled: List[str] = []
    
    def register(self, adapter: SkillAdapter):
        """注册适配器"""
        self._adapters[adapter.config.name] = adapter
        if adapter.config.enabled:
            self._enabled.append(adapter.config.name)
        logger.info(f"Registered adapter: {adapter.config.name}")
    
    def get(self, name: str) -> Optional[SkillAdapter]:
        """获取适配器"""
        return self._adapters.get(name)
    
    def get_enabled(self) -> List[SkillAdapter]:
        """获取所有启用的适配器"""
        return [self._adapters[name] for name in self._enabled if name in self._adapters]
    
    async def collect_all(self) -> List[StandardEvent]:
        """从所有适配器采集"""
        all_events = []
        
        for adapter in self.get_enabled():
            try:
                events = await adapter.collect()
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Adapter {adapter.config.name} failed: {e}")
        
        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        
        return all_events


_registry: AdapterRegistry = None

def get_adapter_registry() -> AdapterRegistry:
    """获取适配器注册表"""
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
        _registry.register(OdailySkillAdapter())
        _registry.register(TwitterAdapter())
        _registry.register(NewsAdapter())
        _registry.register(PANewsAdapter())
    return _registry
