"""
Backtest Worker - 回测工作函数

提供可在子进程中运行的回测函数

要求：
1. 顶层函数，不依赖外部全局变量
2. 入参只使用 dict / list / str / int / float 等可 pickle 对象
3. 函数内部重新 import 需要的策略、BacktestEngine
4. 返回 dict，不返回复杂对象
5. 使用统一的 StrategyRegistry，不硬编码策略映射

位置：backend/engines/optimization/backtest_worker.py
"""
from typing import Dict, Any, Optional, List
import sys
import os
from pathlib import Path


def run_single_backtest_worker(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    单次回测工作函数（可在子进程运行）
    
    Args:
        task: 任务字典，包含：
            - strategy_id: 策略ID
            - params: 参数字典
            - bars_data: K线数据（序列化后的列表）
            - config_dict: 回测配置字典
            - enable_gpu: 是否启用GPU
            - funding_data: 资金费率数据（list或None）
            - oi_data: OI数据（list或None）
    
    Returns:
        回测结果字典：
            - params: 参数
            - sharpe: 夏普比率
            - trades: 交易次数
            - total_return: 总收益
            - max_drawdown: 最大回撤
            - win_rate: 胜率
            - profit_factor: 盈亏比
            - error: 错误信息（如果有）
    """
    try:
        backend_path = os.environ.get('BACKEND_PATH')
        if not backend_path:
            backend_path = Path(__file__).parent.parent.parent
            os.environ['BACKEND_PATH'] = str(backend_path)
        
        if str(backend_path) not in sys.path:
            sys.path.insert(0, str(backend_path))
        
        strategy_id = task.get("strategy_id")
        params = task.get("params", {})
        bars_data = task.get("bars_data", [])
        config_dict = task.get("config_dict", {})
        enable_gpu = task.get("enable_gpu", False)
        funding_data = task.get("funding_data")
        oi_data = task.get("oi_data")
        
        from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, SignalType, Bar
        from engines.compute.strategy.registry import get_strategy
        
        strategy = get_strategy(strategy_id, params)
        
        class StrategyAdapter:
            def __init__(self, strat, fund_df, oi_df):
                self.strategy = strat
                self._closes = []
                self._highs = []
                self._lows = []
                self._volumes = []
                self._funding_df = fund_df
                self._oi_df = oi_df
            
            def _get_supplementary_data(self, timestamp, closes):
                data = {}
                try:
                    import pandas as pd
                    ts_naive = timestamp.replace(tzinfo=None) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None else timestamp
                    
                    if self._funding_df is not None:
                        mask = self._funding_df["timestamp"] <= ts_naive
                        if mask.any():
                            latest = self._funding_df.iloc[-1]
                            data["funding_rate"] = float(latest.get("fundingRate", 0.0))
                    
                    if self._oi_df is not None:
                        mask = self._oi_df["timestamp"] <= ts_naive
                        if mask.any():
                            latest = self._oi_df.iloc[-1]
                            sum_oi = latest.get("sumOpenInterest", 0.0)
                            sum_oi = float(sum_oi) if sum_oi != "" else 0.0
                            if mask.sum() > 24:
                                prev_oi = self._oi_df.iloc[-(mask.sum() - 24)].get("sumOpenInterest", 0.0)
                                prev_oi = float(prev_oi) if prev_oi != "" else 0.0
                                if prev_oi > 0:
                                    data["oi_delta"] = (sum_oi - prev_oi) / prev_oi
                except:
                    pass
                return data
            
            def __call__(self, bar, position=None):
                self._closes.append(bar.close)
                self._highs.append(bar.high)
                self._lows.append(bar.low)
                self._volumes.append(bar.volume)
                
                if len(self._closes) > 600:
                    self._closes = self._closes[-600:]
                    self._highs = self._highs[-600:]
                    self._lows = self._lows[-600:]
                    self._volumes = self._volumes[-600:]
                
                from engines.compute.strategy.strategies import ActionType
                
                basic_data = {
                    "close_prices": self._closes,
                    "high_prices": self._highs,
                    "low_prices": self._lows,
                    "volumes": self._volumes,
                    "symbol": "BTCUSDT",
                    "timestamp": bar.timestamp
                }
                
                supplementary = self._get_supplementary_data(bar.timestamp, self._closes)
                basic_data.update(supplementary)
                
                try:
                    signal = self.strategy.calculate(basic_data)
                    if signal:
                        if signal.action == ActionType.LONG:
                            return SignalType.BUY
                        elif signal.action == ActionType.SHORT:
                            return SignalType.SELL
                except:
                    pass
                
                return SignalType.HOLD
        
        config = BacktestConfig(**config_dict)
        
        import pandas as pd
        funding_df = pd.DataFrame(funding_data) if funding_data else None
        oi_df = pd.DataFrame(oi_data) if oi_data else None
        
        adapter = StrategyAdapter(strategy, funding_df, oi_df)
        
        bars = [Bar(**b) for b in bars_data]
        
        engine = BacktestEngine(config=config, enable_gpu=enable_gpu)
        engine.load_data(bars)
        result = engine.run(adapter)
        
        if result:
            return {
                "params": params,
                "sharpe": result.metrics.sharpe_ratio,
                "trades": result.metrics.total_trades,
                "total_return": result.metrics.total_return,
                "max_drawdown": result.metrics.max_drawdown_pct,
                "win_rate": result.metrics.win_rate,
                "profit_factor": result.metrics.profit_factor,
                "error": None
            }
        
        return {
            "params": params,
            "sharpe": -float('inf'),
            "trades": 0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "error": "No result returned"
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "params": task.get("params", {}),
            "sharpe": -float('inf'),
            "trades": 0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "error": str(e)
        }


def build_backtest_task(
    strategy_id: str,
    params: Dict[str, Any],
    bars_data: List[Dict[str, Any]],
    config_dict: Optional[Dict[str, Any]] = None,
    enable_gpu: bool = False,
    funding_data: Optional[List] = None,
    oi_data: Optional[List] = None
) -> Dict[str, Any]:
    """
    构建回测任务字典
    
    统一任务格式，方便 parallel_map 调用
    """
    if config_dict is None:
        config_dict = {
            "initial_capital": 10000.0,
            "commission": 0.0004,
            "slippage": 0.0005,
            "position_size": 0.1,
            "stop_loss": 0.1,
            "take_profit": 0.2,
            "leverage": 5.0,
            "use_realistic_fees": True
        }
    
    return {
        "strategy_id": strategy_id,
        "params": params,
        "bars_data": bars_data,
        "config_dict": config_dict,
        "enable_gpu": enable_gpu,
        "funding_data": funding_data,
        "oi_data": oi_data
    }
