"""
Bollinger Compression Breakout Strategy Calculator - 布林带压缩突破策略无状态计算模块

纯函数计算，不管理任何状态。
状态由 runtime 层提供和管理。
"""
from typing import Optional, Dict, Any, Tuple


def calculate_bb_compression_signal(
    bb_upper: float,
    bb_lower: float,
    bb_middle: float,
    close: float,
    prev_above_middle: Optional[bool] = None,
    compression_threshold: float = 0.02,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    无状态计算布林带压缩突破策略信号
    
    Args:
        bb_upper: 布林带上轨
        bb_lower: 布林带下轨
        bb_middle: 布林带中轨
        close: 当前收盘价
        prev_above_middle: 前一时刻价格是否在中轨之上（状态由外部提供）
        compression_threshold: 压缩阈值
        params: 其他参数字典
    
    Returns:
        (signal_dict, new_state_data): 信号字典和新状态数据
    """
    params = params or {}
    compression_threshold = params.get('compression_threshold', compression_threshold)
    
    bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle != 0 else 1.0
    currently_above_middle = close > bb_middle
    
    new_state = {'prev_above_middle': currently_above_middle}
    
    # 如果没有前值或者带宽没有压缩，只保存状态，不生成信号
    if prev_above_middle is None or bb_width >= compression_threshold:
        if bb_width >= compression_threshold:
            new_state = {'prev_above_middle': currently_above_middle}  # 即使带宽没有压缩，也更新状态
        return None, new_state
    
    signal = None
    reason = ""
    compression_degree = (compression_threshold - bb_width) / compression_threshold
    
    # 向上突破中轨
    if not prev_above_middle and currently_above_middle:
        signal = 'buy'
        breakout_strength = (close - bb_middle) / bb_middle if bb_middle != 0 else 0
        confidence = min(compression_degree * 0.5 + breakout_strength * 100 + 0.3, 0.95)
        reason = f"BB 压缩向上突破: 带宽={bb_width:.4f}, 压缩度={compression_degree:.2f}"
    # 向下突破中轨
    elif prev_above_middle and not currently_above_middle:
        signal = 'sell'
        breakout_strength = (bb_middle - close) / bb_middle if bb_middle != 0 else 0
        confidence = min(compression_degree * 0.5 + breakout_strength * 100 + 0.3, 0.95)
        reason = f"BB 压缩向下突破: 带宽={bb_width:.4f}, 压缩度={compression_degree:.2f}"
    
    signal_dict = None
    if signal:
        signal_dict = {
            'signal_type': signal,
            'confidence': confidence,
            'reason': reason
        }
    
    return signal_dict, new_state
