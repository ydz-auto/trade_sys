"""
策略参数优化和回测脚本

优化期：2024年12月及之前的数据
回测期：2025年1月到2026年4月的数据
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def run_optimization_and_backtest():
    """运行参数优化和回测"""
    from application.backtest_service import BacktestService
    
    service = BacktestService()
    await service.initialize()
    
    # 时间范围
    # 优化期：2024年1月 - 2024年12月
    opt_start = int(datetime(2024, 1, 1).timestamp() * 1000)
    opt_end = int(datetime(2024, 12, 31, 23, 59, 59).timestamp() * 1000)
    
    # 回测期：2025年1月 - 2026年4月
    bt_start = int(datetime(2025, 1, 1).timestamp() * 1000)
    bt_end = int(datetime(2026, 4, 30, 23, 59, 59).timestamp() * 1000)
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    strategies = ["rsi_oversold", "rsi_overbought", "macd_cross", "sma_cross", "ema_cross", "bollinger_bands"]
    
    results = {
        "optimization_period": "2024-01-01 to 2024-12-31",
        "backtest_period": "2025-01-01 to 2026-04-30",
        "optimization_results": {},
        "backtest_results": {},
    }
    
    print("="*60)
    print("策略参数优化")
    print("="*60)
    print(f"优化期: 2024-01-01 to 2024-12-31")
    print(f"币种: {symbols}")
    print(f"策略: {strategies}")
    print()
    
    # 检查数据是否存在
    data_root = project_root / "data_lake" / "features" / "binance"
    
    for symbol in symbols:
        data_path = data_root / symbol / "features.parquet"
        
        if not data_path.exists():
            print(f"⚠️ 数据不存在: {data_path}")
            continue
        
        print(f"\n处理 {symbol}...")
        
        for strategy_id in strategies:
            print(f"\n  优化策略: {strategy_id}")
            
            try:
                # 参数优化
                opt_result = await service.optimize(
                    symbol=symbol,
                    strategy_id=strategy_id,
                    start_time=opt_start,
                    end_time=opt_end,
                )
                
                best_params = opt_result.get("best_params")
                best_score = opt_result.get("best_score", 0)
                
                print(f"    最佳参数: {best_params}")
                print(f"    最佳分数: {best_score:.4f}")
                
                results["optimization_results"][f"{symbol}_{strategy_id}"] = {
                    "best_params": best_params,
                    "best_score": best_score,
                }
                
                # 使用最佳参数回测
                if best_params:
                    print(f"\n  回测策略: {strategy_id}")
                    
                    bt_result = await service.run_backtest(
                        symbol=symbol,
                        strategy_id=strategy_id,
                        params=best_params,
                        start_time=bt_start,
                        end_time=bt_end,
                    )
                    
                    print(f"    总收益: {bt_result.total_return:.2%}")
                    print(f"    Sharpe: {bt_result.sharpe_ratio:.2f}")
                    print(f"    胜率: {bt_result.win_rate:.2%}")
                    print(f"    最大回撤: {bt_result.max_drawdown:.2%}")
                    print(f"    交易次数: {bt_result.total_trades}")
                    
                    results["backtest_results"][f"{symbol}_{strategy_id}"] = bt_result.to_dict()
                
            except Exception as e:
                print(f"    ❌ 错误: {e}")
    
    # 保存结果
    output_path = project_root / "docs" / f"optimization_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n结果已保存到: {output_path}")
    
    # 汇总
    print("\n" + "="*60)
    print("结果汇总")
    print("="*60)
    
    print("\n优化结果:")
    for key, opt in results["optimization_results"].items():
        print(f"  {key}: score={opt.get('best_score', 0):.4f}, params={opt.get('best_params')}")
    
    print("\n回测结果:")
    for key, bt in results["backtest_results"].items():
        print(f"  {key}: return={bt.get('total_return', 0):.2%}, sharpe={bt.get('sharpe_ratio', 0):.2f}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_optimization_and_backtest())
