"""
在 ZECUSDT 上测试做空策略
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
    short_strategies = [
        "ret_5_positive_reversal",
        "distance_from_high_short",
        "parabolic_runup",
        "volume_climax_short",
        "breakout_failure"
    ]
    
    for strategy in short_strategies:
        print("="*80)
        print(f"测试 {strategy} @ ZECUSDT")
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
            output_dir=f"reports/alpha/test_{strategy}_zec",
            exchange="binance",
            exclude_sources=["oi", "liquidation"]
        )
        
        result = pipeline.run([strategy])
        
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
        
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
