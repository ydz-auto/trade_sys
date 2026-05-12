"""
HTTP Client - 统一的 HTTP 客户端工具
构建在 shared.http_client 之上，提供更高级的功能
"""
import asyncio
import time
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field

import httpx

from shared.http_client import HTTPClient as SharedHTTPClient
from shared.http_client import HTTPRequest, HTTPMethod
from infrastructure.logging import get_logger
from infrastructure.resilience import CircuitBreaker, CircuitBreakerConfig, RetryPolicy, RetryConfig, FallbackChain

logger = get_logger("utils.http_client")


@dataclass
class HTTPResponse:
    """HTTP 响应"""
    url: str
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    text: Optional[str] = None
    json: Optional[Dict[str, Any]] = None
    success: bool = True
    error: Optional[str] = None
    latency_ms: float = 0


class EnhancedHTTPClient:
    """增强的 HTTP 客户端
    
    带重试、熔断、限流的 HTTP 客户端
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        default_headers: Optional[Dict[str, str]] = None,
        enable_circuit_breaker: bool = True,
        enable_retry: bool = True
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.default_headers = default_headers or {}
        
        # 内部客户端
        self._shared_client = SharedHTTPClient()
        self._async_client: Optional[httpx.AsyncClient] = None
        
        # 弹性能力
        self._enable_circuit_breaker = enable_circuit_breaker
        self._enable_retry = enable_retry
        
        # 按域名的熔断器
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # 重试策略
        self._retry_policy = RetryPolicy(RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            backoff_multiplier=2.0
        ))
        
        # 速率限制
        self._request_timestamps: Dict[str, list] = {}
        self._rate_limits: Dict[str, Dict[str, int]] = {}  # domain -> {requests, seconds}
    
    async def _get_or_create_circuit_breaker(self, url: str) -> Optional[CircuitBreaker]:
        """获取或创建熔断器"""
        if not self._enable_circuit_breaker:
            return None
        
        # 提取域名
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        
        if domain not in self._circuit_breakers:
            config = CircuitBreakerConfig(
                name=f"http_{domain}",
                failure_threshold=5,
                recovery_timeout=60.0
            )
            self._circuit_breakers[domain] = CircuitBreaker(config)
        
        return self._circuit_breakers[domain]
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """获取异步客户端"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                base_url=self.base_url,
                headers=self.default_headers
            )
        return self._async_client
    
    async def request(
        self,
        url: str,
        method: HTTPMethod = HTTPMethod.GET,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> HTTPResponse:
        """发送 HTTP 请求
        
        带熔断和重试
        """
        start_time = time.time()
        
        full_url = self._build_url(url)
        request_headers = {**self.default_headers, **(headers or {})}
        
        async def _do_request() -> HTTPResponse:
            client = await self._get_async_client()
            
            request_kwargs = {
                "headers": request_headers,
                "params": params,
                "timeout": timeout or self.timeout
            }
            
            if json is not None:
                request_kwargs["json"] = json
            if data is not None:
                request_kwargs["data"] = data
            
            try:
                response = await client.request(
                    method=method.value,
                    url=full_url,
                    **request_kwargs
                )
                
                result = HTTPResponse(
                    url=str(response.url),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    text=response.text,
                    success=response.is_success
                )
                
                # 尝试解析 JSON
                try:
                    result.json = response.json()
                except Exception:
                    pass
                
                return result
                
            except Exception as e:
                return HTTPResponse(
                    url=full_url,
                    status_code=0,
                    success=False,
                    error=str(e)
                )
        
        # 获取熔断器
        circuit_breaker = await self._get_or_create_circuit_breaker(full_url)
        
        try:
            if circuit_breaker:
                if self._enable_retry:
                    result = await circuit_breaker.execute(
                        lambda: self._retry_policy.execute(_do_request)
                    )
                else:
                    result = await circuit_breaker.execute(_do_request)
            else:
                if self._enable_retry:
                    result = await self._retry_policy.execute(_do_request)
                else:
                    result = await _do_request()
            
            result.latency_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            return HTTPResponse(
                url=full_url,
                status_code=0,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def get(
        self,
        url: str,
        **kwargs
    ) -> HTTPResponse:
        """GET 请求"""
        return await self.request(url, method=HTTPMethod.GET, **kwargs)
    
    async def post(
        self,
        url: str,
        **kwargs
    ) -> HTTPResponse:
        """POST 请求"""
        return await self.request(url, method=HTTPMethod.POST, **kwargs)
    
    async def put(
        self,
        url: str,
        **kwargs
    ) -> HTTPResponse:
        """PUT 请求"""
        return await self.request(url, method=HTTPMethod.PUT, **kwargs)
    
    async def delete(
        self,
        url: str,
        **kwargs
    ) -> HTTPResponse:
        """DELETE 请求"""
        return await self.request(url, method=HTTPMethod.DELETE, **kwargs)
    
    def _build_url(self, url: str) -> str:
        """构建完整 URL"""
        if url.startswith(("http://", "https://")):
            return url
        if self.base_url:
            if self.base_url.endswith("/") and url.startswith("/"):
                return self.base_url + url[1:]
            elif self.base_url.endswith("/") or url.startswith("/"):
                return self.base_url + url
            else:
                return f"{self.base_url}/{url}"
        return url
    
    async def close(self):
        """关闭客户端"""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 便捷函数
_http_client_instance: Optional[EnhancedHTTPClient] = None


def get_http_client() -> EnhancedHTTPClient:
    """获取 HTTP 客户端单例"""
    global _http_client_instance
    if _http_client_instance is None:
        _http_client_instance = EnhancedHTTPClient()
    return _http_client_instance
