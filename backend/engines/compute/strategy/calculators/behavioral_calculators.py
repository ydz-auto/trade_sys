"""
行为策略计算器 - 无状态
包含所有行为策略（Panic Reversal, OI Flush, Short Squeeze等）的无状态计算
"""
from typing import Optional, Dict, Any, Tuple


def calculate_panic_reversal(
    return_1h: Optional[float],
    volume_ratio: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    恐慌反转策略无状态计算
    """
    params = params or {}
    drop_threshold = params.get('drop_threshold', -0.015)
    volume_ratio_threshold = params.get('volume_ratio_threshold', 1.5)
    
    new_state = {}
    
    if return_1h is None or volume_ratio is None:
        return None, new_state
    
    if return_1h <= drop_threshold and volume_ratio >= volume_ratio_threshold:
        confidence = min(0.9, (abs(return_1h) - abs(drop_threshold)) * 50 + 0.5)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"恐慌反转: 1h跌幅={return_1h*100:.2f}%, 成交量比={volume_ratio:.2f}"
        }, new_state
    
    return None, new_state


def calculate_oi_flush(
    oi_delta: Optional[float],
    funding_delta: Optional[float],
    return_1h: Optional[float],
    close: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    OI清洗策略无状态计算
    """
    params = params or {}
    oi_flush_threshold = params.get('oi_flush_threshold', -0.10)
    funding_threshold = params.get('funding_normalization_threshold', 0.5)
    
    new_state = {}
    
    if oi_delta is None or funding_delta is None:
        return None, new_state
    
    if oi_delta >= oi_flush_threshold:
        return None, new_state
    
    if abs(funding_delta) <= funding_threshold:
        return None, new_state
    
    price_change = return_1h if return_1h is not None else 0.0
    
    if price_change < 0:
        signal_type = 'buy'
        reason = f"OI清洗做多: OI变化={oi_delta*100:.2f}%, 资金费率变化={funding_delta:.4f}, 价格变化={price_change*100:.2f}%"
    else:
        signal_type = 'sell'
        reason = f"OI清洗做空: OI变化={oi_delta*100:.2f}%, 资金费率变化={funding_delta:.4f}, 价格变化={price_change*100:.2f}%"
    
    confidence = min(0.9, (abs(oi_delta) / abs(oi_flush_threshold)) * 0.4 + (abs(funding_delta) / funding_threshold) * 0.3)
    
    return {
        'signal_type': signal_type,
        'confidence': confidence,
        'reason': reason
    }, new_state


def calculate_short_squeeze(
    funding_zscore: Optional[float],
    oi_delta: Optional[float],
    short_pressure: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    空头挤压策略无状态计算
    """
    params =