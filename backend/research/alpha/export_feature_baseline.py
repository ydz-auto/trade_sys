"""
Export Feature Baseline - 导出 research 特征矩阵 baseline

用途：
- 锁定当前 research.alpha.feature_matrix.py 的输出
- 作为后续特征迁移的对比基准
- 确保迁移前后特征值一致

使用方式：
    python -m research.alpha.export_feature_baseline --symbol BTCUSDT --days 90

输出：
- reports/feature_parity/baseline/{SYMBOL}_{TIMEFRAME}_{DAYS}d.parquet
- reports/feature_parity/metadata/{SYMBOL}_{TIMEFRAME}_{DAYS}d_metadata.json
- reports/feature_parity/metadata/baseline_manifest.json
"""

import sys
import hashlib
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.features.matrix import build_feature_matrix


def compute_column_checksum(series: pd.Series) -> str:
    """计算列的 SHA256 checksum"""
    try:
        if series.dtype == 'object' or series.dtype.name == 'category' or 'string' in str(series.dtype):
            data = series.dropna().astype(str).values
            hash_obj = hashlib.sha256(str(data).encode('utf-8'))
        else:
            data = series.dropna().fillna(0).astype(float).values
            hash_obj = hashlib.sha256(data.tobytes())
    except Exception:
        data = series.dropna().astype(str).values
        hash_obj = hashlib.sha256(str(data).encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def compute_feature_stats(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """计算每个特征列的统计信息"""
    stats = []
    for col in df.columns:
        if col == 'timestamp':
            continue
        series = df[col]
        missing_rate = series.isna().sum() / len(series)
        stats.append({
            'column': col,
            'missing_rate': round(float(missing_rate), 6),
            'checksum': compute_column_checksum(series),
            'dtype': str(series.dtype),
            'non_null_count': int(series.notna().sum()),
        })
    return stats


def export_single_baseline(
    symbol: str,
    timeframe: str = "1h",
    days: int = 90,
    exchange: str = "binance",
) -> Dict[str, Any]:
    """导出单个 symbol 的 baseline"""
    print(f"\n{'='*60}")
    print(f"Exporting baseline: {symbol} {timeframe} {days}d")
    print(f"{'='*60}")

    fm = build_feature_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )

    print(f"Feature matrix shape: {fm.shape}")
    print(f"Columns: {len(fm.columns)}")

    baseline_dir = BACKEND_ROOT / "reports" / "feature_parity" / "baseline"
    metadata_dir = BACKEND_ROOT / "reports" / "feature_parity" / "metadata"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{symbol}_{timeframe}_{days}d"
    parquet_path = baseline_dir / f"{filename}.parquet"
    metadata_path = metadata_dir / f"{filename}_metadata.json"

    fm.to_parquet(parquet_path, index=True)
    print(f"Saved: {parquet_path}")

    stats = compute_feature_stats(fm)
    metadata = {
        'symbol': symbol,
        'timeframe': timeframe,
        'days': days,
        'exchange': exchange,
        'exported_at': datetime.now().isoformat(),
        'source': 'research.alpha.features.matrix',
        'shape': {
            'rows': len(fm),
            'columns': len(fm.columns),
        },
        'columns': list(fm.columns),
        'features': stats,
    }

    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved: {metadata_path}")

    print_feature_summary(stats)

    return metadata


def print_feature_summary(stats: List[Dict[str, Any]]):
    """打印特征摘要"""
    print(f"\n{'Column':<40} {'Missing':>10} {'Checksum':>18} {'Dtype':<10}")
    print("-" * 80)
    for s in sorted(stats, key=lambda x: x['missing_rate'], reverse=True):
        print(f"{s['column']:<40} {s['missing_rate']:>10.4f} {s['checksum']:>18} {s['dtype']:<10}")


def generate_manifest(all_metadata: List[Dict[str, Any]]):
    """生成 baseline manifest"""
    manifest = {
        'version': '1.0',
        'created_at': datetime.now().isoformat(),
        'source': 'research.alpha.features.matrix',
        'total_symbols': len(all_metadata),
        'baselines': all_metadata,
    }

    manifest_path = BACKEND_ROOT / "reports" / "feature_parity" / "metadata" / "baseline_manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Manifest saved: {manifest_path}")
    print(f"Total baselines: {len(all_metadata)}")

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Export Feature Baseline - 锁定 research 特征矩阵输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m research.alpha.export_feature_baseline --symbol BTCUSDT --days 90
  python -m research.alpha.export_feature_baseline --symbol BTCUSDT --timeframe 4h --days 180
  python -m research.alpha.export_feature_baseline --symbol BTCUSDT,SOLUSDT --days 90
        """,
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1h",
        help="Timeframe (default: 1h)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days (default: 90)",
    )
    parser.add_argument(
        "--exchange",
        type=str,
        default="binance",
        help="Exchange (default: binance)",
    )

    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbol.split(",")]
    all_metadata = []

    for symbol in symbols:
        metadata = export_single_baseline(
            symbol=symbol,
            timeframe=args.timeframe,
            days=args.days,
            exchange=args.exchange,
        )
        all_metadata.append(metadata)

    generate_manifest(all_metadata)

    print(f"\n{'='*60}")
    print("P0 Baseline Export Complete!")
    print(f"{'='*60}")
    print("\nBaseline contract:")
    print(f"  - Source: research.alpha.features.matrix")
    print(f"  - Symbols: {', '.join(symbols)}")
    print(f"  - Timeframe: {args.timeframe}")
    print(f"  - Days: {args.days}")
    print(f"  - Location: reports/feature_parity/")
    print("\nVerification:")
    print(f"  - Columns exported: {all_metadata[0]['shape']['columns']}")
    print(f"  - Each column has: checksum, missing_rate")
    print(f"  - Manifest: reports/feature_parity/metadata/baseline_manifest.json")


if __name__ == "__main__":
    main()
