"""
调优 volume_climax_filter 的阈值，平衡 PF 和交易数
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


def main():
    print("="*80)
    print("调优 volume_climax_filter 参数")
    print("="*80)
    
    symbol = "BTCUSDT"
    
    # 构建特征矩阵
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
    vol_zscore = fm["volume_zscore"].values
    
    print(f"\n特征统计:")
    print(f"parabolic_ret_zscore: 90th={np.nanpercentile(parabolic, 90):.2f}, 95th={np.nanpercentile(parabolic, 95):.2f}")
    print(f"ret_5: 90th={np.nanpercentile(ret_5, 90):.2f}, 95th={np.nanpercentile(ret_5, 95):.2f}")
    print(f"volume_zscore: 90th={np.nanpercentile(vol_zscore, 90):.2f}, 95th={np.nanpercentile(vol_zscore, 95):.2f}")
    
    # 测试不同的参数组合
    results = []
    fee = 0.0005 * 2
    
    for p_thresh in [85, 90, 92, 95]:
        p_val = np.nanpercentile(parabolic, p_thresh)
        for r_thresh in [80, 85, 90]:
            r_val = np.nanpercentile(ret_5, r_thresh)
            for v_thresh in [70, 75, 80, 85]:
                v_val = np.nanpercentile(vol_zscore, v_thresh)
                
                n = len(close)
                holding_bars = 10
                
                valid_idx = []
                for i in range(n - holding_bars):
                    if (not np.isnan(parabolic[i]) and parabolic[i] > p_val and
                        not np.isnan(ret_5[i]) and ret_5[i] > r_val and
                        not np.isnan(vol_zscore[i]) and vol_zscore[i] > v_val):
                        valid_idx.append(i)
                
                if len(valid_idx) >= 30:
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
                    
                    results.append({
                        "p_thresh": p_thresh,
                        "r_thresh": r_thresh,
                        "v_thresh": v_thresh,
                        "trades": trades,
                        "pf": pf,
                        "wr": win_rate,
                        "avg_ret": avg_ret,
                        "total_ret": total_ret
                    })
    
    # 按 PF 排序
    results.sort(key=lambda x: x["pf"], reverse=True)
    
    print(f"\n{'='*80}")
    print(f"最佳参数组合 (PF 降序，trades >= 30):")
    print(f"{'='*80}")
    print(f"{'p_thresh':>10} {'r_thresh':>10} {'v_thresh':>10} {'trades':>8} {'PF':>6} {'WR':>6} {'avg_ret':>10}")
    print(f"{'-'*60}")
    
    for r in results[:10]:
        print(f"{r['p_thresh']:>10} {r['r_thresh']:>10} {r['v_thresh']:>10} {r['trades']:>8} {r['pf']:>6.2f} {r['wr']:>6.1%} {r['avg_ret']:>10.4f}")


if __name__ == "__main__":
    main()
