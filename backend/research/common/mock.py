"""
统一 Mock 数据生成器

替代 simple_backtest / walk_forward_simple / event_study / signal_validation
中各自的 generate_test_contexts() 实现。

唯一入口: generate_test_contexts()
"""

import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engines.compute.context import (
    MarketContext,
    TimeframeContext,
    PriceState,
    TrendStateData,
    VolatilityStateData,
    VolumeStateData,
    FlowState,
    LiquidityStateData,
    DerivativesContext,
    OIData,
    FundingData,
    LiquidationData,
    RiskContext,
    TrendState,
    FlowPressure,
    FundingBias,
    LiquidityState,
    VolatilityState,
    VolumeState,
)


def generate_test_contexts(
    num_samples: int = 1000,
    with_trend: bool = True,
) -> Tuple[List[MarketContext], List[int], np.ndarray]:
    """
    生成测试用的 MarketContext 序列

    Args:
        num_samples: 样本数量
        with_trend: 是否添加趋势结构（event_study 需要方向性价格）

    Returns:
        (market_contexts, timestamps, prices)
    """
    market_contexts = []
    timestamps = []
    prices = []

    base_timestamp = int(pd.Timestamp("2024-01-01").value / 10**6)
    base_price = 45000.0
    extreme_prob = 0.15

    if with_trend:
        trend_direction = 1
        trend_length = 0
        min_trend_length = 5
        max_trend_length = 30

    for i in range(num_samples):
        timestamp = base_timestamp + i * 15 * 60 * 1000
        timestamps.append(timestamp)

        if with_trend:
            trend_length += 1
            if trend_length >= max_trend_length or (
                trend_length >= min_trend_length and np.random.random() < 0.05
            ):
                trend_direction = -trend_direction
                trend_length = 0
            trend_bias = trend_direction * 0.001
            random_component = np.random.normal(0, 0.0025) * base_price
            trend_component = trend_bias * base_price
            price_change = random_component + trend_component
        else:
            price_change = np.random.normal(0, 0.003) * base_price

        price = base_price + price_change
        base_price = price
        prices.append(price)

        tf_contexts = {}

        m1_flow_pressure = np.random.choice(
            [FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL],
            p=[0.35, 0.35, 0.3],
        )
        tf_contexts["1m"] = TimeframeContext(
            timeframe="1m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.0015)),
                low=price * (1 - np.random.uniform(0, 0.0015)),
                close=price,
                change_percent=np.random.uniform(-0.3, 0.3),
            ),
            liquidity=LiquidityStateData(
                state=np.random.choice([LiquidityState.NORMAL, LiquidityState.THIN], p=[0.9, 0.1]),
                spread=0.5,
            ),
            flow=FlowState(
                pressure=m1_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-100, 100),
            ),
        )

        m5_flow_pressure = np.random.choice(
            [FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL],
            p=[0.35, 0.35, 0.3],
        )
        tf_contexts["5m"] = TimeframeContext(
            timeframe="5m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.004)),
                low=price * (1 - np.random.uniform(0, 0.004)),
                close=price,
                change_percent=np.random.uniform(-0.6, 0.6),
            ),
            flow=FlowState(
                pressure=m5_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-500, 500),
            ),
        )

        m15_trend = np.random.choice(
            [TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS],
            p=[0.35, 0.35, 0.3],
        )
        m15_flow_pressure = np.random.choice(
            [FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL],
            p=[0.35, 0.35, 0.3],
        )

        if np.random.random() < extreme_prob:
            m15_change_percent = np.random.uniform(0.5, 1.5)
        else:
            m15_change_percent = np.random.uniform(-1.2, 1.2)

        tf_contexts["15m"] = TimeframeContext(
            timeframe="15m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.006)),
                low=price * (1 - np.random.uniform(0, 0.006)),
                close=price,
                change_percent=m15_change_percent,
            ),
            trend=TrendStateData(
                state=m15_trend,
                slope=np.random.uniform(-0.012, 0.012),
                strength=np.random.uniform(0.3, 0.95),
            ),
            volatility=VolatilityStateData(
                state=np.random.choice(
                    [VolatilityState.NORMAL, VolatilityState.ELEVATED, VolatilityState.LOW],
                    p=[0.5, 0.35, 0.15],
                ),
                atr_pct=np.random.uniform(0.008, 0.025),
            ),
            volume=VolumeStateData(
                state=np.random.choice(
                    [VolumeState.NORMAL, VolumeState.CLIMAX, VolumeState.DRY],
                    p=[0.6, 0.25, 0.15],
                ),
                volume_zscore=np.random.uniform(-2.5, 2.5),
            ),
            flow=FlowState(
                pressure=m15_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-1200, 1200),
                cvd_slope=np.random.uniform(-0.15, 0.15),
                aggressive_ratio=np.random.uniform(0.25, 0.75),
            ),
        )

        tf_contexts["1h"] = TimeframeContext(
            timeframe="1h",
            trend=TrendStateData(
                state=np.random.choice(
                    [TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS],
                    p=[0.35, 0.35, 0.3],
                ),
                slope=np.random.uniform(-0.006, 0.006),
                strength=np.random.uniform(0.3, 0.95),
            ),
            price=PriceState(
                close=price,
                change_percent=np.random.uniform(-1.8, 1.8),
            ),
        )

        tf_contexts["4h"] = TimeframeContext(
            timeframe="4h",
            trend=TrendStateData(
                state=np.random.choice(
                    [TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS],
                    p=[0.35, 0.35, 0.3],
                ),
                slope=np.random.uniform(-0.004, 0.004),
                strength=np.random.uniform(0.3, 0.95),
            ),
        )

        if np.random.random() < extreme_prob:
            oi_zscore = np.random.uniform(1.6, 3.5)
        else:
            oi_zscore = np.random.uniform(-2.8, 2.8)

        if np.random.random() < extreme_prob:
            funding_zscore = np.random.uniform(-3.5, -1.6)
        else:
            funding_zscore = np.random.uniform(-2.8, 2.8)

        if funding_zscore > 2.0:
            funding_bias = FundingBias.EXTREME_POSITIVE
        elif funding_zscore > 0.5:
            funding_bias = FundingBias.POSITIVE
        elif funding_zscore < -2.0:
            funding_bias = FundingBias.EXTREME_NEGATIVE
        elif funding_zscore < -0.5:
            funding_bias = FundingBias.NEGATIVE
        else:
            funding_bias = FundingBias.NEUTRAL

        derivatives = DerivativesContext(
            oi=OIData(
                value=np.random.uniform(1500000, 6000000),
                delta=np.random.uniform(-150000, 150000),
                zscore=oi_zscore,
            ),
            funding=FundingData(
                rate=np.random.uniform(-0.012, 0.012),
                zscore=funding_zscore,
                bias=funding_bias,
            ),
            liquidation=LiquidationData(
                long=np.random.uniform(0, 150000),
                short=np.random.uniform(0, 150000),
                total=np.random.uniform(0, 300000),
                long_zscore=np.random.uniform(-3.5, 3.5),
                short_zscore=np.random.uniform(-3.5, 3.5),
                reversal_signal=np.random.random() < 0.1,
            ),
        )

        ctx = MarketContext(
            symbol="BTCUSDT",
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )

        market_contexts.append(ctx)

    return market_contexts, timestamps, np.array(prices)
