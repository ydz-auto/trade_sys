"""
RSI Strategy Calculator - RSI 策略无状态计算模块

纯函数计算，不管理任何状态。
状态由 runtime 层提供和管理。
"""
from typing import Optional, Dict, Any, Tuple


def calculate_rsi_signal(
    rsi_value: float,
    prev_rsi: Optional[float] = None,
    oversold_threshold: float = 30.0,
    overbought_threshold: float = 70.0,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    无状态计算 RSI 策略信号
    
    Args:
        rsi_value: 当前 RSI 值
        prev_rsi: 前一个 RSI 值（状态由外部提供）
        oversold_threshold: 超卖阈值
        overbought_threshold: 超买阈值
        params: 其他参数字典
    
    Returns:
        (signal_dict, new_state_data): 信号字典和新状态数据
        signal_dict 格式: {'signal_type': 'buy'|'sell'|None, 'confidence': float, 'reason': str}
    """
    params = params or {}
    oversold = params.get('oversold', oversold_threshold)
    overbought = params.get('overbought', overbought_threshold)
    
    new_state = {'prev_rsi': rsi_value}
    
    # 如果没有前值，只保存状态，不生成信号
    if prev_rsi is None:
        return None, new_state
    
    signal = None
    confidence = 0.0
    reason = ""
    
    # RSI 从超卖区域回升 - 买入信号
    if prev_rsi >= oversold and rsi_value < oversold:
        signal = 'buy'
        confidence = 1.0 - (rsi_value / 100)
        reason = f"RSI {rsi_value:.1f} < {oversold} (超卖回升)"
    # RSI 从超买区域回落 - 卖出信号
    elif prev_rsi <= overbought and rsi_value > overbought:
        signal = 'sell'
        confidence = (rsi_value - 50) / 50
        reason = f"RSI {rsi_value:.1f} > {overbought} (超买回落)"
    
    signal_dict = None
    if signal:
        signal_dict = {
            'signal_type': signal,
            'confidence': min(confidence, 0.95),  # 限制最大置信度
            'reason': reason
        }
    
    return signal_dict, new_state
