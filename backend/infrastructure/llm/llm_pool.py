"""
LLM 资源池 - 多级降级 + 熔断器 + 重试
降级链: 免费API → 本地模型 → 关键词匹配
"""

import os
import yaml
import asyncio
import time
import re
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

from infrastructure.logging import get_logger
from infrastructure.config.factory import get_infra_config

logger = get_logger("llm.pool")


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class LLMPoolConfig:
    """单个 LLM 池配置"""
    pool_id: str
    name: str
    enabled: bool
    priority: int
    type: str
    base_url: str
    api_key: str
    models: List[str]
    fallback_to: Optional[str]
    rate_limit: Dict
    circuit_config: Dict


@dataclass
class LLMResponse:
    """LLM 响应"""
    success: bool
    text: str
    pool_used: str
    model_used: str
    latency_ms: int
    error: Optional[str] = None


class CircuitBreaker:
    """单个 LLM 池的熔断器"""

    def __init__(
        self,
        pool_id: str,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.pool_id = pool_id
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.timeout_seconds

    def record_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def can_call(self) -> bool:
        current_state = self.state
        if current_state == CircuitState.OPEN:
            return False
        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                return False
            self._half_open_calls += 1
        return True

    def get_stats(self) -> Dict:
        return {
            "pool_id": self.pool_id,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
        }


class KeywordAnalyzer:
    """关键词匹配分析器（终极降级方案）"""

    def __init__(self, config: Dict):
        self.sentiment_keywords = config.get("sentiment_keywords", {})
        self.black_swan_keywords = config.get("black_swan_keywords", {})

    def analyze_sentiment(self, text: str) -> tuple[str, float, list[str]]:
        """关键词情绪分析"""
        text_lower = text.lower()

        bullish_count = sum(1 for kw in self.sentiment_keywords.get("bullish", []) if kw.lower() in text_lower)
        bearish_count = sum(1 for kw in self.sentiment_keywords.get("bearish", []) if kw.lower() in text_lower)

        total = bullish_count + bearish_count
        if total == 0:
            return "neutral", 0.5, []

        matched_keywords = []
        matched_keywords.extend([kw for kw in self.sentiment_keywords.get("bullish", []) if kw.lower() in text_lower])
        matched_keywords.extend([kw for kw in self.sentiment_keywords.get("bearish", []) if kw.lower() in text_lower])

        if bullish_count > bearish_count:
            score = bullish_count / total
            return "bullish", score, matched_keywords
        elif bearish_count > bullish_count:
            score = bearish_count / total
            return "bearish", score, matched_keywords
        else:
            return "neutral", 0.5, matched_keywords

    def detect_black_swan(self, text: str) -> tuple[bool, str, list[str]]:
        """检测黑天鹅事件"""
        text_lower = text.lower()
        matched_level = None
        matched_keywords = []

        critical_kws = self.black_swan_keywords.get("critical", [])
        high_kws = self.black_swan_keywords.get("high", [])

        for kw in critical_kws:
            if kw.lower() in text_lower:
                matched_keywords.append(kw)
                matched_level = "critical"

        if not matched_level:
            for kw in high_kws:
                if kw.lower() in text_lower:
                    matched_keywords.append(kw)
                    matched_level = "high"

        return (len(matched_keywords) > 0, matched_level or "none", matched_keywords)


class OpenAICompatibleClient:
    """OpenAI 兼容 API 客户端"""

    def __init__(self, config: LLMPoolConfig):
        self.config = config
        self._client = None

    async def _get_client(self):
        if not self._client:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key or "dummy",
                    base_url=self.config.base_url,
                    timeout=30.0
                )
            except ImportError:
                pass
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> tuple[bool, str, Optional[str]]:
        start_time = time.time()
        try:
            client = await self._get_client()
            if not client:
                raise RuntimeError("OpenAI client not available")

            response = await client.chat.completions.create(
                model=model or self.config.models[0],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            text = response.choices[0].message.content or ""
            latency = int((time.time() - start_time) * 1000)
            return True, text, None
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            return False, "", str(e)


class OllamaClient:
    """Ollama 本地模型客户端"""

    def __init__(self, config: LLMPoolConfig):
        self.config = config

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> tuple[bool, str, Optional[str]]:
        start_time = time.time()
        try:
            import httpx

            url = f"{self.config.base_url}/api/chat"
            payload = {
                "model": model or self.config.models[0],
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                text = result.get("message", {}).get("content", "")

            latency = int((time.time() - start_time) * 1000)
            return True, text, None
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            return False, "", str(e)


class LLMPoolManager:
    """LLM 资源池管理器"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = Path(__file__).parent.parent.parent
            config_path = base_dir / "config" / "llm_pools.yaml"

        self.config_path = Path(config_path)
        self._load_config()

        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        for pool_id, pool_config in self.pools.items():
            cb_config = pool_config.circuit_config
            self.circuit_breakers[pool_id] = CircuitBreaker(
                pool_id=pool_id,
                failure_threshold=cb_config.get("failure_threshold", 5),
                timeout_seconds=cb_config.get("timeout_seconds", 60),
            )

        self.clients: Dict[str, Any] = {}
        self.keyword_analyzer = KeywordAnalyzer(self.global_config)
        self._last_pool_index = 0

    def _load_config(self):
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        llm_settings = get_infra_config().llm

        api_key_mapping = {
            "zhipu": (llm_settings.zhipu_api_key, llm_settings.zhipu_base_url),
            "siliconflow": (llm_settings.siliconflow_api_key, llm_settings.siliconflow_base_url),
            "deepseek": (llm_settings.deepseek_api_key, llm_settings.deepseek_base_url),
            "qianfan": (llm_settings.qianfan_api_key, llm_settings.qianfan_base_url),
            "dashscope": (llm_settings.dashscope_api_key, llm_settings.dashscope_base_url),
            "ollama": (None, llm_settings.ollama_base_url),
            "openai": (llm_settings.openai_api_key, llm_settings.openai_base_url),
            "anthropic": (llm_settings.anthropic_api_key, None),
            "minimax": (llm_settings.minimax_api_key, llm_settings.minimax_base_url),
        }

        self.pools: Dict[str, LLMPoolConfig] = {}
        for pool_id, pool_data in config.get("llm_pools", {}).items():
            mapped_key, mapped_url = api_key_mapping.get(pool_id, (None, None))
            
            if mapped_key is not None:
                api_key = mapped_key
            else:
                api_key_env = pool_data.get("api_key_env", "")
                api_key = os.environ.get(api_key_env, "") if api_key_env else ""

            base_url = pool_data.get("base_url", "")
            if mapped_url and not base_url:
                base_url = mapped_url

            self.pools[pool_id] = LLMPoolConfig(
                pool_id=pool_id,
                name=pool_data.get("name", pool_id),
                enabled=pool_data.get("enabled", False),
                priority=pool_data.get("priority", 99),
                type=pool_data.get("type", "openai_compatible"),
                base_url=base_url,
                api_key=api_key,
                models=pool_data.get("models", []),
                fallback_to=pool_data.get("fallback_to"),
                rate_limit=pool_data.get("rate_limit", {}),
                circuit_config=pool_data.get("circuit_breaker", {}),
            )

        self.global_config = config.get("global", {})

    def get_available_pools(self) -> List[LLMPoolConfig]:
        """按优先级获取可用的池"""
        pools = [p for p in self.pools.values() if p.enabled]
        return sorted(pools, key=lambda p: p.priority)

    def get_next_pool(self, exclude: Optional[List[str]] = None) -> Optional[LLMPoolConfig]:
        """获取下一个可用池（带排除列表）"""
        exclude = exclude or []
        available = self.get_available_pools()

        for pool in available:
            if pool.pool_id in exclude:
                continue
            cb = self.circuit_breakers[pool.pool_id]
            if cb.can_call():
                return pool

        return None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        force_pool: Optional[str] = None,
    ) -> LLMResponse:
        """
        发送 chat 请求，自动降级
        """
        start_time = time.time()
        exclude_pools: List[str] = []
        retry_config = self.global_config.get("retry", {})
        max_retries = retry_config.get("max_retries", 2)

        for attempt in range(max_retries + 1):
            pool = None

            if force_pool and force_pool in self.pools:
                pool = self.pools[force_pool]
            else:
                pool = self.get_next_pool(exclude=exclude_pools)

            if not pool:
                logger.warning("All LLM pools exhausted, falling back to keyword analyzer")
                return self._keyword_fallback(messages, start_time)

            cb = self.circuit_breakers[pool.pool_id]

            if pool.type == "keyword":
                return self._keyword_fallback(messages, start_time)

            try:
                client = self._get_or_create_client(pool)
                success, text, error = await client.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                if success:
                    cb.record_success()
                    latency = int((time.time() - start_time) * 1000)
                    logger.debug(f"[{pool.name}] Success in {latency}ms")
                    return LLMResponse(
                        success=True,
                        text=text,
                        pool_used=pool.pool_id,
                        model_used=model or pool.models[0],
                        latency_ms=latency,
                        error=None
                    )
                else:
                    cb.record_failure()
                    logger.warning(f"[{pool.name}] Failed: {error}")

                    if pool.fallback_to and pool.fallback_to not in exclude_pools:
                        exclude_pools.append(pool.pool_id)
                        continue
                    else:
                        exclude_pools.append(pool.pool_id)

            except Exception as e:
                cb.record_failure()
                logger.error(f"[{pool.name}] Error: {str(e)}")
                exclude_pools.append(pool.pool_id)

        return self._keyword_fallback(messages, start_time)

    def _keyword_fallback(self, messages: List[Dict[str, str]], start_time: float) -> LLMResponse:
        """关键词匹配终极降级"""
        combined_text = " ".join([m.get("content", "") for m in messages])
        sentiment, score, keywords = self.keyword_analyzer.analyze_sentiment(combined_text)
        is_black_swan, black_swan_level, black_swan_keywords = self.keyword_analyzer.detect_black_swan(combined_text)

        response_text = self._format_keyword_response(
            sentiment=sentiment,
            score=score,
            keywords=keywords,
            is_black_swan=is_black_swan,
            black_swan_level=black_swan_level,
            black_swan_keywords=black_swan_keywords
        )

        latency = int((time.time() - start_time) * 1000)
        return LLMResponse(
            success=True,
            text=response_text,
            pool_used="keyword",
            model_used="keyword_matching",
            latency_ms=latency,
            error=None
        )

    def _format_keyword_response(
        self,
        sentiment: str,
        score: float,
        keywords: List[str],
        is_black_swan: bool,
        black_swan_level: str,
        black_swan_keywords: List[str]
    ) -> str:
        return f"""
{{
  "sentiment": "{sentiment}",
  "sentiment_score": {score:.2f},
  "keywords": {keywords},
  "is_black_swan": {str(is_black_swan).lower()},
  "black_swan_level": "{black_swan_level}",
  "black_swan_keywords": {black_swan_keywords}
}}
"""

    def _get_or_create_client(self, pool: LLMPoolConfig) -> Any:
        if pool.pool_id in self.clients:
            return self.clients[pool.pool_id]

        if pool.type == "ollama":
            client = OllamaClient(pool)
        else:
            client = OpenAICompatibleClient(pool)

        self.clients[pool.pool_id] = client
        return client

    def get_pool_stats(self) -> Dict[str, Any]:
        """获取所有池状态"""
        stats = {}
        for pool_id, cb in self.circuit_breakers.items():
            stats[pool_id] = cb.get_stats()
        return stats

    async def analyze_news_sentiment(self, title: str, content: str = "") -> Dict[str, Any]:
        """新闻情绪分析（高级方法）"""
        prompt = f"""
分析以下加密货币新闻：

标题: {title}
内容: {content if content else title}

请按以下JSON格式返回结果：
{{
  "sentiment": "bullish|bearish|neutral",
  "sentiment_score": 0.0-1.0,
  "is_black_swan": true|false,
  "black_swan_level": "none|low|high|critical",
  "affected_symbols": ["BTC", "ETH", ...],
  "summary": "1-2 sentence summary"
}}
"""

        messages = [{"role": "user", "content": prompt}]
        response = await self.chat(messages, temperature=0.3, max_tokens=400)

        try:
            import json
            return json.loads(response.text)
        except Exception:
            sentiment, score, _ = self.keyword_analyzer.analyze_sentiment(f"{title} {content}")
            is_bs, bs_level, _ = self.keyword_analyzer.detect_black_swan(f"{title} {content}")
            return {
                "sentiment": sentiment,
                "sentiment_score": score,
                "is_black_swan": is_bs,
                "black_swan_level": bs_level,
                "affected_symbols": ["BTC", "ETH"],
                "summary": title[:100],
                "_fallback": True,
                "_pool_used": response.pool_used
            }


# 全局单例
_llm_pool_manager: Optional[LLMPoolManager] = None


def get_llm_pool(config_path: Optional[str] = None) -> LLMPoolManager:
    """获取 LLM 资源池管理器"""
    global _llm_pool_manager
    if _llm_pool_manager is None:
        _llm_pool_manager = LLMPoolManager(config_path)
    return _llm_pool_manager
