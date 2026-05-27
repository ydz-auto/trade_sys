"""
Trend Following Strategy Calculator - 趋势跟踪策略无状态计算模块

纯函数计算，不管理任何状态。
状态由 runtime 层提供和管理。
"""
from typing import Optional, Dict, Any, Tuple


def calculate_trend_following_signal(
    ema_fast: float,
    ema_slow: float,
    prev_ema_fast: Optional[float] = None,
    prev_ema_slow: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    无状态计算趋势跟踪策略信号
    
    Args:
        ema_fast: 当前快线 EMA
        ema_slow: 当前慢线 EMA
        prev_ema_fast: 前一个快线 EMA（状态由外部提供）
        prev_ema_slow: 前一个慢线 EMA（状态由外部提供）
        params: 其他参数字典
    
    Returns:
        (signal_dict, new_state_data): 信号字典和新状态数据
    """
    params = params or {}
    
    new_state = {
        'prev_ema_fast': ema_fast,
        'prev_ema_slow': ema_slow
    }
    
    # 如果没有前值，只保存状态，不生成信号
    if prev_ema_fast is None or prev_ema_slow is None:
        return None, new_state
    
    signal = None
    reason = ""
    
    # 上升趋势：快线 > 慢线 且 两条线都在上升
    if ema_fast > ema_slow and ema_fast > prev_ema_fast and ema_slow > prev_ema_slow:
        signal = 'buy'
        ema_separation = abs(ema_fast - ema_slow) / ema_slow if ema_slow != 0 else 0
        confidence = min(ema_separation * 200 + 0.4, 0.95)
        reason = f"上升趋势: EMA{params.get('fast_period', 10)}={ema_fast:.2f} > EMA{params.get('slow_period', 50)}={ema_slow:.2f}"
    # 下降趋势：快线 < 慢线 且 两条线都在下降
    elif ema_fast < ema_slow and ema_fast < prev_ema_fast and ema_slow < prev_ema_slow:
        signal = 'sell'
        ema_separation = abs(ema_fast - ema_slow) / ema_slow if ema_slow != 0 else 0
        confidence = min(ema_separation * 200 + 0.4, 0.95)
        reason = f"下降趋势: EMA{params.get('fast_period', 10)}={ema_fast:.2f} < EMA{params.get('slow_period', 50)}={ema_slow:.2f}"
    
    signal_dict = None
    if signal:
        signal_dict = {
            'signal_type': signal,
            'confidence': confidence,
            'reason': reason
        }
    
    return signal_dict, new_state
