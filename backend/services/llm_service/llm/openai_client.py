"""
OpenAI Client
"""

import os
import json
import asyncio
from typing import Dict, List, AsyncIterator
from dataclasses import dataclass

from infrastructure.logging import get_logger
logger = get_logger("llm.openai")


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


class OpenAIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """同步Chat调用"""
        try:
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                model=model,
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            return LLMResponse(
                content="",
                usage={},
                model=model,
                finish_reason="error"
            )

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[StreamChunk]:
        """流式Chat调用"""
        try:
            stream = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            index = 0
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield StreamChunk(
                        delta=chunk.choices[0].delta.content,
                        index=index,
                        done=False
                    )
                    index += 1

                if chunk.choices[0].finish_reason:
                    yield StreamChunk(
                        delta="",
                        index=index,
                        done=True
                    )
                    break

        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            yield StreamChunk(delta="", index=0, done=True)
