#!/usr/bin/env python3
"""
Short Squeeze Strategy - 使用 Trade-Derived Pressure Proxy

策略逻辑：
- 使用 CVD (Cumulative Volume Delta) 作为多空压力代理指标
- 使用 buy_sell_imbalance 和 taker_buy_ratio 作为买入压力指标
- 不依赖真实 OI 数据，避免历史数据缺失问题

注意：
- CVD ≠ OI
- CVD 反映主动成交压力，但不能判断是"新增开仓"还是"平仓"
- 策略名仍为 short_squeeze，但内部使用 trade-derived pressure
"""

import sys
import os
from typing import Dict, Optional

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from engines.compute.strategy.strategies import (
    BaseStrategy,
    StrategySignal,
    StrategyType,
    ActionType,
)


class ShortSqueezePressureStrategy(BaseStrategy):
    """
    使用 Trade-Derived Pressure Proxy 的 Short Squeeze 策略
    
    注意：此策略使用 CVD (Cumulative Volume Delta) 作为 OI 的替代指标
    CVD ≠ OI，仅反映主动成交压力，无法区分开仓和平仓
    
    触发条件：
    1. 价格突破 + 上涨动量
    2. CVD Z-Score > 阈值（反映多头主动成交压力）
    3. Taker Buy Ratio > 阈值（反映被动买入压力）
    4. Volume Z-Score > 阈值（反映成交量异常）
    
    参数：
    - price_momentum_threshold: 价格动量阈值
    - cvd_zscore_threshold: CVD Z-Score 阈值（默认 2.0）
    - taker_buy_ratio_threshold: Taker 买入比例阈值（默认 0.6）
    - volume_zscore_threshold: 成交量 Z-Score 阈值（默认 1.5）
    """
    
    def __init__(
        self,
        strategy_id: str = "short_squeeze_pressure",
        price_momentum_threshold: float = 0.003,
        cvd_zscore_threshold: float = 2.0,
        taker_buy_ratio_threshold: float = 0.6,
        volume_zscore_threshold: float = 1.5,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.price_momentum_threshold = price_momentum_threshold
        self.cvd_zscore_threshold = cvd_zscore_threshold
        self.taker_buy_ratio_threshold = taker_buy_ratio_threshold
        self.volume_zscore_threshold = volume_zscore_threshold
        self.default_quantity = default_quantity
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None
        
        # 获取 OHLCV 数据
        close_prices = data.get("close_prices", [])
        if not close_prices or len(close_prices) < 12:
            return None
        
        # 获取 trade-derived pressure 指标
        cvd_zscore = data.get("cvd_zscore", 0.0)
        taker_buy_ratio = data.get("taker_buy_ratio", 0.5)
        volume_zscore = data.get("volume_zscore", 0.0)
        buy_sell_imbalance = data.get("buy_sell_imbalance", 0.0)
        
        # 计算价格动量（1小时前到现在）
        current_price = close_prices[-1]
        price_1h_ago = close_prices[-12] if len(close_prices) >= 12 else close_prices[0]
        price_momentum = (current_price - price_1h_ago) / price_1h_ago
        
        # Short Squeeze 信号检测
        # 条件：价格突破 + 多头主动成交压力 + 成交量异常
        squeeze_conditions = (
            price_momentum > self.price_momentum_threshold and  # 价格上涨动量
            cvd_zscore > self.cvd_zscore_threshold and  # CVD Z-Score 反映多头主动成交压力
            taker_buy_ratio > self.taker_buy_ratio_threshold and  # Taker 买入比例高
            volume_zscore > self.volume_zscore_threshold  # 成交量异常放大
        )
        
        # 反转信号检测（空头挤压结束）
        squeeze_reversal = (
            price_momentum < -self.price_momentum_threshold and  # 价格下跌
            cvd_zscore < -self.cvd_zscore_threshold  # CVD 反转
        )
        
        if squeeze_conditions:
            symbol = data.get("symbol", "BTCUSDT")
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                confidence=min(1.0, (cvd_zscore - self.cvd_zscore_threshold) / 2.0),
                metadata={
                    "signal_type": "short_squeeze_trigger",
                    "price_momentum": price_momentum,
                    "cvd_zscore": cvd_zscore,
                    "taker_buy_ratio": taker_buy_ratio,
                    "volume_zscore": volume_zscore,
                    "pressure_proxy": "cvd",
                }
            )
        
        elif squeeze_reversal:
            symbol = data.get("symbol", "BTCUSDT")
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.CLOSE,
                quantity=self.default_quantity,
                confidence=0.8,
                metadata={
                    "signal_type": "squeeze_reversal",
                    "price_momentum": price_momentum,
                    "cvd_zscore": cvd_zscore,
                    "pressure_proxy": "cvd",
                }
            )
        
        return None


def create_short_squeeze_strategy(
    price_momentum_threshold: float = 0.003,
    cvd_zscore_threshold: float = 2.0,
    taker_buy_ratio_threshold: float = 0.6,
    volume_zscore_threshold: float = 1.5,
) -> ShortSqueezePressureStrategy:
    """工厂函数：创建 Short Squeeze Pressure 策略"""
    return ShortSqueezePressureStrategy(
        price_momentum_threshold=price_momentum_threshold,
        cvd_zscore_threshold=cvd_zscore_threshold,
        taker_buy_ratio_threshold=taker_buy_ratio_threshold,
        volume_zscore_threshold=volume_zscore_threshold,
    )


# 参数网格（用于 Walk-Forward 优化）
PARAM_GRID = {
    "price_momentum_threshold": [0.002, 0.003, 0.005],
    "cvd_zscore_threshold": [1.5, 2.0, 2.5],
    "taker_buy_ratio_threshold": [0.55, 0.6, 0.65],
    "volume_zscore_threshold": [1.0, 1.5, 2.0],
}
