"""
HTTP Client - HTTP客户端封装（支持重试、超时、并发、流式）
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass
from enum import Enum

from infrastructure.logging import get_logger
logger = get_logger("infrastructure.http")


class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


@dataclass
class HTTPResponse:
    """HTTP响应"""
    status_code: int
    headers: Dict
    body: Any
    text: str
    elapsed_ms: int
    success: bool


@dataclass
class HTTPRequest:
    """HTTP请求配置"""
    url: str
    method: HTTPMethod = HTTPMethod.GET
    headers: Optional[Dict] = None
    params: Optional[Dict] = None
    json_data: Optional[Dict] = None
    timeout: float = 10.0


class HTTPRetryConfig:
    """HTTP重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        retry_on_status: List[int] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on_status = retry_on_status or [429, 500, 502, 503, 504]


class HTTPClient:
    """HTTP客户端"""

    def __init__(self, retry_config: HTTPRetryConfig = None):
        self.retry_config = retry_config or HTTPRetryConfig()
        self.session = None

    async def __aenter__(self):
        import httpx
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()

    async def request(
        self,
        request: HTTPRequest,
        retry_config: HTTPRetryConfig = None
    ) -> HTTPResponse:
        """发送HTTP请求（带重试）"""
        config = retry_config or self.retry_config

        for attempt in range(config.max_retries + 1):
            start_time = time.time()

            try:
                response = await self._do_request(request)
                elapsed_ms = int((time.time() - start_time) * 1000)

                if response.status_code < 400:
                    return response

                if response.status_code in config.retry_on_status and attempt < config.max_retries:
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    logger.warning(
                        f"HTTP {response.status_code} on {request.url}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{config.max_retries + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue

                return response

            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)

                if attempt < config.max_retries:
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    logger.warning(
                        f"HTTP error on {request.url}: {e}, "
                        f"retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue

        return HTTPResponse(
            status_code=0,
            headers={},
            body=None,
            text="",
            elapsed_ms=0,
            success=False
        )

    async def _do_request(self, request: HTTPRequest) -> HTTPResponse:
        """执行单个HTTP请求"""
        if not self.session:
            import httpx
            async with httpx.AsyncClient(timeout=httpx.Timeout(request.timeout)) as session:
                return await self._execute(session, request)
        else:
            return await self._execute(self.session, request)

    async def _execute(self, session, request: HTTPRequest) -> HTTPResponse:
        """执行请求"""
        start_time = time.time()

        import httpx

        if request.method == HTTPMethod.GET:
            response = await session.get(
                request.url,
                headers=request.headers,
                params=request.params
            )
        elif request.method == HTTPMethod.POST:
            response = await session.post(
                request.url,
                headers=request.headers,
                params=request.params,
                json=request.json_data
            )
        elif request.method == HTTPMethod.PUT:
            response = await session.put(
                request.url,
                headers=request.headers,
                params=request.params,
                json=request.json_data
            )
        elif request.method == HTTPMethod.DELETE:
            response = await session.delete(
                request.url,
                headers=request.headers,
                params=request.params
            )
        else:
            raise ValueError(f"Unsupported method: {request.method}")

        elapsed_ms = int((time.time() - start_time) * 1000)

        try:
            body = response.json()
        except Exception:
            body = None

        return HTTPResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=body,
            text=response.text[:1000],
            elapsed_ms=elapsed_ms,
            success=response.status_code < 400
        )

    async def stream_request(
        self,
        request: HTTPRequest
    ) -> AsyncIterator[str]:
        """流式HTTP请求（用于LLM流式响应）"""
        import httpx

        async with httpx.AsyncClient(timeout=httpx.Timeout(request.timeout)) as client:
            async with client.stream(
                method=request.method.value,
                url=request.url,
                headers=request.headers,
                params=request.params,
                json=request.json_data
            ) as response:
                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk

    async def batch_request(
        self,
        requests: List[HTTPRequest],
        max_concurrency: int = 5
    ) -> List[HTTPResponse]:
        """批量并发请求"""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def bounded_request(req: HTTPRequest):
            async with semaphore:
                return await self.request(req)

        return await asyncio.gather(*[bounded_request(r) for r in requests])
