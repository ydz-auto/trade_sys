"""
运行所有做空策略的完整验证
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
        "breakout_failure",
    ]
    
    symbols = ["BTCUSDT", "ETCUSDT", "SOLUSDT", "ZECUSDT"]
    
    results_summary = []
    
    for strategy_name in short_strategies:
        for symbol in symbols:
            print(f"\n{'='*80}")
            print(f"运行完整验证: {strategy_name} @ {symbol}")
            print(f"{'='*80}")
            
            try:
                pipeline = AlphaPipeline(
                    symbols=[symbol],
                    timeframes=["1h"],
                    days=365,
                    fee_mode="both",
                    holding_bars_list=[5, 10, 20],
                    percentile_thresholds=[90, 95, 97],
                    skip_walk_forward=False,
                    skip_stability=False,
                    output_dir=f"reports/alpha/short_{strategy_name}_{symbol}",
                    exchange="binance",
                    exclude_sources=["oi", "liquidation"]
                )
                
                result = pipeline.run([strategy_name])
                
                if result and hasattr(result, 'results') and len(result.results) > 0:
                    val_result = result.results[0]
                    
                    summary = {
                        "strategy": strategy_name,
                        "symbol": symbol,
                        "final_status": val_result.final_status,
                        "passed": val_result.final_status in ["pass", "warning"],
                    }
                    
                    if val_result.best_metrics:
                        summary.update({
                            "profit_factor": val_result.best_metrics.get("profit_factor"),
                            "sharpe": val_result.best_metrics.get("sharpe"),
                            "win_rate": val_result.best_metrics.get("win_rate"),
                            "trades": val_result.best_metrics.get("trades"),
                        })
                    
                    results_summary.append(summary)
                    
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
                    results_summary.append({
                        "strategy": strategy_name,
                        "symbol": symbol,
                        "final_status": "error",
                        "passed": False,
                    })
                    
            except Exception as e:
                print(f"错误: {e}")
                import traceback
                traceback.print_exc()
                results_summary.append({
                    "strategy": strategy_name,
                    "symbol": symbol,
                    "final_status": "error",
                    "passed": False,
                })
    
    # 打印汇总
    print(f"\n{'='*80}")
    print(f"汇总结果")
    print(f"{'='*80}")
    
    passed_results = [r for r in results_summary if r["passed"]]
    print(f"\n通过的策略 ({len(passed_results)}):")
    for r in passed_results:
        pf = r.get("profit_factor", 0)
        sharpe = r.get("sharpe", 0)
        wr = r.get("win_rate", 0)
        print(f"  {r['strategy']:25} @ {r['symbol']:10} | "
              f"PF={pf:.2f} | Sharpe={sharpe:.2f} | WR={wr:.2%} | Status={r['final_status']}")


if __name__ == "__main__":
    main()
