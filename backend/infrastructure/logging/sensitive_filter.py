"""
日志敏感数据过滤器
防止 API Key、密码等敏感信息被记录到日志中
"""

import re
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.logging.sensitive_filter")


@dataclass
class SensitivePattern:
    """敏感数据模式"""
    name: str
    pattern: str
    mask: str = "[REDACTED]"


class SensitiveDataFilter:
    """敏感数据过滤器"""
    
    # 预定义的敏感字段模式
    SENSITIVE_FIELDS = [
        # API Key 相关
        SensitivePattern("api_key", r'(api_key|apikey|api_key|apiKey)', "[REDACTED_API_KEY]"),
        SensitivePattern("api_secret", r'(api_secret|apisecret|apiSecret)', "[REDACTED_API_SECRET]"),
        SensitivePattern("secret", r'(secret|secret_key|secretKey)', "[REDACTED_SECRET]"),
        # 密码相关
        SensitivePattern("password", r'(password|passwd|pwd)', "[REDACTED_PASSWORD]"),
        SensitivePattern("auth", r'(auth_token|authorization|authToken)', "[REDACTED_AUTH]"),
        # JWT 和 Token
        SensitivePattern("token", r'(token|jwt|access_token|accessToken)', "[REDACTED_TOKEN]"),
        # 密钥相关
        SensitivePattern("private_key", r'(private_key|privateKey|pk)', "[REDACTED_PRIVATE_KEY]"),
        SensitivePattern("public_key", r'(public_key|publicKey)', "[REDACTED_PUBLIC_KEY]"),
        # 钱包相关
        SensitivePattern("wallet", r'(mnemonic|seed_phrase|seedPhrase|wallet_key)', "[REDACTED_WALLET]"),
    ]
    
    # 敏感值特征模式（字符串中可能包含的敏感模式）
    SENSITIVE_VALUE_PATTERNS = [
        # API Key 格式（如: sk-...）
        r'sk-[a-zA-Z0-9-]{32,}',
        r'pk-[a-zA-Z0-9-]{32,}',
        # Binance API Key 格式
        r'[a-zA-Z0-9]{64}',
        r'[a-zA-Z0-9-]{36,}',
        # JWT Token
        r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
    ]
    
    def __init__(self):
        self._field_patterns = [
            (sp, re.compile(sp.pattern, re.IGNORECASE))
            for sp in self.SENSITIVE_FIELDS
        ]
        self._value_patterns = [
            re.compile(pattern) for pattern in self.SENSITIVE_VALUE_PATTERNS
        ]
    
    def filter_string(self, text: str) -> str:
        """过滤字符串中的敏感数据"""
        if not text or not isinstance(text, str):
            return text
            
        result = text
        
        # 检查是否是敏感值
        for pattern in self._value_patterns:
            if pattern.search(text):
                # 可能是敏感值，整体替换
                return "[REDACTED_SENSITIVE_VALUE]"
        
        # 检查是否包含敏感字段名
        for sp, pattern in self._field_patterns:
            if pattern.search(text):
                # 包含敏感字段名，需要更仔细检查
                # 简单处理：直接标记为可能敏感
                pass
                
        return result
    
    def filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """递归过滤字典中的敏感数据"""
        if not data or not isinstance(data, dict):
            return data
            
        result = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # 检查 key 是否是敏感字段
            is_sensitive_field = False
            for sp, pattern in self._field_patterns:
                if pattern.search(key):
                    is_sensitive_field = True
                    result[key] = sp.mask
                    break
            
            if not is_sensitive_field:
                # 检查 value 类型
                if isinstance(value, dict):
                    result[key] = self.filter_dict(value)
                elif isinstance(value, list):
                    result[key] = self.filter_list(value)
                elif isinstance(value, str):
                    result[key] = self.filter_string(value)
                else:
                    result[key] = value
        
        return result
    
    def filter_list(self, data: list) -> list:
        """递归过滤列表中的敏感数据"""
        if not data or not isinstance(data, list):
            return data
            
        return [
            self.filter_dict(item) if isinstance(item, dict)
            else self.filter_list(item) if isinstance(item, list)
            else self.filter_string(item) if isinstance(item, str)
            else item
            for item in data
        ]
    
    def filter(self, data: Any) -> Any:
        """过滤任意数据类型中的敏感信息"""
        if isinstance(data, dict):
            return self.filter_dict(data)
        elif isinstance(data, list):
            return self.filter_list(data)
        elif isinstance(data, str):
            return self.filter_string(data)
        return data


# 全局过滤器实例
_sensitive_filter = SensitiveDataFilter()


def get_sensitive_filter() -> SensitiveDataFilter:
    """获取敏感数据过滤器"""
    return _sensitive_filter


def safe_log(data: Any) -> Any:
    """安全记录数据 - 自动过滤敏感信息"""
    return _sensitive_filter.filter(data)


def mask_sensitive_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """过滤字典中的敏感数据（便捷函数）"""
    return _sensitive_filter.filter_dict(data)


def mask_sensitive_value(key: str, value: Any) -> Any:
    """根据 key 决定是否屏蔽 value"""
    key_lower = key.lower()
    
    for sp, pattern in _sensitive_filter._field_patterns:
        if pattern.search(key_lower):
            return sp.mask
            
    if isinstance(value, str):
        return _sensitive_filter.filter_string(value)
        
    return value
