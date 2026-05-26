#!/usr/bin/env python3
"""
诊断脚本：测试 short_squeeze 策略
- 输出每个条件的通过率
- 统计交易次数、Sharpe 等指标
"""
import sys
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Add backend to path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, 'runtimes'))

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy, get_strategy_info
from engines.compute.strategy.strategies import ShortSqueezeStrategy
from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, Bar

logger = get_logger("strategy_diagnosis")


class StrategyDiagnosis:
    def __init__(self, strategy_id, params=None):
        self.strategy_id = strategy_id
        self.params = params or {}
        
        # Condition tracking
        self.condition_stats = defaultdict(int)
        self.total_bars = 0
        self.signals_generated = 0
        
        # Feature tracking
        self.feature_values = defaultdict(list)
        
        # Load strategy
        self.strategy = get_strategy(strategy_id, params)
        self.strategy_info = get_strategy_info(strategy_id)
        
        logger.info(f"Loaded strategy {strategy_id} with params {self.params}")
    
    def _get_supplementary_data(self, timestamp, closes):
        """Get supplementary data (funding, OI) - simplified version"""
        data = {}
        try:
            # Add dummy features for testing
            data["funding_zscore"] = 0.0
            data["oi_delta"] = 0.01
            data["short_pressure"] = 0.5
            data["return_1h"] = 0.005
        except Exception as e:
            logger.debug(f"Error getting supplementary data: {e}")
        return data
    
    def diagnose_bar(self, bar, previous_bars=None):
        """Diagnose a single bar, track condition passes"""
        self.total_bars += 1
        
        # Prepare features
        features = {
            "close": bar.close,
            "high": bar.high,
            "low": bar.low,
            "volume": bar.volume,
            "timestamp": bar.timestamp,
        }
        
        if previous_bars and len(previous_bars) > 0:
            closes = [b.close for b in previous_bars] + [bar.close]
            features["close_prices"] = closes
        else:
            features["close_prices"] = [bar.close]
        
        # Add supplementary features (simplified)
        supplementary = self._get_supplementary_data(bar.timestamp, features.get("close_prices", []))
        features.update(supplementary)
        
        # Track individual conditions for ShortSqueezeStrategy
        if self.strategy_id == "short_squeeze":
            self._diagnose_short_squeeze(features)
        
        # Generate signal
        try:
            signal = self.strategy.generate_signal(features)
            if signal:
                self.signals_generated += 1
                logger.debug(f"Signal generated: {signal}")
                return signal
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
        
        return None
    
    def _diagnose_short_squeeze(self, features):
        """Diagnose short squeeze strategy conditions"""
        funding_zscore = features.get("funding_zscore")
        oi_delta = features.get("oi_delta")
        
        # Get thresholds from params or defaults
        funding_threshold = self.params.get("funding_zscore_threshold", -2.0)
        oi_threshold = self.params.get("oi_growth_threshold", 0.0)
        
        # Check individual conditions
        if funding_zscore is not None:
            self.feature_values["funding_zscore"].append(funding_zscore)
            if funding_zscore < funding_threshold:
                self.condition_stats["funding_zscore_passed"] += 1
            else:
                self.condition_stats["funding_zscore_failed"] += 1
        else:
            self.condition_stats["funding_zscore_missing"] += 1
        
        if oi_delta is not None:
            self.feature_values["oi_delta"].append(oi_delta)
            if oi_delta > oi_threshold:
                self.condition_stats["oi_delta_passed"] += 1
            else:
                self.condition_stats["oi_delta_failed"] += 1
        else:
            self.condition_stats["oi_delta_missing"] += 1
        
        # Check if all conditions passed
        all_passed = (
            funding_zscore is not None and funding_zscore < funding_threshold and
            oi_delta is not None and oi_delta > oi_threshold and
            oi_delta > 0.02  # Extra condition from strategy
        )
        
        if all_passed:
            self.condition_stats["all_conditions_passed"] += 1
        else:
            self.condition_stats["all_conditions_failed"] += 1
    
    def print_report(self):
        """Print diagnosis report"""
        print("\n" + "="*80)
        print("STRATEGY DIAGNOSIS REPORT")
        print("="*80)
        print(f"Strategy: {self.strategy_id}")
        print(f"Params: {self.params}")
        print(f"Total bars: {self.total_bars}")
        print(f"Signals generated: {self.signals_generated}")
        print(f"Signal rate: {self.signals_generated / self.total_bars * 100:.2f}%\n")
        
        print("Condition Stats:")
        print("-" * 40)
        for key, count in sorted(self.condition_stats.items()):
            if key.endswith("_passed") or key.endswith("_failed") or key.endswith("_missing"):
                print(f"  {key}: {count} ({count / self.total_bars * 100:.2f}%)")
        
        print("\nFeature Stats:")
        print("-" * 40)
        for feature, values in self.feature_values.items():
            if len(values) > 0:
                import numpy as np
                print(f"  {feature}:")
                print(f"    Min: {np.min(values):.4f}")
                print(f"    Max: {np.max(values):.4f}")
                print(f"    Mean: {np.mean(values):.4f}")
                print(f"    Std: {np.std(values):.4f}")


def load_year_data(year):
    """Load data for a specific year"""
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
                                    timestamp=datetime.fromtimestamp(row["timestamp"], tz=datetime.UTC) if isinstance(row["timestamp"], (int, float)) else row["timestamp"],
                                    open=float(row["open"]),
                                    high=float(row["high"]),
                                    low=float(row["low"]),
                                    close=float(row["close"]),
                                    volume=float(row["volume"])
                                )
                                all_bars.append(bar)
                            except Exception as e:
                                logger.debug(f"Error parsing bar: {e}")
    
    logger.info(f"Loaded {len(all_bars)} bars for year {year}")
    return all_bars


def main():
    print("\nRunning strategy diagnosis...")
    
    # Test strategy
    strategy_id = "short_squeeze"
    
    # Test params - let's use more relaxed thresholds
    params = {
        "funding_zscore_threshold": -1.5,  # More relaxed
        "oi_growth_threshold": 0.005,      # More relaxed
    }
    
    # Load data
    bars = load_year_data(2023)
    if not bars:
        print("No data loaded!")
        return
    
    # Run diagnosis
    diagnosis = StrategyDiagnosis(strategy_id, params)
    
    previous_bars = []
    for i, bar in enumerate(bars[:5000]):  # Test first 5000 bars
        diagnosis.diagnose_bar(bar, previous_bars)
        previous_bars.append(bar)
        if len(previous_bars) > 100:
            previous_bars.pop(0)
    
    # Print report
    diagnosis.print_report()
    
    # Now run full backtest with relaxed params
    print("\n" + "="*80)
    print("RUNNING FULL BACKTEST WITH RELAXED PARAMS")
    print("="*80)
    
    # Create backtest config
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
    
    # Create strategy
    strategy = ShortSqueezeStrategy(
        strategy_id=strategy_id,
        **params
    )
    
    # Create simple adapter
    class SimpleStrategyAdapter:
        def __init__(self, strategy):
            self.strategy = strategy
            self._closes = []
        
        def _get_supplementary_data(self, timestamp, closes):
            """Simplified supplementary data with test values"""
            return {
                "funding_zscore": -2.5,  # Always pass
                "oi_delta": 0.03,        # Always pass
                "short_pressure": 0.6,
                "return_1h": 0.005
            }
        
        def on_bar(self, bar):
            self._closes.append(bar.close)
            if len(self._closes) > 100:
                self._closes.pop(0)
            
            features = {
                "close": bar.close,
                "high": bar.high,
                "low": bar.low,
                "volume": bar.volume,
                "timestamp": bar.timestamp,
                "close_prices": self._closes
            }
            
            supplementary = self._get_supplementary_data(bar.timestamp, self._closes)
            features.update(supplementary)
            
            try:
                signal = self.strategy.generate_signal(features)
                if signal:
                    if signal["signal_type"] == "buy":
                        return "BUY"
                    elif signal["signal_type"] == "sell":
                        return "SELL"
            except Exception as e:
                logger.error(f"Error in adapter: {e}")
            
            return "HOLD"
    
    # Run backtest
    engine = BacktestEngine(config=config, enable_gpu=False)
    engine.load_data(bars[:5000])
    result = engine.run(SimpleStrategyAdapter(strategy))
    
    if result:
        print(f"\nBacktest Results:")
        print(f"  Total Trades: {result.metrics.total_trades}")
        print(f"  Sharpe Ratio: {result.metrics.sharpe_ratio:.4f}")
        print(f"  Profit Factor: {result.metrics.profit_factor:.4f}")
        print(f"  Total Return: {result.metrics.total_return:.4f}%")
        print(f"  Max Drawdown: {result.metrics.max_drawdown_pct:.4f}%")
        print(f"  Win Rate: {result.metrics.win_rate:.4f}")
    else:
        print("No backtest result!")


if __name__ == "__main__":
    main()

