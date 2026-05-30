"""
手动测试用 ret_5 做反转做空策略
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
    print("手动测试 ret_5 反转做空策略")
    print("="*80)
    
    symbols = ["BTCUSDT", "ETCUSDT", "SOLUSDT", "ZECUSDT"]
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"测试 {symbol}")
        print(f"{'='*80}")
        
        try:
            # 构建特征矩阵
            fm = build_feature_matrix(
                symbol=symbol,
                exchange="binance",
                days=365,
                timeframe="1h",
                exclude_sources=["oi", "liquidation"]
            )
            
            close = fm["close"].values
            feat = fm["ret_5"].values
            
            print(f"\nret_5 分布:")
            print(f"  min: {np.nanmin(feat):.4f}")
            print(f"  max: {np.nanmax(feat):.4f}")
            print(f"  mean: {np.nanmean(feat):.4f}")
            print(f"  90th percentile: {np.nanpercentile(feat, 90):.4f}")
            print(f"  95th percentile: {np.nanpercentile(feat, 95):.4f}")
            
            # 测试不同的阈值和持仓时间
            best_result = None
            best_pf = 0
            
            for percentile in [85, 90, 95, 97]:
                threshold = np.nanpercentile(feat, percentile)
                for holding_bars in [5, 10, 20]:
                    # 手动回测：当 ret_5 > threshold 时做空
                    n = len(close)
                    fee = 0.0005 * 2
                    
                    valid_idx = []
                    for i in range(n - holding_bars):
                        if not np.isnan(feat[i]) and feat[i] > threshold:
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
                        
                        if pf > best_pf and win_rate > 0.5:
                            best_pf = pf
                            best_result = {
                                "percentile": percentile,
                                "threshold": threshold,
                                "holding_bars": holding_bars,
                                "trades": trades,
                                "win_rate": win_rate,
                                "avg_ret": avg_ret,
                                "total_ret": total_ret,
                                "profit_factor": pf
                            }
            
            if best_result:
                print(f"\n最佳结果:")
                for k, v in best_result.items():
                    if isinstance(v, float):
                        print(f"  {k}: {v:.4f}")
                    else:
                        print(f"  {k}: {v}")
            else:
                print(f"\n没有找到满足条件 (WR>0.5, trades>=30) 的参数组合")
                
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
