"""
测试 parabolic_runup 带过滤器的版本
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
    strategies = [
        "parabolic_runup",                    # 原始版本
        "parabolic_runup_vol_filter",        # 成交量过滤器
        "parabolic_runup_ma_filter",         # MA过滤器
        "parabolic_runup_breakout_filter",   # 突破失败过滤器
        "parabolic_runup_combined",          # 组合过滤器
    ]
    
    symbols = ["BTCUSDT", "ETCUSDT"]
    
    results_summary = []
    
    for strategy_name in strategies:
        for symbol in symbols:
            print(f"\n{'='*80}")
            print(f"测试: {strategy_name} @ {symbol}")
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
                    output_dir=f"reports/alpha/parabolic_filters/{strategy_name}_{symbol}",
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
    
    print(f"\n{'='*80}")
    print(f"汇总对比")
    print(f"{'='*80}")
    
    for symbol in symbols:
        print(f"\n{symbol}:")
        print(f"策略{'':<35} PF    Sharpe  WR    Trades")
        print(f"----------------------------------------")
        
        symbol_results = [r for r in results_summary if r["symbol"] == symbol]
        for r in symbol_results:
            pf = r.get("profit_factor", 0)
            sharpe = r.get("sharpe", 0)
            wr = r.get("win_rate", 0)
            trades = r.get("trades", 0)
            status = "✓" if r["passed"] else "✗"
            
            print(f"{status} {r['strategy']:<35} {pf:5.2f}  {sharpe:6.2f}  {wr:.0%}  {trades:6d}")


if __name__ == "__main__":
    main()
