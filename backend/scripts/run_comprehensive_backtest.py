#!/usr/bin/env python3
"""
综合策略回测脚本 - 近五个月数据

整合以下所有策略:
1. BTC Swing 基础策略 (RSI+MACD+EMA)
2. 经典技术指标策略 (3个): BollingerBands, MACross, RSI_MACD
3. 创新策略研究矩阵 (8个)
4. Crypto Behavioral Playbooks (7个)
5. 优化做空策略 (6个)
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from infrastructure.data_lake import get_features_path, get_research_path

logger = get_logger("comprehensive_backtest")


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.3
    stop_loss: float = 0.015
    take_profit: float = 0.03
    max_hold_hours: int = 4
    leverage: float = 50.0
    stop_loss_capital_pct: float = 0.10
    take_profit_capital_pct: float = 0.60


@dataclass
class StrategyResult:
    name: str
    category: str
    direction: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    avg_hold_hours: float = 0.0
    events_detected: int = 0
    trades: List[Dict] = field(default_factory=list)


class ComprehensiveBacktester:
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.df: pd.DataFrame = None
        self.df_5m: pd.DataFrame = None
        self.results: Dict[str, StrategyResult] = {}
        
    def load_data(self, months=60):
        data_path = get_features_path("binance", "BTCUSDT") / "features_with_structure.parquet"
        
        try:
            df = pd.read_parquet(data_path)
        except Exception as e:
            logger.error(f"Cannot load parquet file: {e}")
            return pd.DataFrame()
        
        logger.info(f"Loaded {len(df)} rows, date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        self.df = df
        return df
    
    def prepare_5m_data(self):
        if self.df is None or self.df.empty:
            return
        
        logger.info("Resampling data to 5m...")
        
        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "funding_rate": "last",
            "funding_zscore": "last",
            "funding_delta": "last",
            "bb_upper": "last",
            "bb_lower": "last",
            "bb_middle": "last",
            "bb_position": "last",
            "rsi_14": "last",
            "regime": "last",
            "regime_code": "last",
            "spike_up": "max",
            "spike_down": "max",
            "major_spike_up": "max",
            "major_spike_down": "max",
            "trend_exhaustion": "last",
            "trend_healthy": "last",
            "momentum_shift": "last",
            "volatility_surge": "last",
            "state_squeeze": "max",
            "state_panic_dump": "max",
            "state_breakout": "max",
            "state_accumulation": "max",
            "breakout_high_24h": "max",
            "breakout_low_24h": "max",
            "breakout_strength_24h": "max",
        }
        
        available_cols = [c for c in agg_dict.keys() if c in self.df.columns]
        agg_dict_filtered = {k: v for k, v in agg_dict.items() if k in available_cols}
        
        self.df_5m = self.df.set_index("timestamp").resample("5min", origin="start").agg(agg_dict_filtered).ffill()
        self.df_5m = self.df_5m.dropna(subset=["close"]).reset_index()
        
        self._add_features()
        logger.info(f"Prepared 5m data: {len(self.df_5m)} rows")
    
    def _add_features(self):
        df = self.df_5m
        n = len(df)
        
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        volumes = df["volume"].values
        avg_volumes = np.convolve(volumes, np.ones(288)/288, mode='same')
        df["volume_ratio"] = df["volume"] / (avg_volumes + 0.001)
        
        df["return_5m"] = df["close"].pct_change(1)
        df["return_15m"] = df["close"].pct_change(3)
        df["return_1h"] = df["close"].pct_change(12)
        df["return_4h"] = df["close"].pct_change(48)
        
        df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
        df["body_ratio"] = abs(df["close"] - df["open"]) / (df["high"] - df["low"] + 0.001)
        
        if "bb_upper" in df.columns and "bb_lower" in df.columns:
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["bb_middle"] + 0.001)
        
        df["intrabar_volatility"] = (df["high"] - df["low"]) / (df["close"] + 0.001)
        
        def get_session(hour):
            if 0 <= hour < 8: return "asia"
            elif 8 <= hour < 16: return "europe"
            else: return "us"
        df["session"] = df["hour"].apply(get_session)
        df["session_open"] = df["hour"].isin([0, 8, 16])
        
        df["low_liquidity"] = df["volume_ratio"] < 0.7
        df["volume_spike"] = df["volume_ratio"] > 2.5
        df["spread_widening"] = df["intrabar_volatility"] / (df["volume_ratio"] + 0.01) > 0.03
        
        rolling_highs = df["high"].rolling(288, min_periods=1).max()
        df["breakout_strength_24h_calc"] = (df["high"] - rolling_highs) / (rolling_highs + 0.001)
        
        self.df_5m = df.fillna(0)

    def run_all_strategies(self):
        self._run_btc_swing()
        self._run_classic_strategies()
        self._run_innovation_strategies()
        self._run_behavioral_playbooks()
        self._run_short_strategies()
    
    def _run_btc_swing(self):
        logger.info("Running BTC Swing Strategy...")
        df = self.df_5m.copy()
        
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        
        trades = []
        position = None
        
        for i in range(50, len(df)):
            row = df.iloc[i]
            
            rsi = row.get("rsi_14", 50)
            if pd.isna(rsi):
                rsi = 50
            
            ema_short = row["ema_20"]
            ema_long = row["ema_50"]
            ema_cross_up = ema_short > ema_long
            
            prev_row = df.iloc[i-1]
            prev_ema_cross_up = prev_row["ema_20"] > prev_row["ema_50"]
            golden_cross = ema_cross_up and not prev_ema_cross_up
            death_cross = not ema_cross_up and prev_ema_cross_up
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 96:
                    close_reason = "time_exit"
                elif row["low"] <= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif row["high"] >= position["take_profit_price"]:
                    close_reason = "take_profit"
                elif rsi >= 70:
                    close_reason = "rsi_exit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"],
                                   "close_reason": close_reason, **pnl})
                    position = None
            
            if not position:
                if rsi <= 30 and golden_cross:
                    position = self._open_position(row, "long", "btc_swing", 0.03, 0.05)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"],
                           "close_reason": "end_of_data", **pnl})
        
        self.results["btc_swing"] = self._compile_result("BTC Swing", "经典技术", "双向", trades)
    
    def _run_classic_strategies(self):
        logger.info("Running Classic Technical Strategies...")
        
        self._run_bollinger_bands()
        self._run_ma_cross()
        self._run_rsi_macd()
    
    def _run_bollinger_bands(self):
        df = self.df_5m.copy()
        trades = []
        position = None
        
        for i in range(20, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            bb_upper = row.get("bb_upper", 0)
            bb_lower = row.get("bb_lower", 0)
            
            if bb_upper == 0 or bb_lower == 0:
                continue
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 48:
                    close_reason = "time_exit"
                elif row["low"] <= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif row["high"] >= position["take_profit_price"]:
                    close_reason = "take_profit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"],
                                   "close_reason": close_reason, **pnl})
                    position = None
            
            if not position:
                if prev_row["close"] >= bb_lower and row["close"] < bb_lower:
                    position = self._open_position(row, "long", "bollinger_bands", 0.02, 0.03)
                elif prev_row["close"] <= bb_upper and row["close"] > bb_upper:
                    position = self._open_position(row, "short", "bollinger_bands", 0.02, 0.03)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"],
                           "close_reason": "end_of_data", **pnl})
        
        self.results["bollinger_bands"] = self._compile_result("Bollinger Bands", "经典技术", "双向", trades)
    
    def _run_ma_cross(self):
        df = self.df_5m.copy()
        df["ma_50"] = df["close"].rolling(50).mean()
        df["ma_200"] = df["close"].rolling(200).mean()
        
        trades = []
        position = None
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 168:
                    close_reason = "time_exit"
                elif row["low"] <= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif row["high"] >= position["take_profit_price"]:
                    close_reason = "take_profit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"],
                                   "close_reason": close_reason, **pnl})
                    position = None
            
            if not position:
                golden_cross = prev_row["ma_50"] <= prev_row["ma_200"] and row["ma_50"] > row["ma_200"]
                death_cross = prev_row["ma_50"] >= prev_row["ma_200"] and row["ma_50"] < row["ma_200"]
                
                if golden_cross:
                    position = self._open_position(row, "long", "ma_cross", 0.03, 0.05)
                elif death_cross:
                    position = self._open_position(row, "short", "ma_cross", 0.03, 0.05)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"],
                           "close_reason": "end_of_data", **pnl})
        
        self.results["ma_cross"] = self._compile_result("MA Cross (50/200)", "经典技术", "双向", trades)
    
    def _run_rsi_macd(self):
        df = self.df_5m.copy()
        
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        
        trades = []
        position = None
        
        for i in range(26, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            rsi = row.get("rsi_14", 50)
            if pd.isna(rsi):
                rsi = 50
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 72:
                    close_reason = "time_exit"
                elif row["low"] <= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif row["high"] >= position["take_profit_price"]:
                    close_reason = "take_profit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"],
                                   "close_reason": close_reason, **pnl})
                    position = None
            
            if not position:
                macd_cross_up = prev_row["macd"] <= prev_row["macd_signal"] and row["macd"] > row["macd_signal"]
                macd_cross_down = prev_row["macd"] >= prev_row["macd_signal"] and row["macd"] < row["macd_signal"]
                
                if rsi <= 30 and macd_cross_up:
                    position = self._open_position(row, "long", "rsi_macd", 0.02, 0.03)
                elif rsi >= 70 and macd_cross_down:
                    position = self._open_position(row, "short", "rsi_macd", 0.02, 0.03)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"],
                           "close_reason": "end_of_data", **pnl})
        
        self.results["rsi_macd"] = self._compile_result("RSI+MACD", "经典技术", "双向", trades)
    
    def _run_innovation_strategies(self):
        logger.info("Running Innovation Strategies...")
        
        strategies = {
            "leveraged_short_squeeze": self._detect_leveraged_short_squeeze,
            "micro_range_ripples": self._detect_micro_range_ripples,
            "cascade_flip": self._detect_cascade_flip,
            "funding_exhaustion_trap": self._detect_funding_exhaustion_trap,
            "meme_mania_rotation": self._detect_meme_mania_rotation,
            "session_gap_exploit": self._detect_session_gap_exploit,
            "dead_cat_echo": self._detect_dead_cat_echo,
            "liquidity_vacuum_breakout": self._detect_liquidity_vacuum_breakout,
        }
        
        strategy_config = {
            "leveraged_short_squeeze": ("Leveraged Short Squeeze", "做空", 0.02, 0.015, 1),
            "micro_range_ripples": ("Micro Range Ripples", "做多", 0.008, 0.012, 1),
            "cascade_flip": ("Cascade Flip", "做多", 0.015, 0.03, 2),
            "funding_exhaustion_trap": ("Funding Exhaustion Trap", "做空", 0.02, 0.025, 2),
            "meme_mania_rotation": ("Meme Mania Rotation", "做多", 0.025, 0.05, 4),
            "session_gap_exploit": ("Session Gap Exploit", "做多", 0.01, 0.015, 1),
            "dead_cat_echo": ("Dead Cat Echo", "做空", 0.02, 0.03, 2),
            "liquidity_vacuum_breakout": ("Liquidity Vacuum Breakout", "做多", 0.012, 0.02, 1),
        }
        
        for key, detector in strategies.items():
            name, direction, sl, tp, max_hold = strategy_config[key]
            trades = self._run_single_strategy(key, detector, direction, sl, tp, max_hold)
            self.results[key] = self._compile_result(name, "创新策略", direction, trades)
    
    def _run_single_strategy(self, strategy_key, detector, direction, sl, tp, max_hold_hours):
        df = self.df_5m
        trades = []
        position = None
        
        for i in range(288, len(df)):
            row = df.iloc[i]
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= max_hold_hours:
                    close_reason = "time_exit"
                elif position["type"] == "long" and row["low"] <= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif position["type"] == "long" and row["high"] >= position["take_profit_price"]:
                    close_reason = "take_profit"
                elif position["type"] == "short" and row["high"] >= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif position["type"] == "short" and row["low"] <= position["take_profit_price"]:
                    close_reason = "take_profit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"],
                                   "close_reason": close_reason, **pnl})
                    position = None
            
            if not position:
                if detector(row, i):
                    pos_type = "long" if direction == "做多" else "short"
                    position = self._open_position(row, pos_type, strategy_key, sl, tp)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"],
                           "close_reason": "end_of_data", **pnl})
        
        return trades
    
    def _detect_leveraged_short_squeeze(self, row, i):
        score = 0
        fz = row.get("funding_zscore", 0)
        if not pd.isna(fz) and fz > 1.5: score += 3
        elif not pd.isna(fz) and fz > 1.0: score += 1
        
        funding = row.get("funding_rate", 0)
        if not pd.isna(funding) and funding > 0.0003: score += 2
        elif not pd.isna(funding) and funding > 0.0002: score += 1
        
        ret_1h = row.get("return_1h", 0)
        if ret_1h > 0.01: score += 2
        elif ret_1h > 0.005: score += 1
        
        vr = row.get("volume_ratio", 1)
        if vr > 2.5: score += 2
        elif vr > 1.5: score += 1
        
        if row.get("volume_spike", False): score += 1
        if row.get("spread_widening", False): score += 1
        
        return score >= 5
    
    def _detect_micro_range_ripples(self, row, i):
        return (
            row.get("bb_width", 0.02) < 0.015 and
            row.get("breakout_strength_24h_calc", 0) > 0.003 and
            row.get("volume_ratio", 1) > 1.2
        )
    
    def _detect_cascade_flip(self, row, i):
        return (
            row.get("volume_ratio", 1) > 3.0 and
            row.get("return_1h", 0) < -0.02 and
            row.get("funding_rate", 0) > 0.0002
        )
    
    def _detect_funding_exhaustion_trap(self, row, i):
        return (
            row.get("funding_zscore", 0) > 2.5 and
            row.get("funding_delta", 0) < 0 and
            row.get("return_1h", 0) < 0.005
        )
    
    def _detect_meme_mania_rotation(self, row, i):
        return (
            row.get("volume_spike", False) and
            (row.get("spike_up", False) or row.get("return_1h", 0) > 0.02) and
            row.get("intrabar_volatility", 0) > 0.02
        )
    
    def _detect_session_gap_exploit(self, row, i):
        return (
            row.get("session_open", False) and
            row.get("low_liquidity", False) and
            row.get("intrabar_volatility", 0) > 0.015
        )
    
    def _detect_dead_cat_echo(self, row, i):
        if i < 48:
            return False
        df = self.df_5m
        price_4h_ago = df.iloc[i - 48]["close"]
        price_1h_ago = df.iloc[i - 12]["close"]
        
        drop_4h = (price_4h_ago - row["close"]) / price_4h_ago
        bounce_1h = (row["close"] - price_1h_ago) / price_1h_ago
        
        return (
            drop_4h > 0.03 and
            0.005 < bounce_1h < 0.015 and
            row.get("trend_exhaustion", 0) > 0 and
            row.get("volume_ratio", 1) < 1.0
        )
    
    def _detect_liquidity_vacuum_breakout(self, row, i):
        return (
            row.get("low_liquidity", False) and
            row.get("spread_widening", False) and
            row.get("breakout_strength_24h_calc", 0) > 0.002 and
            row.get("volume_ratio", 1) > 1.0
        )
    
    def _run_behavioral_playbooks(self):
        logger.info("Running Behavioral Playbooks...")
        
        playbooks = {
            "panic_reversal": ("Panic Reversal", "做多"),
            "fake_breakout": ("Fake Breakout", "做空"),
            "oi_flush": ("OI Flush", "做多"),
            "weekend_manipulation": ("Weekend Manipulation", "双向"),
            "short_squeeze": ("Short Squeeze", "做多"),
            "liquidation_cascade": ("Liquidation Cascade", "做多"),
            "volume_climax": ("Volume Climax", "做空"),
        }
        
        detectors = {
            "panic_reversal": self._detect_panic_reversal,
            "fake_breakout": self._detect_fake_breakout,
            "oi_flush": self._detect_oi_flush,
            "weekend_manipulation": self._detect_weekend_manipulation,
            "short_squeeze": self._detect_short_squeeze,
            "liquidation_cascade": self._detect_liquidation_cascade,
            "volume_climax": self._detect_volume_climax,
        }
        
        for key, (name, direction) in playbooks.items():
            trades = self._run_single_strategy(key, detectors[key], direction, 0.015, 0.025, 2)
            self.results[key] = self._compile_result(name, "Behavioral Playbook", direction, trades)
    
    def _detect_panic_reversal(self, row, i):
        return (
            row.get("return_1h", 0) < -0.015 and
            row.get("volume_ratio", 1) > 1.3
        )
    
    def _detect_fake_breakout(self, row, i):
        if i < 24 or i >= len(self.df_5m) - 5:
            return False
        df = self.df_5m
        rolling_high = df.iloc[i-24:i]["high"].max()
        breakout = row["high"] > rolling_high * 1.005
        future_low = df.iloc[i+1:i+6]["low"].min()
        is_fake = future_low < rolling_high
        return breakout and is_fake
    
    def _detect_oi_flush(self, row, i):
        return (
            row.get("funding_rate", 0) > 0.0002 and
            row.get("volume_ratio", 1) > 1.5 and
            abs(row.get("return_5m", 0)) > 0.01 and
            row.get("regime", "") == "volatile"
        )
    
    def _detect_weekend_manipulation(self, row, i):
        return (
            row.get("is_weekend", False) and
            row.get("volume_ratio", 1) < 0.9 and
            abs(row.get("return_5m", 0)) > 0.005
        )
    
    def _detect_short_squeeze(self, row, i):
        return (
            row.get("funding_rate", 0) > 0.0003 and
            row.get("return_5m", 0) > 0.01 and
            row.get("volume_ratio", 1) > 1.5
        )
    
    def _detect_liquidation_cascade(self, row, i):
        return (
            row.get("volume_ratio", 1) > 3.0 and
            row.get("return_5m", 0) < -0.02
        )
    
    def _detect_volume_climax(self, row, i):
        return (
            row.get("volume_ratio", 1) > 1.8 and
            abs(row.get("return_5m", 0)) > 0.015
        )
    
    def _run_short_strategies(self):
        logger.info("Running Short Strategies...")
        
        strategies = {
            "volume_climax_fade_v2": ("Volume Climax Fade V2", "做空"),
            "weak_bounce_short_v2": ("Weak Bounce Short V2", "做空"),
            "fake_breakout_trap_v2": ("Fake Breakout Trap V2", "做空"),
            "weekend_liquidity_trap_v2": ("Weekend Liquidity Trap V2", "双向"),
            "short_squeeze_hunt_v2": ("Short Squeeze Hunt V2", "做多"),
            "funding_reset_v2": ("Funding Reset V2", "做空"),
        }
        
        detectors = {
            "volume_climax_fade_v2": self._detect_volume_climax_fade_v2,
            "weak_bounce_short_v2": self._detect_weak_bounce_short_v2,
            "fake_breakout_trap_v2": self._detect_fake_breakout_trap_v2,
            "weekend_liquidity_trap_v2": self._detect_weekend_liquidity_trap_v2,
            "short_squeeze_hunt_v2": self._detect_short_squeeze_hunt_v2,
            "funding_reset_v2": self._detect_funding_reset_v2,
        }
        
        for key, (name, direction) in strategies.items():
            trades = self._run_single_strategy(key, detectors[key], direction, 0.015, 0.02, 2)
            self.results[key] = self._compile_result(name, "优化做空策略", direction, trades)
    
    def _detect_volume_climax_fade_v2(self, row, i):
        return (
            row.get("volume_ratio", 0) >= 2.0 and
            row.get("wick_ratio", 0) >= 0.3 and
            abs(row.get("return_5m", 0)) >= 0.003 and
            row.get("return_5m", 0) > 0
        )
    
    def _detect_weak_bounce_short_v2(self, row, i):
        if i < 60:
            return False
        df = self.df_5m
        close_4h_ago = df.iloc[i - 48]["close"]
        close_1h_ago = df.iloc[i - 12]["close"]
        
        drop_4h_pct = (close_4h_ago - close_1h_ago) / close_4h_ago
        bounce_pct = (row["close"] - close_1h_ago) / close_1h_ago
        
        return (
            drop_4h_pct >= 0.02 and
            0.003 <= bounce_pct <= 0.015 and
            row.get("volume_ratio", 0) >= 1.5
        )
    
    def _detect_fake_breakout_trap_v2(self, row, i):
        if i < 24:
            return False
        df = self.df_5m
        rolling_high = df.iloc[i-24:i]["high"].max()
        breakout = row.get("high", 0) > rolling_high * 1.005
        volume_ok = row.get("volume_ratio", 1) <= 1.2
        price_rejected = row.get("close", 0) < row.get("high", 0) * 0.998
        return breakout and volume_ok and price_rejected
    
    def _detect_weekend_liquidity_trap_v2(self, row, i):
        is_weekend_or_early = row.get("is_weekend", False) or row.get("hour", 0) in [0, 1, 2, 3, 4, 5, 6, 7]
        low_volume = row.get("volume_ratio", 1) <= 0.5
        price_spike = abs(row.get("return_5m", 0)) >= 0.003
        return is_weekend_or_early and low_volume and price_spike
    
    def _detect_short_squeeze_hunt_v2(self, row, i):
        return (
            row.get("funding_rate", 0) <= -0.00005 and
            row.get("return_1h", 0) >= 0.008
        )
    
    def _detect_funding_reset_v2(self, row, i):
        return (
            row.get("funding_rate", 0) >= 0.0003 and
            row.get("funding_delta", 0) <= -0.00005
        )
    
    def _open_position(self, row, pos_type, strategy, sl_pct, tp_pct):
        leverage = self.config.leverage
        margin = self.config.initial_capital * self.config.position_size
        
        if pos_type == "long":
            sl_price = row["close"] * (1 - sl_pct)
            tp_price = row["close"] * (1 + tp_pct)
        else:
            sl_price = row["close"] * (1 + sl_pct)
            tp_price = row["close"] * (1 - tp_pct)
        
        return {
            "type": pos_type,
            "entry_price": row["close"],
            "entry_time": row["timestamp"],
            "strategy": strategy,
            "margin": margin,
            "leverage": leverage,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
        }
    
    def _calculate_pnl(self, position, exit_price, close_reason):
        entry_price = position["entry_price"]
        margin = position["margin"]
        leverage = position["leverage"]
        
        if position["type"] == "long":
            price_pnl_pct = (exit_price - entry_price) / entry_price
        else:
            price_pnl_pct = (entry_price - exit_price) / entry_price
        
        pnl = margin * price_pnl_pct * leverage
        pnl -= margin * (self.config.commission + self.config.slippage)
        pnl_pct = pnl / margin if margin > 0 else 0
        
        return {"pnl": pnl, "pnl_pct": pnl_pct}
    
    def _compile_result(self, name, category, direction, trades):
        if not trades:
            return StrategyResult(name=name, category=category, direction=direction)
        
        total_return = sum(t.get("pnl", 0) for t in trades)
        total_return_pct = total_return / self.config.initial_capital
        
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]
        
        win_rate = len(wins) / len(trades) if trades else 0
        avg_return = np.mean([t.get("pnl_pct", 0) for t in trades]) if trades else 0
        
        total_wins = sum(t.get("pnl", 0) for t in wins)
        total_losses = abs(sum(t.get("pnl", 0) for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        returns = [t.get("pnl_pct", 0) for t in trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        equity = self.config.initial_capital
        peak = equity
        max_dd = 0
        for t in trades:
            equity += t.get("pnl", 0)
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = max_dd / peak if peak > 0 else 0
        
        avg_hold = np.mean([(t["exit_time"] - t["entry_time"]).total_seconds() / 3600 for t in trades]) if trades else 0
        
        return StrategyResult(
            name=name,
            category=category,
            direction=direction,
            total_trades=len(trades),
            win_rate=win_rate,
            total_return=total_return,
            total_return_pct=total_return_pct,
            avg_return=avg_return,
            max_drawdown=max_dd_pct,
            profit_factor=profit_factor,
            sharpe=sharpe,
            avg_hold_hours=avg_hold,
            trades=trades
        )
    
    def print_report(self):
        print("\n" + "=" * 120)
        print("📊 综合策略回测报告 - 全部数据 (2024-2026)")
        print("=" * 120)
        print(f"数据范围: {self.df_5m['timestamp'].min()} ~ {self.df_5m['timestamp'].max()}")
        print(f"初始资金: ${self.config.initial_capital:,.0f} | 杠杆: {self.config.leverage}x")
        print()
        
        categories = ["经典技术", "创新策略", "Behavioral Playbook", "优化做空策略"]
        
        for cat in categories:
            cat_results = [(k, v) for k, v in self.results.items() if v.category == cat]
            if not cat_results:
                continue
            
            print(f"\n{'=' * 120}")
            print(f"📁 {cat}")
            print("=" * 120)
            print(f"{'策略名称':<30} | {'方向':<6} | {'交易数':>6} | {'胜率':>8} | {'总收益':>12} | {'收益率':>10} | {'最大回撤':>10} | {'盈亏比':>8} | {'夏普':>8}")
            print("-" * 120)
            
            for key, r in sorted(cat_results, key=lambda x: -x[1].total_return):
                print(f"{r.name:<30} | {r.direction:<6} | {r.total_trades:>6} | "
                      f"{r.win_rate*100:>7.1f}% | ${r.total_return:>10,.2f} | "
                      f"{r.total_return_pct*100:>+8.2f}% | {r.max_drawdown*100:>9.2f}% | "
                      f"{r.profit_factor:>8.2f} | {r.sharpe:>8.2f}")
        
        print("\n" + "=" * 120)
        print("🏆 TOP 10 策略 (按总收益排序)")
        print("=" * 120)
        
        sorted_results = sorted(self.results.items(), key=lambda x: -x[1].total_return)
        for i, (key, r) in enumerate(sorted_results[:10], 1):
            print(f"{i:>2}. {r.name:<30} | {r.category:<20} | {r.direction:<4} | "
                  f"交易: {r.total_trades:>4} | 胜率: {r.win_rate*100:>5.1f}% | "
                  f"收益: ${r.total_return:>10,.2f} ({r.total_return_pct*100:>+7.2f}%)")
        
        print("\n" + "=" * 120)
        print("📈 策略分类汇总")
        print("=" * 120)
        
        for cat in categories:
            cat_results = [v for v in self.results.values() if v.category == cat]
            if not cat_results:
                continue
            
            total_trades = sum(r.total_trades for r in cat_results)
            total_return = sum(r.total_return for r in cat_results)
            avg_win_rate = np.mean([r.win_rate for r in cat_results if r.total_trades > 0]) if any(r.total_trades > 0 for r in cat_results) else 0
            
            print(f"{cat:<25} | 总交易: {total_trades:>6} | 平均胜率: {avg_win_rate*100:>5.1f}% | 总收益: ${total_return:>12,.2f}")
    
    def save_results(self):
        output_dir = get_research_path()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_data = {
            "backtest_info": {
                "timestamp": datetime.now().isoformat(),
                "data_range": f"{self.df_5m['timestamp'].min()} ~ {self.df_5m['timestamp'].max()}",
                "initial_capital": self.config.initial_capital,
                "leverage": self.config.leverage,
                "total_strategies": len(self.results),
            },
            "results": {
                key: {
                    "name": r.name,
                    "category": r.category,
                    "direction": r.direction,
                    "total_trades": r.total_trades,
                    "win_rate": r.win_rate,
                    "total_return": r.total_return,
                    "total_return_pct": r.total_return_pct,
                    "avg_return": r.avg_return,
                    "max_drawdown": r.max_drawdown,
                    "profit_factor": r.profit_factor,
                    "sharpe": r.sharpe,
                    "avg_hold_hours": r.avg_hold_hours,
                }
                for key, r in self.results.items()
            }
        }
        
        output_path = output_dir / "comprehensive_backtest_results_5years.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 结果已保存: {output_path}")


def main():
    print("🚀 综合策略回测 - 全部可用数据 (2024-2026)")
    print()
    
    config = BacktestConfig(
        initial_capital=10000,
        leverage=50,
        stop_loss_capital_pct=0.10,
        take_profit_capital_pct=0.60,
    )
    
    tester = ComprehensiveBacktester(config)
    
    df = tester.load_data(months=60)  # 尝试加载5年，实际加载全部可用数据
    
    if df.empty:
        print("❌ 无法加载数据，退出")
        return
    
    tester.prepare_5m_data()
    
    tester.run_all_strategies()
    
    tester.print_report()
    
    tester.save_results()
    
    print("\n✅ 回测完成！")


if __name__ == "__main__":
    main()
