"""
Alpha Signal Strategy - Feature-level 到 Strategy-level 的桥接层

三个组件：
A. AlphaSignalStrategy: 将 feature rule 包装为 StrategyV2
B. build_market_contexts_from_fm(): 从 feature matrix 构建 MarketContext
C. run_feature_walk_forward(): 轻量级 walk-forward（复用 funding_regime_signal.run_signal_test）
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engines.compute.context.schema import (
    MarketContext,
    TimeframeContext,
    PriceState,
    TrendStateData,
    TrendState,
    VolatilityStateData,
    VolatilityState,
    VolumeStateData,
    FundingBias,
    FundingData,
    DerivativesContext,
    RiskContext,
)
from engines.compute.strategy_v2.base import StrategyV2, Signal, SignalType
from engines.compute.strategy_v2.metadata import StrategyMeta
from research.alpha.funding_regime_signal import run_signal_test


class AlphaSignalStrategy(StrategyV2):
    meta = StrategyMeta(
        name="alpha_signal",
        primary_tf="1h",
        tags={"alpha_research"},
    )

    def __init__(
        self,
        symbol: str,
        feature_name: str,
        threshold: float,
        direction: str = "long",
        holding_bars: int = 5,
    ):
        self.feature_name = feature_name
        self.threshold = threshold
        self.direction = direction
        self._holding_bars = holding_bars
        object.__setattr__(
            self,
            "meta",
            StrategyMeta(
                name=f"alpha_{feature_name}_{direction}",
                primary_tf="1h",
                tags={"alpha_research"},
            ),
        )
        super().__init__(symbol=symbol)

    def generate_signal(self, ctx: MarketContext) -> Signal:
        if ctx.raw_features is None:
            return Signal.none(reason="no_raw_features")
        if self.feature_name not in ctx.raw_features:
            return Signal.none(reason=f"missing_{self.feature_name}")

        value = ctx.raw_features[self.feature_name]
        if np.isnan(value):
            return Signal.none(reason="nan_feature")

        if self.direction in ("long", "both"):
            if value < -self.threshold:
                conf = min(1.0, abs(value) / (self.threshold * 3))
                return Signal.long(confidence=conf, reason=f"{self.feature_name}<{ -self.threshold:.4f}")

        if self.direction in ("short", "both"):
            if value > self.threshold:
                conf = min(1.0, abs(value) / (self.threshold * 3))
                return Signal.short(confidence=conf, reason=f"{self.feature_name}>{self.threshold:.4f}")

        return Signal.none(reason="no_trigger")

    def get_holding_bars(self) -> int:
        return self._holding_bars


def build_market_contexts_from_fm(
    fm: pd.DataFrame,
    symbol: str,
    timeframe: str = "1h",
) -> Tuple[List[MarketContext], List[int], np.ndarray]:
    contexts = []
    timestamps_ms = []
    prices = []

    feature_cols = [
        c for c in fm.columns
        if c not in ("timestamp", "open", "high", "low", "close", "volume",
                     "trend_regime", "vol_regime")
    ]

    for idx in range(len(fm)):
        row = fm.iloc[idx]

        ts = int(row.get("timestamp", 0))
        if isinstance(ts, (pd.Timestamp, np.datetime64)):
            ts = int(pd.Timestamp(ts).value / 1_000_000)
        timestamps_ms.append(ts)

        close = float(row.get("close", 0.0))
        prices.append(close)

        raw_features = {}
        for col in feature_cols:
            val = row.get(col, np.nan)
            raw_features[col] = float(val) if pd.notna(val) else np.nan

        trend_20 = raw_features.get("trend_20", 0.0)
        if np.isnan(trend_20):
            trend_20 = 0.0
        if trend_20 > 0.01:
            trend_state = TrendState.STRONG_UP
        elif trend_20 > 0.003:
            trend_state = TrendState.WEAK_UP
        elif trend_20 < -0.01:
            trend_state = TrendState.STRONG_DOWN
        elif trend_20 < -0.003:
            trend_state = TrendState.WEAK_DOWN
        else:
            trend_state = TrendState.SIDEWAYS

        vol_20 = raw_features.get("vol_20", 0.0)
        vol_60 = raw_features.get("vol_60", 0.0)
        if not np.isnan(vol_20) and not np.isnan(vol_60) and vol_60 > 0:
            vol_ratio = vol_20 / vol_60
        else:
            vol_ratio = 1.0
        if vol_ratio > 1.2:
            vol_state = VolatilityState.ELEVATED
        elif vol_ratio < 0.8:
            vol_state = VolatilityState.LOW
        else:
            vol_state = VolatilityState.NORMAL

        funding_zscore = raw_features.get("funding_zscore", 0.0)
        if np.isnan(funding_zscore):
            funding_zscore = 0.0
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

        tf_ctx = TimeframeContext(
            timeframe=timeframe,
            price=PriceState(
                open=float(row.get("open", close)),
                high=float(row.get("high", close)),
                low=float(row.get("low", close)),
                close=close,
            ),
            trend=TrendStateData(state=trend_state, slope=trend_20),
            volatility=VolatilityStateData(state=vol_state, realized_vol=vol_20),
            volume=VolumeStateData(volume_zscore=raw_features.get("volume_zscore", 0.0)),
        )

        derivatives = DerivativesContext(
            funding=FundingData(
                rate=raw_features.get("funding_rate", 0.0),
                zscore=funding_zscore,
                bias=funding_bias,
            ),
        )

        ctx = MarketContext(
            symbol=symbol,
            timestamp=ts,
            tf={timeframe: tf_ctx},
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
            raw_features=raw_features,
        )
        contexts.append(ctx)

    return contexts, timestamps_ms, np.array(prices)


@dataclass
class WalkForwardWindowResult:
    window_idx: int
    test_start: int
    test_end: int
    trades: int
    win_rate: float
    avg_ret: float
    total_ret: float
    sharpe: float
    profit_factor: float


@dataclass
class WalkForwardFeatureResult:
    total_windows: int
    train_bars: int
    test_bars: int
    window_results: List[WalkForwardWindowResult]
    avg_return: float
    avg_sharpe: float
    win_rate_consistency: float
    profit_factor: float


def run_feature_walk_forward(
    close: np.ndarray,
    feature_vals: np.ndarray,
    regime_labels: np.ndarray,
    threshold: float,
    holding_bars: int,
    direction: str,
    taker_fee: float = 0.0005,
    train_bars: int = 720,
    test_bars: int = 168,
    gap_bars: int = 0,
    use_train_only_threshold: bool = True,
    percentile: float = 90.0,
) -> WalkForwardFeatureResult:
    """
    Walk-forward validation for feature signals.
    
    IMPORTANT: To avoid leakage, thresholds should be computed from TRAIN set only!
    """
    n = len(close)
    window_results = []
    idx = 0
    window_idx = 0

    while idx + train_bars + gap_bars + test_bars <= n:
        train_end = idx + train_bars
        test_start = train_end + gap_bars
        test_end = test_start + test_bars

        # Get TRAIN data for threshold calculation
        train_feature = feature_vals[idx:train_end]
        
        # Get TEST data
        test_close = close[test_start:test_end]
        test_feature = feature_vals[test_start:test_end]
        test_regime = regime_labels[test_start:test_end]

        # Calculate threshold from TRAIN set only if enabled
        window_threshold = threshold
        if use_train_only_threshold and len(train_feature) > 0:
            valid_train = train_feature[~np.isnan(train_feature)]
            if len(valid_train) > 0:
                if direction == "long":
                    # For long, we use lower tail (negative side)
                    window_threshold = float(np.nanpercentile(np.abs(valid_train), percentile))
                elif direction == "short":
                    # For short, we use upper tail
                    window_threshold = float(np.nanpercentile(np.abs(valid_train), percentile))
                else:  # both
                    window_threshold = float(np.nanpercentile(np.abs(valid_train), percentile))

        result = run_signal_test(
            close=test_close,
            feature_vals=test_feature,
            regime_labels=test_regime,
            feature_threshold=window_threshold,
            holding_bars=holding_bars,
            direction=direction,
            taker_fee=taker_fee,
        )

        window_results.append(WalkForwardWindowResult(
            window_idx=window_idx,
            test_start=test_start,
            test_end=test_end,
            trades=result.get("trades", 0),
            win_rate=result.get("win_rate", 0.0),
            avg_ret=result.get("avg_ret", 0.0),
            total_ret=result.get("total_ret", 0.0),
            sharpe=result.get("sharpe", 0.0),
            profit_factor=result.get("profit_factor", 0.0),
        ))

        idx += test_bars
        window_idx += 1

    if not window_results:
        return WalkForwardFeatureResult(
            total_windows=0,
            train_bars=train_bars,
            test_bars=test_bars,
            window_results=[],
            avg_return=0.0,
            avg_sharpe=0.0,
            win_rate_consistency=0.0,
            profit_factor=0.0,
        )

    all_rets = []
    for wr in window_results:
        if wr.trades > 0:
            all_rets.extend([wr.avg_ret] * wr.trades)

    active_windows = [wr for wr in window_results if wr.trades > 0]
    avg_return = float(np.mean([wr.avg_ret for wr in active_windows])) if active_windows else 0.0
    avg_sharpe = float(np.mean([wr.sharpe for wr in active_windows])) if active_windows else 0.0

    win_rates = [wr.win_rate for wr in active_windows]
    win_rate_consistency = 1.0 - float(np.std(win_rates)) if len(win_rates) > 1 else (win_rates[0] if win_rates else 0.0)

    if all_rets:
        wins = [r for r in all_rets if r > 0]
        losses = [r for r in all_rets if r < 0]
        pf = sum(wins) / abs(sum(losses)) if losses else float("inf")
    else:
        pf = 0.0

    return WalkForwardFeatureResult(
        total_windows=len(window_results),
        train_bars=train_bars,
        test_bars=test_bars,
        window_results=window_results,
        avg_return=avg_return,
        avg_sharpe=avg_sharpe,
        win_rate_consistency=win_rate_consistency,
        profit_factor=pf,
    )
