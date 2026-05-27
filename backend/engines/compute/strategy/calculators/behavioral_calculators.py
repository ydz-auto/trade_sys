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
    params = params or {}
    funding_threshold = params.get('funding_extreme_threshold', -2.0)
    oi_threshold = params.get('oi_growth_threshold', 0.0)
    
    new_state = {}
    
    if funding_zscore is None or oi_delta is None:
        return None, new_state
    
    if funding_zscore < funding_threshold and oi_delta > oi_threshold and oi_delta > 0.02:
        confidence = min(0.9, (abs(funding_zscore) / abs(funding_threshold)) * 0.4 + (oi_delta / max(abs(oi_delta), 0.01)) * 0.3 + (abs(short_pressure) * 0.3 if short_pressure is not None else 0.0))
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"空头挤压做多: 资金费率Z={funding_zscore:.2f}, OI变化={oi_delta*100:.2f}%, 空头压力={short_pressure}"
        }, new_state
    
    return None, new_state


def calculate_funding_exhaustion_trap(
    funding_zscore: Optional[float],
    funding_divergence: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    资金费率耗尽陷阱策略无状态计算
    """
    params = params or {}
    threshold = params.get('funding_extreme_threshold', 2.5)
    
    new_state = {}
    
    if funding_zscore is None:
        return None, new_state
    
    if funding_zscore > threshold:
        confidence = min(0.9, (funding_zscore / threshold) * 0.5 + abs(funding_divergence or 0) * 0.3)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"资金费率耗尽做空: funding_zscore={funding_zscore:.2f} > {threshold}, 背离={funding_divergence}"
        }, new_state
    elif funding_zscore < -threshold:
        confidence = min(0.9, (abs(funding_zscore) / threshold) * 0.5 + abs(funding_divergence or 0) * 0.3)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"资金费率耗尽做多: funding_zscore={funding_zscore:.2f} < -{threshold}, 背离={funding_divergence}"
        }, new_state
    
    return None, new_state


def calculate_dead_cat_echo(
    return_4h: Optional[float],
    return_1h: Optional[float],
    volume_ratio: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    死猫回声策略无状态计算
    """
    params = params or {}
    drop_threshold = params.get('drop_threshold_4h', -0.02)
    bounce_ratio_max = params.get('bounce_ratio_max', 0.30)
    volume_fade_threshold = params.get('volume_fade_threshold', 0.8)
    
    new_state = {}
    
    if return_4h is None or volume_ratio is None:
        return None, new_state
    
    abs_drop = abs(return_4h)
    bounce_ratio = return_1h / abs_drop if abs_drop > 0 and return_4h < 0 else 0.0
    
    if abs_drop >= abs(drop_threshold) and bounce_ratio <= bounce_ratio_max and volume_ratio <= volume_fade_threshold:
        confidence = min(0.9, (abs_drop / abs(drop_threshold)) * 0.35 + (1.0 - bounce_ratio / bounce_ratio_max) * 0.35 + (1.0 - volume_ratio / volume_fade_threshold) * 0.15 + 0.15)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"死猫回声做空: 4h跌幅={abs_drop*100:.2f}%, 反弹比={bounce_ratio*100:.2f}%, 成交量衰减={volume_ratio:.2f}"
        }, new_state
    
    return None, new_state
