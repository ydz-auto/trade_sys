"""
Parallel Backtest Module - 子进程回测函数

提供在子进程中运行单次回测的能力，支持 GPU 加速
"""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pandas as pd


@dataclass
class BacktestResult:
    """单次回测结果"""
    sharpe: Optional[float]
    total_trades: int
    total_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    params: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def run_backtest_in_subprocess(args: tuple) -> BacktestResult:
    """
    在子进程中运行单次回测（可被pickle）
    
    Args:
        args: (strategy_id, params, bars_data, config_dict, enable_gpu, funding_data, oi_data)
    
    Returns:
        BacktestResult: 回测结果
    """
    strategy_id, params, bars_data, config_dict, enable_gpu, funding_data, oi_data = args
    
    try:
        import os
        import sys
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        sys.path.insert(0, backend_path)
        
        from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, SignalType, Bar
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
        from engines.compute.strategy.behavioral_strategies import (
            OpenInterestBehaviorStrategy, FundingExtremeReversalStrategy,
            LiquidationCascadeStrategy, CVDDivergenceStrategy,
            WhaleTradeStrategy, FundingSettlementStrategy
        )
        
        STRATEGY_CLASS_MAP = {
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
        
        strategy_cls = STRATEGY_CLASS_MAP.get(strategy_id)
        if not strategy_cls:
            return BacktestResult(
                sharpe=None, total_trades=0, total_return=0.0,
                max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                params=params, error=f"Unknown strategy: {strategy_id}"
            )
        
        strategy = strategy_cls(strategy_id=strategy_id, **params)
        
        class SubprocessStrategyAdapter:
            def __init__(self, strategy, funding_df_data, oi_df_data):
                self.strategy = strategy
                self._closes = []
                self._highs = []
                self._lows = []
                self._volumes = []
                self._funding_df_data = funding_df_data
                self._oi_df_data = oi_df_data
            
            def _get_supplementary_data(self, timestamp, closes):
                data = {}
                try:
                    ts_naive = timestamp.replace(tzinfo=None) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None else timestamp
                    
                    if self._funding_df_data is not None:
                        mask = self._funding_df_data["timestamp"] <= ts_naive
                        if mask.any():
                            latest = self._funding_df_data.iloc[-1]
                            data["funding_rate"] = float(latest.get("fundingRate", 0.0))
                    
                    if self._oi_df_data is not None:
                        mask = self._oi_df_data["timestamp"] <= ts_naive
                        if mask.any():
                            latest = self._oi_df_data.iloc[-1]
                            sum_oi = latest.get("sumOpenInterest", 0.0)
                            sum_oi = float(sum_oi) if sum_oi != "" else 0.0
                            if mask.sum() > 24:
                                prev_oi = self._oi_df_data.iloc[-(mask.sum() - 24)].get("sumOpenInterest", 0.0)
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
        
        adapter = SubprocessStrategyAdapter(strategy, funding_df, oi_df)
        
        bars = [Bar(**b) for b in bars_data]
        
        engine = BacktestEngine(config=config, enable_gpu=enable_gpu)
        engine.load_data(bars)
        result = engine.run(adapter)
        
        if result:
            return BacktestResult(
                sharpe=result.metrics.sharpe_ratio,
                total_trades=result.metrics.total_trades,
                total_return=result.metrics.total_return,
                max_drawdown=result.metrics.max_drawdown_pct,
                win_rate=result.metrics.win_rate,
                profit_factor=result.metrics.profit_factor,
                params=params
            )
        return BacktestResult(
            sharpe=None, total_trades=0, total_return=0.0,
            max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
            params=params, error="No result returned"
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return BacktestResult(
            sharpe=None, total_trades=0, total_return=0.0,
            max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
            params=params, error=str(e)
        )
