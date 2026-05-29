"""
测试 Short IC Top5 策略
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


def test_strategy(strategy_name, days=365):
    """测试单个策略"""
    print(f"\n{'='*80}")
    print(f"测试: {strategy_name} @ BTCUSDT (days={days})")
    print(f"{'='*80}")
    
    pipeline = AlphaPipeline(
        symbols=["BTCUSDT"],
        timeframes=["1h"],
        days=days,
        fee_mode="both",
        holding_bars_list=[3, 5, 10],
        percentile_thresholds=[90, 95, 97],
        skip_walk_forward=False,
        skip_stability=False,
        output_dir=f"reports/alpha/short_ic_top5/{strategy_name}_{days}d",
        exchange="binance",
        exclude_sources=["oi", "liquidation"]
    )
    
    result = pipeline.run([strategy_name])
    
    if result and hasattr(result, 'results') and len(result.results) > 0:
        val_result = result.results[0]
        
        summary = {
            "strategy": strategy_name,
            "days": days,
            "status": val_result.final_status,
            "passed": val_result.final_status in ["pass", "warning"],
        }
        
        if val_result.best_metrics:
            summary.update({
                "pf": val_result.best_metrics.get("profit_factor"),
                "sharpe": val_result.best_metrics.get("sharpe"),
                "trades": val_result.best_metrics.get("trades"),
                "win_rate": val_result.best_metrics.get("win_rate"),
            })
        
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
        
        return summary
    else:
        print("没有结果返回")
        return None


def main():
    strategies = [
        "volume_climax_short",
        "double_top_short",
        "momentum_divergence_short",
        "new_high_failure_short",
        "trend_overextended_short",
    ]
    
    days_list = [90, 180, 365]
    
    all_results = []
    
    for strategy in strategies:
        for days in days_list:
            result = test_strategy(strategy, days)
            if result:
                all_results.append(result)
        
        # 暂停避免内存问题
        import time
        time.sleep(2)
    
    print(f"\n{'='*80}")
    print(f"Short IC Top5 策略汇总")
    print(f"{'='*80}")
    print(f"{'策略':<25} {'天数':<6} {'状态':<10} {'PF':<6} {'Sharpe':<8} {'Trades':<8}")
    print(f"{'-'*70}")
    
    for r in all_results:
        pf = f"{r['pf']:.2f}" if r.get('pf') else "-"
        sharpe = f"{r['sharpe']:.2f}" if r.get('sharpe') else "-"
        trades = f"{r['trades']}" if r.get('trades') else "-"
        
        print(f"{r['strategy']:<25} {r['days']:<6} {r['status']:<10} {pf:<6} {sharpe:<8} {trades:<8}")


if __name__ == "__main__":
    main()
