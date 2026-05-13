"""
Cache Module - 缓存模块
提供多级缓存和异步缓存管理
"""

from typing import Dict, Any, Optional, List, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import hashlib
import json
import time
from functools import wraps

from infrastructure.logging import get_logger

logger = get_logger("shared.cache")

T = TypeVar('T')


class CacheLevel(str, Enum):
    """缓存层级"""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DISK = "l3_disk"


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    key: str
    value: T
    created_at: float
    ttl_seconds: int
    
    hits: int = 0
    last_access: float = field(default_factory=time.time)
    
    tags: List[str] = field(default_factory=list)
    
    @property
    def expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return time.time() - self.created_at > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class MemoryCache(Generic[T]):
    """内存缓存"""
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = asyncio.Lock()
        
        self._hits = 0
        self._misses = 0
        
        # 后台清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False
    
    async def start_cleanup(self, interval: float = 60.0):
        """启动后台过期清理任务"""
        if self._cleanup_running:
            return
            
        self._cleanup_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))
    
    async def stop_cleanup(self):
        """停止后台清理任务"""
        self._cleanup_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
    
    async def _cleanup_loop(self, interval: float):
        """后台清理循环"""
        while self._cleanup_running:
            try:
                await asyncio.sleep(interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    async def _cleanup_expired(self):
        """清理过期的缓存条目"""
        async with self._lock:
            now = time.time()
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.expired
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
                
            if keys_to_delete:
                logger.debug(f"Cleaned up {len(keys_to_delete)} expired cache entries")
    
    def _hash_key(self, key: str) -> str:
        if len(key) <= 64:
            return key
        return hashlib.sha256(key.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[T]:
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.expired:
                del self._cache[key]
                self._misses += 1
                return None
            
            entry.hits += 1
            entry.last_access = time.time()
            self._hits += 1
            
            return entry.value
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        async with self._lock:
            if len(self._cache) >= self.max_size:
                await self._evict_lru()
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl or self.default_ttl,
                tags=tags or [],
            )
            
            self._cache[key] = entry
            return True
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self):
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    async def _evict_lru(self):
        if not self._cache:
            return
        
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_access
        )
        
        for key in sorted_keys[:len(sorted_keys) // 4]:
            del self._cache[key]
    
    async def invalidate_by_tag(self, tag: str):
        async with self._lock:
            keys_to_delete = [
                k for k, v in self._cache.items()
                if tag in v.tags
            ]
            for key in keys_to_delete:
                del self._cache[key]
    
    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total
    
    @property
    def size(self) -> int:
        return len(self._cache)
    
    def stats(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.2%}",
        }


class MultiLevelCache:
    """多级缓存"""
    
    def __init__(self):
        self.l1: MemoryCache = MemoryCache(max_size=5000, default_ttl=300)
        self._l2_enabled = False
        self._l2_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        value = await self.l1.get(key)
        if value is not None:
            return value
        
        if self._l2_enabled and self._l2_client:
            try:
                l2_value = await self._l2_client.get(key)
                if l2_value is not None:
                    await self.l1.set(key, l2_value)
                    return l2_value
            except Exception as e:
                logger.warning(f"L2 cache error: {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        await self.l1.set(key, value, ttl, tags)
        
        if self._l2_enabled and self._l2_client:
            try:
                await self._l2_client.set(key, value, ttl or 300)
            except Exception as e:
                logger.warning(f"L2 cache set error: {e}")
        
        return True
    
    async def delete(self, key: str) -> bool:
        result = await self.l1.delete(key)
        
        if self._l2_enabled and self._l2_client:
            try:
                await self._l2_client.delete(key)
            except Exception:
                pass
        
        return result
    
    async def clear(self):
        await self.l1.clear()
    
    def stats(self) -> Dict[str, Any]:
        return {
            "l1": self.l1.stats(),
            "l2_enabled": self._l2_enabled,
        }


_cache: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """获取缓存实例"""
    global _cache
    if _cache is None:
        _cache = MultiLevelCache()
    return _cache


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    tags: Optional[List[str]] = None,
):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache()
            
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            
            await cache.set(cache_key, result, ttl, tags)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class AsyncBatchProcessor:
    """异步批处理器"""
    
    def __init__(
        self,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        max_queue_size: int = 10000,
    ):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._batch_handler: Optional[Callable] = None
    
    def set_handler(self, handler: Callable):
        self._batch_handler = handler
    
    async def add(self, item: Any) -> bool:
        try:
            self._queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            logger.warning("Batch processor queue full")
            return False
    
    async def start(self):
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("Batch processor started")
    
    async def stop(self):
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            self._processor_task = None
        
        await self._flush_remaining()
        logger.info("Batch processor stopped")
    
    async def _process_loop(self):
        batch = []
        last_flush = time.time()
        
        while self._running:
            try:
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.1
                )
                batch.append(item)
                
                if len(batch) >= self.batch_size:
                    await self._process_batch(batch)
                    batch = []
                    last_flush = time.time()
                
            except asyncio.TimeoutError:
                if batch and time.time() - last_flush >= self.flush_interval:
                    await self._process_batch(batch)
                    batch = []
                    last_flush = time.time()
            
            except asyncio.CancelledError:
                break
            
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
    
    async def _process_batch(self, batch: List[Any]):
        if not batch or not self._batch_handler:
            return
        
        try:
            if asyncio.iscoroutinefunction(self._batch_handler):
                await self._batch_handler(batch)
            else:
                self._batch_handler(batch)
            
            logger.debug(f"Processed batch of {len(batch)} items")
            
        except Exception as e:
            logger.error(f"Batch handler error: {e}")
    
    async def _flush_remaining(self):
        batch = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                batch.append(item)
            except asyncio.QueueEmpty:
                break
        
        if batch:
            await self._process_batch(batch)
    
    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


class RateLimiter:
    """速率限制器"""
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: float = 1.0,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        self._requests: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str = "default") -> bool:
        async with self._lock:
            now = time.time()
            
            if key not in self._requests:
                self._requests[key] = []
            
            self._requests[key] = [
                t for t in self._requests[key]
                if now - t < self.window_seconds
            ]
            
            if len(self._requests[key]) >= self.max_requests:
                return False
            
            self._requests[key].append(now)
            return True
    
    async def wait_and_acquire(self, key: str = "default") -> bool:
        while not await self.is_allowed(key):
            await asyncio.sleep(0.01)
        return True
    
    def reset(self, key: Optional[str] = None):
        if key:
            self._requests.pop(key, None)
        else:
            self._requests.clear()


class ConnectionPool:
    """连接池"""
    
    def __init__(
        self,
        factory: Callable,
        max_connections: int = 10,
        idle_timeout: float = 300.0,
    ):
        self.factory = factory
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._active: int = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> Any:
        async with self._lock:
            if not self._pool.empty():
                self._active += 1
                return await self._pool.get()
            
            if self._active < self.max_connections:
                conn = await self._create_connection()
                self._active += 1
                return conn
        
        return await self._pool.get()
    
    async def release(self, conn: Any):
        async with self._lock:
            if self._active > 0:
                self._active -= 1
        
        try:
            self._pool.put_nowait(conn)
        except asyncio.QueueFull:
            await self._close_connection(conn)
    
    async def _create_connection(self) -> Any:
        if asyncio.iscoroutinefunction(self.factory):
            return await self.factory()
        return self.factory()
    
    async def _close_connection(self, conn: Any):
        if hasattr(conn, 'close'):
            if asyncio.iscoroutinefunction(conn.close):
                await conn.close()
            else:
                conn.close()
    
    async def close_all(self):
        async with self._lock:
            while not self._pool.empty():
                conn = await self._pool.get()
                await self._close_connection(conn)
            self._active = 0
    
    @property
    def stats(self) -> Dict[str, int]:
        return {
            "active": self._active,
            "idle": self._pool.qsize(),
            "max": self.max_connections,
        }
