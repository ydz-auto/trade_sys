"""
Slippage Predictor - 滑点预测器

预测执行时的滑点，这是执行智能的核心。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import numpy as np


@dataclass
class SlippagePrediction:
    """滑点预测结果"""
    expected_slippage_bps: float
    slippage_std: float  # 滑点标准差
    worst_case_bps: float
    best_case_bps: float
    confidence: float
    factors: Dict[str, float]  # 影响因素


class SlippagePredictor:
    """滑点预测器"""
    
    def __init__(self):
        # 滑点系数（基于历史数据校准）
        self.spread_coef = 0.5  # 点差系数
        self.volatility_coef = 2.0  # 波动率系数
        self.size_coef = 0.0001  # 规模系数（每1个单位）
        self.liquidity_coef = 0.8  # 流动性系数
        self.history: List[Dict[str, Any]] = []
    
    def predict(
        self,
        order_size: float,
        current_price: float,
        spread_bps: float,
        volatility: float,
        orderbook_depth: float,
        avg_trade_size: float,
        is_maker: bool = False,
    ) -> SlippagePrediction:
        """预测滑点"""
        factors = {}
        
        # 基础滑点（点差）
        base_slippage = spread_bps * self.spread_coef
        factors["spread"] = base_slippage
        
        # 波动率影响
        volatility_slippage = volatility * 100 * self.volatility_coef  # 转换为bps
        factors["volatility"] = volatility_slippage
        
        # 订单规模影响
        relative_size = order_size / (avg_trade_size or 1)
        size_slippage = relative_size * self.size_coef * 100  # bps
        factors["size"] = size_slippage
        
        # 流动性影响
        if orderbook_depth > 0:
            liquidity_ratio = order_size / orderbook_depth
            liquidity_slippage = liquidity_ratio * self.liquidity_coef * 100  # bps
            factors["liquidity"] = liquidity_slippage
        else:
            liquidity_slippage = 0.0
            factors["liquidity"] = 0.0
        
        # 总预期滑点
        total_expected = base_slippage + volatility_slippage + size_slippage + liquidity_slippage
        
        if is_maker:
            total_expected *= 0.3  # 做市单滑点更低
        
        # 标准差（基于波动率）
        slippage_std = volatility * 50  # 经验值
        
        # 最坏/最好情况
        worst_case = total_expected + slippage_std * 2
        best_case = max(0, total_expected - slippage_std * 2)
        
        # 置信度（基于可用数据）
        confidence = 0.7
        if orderbook_depth > 0 and avg_trade_size > 0:
            confidence = 0.9
        
        return SlippagePrediction(
            expected_slippage_bps=total_expected,
            slippage_std=slippage_std,
            worst_case_bps=worst_case,
            best_case_bps=best_case,
            confidence=confidence,
            factors=factors,
        )
    
    def record_actual_slippage(
        self,
        order_size: float,
        requested_price: float,
        actual_price: float,
        side: str,
        market_data: Dict[str, Any],
    ) -> None:
        """记录实际滑点，用于模型校准"""
        if requested_price > 0:
            slippage_pct = abs((actual_price - requested_price) / requested_price)
            slippage_bps = slippage_pct * 10000
            
            self.history.append({
                "size": order_size,
                "slippage_bps": slippage_bps,
                "side": side,
                "timestamp": market_data.get("timestamp"),
                "spread": market_data.get("spread_bps"),
                "volatility": market_data.get("volatility"),
            })
            
            if len(self.history) > 1000:
                self.history = self.history[-1000:]
    
    def calibrate(self) -> None:
        """校准模型参数"""
        if len(self.history) < 100:
            return
        
        recent = self.history[-100:]
        
        spread_slippage = [h["slippage_bps"] / h["spread"] for h in recent if h["spread"] > 0]
        if spread_slippage:
            self.spread_coef = np.mean(spread_slippage)
        
        volatility_slippage = [h["slippage_bps"] / (h["volatility"] * 100) for h in recent if h["volatility"] > 0]
        if volatility_slippage:
            self.volatility_coef = np.mean(volatility_slippage)
