"""
Odaily Adapter - Odaily 数据源适配器

职责：
- 调用 odaily-skill 获取真实数据
- 转换为统一的 StandardEvent 格式
- 作为防腐层，隔离外部 skill 和系统内部

数据流：
odaily-skill (第三方能力包)
    ↓
OdailyAdapter (防腐层)
    ↓
StandardEvent (统一格式)
    ↓
Kafka raw.odaily
"""

import json
import subprocess
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio

from engines.adapters.contracts import (
    StandardEvent,
    Sentiment,
    Source,
    create_news_event,
    create_whale_event
)
from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig

logger = get_logger("adapters.odaily")


class OdailyModule(Enum):
    M1_TODAY_WATCH = "get_today_watch"
    M2_MARKET_ANALYSIS = "get_crypto_market_analysis"
    M3_TOMORROW_WATCH = "get_tomorrow_watch"
    M4_WHALE_TRACKING = "scan_whale_tail_trades"
    M5_API_MODULE = "get_api_module"


@dataclass
class OdailyAdapterConfig:
    name: str = "OdailyAdapter"
    source_type: str = "odaily"
    enabled: bool = True
    modules: List[str] = None
    cache_ttl: int = 300
    retry_count: int = 2
    
    def __post_init__(self):
        if self.modules is None:
            self.modules = ["M5"]


class OdailySkillRunner:
    
    SKILL_DIR = "/Users/yangdezeng/00_crypto/00_trade_agent/odaily-skill-1.0.10"
    
    @staticmethod
    def find_skill_dir() -> Optional[str]:
        possible_paths = [
            "/Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/services/data_service/external/odaily-skill-1.0.10",
            "/Users/yangdezeng/00_crypto/00_trade_agent/odaily-skill-1.0.10",
            "/tmp/odaily-skill",
            os.path.expanduser("~/.openclaw/skills/odaily-skill"),
            os.path.expanduser("~/.claude/skills/odaily-skill"),
        ]
        
        for path in possible_paths:
            run_py = os.path.join(path, "run.py")
            if os.path.exists(run_py):
                logger.debug(f"Found odaily-skill at: {path}")
                return path
        
        return None
    
    @staticmethod
    def call_module(module: str, params: Dict = None) -> Optional[Dict]:
        skill_dir = OdailySkillRunner.find_skill_dir()
        
        if not skill_dir:
            logger.warning("odaily-skill not found")
            return None
        
        params = params or {}
        params_json = json.dumps(params, ensure_ascii=False)
        
        cmd = f'cd "{skill_dir}" && python3 run.py {module} \'{params_json}\''
        
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
                return OdailySkillRunner._parse_text_output(module, output)
            
        except subprocess.TimeoutExpired:
            logger.error("Skill command timed out")
            return None
        except Exception as e:
            logger.error(f"Failed to execute skill: {e}")
            return None
    
    @staticmethod
    def _parse_text_output(module: str, text: str) -> Dict:
        data = {
            "module": module,
            "raw": text,
            "articles": [],
            "flash_news": []
        }
        
        lines = text.split("\n")
        current_section = None
        current_article = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            if "📰" in line or "文章" in line:
                current_section = "articles"
                continue
            elif "⚡" in line or "快讯" in line:
                current_section = "flash_news"
                continue
            elif line.startswith("##") or line.startswith("---"):
                continue
            
            if current_section == "articles":
                if line.startswith(tuple("123456789")):
                    if current_article:
                        data["articles"].append(current_article)
                    
                    title = line.split(". ", 1)[1] if ". " in line else line
                    current_article = {"title": title, "content": "", "url": "", "type": "article"}
                elif current_article:
                    if line.startswith("🔗") or line.startswith("🔗"):
                        current_article["url"] = line.replace("🔗", "").replace("🔗", "").strip()
                    elif line and not line.startswith("🔗"):
                        current_article["content"] += (" " if current_article["content"] else "") + line
            
            elif current_section == "flash_news":
                if line.startswith("•"):
                    if current_article:
                        data["flash_news"].append(current_article)
                    
                    content = line[1:].strip()
                    current_article = {"title": content, "content": "", "url": "", "type": "flash"}
                elif current_article:
                    if line.startswith("🔗") or line.startswith("🔗"):
                        current_article["url"] = line.replace("🔗", "").replace("🔗", "").strip()
                    elif line and not line.startswith("🔗"):
                        current_article["content"] += (" " if current_article["content"] else "") + line
        
        if current_article:
            if current_section == "articles":
                data["articles"].append(current_article)
            elif current_section == "flash_news":
                data["flash_news"].append(current_article)
        
        data["has_data"] = len(data["articles"]) > 0 or len(data["flash_news"]) > 0
        
        return data


class OdailyAdapter:
    
    def __init__(self, config: OdailyAdapterConfig = None):
        self.config = config or OdailyAdapterConfig()
        
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="odaily_adapter",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=self.config.retry_count,
            initial_delay=1.0
        ))
        
        self._skill_available = OdailySkillRunner.find_skill_dir() is not None
        
        if not self._skill_available:
            logger.warning("odaily-skill not found. Will return empty data.")
    
    @property
    def is_available(self) -> bool:
        return self._skill_available
    
    async def fetch_raw_data(self) -> Dict:
        if not self._skill_available:
            return {"source": "odaily", "modules": {}}
        
        raw_data = {
            "source": "odaily",
            "timestamp": int(datetime.now().timestamp()),
            "modules": {}
        }
        
        async def call_m5():
            return ("M5", OdailySkillRunner.call_module(
                OdailyModule.M5_API_MODULE.value, {}
            ))
        
        results = await asyncio.gather(call_m5(), return_exceptions=True)
        
        for result in results:
            if isinstance(result, tuple):
                module_name, module_data = result
                if module_data:
                    raw_data["modules"][module_name] = module_data
        
        return raw_data
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        events = []
        
        modules = raw_data.get("modules", {})
        
        if "M5" in modules:
            events.extend(self._normalize_m5(modules["M5"]))
        
        return events
    
    async def collect(self) -> List[StandardEvent]:
        try:
            raw_data = await self.retry_policy.execute(self.fetch_raw_data)
            events = self.normalize(raw_data)
            logger.info(f"OdailyAdapter: collected {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"OdailyAdapter collect failed: {e}")
            return []
    
    def _normalize_m5(self, data: Any) -> List[StandardEvent]:
        events = []
        
        if isinstance(data, dict):
            articles = data.get("articles", [])
            flash_news = data.get("flash_news", [])
        elif isinstance(data, list):
            articles = data
            flash_news = []
        else:
            return events
        
        for article in articles[:5]:
            if isinstance(article, dict):
                event = create_news_event(
                    source=Source.ODALY.value,
                    title=article.get("title", ""),
                    content=article.get("content", "") or article.get("summary", ""),
                    sentiment=self._parse_sentiment(str(article)),
                    importance=0.75,
                    symbols=self._extract_symbols(str(article)),
                    tags=["odaily", "article"],
                    url=article.get("url", "")
                )
                events.append(event)
        
        for news in flash_news[:10]:
            if isinstance(news, dict):
                event = create_news_event(
                    source=Source.ODALY.value,
                    title=news.get("title", ""),
                    content=news.get("content", "") or news.get("description", ""),
                    sentiment=self._parse_sentiment(str(news)),
                    importance=0.65,
                    symbols=self._extract_symbols(str(news)),
                    tags=["odaily", "flash"],
                    url=news.get("url", "")
                )
                events.append(event)
        
        return events
    
    def _parse_sentiment(self, text: str) -> str:
        text_lower = text.lower()
        
        bullish_keywords = ["bullish", "看涨", "利好", "上涨", "surge", "rally", "突破"]
        bearish_keywords = ["bearish", "看跌", "利空", "下跌", "crash", "plunge", "暴跌"]
        
        if any(kw in text_lower for kw in bullish_keywords):
            return Sentiment.BULLISH.value
        if any(kw in text_lower for kw in bearish_keywords):
            return Sentiment.BEARISH.value
        
        return Sentiment.NEUTRAL.value
    
    def _extract_symbols(self, text: str) -> List[str]:
        symbols = []
        
        crypto_patterns = [
            (r'\bBTC\b', "BTC"), (r'\bETH\b', "ETH"), (r'\bSOL\b', "SOL"),
            (r'\bBNB\b', "BNB"), (r'\bXRP\b', "XRP"), (r'\bDOGE\b', "DOGE"),
            (r'\bADA\b', "ADA"), (r'\bAVAX\b', "AVAX"), (r'\bLINK\b', "LINK"),
        ]
        
        for pattern, symbol in crypto_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if symbol not in symbols:
                    symbols.append(symbol)
        
        return symbols[:5]


_odaily_adapter: Optional[OdailyAdapter] = None


def get_odaily_adapter() -> OdailyAdapter:
    global _odaily_adapter
    if _odaily_adapter is None:
        _odaily_adapter = OdailyAdapter()
    return _odaily_adapter
