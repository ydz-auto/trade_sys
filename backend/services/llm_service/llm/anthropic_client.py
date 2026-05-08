"""
Anthropic Client
"""

import os
import asyncio
from typing import Dict, List, AsyncIterator
from dataclasses import dataclass

from infrastructure.logging import get_logger
logger = get_logger("llm.anthropic")


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


class AnthropicClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-5-haiku-20241022",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """同步Chat调用"""
        try:
            import httpx

            system_msg = ""
            filtered_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system_msg = msg.get("content", "")
                else:
                    filtered_messages.append(msg)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "system": system_msg,
                        "messages": filtered_messages,
                        "temperature": temperature
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return LLMResponse(
                        content=data.get("content", [{}])[0].get("text", ""),
                        usage={
                            "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                            "output_tokens": data.get("usage", {}).get("output_tokens", 0)
                        },
                        model=model,
                        finish_reason="stop"
                    )

            return LLMResponse(content="", usage={}, model=model, finish_reason="error")

        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            return LLMResponse(content="", usage={}, model=model, finish_reason="error")

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-5-haiku-20241022",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[StreamChunk]:
        """流式Chat调用"""
        try:
            import httpx

            system_msg = ""
            filtered_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system_msg = msg.get("content", "")
                else:
                    filtered_messages.append(msg)

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "post",
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "system": system_msg,
                        "messages": filtered_messages,
                        "temperature": temperature,
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
                                if chunk_data.get("type") == "content_block_delta":
                                    delta = chunk_data.get("delta", {}).get("text", "")
                                    if delta:
                                        yield StreamChunk(delta=delta, index=index, done=False)
                                        index += 1
                                elif chunk_data.get("type") == "message_stop":
                                    yield StreamChunk(delta="", index=index, done=True)
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            yield StreamChunk(delta="", index=0, done=True)
