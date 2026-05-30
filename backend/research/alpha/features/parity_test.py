"""
Feature Parity Test - 对比 research vs engine 特征计算一致性

通过标准：
- corr >= 0.999（如果有足够数据）
- max_abs_diff <= 1e-9
- missing_rate_diff <= 0.001

用法：
    python -m research.alpha.features.parity_test \
        --symbol BTCUSDT \
        --timeframe 1h \
        --days 90 \
        --output reports/feature_parity/parity_report.csv
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_baseline(symbol: str, timeframe: str, days: int) -> Tuple[pd.DataFrame, Dict]:
    """加载 baseline 数据和 metadata"""
    baseline_dir = BACKEND_ROOT / "reports" / "feature_parity" / "baseline"
    metadata_dir = BACKEND_ROOT / "reports" / "feature_parity" / "metadata"

    filename = f"{symbol}_{timeframe}_{days}d"
    parquet_path = baseline_dir / f"{filename}.parquet"
    metadata_path = metadata_dir / f"{filename}_metadata.json"

    if not parquet_path.exists():
        raise FileNotFoundError(f"Baseline parquet not found: {parquet_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Baseline metadata not found: {metadata_path}")

    df = pd.read_parquet(parquet_path)
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return df, metadata


def get_current_from_research(symbol: str, timeframe: str, days: int, exchange: str = "binance") -> pd.DataFrame:
    """从 FeatureEngine 获取 research 源特征矩阵"""
    from engines.compute.feature.feature_engine import FeatureEngine
    engine = FeatureEngine(source="research")
    df = engine.build_historical_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    return df


def get_current_from_engine(symbol: str, timeframe: str, days: int, exchange: str = "binance") -> pd.DataFrame:
    """从 FeatureEngine 获取 engine 源特征矩阵"""
    from engines.compute.feature.feature_engine import FeatureEngine
    engine = FeatureEngine(source="engine")
    df = engine.build_historical_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    return df


def get_current_from_feature_engine(symbol: str, timeframe: str, days: int, exchange: str = "binance", source: str = "research") -> pd.DataFrame:
    """从 FeatureEngine 获取当前特征矩阵（统一入口）"""
    if source == "research":
        return get_current_from_research(symbol, timeframe, days, exchange)
    else:
        return get_current_from_engine(symbol, timeframe, days, exchange)


def compute_column_checksum(series: pd.Series) -> str:
    """计算列的 SHA256 checksum（与 export_feature_baseline 一致）"""
    import hashlib
    try:
        if series.dtype == "object" or series.dtype.name == "category" or "string" in str(series.dtype):
            data = series.dropna().astype(str).values
            hash_obj = hashlib.sha256(str(data).encode("utf-8"))
        else:
            data = series.dropna().fillna(0).astype(float).values
            hash_obj = hashlib.sha256(data.tobytes())
    except Exception:
        data = series.dropna().astype(str).values
        hash_obj = hashlib.sha256(str(data).encode("utf-8"))
    return hash_obj.hexdigest()[:16]


def compare_feature(
    col: str,
    baseline_series: pd.Series,
    current_series: pd.Series,
    corr_threshold: float = 0.999,
    max_abs_diff_threshold: float = 1e-9,
    missing_rate_diff_threshold: float = 0.001,
) -> Dict:
    """对比单个特征"""
    result = {"column": col}

    # 对齐索引
    baseline_series = baseline_series.sort_index()
    current_series = current_series.sort_index()
    common_idx = baseline_series.index.intersection(current_series.index)
    baseline_aligned = baseline_series.reindex(common_idx)
    current_aligned = current_series.reindex(common_idx)

    # 缺失率
    result["missing_rate_baseline"] = float(baseline_series.isna().sum() / len(baseline_series))
    result["missing_rate_current"] = float(current_series.isna().sum() / len(current_series))
    result["missing_rate_diff"] = float(abs(result["missing_rate_baseline"] - result["missing_rate_current"]))

    # 计算非 NaN 数据
    non_nan_mask = baseline_aligned.notna() & current_aligned.notna()
    baseline_valid = baseline_aligned[non_nan_mask]
    current_valid = current_aligned[non_nan_mask]

    if len(baseline_valid) > 0 and pd.api.types.is_numeric_dtype(baseline_valid):
        # 数值型特征计算 diff 和 corr
        abs_diff = np.abs(baseline_valid - current_valid)
        result["max_abs_diff"] = float(abs_diff.max()) if len(abs_diff) > 0 else 0.0
        result["mean_abs_diff"] = float(abs_diff.mean()) if len(abs_diff) > 0 else 0.0

        if len(baseline_valid) >= 2:
            try:
                result["corr"] = float(np.corrcoef(baseline_valid, current_valid)[0, 1])
            except (ValueError, FloatingPointError):
                result["corr"] = None
        else:
            result["corr"] = 1.0 if len(baseline_valid) == 1 and np.isclose(baseline_valid.iloc[0], current_valid.iloc[0]) else None

        # 判定
        max_diff_ok = result["max_abs_diff"] <= max_abs_diff_threshold
        missing_ok = result["missing_rate_diff"] <= missing_rate_diff_threshold

        if result["corr"] is not None and not pd.isna(result["corr"]):
            corr_ok = result["corr"] >= corr_threshold
            result["status"] = "PASS" if (corr_ok and max_diff_ok and missing_ok) else "FAIL"
        else:
            # 如果 corr 无法计算，只要 diff 都为 0 且 missing rate 一致也标记为 PASS
            result["status"] = "PASS" if (max_diff_ok and missing_ok) else "FAIL"
    else:
        # 非数值或全 NaN，只对比 checksum
        result["checksum_baseline"] = compute_column_checksum(baseline_series)
        result["checksum_current"] = compute_column_checksum(current_series)
        result["checksum_match"] = result["checksum_baseline"] == result["checksum_current"]

        result["corr"] = None
        result["max_abs_diff"] = None
        result["mean_abs_diff"] = None

        result["status"] = "PASS" if result["checksum_match"] else "FAIL"

    return result


def run_parity_test(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    baseline_metadata: Dict,
    symbol: str,
    timeframe: str,
    days: int,
) -> pd.DataFrame:
    """运行 parity 测试"""
    results = []

    # 对齐列
    common_cols = [col for col in baseline_df.columns if col in current_df.columns]
    missing_from_current = [col for col in baseline_df.columns if col not in current_df.columns]
    extra_in_current = [col for col in current_df.columns if col not in baseline_df.columns]

    print(f"\n=== Parity Test Summary ===")
    print(f"Symbol: {symbol}, Timeframe: {timeframe}, Days: {days}")
    print(f"Baseline columns: {len(baseline_df.columns)}")
    print(f"Current columns: {len(current_df.columns)}")
    print(f"Common columns: {len(common_cols)}")
    if missing_from_current:
        print(f"Missing from current: {len(missing_from_current)} columns")
    if extra_in_current:
        print(f"Extra in current: {len(extra_in_current)} columns")

    # 对比共同列
    for col in common_cols:
        result = compare_feature(col, baseline_df[col], current_df[col])
        result["symbol"] = symbol
        result["timeframe"] = timeframe
        result["days"] = days
        results.append(result)

    # 添加缺失列（标记为 FAIL）
    for col in missing_from_current:
        results.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "column": col,
            "status": "FAIL",
            "note": "Column missing in current",
        })

    # 转为 DataFrame
    report_df = pd.DataFrame(results)
    return report_df


def print_summary(report_df: pd.DataFrame):
    """打印总结"""
    # 第一批迁移的核心特征
    CORE_FEATURES = [
        "ret_1", "ret_3", "ret_5", "ret_10", 
        "volume_zscore", 
        "vol_20", 
        "drawdown_from_high", "distance_from_high", 
        "sma_20", "ma_20",
        "rsi_14"
    ]
    
    print(f"\n=== Parity Test Results ===")
    pass_count = (report_df["status"] == "PASS").sum()
    fail_count = (report_df["status"] == "FAIL").sum()
    total_count = len(report_df)
    print(f"Total: {total_count}")
    print(f"PASS:  {pass_count}")
    print(f"FAIL:  {fail_count}")
    print(f"PASS %: {(pass_count / total_count * 100):.2f}%")
    
    # 核心特征专门总结
    core_df = report_df[report_df["column"].isin(CORE_FEATURES)].copy()
    if len(core_df) > 0:
        core_pass = (core_df["status"] == "PASS").sum()
        core_total = len(core_df)
        print(f"\n=== Core Features Summary ===")
        print(f"Core Total: {core_total}")
        print(f"Core PASS:  {core_pass}")
        print(f"Core FAIL:  {core_total - core_pass}")
        
        # 显示核心特征的详细结果
        display_cols = [c for c in ["column", "corr", "max_abs_diff", "missing_rate_diff", "status", "note"] if c in core_df.columns]
        print("\nCore Features Details:")
        print(core_df[display_cols].to_string(index=False))

    if fail_count > 0:
        print(f"\n=== All FAIL Details ===")
        fail_df = report_df[report_df["status"] == "FAIL"]
        # 只打印关键列
        display_cols = [c for c in ["column", "corr", "max_abs_diff", "missing_rate_diff", "status", "note"] if c in fail_df.columns]
        print(fail_df[display_cols].to_string(index=False))


def main():
    parser = argparse.ArgumentParser(
        description="Feature Parity Test - 对比 research vs engine 特征计算一致性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
通过标准：
  - corr >= 0.999（如果有足够数据）
  - max_abs_diff <= 1e-9
  - missing_rate_diff <= 0.001

用法：
  python -m research.alpha.features.parity_test --symbol BTCUSDT --timeframe 1h --days 90
        """,
    )

    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol (default: BTCUSDT)")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe (default: 1h)")
    parser.add_argument("--days", type=int, default=90, help="Number of days (default: 90)")
    parser.add_argument("--exchange", type=str, default="binance", help="Exchange (default: binance)")
    parser.add_argument("--output", type=str, default="reports/feature_parity/parity_report.csv", help="Output path for parity report CSV")
    parser.add_argument("--compare-sources", action="store_true", help="Also compare FeatureEngine source='research' vs source='engine'")

    args = parser.parse_args()

    print("=== Loading Baseline ===")
    baseline_df, baseline_metadata = load_baseline(args.symbol, args.timeframe, args.days)

    print("\n=== Getting Current from Research (Direct) ===")
    current_research_df = get_current_from_research(args.symbol, args.timeframe, args.days, args.exchange)

    print("\n=== Getting Current from FeatureEngine (source='research') ===")
    current_fe_research_df = get_current_from_feature_engine(args.symbol, args.timeframe, args.days, args.exchange, source="research")

    print("\n=== Getting Current from FeatureEngine (source='engine') ===")
    current_fe_engine_df = get_current_from_feature_engine(args.symbol, args.timeframe, args.days, args.exchange, source="engine")

    print("\n=== Running Parity Test (Baseline vs FeatureEngine Research) ===")
    parity_df = run_parity_test(
        baseline_df=baseline_df,
        current_df=current_fe_research_df,
        baseline_metadata=baseline_metadata,
        symbol=args.symbol,
        timeframe=args.timeframe,
        days=args.days,
    )

    # 保存主要报告
    output_path = BACKEND_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    parity_df.to_csv(output_path, index=False)
    print(f"\nMain report saved to: {output_path}")

    print_summary(parity_df)

    # 如果需要对比两个 source
    if args.compare_sources:
        print("\n" + "="*60)
        print("=== Comparing FeatureEngine source='research' vs source='engine' ===")
        parity_fe_df = run_parity_test(
            baseline_df=current_fe_research_df,
            current_df=current_fe_engine_df,
            baseline_metadata={},
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
        )

        fe_output_path = BACKEND_ROOT / args.output.replace(".csv", "_fe_sources.csv")
        parity_fe_df.to_csv(fe_output_path, index=False)
        print(f"\nFeatureEngine sources comparison report saved to: {fe_output_path}")

        print_summary(parity_fe_df)

    # 返回退出码
    pass_count = (parity_df["status"] == "PASS").sum()
    total_count = len(parity_df)
    if pass_count == total_count:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
