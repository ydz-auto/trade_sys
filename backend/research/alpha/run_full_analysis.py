"""
完整Alpha分析流水线 - 一键运行所有步骤
步骤：
1. 特征可用性审计
2. READY特征批量IC分析
3. READY特征Signal Test
4. Leaderboard生成与输出
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.feature_availability_audit import (
    run_availability_audit,
    FeatureStatus,
)
from research.alpha.feature_matrix import build_feature_matrix
from research.alpha.ic_analysis import compute_ic_table, print_ic_table
from research.alpha.labels import compute_labels_from_df
from research.alpha.regime_analysis import classify_regime
from research.alpha.strategy_alpha_registry import (
    AlphaDefinition,
    AlphaRegistry,
)
from research.alpha.pipeline import AlphaPipeline
from research.alpha.leaderboard import Leaderboard


def run_full_analysis(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    timeframe: str = "1h",
    days: int = 90,
    output_dir: str = "reports/alpha",
    skip_walk_forward: bool = True,
    skip_stability: bool = True,
):
    """运行完整分析流程"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("完整Alpha分析流水线")
    print("=" * 80)
    print(f"Symbol: {symbol}")
    print(f"Exchange: {exchange}")
    print(f"Timeframe: {timeframe}")
    print(f"Days: {days}")
    print(f"Output: {output_path}")

    # 步骤1：特征可用性审计
    print("\n" + "=" * 80)
    print("步骤1：特征可用性审计")
    print("=" * 80)

    audit_df = run_availability_audit(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        days=days,
    )

    ready_features = audit_df[
        audit_df["status"] == FeatureStatus.READY
    ]["feature"].tolist()

    audit_file = output_path / f"feature_audit_{symbol}_{days}d_{timestamp}.csv"
    audit_df.to_csv(audit_file, index=False)
    print(f"\n✅ 特征可用性审计结果已保存到: {audit_file}")

    if len(ready_features) == 0:
        print("\n⚠️  没有READY特征！分析流水线停止。")
        return

    print(f"\n✅ 发现 {len(ready_features)} 个READY特征")
    for feat in ready_features[:20]:
        print(f"  - {feat}")
    if len(ready_features) > 20:
        print(f"  ... 还有 {len(ready_features)-20} 个")

    # 步骤2：准备数据和计算标签
    print("\n" + "=" * 80)
    print("步骤2：加载特征矩阵和计算标签")
    print("=" * 80)

    fm = build_feature_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    fm = classify_regime(fm)
    labels = compute_labels_from_df(fm)

    print(f"✅ 特征矩阵: {len(fm)} 行 x {len(fm.columns)} 列")
    print(f"✅ 标签已计算: {len(labels.columns)} 个标签")

    # 步骤3：批量IC分析
    print("\n" + "=" * 80)
    print("步骤3：READY特征批量IC分析")
    print("=" * 80)

    # 只对在特征矩阵中存在的特征进行IC分析
    available_ready = [f for f in ready_features if f in fm.columns]

    if len(available_ready) == 0:
        print("⚠️  READY特征没有在特征矩阵中发现！")
    else:
        ic_df = compute_ic_table(fm, labels, features=available_ready)

        if len(ic_df) > 0:
            print_ic_table(ic_df)

            ic_file = output_path / f"ic_analysis_{symbol}_{days}d_{timestamp}.csv"
            ic_df.to_csv(ic_file, index=False)
            print(f"\n✅ IC分析结果已保存到: {ic_file}")

            # 统计显著IC
            sig_count = len(ic_df[ic_df["p_value"] < 0.05])
            print(f"\n✅ 发现 {sig_count} 个显著IC（p<0.05）")

    # 步骤4：创建临时Alpha定义并运行Pipeline
    print("\n" + "=" * 80)
    print("步骤4：对READY特征运行Signal Test")
    print("=" * 80)

    # 首先保存当前的Registry状态
    original_registry = dict(AlphaRegistry._registry)

    # 为每个可用的READY特征创建临时Alpha定义
    temp_defs = []
    for feat in available_ready[:50]:  # 限制最大数量避免太慢
        feat_lower = feat.lower()
        direction = "both"

        if any(k in feat_lower for k in ["ret", "drawdown", "distance", "down"]):
            direction = "long"

        alpha_name = f"auto_{feat}"

        if alpha_name not in AlphaRegistry._registry:
            defn = AlphaDefinition(
                name=alpha_name,
                features=[feat],
                mode="reversal",
                direction=direction,
                primary_feature=feat,
                signal_direction_map={
                    feat: "negative_means_long" if direction == "long" else "positive_means_short"
                },
                status="active",
            )
            AlphaRegistry.register(defn)
            temp_defs.append(alpha_name)

    print(f"✅ 创建了 {len(temp_defs)} 个临时Alpha定义")

    # 还添加原始的active策略
    original_active = [d.name for d in AlphaRegistry.get_active() if not d.name.startswith("auto_")]

    # 运行Pipeline
    strategy_names = temp_defs + original_active
    print(f"✅ 运行Pipeline，策略数量: {len(strategy_names)}")

    pipeline = AlphaPipeline(
        symbols=[symbol],
        timeframes=[timeframe],
        days=days,
        fee_mode="taker",
        holding_bars_list=[5, 10, 20],
        percentile_thresholds=[90, 95],
        skip_walk_forward=skip_walk_forward,
        skip_stability=skip_stability,
        output_dir=output_dir,
        exchange=exchange,
    )

    pipeline_result = pipeline.run(strategy_names)

    # 步骤5：生成Leaderboard
    print("\n" + "=" * 80)
    print("步骤5：生成Leaderboard")
    print("=" * 80)

    lb = Leaderboard(pipeline_result)
    lb.print_summary()
    lb.print_table()

    lb_csv = output_path / f"leaderboard_{symbol}_{days}d_{timestamp}.csv"
    lb_json = output_path / f"leaderboard_{symbol}_{days}d_{timestamp}.json"
    lb.save_csv(str(lb_csv))
    lb.save_json(str(lb_json))

    print(f"\n✅ Leaderboard已保存到:")
    print(f"  CSV: {lb_csv}")
    print(f"  JSON: {lb_json}")

    # 恢复Registry
    AlphaRegistry._registry = original_registry

    print("\n" + "=" * 80)
    print("✅ 完整分析流程执行完毕！")
    print("=" * 80)

    return {
        "audit": audit_df,
        "ic": ic_df if 'ic_df' in locals() else None,
        "pipeline_result": pipeline_result,
        "output_dir": output_path,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="完整Alpha分析流水线 - 一键运行所有步骤"
    )
    parser.add_argument("--symbol", type=str, default="BTCUSDT",
                        help="交易对符号")
    parser.add_argument("--exchange", type=str, default="binance",
                        help="交易所名称")
    parser.add_argument("--timeframe", type=str, default="1h",
                        help="K线周期")
    parser.add_argument("--days", type=int, default=30,
                        help="回溯天数")
    parser.add_argument("--output-dir", type=str, default="reports/alpha",
                        help="输出目录")
    parser.add_argument("--skip-walk-forward", action="store_true", default=True,
                        help="跳过Walk-Forward测试")
    parser.add_argument("--skip-stability", action="store_true", default=True,
                        help="跳过参数稳定性测试")

    args = parser.parse_args()

    run_full_analysis(
        symbol=args.symbol,
        exchange=args.exchange,
        timeframe=args.timeframe,
        days=args.days,
        output_dir=args.output_dir,
        skip_walk_forward=args.skip_walk_forward,
        skip_stability=args.skip_stability,
    )


if __name__ == "__main__":
    main()
