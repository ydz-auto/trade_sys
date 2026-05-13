"""
Permission Manager - 权限管理器
基于角色的访问控制 (RBAC) 和配置权限管理
"""

from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from infrastructure.logging import get_logger

logger = get_logger("shared.permission")


class PermissionAction(str, Enum):
    """权限动作"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class PermissionScope(str, Enum):
    """权限范围"""
    GLOBAL = "global"
    SERVICE = "service"
    USER = "user"
    STRATEGY = "strategy"


@dataclass
class Role:
    """角色"""
    role_id: str
    name: str
    description: str = ""
    
    permissions: Set[str] = field(default_factory=set)
    
    parent_role: Optional[str] = None
    
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    
    def has_permission(self, permission: str) -> bool:
        if permission in self.permissions:
            return True
        return False


@dataclass
class Permission:
    """权限定义"""
    permission_id: str
    name: str
    resource_type: str
    
    description: str = ""
    resource_pattern: str = "*"
    
    actions: Set[PermissionAction] = field(default_factory=set)
    
    scope: PermissionScope = PermissionScope.GLOBAL
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, resource: str) -> bool:
        if self.resource_pattern == "*":
            return True
        
        if self.resource_pattern.endswith("*"):
            prefix = self.resource_pattern[:-1]
            return resource.startswith(prefix)
        
        return resource == self.resource_pattern
    
    def allows(self, action: PermissionAction) -> bool:
        if PermissionAction.ADMIN in self.actions:
            return True
        return action in self.actions


@dataclass
class User:
    """用户"""
    user_id: str
    username: str
    
    role_ids: Set[str] = field(default_factory=set)
    
    is_active: bool = True
    
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    last_login: Optional[int] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessLog:
    """访问日志"""
    user_id: str
    action: str
    resource: str
    result: str
    
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    
    details: Dict[str, Any] = field(default_factory=dict)


class PermissionManager:
    """权限管理器
    
    实现基于角色的访问控制 (RBAC)
    - 角色管理
    - 权限分配
    - 访问控制
    - 审计日志
    """
    
    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._permissions: Dict[str, Permission] = {}
        self._users: Dict[str, User] = {}
        self._user_roles: Dict[str, Set[str]] = {}
        
        self._access_logs: List[AccessLog] = []
        self._max_log_size = 10000
        
        self._lock = asyncio.Lock()
        
        self._default_roles: Dict[str, Role] = {}
        self._sensitive_configs: Set[str] = set()
        
        self._setup_default_roles()
    
    def _setup_default_roles(self):
        """设置默认角色"""
        admin_role = Role(
            role_id="admin",
            name="Administrator",
            description="Full system access",
            permissions={"*"},
        )
        
        operator_role = Role(
            role_id="operator",
            name="Operator",
            description="Operational access",
            permissions={
                "config:read",
                "config:write:datasource",
                "config:write:trading",
                "service:read",
                "service:restart",
            },
        )
        
        viewer_role = Role(
            role_id="viewer",
            name="Viewer",
            description="Read-only access",
            permissions={
                "config:read",
                "service:read",
                "state:read",
            },
        )
        
        strategy_role = Role(
            role_id="strategy",
            name="Strategy Runner",
            description="Strategy execution access",
            permissions={
                "config:read:strategy",
                "config:write:strategy",
                "state:read",
                "state:write:strategy",
            },
        )
        
        self._roles["admin"] = admin_role
        self._roles["operator"] = operator_role
        self._roles["viewer"] = viewer_role
        self._roles["strategy"] = strategy_role
        
        self._sensitive_configs = {
            "api_key",
            "api_secret",
            "password",
            "secret_key",
            "token",
        }
    
    async def register_role(self, role: Role) -> bool:
        """注册角色"""
        async with self._lock:
            if role.role_id in self._roles:
                logger.warning(f"Role already exists: {role.role_id}")
                return False
            
            self._roles[role.role_id] = role
            logger.info(f"Role registered: {role.role_id}")
            return True
    
    async def get_role(self, role_id: str) -> Optional[Role]:
        """获取角色"""
        return self._roles.get(role_id)
    
    async def assign_role(self, user_id: str, role_id: str) -> bool:
        """分配角色给用户"""
        async with self._lock:
            if role_id not in self._roles:
                logger.error(f"Role not found: {role_id}")
                return False
            
            if user_id not in self._users:
                self._users[user_id] = User(
                    user_id=user_id,
                    username=user_id,
                    role_ids=set(),
                )
            
            self._users[user_id].role_ids.add(role_id)
            
            if user_id not in self._user_roles:
                self._user_roles[user_id] = set()
            self._user_roles[user_id].add(role_id)
            
            logger.info(f"Role {role_id} assigned to user {user_id}")
            return True
    
    async def revoke_role(self, user_id: str, role_id: str) -> bool:
        """撤销用户角色"""
        async with self._lock:
            if user_id not in self._users:
                return False
            
            if role_id in self._users[user_id].role_ids:
                self._users[user_id].role_ids.remove(role_id)
            
            if user_id in self._user_roles and role_id in self._user_roles[user_id]:
                self._user_roles[user_id].remove(role_id)
            
            return True
    
    async def get_user_roles(self, user_id: str) -> List[Role]:
        """获取用户角色"""
        if user_id not in self._users:
            return []
        
        roles = []
        for role_id in self._users[user_id].role_ids:
            role = self._roles.get(role_id)
            if role:
                roles.append(role)
        
        return roles
    
    def _check_config_permission(
        self,
        user_id: str,
        action: PermissionAction,
        config_key: str,
    ) -> bool:
        """检查配置权限"""
        role_ids = self._user_roles.get(user_id, set())
        
        if "admin" in role_ids:
            return True
        
        if action == PermissionAction.READ:
            required_perm = f"config:read"
        elif action == PermissionAction.WRITE:
            required_perm = f"config:write"
        elif action == PermissionAction.DELETE:
            required_perm = f"config:delete"
        else:
            return False
        
        for role_id in role_ids:
            role = self._roles.get(role_id)
            if role and role.has_permission("*"):
                return True
            
            if role and role.has_permission(required_perm):
                return True
            
            category = config_key.split(".")[0] if "." in config_key else config_key
            category_perm = f"{required_perm}:{category}"
            if role and role.has_permission(category_perm):
                return True
        
        return False
    
    def _is_sensitive_config(self, config_key: str) -> bool:
        """检查是否为敏感配置"""
        for sensitive in self._sensitive_configs:
            if sensitive in config_key.lower():
                return True
        return False
    
    async def check_permission(
        self,
        user_id: str,
        action: PermissionAction,
        resource: str,
        resource_type: str = "config",
    ) -> bool:
        """检查权限"""
        if resource_type == "config":
            return self._check_config_permission(user_id, action, resource)
        
        role_ids = self._user_roles.get(user_id, set())
        
        if "admin" in role_ids:
            return True
        
        required_perm = f"{resource_type}:{action.value}"
        
        for role_id in role_ids:
            role = self._roles.get(role_id)
            if role and role.has_permission("*"):
                return True
            
            if role and role.has_permission(required_perm):
                return True
        
        return False
    
    async def require_permission(
        self,
        user_id: str,
        action: PermissionAction,
        resource: str,
        resource_type: str = "config",
    ) -> bool:
        """要求权限（抛出异常如果没有权限）"""
        has_permission = await self.check_permission(user_id, action, resource, resource_type)
        
        if not has_permission:
            raise PermissionDeniedError(
                f"User {user_id} lacks permission to {action.value} {resource}"
            )
        
        return True
    
    async def log_access(
        self,
        user_id: str,
        action: str,
        resource: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """记录访问日志"""
        log = AccessLog(
            user_id=user_id,
            action=action,
            resource=resource,
            result=result,
            details=details or {},
        )
        
        self._access_logs.append(log)
        
        if len(self._access_logs) > self._max_log_size:
            self._access_logs = self._access_logs[-self._max_log_size:]
    
    async def get_access_logs(
        self,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        limit: int = 100,
    ) -> List[AccessLog]:
        """获取访问日志"""
        logs = self._access_logs
        
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        
        if resource:
            logs = [l for l in logs if resource in l.resource]
        
        return logs[-limit:]
    
    def mark_sensitive_config(self, config_key: str):
        """标记敏感配置"""
        self._sensitive_configs.add(config_key)
    
    def is_sensitive(self, config_key: str) -> bool:
        """检查是否为敏感配置"""
        return self._is_sensitive_config(config_key)
    
    def mask_sensitive_value(self, config_key: str, value: Any) -> Any:
        """屏蔽敏感值"""
        if not self._is_sensitive_config(config_key):
            return value
        
        if isinstance(value, str) and len(value) > 4:
            return "*" * (len(value) - 4) + value[-4:]
        return "****"
    
    async def get_user_permissions(self, user_id: str) -> Set[str]:
        """获取用户所有权限"""
        permissions = set()
        
        roles = await self.get_user_roles(user_id)
        for role in roles:
            permissions.update(role.permissions)
        
        return permissions


class PermissionDeniedError(Exception):
    """权限被拒绝"""
    pass


_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """获取权限管理器单例"""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager


class SecureConfigManager:
    """安全配置管理器
    
    集成权限控制的配置管理器
    """
    
    def __init__(self, config_manager, permission_manager: PermissionManager):
        self._config = config_manager
        self._permission = permission_manager
    
    async def get(
        self,
        key: str,
        user_id: str,
        default: Any = None,
    ) -> Any:
        """获取配置（带权限检查）"""
        has_permission = await self._permission.check_permission(
            user_id,
            PermissionAction.READ,
            key,
            "config",
        )
        
        if not has_permission:
            await self._permission.log_access(
                user_id, "read", key, "denied"
            )
            raise PermissionDeniedError(f"User {user_id} cannot read {key}")
        
        value = self._config.get(key, default)
        
        if self._permission.is_sensitive(key):
            value = self._permission.mask_sensitive_value(key, value)
        
        await self._permission.log_access(
            user_id, "read", key, "allowed"
        )
        
        return value
    
    async def set(
        self,
        key: str,
        value: Any,
        user_id: str,
        reason: Optional[str] = None,
    ):
        """设置配置（带权限检查）"""
        has_permission = await self._permission.check_permission(
            user_id,
            PermissionAction.WRITE,
            key,
            "config",
        )
        
        if not has_permission:
            await self._permission.log_access(
                user_id, "write", key, "denied"
            )
            raise PermissionDeniedError(f"User {user_id} cannot write {key}")
        
        self._config.set(key, value, changed_by=user_id, reason=reason)
        
        await self._permission.log_access(
            user_id, "write", key, "allowed",
            details={"value_type": type(value).__name__}
        )
    
    async def delete(
        self,
        key: str,
        user_id: str,
    ):
        """删除配置（带权限检查）"""
        has_permission = await self._permission.check_permission(
            user_id,
            PermissionAction.DELETE,
            key,
            "config",
        )
        
        if not has_permission:
            await self._permission.log_access(
                user_id, "delete", key, "denied"
            )
            raise PermissionDeniedError(f"User {user_id} cannot delete {key}")
        
        self._config.delete(key)
        
        await self._permission.log_access(
            user_id, "delete", key, "allowed"
        )
    
    def get_config_manager(self):
        """获取底层配置管理器"""
        return self._config
