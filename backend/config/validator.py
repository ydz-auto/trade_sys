"""
Config Validator - 配置验证器

验证配置的正确性和一致性。
"""

from typing import Any, Dict, List, Optional, Set
from pydantic import ValidationError


class ConfigValidator:
    """
    配置验证器
    
    职责：
    - 验证配置格式
    - 验证配置值范围
    - 验证配置依赖关系
    """
    
    VALID_ENVIRONMENTS: Set[str] = {"dev", "prod", "staging", "replay"}
    VALID_LOG_LEVELS: Set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    
    def validate_environment(self, env: str) -> bool:
        """验证环境名称"""
        return env in self.VALID_ENVIRONMENTS
    
    def validate_log_level(self, level: str) -> bool:
        """验证日志级别"""
        return level.upper() in self.VALID_LOG_LEVELS
    
    def validate_kafka_servers(self, servers: str) -> bool:
        """验证 Kafka 服务器地址"""
        if not servers:
            return False
        
        for server in servers.split(","):
            parts = server.strip().split(":")
            if len(parts) != 2:
                return False
            try:
                int(parts[1])
            except ValueError:
                return False
        
        return True
    
    def validate_redis_url(self, url: str) -> bool:
        """验证 Redis URL"""
        return url.startswith("redis://")
    
    def validate_clickhouse_config(self, config: Dict[str, Any]) -> List[str]:
        """验证 ClickHouse 配置"""
        errors = []
        
        if not config.get("host"):
            errors.append("ClickHouse host is required")
        
        port = config.get("port", 9000)
        if not (1 <= port <= 65535):
            errors.append(f"Invalid ClickHouse port: {port}")
        
        return errors
    
    def validate_postgres_config(self, config: Dict[str, Any]) -> List[str]:
        """验证 PostgreSQL 配置"""
        errors = []
        
        if not config.get("host"):
            errors.append("PostgreSQL host is required")
        
        if not config.get("database"):
            errors.append("PostgreSQL database is required")
        
        if not config.get("user"):
            errors.append("PostgreSQL user is required")
        
        return errors
    
    def validate_runtime_config(self, config: Dict[str, Any]) -> List[str]:
        """验证 Runtime 配置"""
        errors = []
        
        if not config.get("name"):
            errors.append("Runtime name is required")
        
        shutdown_timeout = config.get("shutdown_timeout", 30)
        if shutdown_timeout < 0:
            errors.append(f"Invalid shutdown_timeout: {shutdown_timeout}")
        
        health_check_interval = config.get("health_check_interval", 10)
        if health_check_interval < 0:
            errors.append(f"Invalid health_check_interval: {health_check_interval}")
        
        return errors
    
    def validate_feature_flags(self, flags: Dict[str, Any]) -> List[str]:
        """验证功能开关"""
        errors = []
        
        boolean_flags = [
            "enable_llm",
            "enable_replay",
            "enable_projection",
            "enable_shadow_execution",
            "enable_narrative",
        ]
        
        for flag in boolean_flags:
            if flag in flags and not isinstance(flags[flag], bool):
                errors.append(f"Feature flag {flag} must be boolean")
        
        return errors
    
    def validate_all(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """验证所有配置"""
        results = {}
        
        if "environment" in config:
            if not self.validate_environment(config["environment"]):
                results["environment"] = [f"Invalid environment: {config['environment']}"]
        
        if "log_level" in config:
            if not self.validate_log_level(config["log_level"]):
                results["log_level"] = [f"Invalid log_level: {config['log_level']}"]
        
        if "kafka" in config:
            if "bootstrap_servers" in config["kafka"]:
                if not self.validate_kafka_servers(config["kafka"]["bootstrap_servers"]):
                    results["kafka"] = ["Invalid Kafka bootstrap_servers"]
        
        if "redis" in config:
            if "url" in config["redis"]:
                if not self.validate_redis_url(config["redis"]["url"]):
                    results["redis"] = ["Invalid Redis URL"]
        
        if "clickhouse" in config:
            errors = self.validate_clickhouse_config(config["clickhouse"])
            if errors:
                results["clickhouse"] = errors
        
        if "postgresql" in config:
            errors = self.validate_postgres_config(config["postgresql"])
            if errors:
                results["postgresql"] = errors
        
        if "features" in config:
            errors = self.validate_feature_flags(config["features"])
            if errors:
                results["features"] = errors
        
        return results
