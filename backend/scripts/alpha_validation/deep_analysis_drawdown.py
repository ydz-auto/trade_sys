"""
Deep Analysis: drawdown_dip_buying 为什么只有 ZECUSDT READY

逐 symbol 对比：
1. Signal 基本面 (PF / Sharpe / trades / win_rate)
2. Walk Forward 逐窗口详情
3. Parameter Stability 1D/2D sweep 详情
4. Regime 分布
"""

import sys
import json
from pathlib import Path

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETCUSDT", "ZECUSDT"]
STRATEGY = "drawdown_dip_buying"
TIMEFRAME = "1h"
DAYS = 365
EXCHANGE = "binance"


def run_single(strategy, symbol):
    from research.alpha.validation.pipeline import AlphaPipeline
    pipeline = AlphaPipeline(
        symbols=[symbol],
        timeframes=[TIMEFRAME],
        days=DAYS,
        exchange=EXCHANGE,
        skip_walk_forward=False,
        skip_stability=False,
        output_dir=str(Path("reports") / "alpha_production_validation" / "deep_analysis"),
        feature_source="engine_standalone",
    )
    result = pipeline.run([strategy])
    return result


def analyze():
    print("=" * 80)
    print(f"DEEP ANALYSIS: {STRATEGY}")
    print("Why only ZECUSDT is READY?")
    print("=" * 80)
    print()

    for symbol in SYMBOLS:
        print("=" * 80)
        print(f"  {symbol}")
        print("=" * 80)

        result = run_single(STRATEGY, symbol)

        for r in result.results:
            if r.strategy != STRATEGY or r.symbol != symbol:
                continue

            print(f"\n  Final Status: {r.final_status}")
            print(f"  Best Params: {r.best_params}")
            print(f"  Best Metrics: {r.best_metrics}")
            print()

            for s in r.stages:
                print(f"  --- Stage: {s.stage_name} (passed={s.passed}, skipped={s.skipped}) ---")

                if s.stage_name == "feature_ic":
                    ic_table = s.data.get("ic_table", []) if s.data else []
                    if ic_table:
                        df_ic = pd.DataFrame(ic_table)
                        print(f"  IC Table ({len(df_ic)} rows):")
                        for _, row in df_ic.head(10).iterrows():
                            print(f"    feature={row.get('feature', 'N/A')}, "
                                  f"horizon={row.get('horizon', 'N/A')}, "
                                  f"ic={row.get('ic', 0):.6f}, "
                                  f"rank_ic={row.get('rank_ic', 0):.6f}")

                elif s.stage_name == "signal_profitability":
                    if s.data:
                        bm = s.data.get("best_metrics", {})
                        bp = s.data.get("best_params", {})
                        print(f"  Best Params: {bp}")
                        print(f"  Best Metrics: PF={bm.get('profit_factor', 'N/A')}, "
                              f"Sharpe={bm.get('sharpe', 'N/A')}, "
                              f"WR={bm.get('win_rate', 'N/A')}, "
                              f"Trades={bm.get('trades', 'N/A')}")

                elif s.stage_name == "walk_forward":
                    if s.data:
                        print(f"  Total Windows: {s.data.get('total_windows')}")
                        print(f"  Avg Return: {s.data.get('avg_return', 0):.6f}")
                        print(f"  Avg Sharpe: {s.data.get('avg_sharpe', 0):.3f}")
                        print(f"  WR Consistency: {s.data.get('win_rate_consistency', 0):.3f}")
                        print(f"  Decay Rate: {s.data.get('decay_rate', 0):.3f}")
                        print(f"  Profitable Window Ratio: {s.data.get('profitable_window_ratio', 0):.2f}")
                        print(f"  Regime Stability: {s.data.get('regime_stability_score', 0):.3f}")

                        windows = s.data.get("window_details", [])
                        if windows:
                            df_wf = pd.DataFrame(windows)
                            print(f"\n  Per-Window Details ({len(df_wf)} windows):")
                            profitable = df_wf[df_wf["avg_ret"] > 0]
                            losing = df_wf[df_wf["avg_ret"] <= 0]
                            print(f"    Profitable windows: {len(profitable)}/{len(df_wf)}")
                            if len(profitable) > 0:
                                print(f"    Avg PF (profitable): {profitable['profit_factor'].mean():.3f}")
                            if len(losing) > 0:
                                print(f"    Avg PF (losing): {losing['profit_factor'].mean():.3f}")
                                print(f"    Worst window PF: {df_wf['profit_factor'].min():.3f}")

                            print(f"\n  Window Sharpe Distribution:")
                            for _, w in df_wf.iterrows():
                                icon = "+" if w["avg_ret"] > 0 else "-"
                                print(f"    [{icon}] window {w['window_idx']:>2}: "
                                      f"trades={w['trades']:>3}, "
                                      f"sharpe={w['sharpe']:>7.3f}, "
                                      f"PF={w['profit_factor']:>7.3f}, "
                                      f"WR={w['win_rate']:>6.3f}, "
                                      f"avg_ret={w['avg_ret']:>9.6f}")

                elif s.stage_name == "parameter_stability":
                    if s.data:
                        print(f"  1D Stable: {s.data.get('is_1d_stable')}")
                        print(f"  2D Stable: {s.data.get('is_2d_stable')}")
                        print(f"  Cross-Regime Stable: {s.data.get('is_cross_regime_stable')}")
                        print(f"  Stability Score: {s.data.get('stability_score', 0):.3f}")
                        print(f"  Profitable Regimes: {s.data.get('profitable_regimes', [])}")
                        print(f"  Losing Regimes: {s.data.get('losing_regimes', [])}")
                        print(f"  Regime Concentration: {s.data.get('regime_concentration', 0):.3f}")

                        sweep_1d = s.data.get("sweep_1d", {})
                        if sweep_1d:
                            print(f"\n  1D Threshold Sweep:")
                            print(f"    Best param: {sweep_1d.get('best_param', 0):.6f}")
                            print(f"    Best metric: {sweep_1d.get('best_metric', 0):.3f}")
                            print(f"    Mean metric: {sweep_1d.get('mean_metric', 0):.3f}")
                            print(f"    Std metric: {sweep_1d.get('std_metric', 0):.3f}")
                            print(f"    Is flat: {sweep_1d.get('is_flat')}")
                            vals = sweep_1d.get("param_values", [])
                            metrics = sweep_1d.get("metric_values", [])
                            if vals and metrics:
                                print(f"    Sweep points:")
                                for v, m in zip(vals, metrics):
                                    marker = " <-- best" if abs(v - sweep_1d.get("best_param", 0)) < 1e-9 else ""
                                    print(f"      thresh={v:.6f} -> sharpe={m:.3f}{marker}")

                        sweep_2d = s.data.get("sweep_2d", {})
                        if sweep_2d:
                            print(f"\n  2D Stability Analysis:")
                            print(f"    Overall stability score: {sweep_2d.get('overall_stability_score', 0):.3f}")
                            print(f"    Is stable: {sweep_2d.get('is_stable')}")
                            regions = sweep_2d.get("stable_regions", [])
                            if regions:
                                print(f"    Stable regions ({len(regions)}):")
                                for reg in regions[:5]:
                                    print(f"      thresh=[{reg.get('x_min', 0):.4f}, {reg.get('x_max', 0):.4f}], "
                                          f"hold=[{reg.get('y_min', 0):.1f}, {reg.get('y_max', 0):.1f}], "
                                          f"mean_sharpe={reg.get('mean_sharpe', 0):.3f}, "
                                          f"std_sharpe={reg.get('std_sharpe', 0):.3f}")
                            else:
                                print(f"    No stable regions found")

                elif s.stage_name == "fee_sensitivity":
                    if s.data:
                        print(f"  Taker Fee: {s.data.get('taker_fee')}")
                        print(f"  Profitable (taker): {s.data.get('profitable_taker')}")
                        print(f"  Profitable (maker): {s.data.get('profitable_maker')}")

                print()

        print()


if __name__ == "__main__":
    analyze()
