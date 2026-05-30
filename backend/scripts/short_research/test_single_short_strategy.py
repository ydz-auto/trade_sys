"""
测试单个做空策略，避免全量运行崩溃
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
from research.alpha.registry.alpha_registry import AlphaRegistry


def test_single_strategy(strategy_name: str, symbol: str = "BTCUSDT"):
    """
    测试单个策略
    """
    print(f"{'='*60}")
    print(f"测试策略: {strategy_name} @ {symbol}")
    print(f"{'='*60}")
    
    try:
        # 检查策略是否存在
        defn = AlphaRegistry.get(strategy_name)
        print(f"策略定义: {defn}")
        
        # 创建 Pipeline - 先禁用 WF 和 Stability 快速验证
        pipeline = AlphaPipeline(
            symbols=[symbol],
            timeframes=["1h"],
            days=90,
            fee_mode="both",
            holding_bars_list=[10],
            percentile_thresholds=[95],
            skip_walk_forward=True,
            skip_stability=True,
            output_dir=f"reports/alpha/test_{strategy_name}",
            exchange="binance",
            exclude_sources=["oi", "liquidation"]
        )
        
        # 运行单个策略
        result = pipeline.run([strategy_name])
        
        if result and hasattr(result, 'results') and len(result.results) > 0:
            val_result = result.results[0]
            print(f"\n{'='*60}")
            print(f"结果汇总: {strategy_name} @ {symbol}")
            print(f"{'='*60}")
            print(f"最终状态: {val_result.final_status}")
            print(f"阶段数: {len(val_result.stages)}")
            
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
            
            return val_result.final_status == "PASSED"
        else:
            print("没有结果返回")
            return False
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # SHORT_EXHAUSTION 策略列表
    short_strategies = [
        "ret_5_positive_reversal",
        "distance_from_high_short",
        "parabolic_runup",
        "volume_climax_short",
        "breakout_failure"
    ]
    
    # 测试币种
    symbols = ["BTCUSDT", "ETCUSDT", "SOLUSDT", "ZECUSDT"]
    
    print("开始测试单个做空策略")
    print("="*80)
    
    for strategy in short_strategies:
        for symbol in symbols:
            success = test_single_strategy(strategy, symbol)
            print(f"\n策略 {strategy} @ {symbol} {'成功' if success else '失败'}\n")
            # 短暂暂停避免问题
            import time
            time.sleep(2)
