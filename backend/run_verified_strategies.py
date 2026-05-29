"""
只运行验证过的策略（做多 + 做空），生成 leaderboard 和 paper trading 配置
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from research.alpha.pipeline import AlphaPipeline
from research.alpha.leaderboard import Leaderboard
from research.alpha.paper_trading_config import generate_paper_trading_configs


def main():
    # 之前验证通过的做多策略
    long_strategies = [
        "ret_3_reversal",
        "ret_10_reversal",
        "trend_filter_long",
        "drawdown_dip_buying",
    ]
    
    # 新发现的做空策略
    short_strategies = [
        "ret_5_positive_reversal",
        "parabolic_runup",
    ]
    
    all_strategies = long_strategies + short_strategies
    
    print(f"总共有 {len(all_strategies)} 个验证过的策略")
    print(f"做多策略: {long_strategies}")
    print(f"做空策略: {short_strategies}")
    
    symbols = ["BTCUSDT", "ETCUSDT", "SOLUSDT", "ZECUSDT"]
    
    print(f"\n{'='*80}")
    print(f"运行验证过的策略 Pipeline")
    print(f"{'='*80}")
    
    pipeline = AlphaPipeline(
        symbols=symbols,
        timeframes=["1h"],
        days=365,
        fee_mode="both",
        holding_bars_list=[5, 10, 20],
        percentile_thresholds=[90, 95, 97],
        skip_walk_forward=False,
        skip_stability=False,
        output_dir="reports/alpha/verified_with_shorts",
        exchange="binance",
        exclude_sources=["oi", "liquidation"]
    )
    
    result = pipeline.run(all_strategies)
    
    print(f"\n{'='*80}")
    print(f"生成 Leaderboard")
    print(f"{'='*80}")
    
    leaderboard = Leaderboard(result)
    leaderboard.print_table()
    leaderboard.print_summary()
    
    csv_path = "reports/alpha/verified_with_shorts/leaderboard.csv"
    json_path = "reports/alpha/verified_with_shorts/leaderboard.json"
    leaderboard.save_csv(csv_path)
    leaderboard.save_json(json_path)
    
    print(f"Leaderboard CSV 已生成: {csv_path}")
    print(f"Leaderboard JSON 已生成: {json_path}")
    
    print(f"\n{'='*80}")
    print(f"生成 Paper Trading 配置 (Tier A+B，宽松模式)")
    print(f"{'='*80}")
    
    configs = generate_paper_trading_configs(
        result,
        output_dir="reports/alpha/verified_with_shorts/paper_trading",
        tiers=["A", "B"],
        require_strict=False
    )
    
    print(f"\n{'='*80}")
    print(f"完成！")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
