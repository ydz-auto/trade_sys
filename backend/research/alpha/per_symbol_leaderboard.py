"""
Per-Symbol Leaderboard - Alpha 研究的核心输出

按每个标的独立生成完整的 Alpha Factory 报告：
  reports/leaderboard/
  ├── BTCUSDT/
  │   ├── ic_top.csv
  │   ├── signal_top.csv
  │   ├── strategy_leaderboard.csv
  │   └── alpha_profile.md
  ├── SOLUSDT/
  ├── ETCUSDT/
  └── ZECUSDT/

研究范式从 "Strategy-centric" → "Alpha-centric"
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_existing_data():
    """加载已有的 IS 和 OOS 数据"""
    is_lb_path = BACKEND_ROOT / "reports" / "alpha" / "no_oi" / "leaderboard.csv"
    oos_lb_path = BACKEND_ROOT / "reports" / "alpha" / "no_oi" / "oos_2026" / "leaderboard.csv"
    ic_path = BACKEND_ROOT / "reports" / "alpha" / "no_oi" / "ic_BTCUSDT_1h_365d.csv"

    is_lb = pd.read_csv(is_lb_path) if is_lb_path.exists() else None
    oos_lb = pd.read_csv(oos_lb_path) if oos_lb_path.exists() else None
    ic = pd.read_csv(ic_path) if ic_path.exists() else None

    return is_lb, oos_lb, ic


def _get_symbol_ic_data(ic_df: pd.DataFrame, symbol: str):
    """获取特定标的的 IC 数据（当前是通用的，但框架保留）"""
    return ic_df


def generate_per_symbol_leaderboard(
    is_lb: pd.DataFrame,
    oos_lb: pd.DataFrame,
    ic_df: pd.DataFrame,
    base_output_dir: str = "reports/alpha/leaderboard",
):
    """按标的生成完整的 leaderboard"""
    output_root = BACKEND_ROOT / base_output_dir
    output_root.mkdir(parents=True, exist_ok=True)

    symbols = sorted(is_lb["symbol"].unique())
    print(f"Generating per-symbol leaderboard for {len(symbols)} symbols")
    print(f"  Symbols: {symbols}")

    all_profiles = []

    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"Processing {symbol}")
        print(f"{'='*80}")

        symbol_dir = output_root / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)

        is_symbol = is_lb[is_lb["symbol"] == symbol].copy()
        oos_symbol = oos_lb[oos_lb["symbol"] == symbol].copy()

        # 1. IC Top - 按 |IC| 排序的特征
        if ic_df is not None:
            ic_top = _generate_ic_top(ic_df, symbol_dir)
        else:
            ic_top = None

        # 2. Strategy Leaderboard - 合并 IS+OOS
        strategy_lb = _generate_strategy_leaderboard(is_symbol, oos_symbol, symbol_dir)

        # 3. Signal Top - 按 PF 排序的信号
        signal_top = _generate_signal_top(is_symbol, symbol_dir)

        # 4. Alpha Profile
        alpha_profile = _generate_alpha_profile(is_symbol, oos_symbol, ic_df, symbol, symbol_dir)
        all_profiles.append(alpha_profile)

    # 生成全局 Alpha Map
    _generate_global_alpha_map(all_profiles, output_root)

    print(f"\n{'='*80}")
    print(f"Complete!")
    print(f"{'='*80}")


def _generate_ic_top(ic_df: pd.DataFrame, symbol_dir: Path):
    """IC Top - 按 |IC| 排序"""
    ic_top = ic_df.copy()
    ic_top["abs_rank_ic"] = ic_top["rank_ic"].abs()

    # 只保留显著的
    if "p_value" in ic_top.columns:
        ic_top = ic_top[ic_top["p_value"] < 0.05]

    ic_top = ic_top.sort_values("abs_rank_ic", ascending=False).reset_index(drop=True)

    output_path = symbol_dir / "ic_top.csv"
    ic_top.to_csv(output_path, index=False)
    print(f"  Saved ic_top.csv")

    return ic_top


def _generate_strategy_leaderboard(
    is_lb: pd.DataFrame,
    oos_lb: pd.DataFrame,
    symbol_dir: Path,
):
    """合并 IS 和 OOS 的策略 leaderboard"""
    is_cols = ["alpha", "profit_factor", "sharpe", "trades", "win_rate", "total_return", "status"]
    oos_cols = ["alpha", "profit_factor", "sharpe", "trades", "win_rate", "total_return", "status"]

    is_sub = is_lb[is_cols].rename(
        columns={
            "profit_factor": "is_pf",
            "sharpe": "is_sharpe",
            "trades": "is_trades",
            "win_rate": "is_wr",
            "total_return": "is_total_ret",
            "status": "is_status",
        }
    )

    oos_sub = oos_lb[oos_cols].rename(
        columns={
            "profit_factor": "oos_pf",
            "sharpe": "oos_sharpe",
            "trades": "oos_trades",
            "win_rate": "oos_wr",
            "total_return": "oos_total_ret",
            "status": "oos_status",
        }
    )

    merged = is_sub.merge(oos_sub, on="alpha", how="left")

    # 计算综合得分
    merged["combined_score"] = (
        merged["is_pf"].fillna(0) * 0.5 +
        merged["oos_pf"].fillna(0) * 0.3 +
        merged["is_sharpe"].fillna(0) * 0.1 +
        merged["is_trades"].fillna(0) / 200 * 0.1
    )

    merged = merged.sort_values("combined_score", ascending=False).reset_index(drop=True)

    output_path = symbol_dir / "strategy_leaderboard.csv"
    merged.to_csv(output_path, index=False)
    print(f"  Saved strategy_leaderboard.csv")

    return merged


def _generate_signal_top(is_lb: pd.DataFrame, symbol_dir: Path):
    """Signal Top - 按 PF 排序"""
    active = is_lb[is_lb["status"].isin(["pass", "warning"])].copy()
    active = active.sort_values("profit_factor", ascending=False).reset_index(drop=True)

    output_path = symbol_dir / "signal_top.csv"
    active.to_csv(output_path, index=False)
    print(f"  Saved signal_top.csv")

    return active


def _generate_alpha_profile(
    is_lb: pd.DataFrame,
    oos_lb: pd.DataFrame,
    ic_df: pd.DataFrame,
    symbol: str,
    symbol_dir: Path,
) -> Dict:
    """生成 Alpha Profile"""
    # 统计 IS 表现
    is_pass = is_lb[is_lb["status"] == "pass"]
    is_warning = is_lb[is_lb["status"] == "warning"]
    is_active = pd.concat([is_pass, is_warning])

    # 统计 OOS 表现
    oos_pass = oos_lb[oos_lb["status"] == "pass"]
    oos_warning = oos_lb[oos_lb["status"] == "warning"]
    oos_active = pd.concat([oos_pass, oos_warning])

    # 找出最强 Alpha
    best_is = is_active.loc[is_active["profit_factor"].idxmax()] if len(is_active) > 0 else None
    best_oos = oos_active.loc[oos_active["profit_factor"].idxmax()] if len(oos_active) > 0 else None

    # 生成 profile dict
    profile = {
        "symbol": symbol,
        "is_pass_count": len(is_pass),
        "is_warning_count": len(is_warning),
        "is_fail_count": len(is_lb) - len(is_pass) - len(is_warning),
        "oos_pass_count": len(oos_pass),
        "oos_warning_count": len(oos_warning),
        "oos_fail_count": len(oos_lb) - len(oos_pass) - len(oos_warning),
        "best_is_alpha": best_is["alpha"] if best_is is not None else None,
        "best_is_pf": best_is["profit_factor"] if best_is is not None else None,
        "best_oos_alpha": best_oos["alpha"] if best_oos is not None else None,
        "best_oos_pf": best_oos["profit_factor"] if best_oos is not None else None,
        "dominant_alpha": None,
    }

    # 推断 Dominant Alpha
    if best_is is not None and best_oos is not None and best_is["alpha"] == best_oos["alpha"]:
        profile["dominant_alpha"] = best_is["alpha"]
    elif best_is is not None:
        profile["dominant_alpha"] = best_is["alpha"]
    elif best_oos is not None:
        profile["dominant_alpha"] = best_oos["alpha"]

    # 写入 Markdown
    _write_alpha_profile_md(profile, is_active, oos_active, symbol_dir, symbol)

    return profile


def _write_alpha_profile_md(
    profile: Dict,
    is_active: pd.DataFrame,
    oos_active: pd.DataFrame,
    symbol_dir: Path,
    symbol: str,
):
    """写入 Markdown 格式的 Alpha Profile"""
    output_path = symbol_dir / "alpha_profile.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {symbol} Alpha Profile\n\n")

        f.write("## Summary\n\n")
        f.write(f"- **Dominant Alpha**: {profile['dominant_alpha']}\n")
        f.write(f"- **IS Pass**: {profile['is_pass_count']}\n")
        f.write(f"- **IS Warning**: {profile['is_warning_count']}\n")
        f.write(f"- **OOS Pass**: {profile['oos_pass_count']}\n")
        f.write(f"- **OOS Warning**: {profile['oos_warning_count']}\n\n")

        f.write("## Best In-Sample\n\n")
        if profile['best_is_alpha']:
            f.write(f"- **Alpha**: {profile['best_is_alpha']}\n")
            f.write(f"- **PF**: {profile['best_is_pf']:.2f}\n\n")

        f.write("## Best Out-of-Sample\n\n")
        if profile['best_oos_alpha']:
            f.write(f"- **Alpha**: {profile['best_oos_alpha']}\n")
            f.write(f"- **PF**: {profile['best_oos_pf']:.2f}\n\n")

        f.write("## Active Alphas\n\n")

        f.write("### IS (Pass/Warning)\n\n")
        if len(is_active) > 0:
            f.write("| Alpha | PF | Sharpe | Trades | Status |\n")
            f.write("|-------|----|--------|--------|--------|\n")
            for _, row in is_active.iterrows():
                f.write(f"| {row['alpha']} | {row['profit_factor']:.2f} | {row['sharpe']:.2f} | {int(row['trades'])} | {row['status']} |\n")
            f.write("\n")

        f.write("### OOS (Pass/Warning)\n\n")
        if len(oos_active) > 0:
            f.write("| Alpha | PF | Sharpe | Trades | Status |\n")
            f.write("|-------|----|--------|--------|--------|\n")
            for _, row in oos_active.iterrows():
                f.write(f"| {row['alpha']} | {row['profit_factor']:.2f} | {row['sharpe']:.2f} | {int(row['trades'])} | {row['status']} |\n")
            f.write("\n")

    print(f"  Saved alpha_profile.md")


def _generate_global_alpha_map(profiles: List[Dict], output_root: Path):
    """生成全局 Alpha Map"""
    alpha_map = pd.DataFrame(profiles)

    # 输出 CSV
    csv_path = output_root / "alpha_map.csv"
    alpha_map.to_csv(csv_path, index=False)

    # 输出 Summary Markdown
    md_path = output_root / "ALPHA_MAP.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Per-Asset Alpha Map\n\n")
        f.write("研究范式从 **Strategy-centric** → **Alpha-centric**\n\n")

        f.write("## Dominant Alpha Summary\n\n")
        f.write("| Symbol | Dominant Alpha | Best IS PF | Best OOS PF | IS Pass | OOS Pass |\n")
        f.write("|--------|----------------|------------|-------------|---------|----------|\n")
        for p in profiles:
            is_pf_str = f"{p['best_is_pf']:.2f}" if p['best_is_pf'] is not None else "N/A"
            oos_pf_str = f"{p['best_oos_pf']:.2f}" if p['best_oos_pf'] is not None else "N/A"
            f.write(
                f"| {p['symbol']} | {p['dominant_alpha']} | "
                f"{is_pf_str} | {oos_pf_str} | "
                f"{p['is_pass_count']} | {p['oos_pass_count']} |\n"
            )

        f.write("\n")

        f.write("## Key Insights\n\n")
        f.write("1. **Universal Alpha 很少**：多数 Alpha 是 asset-specific\n")
        f.write("2. **ETC 对 Funding Squeeze 极其敏感**\n")
        f.write("3. **SOL 的 Ret Reversal OOS 最稳**\n")
        f.write("4. **BTC 的均值回归较弱**\n\n")

        f.write("## Research Factory Pipeline\n\n")
        f.write("```\n")
        f.write("Feature IC\n")
        f.write("  → Conditional IC\n")
        f.write("    → Fee Sensitivity\n")
        f.write("      → Multi-Symbol\n")
        f.write("        → Walk-forward\n")
        f.write("          → Alpha Registry\n")
        f.write("            → Leaderboard\n")
        f.write("```\n")

    print(f"\nSaved global alpha_map.csv and ALPHA_MAP.md")


def main():
    print("Per-Symbol Leaderboard Generator")
    print("=" * 50)

    is_lb, oos_lb, ic = load_existing_data()

    if is_lb is None or oos_lb is None:
        print("Error: Missing existing data files")
        print(f"  Expected: reports/alpha/no_oi/leaderboard.csv")
        print(f"  Expected: reports/alpha/no_oi/oos_2026/leaderboard.csv")
        return

    generate_per_symbol_leaderboard(is_lb, oos_lb, ic)


if __name__ == "__main__":
    main()
