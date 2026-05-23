"""
LLM Client - LLM服务客户端（支持流式调用）
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, AsyncIterator, Any
from dataclasses import dataclass
from enum import Enum

from infrastructure.logging import get_logger
logger = get_logger("infrastructure.llm")

from infrastructure.http.client import HTTPClient, HTTPRequest, HTTPMethod


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MINIMAX = "minimax"
    LOCAL = "local"


@dataclass
class LLMMessage:
    """LLM消息"""
    role: str
    content: str


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    usage: Dict[str, int]
    model: str
    finish_reason: str = "stop"


@dataclass
class StreamChunk:
    """流式响应块"""
    delta: str
    index: int
    done: bool


class LLMServiceClient:
    """LLM服务客户端（调用独立llm_service微服务，支持流式）"""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("LLM_SERVICE_URL", "http://localhost:8001")
        self.api_key = api_key or os.getenv("LLM_SERVICE_API_KEY", "")
        self.default_model = "gpt-4o-mini"

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """同步chat调用（非流式）"""
        http = HTTPClient()
        request = HTTPRequest(
            url=f"{self.base_url}/api/v1/chat",
            method=HTTPMethod.POST,
            headers=self._get_headers(),
            json_data={
                "messages": messages,
                "model": model or self.default_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            },
            timeout=60.0
        )

        async with http:
            response = await http.request(request)

        if response.success and response.body:
            return LLMResponse(
                content=response.body.get("content", ""),
                usage=response.body.get("usage", {}),
                model=response.body.get("model", model or self.default_model),
                finish_reason=response.body.get("finish_reason", "stop")
            )

        return LLMResponse(
            content="",
            usage={},
            model=model or self.default_model,
            finish_reason="error"
        )

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[StreamChunk]:
        """流式chat调用"""
        http = HTTPClient()

        full_content = []
        index = 0

        async for chunk in http.stream_request(
            HTTPRequest(
                url=f"{self.base_url}/api/v1/chat",
                method=HTTPMethod.POST,
                headers=self._get_headers(),
                json_data={
                    "messages": messages,
                    "model": model or self.default_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                },
                timeout=120.0
            )
        ):
            if chunk:
                try:
                    data = json.loads(chunk)
                    if data.get("type") == "chunk":
                        delta = data.get("delta", "")
                        full_content.append(delta)
                        yield StreamChunk(
                            delta=delta,
                            index=index,
                            done=False
                        )
                        index += 1
                    elif data.get("type") == "done":
                        yield StreamChunk(
                            delta="",
                            index=index,
                            done=True
                        )
                        break
                except json.JSONDecodeError:
                    continue

    async def sentiment_analysis(
        self,
        text: str,
        model: str = None
    ) -> Dict:
        """情绪分析"""
        http = HTTPClient()
        request = HTTPRequest(
            url=f"{self.base_url}/api/v1/sentiment",
            method=HTTPMethod.POST,
            headers=self._get_headers(),
            json_data={
                "text": text,
                "model": model or self.default_model
            },
            timeout=30.0
        )

        async with http:
            response = await http.request(request)

        if response.success and response.body:
            return response.body
        return {"sentiment": "neutral", "confidence": 0.5, "score": 0.0}

    async def stream_sentiment_analysis(
        self,
        text: str,
        model: str = None
    ) -> AsyncIterator[StreamChunk]:
        """流式情绪分析"""
        messages = [
            {"role": "system", "content": "你是一个专业的加密货币市场情绪分析师。"},
            {"role": "user", "content": f"分析以下文本的情绪（看涨/看跌/中性），返回JSON格式：{{\"sentiment\": \"...\", \"confidence\": 0.0-1.0, \"score\": -1.0到1.0}}\n\n文本: {text}"}
        ]

        async for chunk in self.stream_chat(messages, model=model):
            yield chunk

    async def structured_extraction(
        self,
        content: str,
        prompt: str,
        output_schema: Dict = None,
        model: str = None
    ) -> Dict:
        """结构化数据提取"""
        http = HTTPClient()
        request = HTTPRequest(
            url=f"{self.base_url}/api/v1/extract",
            method=HTTPMethod.POST,
            headers=self._get_headers(),
            json_data={
                "content": content,
                "prompt": prompt,
                "schema": output_schema,
                "model": model or self.default_model
            },
            timeout=60.0
        )

        async with http:
            response = await http.request(request)

        if response.success and response.body:
            return response.body
        return {"error": "LLM extraction failed"}

    async def news_analysis(
        self,
        title: str,
        content: str
    ) -> Dict:
        """新闻分析（情绪+事件类型+黑天鹅检测）"""
        http = HTTPClient()
        request = HTTPRequest(
            url=f"{self.base_url}/api/v1/news/analyze",
            method=HTTPMethod.POST,
            headers=self._get_headers(),
            json_data={
                "title": title,
                "content": content
            },
            timeout=30.0
        )

        async with http:
            response = await http.request(request)

        if response.success and response.body:
            return response.body
        return {
            "sentiment": "neutral",
            "confidence": 0.5,
            "event_type": "normal",
            "black_swan_score": 0.0,
            "urgency": "normal",
            "affected_markets": [],
            "affected_symbols": []
        }

    async def stream_news_analysis(
        self,
        title: str,
        content: str
    ) -> AsyncIterator[StreamChunk]:
        """流式新闻分析"""
        messages = [
            {"role": "system", "content": """你是一个专业的加密货币新闻分析专家。
分析新闻并返回JSON格式：
{
    "sentiment": "bullish/bearish/neutral",
    "confidence": 0.0-1.0,
    "event_type": "black_swan/white_swan/regulatory/security/geopolitical/market/technology/macro/normal",
    "black_swan_score": 0.0-1.0,
    "urgency": "critical/urgent/normal/low",
    "affected_markets": ["BTC", "ETH", ...],
    "affected_symbols": ["BTC", "ETH", ...]
}"""},
            {"role": "user", "content": f"标题: {title}\n内容: {content[:2000]}"}
        ]

        async for chunk in self.stream_chat(messages):
            yield chunk

    async def trader_statement_analysis(
        self,
        trader_name: str,
        content: str
    ) -> Dict:
        """交易员言论分析"""
        messages = [
            {"role": "system", "content": """你是一个加密货币交易员言论分析专家。
从交易员的社交媒体文本中提取结构化信息，返回JSON格式：
{
    "观点": "一句话概括核心观点",
    "情绪": "bullish/bearish/neutral",
    "情绪置信度": 0.0-1.0,
    "资产": ["BTC", "ETH", ...],
    "时间预期": "short/medium/long",
    "论据": ["理由1", "理由2"]
}"""},
            {"role": "user", "content": f"交易员: {trader_name}\n内容: {content}"}
        ]

        http = HTTPClient()
        request = HTTPRequest(
            url=f"{self.base_url}/api/v1/chat",
            method=HTTPMethod.POST,
            headers=self._get_headers(),
            json_data={
                "messages": messages,
                "model": self.default_model,
                "stream": False
            },
            timeout=60.0
        )

        async with http:
            response = await http.request(request)

        if response.success and response.body:
            try:
                return json.loads(response.body.get("content", "{}"))
            except json.JSONDecodeError:
                return {"error": "Failed to parse response"}
        return {"error": "Analysis failed"}

    async def batch_sentiment(
        self,
        texts: List[str],
        model: str = None
    ) -> List[Dict]:
        """批量情绪分析"""
        tasks = [self.sentiment_analysis(text, model) for text in texts]
        return await asyncio.gather(*tasks)


class LLMClientPool:
    """LLM客户端连接池"""

    def __init__(self, size: int = 5):
        self.size = size
        self.clients: List[LLMServiceClient] = []
        self._lock = asyncio.Lock()

    async def get_client(self) -> LLMServiceClient:
        """获取一个客户端"""
        async with self._lock:
            if not self.clients:
                for _ in range(self.size):
                    self.clients.append(LLMServiceClient())
            return self.clients.pop()

    async def return_client(self, client: LLMServiceClient):
        """归还客户端"""
        async with self._lock:
            if len(self.clients) < self.size:
                self.clients.append(client)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
