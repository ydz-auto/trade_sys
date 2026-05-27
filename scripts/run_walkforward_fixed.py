#!/usr/bin/env python3
"""
Walk-Forward 参数优化脚本 - 架构优化版

使用系统层加速基础设施：
- backend/infrastructure/acceleration/: CPU/GPU 加速
- backend/engines/optimization/: 参数优化

架构：
    脚本层 (入口、配置、报告)
        ↓
    WalkForwardOptimizer (业务逻辑)
        ↓
    GridSearchOptimizer (参数搜索)
        ↓
    AccelerationService (统一加速服务)
        ↓
    CPUExecutor / ProcessPoolExecutor (底层执行)
"""
import sys
import os
import time
import json
import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from infrastructure.acceleration import (
    AccelerationService,
    AccelerationConfig,
    CPUExecutor,
    DeviceManager
)
from engines.optimization import ParameterOptimizer, OptimizationConfig
from runtime.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
    Trade
)
from engines.compute.strategy.strategies import (
    BaseStrategy,
    RSIStrategy,
    MACDStrategy,
    SMACrossoverStrategy,
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    MomentumStrategy,
    PanicReversalStrategy,
    LongLiquidationBounceStrategy,
    VolumeClimaxFadeStrategy,
    WeakBounceShortStrategy,
    OIFlushStrategy,
    ShortSqueezeStrategy,
    FundingExhaustionTrapStrategy,
    DeadCatEchoStrategy,
    ImbalancePressureStrategy,
    SweepDetectionStrategy,
    LiquidityVacuumStrategy,
    AggressiveFlowStrategy,
    BreakoutStrategy,
    TrendFollowingStrategy,
    VolatilityExpansionStrategy,
    BBCompressionBreakoutStrategy,
    MomentumIgnitionStrategy,
    LeadLagStrategy,
    PremiumDivergenceStrategy
)
from engines.compute.strategy.behavioral_strategies import (
    OpenInterestBehaviorStrategy,
    FundingExtremeReversalStrategy,
    LiquidationCascadeStrategy,
    CVDDivergenceStrategy,
    WhaleTradeStrategy,
    FundingSettlementStrategy
)

logger = get_logger("walkforward_fixed")

# ============= 策略配置 =============

STRATEGY_MAPPING = {
    "rsi_oversold": RSIStrategy,
    "rsi_overbought": RSIStrategy,
    "macd_cross": MACDStrategy,
    "sma_cross": SMACrossoverStrategy,
    "ema_cross": EMACrossoverStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "momentum": MomentumStrategy,
    "panic_reversal": PanicReversalStrategy,
    "long_liquidation_bounce": LongLiquidationBounceStrategy,
    "volume_climax_fade": VolumeClimaxFadeStrategy,
    "weak_bounce_short": WeakBounceShortStrategy,
    "oi_flush": OIFlushStrategy,
    "short_squeeze": ShortSqueezeStrategy,
    "funding_exhaustion_trap": FundingExhaustionTrapStrategy,
    "dead_cat_echo": DeadCatEchoStrategy,
    "imbalance_pressure": ImbalancePressureStrategy,
    "sweep_detection": SweepDetectionStrategy,
    "liquidity_vacuum": LiquidityVacuumStrategy,
    "aggressive_flow": AggressiveFlowStrategy,
    "breakout": BreakoutStrategy,
    "trend_following": TrendFollowingStrategy,
    "volatility_expansion": VolatilityExpansionStrategy,
    "bb_compression_breakout": BBCompressionBreakoutStrategy,
    "momentum_ignition": MomentumIgnitionStrategy,
    "lead_lag": LeadLagStrategy,
    "premium_divergence": PremiumDivergenceStrategy,
    "oi_behavior": OpenInterestBehaviorStrategy,
    "funding_extreme_reversal": FundingExtremeReversalStrategy,
    "liquidation_cascade": LiquidationCascadeStrategy,
    "cvd_divergence": CVDDivergenceStrategy,
    "whale_trade": WhaleTradeStrategy,
    "funding_settlement": FundingSettlementStrategy
}

DEFAULT_PARAM_GRIDS = {
    "long_liquidation_bounce": {
        "drop_threshold": [-0.015, -0.02, -0.025],
        "rsi_threshold": [20, 25, 30],
        "volume_ratio_threshold": [1.5, 2.0, 2.5]
    },
    "short_squeeze": {
        "funding_zscore_threshold": [-3.0, -2.5, -2.0, -1.5],
        "oi_growth_threshold": [0.005, 0.01, 0.015, 0.02]
    },
    "funding_exhaustion_trap": {
        "funding_threshold": [-0.001, -0.002, -0.003],
        "rsi_threshold": [25, 30, 35],
        "volume_spike": [1.5, 2.0, 2.5]
    },
    "oi_flush": {
        "oi_drop_threshold": [-0.05, -0.075, -0.1],
        "price_confirm_threshold": [0.01, 0.015, 0.02],
        "volume_threshold": [1.2, 1.5, 2.0]
    },
    "dead_cat_echo": {
        "initial_drop_threshold": [-0.03, -0.05, -0.07],
        "bounce_threshold": [0.02, 0.03, 0.04],
        "max_bounce_duration": [24, 48, 72]
    },
    "imbalance_pressure": {
        "imbalance_threshold": [0.7, 0.8, 0.9],
        "volume_threshold": [1.2, 1.5, 2.0],
        "lookback_bars": [5, 10, 20]
    }
}

# ============= 数据类 =============

@dataclass
class OptimizationResult:
    best_params: Dict[str, Any]
    best_sharpe: float
    best_trades: int
    best_return: float
    all_results: List[Dict[str, Any]]
    elapsed: float


@dataclass
class WalkForwardResult:
    year: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str
    best_params: Dict[str, Any]
    train_sharpe: float
    train_trades: int
    train_return: float
    val_sharpe: float
    val_trades: int
    val_return: float
    test_sharpe: float
    test_trades: int
    test_return: float
    decay_ratio: float


# ============= 模块级回测函数 =============

def run_single_backtest_module(
    args: Tuple
) -> Dict[str, Any]:
    """
    模块级单次回测函数（可被 pickle）
    
    Args:
        args: (strategy_id, params, bars_data, config_dict, enable_gpu, funding_data, oi_data)
    
    Returns:
        回测结果字典
    """
    strategy_id, params, bars_data, config_dict, enable_gpu, funding_data, oi_data = args
    
    try:
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        
        from runtime.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, SignalType, Bar
        from engines.compute.strategy.strategies import (
            RSIStrategy, MACDStrategy, SMACrossoverStrategy, EMACrossoverStrategy,
            BollingerBandsStrategy, MomentumStrategy, PanicReversalStrategy,
            LongLiquidationBounceStrategy, VolumeClimaxFadeStrategy,
            WeakBounceShortStrategy, OIFlushStrategy, ShortSqueezeStrategy,
            FundingExhaustionTrapStrategy, DeadCatEchoStrategy,
            ImbalancePressureStrategy, SweepDetectionStrategy,
            LiquidityVacuumStrategy, AggressiveFlowStrategy, BreakoutStrategy,
            TrendFollowingStrategy, VolatilityExpansionStrategy,
            BBCompressionBreakoutStrategy, MomentumIgnitionStrategy,
            LeadLagStrategy, PremiumDivergenceStrategy
        )
        
        STRATEGY_MAP = {
            "rsi_oversold": RSIStrategy,
            "rsi_overbought": RSIStrategy,
            "macd_cross": MACDStrategy,
            "sma_cross": SMACrossoverStrategy,
            "ema_cross": EMACrossoverStrategy,
            "bollinger_bands": BollingerBandsStrategy,
            "momentum": MomentumStrategy,
            "panic_reversal": PanicReversalStrategy,
            "long_liquidation_bounce": LongLiquidationBounceStrategy,
            "volume_climax_fade": VolumeClimaxFadeStrategy,
            "weak_bounce_short": WeakBounceShortStrategy,
            "oi_flush": OIFlushStrategy,
            "short_squeeze": ShortSqueezeStrategy,
            "funding_exhaustion_trap": FundingExhaustionTrapStrategy,
            "dead_cat_echo": DeadCatEchoStrategy,
            "imbalance_pressure": ImbalancePressureStrategy,
            "sweep_detection": SweepDetectionStrategy,
            "liquidity_vacuum": LiquidityVacuumStrategy,
            "aggressive_flow": AggressiveFlowStrategy,
            "breakout": BreakoutStrategy,
            "trend_following": TrendFollowingStrategy,
            "volatility_expansion": VolatilityExpansionStrategy,
            "bb_compression_breakout": BBCompressionBreakoutStrategy,
            "momentum_ignition": MomentumIgnitionStrategy,
            "lead_lag": LeadLagStrategy,
            "premium_divergence": PremiumDivergenceStrategy
        }
        
        strategy_cls = STRATEGY_MAP.get(strategy_id)
        if not strategy_cls:
            return {
                "params": params,
                "sharpe": -float('inf'),
                "trades": 0,
                "return": 0.0,
                "error": f"Unknown strategy: {strategy_id}"
            }
        
        strategy = strategy_cls(strategy_id=strategy_id, **params)
        
        class StrategyAdapter:
            def __init__(self, strat, fund_df, op_df):
                self.strategy = strat
                self._closes = []
                self._highs = []
                self._lows = []
                self._volumes = []
                self._funding_df = fund_df
                self._oi_df = op_df
            
            def _get_supplementary_data(self, timestamp, closes):
                data = {}
                try:
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
                "return": result.metrics.total_return,
                "max_drawdown": result.metrics.max_drawdown_pct,
                "win_rate": result.metrics.win_rate,
                "profit_factor": result.metrics.profit_factor
            }
        
        return {
            "params": params,
            "sharpe": -float('inf'),
            "trades": 0,
            "return": 0.0,
            "error": "No result returned"
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "params": params,
            "sharpe": -float('inf'),
            "trades": 0,
            "return": 0.0,
            "error": str(e)
        }


# ============= WalkForwardRunner =============

class WalkForwardRunner:
    """
    Walk-Forward 参数优化运行器
    
    使用系统层加速基础设施：
    - AccelerationService: 统一加速服务
    - CPUExecutor: CPU 多进程执行器
    """
    
    def __init__(self, enable_gpu: bool = False, resample: str = "1h"):
        self.enable_gpu = enable_gpu
        self.resample = resample
        
        self._funding_df = self._load_funding_data()
        self._oi_df = self._load_oi_data()
        
        self._acceleration_service = AccelerationService.create_for_optimization(
            enable_multiprocess=True,
            enable_gpu=enable_gpu
        )
        
        self._optimizer = ParameterOptimizer(
            enable_multiprocess=True,
            enable_gpu=enable_gpu
        )
        
        device_info = DeviceManager.detect()
        logger.info(
            f"WalkForwardRunner initialized: resample={resample}, "
            f"device={device_info.device_type}, enable_gpu={enable_gpu}"
        )
    
    def _load_funding_data(self) -> Optional[pd.DataFrame]:
        data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "funding" / "symbol=BTCUSDT" / "data.parquet"
        if data_path.exists():
            df = read_parquet_safe(data_path)
            if df is not None and len(df) > 0:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                logger.info(f"Loaded funding data: {len(df)} rows")
                return df
        return None
    
    def _load_oi_data(self) -> Optional[pd.DataFrame]:
        data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "oi" / "symbol=BTCUSDT" / "data.parquet"
        if data_path.exists():
            df = read_parquet_safe(data_path)
            if df is not None and len(df) > 0:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                logger.info(f"Loaded OI data: {len(df)} rows")
                return df
        return None
    
    def load_year_data(self, year: int) -> List[Bar]:
        data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / f"year={year}"
        all_bars = []
        
        if data_path.exists():
            for month_dir in sorted(data_path.iterdir()):
                if month_dir.is_dir() and month_dir.name.startswith("month="):
                    parquet_file = month_dir / "data.parquet"
                    if parquet_file.exists():
                        df = read_parquet_safe(parquet_file)
                        if df is not None and len(df) > 0:
                            for _, row in df.iterrows():
                                try:
                                    bar = Bar(
                                        timestamp=pd.to_datetime(row["timestamp"], utc=True),
                                        open=float(row["open"]),
                                        high=float(row["high"]),
                                        low=float(row["low"]),
                                        close=float(row["close"]),
                                        volume=float(row["volume"])
                                    )
                                    all_bars.append(bar)
                                except:
                                    continue
        
        logger.info(f"Loaded {year} data: {len(all_bars)} bars (resample={self.resample})")
        return all_bars
    
    def generate_param_grid(self, strategy_id: str) -> List[Dict[str, Any]]:
        param_grid = DEFAULT_PARAM_GRIDS.get(strategy_id, {
            "param1": [1, 2, 3],
            "param2": [10, 20, 30]
        })
        
        from itertools import product
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = [dict(zip(keys, combo)) for combo in product(*values)]
        
        return combinations
    
    def optimize_params(
        self,
        strategy_id: str,
        optimize_bars: List[Bar],
        use_multiprocess: bool = True
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float], Optional[int], Optional[float]]:
        """
        使用 ParameterOptimizer 优化参数
        
        Args:
            strategy_id: 策略ID
            optimize_bars: 优化用K线
            use_multiprocess: 是否使用多进程
        
        Returns:
            (best_params, best_sharpe, best_trades, best_return)
        """
        param_grid = DEFAULT_PARAM_GRIDS.get(strategy_id, {
            "param1": [1, 2, 3],
            "param2": [10, 20, 30]
        })
        
        bars_data = [
            {
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume
            }
            for bar in optimize_bars
        ]
        
        funding_data = None
        oi_data = None
        if self._funding_df is not None and len(self._funding_df) > 0:
            funding_data = self._funding_df.to_dict("records")
        if self._oi_df is not None and len(self._oi_df) > 0:
            oi_data = self._oi_df.to_dict("records")
        
        result = self._optimizer.optimize(
            strategy_id=strategy_id,
            param_grid=param_grid,
            bars_data=bars_data,
            funding_data=funding_data,
            oi_data=oi_data
        )
        
        logger.info(
            f"Optimization complete: best_params={result.best_params}, "
            f"sharpe={result.best_sharpe:.4f}, elapsed={result.elapsed_time:.2f}s"
        )
        
        return result.best_params, result.best_sharpe, result.best_trades, result.best_return
    
    def run_single_backtest(
        self,
        strategy_id: str,
        params: Dict[str, Any],
        bars: List[Bar]
    ) -> Tuple[Optional[float], Optional[int], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
        from engines.compute.strategy.registry import get_strategy
        
        try:
            strategy = get_strategy(strategy_id, params)
        except:
            # Fallback to old mapping if needed
            strategy_cls = STRATEGY_MAPPING.get(strategy_id)
            if not strategy_cls:
                logger.error(f"Unknown strategy: {strategy_id}")
                return None, 0, 0.0, 0.0, 0.0, 0.0
            strategy = strategy_cls(strategy_id=strategy_id, **params)
        
        class StrategyAdapter:
            def __init__(self, strat, fund_df, op_df):
                self.strategy = strat
                self._closes = []
                self._highs = []
                self._lows = []
                self._volumes = []
                self._funding_df = fund_df
                self._oi_df = op_df
                self._funding_rates = []
                self._oi_values = []
            
            def _calculate_rsi(self, prices, period=14):
                """Calculate RSI indicator"""
                if len(prices) < period + 1:
                    return 50.0
                
                import numpy as np
                deltas = np.diff(prices)
                gains = np.where(deltas > 0, deltas, 0)
                losses = np.where(deltas < 0, -deltas, 0)
                
                avg_gain = np.mean(gains[-period:])
                avg_loss = np.mean(losses[-period:])
                
                if avg_loss == 0:
                    return 100.0
                
                rs = avg_gain / avg_loss
                return 100.0 - (100.0 / (1.0 + rs))
            
            def _calculate_volume_ratio(self, volumes, period=24):
                """Calculate volume ratio (current / average)"""
                if len(volumes) < period + 1:
                    return 1.0
                
                import numpy as np
                current_volume = volumes[-1]
                avg_volume = np.mean(volumes[-period-1:-1])
                
                if avg_volume == 0:
                    return 1.0
                
                return current_volume / avg_volume
            
            def _calculate_zscore(self, values, period=240):
                """Calculate z-score for a series"""
                if len(values) < period:
                    return 0.0
                
                import numpy as np
                recent = values[-period:]
                mean = np.mean(recent)
                std = np.std(recent)
                
                if std == 0:
                    return 0.0
                
                return (values[-1] - mean) / std
            
            def _get_supplementary_data(self, timestamp, closes):
                data = {}
                try:
                    ts_naive = timestamp.replace(tzinfo=None) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None else timestamp
                    
                    if self._funding_df is not None:
                        mask = self._funding_df["timestamp"] <= ts_naive
                        if mask.any():
                            latest = self._funding_df.iloc[-1]
                            funding_rate = float(latest.get("fundingRate", 0.0))
                            data["funding_rate"] = funding_rate
                            self._funding_rates.append(funding_rate)
                            if len(self._funding_rates) > 1000:
                                self._funding_rates = self._funding_rates[-1000:]
                            # Calculate funding z-score
                            data["funding_zscore"] = self._calculate_zscore(self._funding_rates)
                    
                    if self._oi_df is not None:
                        mask = self._oi_df["timestamp"] <= ts_naive
                        if mask.any():
                            latest = self._oi_df.iloc[-1]
                            sum_oi = latest.get("sumOpenInterest", 0.0)
                            sum_oi = float(sum_oi) if sum_oi != "" else 0.0
                            self._oi_values.append(sum_oi)
                            if len(self._oi_values) > 1000:
                                self._oi_values = self._oi_values[-1000:]
                            
                            if mask.sum() > 24:
                                prev_oi = self._oi_df.iloc[-(mask.sum() - 24)].get("sumOpenInterest", 0.0)
                                prev_oi = float(prev_oi) if prev_oi != "" else 0.0
                                if prev_oi > 0:
                                    data["oi_delta"] = (sum_oi - prev_oi) / prev_oi
                    
                    # Add short pressure (simplified)
                    data["short_pressure"] = 0.5
                    
                except Exception as e:
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
                
                # Calculate basic features
                features = {
                    "close_prices": self._closes,
                    "high_prices": self._highs,
                    "low_prices": self._lows,
                    "volumes": self._volumes,
                    "close": bar.close,
                    "high": bar.high,
                    "low": bar.low,
                    "volume": bar.volume,
                    "symbol": "BTCUSDT",
                    "timestamp": bar.timestamp
                }
                
                # Calculate return_1h
                if len(self._closes) > 24:
                    features["return_1h"] = (self._closes[-1] - self._closes[-24]) / self._closes[-24]
                
                # Calculate volume_ratio
                features["volume_ratio"] = self._calculate_volume_ratio(self._volumes)
                
                # Calculate RSI
                features["rsi_14"] = self._calculate_rsi(self._closes)
                
                # Calculate EMA
                if len(self._closes) > 50:
                    import numpy as np
                    def ema(data, period):
                        weights = np.exp(np.linspace(-1., 0., period))
                        weights /= weights.sum()
                        return np.convolve(data, weights, mode='valid')[-1]
                    
                    features["ema_fast"] = ema(self._closes, 10)
                    features["ema_slow"] = ema(self._closes, 50)
                
                # Calculate BB
                if len(self._closes) > 20:
                    import numpy as np
                    sma = np.mean(self._closes[-20:])
                    std = np.std(self._closes[-20:])
                    features["bb_upper"] = sma + 2 * std
                    features["bb_middle"] = sma
                    features["bb_lower"] = sma - 2 * std
                
                # Add supplementary features
                supplementary = self._get_supplementary_data(bar.timestamp, self._closes)
                features.update(supplementary)
                
                # Use generate_signal interface
                try:
                    signal_dict = self.strategy.generate_signal(features)
                    if signal_dict:
                        if signal_dict.get("signal_type") == "buy":
                            return SignalType.BUY
                        elif signal_dict.get("signal_type") == "sell":
                            return SignalType.SELL
                except Exception as e:
                    # Fallback to old calculate method if needed
                    try:
                        from engines.compute.strategy.strategies import ActionType
                        signal = self.strategy.calculate(features)
                        if signal:
                            if signal.action == ActionType.LONG:
                                return SignalType.BUY
                            elif signal.action == ActionType.SHORT:
                                return SignalType.SELL
                    except:
                        pass
                
                return SignalType.HOLD
        
        config = BacktestConfig(
            initial_capital=10000.0,
            commission=0.0004,
            slippage=0.0005,
            position_size=0.1,
            stop_loss=0.1,
            take_profit=0.2,
            leverage=5.0,
            use_realistic_fees=True
        )
        
        adapter = StrategyAdapter(strategy, self._funding_df, self._oi_df)
        
        engine = BacktestEngine(config=config, enable_gpu=self.enable_gpu)
        engine.load_data(bars)
        result = engine.run(adapter)
        
        if result:
            return (
                result.metrics.sharpe_ratio,
                result.metrics.total_trades,
                result.metrics.total_return,
                result.metrics.max_drawdown_pct,
                result.metrics.win_rate,
                result.metrics.profit_factor,
                result.equity_curve
            )
        
        return None, 0, 0.0, 0.0, 0.0, 0.0, None
    
    def split_walkforward_windows(
        self,
        bars: List[Bar],
        year: int
    ) -> Tuple[List[Bar], List[Bar], List[Bar], str, str, str, str, str, str]:
        import datetime
        from datetime import timezone
        
        start_date = datetime.datetime(year, 1, 1, tzinfo=timezone.utc)
        end_date = datetime.datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        
        if not bars:
            return [], [], [], "", "", "", "", "", ""
        
        first_timestamp = bars[0].timestamp
        last_timestamp = bars[-1].timestamp
        
        train_start = max(start_date, first_timestamp)
        train_end = datetime.datetime(year, 6, 1, tzinfo=timezone.utc)
        
        val_start = train_end
        val_end = datetime.datetime(year, 9, 1, tzinfo=timezone.utc)
        
        test_start = val_end
        test_end = min(end_date, last_timestamp)
        
        train_bars = [bar for bar in bars if train_start <= bar.timestamp < train_end]
        val_bars = [bar for bar in bars if val_start <= bar.timestamp < val_end]
        test_bars = [bar for bar in bars if test_start <= bar.timestamp < test_end]
        
        return (
            train_bars, val_bars, test_bars,
            train_start.strftime("%Y-%m-%d"),
            train_end.strftime("%Y-%m-%d"),
            val_start.strftime("%Y-%m-%d"),
            val_end.strftime("%Y-%m-%d"),
            test_start.strftime("%Y-%m-%d"),
            test_end.strftime("%Y-%m-%d")
        )
    
    def run_single_year(
        self,
        year: int,
        strategy_id: str
    ) -> WalkForwardResult:
        logger.info(f"Running Walk-Forward for year {year}, strategy {strategy_id}")
        
        all_bars = self.load_year_data(year)
        
        if not all_bars:
            logger.error(f"No data for year {year}")
            return WalkForwardResult(
                year=year,
                train_start="",
                train_end="",
                val_start="",
                val_end="",
                test_start="",
                test_end="",
                best_params={},
                train_sharpe=-float('inf'),
                train_trades=0,
                train_return=0.0,
                val_sharpe=-float('inf'),
                val_trades=0,
                val_return=0.0,
                test_sharpe=-float('inf'),
                test_trades=0,
                test_return=0.0,
                decay_ratio=0.0
            )
        
        train_bars, val_bars, test_bars, t_start, t_end, v_start, v_end, ts_start, ts_end = self.split_walkforward_windows(all_bars, year)
        
        logger.info(
            f"Train: {len(train_bars)} bars ({t_start} to {t_end}), "
            f"Val: {len(val_bars)} bars ({v_start} to {v_end}), "
            f"Test: {len(test_bars)} bars ({ts_start} to {ts_end})"
        )
        
        best_params, best_sharpe, best_trades, best_return = self.optimize_params(
            strategy_id, train_bars, use_multiprocess=True
        )
        
        if not best_params:
            logger.error("No best params found, skipping this year")
            return WalkForwardResult(
                year=year,
                train_start=t_start,
                train_end=t_end,
                val_start=v_start,
                val_end=v_end,
                test_start=ts_start,
                test_end=ts_end,
                best_params={},
                train_sharpe=best_sharpe or -float('inf'),
                train_trades=best_trades or 0,
                train_return=best_return or 0.0,
                val_sharpe=-float('inf'),
                val_trades=0,
                val_return=0.0,
                test_sharpe=-float('inf'),
                test_trades=0,
                test_return=0.0,
                decay_ratio=0.0
            )
        
        logger.info(f"Running val with best params: {best_params}")
        val_sharpe, val_trades, val_return, _, _, _, _ = self.run_single_backtest(
            strategy_id, best_params, val_bars
        )
        
        logger.info(f"Running test with best params: {best_params}")
        test_sharpe, test_trades, test_return, _, _, _, _ = self.run_single_backtest(
            strategy_id, best_params, test_bars
        )
        
        decay_ratio = 0.0
        if best_sharpe > 0:
            decay_ratio = (best_sharpe - test_sharpe) / best_sharpe if test_sharpe else 1.0
        
        logger.info(
            f"Year {year} results: Train Sharpe={best_sharpe:.4f} ({best_trades} trades), "
            f"Val Sharpe={val_sharpe:.4f} ({val_trades} trades), "
            f"Test Sharpe={test_sharpe:.4f} ({test_trades} trades), "
            f"Decay Ratio={decay_ratio:.4f}"
        )
        
        return WalkForwardResult(
            year=year,
            train_start=t_start,
            train_end=t_end,
            val_start=v_start,
            val_end=v_end,
            test_start=ts_start,
            test_end=ts_end,
            best_params=best_params,
            train_sharpe=best_sharpe,
            train_trades=best_trades,
            train_return=best_return,
            val_sharpe=val_sharpe,
            val_trades=val_trades,
            val_return=val_return,
            test_sharpe=test_sharpe,
            test_trades=test_trades,
            test_return=test_return,
            decay_ratio=decay_ratio
        )
    
    def run_multiple_years(
        self,
        strategy_id: str,
        years: List[int]
    ) -> List[WalkForwardResult]:
        all_results = []
        
        for year in years:
            result = self.run_single_year(year, strategy_id)
            all_results.append(result)
        
        return all_results
    
    def save_results_to_csv(
        self,
        results: List[WalkForwardResult],
        output_path: str
    ):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Year",
                "Train Start", "Train End", "Val Start", "Val End", "Test Start", "Test End",
                "Best Params", "Train Sharpe", "Train Trades", "Train Return",
                "Val Sharpe", "Val Trades", "Val Return",
                "Test Sharpe", "Test Trades", "Test Return", "Decay Ratio"
            ])
            
            for result in results:
                writer.writerow([
                    result.year,
                    result.train_start, result.train_end, result.val_start, result.val_end, result.test_start, result.test_end,
                    json.dumps(result.best_params),
                    result.train_sharpe, result.train_trades, result.train_return,
                    result.val_sharpe, result.val_trades, result.val_return,
                    result.test_sharpe, result.test_trades, result.test_return,
                    result.decay_ratio
                ])
        
        logger.info(f"Results saved to: {output_path}")


# ============= 主函数 =============

def main():
    strategy_id = "long_liquidation_bounce"
    years = [2023]  # Test 2023 first
    
    logger.info("=" * 80)
    logger.info("Starting Walk-Forward Optimization (Architecture Optimized)")
    logger.info("=" * 80)
    logger.info(f"Strategy: {strategy_id}")
    logger.info(f"Years: {years}")
    logger.info("=" * 80)
    
    runner = WalkForwardRunner(enable_gpu=False, resample="1h")
    
    results = runner.run_multiple_years(strategy_id, years)
    
    output_csv = Path(backend_path) / ".." / "scripts" / "output" / f"walkforward_fixed_{strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    runner.save_results_to_csv(results, str(output_csv))
    
    logger.info("=" * 80)
    logger.info("Walk-Forward Optimization Complete")
    logger.info("=" * 80)
    
    logger.info("\nYearly Results:")
    logger.info("-" * 80)
    
    avg_test_sharpe = 0.0
    avg_decay_ratio = 0.0
    valid_count = 0
    
    for result in results:
        logger.info(
            f"Year {result.year}: Train Sharpe={result.train_sharpe:.4f} ({result.train_trades} trades), "
            f"Test Sharpe={result.test_sharpe:.4f} ({result.test_trades} trades), "
            f"Decay Ratio={result.decay_ratio:.4f}"
        )
        
        if result.test_sharpe != -float('inf'):
            avg_test_sharpe += result.test_sharpe
            avg_decay_ratio += result.decay_ratio
            valid_count += 1
    
    if valid_count > 0:
        avg_test_sharpe /= valid_count
        avg_decay_ratio /= valid_count
        
        logger.info("-" * 80)
        logger.info(
            f"Average Test Sharpe: {avg_test_sharpe:.4f}, "
            f"Average Decay Ratio: {avg_decay_ratio:.4f}"
        )
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
