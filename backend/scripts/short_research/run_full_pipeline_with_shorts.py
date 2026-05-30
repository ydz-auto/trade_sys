"""
运行完整的 pipeline，包括做多和做空策略，生成 leaderboard 和 paper trading 配置
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from research.alpha.validation.pipeline import AlphaPipeline
from research.alpha.leaderboard import generate_leaderboard
from research.alpha.paper_trading_config import generate_paper_trading_config


def main():
    # 获取所有活跃策略
    from research.alpha.registry.alpha_registry import AlphaRegistry
    all_strategies = [s.name for s in AlphaRegistry.get_active()]
    
    print(f"总共有 {len(all_strategies)} 个活跃策略")
    print(f"策略列表: {all_strategies}")
    
    symbols = ["BTCUSDT", "ETCUSDT", "SOLUSDT", "ZECUSDT"]
    
    print(f"\n{'='*80}")
    print(f"运行完整 Pipeline")
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
        output_dir="reports/alpha/full_with_shorts",
        exchange="binance",
        exclude_sources=["oi", "liquidation"]
    )
    
    result = pipeline.run(all_strategies)
    
    print(f"\n{'='*80}")
    print(f"生成 Leaderboard")
    print(f"{'='*80}")
    
    leaderboard_path = generate_leaderboard(
        result,
        output_dir="reports/alpha/full_with_shorts"
    )
    
    print(f"Leaderboard 已生成: {leaderboard_path}")
    
    print(f"\n{'='*80}")
    print(f"生成 Paper Trading 配置 (严格模式)")
    print(f"{'='*80}")
    
    paper_config_path = generate_paper_trading_config(
        result,
        output_dir="reports/alpha/full_with_shorts",
        require_strict=True
    )
    
    print(f"Paper Trading 配置已生成: {paper_config_path}")
    
    print(f"\n{'='*80}")
    print(f"完成！")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
