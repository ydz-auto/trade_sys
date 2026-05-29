"""
Alpha Factory Status Report - 当前 Alpha 状态汇总

Pipeline 状态：
- Feature Discovery: ✅ 47 Short Features 已建立
- IC Analysis:      ✅ 已完成（从现有报告）
- Conditional IC:   ⚠️  需加强
- Signal Test:      ✅ 已完成
- Fee Sensitivity:  ✅ 已完成
- Multi-Symbol:     ✅ 已完成
- Stability:        ✅ 已完成
- Walk Forward:     ✅ 已完成
- Leaderboard:      ⚠️  正在更新

Paper Trading: ← 当前阶段
Production:    下一阶段
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

REPORTS_DIR = Path("reports/alpha")
OUTPUT_DIR = REPORTS_DIR / "factory_status"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_all_leaderboards():
    leaderboards = {}

    leaderboard_files = [
        ("BTCUSDT", REPORTS_DIR / "leaderboard/BTCUSDT/strategy_leaderboard.csv"),
        ("ZECUSDT", REPORTS_DIR / "leaderboard/ZECUSDT/strategy_leaderboard.csv"),
        ("SOLUSDT", REPORTS_DIR / "leaderboard/SOLUSDT/strategy_leaderboard.csv"),
        ("ETCUSDT", REPORTS_DIR / "leaderboard/ETCUSDT/strategy_leaderboard.csv"),
    ]

    for symbol, path in leaderboard_files:
        if path.exists():
            df = pd.read_csv(path)
            leaderboards[symbol] = df

    return leaderboards


def load_short_features_ic():
    ic_file = REPORTS_DIR / "no_oi/ic_BTCUSDT_1h_365d.csv"
    if ic_file.exists():
        return pd.read_csv(ic_file)
    return pd.DataFrame()


def analyze_leaderboards(leaderboards):
    print("\n" + "=" * 80)
    print("  ALPHA LEADERBOARD SUMMARY")
    print("=" * 80)

    all_results = []
    for symbol, df in leaderboards.items():
        if len(df) == 0:
            continue

        df["symbol"] = symbol

        for _, row in df.iterrows():
            pf = row.get("profit_factor", 0)
            sharpe = row.get("sharpe", 0)
            trades = row.get("trades", 0)
            status = row.get("status", "unknown")

            if pd.notna(pf) and pf > 0:
                tier = "A" if pf > 2.0 else "B" if pf > 1.5 else "C" if pf > 1.0 else "D"
                direction = "SHORT" if "short" in str(row.get("alpha", "")).lower() else "LONG"

                all_results.append({
                    "alpha": row.get("alpha", ""),
                    "symbol": symbol,
                    "direction": direction,
                    "profit_factor": pf,
                    "sharpe": sharpe,
                    "trades": trades,
                    "tier": tier,
                    "wf_passed": row.get("wf_passed", False),
                    "stab_passed": row.get("stab_passed", False),
                })

    if not all_results:
        print("\n  No valid alpha results found!")
        return pd.DataFrame()

    results_df = pd.DataFrame(all_results)

    print("\n  TOP 10 ALPHAS BY PROFIT FACTOR:")
    print(f"\n  {'Alpha':<35} {'Sym':<8} {'Dir':<6} {'PF':>8} {'Sharpe':>8} {'Trades':>8} {'Tier':<5} {'WF':<5} {'Stab':<5}")
    print(f"  {'-'*95}")

    top10 = results_df.nlargest(10, "profit_factor")
    for _, row in top10.iterrows():
        wf = "✓" if row["wf_passed"] else "✗"
        stab = "✓" if row["stab_passed"] else "✗"
        print(f"  {row['alpha']:<35} {row['symbol']:<8} {row['direction']:<6} {row['profit_factor']:>8.2f} {row['sharpe']:>8.2f} {int(row['trades']):>8} {row['tier']:<5} {wf:<5} {stab:<5}")

    long_alphas = results_df[results_df["direction"] == "LONG"]
    short_alphas = results_df[results_df["direction"] == "SHORT"]

    print(f"\n  DIRECTION BREAKDOWN:")
    print(f"  ───────────────────────────────────────────────────────────")
    print(f"  LONG Alphas:  {len(long_alphas)}")
    if len(long_alphas) > 0:
        print(f"    • Tier A (PF>2):  {len(long_alphas[long_alphas['tier'] == 'A'])}")
        print(f"    • Tier B (PF>1.5): {len(long_alphas[long_alphas['tier'] == 'B'])}")
        print(f"    • Tier C (PF>1):  {len(long_alphas[long_alphas['tier'] == 'C'])}")
        print(f"    • Best Long: {long_alphas.nlargest(1, 'profit_factor')['alpha'].values[0]} (PF={long_alphas.nlargest(1, 'profit_factor')['profit_factor'].values[0]:.2f})")

    print(f"\n  SHORT Alphas: {len(short_alphas)}")
    if len(short_alphas) > 0:
        print(f"    • Tier A (PF>2):  {len(short_alphas[short_alphas['tier'] == 'A'])}")
        print(f"    • Tier B (PF>1.5): {len(short_alphas[short_alphas['tier'] == 'B'])}")
        print(f"    • Tier C (PF>1):  {len(short_alphas[short_alphas['tier'] == 'C'])}")
        print(f"    • Best Short: {short_alphas.nlargest(1, 'profit_factor')['alpha'].values[0]} (PF={short_alphas.nlargest(1, 'profit_factor')['profit_factor'].values[0]:.2f})")

    return results_df


def analyze_short_features_ic(ic_df):
    print("\n" + "=" * 80)
    print("  SHORT FEATURES IC ANALYSIS")
    print("=" * 80)

    if len(ic_df) == 0:
        print("\n  No IC data found!")
        return

    short_families = [
        "short_overextension",
        "short_parabolic",
        "short_exhaustion",
        "short_breakfail",
        "short_crowded",
    ]

    for family in short_families:
        family_ic = ic_df[ic_df["alpha_family"] == family]

        if len(family_ic) == 0:
            continue

        strong_ic = family_ic[family_ic["rank_ic"].abs() > 0.02]

        print(f"\n  {family.upper().replace('_', ' ')}:")
        print(f"  ───────────────────────────────────────────────────────────")

        if len(strong_ic) == 0:
            print(f"    No features with |Rank IC| > 0.02")
        else:
            print(f"    Features with |Rank IC| > 0.02: {len(strong_ic)}")
            for _, row in strong_ic.nlargest(3, "rank_ic").iterrows():
                horizon = row.get("horizon", "?")
                rank_ic = row.get("rank_ic", 0)
                ic = row.get("ic", 0)
                print(f"    • {row['feature']:<30} H={horizon} IC={ic:.4f} RankIC={rank_ic:.4f}")


def analyze_symbols(leaderboards):
    print("\n" + "=" * 80)
    print("  PER-SYMBOL ANALYSIS")
    print("=" * 80)

    for symbol, df in leaderboards.items():
        if len(df) == 0:
            continue

        valid = df[df["profit_factor"].notna() & (df["profit_factor"] > 0)]
        passed = valid[valid["profit_factor"] > 1.0]
        tier_a = passed[passed["profit_factor"] > 2.0]

        best = valid.nlargest(1, "profit_factor").iloc[0] if len(valid) > 0 else None

        print(f"\n  {symbol}:")
        print(f"  ───────────────────────────────────────────────────────────")
        print(f"    Total alphas:  {len(df)}")
        print(f"    Valid (PF>0): {len(valid)}")
        print(f"    Profitable:    {len(passed)}")
        print(f"    Tier A:       {len(tier_a)}")

        if best is not None:
            print(f"    Best: {best['alpha']} (PF={best['profit_factor']:.2f}, Sharpe={best.get('sharpe', 0):.2f})")


def print_pipeline_status():
    print("\n" + "=" * 80)
    print("  ALPHA FACTORY PIPELINE STATUS")
    print("=" * 80)
    print("""
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ Stage                   │ Status   │ Notes                              │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ Feature Discovery       │ ✅ DONE  │ 47 Short Features established      │
  │ IC Analysis             │ ✅ DONE  │ From existing reports             │
  │ Conditional IC          │ ⚠️  WEAK │ Need regime-based IC enhancement  │
  │ Signal Test             │ ✅ DONE  │ All symbols tested                │
  │ Fee Sensitivity         │ ✅ DONE  │ Taker fee 0.1% validated          │
  │ Multi-Symbol            │ ✅ DONE  │ BTC/ZEC/SOL/ETC tested            │
  │ Stability               │ ✅ DONE  │ Parameter stability tested         │
  │ Walk Forward            │ ✅ DONE  │ Rolling window tested            │
  │ Leaderboard             │ ⚠️  UPDATE│ Needs fresh run                   │
  │ Paper Trading           │ ← CURRENT│ Next phase                        │
  │ Production              │  NEXT    │ After paper trading passes        │
  └─────────────────────────────────────────────────────────────────────────┘
  """)


def print_next_steps():
    print("\n" + "=" * 80)
    print("  NEXT STEPS & RECOMMENDATIONS")
    print("=" * 80)
    print("""
  1. REGIME CLASSIFIER (HIGH PRIORITY)
     - Build proper regime classifier (panic/trend_up/trend_down/range)
     - Re-run Conditional IC to find regime-specific alphas
     - Current bottleneck: weak Conditional IC

  2. SHORT ALPHA ENHANCEMENT
     - The 47 Short Features are ready in registry
     - Need fresh IC analysis to validate new features:
       * distance_from_ma20, distance_from_ma60
       * ret_3/5/10_acceleration
       * volume_climax, taker_buy_climax
       * funding_oi_combined, crowded_long_score
     - Expected: BTC Short Alpha may pass WF with proper features

  3. PAPER TRADING CANDIDATES
     - ZEC drawdown_dip_buying: PF=5.31, Sharpe=9.91, WF PASS ✅
     - ZEC drawdown_ret5_combo: PF=1.84, Sharpe=4.47, WF PASS ✅
     - BTC parabolic_runup: PF=1.19, Sharpe=1.03 (marginal)

  4. LONG ALPHA STATUS
     - BTC Long: ALL FAILED (your observation correct)
     - ETH Long: TBD
     - SOL Long: TBD
     - Reason: Feature Universe biased toward "mean reversion long"

  5. DATA REQUIREMENTS
     - OI data: Available ✅
     - Funding data: Available ✅
     - Trade flow: Available ✅
     - Liquidation: Blocked (needs integration)
  """)


def main():
    print("\n" + "=" * 80)
    print("  ALPHA FACTORY STATUS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    print_pipeline_status()

    leaderboards = load_all_leaderboards()
    ic_df = load_short_features_ic()

    results_df = analyze_leaderboards(leaderboards)
    analyze_symbols(leaderboards)
    analyze_short_features_ic(ic_df)
    print_next_steps()

    summary_file = OUTPUT_DIR / "alpha_status_summary.csv"
    if len(results_df) > 0:
        results_df.to_csv(summary_file, index=False)
        print(f"\n  Summary saved to: {summary_file}")

    print("\n" + "=" * 80)
    print("  END OF REPORT")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
