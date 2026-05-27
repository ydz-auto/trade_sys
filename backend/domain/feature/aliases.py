"""
Feature Aliases - 特征别名兼容 (Domain 层)

核心原则：
- 旧名字 -> 新名字的映射
- 所有入口都要通过 normalize_feature_name 归一化
- 新代码直接使用 FEATURE_REGISTRY 里的正式名称
"""

from typing import Dict


# ========== 别名映射表 ==========
# 规则：旧名字 -> 新名字（FEATURE_REGISTRY 里的正式名称）
FEATURE_ALIASES: Dict[str, str] = {
    # RSI 别名
    "rsi": "rsi_14",
    
    # 持仓量别名
    "open_interest": "oi",
    
    # 主动买卖别名
    "aggressive_buy": "aggressive_buy_volume",
    "aggressive_sell": "aggressive_sell_volume",
    
    # 点差别名
    "spread": "spread_bps",
    
    # 流动性真空别名
    "liquidity_vacuum": "is_vacuum",
}


def normalize_feature_name(name: str) -> str:
    """
    归一化特征名称
    
    处理流程：
    1. 转换为小写
    2. 去除首尾空格
    3. 应用别名映射
    4. 返回归一化后的名称
    
    Args:
        name: 原始特征名称
        
    Returns:
        归一化后的特征名称（总是 FEATURE_REGISTRY 里的正式名称）
    """
    normalized = name.strip().lower()
    return FEATURE_ALIASES.get(normalized, normalized)


def get_original_names(canonical_name: str) -> list[str]:
    """
    获取某个正式名称的所有原始别名
    
    Args:
        canonical_name: FEATURE_REGISTRY 里的正式名称
        
    Returns:
        所有指向这个正式名称的原始别名列表
    """
    return [
        alias for alias, canonical in FEATURE_ALIASES.items()
        if canonical == canonical_name
    ]
