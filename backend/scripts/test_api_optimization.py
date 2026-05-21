"""
使用系统 API 进行批量策略优化和回测测试脚本
"""
import sys
from pathlib import Path
from datetime import datetime
import asyncio
import json

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    print("=" * 80)
    print("使用系统 Application 层进行批量策略优化和回测")
    print("=" * 80)
    
    # 步骤 1: 导入必要的模块
    from application.optimization_service import get_optimization_service
    from application.optimization_service.models import (
        OptimizationConfig,
    )
    
    # 步骤 2: 准备配置
    optimization_start = "2022-01-01"
    optimization_end = "2024-12-31"
    backtest_start = "2025-01-01"
    backtest_end = "2026-04-30"
    symbol = "BTCUSDT"
    
    strategy_ids = [
        "rsi_oversold",
        "sma_cross",
        "macd_cross",
        "ema_cross",
        "bollinger_bands",
    ]
    
    # 步骤 3: 获取优化服务
    service = get_optimization_service()
    
    all_results = []
    
    # 步骤 4: 对每个策略进行优化和回测
    for strategy_id in strategy_ids:
        print(f"\n{'=' * 60}")
        print(f"正在优化策略: {strategy_id}")
        print(f"{'=' * 60}")
        
        try:
            # 创建优化配置
            config = OptimizationConfig(
                initial_capital=10000.0,
                commission=0.0005,
                slippage=0.0002,
                position_size=0.3,
                stop_loss=0.02,
                take_profit=0.04,
                max_hold_hours=48,
                optimization_start=optimization_start,
                optimization_end=optimization_end,
                backtest_start=backtest_start,
                backtest_end=backtest_end,
                resample_freq="10min",
                enable_slippage=False,
                enable_latency=False,
            )
            
            # 创建和运行优化任务
            task = await service.create_task(
                strategy_id=strategy_id,
                symbol=symbol,
                config=config,
            )
            
            print(f"任务已创建: {task.task_id}")
            print(f"参数组合数量: {task.total_combos}")
            
            result = await service.run_task(task.task_id)
            
            # 处理结果
            print(f"\n优化完成!")
            print(f"状态: {result.status}")
            print(f"最佳参数: {result.best_params}")
            print(f"最佳分数: {result.best_score}")
            
            opt_return = 0.0
            opt_sharpe = 0.0
            opt_win_rate = 0.0
            opt_max_dd = 0.0
            
            if result.best_metrics:
                opt_return = result.best_metrics.total_return
                opt_sharpe = result.best_metrics.sharpe_ratio
                opt_win_rate = result.best_metrics.win_rate
                opt_max_dd = result.best_metrics.max_drawdown
                
                print(f"优化期收益: {opt_return:.2%}")
                print(f"优化期夏普: {opt_sharpe:.2f}")
                print(f"优化期胜率: {opt_win_rate:.2%}")
                print(f"优化期最大回撤: {opt_max_dd:.2%}")
            
            # 回测期结果
            backtest_metrics = None
            bt_return = 0.0
            bt_sharpe = 0.0
            bt_win_rate = 0.0
            bt_max_dd = 0.0
            bt_trades = 0
            
            if result.runtime_stats and "backtest_metrics" in result.runtime_stats:
                backtest_metrics = result.runtime_stats["backtest_metrics"]
                bt_return = backtest_metrics.get("total_return", 0)
                bt_sharpe = backtest_metrics.get("sharpe_ratio", 0)
                bt_win_rate = backtest_metrics.get("win_rate", 0)
                bt_max_dd = backtest_metrics.get("max_drawdown", 0)
                bt_trades = backtest_metrics.get("total_trades", 0)
                
                print(f"\n回测期结果:")
                print(f"回测期收益: {bt_return:.2%}")
                print(f"回测期夏普: {bt_sharpe:.2f}")
                print(f"回测期胜率: {bt_win_rate:.2%}")
                print(f"回测期最大回撤: {bt_max_dd:.2%}")
                print(f"回测期交易次数: {bt_trades}")
            
            # 保存结果
            all_results.append({
                "strategy_id": strategy_id,
                "best_params": result.best_params,
                "best_score": result.best_score,
                "optimization": {
                    "total_return": opt_return,
                    "sharpe_ratio": opt_sharpe,
                    "win_rate": opt_win_rate,
                    "max_drawdown": opt_max_dd,
                },
                "backtest": {
                    "total_return": bt_return,
                    "sharpe_ratio": bt_sharpe,
                    "win_rate": bt_win_rate,
                    "max_drawdown": bt_max_dd,
                    "total_trades": bt_trades,
                },
                "status": result.status.value,
                "error": result.error,
            })
            
        except Exception as e:
            print(f"\n策略 {strategy_id} 优化失败: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "strategy_id": strategy_id,
                "error": str(e),
            })
    
    # 步骤 5: 汇总结果
    print("\n" + "=" * 80)
    print("回测结果汇总（按回测期夏普排序）")
    print("=" * 80)
    print(f"{'策略':<20} {'优化期夏普':>12} {'回测期收益':>12} {'回测期夏普':>12} {'最佳参数':<25}")
    print("-" * 80)
    
    # 排序
    sorted_results = sorted(
        all_results,
        key=lambda x: (x.get("backtest", {}).get("sharpe_ratio", -float("inf")) 
                       if x.get("backtest") else -float("inf")),
        reverse=True
    )
    
    for res in sorted_results:
        if "error" in res:
            print(f"{res['strategy_id']:<20} {'ERROR':>12}")
            continue
            
        strategy_id = res["strategy_id"]
        opt_sharpe = res.get("optimization", {}).get("sharpe_ratio", 0)
        bt_return = res.get("backtest", {}).get("total_return", 0)
        bt_sharpe = res.get("backtest", {}).get("sharpe_ratio", 0)
        best_params = res.get("best_params", {})
        
        print(f"{strategy_id:<20} {opt_sharpe:>12.2f} {bt_return:>12.2%} {bt_sharpe:>12.2f} {str(best_params):<25}")
    
    print("=" * 80)
    
    # 保存结果
    output_path = Path(__file__).parent.parent / "data_lake" / "api_optimization_results_10min_48h.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {
                "optimization_period": f"{optimization_start} to {optimization_end}",
                "backtest_period": f"{backtest_start} to {backtest_end}",
                "symbol": symbol,
                "max_hold_hours": 48,
                "resample_freq": "10min",
            },
            "results": sorted_results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存至: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
