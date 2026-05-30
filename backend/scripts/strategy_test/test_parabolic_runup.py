"""
仅测试 parabolic_runup 策略
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
    print("测试 parabolic_runup 策略 @ BTCUSDT")
    print("="*80)
    
    pipeline = AlphaPipeline(
        symbols=["BTCUSDT"],
        timeframes=["1h"],
        days=90,
        fee_mode="both",
        holding_bars_list=[10],
        percentile_thresholds=[95],
        skip_walk_forward=True,
        skip_stability=True,
        output_dir="reports/alpha/test_parabolic_runup",
        exchange="binance",
        exclude_sources=["oi", "liquidation"]
    )
    
    result = pipeline.run(["parabolic_runup"])
    
    if result and hasattr(result, 'results') and len(result.results) > 0:
        val_result = result.results[0]
        print(f"\n{'='*80}")
        print(f"最终状态: {val_result.final_status}")
        print(f"{'='*80}")
        
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
