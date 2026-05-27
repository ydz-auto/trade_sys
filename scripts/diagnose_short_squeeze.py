#!/usr/bin/env python3
"""
诊断脚本：分析 short_squeeze 策略的条件通过率
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy
from runtime.replay_runtime.backtest_engine import Bar

logger = get_logger("strategy_diagnosis")


def load_data(year):
    """Load K-line, funding, and OI data"""
    # Load K-line data
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
                                    timestamp=row["timestamp"],
                                    open=float(row["open"]),
                                    high=float(row["high"]),
                                    low=float(row["low"]),
                                    close=float(row["close"]),
                                    volume=float(row["volume"])
                                )
                                all_bars.append(bar)
                            except Exception as e:
                                pass
    
    # Load funding data
    funding_df = None
    funding_path = Path(backend_path) / "data_lake" / "deribit" / "funding_rates" / "BTC-USDT-SWAP.parquet"
    if funding_path.exists():
        funding_df = read_parquet_safe(funding_path)
        if funding_df is not None and len(funding_df) > 0:
            import pandas as pd
            funding_df["timestamp"] = pd.to_datetime(funding_df["timestamp"], utc=True)
    
    # Load OI data
    oi_df = None
    oi_path = Path(backend_path) / "data_lake" / "deribit" / "open_interest" / "BTC-USDT-SWAP.parquet"
    if oi_path.exists():
        oi_df = read_parquet_safe(oi_path)
        if oi_df is not None and len(oi_df) > 0:
            import pandas as pd
            oi_df["timestamp"] = pd.to_datetime(oi_df["timestamp"], utc=True)
    
    return all_bars, funding_df, oi_df


class StrategyDiagnostic:
    def __init__(self, strategy_id, params):
        self.strategy_id = strategy_id
        self.params = params
        self.strategy = get_strategy(strategy_id, params)
        
        # Stats
        self.total_bars = 0
        self.funding_zscore_missing = 0
        self.funding_zscore_checked = 0
        self.funding_zscore_passed = 0
        self.oi_delta_missing = 0
        self.oi_delta_checked = 0
        self.oi_delta_passed = 0
        self.oi_growth_passed = 0
        self.all_conditions_passed = 0
        self.signals_generated = 0
        
        # State for calculations
        self._closes = []
        self._volumes = []
        self._funding_rates = []
        self._oi_values = []
        
        self.funding_df = None
        self.oi_df = None
    
    def set_dataframes(self, funding_df, oi_df):
        self.funding_df = funding_df
        self.oi_df = oi_df
    
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
    
    def _get_supplementary_data(self, timestamp):
        data = {}
        try:
            import pandas as pd
            ts_naive = timestamp.replace(tzinfo=None) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None else timestamp
            
            if self.funding_df is not None:
                mask = self.funding_df["timestamp"] <= ts_naive
                if mask.any():
                    latest = self.funding_df.iloc[-1]
                    funding_rate = float(latest.get("fundingRate", 0.0))
                    data["funding_rate"] = funding_rate
                    self._funding_rates.append(funding_rate)
                    if len(self._funding_rates) > 1000:
                        self._funding_rates = self._funding_rates[-1000:]
                    # Calculate funding z-score
                    data["funding_zscore"] = self._calculate_zscore(self._funding_rates)
            
            if self.oi_df is not None:
                mask = self.oi_df["timestamp"] <= ts_naive
                if mask.any():
                    latest = self.oi_df.iloc[-1]
                    sum_oi = latest.get("sumOpenInterest", 0.0)
                    sum_oi = float(sum_oi) if sum_oi != "" else 0.0
                    self._oi_values.append(sum_oi)
                    if len(self._oi_values) > 1000:
                        self._oi_values = self._oi_values[-1000:]
                    
                    if mask.sum() > 24:
                        prev_oi = self.oi_df.iloc[-(mask.sum() - 24)].get("sumOpenInterest", 0.0)
                        prev_oi = float(prev_oi) if prev_oi != "" else 0.0
                        if prev_oi > 0:
                            data["oi_delta"] = (sum_oi - prev_oi) / prev_oi
            
            # Add short pressure (simplified)
            data["short_pressure"] = 0.5
            
        except Exception as e:
            pass
        return data
    
    def process_bar(self, bar):
        self.total_bars += 1
        
        # Update state
        self._closes.append(bar.close)
        self._volumes.append(bar.volume)
        
        if len(self._closes) > 600:
            self._closes = self._closes[-600:]
            self._volumes = self._volumes[-600:]
        
        # Calculate features
        features = {
            "close_prices": self._closes,
            "high_prices": [bar.high],
            "low_prices": [bar.low],
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
        supplementary = self._get_supplementary_data(bar.timestamp)
        features.update(supplementary)
        
        # Diagnose individual conditions
        funding_zscore = features.get("funding_zscore")
        oi_delta = features.get("oi_delta")
        funding_threshold = self.params.get("funding_zscore_threshold", -2.0)
        oi_threshold = self.params.get("oi_growth_threshold", 0.0)
        
        if funding_zscore is None:
            self.funding_zscore_missing += 1
        else:
            self.funding_zscore_checked += 1
            if funding_zscore < funding_threshold:
                self.funding_zscore_passed += 1
        
        if oi_delta is None:
            self.oi_delta_missing += 1
        else:
            self.oi_delta_checked += 1
            if oi_delta > oi_threshold:
                self.oi_delta_passed += 1
            if oi_delta > 0.02:
                self.oi_growth_passed += 1
        
        # Check all conditions together
        if (funding_zscore is not None and oi_delta is not None and
            funding_zscore < funding_threshold and 
            oi_delta > oi_threshold and 
            oi_delta > 0.02):
            self.all_conditions_passed += 1
        
        # Try to generate signal
        try:
            signal_dict = self.strategy.generate_signal(features)
            if signal_dict:
                self.signals_generated += 1
        except Exception as e:
            pass
    
    def print_report(self):
        print("\n" + "="*80)
        print("STRATEGY DIAGNOSTIC REPORT")
        print("="*80)
        print(f"Strategy: {self.strategy_id}")
        print(f"Params: {self.params}")
        print(f"Total bars processed: {self.total_bars}")
        print()
        print("Condition Analysis:")
        print("-"*40)
        
        if self.funding_zscore_checked > 0:
            print(f"  Funding z-score checked: {self.funding_zscore_checked}")
            print(f"  Funding z-score passed: {self.funding_zscore_passed} ({self.funding_zscore_passed / self.funding_zscore_checked * 100:.2f}%)")
        if self.funding_zscore_missing > 0:
            print(f"  Funding z-score missing: {self.funding_zscore_missing}")
        print()
        
        if self.oi_delta_checked > 0:
            print(f"  OI delta checked: {self.oi_delta_checked}")
            print(f"  OI delta > threshold passed: {self.oi_delta_passed} ({self.oi_delta_passed / self.oi_delta_checked * 100:.2f}%)")
            print(f"  OI delta > 0.02 passed: {self.oi_growth_passed} ({self.oi_growth_passed / self.oi_delta_checked * 100:.2f}%)")
        if self.oi_delta_missing > 0:
            print(f"  OI delta missing: {self.oi_delta_missing}")
        print()
        
        print(f"  All conditions passed together: {self.all_conditions_passed} times")
        print(f"  Signals generated: {self.signals_generated}")
        if self.total_bars > 0:
            print(f"  Signal rate: {self.signals_generated / self.total_bars * 100:.4f}%")
        print()
        print("="*80)


def main():
    print("Running strategy diagnosis...")
    
    # Load data
    year = 2023
    all_bars, funding_df, oi_df = load_data(year)
    
    if not all_bars:
        print("No data loaded!")
        return
    
    print(f"Loaded {len(all_bars)} bars, funding data: {funding_df is not None}, OI data: {oi_df is not None}")
    
    # Test with relaxed parameters first
    relaxed_params = {
        "funding_zscore_threshold": -1.0,
        "oi_growth_threshold": 0.0
    }
    
    print("\n" + "="*80)
    print("Testing with RELAXED parameters:")
    print(f"  funding_zscore_threshold: {relaxed_params['funding_zscore_threshold']}")
    print(f"  oi_growth_threshold: {relaxed_params['oi_growth_threshold']}")
    print("="*80)
    
    diagnostic = StrategyDiagnostic("short_squeeze", relaxed_params)
    diagnostic.set_dataframes(funding_df, oi_df)
    
    # Process a sample
    sample_size = min(len(all_bars), 100000)
    print(f"Processing first {sample_size} bars...")
    
    for i, bar in enumerate(all_bars[:sample_size]):
        diagnostic.process_bar(bar)
        if (i + 1) % 10000 == 0:
            print(f"  Processed {i + 1}/{sample_size} bars")
    
    diagnostic.print_report()
    
    # Also test with original parameters
    print("\n" + "="*80)
    print("Testing with ORIGINAL parameters:")
    original_params = {
        "funding_zscore_threshold": -3.0,
        "oi_growth_threshold": 0.005
    }
    print(f"  funding_zscore_threshold: {original_params['funding_zscore_threshold']}")
    print(f"  oi_growth_threshold: {original_params['oi_growth_threshold']}")
    print("="*80)
    
    diagnostic2 = StrategyDiagnostic("short_squeeze", original_params)
    diagnostic2.set_dataframes(funding_df, oi_df)
    
    print(f"Processing first {sample_size} bars...")
    
    for i, bar in enumerate(all_bars[:sample_size]):
        diagnostic2.process_bar(bar)
        if (i + 1) % 10000 == 0:
            print(f"  Processed {i + 1}/{sample_size} bars")
    
    diagnostic2.print_report()


if __name__ == "__main__":
    main()
