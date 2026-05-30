"""
Registry Consistency Audit

检查 AlphaRegistry 与代码中实际使用的 strategy/feature 之间的断链。

检查项：
1. AlphaRegistry 注册完整性
2. Pipeline 引用的 strategy 是否全部注册
3. Registry 中引用的 feature 是否在 feature matrix 中存在
4. short_exhaustion family 断链检测
5. blocked strategy 状态确认

用法：
    python registry_audit.py
"""

import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

OUTPUT_DIR = BACKEND_ROOT / "reports" / "feature_parity" / "registry_audit"


def audit_registry():
    from research.alpha.registry.alpha_registry import AlphaRegistry, AlphaDefinition

    all_strategies = AlphaRegistry.list_all()
    active_strategies = AlphaRegistry.get_active()

    print("=" * 70)
    print("REGISTRY CONSISTENCY AUDIT")
    print("=" * 70)
    print()

    print(f"Total registered: {len(all_strategies)}")
    print(f"Active:           {len(active_strategies)}")
    print(f"Blocked:          {len(all_strategies) - len(active_strategies)}")
    print()

    registered_names = {s.name for s in all_strategies}
    active_names = {s.name for s in active_strategies}

    print("-" * 70)
    print("1. REGISTERED STRATEGIES")
    print("-" * 70)
    for s in all_strategies:
        status_icon = "🟢" if s.status == "active" else "🔴"
        dir_icon = "L" if s.direction == "long" else "S" if s.direction == "short" else "B"
        combo = f"+combo({s.combo_logic})" if s.combo_logic else ""
        print(f"  {status_icon} {s.name:<40} [{dir_icon}] {s.primary_feature:<25} {combo}")
    print()

    print("-" * 70)
    print("2. PIPELINE_DIFF RUNNER REFERENCED STRATEGIES")
    print("-" * 70)
    pipeline_strategies = [
        "ret_5_reversal",
        "drawdown_dip_buying",
        "funding_extreme_reversal",
        "volatility_panic_reversal",
        "short_exhaustion",
    ]
    missing_from_registry = []
    for name in pipeline_strategies:
        if name in registered_names:
            print(f"  ✅ {name:<40} registered")
        else:
            print(f"  ❌ {name:<40} NOT REGISTERED")
            missing_from_registry.append(name)
    print()

    print("-" * 70)
    print("3. SHORT_EXHAUSTION FAMILY AUDIT")
    print("-" * 70)

    short_family_names = [
        "short_exhaustion",
        "ret_5_positive_reversal",
        "distance_from_high_short",
        "parabolic_runup",
        "parabolic_runup_vol_filter",
        "parabolic_runup_ma_filter",
        "parabolic_runup_breakout_filter",
        "parabolic_runup_combined",
        "volume_climax_short",
        "breakout_failure",
        "crowded_long_reversal",
        "parabolic_blowoff",
        "failed_breakout",
        "trend_exhaustion",
        "funding_trap_short",
    ]

    short_registered = []
    short_missing = []
    for name in short_family_names:
        if name in registered_names:
            s = AlphaRegistry.get(name)
            short_registered.append(name)
            print(f"  ✅ {name:<40} direction={s.direction}")
        else:
            short_missing.append(name)
            print(f"  ❌ {name:<40} NOT REGISTERED")

    print()
    print(f"  Short family: {len(short_registered)}/{len(short_family_names)} registered")
    if short_missing:
        print(f"  ⚠️  Missing: {short_missing}")
    print()

    print("-" * 70)
    print("4. FEATURE AVAILABILITY CHECK")
    print("-" * 70)

    all_referenced_features: Set[str] = set()
    feature_to_strategies: Dict[str, List[str]] = {}
    for s in all_strategies:
        for feat in s.features:
            all_referenced_features.add(feat)
            feature_to_strategies.setdefault(feat, []).append(s.name)

    from research.alpha.features.matrix import build_feature_matrix
    print("  Building BTCUSDT feature matrix for feature availability check...")
    sample_df = build_feature_matrix(symbol="BTCUSDT", exchange="binance", days=10, timeframe="1h")
    available_features = set(sample_df.columns)

    missing_features = []
    available_count = 0
    for feat in sorted(all_referenced_features):
        if feat in available_features:
            available_count += 1
            print(f"  ✅ {feat:<30} available")
        else:
            missing_features.append(feat)
            strategies_using = feature_to_strategies.get(feat, [])
            print(f"  ❌ {feat:<30} MISSING (used by: {strategies_using})")

    print()
    print(f"  Feature availability: {available_count}/{len(all_referenced_features)}")
    if missing_features:
        print(f"  ⚠️  Missing features: {missing_features}")
    print()

    print("-" * 70)
    print("5. BLOCKED STRATEGIES")
    print("-" * 70)
    blocked = [s for s in all_strategies if s.status == "blocked"]
    if blocked:
        for s in blocked:
            print(f"  🔴 {s.name:<40} reason: {s.blocked_reason}")
    else:
        print("  None")
    print()

    print("=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)

    issues = []

    if missing_from_registry:
        issues.append(f"CRITICAL: {missing_from_registry} referenced in pipeline but NOT registered")
    if short_missing:
        issues.append(f"HIGH: short_exhaustion family missing: {short_missing}")
    if missing_features:
        issues.append(f"HIGH: features referenced by registry but not in matrix: {missing_features}")

    if not issues:
        print("  ✅ No issues found")
    else:
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "audit_report.txt", "w", encoding="utf-8") as f:
        f.write("Registry Consistency Audit Report\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total registered: {len(all_strategies)}\n")
        f.write(f"Active: {len(active_strategies)}\n")
        f.write(f"Blocked: {len(blocked)}\n\n")
        if missing_from_registry:
            f.write(f"MISSING FROM REGISTRY: {missing_from_registry}\n")
        if short_missing:
            f.write(f"SHORT FAMILY MISSING: {short_missing}\n")
        if missing_features:
            f.write(f"MISSING FEATURES: {missing_features}\n")
        if not issues:
            f.write("No issues found.\n")

    print(f"Report saved to: {OUTPUT_DIR / 'audit_report.txt'}")

    return {
        "missing_from_registry": missing_from_registry,
        "short_missing": short_missing,
        "missing_features": missing_features,
        "total_registered": len(all_strategies),
        "total_active": len(active_strategies),
    }


if __name__ == "__main__":
    result = audit_registry()
