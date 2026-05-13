"""
Permission Manager Verification Script
验证权限管理功能
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.permission import (
    PermissionManager,
    PermissionAction,
    PermissionScope,
    SecureConfigManager,
    PermissionDeniedError,
    get_permission_manager,
    Role,
)
from shared.config import get_config_manager


async def verify_permission_manager():
    """验证权限管理器"""
    print("=" * 60)
    print("Permission Manager Verification")
    print("=" * 60)
    
    permission = get_permission_manager()
    
    print("\n[1] Testing default roles...")
    roles = list(permission._roles.keys())
    print(f"    Available roles: {roles}")
    
    print("\n[2] Testing role assignment...")
    await permission.assign_role("user_001", "operator")
    user_roles = await permission.get_user_roles("user_001")
    print(f"    User roles: {[r.name for r in user_roles]}")
    
    print("\n[3] Testing permission check...")
    can_read = await permission.check_permission(
        "user_001",
        PermissionAction.READ,
        "datasource.symbols",
        "config"
    )
    print(f"    Can read datasource.symbols: {can_read}")
    
    can_write = await permission.check_permission(
        "user_001",
        PermissionAction.WRITE,
        "api_key",
        "config"
    )
    print(f"    Can write api_key: {can_write}")
    
    print("\n[4] Testing sensitive config detection...")
    is_sensitive = permission.is_sensitive("binance.api_key")
    print(f"    Is 'binance.api_key' sensitive: {is_sensitive}")
    
    print("\n[5] Testing sensitive value masking...")
    masked = permission.mask_sensitive_value("api_key", "super_secret_key_12345")
    print(f"    Masked value: {masked}")
    
    print("\n[6] Testing admin access...")
    await permission.assign_role("admin_user", "admin")
    can_do_anything = await permission.check_permission(
        "admin_user",
        PermissionAction.WRITE,
        "anything.here",
        "config"
    )
    print(f"    Admin can write anything: {can_do_anything}")
    
    print("\n[7] Testing access logging...")
    await permission.log_access("user_001", "read", "test.config", "allowed")
    await permission.log_access("user_001", "write", "test.config", "denied")
    logs = await permission.get_access_logs("user_001")
    print(f"    Access logs for user_001: {len(logs)} entries")
    for log in logs[-2:]:
        print(f"      - {log.action} {log.resource}: {log.result}")
    
    print("\n" + "=" * 60)
    print("✅ Permission Manager Verification Complete!")
    print("=" * 60)
    
    return True


async def verify_secure_config_manager():
    """验证安全配置管理器"""
    print("\n[Secure Config Manager Verification]")
    
    config_manager = get_config_manager()
    permission = get_permission_manager()
    
    secure_config = SecureConfigManager(config_manager, permission)
    
    print("\n  Testing secure get...")
    try:
        await permission.assign_role("test_user", "viewer")
        value = await secure_config.get("test_key", "test_user", "default")
        print(f"    Got value: {value}")
    except PermissionDeniedError as e:
        print(f"    Permission denied: {e}")
    
    print("  ✅ Secure Config Manager verified!")
    return True


async def main():
    """主函数"""
    try:
        await verify_permission_manager()
        await verify_secure_config_manager()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
