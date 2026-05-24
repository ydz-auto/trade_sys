"""
Runtime Time Authority - 统一时间系统（强制执法）

核心原则：
- Runtime 内部只允许 int64 ms 格式
- 所有进入 Runtime 的时间必须经过 normalize
- 严格的类型验证和单调检查

时间类型规范：
- int64 ms: Runtime 内部唯一格式 ✓
- str: 仅用于 API 输入/输出（必须转换）
- pd.Timestamp: 仅用于 pandas Adapter 层（必须转换）
- datetime: 禁止进入 Runtime

转换规则：
- str -> int64 ms (parse ISO format)
- pd.Timestamp -> int64 ms
- datetime -> int64 ms
- int (s) -> int64 ms (* 1000)
"""

from datetime import datetime, timezone
from typing import Union, Optional, Dict, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.time_authority")


class TimeSource(Enum):
    """时间来源"""
    WEBSOCKET = "websocket"
    PARQUET = "parquet"
    API = "api"
    CSV = "csv"
    DATAFRAME = "dataframe"
    JSON = "json"
    EXCHANGE = "exchange"


@dataclass
class TimeValidationResult:
    """时间验证结果"""
    is_valid: bool
    time_ms: int = 0
    issues: List[str] = field(default_factory=list)
    source: str = ""
    original_type: str = ""


class TimeAuthority:
    """
    时间权威机构 - 强制执行时间纪律
    
    核心能力：
    1. normalize_time - 将任意时间格式转换为 int64 ms
    2. validate_time - 验证时间有效性
    3. monotonic_check - 单调递增检查
    4. timezone_handling - 时区统一（UTC）
    5. session_time - 会话时间管理
    6. causal_time - 因果时间检查
    """
    
    # 合理的时间范围：1970-01-01 到 2050-01-01
    MIN_VALID_MS = 0  # 1970-01-01
    MAX_VALID_MS = 2524608000000  # 2050-01-01
    
    def __init__(self):
        self._last_timestamp_ms: int = 0
        self._strict_mode: bool = True
        self._source_tracking: Dict[str, int] = {}
    
    def set_strict_mode(self, strict: bool = True):
        """设置严格模式（严格模式下无效时间会抛出异常）"""
        self._strict_mode = strict
    
    def normalize_time_ms(
        self,
        time_value: Union[str, int, float, datetime, pd.Timestamp, np.datetime64],
        source: Union[TimeSource, str] = "unknown",
        field_name: str = "time_value"
    ) -> int:
        """
        将任意时间格式转换为 int64 ms
        
        Args:
            time_value: 输入时间，可以是：
                - str: ISO 格式如 "2024-01-01", "2024-01-01 12:00:00"
                - int: 毫秒时间戳或秒时间戳（自动检测）
                - float: 秒时间戳
                - datetime: 时区感知或本地时间
                - pd.Timestamp: pandas 时间戳
                - np.datetime64: numpy 时间戳
            source: 时间来源（用于追踪）
            field_name: 字段名称（用于错误消息）
        
        Returns:
            int: 毫秒时间戳
        
        Raises:
            ValueError: 如果无法解析时间格式或验证失败
        """
        original_type = type(time_value).__name__
        source_str = source.value if isinstance(source, TimeSource) else source
        
        if time_value is None:
            raise ValueError(f"{field_name} cannot be None (source: {source_str})")
        
        # 处理 int 类型
        if isinstance(time_value, int):
            return self._handle_int(time_value, field_name, source_str)
        
        # 处理 np.int64 / np.int32
        if isinstance(time_value, (np.int64, np.int32, np.int_)):
            return self._handle_int(int(time_value), field_name, source_str)
        
        # 处理 float 类型（通常是秒）
        if isinstance(time_value, float):
            return self._handle_float(time_value, field_name, source_str)
        
        # 处理 np.float64
        if isinstance(time_value, (np.float64, np.float_)):
            return self._handle_float(float(time_value), field_name, source_str)
        
        # 处理 pd.Timestamp
        if isinstance(time_value, pd.Timestamp):
            return self._handle_pd_timestamp(time_value, field_name, source_str)
        
        # 处理 np.datetime64
        if isinstance(time_value, np.datetime64):
            return self._handle_np_datetime64(time_value, field_name, source_str)
        
        # 处理 datetime
        if isinstance(time_value, datetime):
            return self._handle_datetime(time_value, field_name, source_str)
        
        # 处理字符串
        if isinstance(time_value, str):
            return self._handle_string(time_value.strip(), field_name, source_str)
        
        raise ValueError(
            f"Unsupported time type '{original_type}' for {field_name} (source: {source_str})"
        )
    
    def _handle_int(self, value: int, field_name: str, source: str) -> int:
        """处理整数类型时间戳"""
        if value < 10**12:  # 秒时间戳
            result = value * 1000
            logger.debug(f"Converted seconds to ms: {value} -> {result} (source: {source})")
        else:  # 毫秒时间戳
            result = value
        
        self._validate_range(result, field_name, source)
        return result
    
    def _handle_float(self, value: float, field_name: str, source: str) -> int:
        """处理浮点数类型时间戳（通常是秒）"""
        result = int(value * 1000)
        self._validate_range(result, field_name, source)
        return result
    
    def _handle_pd_timestamp(self, value: pd.Timestamp, field_name: str, source: str) -> int:
        """处理 pandas Timestamp"""
        result = int(value.timestamp() * 1000)
        logger.debug(f"Converted pd.Timestamp to ms: {value} -> {result} (source: {source})")
        self._validate_range(result, field_name, source)
        return result
    
    def _handle_np_datetime64(self, value: np.datetime64, field_name: str, source: str) -> int:
        """处理 numpy datetime64"""
        # 转换为 pandas Timestamp 再处理
        ts = pd.Timestamp(value)
        return self._handle_pd_timestamp(ts, field_name, source)
    
    def _handle_datetime(self, value: datetime, field_name: str, source: str) -> int:
        """处理 datetime"""
        if value.tzinfo is None:
            # 假设本地时间转换为 UTC
            result = int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)
            logger.warning(
                f"Converting naive datetime to UTC: {value} -> {result} (source: {source})"
            )
        else:
            result = int(value.timestamp() * 1000)
        
        self._validate_range(result, field_name, source)
        return result
    
    def _handle_string(self, value: str, field_name: str, source: str) -> int:
        """处理字符串时间"""
        # 尝试解析 ISO 格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                result = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                logger.debug(f"Parsed string '{value}' -> {result} (source: {source})")
                self._validate_range(result, field_name, source)
                return result
            except ValueError:
                continue
        
        # 尝试解析为数字字符串
        try:
            num_value = float(value)
            return self._handle_float(num_value, field_name, source)
        except ValueError:
            pass
        
        raise ValueError(f"Cannot parse time string '{value}' for {field_name} (source: {source})")
    
    def _validate_range(self, time_ms: int, field_name: str, source: str):
        """验证时间范围"""
        if not (self.MIN_VALID_MS < time_ms < self.MAX_VALID_MS):
            raise ValueError(
                f"{field_name} out of valid range: {time_ms} (source: {source}). "
                f"Valid range: {self.MIN_VALID_MS} - {self.MAX_VALID_MS}"
            )
    
    def validate_time_ms(self, time_ms: int) -> TimeValidationResult:
        """
        验证毫秒时间戳是否有效
        
        Returns:
            TimeValidationResult: 验证结果
        """
        issues = []
        
        if not isinstance(time_ms, int):
            issues.append(f"Expected int, got {type(time_ms).__name__}")
            return TimeValidationResult(is_valid=False, issues=issues)
        
        if time_ms <= self.MIN_VALID_MS:
            issues.append(f"Time {time_ms} is before epoch")
        
        if time_ms >= self.MAX_VALID_MS:
            issues.append(f"Time {time_ms} is after 2050")
        
        return TimeValidationResult(
            is_valid=len(issues) == 0,
            time_ms=time_ms,
            issues=issues
        )
    
    def ensure_time_ms(
        self,
        time_value: Union[str, int, float, datetime, pd.Timestamp],
        source: Union[TimeSource, str] = "unknown",
        field_name: str = "time_value"
    ) -> int:
        """
        确保时间值是 int64 ms 格式，如果不是则转换
        
        Args:
            time_value: 输入时间
            source: 时间来源
            field_name: 参数名称（用于错误消息）
        
        Returns:
            int: 毫秒时间戳
        
        Raises:
            ValueError: 如果无法解析或验证失败
        """
        try:
            time_ms = self.normalize_time_ms(time_value, source, field_name)
        except ValueError as e:
            raise ValueError(f"Invalid {field_name}: {e}")
        
        validation = self.validate_time_ms(time_ms)
        if not validation.is_valid:
            raise ValueError(f"{field_name} validation failed: {', '.join(validation.issues)}")
        
        return time_ms
    
    def check_monotonic(self, timestamp_ms: int) -> bool:
        """
        检查时间是否单调递增
        
        Args:
            timestamp_ms: 当前时间戳
        
        Returns:
            bool: 是否单调递增
        
        Side effect: 更新内部记录的最后时间戳
        """
        if timestamp_ms < self._last_timestamp_ms:
            logger.warning(
                f"Non-monotonic timestamp detected: {timestamp_ms} < {self._last_timestamp_ms}"
            )
            if self._strict_mode:
                raise ValueError(
                    f"Non-monotonic timestamp: {timestamp_ms} < {self._last_timestamp_ms}"
                )
            return False
        
        self._last_timestamp_ms = timestamp_ms
        return True
    
    def reset_monotonic(self):
        """重置单调检查状态"""
        self._last_timestamp_ms = 0
    
    def get_last_timestamp_ms(self) -> int:
        """获取最后记录的时间戳"""
        return self._last_timestamp_ms
    
    # === 便捷转换方法 ===
    
    def to_datetime(self, time_ms: int) -> datetime:
        """将毫秒时间戳转换为 datetime (UTC)"""
        return datetime.fromtimestamp(time_ms / 1000, timezone.utc)
    
    def to_pd_timestamp(self, time_ms: int) -> pd.Timestamp:
        """将毫秒时间戳转换为 pd.Timestamp"""
        return pd.Timestamp(time_ms, unit='ms', tz='UTC')
    
    def format_time_ms(self, time_ms: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """格式化毫秒时间戳为字符串"""
        return self.to_datetime(time_ms).strftime(fmt)
    
    # === 时区处理 ===
    
    def ensure_utc(self, time_ms: int) -> int:
        """确保时间是 UTC（毫秒时间戳本身就是 UTC）"""
        return time_ms
    
    # === 会话时间管理 ===
    
    def start_session(self, start_time_ms: int):
        """开始新会话"""
        self.reset_monotonic()
        self._last_timestamp_ms = start_time_ms
        logger.info(f"Time session started at {start_time_ms}")
    
    def end_session(self):
        """结束会话"""
        logger.info(f"Time session ended. Last timestamp: {self._last_timestamp_ms}")


# 全局时间权威实例
_time_authority_instance: Optional[TimeAuthority] = None


def get_time_authority() -> TimeAuthority:
    """获取全局时间权威实例"""
    global _time_authority_instance
    if _time_authority_instance is None:
        _time_authority_instance = TimeAuthority()
    return _time_authority_instance


# === 便捷函数 ===

def normalize_time_ms(
    time_value: Union[str, int, float, datetime, pd.Timestamp],
    source: Union[TimeSource, str] = "unknown",
    field_name: str = "time_value"
) -> int:
    """便捷函数：归一化时间到毫秒"""
    return get_time_authority().normalize_time_ms(time_value, source, field_name)


def ensure_time_ms(
    time_value: Union[str, int, float, datetime, pd.Timestamp],
    source: Union[TimeSource, str] = "unknown",
    field_name: str = "time_value"
) -> int:
    """便捷函数：确保时间是毫秒格式"""
    return get_time_authority().ensure_time_ms(time_value, source, field_name)


def validate_time_ms(time_ms: int) -> TimeValidationResult:
    """便捷函数：验证时间"""
    return get_time_authority().validate_time_ms(time_ms)


def check_monotonic(timestamp_ms: int) -> bool:
    """便捷函数：检查单调递增"""
    return get_time_authority().check_monotonic(timestamp_ms)


def to_datetime(time_ms: int) -> datetime:
    """便捷函数：转换为 datetime"""
    return get_time_authority().to_datetime(time_ms)


def to_pd_timestamp(time_ms: int) -> pd.Timestamp:
    """便捷函数：转换为 pd.Timestamp"""
    return get_time_authority().to_pd_timestamp(time_ms)


def format_time_ms(time_ms: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """便捷函数：格式化时间"""
    return get_time_authority().format_time_ms(time_ms, fmt)