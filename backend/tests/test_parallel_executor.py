"""
测试通用 ParallelExecutor

验证架构分层后的通用并行执行能力
"""
import sys
import os
import time

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from engines.optimization import ParallelExecutor, GridSearchOptimizer


def simple_task(args):
    """简单的测试任务"""
    value, = args
    time.sleep(0.1)
    return {"value": value, "result": value * 2}


def test_parallel_executor():
    """测试并行执行器"""
    print("="*80)
    print("测试 ParallelExecutor (多进程)")
    print("="*80)
    
    executor = ParallelExecutor(
        executor_type="process",
        max_workers=8
    )
    
    tasks = [(i,) for i in range(16)]
    
    print(f"任务数: {len(tasks)}")
    print(f"执行器: {executor.executor_type}")
    print(f"工作进程: {executor.max_workers}")
    
    print("\n开始执行...")
    start = time.time()
    
    results = executor.execute(
        func=simple_task,
        tasks=tasks,
        progress_callback=lambda done, total: print(f"  进度: {done}/{total}")
    )
    
    elapsed = time.time() - start
    
    print(f"\n执行完成，耗时: {elapsed:.2f}秒")
    print(f"结果数: {len(results)}")
    print(f"首个结果: {results[0]}")
    
    return elapsed


def test_grid_search_optimizer():
    """测试 Grid Search 优化器"""
    print("\n" + "="*80)
    print("测试 GridSearchOptimizer")
    print("="*80)
    
    optimizer = GridSearchOptimizer(
        executor=ParallelExecutor(executor_type="process", max_workers=8)
    )
    
    def mock_backtest(params):
        period = params["period"]
        threshold = params["threshold"]
        score = period * 0.1 + threshold * 10 + (hash(str(params)) % 100) / 100
        return {
            "params": params,
            "score": score,
            "sharpe": score,
            "trades": int(score * 10),
            "total_return": score * 0.01
        }
    
    param_grid = {
        "period": [7, 14, 21, 28],
        "threshold": [0.01, 0.02, 0.03, 0.04]
    }
    
    print(f"参数网格: {param_grid}")
    print(f"组合数: {4 * 4} = 16")
    
    start = time.time()
    result = optimizer.optimize(
        strategy_id="test_strategy",
        param_grid=param_grid,
        backtest_func=mock_backtest,
        objective="sharpe",
        verbose=True
    )
    elapsed = time.time() - start
    
    print(f"\n优化完成，耗时: {elapsed:.2f}秒")
    print(f"最佳参数: {result['best_params']}")
    print(f"最佳分数: {result['best_score']:.4f}")
    
    return elapsed


def test_sequential():
    """测试串行执行"""
    print("\n" + "="*80)
    print("测试 ParallelExecutor (串行)")
    print("="*80)
    
    executor = ParallelExecutor(executor_type="sequential", max_workers=1)
    
    tasks = [(i,) for i in range(16)]
    
    print(f"任务数: {len(tasks)}")
    
    start = time.time()
    
    results = executor.execute(
        func=simple_task,
        tasks=tasks,
        progress_callback=lambda done, total: print(f"  进度: {done}/{total}")
    )
    
    elapsed = time.time() - start
    
    print(f"\n执行完成，耗时: {elapsed:.2f}秒")
    
    return elapsed


if __name__ == '__main__':
    mp_time = test_parallel_executor()
    gs_time = test_grid_search_optimizer()
    seq_time = test_sequential()
    
    print("\n" + "="*80)
    print("性能对比")
    print("="*80)
    print(f"多进程 (16任务): {mp_time:.2f}秒")
    print(f"GridSearch (16组合): {gs_time:.2f}秒")
    print(f"串行 (16任务): {seq_time:.2f}秒")
    print(f"加速比: {seq_time/mp_time:.2f}x")
    print("="*80)
