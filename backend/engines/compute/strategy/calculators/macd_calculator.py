"""
MACD Strategy Calculator - MACD 策略无状态计算模块

纯函数计算，不管理任何状态。
状态由 runtime 层提供和管理。
"""
from typing import Optional, Dict, Any, Tuple


def calculate_macd_signal(
    macd_value: float,
    signal_value: float,
    prev_macd: Optional[float] = None,
    prev_signal: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    无状态计算 MACD 策略信号
    
    Args:
        macd_value: 当前 MACD 值
        signal_value: 当前信号线值
        prev_macd: 前一个 MACD 值（状态由外部提供）
        prev_signal: 前一个信号线值（状态由外部提供）
        params: 其他参数字典
    
    Returns:
        (signal_dict, new_state_data): 信号字典和新状态数据
    """
    params = params or {}
    
    new_state = {
        'prev_macd': macd_value,
        'prev_signal': signal_value
    }
    
    # 如果没有前值，只保存状态，不生成信号
    if prev_macd is None or prev_signal is None:
        return None, new_state
    
    signal = None
    confidence = 0.7  # 默认置信度
    reason = ""
    
    # MACD 金叉 - 买入信号
    if prev_macd <= prev_signal and macd_value > signal_value:
        signal = 'buy'
        reason = f"MACD 金叉: {macd_value:.4f} > {signal_value:.4f}"
    # MACD 死叉 - 卖出信号
    elif prev_macd >= prev_signal and macd_value < signal_value:
        signal = 'sell'
        reason = f"MACD 死叉: {macd_value:.4f} < {signal_value:.4f}"
    
    signal_dict = None
    if signal:
        signal_dict = {
            'signal_type': signal,
            'confidence': confidence,
            'reason': reason
        }
    
    return signal_dict, new_state
