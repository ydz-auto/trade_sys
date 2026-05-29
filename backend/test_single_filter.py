"""
逐个测试带过滤器的策略，避免崩溃
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

from research.alpha.pipeline import AlphaPipeline


def test_strategy(strategy_name, symbol):
    print(f"\n{'='*80}")
    print(f"测试: {strategy_name} @ {symbol}")
    print(f"{'='*80}")
    
    pipeline = AlphaPipeline(
        symbols=[symbol],
        timeframes=["1h"],
        days=365,
        fee_mode="both",
        holding_bars_list=[5, 10, 20],
        percentile_thresholds=[85, 90, 95],
        skip_walk_forward=False,
        skip_stability=False,
        output_dir=f"reports/alpha/single_filter/{strategy_name}_{symbol}",
        exchange="binance",
        exclude_sources=["oi", "liquidation"]
    )
    
    result = pipeline.run([strategy_name])
    
    if result and hasattr(result, 'results') and len(result.results) > 0:
        val_result = result.results[0]
        print(f"\n最终状态: {val_result.final_status}")
        
        for stage in val_result.stages:
            status = "✓ PASS" if stage.passed else ("- SKIP" if stage.skipped else "✗ FAIL")
            print(f"  {stage.stage_name}: {status} - {stage.message}")
        
        if val_result.best_metrics:
            print(f"\n最佳指标:")
            for k, v in val_result.best_metrics.items():
                if isinstance(v, float):
                    print(f"  {k}: {v:.4f}")
                else:
                    print(f"  {k}: {v}")
        
        return {
            "strategy": strategy_name,
            "symbol": symbol,
            "status": val_result.final_status,
            "pf": val_result.best_metrics.get("profit_factor") if val_result.best_metrics else 0,
            "sharpe": val_result.best_metrics.get("sharpe") if val_result.best_metrics else 0,
            "trades": val_result.best_metrics.get("trades") if val_result.best_metrics else 0,
        }
    else:
        print("没有结果返回")
        return None


if __name__ == "__main__":
    results = []
    
    # 先测试 vol_filter
    result = test_strategy("parabolic_runup_vol_filter", "BTCUSDT")
    if result:
        results.append(result)
    
    # 暂停一下避免内存问题
    import time
    time.sleep(2)
    
    # 测试 ma_filter
    result = test_strategy("parabolic_runup_ma_filter", "BTCUSDT")
    if result:
        results.append(result)
    
    # 打印汇总
    print(f"\n{'='*80}")
    print(f"汇总结果")
    print(f"{'='*80}")
    print(f"策略{'':<35} PF    Sharpe  Trades")
    print(f"----------------------------------------")
    
    for r in results:
        print(f"{r['strategy']:<35} {r['pf']:5.2f}  {r['sharpe']:6.2f}  {r['trades']:6d}")
