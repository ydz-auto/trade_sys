"""
Common Loaders - 通用数据加载器

提供从不同数据源加载数据的功能。
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import os

from .types import PriceData, SignalRecord


def load_ohlcv_from_csv(file_path: str) -> List[PriceData]:
    """
    从 CSV 文件加载 OHLCV 数据
    
    Args:
        file_path: CSV 文件路径
    
    Returns:
        List[PriceData]: 价格数据列表
    """
    df = pd.read_csv(file_path)
    
    if 'timestamp' not in df.columns:
        if 'datetime' in df.columns:
            df['timestamp'] = pd.to_datetime(df['datetime']).astype(int) // 10**6
        else:
            raise ValueError("CSV 文件必须包含 timestamp 或 datetime 列")
    
    price_data = []
    for _, row in df.iterrows():
        price_data.append(PriceData(
            timestamp=int(row['timestamp']),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row.get('volume', 0.0))
        ))
    
    return price_data


def load_signals_from_csv(file_path: str) -> List[SignalRecord]:
    """
    从 CSV 文件加载信号记录
    
    Args:
        file_path: CSV 文件路径
    
    Returns:
        List[SignalRecord]: 信号记录列表
    """
    df = pd.read_csv(file_path)
    
    signals = []
    for _, row in df.iterrows():
        signals.append(SignalRecord(
            timestamp=int(row['timestamp']),
            symbol=str(row['symbol']),
            strategy=str(row['strategy']),
            signal_type=str(row['signal_type']),
            confidence=float(row['confidence']),
            reason=str(row['reason']),
            additional_info=eval(row.get('additional_info', '{}'))
        ))
    
    return signals


def generate_test_data(
    num_samples: int = 1000,
    base_price: float = 45000.0,
    volatility: float = 0.002
) -> Tuple[List[PriceData], List[SignalRecord]]:
    """
    生成测试数据
    
    Args:
        num_samples: 样本数量
        base_price: 基准价格
        volatility: 波动率
    
    Returns:
        Tuple[List[PriceData], List[SignalRecord]]: (价格数据, 信号记录)
    """
    price_data = []
    signals = []
    
    base_timestamp = int(datetime(2024, 1, 1).timestamp() * 1000)
    price = base_price
    
    for i in range(num_samples):
        timestamp = base_timestamp + i * 15 * 60 * 1000
        
        price_change = np.random.normal(0, volatility) * price
        price = max(price + price_change, 1000)
        
        price_data.append(PriceData(
            timestamp=timestamp,
            open=price,
            high=price * (1 + np.random.uniform(0, 0.005)),
            low=price * (1 - np.random.uniform(0, 0.005)),
            close=price,
            volume=np.random.uniform(100, 1000)
        ))
        
        signal_type = np.random.choice(['long', 'short', 'none'], p=[0.3, 0.3, 0.4])
        if signal_type != 'none':
            signals.append(SignalRecord(
                timestamp=timestamp,
                symbol='BTCUSDT',
                strategy='test_strategy',
                signal_type=signal_type,
                confidence=np.random.uniform(0.5, 1.0),
                reason='test_signal',
                additional_info={'test': True}
            ))
    
    return price_data, signals


# ==================== DataLake 数据加载 ====================

def load_from_datalake(
    symbol: str,
    days: int,
    timeframe: str = "15m"
) -> Tuple[List[Dict[str, Any]], List[int], np.ndarray]:
    """
    从 DataLake 加载真实历史数据
    
    Args:
        symbol: 交易对
        days: 天数
        timeframe: 时间周期
    
    Returns:
        Tuple[List[Dict], List[int], np.ndarray]: (市场数据列表, 时间戳列表, 价格数组)
    """
    import asyncio
    
    from infrastructure.storage.data_lake.manager import (
        QueryRequest,
        get_data_lake_manager,
    )
    from infrastructure.storage.data_lake.layer import DataLayer
    
    def _load():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            manager = loop.run_until_complete(get_data_lake_manager())
            
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            request = QueryRequest(
                layer=DataLayer.HOT,
                table=f"ohlcv_{timeframe}",
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                limit=0,
                order_by="timestamp"
            )
            
            data = loop.run_until_complete(manager.query(request))
            
            if not data:
                print(f"警告: 从 HOT 层未获取到数据，尝试 WARM 层")
                request.layer = DataLayer.WARM
                data = loop.run_until_complete(manager.query(request))
            
            loop.run_until_complete(manager.close())
            
            if data:
                timestamps = [row["timestamp"] for row in data]
                prices = np.array([row["close"] for row in data])
                return data, timestamps, prices
            else:
                return [], [], np.array([])
        
        except Exception as e:
            print(f"从 DataLake 加载数据失败: {e}")
            return [], [], np.array([])
    
    return _load()


def get_strategy_class(strategy_name: str):
    """
    根据策略名称获取策略类
    
    Args:
        strategy_name: 策略名称
    
    Returns:
        StrategyV2: 策略类
    """
    from engines.compute.strategy_v2.strategies import (
        ShortSqueezeStrategy,
        OpenInterestBehaviorStrategy,
        FundingExtremeReversalStrategy,
        LiquidationCascadeStrategy,
        TradePressureBounceStrategy,
    )
    
    strategy_map = {
        'short_squeeze': ShortSqueezeStrategy,
        'oi_behavior': OpenInterestBehaviorStrategy,
        'funding_extreme_reversal': FundingExtremeReversalStrategy,
        'liquidation_cascade': LiquidationCascadeStrategy,
        'trade_pressure_bounce': TradePressureBounceStrategy,
    }
    
    return strategy_map.get(strategy_name)


def save_results_to_csv(results: Dict[str, Any], file_path: str):
    """
    保存结果到 CSV 文件
    
    Args:
        results: 结果字典
        file_path: 输出文件路径
    """
    df = pd.DataFrame(results)
    df.to_csv(file_path, index=False)
    print(f"结果已保存到: {file_path}")


def save_results_to_json(results: Dict[str, Any], file_path: str):
    """
    保存结果到 JSON 文件
    
    Args:
        results: 结果字典
        file_path: 输出文件路径
    """
    import json
    
    with open(file_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"结果已保存到: {file_path}")


__all__ = [
    'load_ohlcv_from_csv',
    'load_signals_from_csv',
    'generate_test_data',
    'load_from_datalake',
    'get_strategy_class',
    'save_results_to_csv',
    'save_results_to_json',
]
