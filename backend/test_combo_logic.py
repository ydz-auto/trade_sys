"""
测试不同组合逻辑对策略表现的影响
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
from research.alpha.strategy_alpha_registry import AlphaRegistry, AlphaDefinition


def main():
    # 临时注册不同组合逻辑的版本
    test_strategies = [
        ("parabolic_runup_primary_confirm", "primary_with_confirm"),
        ("parabolic_runup_all_trigger", "all_must_trigger"),
    ]
    
    for name, combo_logic in test_strategies:
        if AlphaRegistry.get(name):
            continue
        
        AlphaRegistry.register(AlphaDefinition(
            name=name,
            features=["parabolic_ret_zscore", "ret_5", "volume_zscore"],
            mode=f"parabolic_short_{name}",
            direction="short",
            primary_feature="parabolic_ret_zscore",
            signal_direction_map={
                "parabolic_ret_zscore": "positive_means_short",
                "ret_5": "positive_means_short",
                "volume_zscore": "positive_means_short",
            },
            combo_logic=combo_logic,
        ))
    
    symbols = ["BTCUSDT"]
    
    for strategy_name in [s[0] for s in test_strategies]:
        print(f"\n{'='*80}")
        print(f"测试: {strategy_name} @ BTCUSDT")
        print(f"{'='*80}")
        
        pipeline = AlphaPipeline(
            symbols=["BTCUSDT"],
            timeframes=["1h"],
            days=365,
            fee_mode="both",
            holding_bars_list=[5, 10, 20],
            percentile_thresholds=[85, 90, 95],
            skip_walk_forward=False,
            skip_stability=False,
            output_dir=f"reports/alpha/combo_test/{strategy_name}",
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
