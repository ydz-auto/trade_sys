"""
测试 distance_from_high_short 策略 @ ZECUSDT
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

from research.alpha.validation.pipeline import AlphaPipeline


def main():
    print("="*80)
    print("测试 distance_from_high_short 策略 @ ZECUSDT")
    print("="*80)
    
    pipeline = AlphaPipeline(
        symbols=["ZECUSDT"],
        timeframes=["1h"],
        days=365,
        fee_mode="both",
        holding_bars_list=[5, 10, 20],
        percentile_thresholds=[90, 95, 97],
        skip_walk_forward=True,
        skip_stability=True,
        output_dir="reports/alpha/test_distance_from_high_short_zec",
        exchange="binance",
        exclude_sources=["oi", "liquidation"]
    )
    
    result = pipeline.run(["distance_from_high_short"])
    
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
