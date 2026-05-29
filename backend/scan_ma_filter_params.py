"""
MA Filter 参数稳定性扫描
目标：找到一片稳定的参数区域，而非单个最优参数

特征说明：
- trend_20: (close - ma20) / ma20，距离 MA20 的百分比
- trend_60: (close - ma60) / ma60，距离 MA60 的百分比
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import pandas as pd
from research.alpha.feature_matrix import build_feature_matrix


def compute_strategy_metrics(close, feature_primary, feature_confirm, 
                            p_thresh, dist_thresh,
                            holding_bars, fee=0.001):
    """
    计算策略指标
    - feature_primary: parabolic_ret_zscore
    - feature_confirm: trend_XX = (close - ma) / ma
    """
    n = len(close)
    
    valid_idx = []
    for i in range(n - holding_bars):
        if (not np.isnan(feature_primary[i]) and feature_primary[i] > p_thresh and
            not np.isnan(feature_confirm[i]) and feature_confirm[i] > dist_thresh):
            valid_idx.append(i)
    
    if len(valid_idx) < 30:
        return None
    
    entry_prices = close[valid_idx]
    exit_prices = close[np.array(valid_idx) + holding_bars]
    raw_ret = -(exit_prices - entry_prices) / entry_prices
    rets = raw_ret - fee
    
    trades = len(rets)
    if trades < 30:
        return None
    
    wins = rets[rets > 0]
    win_rate = len(wins) / trades
    avg_ret = np.mean(rets)
    total_ret = np.sum(rets)
    sum_win = np.sum(wins) if len(wins) > 0 else 0
    sum_loss = abs(np.sum(rets[rets <= 0])) if len(rets[rets <= 0]) > 0 else 1
    pf = sum_win / sum_loss if sum_loss > 0 else 0
    
    sharpe = np.mean(rets) / np.std(rets) * np.sqrt(24 * 365 / holding_bars) if np.std(rets) > 0 else 0
    
    return {
        "trades": trades,
        "win_rate": win_rate,
        "avg_ret": avg_ret,
        "total_ret": total_ret,
        "profit_factor": pf,
        "sharpe": sharpe,
    }


def scan_ma_filter_params(symbol):
    """扫描 MA filter 的参数组合"""
    print(f"\n扫描 {symbol}...")
    
    fm = build_feature_matrix(
        symbol=symbol,
        exchange="binance",
        days=365,
        timeframe="1h",
        exclude_sources=["oi", "liquidation"]
    )
    
    close = fm["close"].values
    parabolic = fm["parabolic_ret_zscore"].values
    ret_5 = fm["ret_5"].values
    
    results = []
    
    trend_cols = ["trend_20", "trend_60"]
    distances = [0.01, 0.015, 0.02, 0.03, 0.05, 0.07, 0.10]  # 1%, 1.5%, 2%, 3%, 5%, 7%, 10%
    holding_bars_list = [5, 10, 20]
    
    for trend_col in trend_cols:
        if trend_col not in fm.columns:
            print(f"  跳过 {trend_col}，列不存在")
            continue
        
        trend = fm[trend_col].values
        
        for dist_pct in distances:
            for holding_bars in holding_bars_list:
                for pct in [85, 90, 95]:
                    p_val = np.nanpercentile(parabolic, pct)
                    
                    metrics = compute_strategy_metrics(
                        close, parabolic, trend,
                        p_val, dist_pct,
                        holding_bars
                    )
                    
                    if metrics:
                        metrics.update({
                            "symbol": symbol,
                            "trend_col": trend_col,
                            "distance_pct": dist_pct * 100,
                            "holding_bars": holding_bars,
                            "percentile": pct,
                        })
                        results.append(metrics)
    
    print(f"  完成，找到 {len(results)} 个有效参数组合")
    return results


def main():
    symbols = ["BTCUSDT", "ETCUSDT", "SOLUSDT", "ZECUSDT"]
    
    all_results = []
    
    for symbol in symbols:
        results = scan_ma_filter_params(symbol)
        all_results.extend(results)
    
    df = pd.DataFrame(all_results)
    
    print(f"\n{'='*80}")
    print(f"参数扫描汇总")
    print(f"{'='*80}")
    print(f"总共 {len(df)} 个有效参数组合")
    
    if len(df) == 0:
        print("没有找到有效参数组合")
        return
    
    print(f"\n特征统计:")
    print(f"profit_factor: min={df['profit_factor'].min():.3f}, max={df['profit_factor'].max():.3f}, mean={df['profit_factor'].mean():.3f}")
    print(f"sharpe: min={df['sharpe'].min():.3f}, max={df['sharpe'].max():.3f}, mean={df['sharpe'].mean():.3f}")
    print(f"trades: min={df['trades'].min()}, max={df['trades'].max()}, mean={df['trades'].mean():.0f}")
    
    df_stable = df[
        (df["profit_factor"] > 1.25) &
        (df["sharpe"] > 1.2) &
        (df["trades"] > 150)
    ]
    
    print(f"\n稳定区域参数组合 (PF>1.25, Sharpe>1.2, Trades>150): {len(df_stable)} 个")
    
    if len(df_stable) > 0:
        print(f"\n稳定区域分布：")
        
        print(f"\n按 Trend Column:")
        period_stats = df_stable.groupby("trend_col").agg({
            "profit_factor": ["count", "mean", "max"],
            "sharpe": ["mean", "max"],
            "trades": "mean"
        }).round(3)
        print(period_stats)
        
        print(f"\n按 Distance Threshold (%):")
        dist_stats = df_stable.groupby("distance_pct").agg({
            "profit_factor": ["count", "mean", "max"],
            "sharpe": ["mean", "max"],
            "trades": "mean"
        }).round(3)
        print(dist_stats)
        
        print(f"\n按 Holding Bars:")
        holding_stats = df_stable.groupby("holding_bars").agg({
            "profit_factor": ["count", "mean", "max"],
            "sharpe": ["mean", "max"],
            "trades": "mean"
        }).round(3)
        print(holding_stats)
        
        print(f"\n最佳组合 Top 10:")
        df_sorted = df_stable.sort_values("profit_factor", ascending=False).head(10)
        print(df_sorted[["symbol", "trend_col", "distance_pct", "holding_bars", 
                          "profit_factor", "sharpe", "trades", "win_rate"]].to_string(index=False))
    else:
        print(f"\n没有找到满足稳定区域标准的参数组合")
        print(f"\n放宽条件后的结果:")
        
        df_relaxed = df[
            (df["profit_factor"] > 1.1) &
            (df["trades"] > 100)
        ]
        print(f"PF>1.1, Trades>100: {len(df_relaxed)} 个组合")
        
        if len(df_relaxed) > 0:
            print(f"\n按 Trend Column 分布:")
            print(df_relaxed.groupby("trend_col").agg({
                "profit_factor": ["count", "mean", "max"],
                "sharpe": "mean",
                "trades": "mean"
            }).round(3))
            
            print(f"\n按 Distance Threshold (%):")
            print(df_relaxed.groupby("distance_pct").agg({
                "profit_factor": ["count", "mean", "max"],
                "sharpe": "mean",
                "trades": "mean"
            }).round(3))
            
            print(f"\n最佳组合 Top 10:")
            df_sorted = df_relaxed.sort_values("profit_factor", ascending=False).head(10)
            print(df_sorted[["symbol", "trend_col", "distance_pct", "holding_bars", 
                              "profit_factor", "sharpe", "trades", "win_rate"]].to_string(index=False))


if __name__ == "__main__":
    main()
