"""
Context Leakage Guard - 防止未来信息泄漏

核心职责：
1. 验证 feature 输出是否包含 _meta
2. 验证 as_of 是否 <= ctx_timestamp
3. 验证 bar 是否已关闭（close_only 模式）
4. 检测禁止的未来信息字段名

使用场景：
- backtest/replay: close_only 模式
- live: partial_allowed 模式
"""

from typing import Dict, Any, List
from dataclasses import dataclass


class FutureLeakageError(Exception):
    """未来信息泄漏异常"""
    pass


FORBIDDEN_PATTERNS: List[str] = [
    "future",
    "next_",
    "forward",
    "target",
    "label",
    "return_fwd",
    "lead_",
]


class LeakageGuardMode:
    """泄漏防护模式"""
    CLOSE_ONLY = "close_only"
    PARTIAL_ALLOWED = "partial_allowed"


@dataclass
class FeatureMeta:
    """Feature 元数据"""
    tf: str
    as_of: int
    bar_start: int
    bar_end: int
    is_closed: bool
    source: str = "unknown"


class ContextLeakageGuard:
    """
    未来信息泄漏防护器
    
    规则：
    1. 所有 feature 输出必须包含 _meta
    2. as_of 必须 <= ctx_timestamp
    3. close_only 模式下 bar 必须已关闭
    4. 禁止使用未来信息字段名
    """
    
    def __init__(self, mode: str = LeakageGuardMode.CLOSE_ONLY):
        self.mode = mode
    
    def validate(
        self,
        features_by_tf: Dict[str, Dict[str, Any]],
        ctx_timestamp: int,
    ) -> None:
        """
        验证 features_by_tf 是否存在未来信息泄漏
        
        Args:
            features_by_tf: 按时间周期分组的 features
            ctx_timestamp: 上下文时间戳（毫秒）
        
        Raises:
            FutureLeakageError: 如果检测到未来信息泄漏
        """
        for tf, features in features_by_tf.items():
            self._validate_timeframe(features, tf, ctx_timestamp)
    
    def _validate_timeframe(
        self,
        features: Dict[str, Any],
        tf: str,
        ctx_timestamp: int,
    ) -> None:
        """验证单个时间周期的 features"""
        meta = features.get("_meta")
        
        if meta is None:
            raise FutureLeakageError(f"{tf} missing _meta")
        
        self._validate_meta(meta, tf, ctx_timestamp)
        self._validate_field_names(features, tf)
    
    def _validate_meta(
        self,
        meta: Dict[str, Any],
        tf: str,
        ctx_timestamp: int,
    ) -> None:
        """验证 _meta 内容"""
        as_of = meta.get("as_of")
        if as_of is None:
            raise FutureLeakageError(f"{tf} _meta missing as_of")
        
        if as_of > ctx_timestamp:
            raise FutureLeakageError(
                f"{tf} as_of ({as_of}) > ctx_timestamp ({ctx_timestamp})"
            )
        
        if self.mode == LeakageGuardMode.CLOSE_ONLY:
            bar_end = meta.get("bar_end")
            is_closed = meta.get("is_closed", False)
            
            if bar_end is not None and bar_end > ctx_timestamp:
                raise FutureLeakageError(
                    f"{tf} bar_end ({bar_end}) > ctx_timestamp ({ctx_timestamp})"
                )
            
            if not is_closed:
                raise FutureLeakageError(f"{tf} bar is not closed")
    
    def _validate_field_names(
        self,
        features: Dict[str, Any],
        tf: str,
    ) -> None:
        """验证字段名是否包含禁止的未来信息模式"""
        for key in features.keys():
            if key.startswith("_"):
                continue
            
            lower_key = key.lower()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in lower_key:
                    raise FutureLeakageError(
                        f"{tf} forbidden future-like field: {key}"
                    )


def create_guard(mode: str = LeakageGuardMode.CLOSE_ONLY) -> ContextLeakageGuard:
    """创建泄漏防护器的便捷函数"""
    return ContextLeakageGuard(mode=mode)


__all__ = [
    "FutureLeakageError",
    "FORBIDDEN_PATTERNS",
    "LeakageGuardMode",
    "FeatureMeta",
    "ContextLeakageGuard",
    "create_guard",
]
