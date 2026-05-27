"""
MarketContext Validators - 验证上下文数据完整性

核心职责：
1. 验证策略声明的 required_context 是否有效
2. 验证构建的 MarketContext 是否包含所有必需字段
3. 在缺失字段时提供清晰的错误信息
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import fields

from .schema import (
    MarketContext,
    TimeframeContext,
    STANDARD_TIMEFRAMES,
)
from .feature_map import validate_context_path


class ContextValidationError(Exception):
    """上下文验证错误"""
    pass


class MarketContextValidator:
    """
    验证 MarketContext 的完整性
    """
    
    def __init__(self):
        pass
    
    def validate_context_paths(self, paths: List[str]) -> Tuple[bool, List[str]]:
        """
        验证上下文路径列表是否有效
        
        Args:
            paths: 上下文路径列表
        
        Returns:
            (是否有效, 错误消息列表)
        """
        errors: List[str] = []
        
        for path in paths:
            if not validate_context_path(path):
                errors.append(f"无效的上下文路径: {path}")
        
        return (len(errors) == 0, errors)
    
    def validate_market_context(
        self,
        context: MarketContext,
        required_context: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        验证 MarketContext 是否包含所有必需的上下文
        
        Args:
            context: 要验证的 MarketContext
            required_context: 策略声明的必需上下文路径
        
        Returns:
            (是否有效, 错误消息列表)
        """
        errors: List[str] = []
        
        for path in required_context:
            if not self._check_path_exists(context, path):
                errors.append(f"缺失必需的上下文: {path}")
        
        return (len(errors) == 0, errors)
    
    def _check_path_exists(self, context: MarketContext, path: str) -> bool:
        """
        检查单个路径是否存在于 MarketContext 中
        
        Args:
            context: MarketContext
            path: 上下文路径
        
        Returns:
            是否存在
        """
        if path.startswith("tf."):
            parts = path.split(".")
            if len(parts) != 3:
                return False
            
            tf = parts[1]
            field_name = parts[2]
            
            # 检查时间周期是否存在
            if tf not in context.tf:
                return False
            
            tf_ctx = context.tf[tf]
            
            # 检查字段是否存在
            return hasattr(tf_ctx, field_name)
        
        elif path.startswith("derivatives."):
            parts = path.split(".")
            if len(parts) != 2:
                return False
            
            field_name = parts[1]
            return hasattr(context.derivatives, field_name)
        
        elif path == "cross_market":
            return context.cross_market is not None
        
        elif path == "risk":
            return context.risk is not None
        
        return False
    
    def validate_timeframe_completeness(self, context: MarketContext) -> Tuple[bool, List[str]]:
        """
        验证所有标准时间周期是否都存在
        
        Args:
            context: MarketContext
        
        Returns:
            (是否完整, 缺失的时间周期列表)
        """
        missing_tfs = [tf for tf in STANDARD_TIMEFRAMES if tf not in context.tf]
        return (len(missing_tfs) == 0, missing_tfs)
    
    def validate_field_values(self, context: MarketContext) -> List[str]:
        """
        验证字段值是否合理
        
        Args:
            context: MarketContext
        
        Returns:
            警告消息列表
        """
        warnings: List[str] = []
        
        # 检查价格是否合理
        for tf, tf_ctx in context.tf.items():
            if tf_ctx.price.close <= 0:
                warnings.append(f"{tf} 周期价格不合理: close={tf_ctx.price.close}")
            
            if tf_ctx.price.high < tf_ctx.price.low:
                warnings.append(f"{tf} 周期价格范围不合理: high={tf_ctx.price.high}, low={tf_ctx.price.low}")
        
        # 检查风险乘数
        if context.risk.multiplier <= 0:
            warnings.append(f"风险乘数不合理: {context.risk.multiplier}")
        
        return warnings


def validate_strategy_requirements(
    required_context: List[str],
    context: Optional[MarketContext] = None,
) -> Tuple[bool, List[str]]:
    """
    便捷函数：验证策略需求
    
    Args:
        required_context: 策略声明的必需上下文
        context: 可选的 MarketContext 实例
    
    Returns:
        (是否有效, 错误/警告消息列表)
    """
    validator = MarketContextValidator()
    messages: List[str] = []
    
    # 验证路径格式
    is_valid, errors = validator.validate_context_paths(required_context)
    if not is_valid:
        messages.extend(errors)
    
    # 如果提供了 context，验证完整性
    if context is not None:
        is_complete, missing = validator.validate_market_context(context, required_context)
        if not is_complete:
            messages.extend(missing)
        
        # 验证时间周期完整性
        is_tf_complete, missing_tfs = validator.validate_timeframe_completeness(context)
        if not is_tf_complete:
            messages.append(f"缺失时间周期: {', '.join(missing_tfs)}")
        
        # 验证字段值
        warnings = validator.validate_field_values(context)
        messages.extend(warnings)
    
    return (len(messages) == 0, messages)


__all__ = [
    "ContextValidationError",
    "MarketContextValidator",
    "validate_strategy_requirements",
]
