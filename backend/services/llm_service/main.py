"""
LLM Service - 独立LLM微服务（支持流式调用）
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from infrastructure.logging import LoggerFactory, LogType
from infrastructure.logging.config import LOG_LEVELS as CONFIG_LOG_LEVELS
from shared.config.defaults.infrastructure import LOGGING_CONFIGS

from .config import get_settings
from .llm.openai_client import OpenAIClient
from .llm.anthropic_client import AnthropicClient
from .llm.minimax_client import MiniMaxClient
from .services.sentiment_analyzer import SentimentAnalyzer
from .services.news_extractor import NewsExtractor
from .services.social_analyzer import SocialAnalyzer
from .cache.response_cache import ResponseCache

logger = LoggerFactory.get_logger("llm_service", LogType.SYSTEM)

settings = get_settings()

llm_clients = {
    "openai": OpenAIClient(),
    "anthropic": AnthropicClient(),
    "minimax": MiniMaxClient(),
}

sentiment_analyzer = SentimentAnalyzer()
news_extractor = NewsExtractor()
social_analyzer = SocialAnalyzer()
response_cache = ResponseCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = os.getenv("LOG_LEVEL", LOGGING_CONFIGS.get("logging.system_level", "INFO"))
    LoggerFactory.initialize(log_dir="logs", log_level=log_level)
    logger.info("LLM Service starting...")
    yield
    logger.info("LLM Service shutting down...")


app = FastAPI(
    title="LLM Service",
    description="LLM微服务 - 情绪分析、结构化提取、策略解释",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def generate_sse_chunks(stream):
    """生成SSE格式的流式响应"""
    async for chunk in stream:
        if chunk.done:
            yield {"event": "done", "data": json.dumps({"done": True})}
        else:
            yield {"event": "chunk", "data": json.dumps({"delta": chunk.delta, "index": chunk.index})}
    yield {"event": "done", "data": json.dumps({"done": True, "final": True})}


@app.post("/api/v1/chat")
async def chat(request: Request):
    """通用Chat接口（支持流式）"""
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "gpt-4o-mini")
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens", 2000)
    stream = body.get("stream", False)

    provider = "openai"
    if model.startswith("gpt"):
        provider = "openai"
    elif model.startswith("claude"):
        provider = "anthropic"
    elif model.startswith("minimax"):
        provider = "minimax"

    client = llm_clients.get(provider)
    if not client:
        raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")

    try:
        if stream:
            return EventSourceResponse(generate_sse_chunks(
                client.stream_chat(messages, model, temperature, max_tokens)
            ))
        else:
            result = await client.chat(messages, model, temperature, max_tokens)
            return {
                "content": result.content,
                "usage": result.usage,
                "model": model,
                "finish_reason": result.finish_reason
            }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sentiment")
async def sentiment_analysis(request: Request):
    """情绪分析接口"""
    body = await request.json()
    text = body.get("text", "")
    model = body.get("model", "gpt-4o-mini")

    cache_key = f"sentiment:{hash(text)}"
    cached = await response_cache.get(cache_key)
    if cached:
        return cached

    result = await sentiment_analyzer.analyze(text, model)

    await response_cache.set(cache_key, result, ttl=3600)
    return result


@app.post("/api/v1/extract")
async def structured_extraction(request: Request):
    """结构化数据提取接口"""
    body = await request.json()
    content = body.get("content", "")
    prompt = body.get("prompt", "")
    schema = body.get("schema")
    model = body.get("model", "gpt-4o-mini")

    cache_key = f"extract:{hash(content + prompt)}"
    cached = await response_cache.get(cache_key)
    if cached:
        return cached

    result = await news_extractor.extract(content, prompt, schema, model)

    await response_cache.set(cache_key, result, ttl=3600)
    return result


@app.post("/api/v1/news/analyze")
async def news_analysis(request: Request):
    """新闻分析接口"""
    body = await request.json()
    title = body.get("title", "")
    content = body.get("content", "")

    cache_key = f"news:{hash(title)}"
    cached = await response_cache.get(cache_key)
    if cached:
        return cached

    result = await news_extractor.analyze_news(title, content)

    await response_cache.set(cache_key, result, ttl=1800)
    return result


@app.post("/api/v1/social/analyze")
async def social_analysis(request: Request):
    """社交媒体分析接口"""
    body = await request.json()
    content = body.get("content", "")
    platform = body.get("platform", "twitter")

    result = await social_analyzer.analyze(content, platform)
    return result


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy", "service": "llm_service"}


@app.get("/ready")
async def ready():
    """就绪检查"""
    return {
        "status": "ready",
        "models": list(llm_clients.keys()),
        "cache_size": await response_cache.size()
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("LLM_SERVICE_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
