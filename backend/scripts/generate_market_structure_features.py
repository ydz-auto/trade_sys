#!/usr/bin/env python3
"""
市场结构特征 (Market Structure Features)

实现：
1. Rolling High/Low（滚动高低价）
2. Distance to Resistance/Support（距离压力/支撑位）
3. Spike Event Detection（暴涨暴跌事件）
4. Follow-through Return（后续收益）
5. Mean Reversion（均值回归）
6. Trend Classification（趋势分类）
7. State Classification（市场状态分类）
8. Contextual Features（上下文特征）
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd
import numpy as np


def add_market_structure_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    添加市场结构特征
    
    这比RSI、MACD更高级，因为：
    - 描述市场行为模式
    - 包含上下文信息
    - 支持事件分析
    """
    df = df.copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # 确保数值列
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # ========== 1. Rolling High / Low ==========
    print("  📊 计算 Rolling High/Low...")
    
    for window in [24, 72, 168]:  # 24h, 3d, 7d
        df[f"rolling_high_{window}h"] = df["high"].rolling(window=window).max()
        df[f"rolling_low_{window}h"] = df["low"].rolling(window=window).min()
        df[f"rolling_range_{window}h"] = df[f"rolling_high_{window}h"] - df[f"rolling_low_{window}h"]
    
    # ========== 2. Distance to Resistance / Support ==========
    print("  📊 计算 Distance to Resistance/Support...")
    
    for window in [24, 72]:
        # 距离阻力位（滚动高点）的百分比
        df[f"dist_to_resistance_{window}h"] = (df["close"] - df[f"rolling_high_{window}h"]) / df["close"]
        
        # 距离支撑位（滚动低点）的百分比
        df[f"dist_to_support_{window}h"] = (df["close"] - df[f"rolling_low_{window}h"]) / df["close"]
        
        # 在区间中的位置（0=底部，1=顶部）
        range_val = df[f"rolling_range_{window}h"]
        df[f"position_in_range_{window}h"] = np.where(
            range_val > 0,
            (df["close"] - df[f"rolling_low_{window}h"]) / range_val,
            0.5
        )
    
    # ========== 3. Breakout Detection ==========
    print("  📊 计算 Breakout Detection...")
    
    for window in [24, 72]:
        # 突破rolling high
        df[f"breakout_high_{window}h"] = df["high"] > df[f"rolling_high_{window}h"].shift(1)
        
        # 突破rolling low
        df[f"breakout_low_{window}h"] = df["low"] < df[f"rolling_low_{window}h"].shift(1)
        
        # 突破幅度（价格突破rolling high多少%）
        df[f"breakout_strength_{window}h"] = np.where(
            df[f"breakout_high_{window}h"],
            (df["high"] - df[f"rolling_high_{window}h"].shift(1)) / df[f"rolling_high_{window}h"].shift(1),
            0
        )
    
    # ========== 4. Spike Event Detection ==========
    print("  📊 计算 Spike Event Detection...")
    
    # 计算5分钟收益
    df["return_5m"] = df["close"].pct_change(5)
    
    # 定义spike阈值
    SPIKE_THRESHOLD = 0.03  # 3%
    MAJOR_SPIKE_THRESHOLD = 0.05  # 5%
    
    # Spike事件标记
    df["spike_up"] = df["return_5m"] > SPIKE_THRESHOLD
    df["spike_down"] = df["return_5m"] < -SPIKE_THRESHOLD
    df["major_spike_up"] = df["return_5m"] > MAJOR_SPIKE_THRESHOLD
    df["major_spike_down"] = df["return_5m"] < -MAJOR_SPIKE_THRESHOLD
    
    # Spike强度
    df["spike_strength"] = df["return_5m"].clip(-0.1, 0.1)
    
    # ========== 5. Follow-through Return（后续收益） ==========
    print("  📊 计算 Follow-through Return...")
    
    # Spike后5分钟收益
    df["follow_through_5m"] = df["return_5m"].shift(-5)  # 当前spike后5m的收益
    df["follow_through_15m"] = df["close"].pct_change(20).shift(-20)  # 15m后的收益
    df["follow_through_1h"] = df["close"].pct_change(60).shift(-60)  # 1h后的收益
    
    # Spike持续时间（价格维持高位的时间）
    for window in [12, 24, 60]:  # 1h, 2h, 5h
        df[f"spike_persistence_{window//60}h"] = (
            (df["close"] > df["close"].rolling(window).mean() * 1.01).rolling(window).sum()
        ) / window
    
    # ========== 6. Mean Reversion Strength ==========
    print("  📊 计算 Mean Reversion Strength...")
    
    # Spike后的回撤比例
    for lookback in [12, 24, 60]:  # 1h, 2h, 5h
        future_max = df["close"].rolling(window=lookback).max().shift(-lookback)
        future_min = df["close"].rolling(window=lookback).min().shift(-lookback)
        
        # 回撤强度 = (峰值 - 当前) / spike幅度
        spike_peak = df["close"] * (1 + df["return_5m"].clip(0, 1))
        df[f"mean_reversion_{lookback//60}h"] = (spike_peak - future_max) / (spike_peak + 1)
    
    # 距离均值的百分比
    for window in [20, 60]:
        df[f"price_vs_ma_{window}"] = (df["close"] - df["close"].rolling(window).mean()) / df["close"]
    
    # ========== 7. Trend Classification ==========
    print("  📊 计算 Trend Classification...")
    
    # 趋势方向
    for window in [12, 24, 60]:
        df[f"trend_direction_{window}h"] = np.sign(df["close"].diff(window))
    
    # 趋势强度
    for window in [12, 24, 60]:
        df[f"trend_strength_{window}h"] = (
            df["close"] / df["close"].shift(window) - 1
        ).clip(-0.5, 0.5)
    
    # 趋势持续时间（连续同向移动的bar数）
    df["trend_bars_up"] = (df["close"] > df["close"].shift(1)).astype(int)
    df["trend_bars_down"] = (df["close"] < df["close"].shift(1)).astype(int)
    
    # 趋势加速度（变化率的二阶导）
    returns = df["close"].pct_change()
    df["trend_acceleration"] = returns.diff()
    
    # ========== 8. Market State Classification ==========
    print("  📊 计算 Market State Classification...")
    
    # 计算市场状态的各个维度
    rsi = df["rsi_14"].fillna(50)
    returns_1h = df.get("returns_1h", df["close"].pct_change(60)).fillna(0)
    volatility = df.get("volatility_1h", df["close"].pct_change().rolling(60).std()).fillna(0)
    volume_ratio = df.get("volume_ratio", df["volume"] / df["volume"].rolling(20).mean()).fillna(1)
    
    # Squeeze状态：价格涨 + OI涨 + volatility低
    oi_change = df.get("oi_change_1h", 0).fillna(0)
    df["state_squeeze"] = (
        (returns_1h > 0) & 
        (oi_change > 0) & 
        (volatility < volatility.rolling(168).mean())
    ).astype(int)
    
    # Panic Dump状态：价格跌 + volume放大
    df["state_panic_dump"] = (
        (returns_1h < -0.01) & 
        (volume_ratio > 2)
    ).astype(int)
    
    # Breakout状态：突破 + volume放大
    df["state_breakout"] = (
        (df.get("breakout_high_24h", False)) & 
        (volume_ratio > 1.5)
    ).astype(int)
    
    # Accumulation状态：价格在区间内 + volume稳定 + funding低
    funding_rate = df.get("funding_rate", 0).fillna(0)
    position_in_range = df.get("position_in_range_24h", 0.5)
    df["state_accumulation"] = (
        (position_in_range > 0.3) & 
        (position_in_range < 0.7) &
        (volume_ratio < 1.3) &
        (funding_rate.abs() < 0.001)
    ).astype(int)
    
    # ========== 9. Contextual Features ==========
    print("  📊 计算 Contextual Features...")
    
    # 突破前市场状态（Context）
    for window in [24, 72]:
        df[f"volume_before_breakout_{window}h"] = df["volume"].rolling(window).mean()
        df[f"volatility_before_breakout_{window}h"] = df["close"].pct_change().rolling(window).std()
    
    # 压力支撑重叠区域
    df["resistance_support_overlap"] = (
        df["rolling_high_24h"] - df["rolling_low_24h"]
    ) / df["close"] < 0.02  # 区间很窄
    
    # 趋势+背离（高级特征）
    if "rsi_14" in df.columns:
        df["price_rsi_divergence"] = np.where(
            (df["close"] > df["close"].shift(24)) & (rsi < 50), -1,
            np.where(
                (df["close"] < df["close"].shift(24)) & (rsi > 50), 1,
                0
            )
        )
    
    # ========== 10. Advanced State Features ==========
    print("  📊 计算 Advanced State Features...")
    
    # Trend Exhaustion（趋势衰竭）
    if all(col in df.columns for col in ["rsi_14", "funding_rate"]):
        df["trend_exhaustion"] = (
            (rsi > 75) & (df["funding_rate"] > 0.001) & (volatility > volatility.rolling(168).mean())
        ).astype(int)
        
        df["trend_healthy"] = (
            (rsi < 70) & (df["funding_rate"].abs() < 0.0005) & (volatility < volatility.rolling(168).mean())
        ).astype(int)
    
    # Momentum转换
    df["momentum_shift"] = np.sign(df["close"].diff(12) - df["close"].diff(24))
    
    # 波动率异常
    df["volatility_surge"] = volatility > volatility.rolling(168).mean() * 2
    
    print(f"  ✅ 市场结构特征计算完成！共 {len([c for c in df.columns if c.startswith(('rolling', 'dist', 'breakout', 'spike', 'state', 'trend', 'follow'))])} 个特征")
    
    return df


def analyze_spike_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    事件窗口分析 (Event Study)
    
    对所有spike事件，统计后续收益
    """
    df = df.copy()
    
    # 找出所有spike事件
    spike_events = df[df["spike_up"] == True].copy()
    
    if len(spike_events) == 0:
        print("  ⚠️ 没有找到spike事件")
        return df
    
    print(f"  📊 找到 {len(spike_events)} 个spike事件")
    
    # 计算spike事件后的平均收益
    for lookforward in [5, 15, 60]:
        col_name = f"spike_avg_return_{lookforward}m"
        
        # 每个spike事件后N分钟的收益
        spike_events[col_name] = spike_events["close"].pct_change(lookforward).shift(-lookforward)
    
    # 全局统计
    for col in ["spike_avg_return_5m", "spike_avg_return_15m", "spike_avg_return_60m"]:
        if col in spike_events.columns:
            mean_ret = spike_events[col].mean()
            print(f"    Spike后5分钟平均收益: {mean_ret*100:.2f}%")
    
    return df


def classify_market_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    市场状态分类 (Market Regime Classification)
    
    分类：
    - Trending Up: 强势上涨
    - Trending Down: 强势下跌
    - Ranging: 区间震荡
    - Volatile: 高波动
    """
    df = df.copy()
    
    # 计算regime指标
    returns = df["close"].pct_change()
    volatility = returns.rolling(24).std()
    trend = df["close"] / df["close"].rolling(24).mean() - 1
    
    # 分类
    df["regime"] = "ranging"  # 默认区间
    
    # Trending Up: 趋势明显向上
    df.loc[(trend > 0.02) & (returns > 0), "regime"] = "trending_up"
    
    # Trending Down: 趋势明显向下
    df.loc[(trend < -0.02) & (returns < 0), "regime"] = "trending_down"
    
    # Volatile: 波动率很高
    df.loc[volatility > volatility.quantile(0.9), "regime"] = "volatile"
    
    # Regime编码
    regime_map = {
        "trending_up": 1,
        "trending_down": -1,
        "volatile": 2,
        "ranging": 0
    }
    df["regime_code"] = df["regime"].map(regime_map)
    
    print(f"  📊 Regime分布:")
    print(df["regime"].value_counts())
    
    return df


if __name__ == "__main__":
    # 测试
    from pathlib import Path
    
    data_path = Path("data_lake/features/binance/BTCUSDT/features.parquet")
    df = pd.read_parquet(data_path)
    
    print("="*70)
    print("市场结构特征工程")
    print("="*70)
    
    # 添加市场结构特征
    df = add_market_structure_features(df)
    
    # 事件分析
    df = analyze_spike_events(df)
    
    # Regime分类
    df = classify_market_regime(df)
    
    # 保存
    output_path = data_path.parent / "features_with_structure.parquet"
    df.to_parquet(output_path, compression="zstd", index=False)
    
    print(f"\n✅ 已保存到: {output_path}")
    print(f"   总列数: {len(df.columns)}")
