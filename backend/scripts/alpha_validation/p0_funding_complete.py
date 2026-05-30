"""
P0 - Funding Conditional IC Analysis (Complete Version)

This script performs a complete funding conditional IC analysis:
1. Loads feature matrix from data lake files directly (no heavy dependencies)
2. Calculates unconditional IC for funding features
3. Classifies market regimes (trend, volatility, funding)
4. Calculates conditional IC by regime
5. Generates comprehensive reports

Usage:
    python scripts/alpha_validation/p0_funding_complete.py
    python scripts/alpha_validation/p0_funding_complete.py --symbol BTCUSDT --days 365
"""

import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import argparse
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats

# Set up paths
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

REPORTS_DIR = BACKEND_ROOT / "reports" / "funding_ic"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ICResult:
    feature: str
    label: str
    ic: float
    rank_ic: float
    p_value: float
    rank_p_value: float
    sample_count: int
    regime: str = "unconditional"
    regime_col: str = "all"


def load_klines(symbol: str, exchange: str = "binance", timeframe: str = "1h", days: int = 365) -> Optional[pd.DataFrame]:
    """Load klines data from data lake."""
    try:
        from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
        reader = FileDataLakeReader()
        klines = reader.load_klines(exchange, symbol, timeframe=timeframe)
        if klines is None or len(klines) == 0:
            print(f"  No klines data found for {symbol}")
            return None
        
        klines["timestamp"] = pd.to_datetime(klines["timestamp"])
        cutoff = klines["timestamp"].max() - pd.Timedelta(days=days)
        klines = klines[klines["timestamp"] >= cutoff].copy()
        
        for col in ["open", "high", "low", "close", "volume"]:
            klines[col] = pd.to_numeric(klines[col], errors="coerce")
        
        return klines
    except Exception as e:
        print(f"  Error loading klines: {e}")
        return None


def load_funding(symbol: str, exchange: str = "binance") -> Optional[pd.DataFrame]:
    """Load funding data from data lake."""
    try:
        from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
        reader = FileDataLakeReader()
        funding = reader.load_funding(exchange, symbol)
        if funding is None or len(funding) == 0:
            print(f"  No funding data found for {symbol}")
            return None
        
        funding = funding.copy()
        if "funding_time" in funding.columns:
            funding["timestamp"] = pd.to_datetime(funding["funding_time"])
        elif "timestamp" in funding.columns:
            funding["timestamp"] = pd.to_datetime(funding["timestamp"])
        
        if "funding_rate" not in funding.columns and "fundingRate" in funding.columns:
            funding["funding_rate"] = pd.to_numeric(funding["fundingRate"], errors="coerce")
        elif "funding_rate" in funding.columns:
            funding["funding_rate"] = pd.to_numeric(funding["funding_rate"], errors="coerce")
        
        return funding
    except Exception as e:
        print(f"  Error loading funding: {e}")
        return None


def build_simple_feature_matrix(
    klines: pd.DataFrame, 
    funding: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """Build a simple feature matrix with basic features and funding."""
    df = klines[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    close = df["close"]
    
    # Basic returns
    df["ret_1"] = close.pct_change(1)
    df["ret_3"] = close.pct_change(3)
    df["ret_5"] = close.pct_change(5)
    df["ret_10"] = close.pct_change(10)
    
    # Trend
    df["trend_20"] = (close - close.rolling(20).mean()) / close.rolling(20).mean()
    
    # Volatility
    df["vol_20"] = df["ret_1"].rolling(20).std()
    df["vol_60"] = df["ret_1"].rolling(60).std()
    
    # Volume
    df["volume_zscore"] = (df["volume"] - df["volume"].rolling(100).mean()) / df["volume"].rolling(100).std().replace(0, np.nan)
    
    # Merge funding data
    if funding is not None and len(funding) > 0 and "funding_rate" in funding.columns:
        df_sorted = df.sort_values("timestamp")
        funding_sorted = funding.sort_values("timestamp")
        
        merged = pd.merge_asof(
            df_sorted, 
            funding_sorted[["timestamp", "funding_rate"]], 
            on="timestamp", 
            direction="backward"
        )
        
        df["funding_rate"] = merged["funding_rate"].values
        
        # Calculate funding z-score
        fr = df["funding_rate"]
        df["funding_zscore"] = (fr - fr.rolling(100).mean()) / fr.rolling(100).std().replace(0, np.nan)
    else:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
    
    return df


def compute_labels(feature_matrix: pd.DataFrame) -> pd.DataFrame:
    """Compute future return labels."""
    labels = pd.DataFrame(index=feature_matrix.index)
    close = feature_matrix["close"].values.astype(float)
    
    for horizon in [1, 3, 5, 10]:
        if len(close) > horizon:
            fut_ret = (close[horizon:] - close[:-horizon]) / close[:-horizon]
            pad = np.full(horizon, np.nan)
            labels[f"future_ret_{horizon}"] = np.concatenate([fut_ret, pad])
        else:
            labels[f"future_ret_{horizon}"] = np.nan
    
    return labels


def classify_regimes(feature_matrix: pd.DataFrame) -> pd.DataFrame:
    """Classify market regimes."""
    df = feature_matrix.copy()
    
    # Trend regime
    if "trend_20" in df.columns:
        trend = df["trend_20"].fillna(0)
        df["trend_regime"] = np.where(
            trend > 0.01, "trend_up",
            np.where(trend < -0.01, "trend_down", "range")
        )
    else:
        df["trend_regime"] = "range"
    
    # Volatility regime
    if "vol_20" in df.columns and "vol_60" in df.columns:
        vol_short = df["vol_20"].fillna(0)
        vol_long = df["vol_60"].fillna(0)
        df["vol_regime"] = np.where(
            vol_short > vol_long * 1.2, "high_vol",
            np.where(vol_short < vol_long * 0.8, "low_vol", "normal_vol")
        )
    else:
        df["vol_regime"] = "normal_vol"
    
    # Funding regime
    if "funding_zscore" in df.columns:
        fr_z = df["funding_zscore"]
        df["funding_regime"] = np.where(
            fr_z > 1.5, "extreme_positive",
            np.where(
                fr_z > 0.5, "positive",
                np.where(
                    fr_z < -1.5, "extreme_negative",
                    np.where(fr_z < -0.5, "negative", "neutral")
                )
            )
        )
    else:
        df["funding_regime"] = "neutral"
    
    return df


def compute_single_ic(feature_vals: np.ndarray, label_vals: np.ndarray) -> Dict:
    """Compute single IC pair."""
    mask = ~(np.isnan(feature_vals) | np.isnan(label_vals))
    f = feature_vals[mask]
    l = label_vals[mask]
    n = len(f)
    
    if n < 30:
        return {
            "ic": np.nan, "rank_ic": np.nan,
            "p_value": np.nan, "rank_p_value": np.nan,
            "sample_count": n
        }
    
    ic, p_val = stats.pearsonr(f, l)
    rank_ic, rank_p = stats.spearmanr(f, l)
    
    return {
        "ic": ic,
        "rank_ic": rank_ic,
        "p_value": p_val,
        "rank_p_value": rank_p,
        "sample_count": n
    }


def run_analysis(symbol: str, days: int = 365) -> Optional[List[ICResult]]:
    """Run complete analysis for a symbol."""
    print(f"\n{'='*80}")
    print(f"Analyzing {symbol} ({days} days)")
    print(f"{'='*80}")
    
    # Load data
    print("\n  Loading data...")
    klines = load_klines(symbol, days=days)
    if klines is None or len(klines) == 0:
        return None
    print(f"  Loaded {len(klines)} klines")
    
    funding = load_funding(symbol)
    if funding is not None:
        print(f"  Loaded {len(funding)} funding records")
    
    # Build feature matrix
    print("\n  Building feature matrix...")
    fm = build_simple_feature_matrix(klines, funding)
    print(f"  Feature matrix: {len(fm)} rows, {len(fm.columns)} columns")
    
    # Check funding data availability
    has_funding = fm["funding_rate"].notna().any()
    if not has_funding:
        print("  WARNING: No funding data available!")
    
    # Compute labels
    labels = compute_labels(fm)
    
    # Classify regimes
    fm = classify_regimes(fm)
    
    results = []
    
    # Unconditional IC
    print("\n  Calculating unconditional IC...")
    features = ["funding_rate", "funding_zscore"]
    label_cols = ["future_ret_1", "future_ret_3", "future_ret_5", "future_ret_10"]
    
    for feat in features:
        if feat not in fm.columns:
            continue
        for lab in label_cols:
            if lab not in labels.columns:
                continue
            ic_result = compute_single_ic(fm[feat].values, labels[lab].values)
            results.append(ICResult(
                feature=feat,
                label=lab,
                **ic_result
            ))
    
    # Conditional IC (focus on future_ret_5)
    print("\n  Calculating conditional IC...")
    regime_cols = ["trend_regime", "vol_regime", "funding_regime"]
    
    for feat in features:
        if feat not in fm.columns:
            continue
        lab = "future_ret_5"
        if lab not in labels.columns:
            continue
        
        for regime_col in regime_cols:
            if regime_col not in fm.columns:
                continue
            
            regimes = fm[regime_col].unique()
            for regime in regimes:
                mask = fm[regime_col] == regime
                feat_vals = fm[feat].values[mask]
                label_vals = labels[lab].values[mask]
                
                ic_result = compute_single_ic(feat_vals, label_vals)
                results.append(ICResult(
                    feature=feat,
                    label=lab,
                    regime=regime,
                    regime_col=regime_col,
                    **ic_result
                ))
    
    return results


def print_report(results: List[ICResult], symbol: str):
    """Print comprehensive report."""
    print(f"\n{'='*80}")
    print(f"FUNDING CONDITIONAL IC REPORT - {symbol}")
    print(f"{'='*80}")
    
    # Unconditional IC
    print(f"\n--- UNCONDITIONAL IC ---")
    print(f"{'Feature':<20} {'Label':<16} {'IC':>10} {'Rank IC':>10} {'p-value':>10} {'N':>8}")
    print(f"{'-'*78}")
    
    unconditional = [r for r in results if r.regime == "unconditional"]
    for r in sorted(unconditional, key=lambda x: (x.feature, x.label)):
        ic_str = f"{r.ic:.4f}" if not np.isnan(r.ic) else "nan"
        ric_str = f"{r.rank_ic:.4f}" if not np.isnan(r.rank_ic) else "nan"
        p_str = f"{r.p_value:.4f}" if not np.isnan(r.p_value) else "nan"
        sig = " **" if not np.isnan(r.p_value) and r.p_value < 0.01 else \
              " *" if not np.isnan(r.p_value) and r.p_value < 0.05 else ""
        print(f"{r.feature:<20} {r.label:<16} {ic_str:>10} {ric_str:>10} {p_str:>10} {r.sample_count:>8}{sig}")
    
    # Conditional IC by regime
    regime_cols = ["trend_regime", "vol_regime", "funding_regime"]
    
    for regime_col in regime_cols:
        print(f"\n--- CONDITIONAL IC BY {regime_col.upper()} ---")
        print(f"{'Feature':<20} {'Regime':<20} {'IC':>10} {'Rank IC':>10} {'p-value':>10} {'N':>8}")
        print(f"{'-'*88}")
        
        conditional = [r for r in results if r.regime_col == regime_col]
        for r in sorted(conditional, key=lambda x: (x.feature, x.regime)):
            ic_str = f"{r.ic:.4f}" if not np.isnan(r.ic) else "nan"
            ric_str = f"{r.rank_ic:.4f}" if not np.isnan(r.rank_ic) else "nan"
            p_str = f"{r.p_value:.4f}" if not np.isnan(r.p_value) else "nan"
            sig = " **" if not np.isnan(r.p_value) and r.p_value < 0.01 else \
                  " *" if not np.isnan(r.p_value) and r.p_value < 0.05 else ""
            print(f"{r.feature:<20} {r.regime:<20} {ic_str:>10} {ric_str:>10} {p_str:>10} {r.sample_count:>8}{sig}")


def save_results(results: List[ICResult], symbol: str):
    """Save results to CSV."""
    data = []
    for r in results:
        data.append({
            "symbol": symbol,
            "feature": r.feature,
            "label": r.label,
            "regime": r.regime,
            "regime_col": r.regime_col,
            "ic": r.ic,
            "rank_ic": r.rank_ic,
            "p_value": r.p_value,
            "rank_p_value": r.rank_p_value,
            "sample_count": r.sample_count
        })
    
    df = pd.DataFrame(data)
    output_path = REPORTS_DIR / f"p0_funding_ic_{symbol}.csv"
    df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="P0 Funding Conditional IC Analysis")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--days", type=int, default=365)
    
    args = parser.parse_args()
    
    results = run_analysis(args.symbol, args.days)
    
    if results:
        print_report(results, args.symbol)
        save_results(results, args.symbol)
        
        # Check for other symbols if we have data
        # Try ETCUSDT, SOLUSDT, ZECUSDT
        other_symbols = ["ETCUSDT", "SOLUSDT", "ZECUSDT"]
        for sym in other_symbols:
            try:
                other_results = run_analysis(sym, args.days)
                if other_results:
                    print_report(other_results, sym)
                    save_results(other_results, sym)
            except Exception as e:
                print(f"\nError analyzing {sym}: {e}")
    else:
        print("\nNo results generated.")


if __name__ == "__main__":
    main()
