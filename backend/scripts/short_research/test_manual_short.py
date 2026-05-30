"""
手动测试做空策略逻辑
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import pandas as pd
from research.alpha.features.matrix import build_feature_matrix
from research.alpha.labels import compute_labels_from_df
from research.alpha.signals.funding_regime_signal import run_signal_test


def main():
    print("="*80)
    print("手动测试 ZECUSDT 做空策略逻辑")
    print("="*80)
    
    # 构建特征矩阵
    fm = build_feature_matrix(
        symbol="ZECUSDT",
        exchange="binance",
        days=365,
        timeframe="1h",
        exclude_sources=["oi", "liquidation"]
    )
    
    print(f"\n特征矩阵形状: {fm.shape}")
    print(f"列: {list(fm.columns[:20])}...")
    
    # 计算标签
    labels = compute_labels_from_df(fm)
    close = fm["close"].values
    
    # 查看 drawdown_from_high 的分布
    feat = fm["drawdown_from_high"].values
    print(f"\ndrawdown_from_high:")
    print(f"  min: {np.nanmin(feat):.4f}")
    print(f"  max: {np.nanmax(feat):.4f}")
    print(f"  mean: {np.nanmean(feat):.4f}")
    print(f"  95th percentile: {np.nanpercentile(feat, 95):.4f}")
    print(f"  90th percentile: {np.nanpercentile(feat, 90):.4f}")
    
    # 测试：当 drawdown_from_high 接近 0（接近高点）时做空
    print(f"\n测试：当 drawdown_from_high > -0.05（接近高点）时做空，持有 20 根 K 线")
    
    # 创建一个特征：-drawdown_from_high，这样当价格接近高点时，这个值更大
    feat_short = -feat
    
    result = run_signal_test(
        close=close,
        feature_vals=feat_short,
        regime_labels=fm["trend_regime"].values if "trend_regime" in fm.columns else np.array(["all"]*len(close)),
        feature_threshold=0.05,  # -drawdown_from_high > 0.05 等价于 drawdown_from_high < -0.05？不对
        holding_bars=20,
        direction="short"
    )
    
    print(f"结果:")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
    
    # 换一种方式：直接用原始特征，但用不同的阈值逻辑
    print(f"\n测试：用原始特征，当 drawdown_from_high > -0.03（接近高点）时做空")
    # 我们需要修改逻辑：当 drawdown_from_high > threshold（不是绝对值）时做空
    # 手动回测
    n = len(close)
    holding_bars = 20
    threshold = -0.03
    fee = 0.0005 * 2
    
    valid_idx = []
    for i in range(n - holding_bars):
        if not np.isnan(feat[i]) and feat[i] > threshold:
            valid_idx.append(i)
    
    if len(valid_idx) > 0:
        entry_prices = close[valid_idx]
        exit_prices = close[np.array(valid_idx) + holding_bars]
        raw_ret = -(exit_prices - entry_prices) / entry_prices
        rets = raw_ret - fee
        
        trades = len(rets)
        wins = rets[rets > 0]
        win_rate = len(wins) / trades
        avg_ret = np.mean(rets)
        total_ret = np.sum(rets)
        sum_win = np.sum(wins) if len(wins) > 0 else 0
        sum_loss = abs(np.sum(rets[rets <= 0])) if len(rets[rets <= 0]) > 0 else 1
        pf = sum_win / sum_loss
        
        print(f"  trades: {trades}")
        print(f"  win_rate: {win_rate:.4f}")
        print(f"  avg_ret: {avg_ret:.4f}")
        print(f"  total_ret: {total_ret:.4f}")
        print(f"  profit_factor: {pf:.4f}")


if __name__ == "__main__":
    main()
