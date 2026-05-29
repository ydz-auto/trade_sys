"""
测试单个 Short IC 策略（365天）
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


def main():
    strategy_name = "trend_overextended_short"
    
    print(f"{'='*80}")
    print(f"测试: {strategy_name} @ BTCUSDT (365天)")
    print(f"{'='*80}")
    
    pipeline = AlphaPipeline(
        symbols=["BTCUSDT"],
        timeframes=["1h"],
        days=365,
        fee_mode="both",
        holding_bars_list=[3, 5, 10],
        percentile_thresholds=[90, 95, 97],
        skip_walk_forward=False,
        skip_stability=False,
        output_dir=f"reports/alpha/short_ic_single/{strategy_name}",
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
    else:
        print("没有结果返回")


if __name__ == "__main__":
    main()
