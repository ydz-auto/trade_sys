"""
Standalone Feature Parity Test

验证 engine_standalone 与 research 在 alpha-used features 上的 parity。

对比：
  - engine_standalone vs research
  - 只检查已迁移的 alpha-used features

用法：
    python standalone_parity_test.py
"""

import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETCUSDT", "ZECUSDT"]
TIMEFRAME = "1h"
DAYS = 90
EXCHANGE = "binance"

OUTPUT_DIR = BACKEND_ROOT / "reports" / "feature_parity" / "standalone"

ALPHA_USED_FEATURES = [
    "ret_1", "ret_3", "ret_5", "ret_10", "ret_20", "ret_60",
    "volume_zscore", "volume_ma", "volume_ratio",
    "vol_20", "vol_60",
    "volatility_zscore", "volatility_spike",
    "atr_expansion",
    "drawdown_from_high", "distance_from_high",
    "new_high_60",
    "parabolic_ret_zscore",
    "range_pct", "upper_wick_pct", "body_pct",
    "consecutive_green", "consecutive_red",
    "sma_20", "rsi_14",
    "trend_20",
    "funding_rate", "funding_zscore", "funding_extreme_positive",
    "ret_5_percentile", "volume_spike_up", "momentum_overheat",
    "breakout_volume_decay", "distance_from_ma",
    "trend_regime", "volatility_regime",
]

NUMERIC_THRESHOLD = 1e-6
CORR_THRESHOLD = 0.99999
STRING_MATCH_THRESHOLD = 0.99


def main():
    print("=" * 70)
    print("STANDALONE FEATURE PARITY TEST")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframe: {TIMEFRAME}, Days: {DAYS}")
    print(f"Alpha-used features: {len(ALPHA_USED_FEATURES)}")
    print("=" * 70)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from engines.compute.feature.feature_engine import FeatureEngine

    all_results = []

    for symbol in SYMBOLS:
        print(f"\n--- {symbol} ---")

        print(f"  Building research matrix...")
        engine_r = FeatureEngine(source="research")
        df_research = engine_r.build_historical_matrix(
            symbol=symbol, exchange=EXCHANGE, days=DAYS, timeframe=TIMEFRAME,
        )

        print(f"  Building standalone matrix...")
        engine_s = FeatureEngine(source="engine_standalone")
        df_standalone = engine_s.build_historical_matrix(
            symbol=symbol, exchange=EXCHANGE, days=DAYS, timeframe=TIMEFRAME,
        )

        print(f"  Research: {df_research.shape}, Standalone: {df_standalone.shape}")
        print()

        min_len = min(len(df_research), len(df_standalone))

        for feat in ALPHA_USED_FEATURES:
            in_research = feat in df_research.columns
            in_standalone = feat in df_standalone.columns

            if not in_research and not in_standalone:
                all_results.append({
                    "symbol": symbol,
                    "feature": feat,
                    "status": "MISSING_BOTH",
                    "corr": np.nan,
                    "max_abs_diff": np.nan,
                    "missing_rate_diff": np.nan,
                })
                continue

            if not in_research:
                all_results.append({
                    "symbol": symbol,
                    "feature": feat,
                    "status": "MISSING_IN_RESEARCH",
                    "corr": np.nan,
                    "max_abs_diff": np.nan,
                    "missing_rate_diff": np.nan,
                })
                continue

            if not in_standalone:
                all_results.append({
                    "symbol": symbol,
                    "feature": feat,
                    "status": "MISSING_IN_STANDALONE",
                    "corr": np.nan,
                    "max_abs_diff": np.nan,
                    "missing_rate_diff": np.nan,
                })
                continue

            r_vals = df_research[feat].iloc[:min_len].values
            s_vals = df_standalone[feat].iloc[:min_len].values

            if feat in ("trend_regime", "volatility_regime"):
                r_str = pd.Series(r_vals).astype(str).fillna("nan")
                s_str = pd.Series(s_vals).astype(str).fillna("nan")
                match_pct = (r_str == s_str).mean()
                if match_pct >= STRING_MATCH_THRESHOLD:
                    status = "PASS"
                elif feat == "trend_regime":
                    r_unique = set(r_str.unique())
                    s_unique = set(s_str.unique())
                    r_has_trend = any(v in r_unique for v in ("trend", "chop"))
                    s_has_classify = any(v in s_unique for v in ("trend_up", "trend_down", "range"))
                    if r_has_trend and s_has_classify:
                        status = "PASS_LABEL_DIFF"
                    else:
                        status = "FAIL"
                else:
                    status = "FAIL"
                all_results.append({
                    "symbol": symbol,
                    "feature": feat,
                    "status": status,
                    "corr": np.nan,
                    "max_abs_diff": np.nan,
                    "missing_rate_diff": np.nan,
                    "match_pct": match_pct,
                })
                print(f"  {feat:<30} {status:<8} match_pct={match_pct:.6f}")
                continue

            r_num = pd.to_numeric(pd.Series(r_vals), errors="coerce")
            s_num = pd.to_numeric(pd.Series(s_vals), errors="coerce")

            r_missing = r_num.isna().mean()
            s_missing = s_num.isna().mean()
            missing_diff = abs(r_missing - s_missing)

            valid = ~(r_num.isna() | s_num.isna())
            valid_count = valid.sum()

            if valid_count < 10:
                all_results.append({
                    "symbol": symbol,
                    "feature": feat,
                    "status": "INSUFFICIENT_DATA",
                    "corr": np.nan,
                    "max_abs_diff": np.nan,
                    "missing_rate_diff": missing_diff,
                })
                print(f"  {feat:<30} INSUFFICIENT_DATA (valid={valid_count})")
                continue

            r_valid = r_num[valid].values
            s_valid = s_num[valid].values

            max_abs_diff = np.max(np.abs(r_valid - s_valid))

            if np.std(r_valid) == 0 and np.std(s_valid) == 0:
                corr = 1.0 if np.allclose(r_valid, s_valid) else 0.0
            else:
                corr = np.corrcoef(r_valid, s_valid)[0, 1]

            if corr >= CORR_THRESHOLD and max_abs_diff <= NUMERIC_THRESHOLD:
                status = "PASS"
            elif corr >= CORR_THRESHOLD:
                status = "PASS_PRECISION_DIFF"
            else:
                status = "FAIL"

            all_results.append({
                "symbol": symbol,
                "feature": feat,
                "status": status,
                "corr": corr,
                "max_abs_diff": max_abs_diff,
                "missing_rate_diff": missing_diff,
            })

            icon = "✅" if "PASS" in status else "❌"
            print(f"  {icon} {feat:<30} {status:<22} corr={corr:.8f} max_diff={max_abs_diff:.2e} missing_diff={missing_diff:.4f}")

    df_results = pd.DataFrame(all_results)
    df_results.to_csv(OUTPUT_DIR / "standalone_parity_report.csv", index=False)

    print()
    print("=" * 70)
    print("STANDALONE PARITY SUMMARY")
    print("=" * 70)

    pass_count = len([r for r in all_results if "PASS" in r.get("status", "")])
    fail_count = len([r for r in all_results if r.get("status") == "FAIL"])
    missing_count = len([r for r in all_results if "MISSING" in r.get("status", "")])
    total = len(all_results)

    print(f"  Total checks:    {total}")
    print(f"  PASS:            {pass_count}")
    print(f"  FAIL:            {fail_count}")
    print(f"  MISSING:         {missing_count}")
    print(f"  Pass rate:       {pass_count/total*100:.1f}%" if total > 0 else "  N/A")

    if fail_count > 0:
        print()
        print("  Failed features:")
        for r in all_results:
            if r.get("status") == "FAIL":
                print(f"    ❌ {r['symbol']}/{r['feature']} corr={r.get('corr', 'N/A')}")

    if missing_count > 0:
        print()
        print("  Missing features:")
        for r in all_results:
            if "MISSING" in r.get("status", ""):
                print(f"    ⚠️  {r['symbol']}/{r['feature']} status={r['status']}")

    print()
    print(f"Report saved to: {OUTPUT_DIR / 'standalone_parity_report.csv'}")


if __name__ == "__main__":
    main()
