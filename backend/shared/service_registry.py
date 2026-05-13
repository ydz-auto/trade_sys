"""
Service Registry - 服务注册中心
去中心化服务发现机制
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import hashlib

from infrastructure.logging import get_logger

logger = get_logger("shared.service_registry")


class ServiceStatus(str, Enum):
    """服务状态"""
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


@dataclass
class ServiceEndpoint:
    """服务端点"""
    host: str
    port: int
    protocol: str = "http"
    
    def __str__(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def url(self) -> str:
        return str(self)


@dataclass
class ServiceInfo:
    """服务信息"""
    service_id: str
    service_name: str
    version: str
    
    endpoints: List[ServiceEndpoint] = field(default_factory=list)
    
    status: ServiceStatus = ServiceStatus.STARTING
    
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    registered_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    last_heartbeat: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "version": self.version,
            "endpoints": [{"host": e.host, "port": e.port, "protocol": e.protocol} for e in self.endpoints],
            "status": self.status.value,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInfo":
        endpoints = [
            ServiceEndpoint(host=e["host"], port=e["port"], protocol=e.get("protocol", "http"))
            for e in data.get("endpoints", [])
        ]
        return cls(
            service_id=data["service_id"],
            service_name=data["service_name"],
            version=data["version"],
            endpoints=endpoints,
            status=ServiceStatus(data.get("status", "starting")),
            capabilities=data.get("capabilities", []),
            dependencies=data.get("dependencies", []),
            registered_at=data.get("registered_at", 0),
            last_heartbeat=data.get("last_heartbeat", 0),
            metadata=data.get("metadata", {}),
        )


class ServiceRegistry:
    """服务注册中心
    
    去中心化的服务注册和发现机制
    - 服务注册
    - 服务发现
    - 健康检查
    - 服务注销
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceInfo] = {}
        self._name_index: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
        
        self._health_check_interval = 30
        self._health_check_task: Optional[asyncio.Task] = None
        
        self._subscribers: Dict[str, List[Callable]] = {
            "register": [],
            "unregister": [],
            "status_change": [],
        }
    
    def generate_service_id(self, service_name: str, instance_id: str = "") -> str:
        """生成服务ID"""
        timestamp = int(datetime.now().timestamp() * 1000)
        raw = f"{service_name}:{instance_id}:{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    async def register(
        self,
        service_name: str,
        version: str,
        endpoints: List[ServiceEndpoint],
        capabilities: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        instance_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """注册服务"""
        async with self._lock:
            service_id = self.generate_service_id(service_name, instance_id or "")
            
            service = ServiceInfo(
                service_id=service_id,
                service_name=service_name,
                version=version,
                endpoints=endpoints,
                capabilities=capabilities or [],
                dependencies=dependencies or [],
                metadata=metadata or {},
            )
            
            self._services[service_id] = service
            
            if service_name not in self._name_index:
                self._name_index[service_name] = []
            self._name_index[service_name].append(service_id)
            
            logger.info(f"Service registered: {service_name} ({service_id})")
            
            await self._notify_subscribers("register", service)
            
            return service_id
    
    async def unregister(self, service_id: str) -> bool:
        """注销服务"""
        async with self._lock:
            if service_id not in self._services:
                return False
            
            service = self._services[service_id]
            
            del self._services[service_id]
            
            if service.service_name in self._name_index:
                if service_id in self._name_index[service.service_name]:
                    self._name_index[service.service_name].remove(service_id)
            
            logger.info(f"Service unregistered: {service.service_name} ({service_id})")
            
            await self._notify_subscribers("unregister", service)
            
            return True
    
    async def update_status(self, service_id: str, status: ServiceStatus) -> bool:
        """更新服务状态"""
        async with self._lock:
            if service_id not in self._services:
                return False
            
            service = self._services[service_id]
            old_status = service.status
            service.status = status
            service.last_heartbeat = int(datetime.now().timestamp() * 1000)
            
            if old_status != status:
                await self._notify_subscribers("status_change", service, old_status)
            
            return True
    
    async def heartbeat(self, service_id: str) -> bool:
        """服务心跳"""
        return await self.update_status(service_id, ServiceStatus.HEALTHY)
    
    async def get_service(self, service_id: str) -> Optional[ServiceInfo]:
        """获取服务信息"""
        return self._services.get(service_id)
    
    async def discover(
        self,
        service_name: str,
        status_filter: Optional[ServiceStatus] = None,
    ) -> List[ServiceInfo]:
        """发现服务"""
        async with self._lock:
            service_ids = self._name_index.get(service_name, [])
            services = []
            
            for sid in service_ids:
                service = self._services.get(sid)
                if service:
                    if status_filter is None or service.status == status_filter:
                        services.append(service)
            
            return services
    
    async def discover_one(
        self,
        service_name: str,
        status_filter: Optional[ServiceStatus] = None,
    ) -> Optional[ServiceInfo]:
        """发现单个服务（负载均衡）"""
        services = await self.discover(service_name, status_filter)
        
        if not services:
            return None
        
        return services[0]
    
    async def discover_with_capability(
        self,
        capability: str,
        status_filter: Optional[ServiceStatus] = None,
    ) -> List[ServiceInfo]:
        """根据能力发现服务"""
        async with self._lock:
            results = []
            
            for service in self._services.values():
                if capability in service.capabilities:
                    if status_filter is None or service.status == status_filter:
                        results.append(service)
            
            return results
    
    async def get_all_services(
        self,
        status_filter: Optional[ServiceStatus] = None,
    ) -> List[ServiceInfo]:
        """获取所有服务"""
        async with self._lock:
            if status_filter is None:
                return list(self._services.values())
            return [s for s in self._services.values() if s.status == status_filter]
    
    async def get_dependencies(self, service_id: str) -> Dict[str, List[ServiceInfo]]:
        """获取服务依赖"""
        service = await self.get_service(service_id)
        if not service:
            return {}
        
        dependencies = {}
        for dep_name in service.dependencies:
            deps = await self.discover(dep_name)
            if deps:
                dependencies[dep_name] = deps
        
        return dependencies
    
    def subscribe(self, event: str, callback: Callable):
        """订阅事件"""
        if event in self._subscribers:
            self._subscribers[event].append(callback)
    
    def unsubscribe(self, event: str, callback: Callable):
        """取消订阅"""
        if event in self._subscribers and callback in self._subscribers[event]:
            self._subscribers[event].remove(callback)
    
    async def _notify_subscribers(self, event: str, *args):
        """通知订阅者"""
        if event not in self._subscribers:
            return
        
        for callback in self._subscribers[event]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    callback(*args)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_check(self):
        """执行健康检查"""
        async with self._lock:
            now = int(datetime.now().timestamp() * 1000)
            threshold = self._health_check_interval * 3 * 1000
            
            for service in self._services.values():
                if service.status not in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]:
                    continue
                
                if now - service.last_heartbeat > threshold:
                    service.status = ServiceStatus.UNHEALTHY
                    await self._notify_subscribers("status_change", service, ServiceStatus.HEALTHY)
                    logger.warning(f"Service heartbeat timeout: {service.service_name}")
    
    async def start_health_check(self):
        """启动健康检查"""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop_health_check(self):
        """停止健康检查"""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None


_service_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """获取服务注册中心单例"""
    global _service_registry
    if _service_registry is None:
        _service_registry = ServiceRegistry()
    return _service_registry


class ServiceClient:
    """服务客户端
    
    封装服务发现和调用的客户端
    """
    
    def __init__(self, registry: Optional[ServiceRegistry] = None):
        self.registry = registry or get_service_registry()
        self._cache: Dict[str, ServiceInfo] = {}
        self._cache_ttl = 60
    
    async def get_endpoint(
        self,
        service_name: str,
        protocol: str = "http",
    ) -> Optional[ServiceEndpoint]:
        """获取服务端点"""
        cache_key = f"{service_name}:{protocol}"
        
        if cache_key in self._cache:
            service = self._cache[cache_key]
            if service.status == ServiceStatus.HEALTHY:
                for endpoint in service.endpoints:
                    if endpoint.protocol == protocol:
                        return endpoint
        
        service = await self.registry.discover_one(service_name, ServiceStatus.HEALTHY)
        
        if service:
            self._cache[cache_key] = service
            for endpoint in service.endpoints:
                if endpoint.protocol == protocol:
                    return endpoint
        
        return None
    
    async def call_service(
        self,
        service_name: str,
        path: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """调用服务"""
        import aiohttp
        
        endpoint = await self.get_endpoint(service_name)
        if not endpoint:
            logger.error(f"Service not found: {service_name}")
            return None
        
        url = f"{endpoint.url}{path}"
        
        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(url) as response:
                        return await response.json()
                elif method == "POST":
                    async with session.post(url, json=data) as response:
                        return await response.json()
                elif method == "PUT":
                    async with session.put(url, json=data) as response:
                        return await response.json()
                elif method == "DELETE":
                    async with session.delete(url) as response:
                        return await response.json()
        except Exception as e:
            logger.error(f"Service call failed: {e}")
            return None
        
        return None
    
    def invalidate_cache(self, service_name: Optional[str] = None):
        """使缓存失效"""
        if service_name:
            keys_to_remove = [k for k in self._cache if k.startswith(service_name)]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()


_service_client: Optional[ServiceClient] = None


def get_service_client() -> ServiceClient:
    """获取服务客户端单例"""
    global _service_client
    if _service_client is None:
        _service_client = ServiceClient()
    return _service_client
