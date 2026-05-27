"""
跨交易所策略计算器 - 无状态
包含领先滞后、溢价背离等策略的无状态计算
"""
from typing import Optional, Dict, Any, Tuple


def calculate_lead_lag(
    binance_return: Optional[float],
    okx_return: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    跨交易所领先滞后策略无状态计算
    """
    params = params or {}
    threshold = params.get('divergence_threshold', 0.005)
    
    new_state = {}
    
    if binance_return is None or okx_return is None:
        return None, new_state
    
    return_diff = binance_return - okx_return
    
    if return_diff > threshold:
        divergence_magnitude = (return_diff - threshold) / threshold
        confidence = min(0.9, divergence_magnitude * 0.7 + 0.2)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"领先滞后做多: Binance领先, 收益率差={return_diff*100:.3f}%, threshold={threshold*100:.3f}%"
        }, new_state
    elif return_diff < -threshold:
        divergence_magnitude = (abs(return_diff) - threshold) / threshold
        confidence = min(0.9, divergence_magnitude * 0.7 + 0.2)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"领先滞后做空: Binance领跌, 收益率差={return_diff*100:.3f}%, threshold={threshold*100:.3f}%"
        }, new_state
    
    return None, new_state


def calculate_premium_divergence(
    premium: Optional[float],
    basis: Optional[float],
    spread: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    跨交易所溢价背离策略无状态计算
    """
    params = params or {}
    premium_threshold = params.get('premium_threshold', 0.005)
    
    new_state = {}
    
    if premium is None:
        return None, new_state
    
    if premium > premium_threshold:
        premium_magnitude = (premium - premium_threshold) / premium_threshold if premium_threshold > 0 else 0
        basis_alignment = min(abs(basis) / 0.01, 1.0) if basis is not None else 0.5
        confidence = min(0.9, premium_magnitude * 0.5 + basis_alignment * 0.3 + 0.2)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"溢价背离做空: 溢价={premium*100:.3f}%, 基差={basis*100:.3f}%"
        }, new_state
    elif premium < -premium_threshold:
        premium_magnitude = (abs(premium) - premium_threshold) / premium_threshold if premium_threshold > 0 else 0
        basis_alignment = min(abs(basis) / 0.01, 1.0) if basis is not None else 0.5
        confidence = min(0.9, premium_magnitude * 0.5 + basis_alignment * 0.3 + 0.2)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"溢价背离做多: 溢价={premium*100:.3f}%, 基差={basis*100:.3f}%"
        }, new_state
    
    return None, new_state
