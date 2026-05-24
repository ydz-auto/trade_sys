"""
路由管理
"""

import re
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from infrastructure.security.api_gateway.config import HTTPMethod


@dataclass
class Route:
    path: str
    method: HTTPMethod
    handler: Callable
    endpoint: Optional[str] = None
    auth_required: bool = True
    rate_limit_key: str = "default"
    permissions: Optional[List[str]] = None


class Router:
    def __init__(self):
        self._routes: Dict[str, Route] = {}
        self._route_patterns: List[tuple] = []

    def add_route(
        self,
        path: str,
        method: HTTPMethod,
        handler: Callable,
        endpoint: Optional[str] = None,
        auth_required: bool = True,
        rate_limit_key: str = "default",
        permissions: Optional[List[str]] = None,
    ) -> None:
        route_key = f"{method.value}:{path}"
        route = Route(
            path=path,
            method=method,
            handler=handler,
            endpoint=endpoint or route_key,
            auth_required=auth_required,
            rate_limit_key=rate_limit_key,
            permissions=permissions,
        )
        self._routes[route_key] = route
        self._compile_route_pattern(path, method)

    def _compile_route_pattern(self, path: str, method: HTTPMethod):
        pattern = path
        param_names = []

        param_pattern = re.compile(r"\{(\w+)\}")
        matches = param_pattern.findall(path)
        for match in matches:
            param_names.append(match)
            pattern = pattern.replace(f"{{{match}}}", r"([^/]+)")

        pattern = f"^{pattern}$"

        self._route_patterns.append({
            "pattern": re.compile(pattern),
            "method": method,
            "param_names": param_names,
            "route_key": f"{method.value}:{path}",
        })

    def get_route(
        self,
        path: str,
        method: HTTPMethod,
    ) -> Optional[Route]:
        route_key = f"{method.value}:{path}"
        if route_key in self._routes:
            return self._routes[route_key]

        for route_info in self._route_patterns:
            if route_info["method"] != method:
                continue

            match = route_info["pattern"].match(path)
            if match:
                route_key = route_info["route_key"]
                return self._routes.get(route_key)

        return None

    def match_route(
        self,
        path: str,
        method: HTTPMethod,
    ) -> tuple[Optional[Route], Optional[Dict[str, str]]]:
        route = self.get_route(path, method)
        if not route:
            return None, None

        for route_info in self._route_patterns:
            if route_info["method"] != method:
                continue

            match = route_info["pattern"].match(path)
            if match:
                params = dict(zip(route_info["param_names"], match.groups()))
                return route, params

        return route, None

    def get(self, path: str, **kwargs):
        def decorator(func: Callable):
            self.add_route(path, HTTPMethod.GET, func, **kwargs)
            return func
        return decorator

    def post(self, path: str, **kwargs):
        def decorator(func: Callable):
            self.add_route(path, HTTPMethod.POST, func, **kwargs)
            return func
        return decorator

    def put(self, path: str, **kwargs):
        def decorator(func: Callable):
            self.add_route(path, HTTPMethod.PUT, func, **kwargs)
            return func
        return decorator

    def delete(self, path: str, **kwargs):
        def decorator(func: Callable):
            self.add_route(path, HTTPMethod.DELETE, func, **kwargs)
            return func
        return decorator

    def patch(self, path: str, **kwargs):
        def decorator(func: Callable):
            self.add_route(path, HTTPMethod.PATCH, func, **kwargs)
            return func
        return decorator

    @property
    def routes(self) -> List[Route]:
        return list(self._routes.values())


class RouteGroup:
    def __init__(self, prefix: str, router: Optional[Router] = None):
        self.prefix = prefix
        self.router = router or Router()
        self._sub_groups: List["RouteGroup"] = []

    def add_sub_group(self, group: "RouteGroup"):
        self._sub_groups.append(group)

    def get(self, path: str, **kwargs):
        full_path = f"{self.prefix}{path}" if path.startswith("/") else f"{self.prefix}/{path}"
        return self.router.get(full_path, **kwargs)

    def post(self, path: str, **kwargs):
        full_path = f"{self.prefix}{path}" if path.startswith("/") else f"{self.prefix}/{path}"
        return self.router.post(full_path, **kwargs)

    def put(self, path: str, **kwargs):
        full_path = f"{self.prefix}{path}" if path.startswith("/") else f"{self.prefix}/{path}"
        return self.router.put(full_path, **kwargs)

    def delete(self, path: str, **kwargs):
        full_path = f"{self.prefix}{path}" if path.startswith("/") else f"{self.prefix}/{path}"
        return self.router.delete(full_path, **kwargs)

    def include_router(self, router: Router):
        for route in router.routes:
            new_path = f"{self.prefix}{route.path}" if route.path.startswith("/") else f"{self.prefix}/{route.path}"
            self.router.add_route(
                new_path,
                route.method,
                route.handler,
                endpoint=route.endpoint,
                auth_required=route.auth_required,
                rate_limit_key=route.rate_limit_key,
                permissions=route.permissions,
            )