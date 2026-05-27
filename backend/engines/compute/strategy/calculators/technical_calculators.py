"""
技术指标策略计算器 - 无状态
包含突破、布林带、均线交叉、动量等策略的无状态计算
"""
from typing import Optional, Dict, Any, Tuple


def calculate_breakout(
    close: Optional[float],
    high: Optional[float],
    low: Optional[float],
    volume_ratio: Optional[float],
    range_high: Optional[float],
    range_low: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    突破策略无状态计算
    """
    params = params or {}
    volume_ratio_threshold = params.get('volume_ratio_threshold', 1.5)
    
    new_state = {}
    
    if close is None or high is None or low is None or volume_ratio is None:
        return None, new_state
    
    if range_high is None or range_low is None:
        return None, new_state
    
    if close > range_high and volume_ratio >= volume_ratio_threshold:
        breakout_magnitude = (close - range_high) / range_high if range_high > 0 else 0
        confidence = min(0.9, breakout_magnitude * 50 + (volume_ratio / volume_ratio_threshold) * 0.3)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"向上突破: 价格={close:.2f}, 区间高点={range_high:.2f}, 成交量比={volume_ratio:.2f}"
        }, new_state
    
    if close < range_low and volume_ratio >= volume_ratio_threshold:
        breakout_magnitude = (range_low - close) / range_low if range_low > 0 else 0
        confidence = min(0.9, breakout_magnitude * 50 + (volume_ratio / volume_ratio_threshold) * 0.3)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"向下突破: 价格={close:.2f}, 区间低点={range_low:.2f}, 成交量比={volume_ratio:.2f}"
        }, new_state
    
    return None, new_state


def calculate_volatility_expansion(
    atr_ratio: Optional[float],
    price_position: Optional[float],
    close: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    波动率扩张策略无状态计算
    """
    params = params or {}
    atr_expansion_ratio = params.get('atr_expansion_ratio', 1.5)
    
    new_state = {}
    
    if atr_ratio is None or price_position is None:
        return None, new_state
    
    if atr_ratio < atr_expansion_ratio:
        return None, new_state
    
    if price_position > 0.5:
        confidence = min(0.9, (atr_ratio / atr_expansion_ratio) * 0.4 + price_position * 0.4 + 0.1)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"波动率扩张向上: ATR比={atr_ratio:.2f}, 价格位置={price_position:.2f}"
        }, new_state
    
    if price_position < -0.5:
        confidence = min(0.9, (atr_ratio / atr_expansion_ratio) * 0.4 + abs(price_position) * 0.4 + 0.1)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"波动率扩张向下: ATR比={atr_ratio:.2f}, 价格位置={price_position:.2f}"
        }, new_state
    
    return None, new_state


def calculate_momentum_ignition(
    volume_ratio: Optional[float],
    return_1h: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    动量点火策略无状态计算
    """
    params = params or {}
    volume_spike_ratio = params.get('volume_spike_ratio', 3.0)
    return_threshold = params.get('return_threshold', 0.01)
    
    new_state = {}
    
    if volume_ratio is None or return_1h is None:
        return None, new_state
    
    if volume_ratio >= volume_spike_ratio and return_1h >= return_threshold:
        confidence = min(0.9, ((volume_ratio / volume_spike_ratio) * 0.4 + (return_1h / return_threshold) * 0.4 + 0.1))
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"动量点火做多: 成交量急放={volume_ratio:.2f}x, 1h涨幅={return_1h*100:.2f}%"
        }, new_state
    elif volume_ratio >= volume_spike_ratio and return_1h <= -return_threshold:
        confidence = min(0.9, ((volume_ratio / volume_spike_ratio) * 0.4 + (abs(return_1h) / return_threshold) * 0.4 + 0.1))
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"动量点火做空: 成交量急放={volume_ratio:.2f}x, 1h跌幅={return_1h*100:.2f}%"
        }, new_state
    
    return None, new_state


def calculate_sma_crossover(
    sma_fast: Optional[float],
    sma_slow: Optional[float],
    fast_prev: Optional[float] = None,
    slow_prev: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    SMA交叉策略无状态计算
    """
    params = params or {}
    new_state = {'fast_prev': sma_fast, 'slow_prev': sma_slow}
    
    if sma_fast is None or sma_slow is None:
        return None, new_state
    
    if fast_prev is None or slow_prev is None:
        return None, new_state
    
    if sma_fast > sma_slow and fast_prev <= slow_prev:
        confidence = min(0.9, 0.5 + (sma_fast - sma_slow) / sma_slow * 2)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"SMA金叉: SMA={sma_fast:.2f} > SMA={sma_slow:.2f}"
        }, new_state
    elif sma_fast < sma_slow and fast_prev >= slow_prev:
        confidence = min(0.9, 0.5 + (sma_slow - sma_fast) / sma_slow * 2)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"SMA死叉: SMA={sma_fast:.2f} < SMA={sma_slow:.2f}"
        }, new_state
    
    return None, new_state


def calculate_ema_crossover(
    ema_fast: Optional[float],
    ema_slow: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    EMA交叉策略无状态计算
    """
    params = params or {}
    new_state = {}
    
    if ema_fast is None or ema_slow is None:
        return None, new_state
    
    signal_type = None
    if ema_fast > ema_slow:
        signal_type = 'buy'
    elif ema_fast < ema_slow:
        signal_type = 'sell'
    
    if signal_type is None:
        return None, new_state
    
    confidence = min(0.9, 0.5 + abs(ema_fast - ema_slow) / ema_slow * 2)
    
    return {
        'signal_type': signal_type,
        'confidence': confidence,
        'reason': f"EMA交叉: EMA={ema_fast:.2f} vs EMA={ema_slow:.2f}"
    }, new_state


def calculate_bollinger_bands(
    close: Optional[float],
    bb_upper: Optional[float],
    bb_lower: Optional[float],
    price_prev: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    布林带策略无状态计算
    """
    params = params or {}
    new_state = {'price_prev': close}
    
    if close is None or bb_upper is None or bb_lower is None:
        return None, new_state
    
    if price_prev is None:
        return None, new_state
    
    if price_prev > bb_lower and close <= bb_lower:
        confidence = min(0.9, 0.5 + (bb_lower - close) / bb_lower)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"布林带跌破下轨: 价格={close:.2f}, 下轨={bb_lower:.2f}"
        }, new_state
    elif price_prev < bb_upper and close >= bb_upper:
        confidence = min(0.9, 0.5 + (close - bb_upper) / bb_upper)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"布林带突破上轨: 价格={close:.2f}, 上轨={bb_upper:.2f}"
        }, new_state
    
    return None, new_state


def calculate_momentum(
    momentum: Optional[float],
    close: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    动量策略无状态计算
    """
    params = params or {}
    threshold = params.get('threshold', 0.02)
    
    new_state = {}
    
    if momentum is None:
        return None, new_state
    
    if momentum > threshold:
        confidence = min(0.9, 0.5 + momentum / threshold * 0.4)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"动量向上: momentum={momentum*100:.2f}%"
        }, new_state
    elif momentum < -threshold:
        confidence = min(0.9, 0.5 + abs(momentum) / threshold * 0.4)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"动量向下: momentum={momentum*100:.2f}%"
        }, new_state
    
    return None, new_state
