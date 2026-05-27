"""
微观结构策略计算器 - 无状态
包含订单簿失衡、扫单检测、流动性真空等策略的无状态计算
"""
from typing import Optional, Dict, Any, Tuple


def calculate_imbalance_pressure(
    imbalance_5: Optional[float],
    microprice: Optional[float],
    mid_price: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    订单簿失衡压力策略无状态计算
    """
    params = params or {}
    imbalance_threshold = params.get('imbalance_threshold', 0.3)
    
    new_state = {}
    
    if imbalance_5 is None or microprice is None or mid_price is None or mid_price == 0:
        return None, new_state
    
    if imbalance_5 > imbalance_threshold and microprice > mid_price:
        imbalance_strength = (imbalance_5 - imbalance_threshold) / (1.0 - imbalance_threshold)
        confidence = min(0.9, imbalance_strength * 0.7 + 0.2)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"订单簿买盘失衡: imbalance_5={imbalance_5:.3f}, microprice偏移={((microprice - mid_price) / mid_price) * 100:.4f}%"
        }, new_state
    elif imbalance_5 < -imbalance_threshold and microprice < mid_price:
        imbalance_strength = (abs(imbalance_5) - imbalance_threshold) / (1.0 - imbalance_threshold)
        confidence = min(0.9, imbalance_strength * 0.7 + 0.2)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"订单簿卖盘失衡: imbalance_5={imbalance_5:.3f}, microprice偏移={((microprice - mid_price) / mid_price) * 100:.4f}%"
        }, new_state
    
    return None, new_state


def calculate_sweep_detection(
    sweep_buy_score: Optional[float],
    sweep_sell_score: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    扫单检测策略无状态计算
    """
    params = params or {}
    sweep_threshold = params.get('sweep_threshold', 0.7)
    
    new_state = {}
    
    if sweep_buy_score is None or sweep_sell_score is None:
        return None, new_state
    
    if sweep_buy_score > sweep_threshold:
        sweep_strength = (sweep_buy_score - sweep_threshold) / (1.0 - sweep_threshold) if sweep_threshold < 1.0 else sweep_buy_score
        confidence = min(0.9, sweep_strength * 0.7 + 0.2)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"买方扫单: sweep_buy_score={sweep_buy_score:.3f} > {sweep_threshold}"
        }, new_state
    
    if sweep_sell_score > sweep_threshold:
        sweep_strength = (sweep_sell_score - sweep_threshold) / (1.0 - sweep_threshold) if sweep_threshold < 1.0 else sweep_sell_score
        confidence = min(0.9, sweep_strength * 0.7 + 0.2)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"卖方扫单: sweep_sell_score={sweep_sell_score:.3f} > {sweep_threshold}"
        }, new_state
    
    return None, new_state


def calculate_liquidity_vacuum(
    spread: Optional[float],
    top5_depth: Optional[float],
    cancel_rate: Optional[float],
    trade_delta: Optional[float],
    prev_avg_spread: Optional[float] = None,
    prev_top5_depth: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    流动性真空策略无状态计算
    """
    params = params or {}
    spread_expansion_factor = params.get('spread_expansion_factor', 2.0)
    cancel_rate_threshold = params.get('cancel_rate_threshold', 0.3)
    
    new_state = {
        'avg_spread': spread,
        'prev_top5_depth': top5_depth
    }
    
    if spread is None or top5_depth is None or cancel_rate is None or trade_delta is None:
        return None, new_state
    
    if prev_avg_spread is None or prev_top5_depth is None:
        return None, new_state
    
    avg_spread = prev_avg_spread * 0.95 + spread * 0.05
    spread_expansion = spread / avg_spread if avg_spread > 0 else 1.0
    
    depth_declining = False
    if prev_top5_depth is not None and prev_top5_depth > 0:
        depth_decline_ratio = (prev_top5_depth - top5_depth) / prev_top5_depth
        depth_declining = depth_decline_ratio > 0.1
    
    if spread_expansion >= spread_expansion_factor and depth_declining and cancel_rate >= cancel_rate_threshold:
        spread_score = min((spread_expansion - spread_expansion_factor) / spread_expansion_factor, 1.0)
        depth_score = min(depth_decline_ratio / 0.3, 1.0)
        cancel_score = min(cancel_rate / 0.5, 1.0)
        confidence = min(0.9, spread_score * 0.4 + depth_score * 0.3 + cancel_score * 0.2 + 0.1)
        
        if trade_delta > 0:
            signal_type = 'buy'
        else:
            signal_type = 'sell'
        
        return {
            'signal_type': signal_type,
            'confidence': confidence,
            'reason': f"流动性真空突破: spread扩张={spread_expansion:.2f}x, 深度下降={depth_decline_ratio*100:.1f}%, cancel_rate={cancel_rate:.3f}, trade_delta={trade_delta:.1f}"
        }, new_state
    
    return None, new_state


def calculate_aggressive_flow(
    cumulative_delta: Optional[float],
    aggressive_buy_volume: Optional[float],
    aggressive_sell_volume: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    激进流向策略无状态计算
    """
    params = params or {}
    flow_imbalance_threshold = params.get('flow_imbalance_threshold', 2.0)
    
    new_state = {}
    
    if cumulative_delta is None or aggressive_buy_volume is None or aggressive_sell_volume is None:
        return None, new_state
    
    if aggressive_sell_volume > 0:
        buy_sell_ratio = aggressive_buy_volume / aggressive_sell_volume
    else:
        buy_sell_ratio = float('inf') if aggressive_buy_volume > 0 else 1.0
    
    if aggressive_buy_volume > 0:
        sell_buy_ratio = aggressive_sell_volume / aggressive_buy_volume
    else:
        sell_buy_ratio = float('inf') if aggressive_sell_volume > 0 else 1.0
    
    if buy_sell_ratio >= flow_imbalance_threshold and cumulative_delta > 0:
        flow_imbalance = min((buy_sell_ratio - flow_imbalance_threshold) / flow_imbalance_threshold, 1.0)
        delta_alignment = min(abs(cumulative_delta) / 100.0, 1.0)
        confidence = min(0.9, flow_imbalance * 0.5 + delta_alignment * 0.3 + 0.2)
        return {
            'signal_type': 'buy',
            'confidence': confidence,
            'reason': f"激进买盘主导: 买/卖比={buy_sell_ratio:.2f}, cumulative_delta={cumulative_delta:.1f}"
        }, new_state
    elif sell_buy_ratio >= flow_imbalance_threshold and cumulative_delta < 0:
        flow_imbalance = min((sell_buy_ratio - flow_imbalance_threshold) / flow_imbalance_threshold, 1.0)
        delta_alignment = min(abs(cumulative_delta) / 100.0, 1.0)
        confidence = min(0.9, flow_imbalance * 0.5 + delta_alignment * 0.3 + 0.2)
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"激进卖盘主导: 卖/买比={sell_buy_ratio:.2f}, cumulative_delta={cumulative_delta:.1f}"
        }, new_state
    
    return None, new_state


def calculate_volume_climax_fade(
    volume_ratio: Optional[float],
    upper_shadow_ratio: Optional[float],
    return_1h: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    放量高潮衰竭策略无状态计算
    """
    params = params or {}
    volume_ratio_threshold = params.get('volume_ratio_threshold', 2.0)
    upper_shadow_threshold = params.get('upper_shadow_threshold', 0.3)
    price_threshold = params.get('price_threshold', 0.003)
    
    new_state = {}
    
    if volume_ratio is None or upper_shadow_ratio is None or return_1h is None:
        return None, new_state
    
    if volume_ratio >= volume_ratio_threshold and upper_shadow_ratio >= upper_shadow_threshold and return_1h >= price_threshold:
        confidence = min(0.9, ((volume_ratio / volume_ratio_threshold) * 0.3 + (upper_shadow_ratio / upper_shadow_threshold) * 0.4 + 0.2))
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"放量高潮衰竭: 成交量比={volume_ratio:.2f}, 上影线比={upper_shadow_ratio:.2f}, 1h涨幅={return_1h*100:.2f}%"
        }, new_state
    
    return None, new_state


def calculate_weak_bounce_short(
    return_4h: Optional[float],
    return_1h: Optional[float],
    volume_ratio: Optional[float],
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    弱反弹做空策略无状态计算
    """
    params = params or {}
    drop_threshold = params.get('drop_threshold_4h', -0.02)
    bounce_min = params.get('bounce_min', 0.003)
    bounce_max = params.get('bounce_max', 0.015)
    volume_threshold = params.get('volume_ratio_threshold', 1.5)
    
    new_state = {}
    
    if return_4h is None or return_1h is None or volume_ratio is None:
        return None, new_state
    
    if return_4h <= drop_threshold and bounce_min <= return_1h <= bounce_max and volume_ratio >= volume_threshold:
        confidence = min(0.9, ((abs(return_4h) / abs(drop_threshold)) * 0.4 + (return_1h / bounce_max) * 0.3 + (volume_ratio / volume_threshold) * 0.3))
        return {
            'signal_type': 'sell',
            'confidence': confidence,
            'reason': f"弱反弹做空: 4h跌幅={return_4h*100:.2f}%, 反弹幅={return_1h*100:.2f}%, 成交量比={volume_ratio:.2f}"
        }, new_state
    
    return None, new_state
