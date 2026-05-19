#!/usr/bin/env python3
"""
分析5分钟数据中各策略的最大有利波动分布
用P90来设定更合理的止盈起点
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import pandas as pd
import numpy as np
import pyarrow.parquet as pq
import gc

# ============================================================
# 加载数据
# ============================================================

data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
print("📥 加载1分钟数据...")
usecols = ["timestamp", "open", "high", "low", "close", "volume"]
df_1m = pd.read_parquet(data_path, columns=usecols)
df_1m = df_1m.sort_values("timestamp").reset_index(drop=True)
print(f"   1分钟数据: {len(df_1m)} 行")

# 聚合5分钟
print("⏳ 聚合5分钟数据...")
df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
df_1m.set_index('timestamp', inplace=True)
df_5m = df_1m.resample('5min').agg({
    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
}).dropna().reset_index()
del df_1m
gc.collect()
print(f"   5分钟数据: {len(df_5m)} 行")

# ============================================================
# 计算基础特征
# ============================================================

closes = df_5m['close'].values
volumes = df_5m['volume'].values

# 收益率
df_5m['return_5m'] = closes / np.roll(closes, 1) - 1
df_5m['return_1h'] = closes / np.roll(closes, 12) - 1

# 成交量比率
vol_ma = pd.Series(volumes).rolling(288, min_periods=1).mean().values
df_5m['volume_ratio'] = volumes / (vol_ma + 1e-10)

# RSI
def calc_rsi(prices, period=14):
    rsi = np.full_like(prices, 50.0)
    deltas = np.diff(prices)
    for i in range(period + 1, len(prices)):
        window = deltas[i-period:i]
        gains = window[window > 0]
        losses = -window[window < 0]
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    return rsi

def calc_ema(prices, period):
    ema = np.zeros_like(prices)
    ema[0] = prices[0]
    k = 2 / (period + 1)
    for i in range(1, len(prices)):
        ema[i] = ema[i-1] * (1 - k) + prices[i] * k
    return ema

def calc_sma(prices, period):
    sma = np.zeros_like(prices)
    for i in range(period, len(prices)):
        sma[i] = np.mean(prices[i-period:i])
    return sma

def calc_bollinger(prices, period, std_dev):
    middle = calc_sma(prices, period)
    upper = np.zeros_like(prices)
    lower = np.zeros_like(prices)
    for i in range(period, len(prices)):
        std = np.std(prices[i-period:i])
        upper[i] = middle[i] + std_dev * std
        lower[i] = middle[i] - std_dev * std
    return {'upper': upper, 'lower': lower, 'middle': middle}

df_5m['rsi'] = calc_rsi(closes, 14)
ema_fast = calc_ema(closes, 12)
ema_slow = calc_ema(closes, 26)
df_5m['macd_line'] = ema_fast - ema_slow
df_5m['macd_signal'] = calc_ema(ema_fast - ema_slow, 9)
df_5m['ema_20'] = calc_ema(closes, 20)
df_5m['ema_50'] = calc_ema(closes, 50)
bb = calc_bollinger(closes, 20, 2.0)
df_5m['bb_upper'] = bb['upper']
df_5m['bb_lower'] = bb['lower']
df_5m['sma_50'] = calc_sma(closes, 50)
df_5m['sma_200'] = calc_sma(closes, 200)
df_5m['volatility_1h'] = pd.Series(df_5m['return_5m']).rolling(12).std().values

highs = df_5m['high'].values
lows = df_5m['low'].values
candle_range = highs - lows + 1e-10
df_5m['upper_wick_ratio'] = (highs - np.maximum(closes, np.roll(closes, 1))) / candle_range
df_5m['lower_wick_ratio'] = (np.minimum(closes, np.roll(closes, 1)) - lows) / candle_range
df_5m = df_5m.fillna(0)

print("✅ 特征计算完成")

# ============================================================
# 策略信号检测 + 最大有利波动追踪
# ============================================================

def track_max_favorable(df, detect_fn, direction_fn, max_hold=576, cooldown=6):
    """
    追踪每次信号后的最大有利波动
    返回: list of max_favorable_points
    """
    results = []
    n = len(df)
    last_signal = -999
    i = 288
    
    while i < n:
        if i - last_signal < cooldown:
            i += 1
            continue
        
        triggered = detect_fn(df, i)
        if not triggered:
            i += 1
            continue
        
        last_signal = i
        entry_price = df['close'].iloc[i]
        direction = direction_fn(df, i)
        
        max_fav = 0.0
        j = i + 1
        
        while j < n and (j - i) < max_hold:
            h = df['high'].iloc[j]
            l = df['low'].iloc[j]
            
            if direction == "long":
                fav = h - entry_price
            else:
                fav = entry_price - l
            
            if fav > max_fav:
                max_fav = fav
            j += 1
        
        results.append(max_fav)
        i = j + 1  # 跳到这笔交易结束后
    
    return results


# 策略检测函数
strategies = {}

# BTC Swing
strategies["BTC Swing"] = {
    "detect": lambda df, i: (
        i >= 50 and
        df['rsi'].iloc[i] <= 30 and
        df['macd_line'].iloc[i-1] <= df['macd_signal'].iloc[i-1] and
        df['macd_line'].iloc[i] > df['macd_signal'].iloc[i]
    ),
    "direction": lambda df, i: "long",
}

# Bollinger Bands
def bb_detect(df, i):
    if i < 20: return False
    price = df['close'].iloc[i]
    prev_price = df['close'].iloc[i-1]
    return (prev_price >= df['bb_lower'].iloc[i-1] and price < df['bb_lower'].iloc[i]) or \
           (prev_price <= df['bb_upper'].iloc[i-1] and price > df['bb_upper'].iloc[i])

def bb_dir(df, i):
    if df['close'].iloc[i] < df['bb_lower'].iloc[i]: return "long"
    return "short"

strategies["Bollinger Bands"] = {"detect": bb_detect, "direction": bb_dir}

# MA Cross
def ma_detect(df, i):
    if i < 200: return False
    fast = df['sma_50'].iloc[i]; slow = df['sma_200'].iloc[i]
    pf = df['sma_50'].iloc[i-1]; ps = df['sma_200'].iloc[i-1]
    return (pf <= ps and fast > slow) or (pf >= ps and fast < slow)

def ma_dir(df, i):
    if df['sma_50'].iloc[i] > df['sma_200'].iloc[i]: return "long"
    return "short"

strategies["MA Cross"] = {"detect": ma_detect, "direction": ma_dir}

# RSI+MACD
def rsi_macd_detect(df, i):
    if i < 26: return False
    rsi = df['rsi'].iloc[i]
    m = df['macd_line'].iloc[i]; s = df['macd_signal'].iloc[i]
    pm = df['macd_line'].iloc[i-1]; ps = df['macd_signal'].iloc[i-1]
    return (rsi <= 30 and pm <= ps and m > s) or (rsi >= 70 and pm >= ps and m < s)

def rsi_macd_dir(df, i):
    if df['rsi'].iloc[i] <= 30: return "long"
    return "short"

strategies["RSI+MACD"] = {"detect": rsi_macd_detect, "direction": rsi_macd_dir}

# Liquidation Cascade
def liq_detect(df, i):
    if i < 12: return False
    score = 0
    if df['volume_ratio'].iloc[i] > 3: score += 3
    elif df['volume_ratio'].iloc[i] > 2: score += 2
    if df['return_1h'].iloc[i] < -0.015: score += 2
    elif df['return_1h'].iloc[i] < -0.01: score += 1
    if df['volatility_1h'].iloc[i] > df['volatility_1h'].iloc[i-12:i].mean() * 2: score += 1
    return score >= 5

strategies["Liquidation Cascade"] = {"detect": liq_detect, "direction": lambda df, i: "long"}

# Short Squeeze
def ss_detect(df, i):
    if i < 12: return False
    score = 0
    if df['return_1h'].iloc[i] > 0.01: score += 2
    elif df['return_1h'].iloc[i] > 0.005: score += 1
    if df['volume_ratio'].iloc[i] > 2.5: score += 2
    elif df['volume_ratio'].iloc[i] > 1.5: score += 1
    if df['volatility_1h'].iloc[i] > df['volatility_1h'].iloc[i-12:i].mean() * 1.5: score += 1
    return score >= 4

strategies["Short Squeeze"] = {"detect": ss_detect, "direction": lambda df, i: "long"}

# Cascade Flip
def cf_detect(df, i):
    if i < 12: return False
    score = 0
    if df['volume_ratio'].iloc[i] > 3: score += 3
    if df['return_1h'].iloc[i] < -0.02: score += 2
    if df['lower_wick_ratio'].iloc[i] > 0.5: score += 2
    return score >= 5

strategies["Cascade Flip"] = {"detect": cf_detect, "direction": lambda df, i: "long"}

# Panic Reversal
def panic_detect(df, i):
    if i < 12: return False
    return df['return_1h'].iloc[i] < -0.015 and df['volume_ratio'].iloc[i] > 1.3

strategies["Panic Reversal"] = {"detect": panic_detect, "direction": lambda df, i: "long"}

# Volume Climax
def vc_detect(df, i):
    if i < 6: return False
    return (df['volume_ratio'].iloc[i] > 2.0 and 
            df['upper_wick_ratio'].iloc[i] > 0.3 and 
            df['return_5m'].iloc[i] > 0)

strategies["Volume Climax"] = {"detect": vc_detect, "direction": lambda df, i: "short"}

# Weekend Manipulation
def wm_detect(df, i):
    if i < 6: return False
    return df['volume_ratio'].iloc[i] < 0.6 and abs(df['return_5m'].iloc[i]) > 0.008

def wm_dir(df, i):
    return "long" if df['return_5m'].iloc[i] > 0 else "short"

strategies["Weekend Manipulation"] = {"detect": wm_detect, "direction": wm_dir}

# ============================================================
# 运行分析
# ============================================================

print(f"\n{'='*100}")
print("  📊 5分钟数据 - 各策略最大有利波动分布分析")
print(f"{'='*100}")

all_analysis = {}

for name, s in strategies.items():
    print(f"\n⏳ 分析 {name}...")
    favs = track_max_favorable(df_5m, s["detect"], s["direction"], max_hold=576, cooldown=6)
    
    if len(favs) == 0:
        print(f"   无信号")
        continue
    
    favs_arr = np.array(favs)
    
    analysis = {
        "signal_count": len(favs),
        "mean": float(np.mean(favs_arr)),
        "std": float(np.std(favs_arr)),
        "min": float(np.min(favs_arr)),
        "max": float(np.max(favs_arr)),
        "p25": float(np.percentile(favs_arr, 25)),
        "p50": float(np.percentile(favs_arr, 50)),
        "p75": float(np.percentile(favs_arr, 75)),
        "p80": float(np.percentile(favs_arr, 80)),
        "p85": float(np.percentile(favs_arr, 85)),
        "p90": float(np.percentile(favs_arr, 90)),
        "p95": float(np.percentile(favs_arr, 95)),
    }
    all_analysis[name] = analysis
    
    print(f"   信号数: {len(favs)}")
    print(f"   均值: {analysis['mean']:.0f} | 中位: {analysis['p50']:.0f} | P75: {analysis['p75']:.0f} | P90: {analysis['p90']:.0f}")
    print(f"   范围: {analysis['min']:.0f} ~ {analysis['max']:.0f}")

# ============================================================
# 生成新的止盈建议 (基于P90)
# ============================================================

print(f"\n{'='*100}")
print("  🎯 基于P90的个性化止盈参数建议")
print(f"{'='*100}")

import json

tp_config = {}
for name, a in all_analysis.items():
    p90 = a["p90"]
    
    # 止盈起点 = P90 (只有前10%的好行情才触发)
    tp_start = max(50, int(p90 * 0.8))  # P90的80%作为起点
    tp_max = int(p90 * 3)  # 最大止盈 = P90的3倍
    tp_step = tp_start  # 步长 = 起点
    
    # 确保合理范围
    tp_start = max(50, min(tp_start, 500))
    tp_max = max(tp_start * 2, min(tp_max, 3000))
    tp_step = tp_start
    
    tp_config[name] = {
        "tp_start": tp_start,
        "tp_max": tp_max,
        "tp_step": tp_step,
        "p90_favorable": round(p90, 1),
        "signal_count": a["signal_count"],
    }
    
    print(f"\n  {name}:")
    print(f"    P90最大有利波动: {p90:.0f}点")
    print(f"    止盈: {tp_start}→{tp_max}点 (步长{tp_step})")

# 保存
output_path = backend_path / "data_lake/research/strategy_tp_p90_config.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(tp_config, f, indent=2, ensure_ascii=False)

print(f"\n💾 配置已保存: {output_path}")

# ============================================================
# 额外分析: 5分钟K线平均波幅
# ============================================================

avg_range = np.mean(df_5m['high'].values - df_5m['low'].values)
print(f"\n📊 5分钟K线平均波幅: {avg_range:.1f}点")
print(f"   止损(0.3%价格) ≈ {df_5m['close'].mean() * 0.003:.1f}点")
print(f"   止损(0.2%价格) ≈ {df_5m['close'].mean() * 0.002:.1f}点")

# 各时间段波幅
df_5m['hour'] = pd.to_datetime(df_5m['timestamp']).dt.hour
hourly_range = df_5m.groupby('hour')['high'].max() - df_5m.groupby('hour')['low'].min()
print(f"\n📊 各小时平均K线波幅:")
for hour in range(24):
    subset = df_5m[df_5m['hour'] == hour]
    if len(subset) > 0:
        avg_r = np.mean(subset['high'].values - subset['low'].values)
        print(f"   {hour:02d}:00 - {avg_r:.0f}点")
