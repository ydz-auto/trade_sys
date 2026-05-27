"""
Feature Mapping - 原料到上下文的映射

将底层 feature 映射到 MarketContext 的结构化字段。

设计原则：
1. required_features 从策略层移到这里
2. 每个上下文字段明确声明需要哪些原料
3. 支持通配符 * 表示所有时间周期
4. 所有特征必须在 FEATURE_REGISTRY 中注册
"""

from typing import Dict, List
import sys
from pathlib import Path

# 添加 backend 到路径以支持绝对导入
backend_path = Path(__file__).resolve().parents[3]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    from backend.domain.feature.registry import FEATURE_REGISTRY, is_feature_registered
    from backend.domain.feature.aliases import normalize_feature_name
except ImportError:
    from domain.feature.registry import FEATURE_REGISTRY, is_feature_registered
    from domain.feature.aliases import normalize_feature_name


# ========== 上下文特征映射表 ==========
# 规则：context_path -> [feature_names]
# 注意：所有 feature_names 必须是 FEATURE_REGISTRY 里的正式名称
CONTEXT_FEATURE_MAP: Dict[str, List[str]] = {
    # ========== 时间周期特征 ==========
    
    # 价格
    "tf.*.price": [
        "open", "high", "low", "close",
        "return_1h", "return_24h",
        "change", "change_percent",
        "closes", "highs", "lows",
        "support", "resistance",
    ],
    
    # 趋势
    "tf.*.trend": [
        "ema_20", "ema_50", "slope", "structure", "strength",
    ],
    
    # 动量
    "tf.*.momentum": [
        "rsi_14", "macd", "macd_signal", "momentum_score",
    ],
    
    # 波动率
    "tf.*.volatility": [
        "atr", "atr_pct", "bb_width", "bb_width_pct",
        "realized_vol", "realized_vol_zscore",
    ],
    
    # 成交量
    "tf.*.volume": [
        "volume", "volume_ma", "volume_zscore", "volume_ratio",
    ],
    
    # 资金流
    "tf.*.flow": [
        "cvd", "cvd_slope", "cumulative_delta",
        "aggressive_buy_volume", "aggressive_sell_volume", "aggressive_ratio",
        "whale_buy_count", "whale_sell_count",
        "whale_buy_volume", "whale_sell_volume",
        "imbalance_5",
    ],
    
    # 流动性
    "tf.*.liquidity": [
        "spread_bps",
        "depth_ratio", "top5_bid_depth", "top5_ask_depth",
        "microprice",
        "is_vacuum", "vacuum_score",
        "cancel_rate",
    ],
    
    # ========== 跨周期特征 ==========
    
    # 持仓量
    "derivatives.oi": [
        "oi", "oi_delta", "oi_zscore", "oi_history",
    ],
    
    # 资金费率
    "derivatives.funding": [
        "funding_rate", "funding_zscore", "funding_history",
    ],
    
    # 强平
    "derivatives.liquidation": [
        "liquidation_long", "liquidation_short", "liquidation_total",
        "liquidation_long_zscore", "liquidation_short_zscore",
        "liquidation_reversal_signal",
    ],
    
    # 跨市场
    "cross_market": [
        "binance_return", "okx_return", "bybit_return",
        "basis", "premium",
        "lead_exchange", "lag_exchange", "lead_lag_score",
    ],
    
    # 风险
    "risk": [
        "high_volatility", "low_liquidity", "news_event",
        "overtrading", "drawdown_exceeded", "slippage_warning",
        "execution_paused", "regime_change", "extreme_move",
        "risk_multiplier",
    ],
}


def _validate_feature_map() -> None:
    """
    校验 CONTEXT_FEATURE_MAP 中的所有特征都在 FEATURE_REGISTRY 中注册
    
    会在模块导入时自动执行一次
    """
    unregistered_features = set()
    
    for context_path, feature_list in CONTEXT_FEATURE_MAP.items():
        for feature_name in feature_list:
            normalized = normalize_feature_name(feature_name)
            if not is_feature_registered(normalized):
                unregistered_features.add((context_path, feature_name))
    
    if unregistered_features:
        error_msg = "CONTEXT_FEATURE_MAP 包含未注册的特征:\n"
        for context_path, feature_name in sorted(unregistered_features):
            error_msg += f"  - {context_path}: '{feature_name}'\n"
        raise ValueError(error_msg)


# 导入时自动校验
_validate_feature_map()


def get_required_features(context_paths: List[str]) -> List[str]:
    """
    根据策略声明的 required_context 获取所需的原料特征列表
    
    Args:
        context_paths: 策略声明的上下文路径，如 ["tf.15m.price", "derivatives.oi"]
        
    Returns:
        所需的原料特征列表（归一化后的正式名称）
    """
    features: List[str] = []
    
    for path in context_paths:
        # 处理带具体时间周期的路径，如 "tf.15m.price"
        if path.startswith("tf."):
            # 提取模式 "tf.*.xxx"
            parts = path.split(".")
            if len(parts) >= 3:
                pattern = f"tf.*.{parts[2]}"
                if pattern in CONTEXT_FEATURE_MAP:
                    features.extend(CONTEXT_FEATURE_MAP[pattern])
        # 处理跨周期路径
        elif path in CONTEXT_FEATURE_MAP:
            features.extend(CONTEXT_FEATURE_MAP[path])
    
    # 归一化并去重，保持顺序
    seen = set()
    result = []
    for f in features:
        normalized = normalize_feature_name(f)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    
    return result


def validate_context_path(path: str) -> bool:
    """
    验证上下文路径是否有效
    
    Args:
        path: 上下文路径
        
    Returns:
        是否有效
    """
    # 检查时间周期路径
    if path.startswith("tf."):
        parts = path.split(".")
        if len(parts) != 3:
            return False
        
        tf = parts[1]
        field = parts[2]
        
        valid_tfs = ["1m", "5m", "15m", "1h", "4h"]
        valid_fields = ["price", "trend", "momentum", "volatility", "volume", "flow", "liquidity"]
        
        return tf in valid_tfs and field in valid_fields
    
    # 检查跨周期路径
    valid_cross_paths = [
        "derivatives.oi",
        "derivatives.funding",
        "derivatives.liquidation",
        "cross_market",
        "risk",
    ]
    
    return path in valid_cross_paths


__all__ = [
    "CONTEXT_FEATURE_MAP",
    "get_required_features",
    "validate_context_path",
]
