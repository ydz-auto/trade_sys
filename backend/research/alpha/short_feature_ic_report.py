"""
Short Feature IC Top20 Report Generator
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

REPORTS_DIR = Path("reports/alpha/debug")
OUTPUT_DIR = Path("reports/alpha")


def generate_short_ic_top20(symbol: str = "BTCUSDT", timeframe: str = "1h", days: int = 90):
    ic_file = REPORTS_DIR / f"ic_results_{symbol}_{timeframe}_{days}d.csv"
    
    if not ic_file.exists():
        print(f"IC file not found: {ic_file}")
        return
    
    ic_df = pd.read_csv(ic_file)
    
    short_families = [
        "short_overextension",
        "short_parabolic", 
        "short_exhaustion",
        "short_breakfail",
        "short_crowded",
    ]
    
    short_ic = ic_df[ic_df["alpha_family"].isin(short_families)]
    
    short_ic = short_ic.sort_values("rank_ic", ascending=False)
    
    print("\n" + "=" * 80)
    print(f"  SHORT FEATURE IC TOP20 REPORT")
    print(f"  Symbol: {symbol} | Timeframe: {timeframe} | Days: {days}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    
    print(f"\n  {'Rank':<6} {'Feature':<25} {'Family':<20} {'Horizon':<10} {'IC':>10} {'Rank IC':>10}")
    print(f"  {'-'*85}")
    
    for i, (_, row) in enumerate(short_ic.head(20).iterrows(), 1):
        family = row.get("alpha_family", "unknown")
        family_display = family.replace("_", " ").upper()[:18]
        print(f"  {i:<6} {row['feature']:<25} {family_display:<20} {row['horizon']:<10} {row['ic']:>10.4f} {row['rank_ic']:>10.4f}")
    
    print(f"\n  Total Short Features tested: {len(short_ic)}")
    strong_count = len(short_ic[short_ic["rank_ic"].abs() > 0.03])
    print(f"  Features with |Rank IC| > 0.03: {strong_count}")
    
    output_file = OUTPUT_DIR / f"short_feature_ic_top20_{symbol}_{timeframe}_{days}d.csv"
    short_ic.head(20).to_csv(output_file, index=False)
    print(f"\n  Report saved to: {output_file}")
    
    return short_ic.head(20)


def analyze_by_family(ic_df):
    print("\n" + "=" * 80)
    print("  FAMILY PERFORMANCE SUMMARY")
    print("=" * 80)
    
    short_families = {
        "short_overextension": "OVEREXTENSION",
        "short_parabolic": "PARABOLIC",
        "short_exhaustion": "EXHAUSTION",
        "short_breakfail": "BREAKFAIL",
        "short_crowded": "CROWDED",
    }
    
    for family_code, family_name in short_families.items():
        family_ic = ic_df[ic_df["alpha_family"] == family_code]
        
        if len(family_ic) == 0:
            continue
        
        avg_ic = family_ic["rank_ic"].mean()
        max_ic = family_ic["rank_ic"].max()
        strong_count = len(family_ic[family_ic["rank_ic"].abs() > 0.03])
        
        print(f"\n  {family_name}:")
        print(f"  ─────────────────────────────────────────────────")
        print(f"    Features: {len(family_ic)}")
        print(f"    Avg Rank IC: {avg_ic:.4f}")
        print(f"    Max Rank IC: {max_ic:.4f}")
        print(f"    Strong (>0.03): {strong_count}")
        
        top_features = family_ic.nlargest(3, "rank_ic")
        if len(top_features) > 0:
            print(f"    Top Features:")
            for _, row in top_features.iterrows():
                print(f"      • {row['feature']}: Rank IC = {row['rank_ic']:.4f}")


if __name__ == "__main__":
    top20 = generate_short_ic_top20("BTCUSDT", "1h", 90)
    
    ic_file = Path("reports/alpha/debug") / f"ic_results_BTCUSDT_1h_90d.csv"
    if ic_file.exists():
        ic_df = pd.read_csv(ic_file)
        analyze_by_family(ic_df)
    
    print("\n" + "=" * 80)
    print("  END OF REPORT")
    print("=" * 80)
