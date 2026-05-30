"""
Alpha Return Matrix Builder

提取所有 Alpha 策略的真实逐笔收益序列，构建统一的时间对齐收益矩阵。

核心逻辑：
  1. 遍历 AlphaRegistry 中所有 active 策略
  2. 对每个策略运行信号回测，提取逐笔 (entry_bar, return) 序列
  3. 将逐笔收益映射到 entry bar 的 timestamp 上
  4. 对齐所有策略到统一时间轴，缺失值填 0

输出：
  DataFrame: index=timestamp, columns=alpha_name, values=per-bar return
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from infrastructure.logging import get_logger
from research.alpha.registry.alpha_registry import AlphaRegistry, AlphaDefinition
from research.alpha.signals.funding_regime_signal import run_signal_test

logger = get_logger("research.alpha.correlation.return_matrix")


def _extract_trade_returns(
    close: np.ndarray,
    feature_vals: np.ndarray,
    regime_labels: np.ndarray,
    feature_threshold: float,
    holding_bars: int,
    direction: str,
    taker_fee: float = 0.0005,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    提取逐笔交易的 (entry_bar_index, return) 序列。

    Returns:
        entry_indices: 逐笔入场的 bar index
        trade_returns: 逐笔扣费后收益
    """
    n = len(close)
    max_exit = n - holding_bars

    feat_valid = ~np.isnan(feature_vals)

    if direction == "short":
        signal_mask = feat_valid & (feature_vals > feature_threshold)
    else:
        signal_mask = feat_valid & (feature_vals < -feature_threshold)

    valid_idx = np.where(signal_mask[:max_exit])[0]

    if len(valid_idx) == 0:
        return np.array([], dtype=int), np.array([], dtype=float)

    entry_prices = close[valid_idx]
    exit_prices = close[valid_idx + holding_bars]

    if direction == "short":
        raw_ret = -(exit_prices - entry_prices) / entry_prices
    else:
        raw_ret = (exit_prices - entry_prices) / entry_prices

    fee = 2.0 * taker_fee
    rets = raw_ret - fee

    return valid_idx, rets


def _compute_threshold_for_alpha(
    feature_vals: np.ndarray,
    direction: str,
    percentile: float = 90.0,
) -> float:
    valid = feature_vals[~np.isnan(feature_vals)]
    if len(valid) == 0:
        return 0.0
    return float(np.nanpercentile(np.abs(valid), percentile))


class AlphaReturnMatrixBuilder:
    def __init__(
        self,
        symbol: str,
        exchange: str = "binance",
        timeframe: str = "1h",
        days: int = 365,
        holding_bars: int = 20,
        percentile: float = 90.0,
        taker_fee: float = 0.0004,
        feature_source: str = "engine_standalone",
    ):
        self.symbol = symbol
        self.exchange = exchange
        self.timeframe = timeframe
        self.days = days
        self.holding_bars = holding_bars
        self.percentile = percentile
        self.taker_fee = taker_fee
        self.feature_source = feature_source

    def build(self, alpha_names: Optional[List[str]] = None) -> pd.DataFrame:
        fm = self._load_feature_matrix()
        close = fm["close"].values.astype(float)
        regime_labels = fm.get("trend_regime", pd.Series(["unknown"] * len(fm))).values

        if "timestamp" in fm.columns:
            timestamps = pd.to_datetime(fm["timestamp"])
        else:
            timestamps = pd.date_range(
                end=pd.Timestamp.now(),
                periods=len(fm),
                freq=self.timeframe,
            )

        definitions = self._get_alpha_definitions(alpha_names)

        all_series: Dict[str, pd.Series] = {}

        for defn in definitions:
            try:
                series = self._build_single_series(
                    defn, fm, close, regime_labels, timestamps
                )
                if series is not None and len(series) > 0:
                    all_series[defn.name] = series
                    logger.info(
                        f"{defn.name}: {len(series)} trades, "
                        f"mean_ret={series.mean():.5f}"
                    )
            except Exception as e:
                logger.warning(f"Failed for {defn.name}: {e}")

        if not all_series:
            return pd.DataFrame()

        df = pd.DataFrame(all_series)
        df = df.reindex(timestamps)
        df = df.fillna(0.0)
        df.index.name = "timestamp"

        return df

    def _load_feature_matrix(self) -> pd.DataFrame:
        from research.alpha.features.matrix_adapter import get_research_feature_matrix
        from research.alpha.regime_analysis import classify_regime

        fm = get_research_feature_matrix(
            symbol=self.symbol,
            exchange=self.exchange,
            days=self.days,
            timeframe=self.timeframe,
            feature_source=self.feature_source,
        )
        fm = classify_regime(fm)
        return fm

    def _get_alpha_definitions(
        self, alpha_names: Optional[List[str]]
    ) -> List[AlphaDefinition]:
        if alpha_names:
            return [AlphaRegistry.get(n) for n in alpha_names]
        return AlphaRegistry.get_active()

    def _build_single_series(
        self,
        defn: AlphaDefinition,
        fm: pd.DataFrame,
        close: np.ndarray,
        regime_labels: np.ndarray,
        timestamps: pd.DatetimeIndex,
    ) -> Optional[pd.Series]:
        feature_name = defn.primary_feature
        if not feature_name or feature_name not in fm.columns:
            logger.warning(f"{defn.name}: feature '{feature_name}' not in fm")
            return None

        feature_vals = fm[feature_name].values.astype(float)

        if defn.combo_logic == "all_must_trigger" and len(defn.features) > 1:
            feature_vals = self._apply_combo_mask(fm, defn, feature_vals)

        threshold = self._compute_threshold(feature_vals, defn.direction)

        entry_indices, trade_returns = _extract_trade_returns(
            close=close,
            feature_vals=feature_vals,
            regime_labels=regime_labels,
            feature_threshold=threshold,
            holding_bars=self.holding_bars,
            direction=defn.direction,
            taker_fee=self.taker_fee,
        )

        if len(entry_indices) == 0:
            return None

        entry_timestamps = timestamps[entry_indices]
        series = pd.Series(trade_returns, index=entry_timestamps, name=defn.name)

        return series

    def _compute_threshold(self, feature_vals: np.ndarray, direction: str) -> float:
        return _compute_threshold_for_alpha(
            feature_vals, direction, self.percentile
        )

    def _apply_combo_mask(
        self,
        fm: pd.DataFrame,
        defn: AlphaDefinition,
        primary_vals: np.ndarray,
    ) -> np.ndarray:
        mask = pd.Series(True, index=fm.index)
        for feat_name, direction in defn.signal_direction_map.items():
            if feat_name == defn.primary_feature:
                continue
            if feat_name not in fm.columns:
                continue
            feat_vals = fm[feat_name]
            if "negative" in direction:
                threshold = feat_vals.quantile(0.05)
                mask &= (feat_vals < threshold)
            elif "positive" in direction:
                threshold = feat_vals.quantile(0.95)
                mask &= (feat_vals > threshold)

        result = primary_vals.copy()
        result[~mask.values] = np.nan
        return result
