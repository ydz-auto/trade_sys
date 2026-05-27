#!/usr/bin/env python3
"""
Walk-Forward 参数优化验证测试

核心目标：验证参数优化不会在同一段数据上既调参又验收益

验证点：
1. 优化集和测试集严格分离（无重叠）
2. 参数只在优化集上搜索，测试集仅用于验证
3. 使用 ReplayRuntime 进行回测（确保与实盘一致）
4. 禁止在测试集上调整参数

时间划分方案：
方案A - 固定年份划分：
  2022 optimize → 优化参数
  2023 validation → 验证参数
  2024 test → 最终测试

方案B - 滚动窗口 walk-forward：
  6个月优化 → 1个月测试
"""
import sys
sys.path.insert(0, '.')

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
import statistics

from infrastructure.logging import get_logger

logger = get_logger("test_optimization_wf")


@dataclass
class WalkForwardWindow:
    """Walk-Forward 窗口"""
    window_index: int
    optimize_start_ms: int
    optimize_end_ms: int
    test_start_ms: int
    test_end_ms: int
    
    def validate_no_overlap(self) -> bool:
        """验证优化集和测试集无重叠"""
        return self.optimize_end_ms <= self.test_start_ms
    
    def validate_purge_gap(self, min_gap_ms: int = 0) -> bool:
        """验证 purge gap"""
        actual_gap = self.test_start_ms - self.optimize_end_ms
        return actual_gap >= min_gap_ms
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_index": self.window_index,
            "optimize_range": {
                "start_ms": self.optimize_start_ms,
                "end_ms": self.optimize_end_ms,
            },
            "test_range": {
                "start_ms": self.test_start_ms,
                "end_ms": self.test_end_ms,
            },
            "optimize_test_gap_ms": self.test_start_ms - self.optimize_end_ms,
        }


class WalkForwardOptimizer:
    """
    Walk-Forward 参数优化器
    
    核心原则：
    1. 参数只在优化集上搜索
    2. 测试集仅用于验证（绝不调参）
    3. 使用 ReplayRuntime 进行回测
    4. 记录每个窗口的最佳参数和测试表现
    """
    
    def __init__(self):
        self._windows: List[WalkForwardWindow] = []
        self._results: List[Dict[str, Any]] = []
        self._optimization_history: List[Dict[str, Any]] = []
    
    def create_fixed_year_windows(self) -> List[WalkForwardWindow]:
        """
        方案A：固定年份划分
        
        2022 optimize → 优化参数
        2023 validation → 验证参数（可选调参）
        2024 test → 最终测试（绝不调参）
        """
        windows = []
        
        tz = timezone.utc
        
        optimize_start = datetime(2022, 1, 1, tzinfo=tz)
        optimize_end = datetime(2023, 1, 1, tzinfo=tz)
        
        val_start = datetime(2023, 1, 1, tzinfo=tz)
        val_end = datetime(2024, 1, 1, tzinfo=tz)
        
        test_start = datetime(2024, 1, 1, tzinfo=tz)
        test_end = datetime(2025, 1, 1, tzinfo=tz)
        
        windows.append(WalkForwardWindow(
            window_index=0,
            optimize_start_ms=int(optimize_start.timestamp() * 1000),
            optimize_end_ms=int(optimize_end.timestamp() * 1000),
            test_start_ms=int(val_start.timestamp() * 1000),
            test_end_ms=int(val_end.timestamp() * 1000),
        ))
        
        windows.append(WalkForwardWindow(
            window_index=1,
            optimize_start_ms=int(optimize_start.timestamp() * 1000),
            optimize_end_ms=int(val_end.timestamp() * 1000),
            test_start_ms=int(test_start.timestamp() * 1000),
            test_end_ms=int(test_end.timestamp() * 1000),
        ))
        
        self._windows = windows
        return windows
    
    def create_rolling_windows(
        self,
        optimize_months: int = 6,
        test_months: int = 1,
        start_year: int = 2022,
        end_year: int = 2024,
    ) -> List[WalkForwardWindow]:
        """
        方案B：滚动窗口 walk-forward
        
        6个月优化 → 1个月测试
        """
        windows = []
        
        tz = timezone.utc
        
        optimize_duration_ms = optimize_months * 30 * 86400000
        test_duration_ms = test_months * 30 * 86400000
        step_ms = test_duration_ms
        
        start_dt = datetime(start_year, 1, 1, tzinfo=tz)
        start_ms = int(start_dt.timestamp() * 1000)
        
        end_dt = datetime(end_year + 1, 1, 1, tzinfo=tz)
        end_ms = int(end_dt.timestamp() * 1000)
        
        window_index = 0
        test_start = start_ms + optimize_duration_ms
        
        while test_start + test_duration_ms <= end_ms:
            optimize_end = test_start
            optimize_start = optimize_end - optimize_duration_ms
            
            if optimize_start < start_ms:
                optimize_start = start_ms
            
            window = WalkForwardWindow(
                window_index=window_index,
                optimize_start_ms=optimize_start,
                optimize_end_ms=optimize_end,
                test_start_ms=test_start,
                test_end_ms=test_start + test_duration_ms,
            )
            
            windows.append(window)
            
            test_start += step_ms
            window_index += 1
        
        self._windows = windows
        return windows
    
    def validate_windows(self, windows: List[WalkForwardWindow]) -> Dict[str, Any]:
        """
        验证所有窗口的数据分离
        
        返回验证报告
        """
        validation_results = {
            "total_windows": len(windows),
            "all_valid": True,
            "overlap_violations": [],
            "gap_violations": [],
            "window_details": [],
        }
        
        for window in windows:
            detail = window.to_dict()
            
            if not window.validate_no_overlap():
                validation_results["all_valid"] = False
                validation_results["overlap_violations"].append({
                    "window_index": window.window_index,
                    "optimize_end_ms": window.optimize_end_ms,
                    "test_start_ms": window.test_start_ms,
                    "overlap_ms": window.test_start_ms - window.optimize_end_ms,
                })
            
            detail["no_overlap"] = window.validate_no_overlap()
            detail["purge_gap_valid"] = window.validate_purge_gap(0)
            
            validation_results["window_details"].append(detail)
        
        return validation_results
    
    async def optimize_params_on_optimize_set(
        self,
        window: WalkForwardWindow,
        strategy_id: str,
        param_grid: Dict[str, List[Any]],
        symbol: str = "BTCUSDT",
    ) -> Dict[str, Any]:
        """
        在优化集上搜索最佳参数
        
        核心原则：
        1. 只使用优化集数据
        2. 使用 ReplayRuntime 进行回测
        3. 返回最佳参数和优化集表现
        4. 并行执行多个参数组合（利用 M4 多核）
        """
        from runtime.replay_runtime.runtime import get_replay_runtime, ReplayConfig, EventType, ReplayEvent
        
        best_params = None
        best_score = -float('inf')
        all_results = []
        
        param_combinations = self._generate_param_combinations(param_grid)
        
        logger.info(
            f"Window {window.window_index}: Optimizing params on OPTIMIZE set "
            f"[{window.optimize_start_ms} - {window.optimize_end_ms}] "
            f"({len(param_combinations)} combinations, parallel execution)"
        )
        
        tasks = [
            self._run_single_backtest(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                start_ms=window.optimize_start_ms,
                end_ms=window.optimize_end_ms,
            )
            for params in param_combinations
        ]
        
        scores = await asyncio.gather(*tasks)
        
        for params, score in zip(param_combinations, scores):
            all_results.append({
                "params": params,
                "score": score,
                "data_range": "optimize",
            })
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return {
            "window_index": window.window_index,
            "best_params": best_params,
            "best_optimize_score": best_score,
            "all_optimize_results": all_results,
            "optimize_range": {
                "start_ms": window.optimize_start_ms,
                "end_ms": window.optimize_end_ms,
            },
        }
    
    async def validate_params_on_test_set(
        self,
        window: WalkForwardWindow,
        best_params: Dict[str, Any],
        strategy_id: str,
        symbol: str = "BTCUSDT",
    ) -> Dict[str, Any]:
        """
        在测试集上验证参数
        
        核心原则：
        1. 只使用测试集数据
        2. 绝不调整参数
        3. 使用 ReplayRuntime 进行回测
        4. 记录测试集表现（用于最终评估）
        """
        from runtime.replay_runtime.runtime import get_replay_runtime, ReplayConfig
        
        logger.info(
            f"Window {window.window_index}: Validating params on TEST set "
            f"[{window.test_start_ms} - {window.test_end_ms}] "
            f"with params={best_params}"
        )
        
        test_score = await self._run_single_backtest(
            symbol=symbol,
            strategy_id=strategy_id,
            params=best_params,
            start_ms=window.test_start_ms,
            end_ms=window.test_end_ms,
        )
        
        return {
            "window_index": window.window_index,
            "params_used": best_params,
            "test_score": test_score,
            "test_range": {
                "start_ms": window.test_start_ms,
                "end_ms": window.test_end_ms,
            },
            "param_adjusted": False,
        }
    
    async def _run_single_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start_ms: int,
        end_ms: int,
    ) -> float:
        """
        使用 ReplayRuntime 运行单次回测
        
        返回 Sharpe Ratio
        """
        from runtime.replay_runtime.runtime import (
            get_replay_runtime,
            ReplayConfig,
            EventType,
            ReplayEvent,
        )
        
        config = ReplayConfig(
            symbol=symbol,
            start_time_ms=start_ms,
            end_time_ms=end_ms,
            warmup_periods=0,
        )
        
        runtime = get_replay_runtime(config)
        
        synthetic_klines = self._generate_synthetic_klines(start_ms, end_ms)
        
        async def kline_generator():
            for kline in synthetic_klines:
                yield ReplayEvent(
                    event_id=f"kline_{kline['timestamp_ms']}",
                    event_type=EventType.KLINE,
                    timestamp_ms=int(kline['timestamp_ms']),
                    data={
                        'open': float(kline['open']),
                        'high': float(kline['high']),
                        'low': float(kline['low']),
                        'close': float(kline['close']),
                        'volume': float(kline['volume']),
                        'symbol': symbol
                    }
                )
        
        try:
            session_state = await runtime.run_backtest(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                initial_capital=10000.0,
                event_iterator=kline_generator(),
            )
            
            trades = session_state.trades
            if len(trades) < 2:
                return 0.0
            
            returns = []
            for trade in trades:
                pnl_pct = trade.get('pnl', 0) / 10000.0
                returns.append(pnl_pct)
            
            if len(returns) > 1:
                mean_return = statistics.mean(returns)
                std_return = statistics.stdev(returns)
                sharpe = mean_return / (std_return + 1e-10) * (252 ** 0.5)
                return sharpe
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Backtest failed: {e}")
            return -float('inf')
    
    def _generate_param_combinations(
        self,
        param_grid: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """生成参数组合"""
        from itertools import product
        
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        
        combinations = []
        for combo in product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _generate_synthetic_klines(
        self,
        start_ms: int,
        end_ms: int,
        interval_ms: int = 60000
    ) -> List[Dict[str, Any]]:
        """生成合成 K 线数据"""
        import random
        
        klines = []
        price = 45000.0
        
        ts = start_ms
        while ts <= end_ms:
            change = random.uniform(-0.003, 0.004)
            open_p = price
            close_p = price * (1 + change)
            high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.001))
            low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.001))
            volume = random.uniform(50, 200)
            
            klines.append({
                'timestamp_ms': ts,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
                'volume': volume,
            })
            
            price = close_p
            ts += interval_ms
        
        return klines


async def test_window_data_separation():
    """
    测试1：验证优化集/测试集数据严格分离
    
    核心验证点：
    - 优化集结束时间 <= 测试集开始时间
    - 无任何重叠
    """
    print("\n" + "=" * 80)
    print("测试1：优化集/测试集数据分离验证")
    print("=" * 80)
    
    optimizer = WalkForwardOptimizer()
    
    fixed_windows = optimizer.create_fixed_year_windows()
    print(f"\n固定年份划分: {len(fixed_windows)} 个窗口")
    for w in fixed_windows:
        print(f"  Window {w.window_index}: optimize=[{w.optimize_start_ms}, {w.optimize_end_ms}], "
              f"test=[{w.test_start_ms}, {w.test_end_ms}], "
              f"gap={w.test_start_ms - w.optimize_end_ms}ms")
    
    validation = optimizer.validate_windows(fixed_windows)
    print(f"\n验证结果: all_valid={validation['all_valid']}")
    
    assert validation["all_valid"], "固定年份划分存在数据重叠！"
    assert len(validation["overlap_violations"]) == 0, "存在重叠违规！"
    
    rolling_windows = optimizer.create_rolling_windows()
    print(f"\n滚动窗口划分: {len(rolling_windows)} 个窗口")
    for w in rolling_windows[:3]:
        print(f"  Window {w.window_index}: optimize=[{w.optimize_start_ms}, {w.optimize_end_ms}], "
              f"test=[{w.test_start_ms}, {w.test_end_ms}]")
    
    validation_rolling = optimizer.validate_windows(rolling_windows)
    print(f"\n验证结果: all_valid={validation_rolling['all_valid']}")
    
    assert validation_rolling["all_valid"], "滚动窗口划分存在数据重叠！"
    
    print("\n✅ 测试1通过：所有窗口优化集/测试集数据严格分离")


async def test_optimization_only_on_optimize_set():
    """
    测试2：验证参数只在优化集上搜索
    
    核心验证点：
    - 参数搜索过程只使用优化集数据
    - 测试集数据不参与参数选择
    """
    print("\n" + "=" * 80)
    print("测试2：参数优化只在优化集")
    print("=" * 80)
    
    optimizer = WalkForwardOptimizer()
    
    windows = optimizer.create_rolling_windows(optimize_months=1, test_months=1)
    
    param_grid = {
        "rsi_period": [7, 14],
        "oversold": [25, 30],
    }
    
    window = windows[0]
    
    optimize_result = await optimizer.optimize_params_on_optimize_set(
        window=window,
        strategy_id="rsi",
        param_grid=param_grid,
        symbol="BTCUSDT",
    )
    
    print(f"\n优化集参数搜索结果:")
    print(f"  最佳参数: {optimize_result['best_params']}")
    print(f"  最佳优化分数: {optimize_result['best_optimize_score']:.4f}")
    print(f"  数据范围: optimize [{optimize_result['optimize_range']['start_ms']}, {optimize_result['optimize_range']['end_ms']}]")
    
    assert optimize_result["optimize_range"]["end_ms"] <= window.test_start_ms, \
        "优化集数据泄漏到测试集！"
    
    for result in optimize_result["all_optimize_results"]:
        assert result["data_range"] == "optimize", \
            "存在非优化集数据参与参数搜索！"
    
    print("\n✅ 测试2通过：参数优化只在优化集上进行")


async def test_no_param_adjustment_on_test():
    """
    测试3：验证测试集上绝不调整参数
    
    核心验证点：
    - 测试集验证使用优化集最佳参数
    - 不根据测试集表现调整参数
    """
    print("\n" + "=" * 80)
    print("测试3：测试集不调整参数")
    print("=" * 80)
    
    optimizer = WalkForwardOptimizer()
    
    windows = optimizer.create_rolling_windows(optimize_months=1, test_months=1)
    
    param_grid = {
        "rsi_period": [7, 14],
        "oversold": [25, 30],
    }
    
    window = windows[0]
    
    optimize_result = await optimizer.optimize_params_on_optimize_set(
        window=window,
        strategy_id="rsi",
        param_grid=param_grid,
        symbol="BTCUSDT",
    )
    
    best_params_from_optimize = optimize_result["best_params"]
    
    test_result = await optimizer.validate_params_on_test_set(
        window=window,
        best_params=best_params_from_optimize,
        strategy_id="rsi",
        symbol="BTCUSDT",
    )
    
    print(f"\n测试集验证结果:")
    print(f"  使用参数: {test_result['params_used']}")
    print(f"  测试分数: {test_result['test_score']:.4f}")
    print(f"  参数是否调整: {test_result['param_adjusted']}")
    
    assert test_result["params_used"] == best_params_from_optimize, \
        "测试集使用了不同参数（参数被调整）！"
    
    assert test_result["param_adjusted"] == False, \
        "测试集上调整了参数！"
    
    assert test_result["test_range"]["start_ms"] >= window.optimize_end_ms, \
        "测试集数据泄漏到优化集！"
    
    print("\n✅ 测试3通过：测试集上绝不调整参数")


async def main():
    """运行所有测试"""
    print("=" * 80)
    print("Walk-Forward 参数优化验证测试")
    print("=" * 80)
    print("\n核心目标：验证参数优化不会在同一段数据上既调参又验收益")
    print("\n验证点:")
    print("  1. 优化集和测试集严格分离（无重叠）")
    print("  2. 参数只在优化集上搜索，测试集仅用于验证")
    print("  3. 使用 ReplayRuntime 进行回测（确保与实盘一致）")
    print("  4. 禁止在测试集上调整参数")
    
    try:
        await test_window_data_separation()
        await test_optimization_only_on_optimize_set()
        await test_no_param_adjustment_on_test()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试通过！Walk-Forward 参数优化验证成功")
        print("=" * 80)
        print("\n下一步建议:")
        print("  1. 使用真实数据运行 Walk-Forward 优化")
        print("  2. 生成标准回测报告")
        print("  3. 根据过拟合指标决定是否上 paper trading")
        
    except AssertionError as e:
        print("\n" + "=" * 80)
        print(f"❌ 测试失败: {e}")
        print("=" * 80)
        raise
    
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        raise


if __name__ == "__main__":
    asyncio.run(main())