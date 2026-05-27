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


# ==================== Parquet 数据加载 ====================


def load_from_parquet(
    symbol: str,
    days: int,
    timeframe: str = "1m",
) -> Tuple[List[Any], List[int], np.ndarray]:
    """
    从本地 Parquet 文件加载真实历史数据并构建 MarketContext

    数据路径: DATA_LAKE_ROOT/crypto/binance/{klines,oi,funding}/symbol={symbol}/

    Args:
        symbol: 交易对
        days: 天数
        timeframe: K线周期

    Returns:
        Tuple[List[MarketContext], List[int], np.ndarray]:
            (MarketContext 列表, 时间戳列表, 价格数组)
    """
    from engines.compute.context import (
        MarketContext,
        TimeframeContext,
        PriceState,
        TrendStateData,
        VolatilityStateData,
        VolumeStateData,
        FlowState,
        LiquidityStateData,
        DerivativesContext,
        OIData,
        FundingData,
        LiquidationData,
        RiskContext,
        TrendState,
        FlowPressure,
        FundingBias,
        LiquidityState,
        VolatilityState,
        VolumeState,
    )

    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

    reader = FileDataLakeReader()

    print(f"  加载 Klines (via FileDataLakeReader): binance/{symbol}")
    klines_df = reader.load_klines("binance", symbol, timeframe=timeframe)

    if klines_df.empty:
        print(f"  错误: Klines 数据为空")
        return [], [], np.array([])

    if "timestamp" in klines_df.columns:
        klines_df["timestamp"] = pd.to_datetime(klines_df["timestamp"]).dt.tz_localize(None)

    if "interval" in klines_df.columns:
        tf_df = klines_df[klines_df["interval"] == timeframe]
        if not tf_df.empty:
            klines_df = tf_df

    if "timestamp" in klines_df.columns and len(klines_df) > 0:
        latest_ts = klines_df["timestamp"].iloc[-1]
        if hasattr(latest_ts, "value"):
            end_ts = int(latest_ts.value / 1e6)
        else:
            end_ts = int(pd.Timestamp(latest_ts).value / 1e6)
        start_ts = end_ts - days * 24 * 60 * 60 * 1000

        ts_start = pd.Timestamp(start_ts, unit="ms")
        ts_end = pd.Timestamp(end_ts, unit="ms")
        klines_df = klines_df[(klines_df["timestamp"] >= ts_start) & (klines_df["timestamp"] <= ts_end)]

    if klines_df.empty:
        print(f"  错误: 时间范围过滤后 Klines 数据为空")
        return [], [], np.array([])

    print(f"  Klines: {len(klines_df)} rows, {klines_df['timestamp'].iloc[0]} ~ {klines_df['timestamp'].iloc[-1]}")

    print(f"  加载 OI (via FileDataLakeReader)")
    oi_df = reader.load_oi("binance", symbol)
    print(f"  OI: {len(oi_df)} rows")

    print(f"  加载 Funding (via FileDataLakeReader)")
    funding_df = reader.load_funding("binance", symbol)
    print(f"  Funding: {len(funding_df)} rows")

    if not oi_df.empty:
        if "sumOpenInterestValue" in oi_df.columns:
            oi_values = oi_df["sumOpenInterestValue"].astype(float)
            oi_mean = oi_values.rolling(100, min_periods=10).mean()
            oi_std = oi_values.rolling(100, min_periods=10).std()
            oi_df["oi_zscore"] = (oi_values - oi_mean) / (oi_std + 1e-10)
        oi_ts = oi_df.set_index("timestamp")
    else:
        oi_ts = pd.DataFrame()

    if not funding_df.empty:
        if "fundingRate" in funding_df.columns:
            fr_values = funding_df["fundingRate"].astype(float)
            fr_mean = fr_values.rolling(100, min_periods=10).mean()
            fr_std = fr_values.rolling(100, min_periods=10).std()
            funding_df["funding_zscore"] = (fr_values - fr_mean) / (fr_std + 1e-10)
        funding_ts = funding_df.set_index("timestamp")
    else:
        funding_ts = pd.DataFrame()

    market_contexts = []
    timestamps = []
    prices = []

    for idx, row in klines_df.iterrows():
        ts = row["timestamp"]
        ts_ms = int(ts.value / 1e6) if hasattr(ts, "value") else int(pd.Timestamp(ts).value / 1e6)
        close = float(row["close"])
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        volume = float(row.get("volume", 0))
        change_pct = (close - open_) / open_ * 100 if open_ > 0 else 0

        timestamps.append(ts_ms)
        prices.append(close)

        tf_contexts = {}

        tf_contexts["1m"] = TimeframeContext(
            timeframe="1m",
            price=PriceState(
                open=open_,
                high=high,
                low=low,
                close=close,
                change_percent=change_pct,
            ),
            liquidity=LiquidityStateData(
                state=LiquidityState.NORMAL,
                spread=0.5,
            ),
            flow=FlowState(
                pressure=FlowPressure.NEUTRAL,
                score=0.0,
                cvd=0.0,
            ),
        )

        tf_contexts["5m"] = TimeframeContext(
            timeframe="5m",
            price=PriceState(
                open=open_,
                high=high,
                low=low,
                close=close,
                change_percent=change_pct,
            ),
            flow=FlowState(
                pressure=FlowPressure.NEUTRAL,
                score=0.0,
                cvd=0.0,
            ),
        )

        trend_state = TrendState.SIDEWAYS
        if change_pct > 0.3:
            trend_state = TrendState.WEAK_UP
        elif change_pct < -0.3:
            trend_state = TrendState.WEAK_DOWN

        vol_state = VolatilityState.NORMAL
        atr_pct = (high - low) / close if close > 0 else 0.01
        if atr_pct > 0.02:
            vol_state = VolatilityState.ELEVATED
        elif atr_pct < 0.005:
            vol_state = VolatilityState.LOW

        tf_contexts["15m"] = TimeframeContext(
            timeframe="15m",
            price=PriceState(
                open=open_,
                high=high,
                low=low,
                close=close,
                change_percent=change_pct,
            ),
            trend=TrendStateData(
                state=trend_state,
                slope=change_pct * 0.001,
                strength=min(abs(change_pct) / 2.0, 0.95),
            ),
            volatility=VolatilityStateData(
                state=vol_state,
                atr_pct=atr_pct,
            ),
            volume=VolumeStateData(
                state=VolumeState.NORMAL,
                volume_zscore=0.0,
            ),
            flow=FlowState(
                pressure=FlowPressure.NEUTRAL,
                score=0.0,
                cvd=0.0,
                cvd_slope=0.0,
                aggressive_ratio=0.5,
            ),
        )

        tf_contexts["1h"] = TimeframeContext(
            timeframe="1h",
            trend=TrendStateData(
                state=trend_state,
                slope=change_pct * 0.0005,
                strength=min(abs(change_pct) / 3.0, 0.95),
            ),
            price=PriceState(close=close, change_percent=change_pct),
        )

        tf_contexts["4h"] = TimeframeContext(
            timeframe="4h",
            trend=TrendStateData(
                state=trend_state,
                slope=change_pct * 0.0003,
                strength=min(abs(change_pct) / 4.0, 0.95),
            ),
        )

        oi_value = 0.0
        oi_delta = 0.0
        oi_zscore = 0.0
        if not oi_ts.empty:
            try:
                ts_pd = pd.Timestamp(ts_ms, unit="ms")
                nearest = oi_ts.index.get_indexer([ts_pd], method="nearest")
                if nearest[0] >= 0:
                    oi_row = oi_ts.iloc[nearest[0]]
                    oi_val_str = str(oi_row.get("sumOpenInterestValue", "0"))
                    oi_value = float(oi_val_str) if oi_val_str and oi_val_str != "" else 0.0
                    if "oi_zscore" in oi_row.index:
                        oi_zscore = float(oi_row["oi_zscore"]) if not pd.isna(oi_row["oi_zscore"]) else 0.0
            except Exception:
                pass

        funding_rate = 0.0
        funding_zscore = 0.0
        funding_bias = FundingBias.NEUTRAL
        if not funding_ts.empty:
            try:
                ts_pd = pd.Timestamp(ts_ms, unit="ms")
                nearest = funding_ts.index.get_indexer([ts_pd], method="nearest")
                if nearest[0] >= 0:
                    f_row = funding_ts.iloc[nearest[0]]
                    fr_str = str(f_row.get("fundingRate", "0"))
                    funding_rate = float(fr_str) if fr_str and fr_str != "" else 0.0
                    if "funding_zscore" in f_row.index:
                        funding_zscore = float(f_row["funding_zscore"]) if not pd.isna(f_row["funding_zscore"]) else 0.0
                    else:
                        funding_zscore = funding_rate / 0.0001 if abs(funding_rate) > 0 else 0.0

                    if funding_zscore > 2.0:
                        funding_bias = FundingBias.EXTREME_POSITIVE
                    elif funding_zscore > 0.5:
                        funding_bias = FundingBias.POSITIVE
                    elif funding_zscore < -2.0:
                        funding_bias = FundingBias.EXTREME_NEGATIVE
                    elif funding_zscore < -0.5:
                        funding_bias = FundingBias.NEGATIVE
            except Exception:
                pass

        derivatives = DerivativesContext(
            oi=OIData(
                value=oi_value,
                delta=oi_delta,
                zscore=oi_zscore,
            ),
            funding=FundingData(
                rate=funding_rate,
                zscore=funding_zscore,
                bias=funding_bias,
            ),
            liquidation=LiquidationData(
                long=0.0,
                short=0.0,
                total=0.0,
                long_zscore=0.0,
                short_zscore=0.0,
                reversal_signal=False,
            ),
        )

        ctx = MarketContext(
            symbol=symbol,
            timestamp=ts_ms,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )

        market_contexts.append(ctx)

    prices_arr = np.array(prices)
    print(f"  构建 MarketContext: {len(market_contexts)} 条, 价格范围 [{prices_arr.min():.2f}, {prices_arr.max():.2f}]")

    return market_contexts, timestamps, prices_arr


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
                layer=DataLayer.AGGREGATED,
                table="aggregated_klines",
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                filters={"timeframe": timeframe},
                limit=0,
                order_by="open_time",
                time_column="open_time",
            )
            
            data = loop.run_until_complete(manager.query(request))
            
            if not data:
                print(f"警告: 从 AGGREGATED 层未获取到数据")
            
            loop.run_until_complete(manager.close())
            
            if data:
                timestamps = [int(row["open_time"].timestamp() * 1000) if hasattr(row["open_time"], "timestamp") else row["open_time"] for row in data]
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
    'load_from_parquet',
    'load_from_datalake',
    'get_strategy_class',
    'save_results_to_csv',
    'save_results_to_json',
]
