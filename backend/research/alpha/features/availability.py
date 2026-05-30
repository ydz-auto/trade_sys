"""
Feature Availability Audit - 特征可用性审计

验证 Registry 中的 171 个 features 是否真的能被当前数据湖 + pipeline 实际产出。

输出表格：
  feature
  alpha_family
  category
  registered
  data_source_available
  extractor_available
  matrix_available
  sample_non_null_ratio
  status

状态定义：
  READY                    在 feature_matrix 中可用，且有非空样本
  IN_MATRIX_LOW_COVERAGE   在 feature_matrix 中可用，但非空率 < 50%
  REGISTERED_ONLY          有定义，但没有在 feature_matrix 中
  EXTRACTOR_NOT_CONNECTED  有 extractor 代码，但未接入 feature_matrix
  DATA_MISSING             数据源缺失
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import pandas as pd

from infrastructure.acceleration import AccelerationService
from infrastructure.acceleration.memory_optimizer import MemoryOptimizer

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------- 状态枚举 ----------

class FeatureStatus:
    READY = "READY"
    IN_MATRIX_LOW_COVERAGE = "IN_MATRIX_LOW_COVERAGE"
    REGISTERED_ONLY = "REGISTERED_ONLY"
    EXTRACTOR_NOT_CONNECTED = "EXTRACTOR_NOT_CONNECTED"
    DATA_MISSING = "DATA_MISSING"


# ---------- 数据湖可用性检查 ----------

def _load_single_source(source_name, exchange, symbol, exclude_set):
    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
    reader = FileDataLakeReader()
    if source_name in exclude_set:
        return (source_name, False)
    try:
        if source_name == "kline":
            data = reader.load_klines(exchange=exchange, symbol=symbol, timeframe="1h")
        elif source_name == "funding":
            data = reader.load_funding(exchange=exchange, symbol=symbol)
        elif source_name == "oi":
            data = reader.load_oi(exchange=exchange, symbol=symbol)
        elif source_name == "trades":
            from infrastructure.storage.data_lake.trade_flow_writer import TradeFlowWriter
            tf = TradeFlowWriter()
            tf_data = tf.load(exchange, symbol, "1h")
            return (source_name, tf_data is not None and len(tf_data) > 0)
        else:
            return (source_name, False)
        return (source_name, data is not None and len(data) > 0)
    except Exception:
        return (source_name, False)


def check_data_source_availability(
    symbol: str,
    exchange: str,
    exclude_sources: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """
    检查当前数据湖有哪些数据源可用。

    Args:
        exclude_sources: 要排除的数据源列表，设置为 False

    Returns:
        {kline: True, funding: True, trades: False, liquidation: False, orderbook: False, oi: False}
    """
    exclude_sources = exclude_sources or []
    exclude_set = {s.lower().strip() for s in exclude_sources}

    service = AccelerationService()
    sources = ["kline", "funding", "oi", "trades", "liquidation", "orderbook"]
    tasks = [(s, exchange, symbol, exclude_set) for s in sources]
    results = service.parallel_map(_load_single_source, tasks, executor="thread")

    availability = {s: False for s in sources}
    availability["cross_market"] = False
    for source_name, available in results:
        availability[source_name] = available
    return availability


# ---------- Extractor 代码存在性检查 ----------

def check_extractor_available(feature_name: str) -> bool:
    """
    检查是否有对应的特征提取代码。

    基于 feature_name 猜测是否有对应的实现模块存在。
    """
    from domain.feature.registry import get_feature_def
    fdef = get_feature_def(feature_name)
    if not fdef:
        return False

    # 简单规则判断
    feature_lower = feature_name.lower()

    # Order Flow 相关特征
    if any(keyword in feature_lower for keyword in [
        "cvd", "cvd", "aggressive", "taker", "buy_sell", "trade_delta",
        "sweep", "whale", "trade_velocity", "large_trade"
    ]):
        return True

    # Liquidation 相关特征
    if any(keyword in feature_lower for keyword in [
        "liquidation", "cascade", "liq"
    ]):
        return True

    # Microstructure / Orderbook 相关特征
    if any(keyword in feature_lower for keyword in [
        "spread", "imbalance", "microprice", "vacuum", "wall", "spoof",
        "bid", "ask", "depth"
    ]):
        return True

    # OI 相关特征
    if any(keyword in feature_lower for keyword in [
        "oi_", "open_interest"
    ]):
        return True

    # Regime 相关特征
    if any(keyword in feature_lower for keyword in [
        "regime", "high_volatility", "low_liquidity", "risk"
    ]):
        return True

    # 基础特征（kline/funding）总是在
    base_features = [
        "open", "high", "low", "close", "volume", "ret_", "vol_", "atr",
        "range_pct", "volume_zscore", "trend_", "drawdown", "funding_",
        "distance_from_high", "parabolic", "funding_extreme"
    ]
    if any(feature_lower.startswith(prefix) for prefix in base_features):
        return True

    return False


# ---------- Audit 主逻辑 ----------

def run_availability_audit(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    timeframe: str = "1h",
    days: int = 90,
    exclude_sources: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    运行特征可用性审计。

    Returns:
        审计结果 DataFrame
    """
    from domain.feature.registry import FEATURE_REGISTRY, get_taxonomy_summary
    from research.alpha.features.matrix_adapter import get_research_feature_matrix

    print(f"Feature Availability Audit: {symbol} | {exchange} | {timeframe} | {days}d")
    print("=" * 70)

    # 1. 检查数据源可用性
    print("\n[1/5] Checking data source availability...")
    data_avail = check_data_source_availability(symbol, exchange, exclude_sources)
    print(f"  Data sources available:")
    for src, avail in data_avail.items():
        status = "✅" if avail else "❌"
        print(f"    {status} {src}")

    # 2. 加载 feature matrix
    print("\n[2/5] Loading feature matrix...")
    try:
        fm = get_research_feature_matrix(
            symbol=symbol,
            exchange=exchange,
            days=days,
            timeframe=timeframe,
            feature_source="research",
        )
        if exclude_sources:
            columns_to_keep = [
                col for col in fm.columns 
                if not any(source in col.lower() for source in exclude_sources)
            ]
            fm = fm[columns_to_keep]
        fm = MemoryOptimizer.optimize_dtypes(fm)
        matrix_available = True
        matrix_cols = set(fm.columns)
        total_bars = len(fm)
        print(f"  Loaded: {total_bars} bars, {len(matrix_cols)} feature columns")
    except Exception as e:
        print(f"  Error loading feature matrix: {e}")
        fm = None
        matrix_available = False
        matrix_cols = set()
        total_bars = 0

    # 3. 逐个 feature 审计
    print("\n[3/5] Auditing features...")
    results = []

    non_null_counts = {}
    non_null_ratios = {}
    if fm is not None and total_bars > 0:
        counts = fm.notna().sum()
        non_null_counts = counts.to_dict()
        non_null_ratios = (counts / total_bars).to_dict()

    for feature_name, fdef in FEATURE_REGISTRY.items():
        row = {
            "feature": feature_name,
            "alpha_family": fdef.alpha_family.value if fdef.alpha_family else "none",
            "category": fdef.category.value,
            "registered": True,
            "data_source_available": _check_required_sources(fdef, data_avail),
            "extractor_available": check_extractor_available(feature_name),
            "matrix_available": feature_name in matrix_cols,
            "sample_count": 0,
            "sample_non_null_ratio": 0.0,
            "status": FeatureStatus.REGISTERED_ONLY,
        }

        if feature_name in non_null_counts:
            row["sample_count"] = int(non_null_counts[feature_name])
            row["sample_non_null_ratio"] = non_null_ratios.get(feature_name, 0.0)

        # 状态判定
        if fm is not None and feature_name in fm.columns:
            if row["sample_non_null_ratio"] >= 0.5:
                row["status"] = FeatureStatus.READY
            else:
                row["status"] = FeatureStatus.IN_MATRIX_LOW_COVERAGE
        else:
            if check_extractor_available(feature_name):
                if row["data_source_available"]:
                    row["status"] = FeatureStatus.EXTRACTOR_NOT_CONNECTED
                else:
                    row["status"] = FeatureStatus.DATA_MISSING
            else:
                row["status"] = FeatureStatus.REGISTERED_ONLY

        results.append(row)

    # 4. 构建结果 DataFrame
    audit_df = pd.DataFrame(results)
    audit_df = audit_df.sort_values(["alpha_family", "status", "feature"]).reset_index(drop=True)

    # 5. 打印统计摘要
    print("\n[4/5] Generating summary...")
    _print_audit_summary(audit_df)

    print("\n[5/5] Audit complete.")
    print("=" * 70)

    audit_df = MemoryOptimizer.downcast_float(audit_df)

    return audit_df


def _check_required_sources(fdef, data_avail: Dict[str, bool]) -> bool:
    """
    检查 feature 所需的数据源是否都可用。
    """
    if not fdef.required_sources:
        return True

    for src in fdef.required_sources:
        src_lower = src.lower()
        if "kline" in src_lower:
            if not data_avail.get("kline", False):
                return False
        elif "funding" in src_lower:
            if not data_avail.get("funding", False):
                return False
        elif "trade" in src_lower or "aggtrade" in src_lower:
            if not data_avail.get("trades", False):
                return False
        elif "liquidation" in src_lower or "liq" in src_lower:
            if not data_avail.get("liquidation", False):
                return False
        elif "orderbook" in src_lower or "l2" in src_lower or "book" in src_lower:
            if not data_avail.get("orderbook", False):
                return False
        elif "open_interest" in src_lower or "oi" in src_lower:
            if not data_avail.get("oi", False):
                return False
        elif "cross_market" in src_lower or "cross" in src_lower:
            if not data_avail.get("cross_market", False):
                return False

    return True


def _print_audit_summary(audit_df: pd.DataFrame):
    """打印审计结果摘要。"""
    total = len(audit_df)
    status_counts = audit_df["status"].value_counts()

    print(f"\n{'Status':<25} {'Count':>6} {'Percent':>8}")
    print("-" * 40)
    for status in [
        FeatureStatus.READY,
        FeatureStatus.IN_MATRIX_LOW_COVERAGE,
        FeatureStatus.EXTRACTOR_NOT_CONNECTED,
        FeatureStatus.DATA_MISSING,
        FeatureStatus.REGISTERED_ONLY,
    ]:
        cnt = int(status_counts.get(status, 0))
        pct = cnt / total * 100
        print(f"{status:<25} {cnt:>6} {pct:>7.1f}%")

    # 按 Alpha Family 统计
    print(f"\nBy Alpha Family:")
    print("-" * 60)
    for family in sorted(audit_df["alpha_family"].unique()):
        family_df = audit_df[audit_df["alpha_family"] == family]
        ready_cnt = int((family_df["status"] == FeatureStatus.READY).sum())
        total_family = len(family_df)
        print(f"  {family:<20} {ready_cnt:>3} / {total_family:>3} READY")


# ---------- 便捷打印函数 ----------

def print_ready_features(audit_df: pd.DataFrame):
    """只打印 READY 状态的 features。"""
    ready_df = audit_df[audit_df["status"] == FeatureStatus.READY].copy()
    if len(ready_df) == 0:
        print("No READY features found.")
        return

    print(f"\n{'='*90}")
    print(f"READY Features ({len(ready_df)} total):")
    print(f"{'='*90}")

    for family in sorted(ready_df["alpha_family"].unique()):
        family_ready = ready_df[ready_df["alpha_family"] == family]
        print(f"\n[{family.upper()}]")
        for _, row in family_ready.iterrows():
            print(f"  {row['feature']:<30} coverage={row['sample_non_null_ratio']:.1%}")


# ---------- CLI ----------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Feature Availability Audit")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--show-ready", action="store_true", help="Only show READY features")
    parser.add_argument("--exclude-sources", type=str, default=None,
                        help="Comma-separated list of data sources to exclude (oi, liquidation, orderbook)")

    args = parser.parse_args()

    exclude_sources = None
    if args.exclude_sources:
        exclude_sources = [s.strip() for s in args.exclude_sources.split(",")]

    audit_df = run_availability_audit(
        symbol=args.symbol,
        exchange=args.exchange,
        timeframe=args.timeframe,
        days=args.days,
        exclude_sources=exclude_sources,
    )

    if args.show_ready:
        print_ready_features(audit_df)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audit_df.to_csv(output_path, index=False)
        print(f"\nSaved audit report to: {output_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()


__all__ = ["run_availability_audit", "print_ready_features", "FeatureStatus"]
