"""
MiniMax Client
"""

import os
import asyncio
from typing import Dict, List, AsyncIterator
from dataclasses import dataclass

from infrastructure.logging import get_logger
logger = get_logger("llm.minimax")


@dataclass
class LLMResponse:
    content: str
    usage: Dict[str, int]
    model: str
    finish_reason: str = "stop"


@dataclass
class StreamChunk:
    delta: str
    index: int
    done: bool = False


class MiniMaxClient:
    def __init__(self, api_key: str = None, api_base: str = None):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        self.base_url = api_base or os.getenv("MINIMAX_API_BASE", "https://api.minimax.chat/v1")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "MiniMax-Text-01",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """同步Chat调用"""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return LLMResponse(
                        content=data["choices"][0]["message"]["content"],
                        usage=data.get("usage", {}),
                        model=model,
                        finish_reason=data["choices"][0].get("finish_reason", "stop")
                    )

            return LLMResponse(content="", usage={}, model=model, finish_reason="error")

        except Exception as e:
            logger.error(f"MiniMax chat error: {e}")
            return LLMResponse(content="", usage={}, model=model, finish_reason="error")

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "MiniMax-Text-01",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[StreamChunk]:
        """流式Chat调用"""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "post",
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True
                    },
                    timeout=120.0
                ) as response:
                    index = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                yield StreamChunk(delta="", index=index, done=True)
                                break
                            import json
                            try:
                                chunk_data = json.loads(data)
                                delta = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield StreamChunk(delta=delta, index=index, done=False)
                                    index += 1
                            except json.JSONDecodeError:
                                continue

                    yield StreamChunk(delta="", index=index, done=True)

        except Exception as e:
            logger.error(f"MiniMax stream error: {e}")
            yield StreamChunk(delta="", index=0, done=True)
