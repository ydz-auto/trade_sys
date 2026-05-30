"""
Regime Analysis - 市场环境分类

基于趋势和波动率对每个 bar 分类市场环境。

用途：在 IC 分析中按 regime 分组，看 feature 在不同市场下的预测力。
"""

import numpy as np
import pandas as pd


def classify_regime(
    feature_matrix: pd.DataFrame,
    trend_col: str = "trend_20",
    vol_short_col: str = "vol_20",
    vol_long_col: str = "vol_60",
    trend_threshold: float = 0.01,
    vol_ratio_high: float = 1.2,
    vol_ratio_low: float = 0.8,
) -> pd.DataFrame:
    """
    对 feature_matrix 追加 trend_regime 和 vol_regime 列。
    
    trend_regime:
    - trend_up:   trend_20 > threshold
    - trend_down: trend_20 < -threshold
    - range:      其他
    
    vol_regime:
    - high_vol: vol_20 > vol_60 * vol_ratio_high
    - low_vol:  vol_20 < vol_60 * vol_ratio_low
    - normal:   其他
    
    Args:
        feature_matrix: 特征矩阵（需包含 trend_col, vol_short_col, vol_long_col）
        trend_col: 趋势列名
        vol_short_col: 短期波动列名
        vol_long_col: 长期波动列名
        trend_threshold: 趋势判定阈值
        vol_ratio_high: 高波动比率
        vol_ratio_low: 低波动比率
    
    Returns:
        追加了 trend_regime, vol_regime 列的 DataFrame（原 df 的副本）
    """
    df = feature_matrix.copy()
    
    # Trend regime - 更健壮的处理
    if trend_col in df.columns:
        trend = df[trend_col]
        df["trend_regime"] = np.where(
            trend > trend_threshold, "trend_up",
            np.where(trend < -trend_threshold, "trend_down", "range")
        )
    else:
        # 如果没有趋势特征，默认为 range
        df["trend_regime"] = "range"
        print(f"[Regime] 警告: 列 {trend_col} 不存在，默认所有为 range")
    
    # Vol regime - 更健壮的处理
    if vol_short_col in df.columns and vol_long_col in df.columns:
        vol_short = df[vol_short_col]
        vol_long = df[vol_long_col]
        df["vol_regime"] = np.where(
            vol_short > vol_long * vol_ratio_high, "high_vol",
            np.where(vol_short < vol_long * vol_ratio_low, "low_vol", "normal")
        )
    else:
        # 如果没有波动率特征，默认为 normal
        df["vol_regime"] = "normal"
        missing = []
        if vol_short_col not in df.columns:
            missing.append(vol_short_col)
        if vol_long_col not in df.columns:
            missing.append(vol_long_col)
        print(f"[Regime] 警告: 列 {', '.join(missing)} 不存在，默认所有为 normal")
    
    return df


def regime_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    统计各 regime 的样本数和占比。

    Args:
        df: 包含 trend_regime, vol_regime 列的 DataFrame

    Returns:
        汇总 DataFrame
    """
    rows = []
    for col in ["trend_regime", "vol_regime"]:
        if col not in df.columns:
            continue
        counts = df[col].value_counts()
        total = len(df)
        for regime, count in counts.items():
            rows.append({
                "regime_type": col,
                "regime": regime,
                "count": count,
                "pct": count / total,
            })
    return pd.DataFrame(rows)


__all__ = ["classify_regime", "regime_summary"]
