
"""
P0 Funding Conditional IC Analysis - 使用现有报告

读取已有 IC 报告数据，并分析不同 regime 下的 funding 特征表现
"""

import sys
from pathlib import Path
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

IC_REPORT_PATH = BACKEND_ROOT / "reports" / "alpha" / "no_oi"


def main():
    print("=" * 80)
    print("P0 Funding Conditional IC Analysis")
    print("=" * 80)

    symbols = ["BTCUSDT", "ETCUSDT", "ZECUSDT", "SOLUSDT"]

    for symbol in symbols:
        ic_file = IC_REPORT_PATH / f"ic_{symbol}_1h_365d.csv"
        if not ic_file.exists():
            print(f"\n{symbol}: IC report not found at {ic_file}")
            continue

        print(f"\n{symbol}")
        print("-" * 80)

        ic_df = pd.read_csv(ic_file)
        funding_df = ic_df[ic_df["feature"].str.contains("funding", case=False, na=False)].copy()

        if len(funding_df) == 0:
            print("  No funding features found")
            continue

        for _, row in funding_df.iterrows():
            sig_level = ""
            if pd.notna(row.get("p_value")) and row["p_value"] < 0.01:
                sig_level = " **"
            elif pd.notna(row.get("p_value")) and row["p_value"] < 0.05:
                sig_level = " *"

            print(f"  {row['feature']} -> {row['label']}: IC={row['ic']:.4f}, RankIC={row['rank_ic']:.4f}, p={row['p_value']:.4f}{sig_level}, n={row['sample_count']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
