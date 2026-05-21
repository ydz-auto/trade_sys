#!/usr/bin/env python3
"""
完整版策略回测 - 所有策略 + 上下文过滤

测试策略清单:
1. BTC Swing 基础策略 (1个)
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
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from infrastructure.data_lake import get_features_path, get_research_path

logger = get_logger("full_backtest")


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.3
    leverage: float = 50.0


@dataclass
class StrategyResult:
    name: str
    category: str
    direction: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    avg_hold_hours: float = 0.0
    trades: List[Dict] = field(default_factory=list)


class FullBacktester:
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.df: pd.DataFrame = None
        self.df_5m: pd.DataFrame = None
        self.results: Dict[str, StrategyResult] = {}
    
    def load_data(self, months: int = None) -> pd.DataFrame:
        data_path = get_features_path("binance", "BTCUSDT") / "features_with_structure.parquet"
        try:
            df = pd.read_parquet(data_path)
        except Exception as e:
            logger.error(f"Cannot load parquet file: {e}")
            return pd.DataFrame()
        
        if months:
            cutoff = datetime.now() - timedelta(days=months * 30)
            df = df[df["timestamp"] >= pd.Timestamp(cutoff)].copy()
            logger.info(f"Filtered to last {months} months")
        
        logger.info(f"Loaded {len(df)} rows, date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        self.df = df
        return df
    
    def prepare_5m_data(self):
        if self.df is None or self.df.empty:
            return
        
        logger.info("Resampling data to 5m...")
        
        agg_dict = {
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
            "funding_rate": "last", "funding_zscore": "last", "funding_delta": "last",
            "bb_upper": "last", "bb_lower": "last", "bb_middle": "last", "bb_position": "last",
            "rsi_14": "last", "regime": "last", "regime_code": "last",
            "spike_up": "max", "spike_down": "max", "major_spike_up": "max", "major_spike_down": "max",
            "trend_exhaustion": "last", "trend_healthy": "last", "momentum_shift": "last", "volatility_surge": "last",
            "state_squeeze": "max", "state_panic_dump": "max", "state_breakout": "max", "state_accumulation": "max",
            "breakout_high_24h": "max", "breakout_low_24h": "max", "breakout_strength_24h": "max",
            "trend_direction_12h": "last", "trend_strength_12h": "last",
            "volatility_1h": "last", "oi_change_1h": "last",
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
        
        def get_session(hour):
            if 0 <= hour < 8: return "asia"
            elif 8 <= hour < 16: return "europe"
            else: return "us"
        df["session"] = df["hour"].apply(get_session)
        df["session_open"] = df["hour"].isin([0, 8, 16])
        
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(288).mean().fillna(1)
        df["low_liquidity"] = df["volume_ratio"] < 0.7
        df["volume_spike"] = df["volume_ratio"] > 2.5
        
        df["high_funding"] = df["funding_rate"] > 0.0001
        df["low_funding"] = df["funding_rate"] < -0.0001
        
        df["return_5m"] = df["close"].pct_change(1)
        df["return_15m"] = df["close"].pct_change(3)
        df["return_1h"] = df["close"].pct_change(12)
        df["return_4h"] = df["close"].pct_change(48)
        
        if "bb_upper" in df.columns and "bb_lower" in df.columns:
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["bb_middle"] + 0.0001)
        
        df["intrabar_volatility"] = (df["high"] - df["low"]) / (df["close"] + 0.0001)
        df["spread_widening"] = df["intrabar_volatility"] / (df["volume_ratio"] + 0.01) > 0.03
        
        rolling_highs = df["high"].rolling(288, min_periods=1).max()
        df["breakout_strength_24h_calc"] = (df["high"] - rolling_highs) / (rolling_highs + 0.0001)
        
        self.df_5m = df.fillna(0)
    
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
    
    def _calculate_pnl(self, position, exit_price):
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
        
        total_wins = sum(t.get("pnl", 0) for t in wins)
        total_losses = abs(sum(t.get("pnl", 0) for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        returns = [t.get("pnl_pct", 0) for t in trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if (np.std(returns) > 0 and len(returns) > 1) else 0
        
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
            name=name, category=category, direction=direction,
            total_trades=len(trades), win_rate=win_rate,
            total_return=total_return, total_return_pct=total_return_pct,
            max_drawdown=max_dd_pct, profit_factor=profit_factor,
            sharpe=sharpe, avg_hold_hours=avg_hold, trades=trades
        )
    
    def _run_strategy(self, name: str, category: str, direction: str, 
                      detector: Callable, sl_pct: float, tp_pct: float, max_hold_hours: int):
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
                    pnl = self._calculate_pnl(position, row["close"])
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"], **pnl})
                    position = None
            
            if not position:
                signal = detector(row, i)
                if signal:
                    pos_type = "long" if direction in ["做多", "双向"] else "short"
                    if direction == "双向" and signal == "short":
                        pos_type = "short"
                    position = self._open_position(row, pos_type, name, sl_pct, tp_pct)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"])
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], **pnl})
        
        return self._compile_result(name, category, direction, trades)

    # ==================== 一、BTC Swing 基础策略 ====================
    def _run_btc_swing(self):
        df = self.df_5m
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        
        trades = []
        position = None
        
        for i in range(50, len(df)):
            row = df.iloc[i]
            rsi = row.get("rsi_14", 50)
            if pd.isna(rsi): rsi = 50
            
            ema_cross_up = row["ema_20"] > row["ema_50"]
            prev_ema_cross_up = df.iloc[i-1]["ema_20"] > df.iloc[i-1]["ema_50"]
            golden_cross = ema_cross_up and not prev_ema_cross_up
            
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
                    pnl = self._calculate_pnl(position, row["close"])
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"], **pnl})
                    position = None
            
            if not position:
                # 上下文过滤: volatile regime + 非squeeze状态
                if rsi <= 30 and golden_cross:
                    if row.get("regime", "") == "volatile" and row.get("state_squeeze", 0) == 0:
                        position = self._open_position(row, "long", "btc_swing", 0.03, 0.05)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"])
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], **pnl})
        
        self.results["btc_swing"] = self._compile_result("BTC Swing", "经典技术", "双向", trades)

    # ==================== 二、经典技术指标策略 ====================
    def _run_bollinger_bands(self):
        def detector(row, i):
            bb_upper = row.get("bb_upper", 0)
            bb_lower = row.get("bb_lower", 0)
            if bb_upper == 0 or bb_lower == 0:
                return None
            
            # 上下文过滤: ranging regime 效果更好
            if row.get("regime", "") == "ranging":
                if row["close"] < bb_lower:
                    return "long"
                elif row["close"] > bb_upper:
                    return "short"
            return None
        
        self.results["bollinger_bands"] = self._run_strategy(
            "Bollinger Bands", "经典技术", "双向", detector, 0.02, 0.03, 48
        )
    
    def _run_ma_cross(self):
        df = self.df_5m
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
                    pnl = self._calculate_pnl(position, row["close"])
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"], **pnl})
                    position = None
            
            if not position:
                golden_cross = prev_row["ma_50"] <= prev_row["ma_200"] and row["ma_50"] > row["ma_200"]
                death_cross = prev_row["ma_50"] >= prev_row["ma_200"] and row["ma_50"] < row["ma_200"]
                
                # 上下文过滤: volatile regime 下趋势更可靠
                if row.get("regime", "") == "volatile":
                    if golden_cross:
                        position = self._open_position(row, "long", "ma_cross", 0.03, 0.05)
                    elif death_cross:
                        position = self._open_position(row, "short", "ma_cross", 0.03, 0.05)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"])
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], **pnl})
        
        self.results["ma_cross"] = self._compile_result("MA Cross (50/200)", "经典技术", "双向", trades)
    
    def _run_rsi_macd(self):
        df = self.df_5m
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
            if pd.isna(rsi): rsi = 50
            
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
                    pnl = self._calculate_pnl(position, row["close"])
                    trades.append({**position, "exit_price": row["close"], "exit_time": row["timestamp"], **pnl})
                    position = None
            
            if not position:
                macd_cross_up = prev_row["macd"] <= prev_row["macd_signal"] and row["macd"] > row["macd_signal"]
                macd_cross_down = prev_row["macd"] >= prev_row["macd_signal"] and row["macd"] < row["macd_signal"]
                
                # 上下文过滤
                if rsi <= 30 and macd_cross_up and row.get("regime", "") == "volatile":
                    position = self._open_position(row, "long", "rsi_macd", 0.02, 0.03)
                elif rsi >= 70 and macd_cross_down and row.get("regime", "") == "volatile":
                    position = self._open_position(row, "short", "rsi_macd", 0.02, 0.03)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"])
            trades.append({**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], **pnl})
        
        self.results["rsi_macd"] = self._compile_result("RSI+MACD", "经典技术", "双向", trades)

    # ==================== 三、创新策略研究矩阵 (8个) ====================
    def _run_leveraged_short_squeeze(self):
        def detector(row, i):
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
            
            # 上下文过滤
            if row.get("state_squeeze", 0) > 0: score += 2
            if row.get("high_funding", False) and row.get("regime", "") == "volatile": pass
            if row.get("low_liquidity", False) and row.get("is_weekend", False): return False
            
            return score >= 5
        
        self.results["leveraged_short_squeeze"] = self._run_strategy(
            "Leveraged Short Squeeze", "创新策略", "做空", detector, 0.02, 0.015, 1
        )
    
    def _run_micro_range_ripples(self):
        def detector(row, i):
            return (
                row.get("bb_width", 0.02) < 0.015 and
                row.get("breakout_strength_24h_calc", 0) > 0.003 and
                row.get("volume_ratio", 1) > 1.2 and
                row.get("regime", "") == "ranging"
            )
        
        self.results["micro_range_ripples"] = self._run_strategy(
            "Micro Range Ripples", "创新策略", "做多", detector, 0.008, 0.012, 1
        )
    
    def _run_cascade_flip(self):
        def detector(row, i):
            return (
                row.get("volume_ratio", 1) > 3.0 and
                row.get("return_1h", 0) < -0.02 and
                row.get("funding_rate", 0) > 0.0002 and
                row.get("state_panic_dump", 0) > 0
            )
        
        self.results["cascade_flip"] = self._run_strategy(
            "Cascade Flip", "创新策略", "做多", detector, 0.015, 0.03, 2
        )
    
    def _run_funding_exhaustion_trap(self):
        def detector(row, i):
            return (
                row.get("funding_zscore", 0) > 2.5 and
                row.get("funding_delta", 0) < 0 and
                row.get("return_1h", 0) < 0.005 and
                row.get("high_funding", False)
            )
        
        self.results["funding_exhaustion_trap"] = self._run_strategy(
            "Funding Exhaustion Trap", "创新策略", "做空", detector, 0.02, 0.025, 2
        )
    
    def _run_meme_mania_rotation(self):
        def detector(row, i):
            return (
                row.get("volume_spike", False) and
                (row.get("spike_up", False) or row.get("return_1h", 0) > 0.02) and
                row.get("intrabar_volatility", 0) > 0.02 and
                row.get("regime", "") == "volatile"
            )
        
        self.results["meme_mania_rotation"] = self._run_strategy(
            "Meme Mania Rotation", "创新策略", "做多", detector, 0.025, 0.05, 4
        )
    
    def _run_session_gap_exploit(self):
        def detector(row, i):
            return (
                row.get("session_open", False) and
                row.get("low_liquidity", False) and
                row.get("intrabar_volatility", 0) > 0.015 and
                row.get("session", "") in ["europe", "us"]
            )
        
        self.results["session_gap_exploit"] = self._run_strategy(
            "Session Gap Exploit", "创新策略", "做多", detector, 0.01, 0.015, 1
        )
    
    def _run_dead_cat_echo(self):
        def detector(row, i):
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
                row.get("volume_ratio", 1) < 1.0 and
                row.get("regime", "") == "ranging"
            )
        
        self.results["dead_cat_echo"] = self._run_strategy(
            "Dead Cat Echo", "创新策略", "做空", detector, 0.02, 0.03, 2
        )
    
    def _run_liquidity_vacuum_breakout(self):
        def detector(row, i):
            return (
                row.get("low_liquidity", False) and
                row.get("spread_widening", False) and
                row.get("breakout_strength_24h_calc", 0) > 0.002 and
                row.get("volume_ratio", 1) > 1.0 and
                row.get("session", "") == "us"
            )
        
        self.results["liquidity_vacuum_breakout"] = self._run_strategy(
            "Liquidity Vacuum Breakout", "创新策略", "做多", detector, 0.012, 0.02, 1
        )

    # ==================== 四、Crypto Behavioral Playbooks (7个) ====================
    def _run_panic_reversal(self):
        def detector(row, i):
            if row.get("return_1h", 0) < -0.015 and row.get("volume_ratio", 0) > 1.3:
                # 上下文过滤
                if row.get("state_panic_dump", 0) > 0:
                    return True
                if row.get("is_weekend", False):
                    return True
                if row.get("session", "") == "asia":
                    return True
            return False
        
        self.results["panic_reversal"] = self._run_strategy(
            "Panic Reversal", "Behavioral Playbook", "做多", detector, 0.04, 0.07, 48
        )
    
    def _run_fake_breakout(self):
        def detector(row, i):
            if i < 24:
                return False
            df = self.df_5m
            rolling_high = df.iloc[i-24:i]["high"].max()
            if row["high"] > rolling_high * 1.003:
                # 上下文过滤
                if row.get("high_funding", False):
                    return "short"
                if row.get("session", "") in ["europe", "us"]:
                    return "short"
                if row.get("regime", "") == "ranging":
                    return "short"
                if row.get("volume_ratio", 1) < 1.5:
                    return "short"
            return None
        
        self.results["fake_breakout"] = self._run_strategy(
            "Fake Breakout", "Behavioral Playbook", "做空", detector, 0.02, 0.03, 6
        )
    
    def _run_oi_flush(self):
        def detector(row, i):
            return (
                row.get("funding_rate", 0) > 0.0002 and
                row.get("volume_ratio", 1) > 1.5 and
                abs(row.get("return_5m", 0)) > 0.01 and
                row.get("regime", "") == "volatile"
            )
        
        self.results["oi_flush"] = self._run_strategy(
            "OI Flush", "Behavioral Playbook", "做多", detector, 0.02, 0.03, 2
        )
    
    def _run_weekend_manipulation(self):
        def detector(row, i):
            return (
                row.get("is_weekend", False) and
                row.get("volume_ratio", 1) < 0.9 and
                abs(row.get("return_5m", 0)) > 0.005 and
                row.get("low_liquidity", False)
            )
        
        self.results["weekend_manipulation"] = self._run_strategy(
            "Weekend Manipulation", "Behavioral Playbook", "双向", detector, 0.015, 0.025, 2
        )
    
    def _run_short_squeeze(self):
        def detector(row, i):
            return (
                row.get("funding_rate", 0) > 0.0003 and
                row.get("return_5m", 0) > 0.01 and
                row.get("volume_ratio", 1) > 1.5 and
                row.get("state_squeeze", 0) > 0
            )
        
        self.results["short_squeeze"] = self._run_strategy(
            "Short Squeeze", "Behavioral Playbook", "做多", detector, 0.02, 0.03, 2
        )
    
    def _run_liquidation_cascade(self):
        def detector(row, i):
            return (
                row.get("volume_ratio", 1) > 3.0 and
                row.get("return_5m", 0) < -0.02 and
                row.get("regime", "") == "volatile"
            )
        
        self.results["liquidation_cascade"] = self._run_strategy(
            "Liquidation Cascade", "Behavioral Playbook", "做多", detector, 0.03, 0.05, 6
        )
    
    def _run_volume_climax(self):
        def detector(row, i):
            return (
                row.get("volume_ratio", 1) > 1.8 and
                abs(row.get("return_5m", 0)) > 0.015 and
                row.get("regime", "") == "volatile"
            )
        
        self.results["volume_climax"] = self._run_strategy(
            "Volume Climax", "Behavioral Playbook", "做空", detector, 0.015, 0.025, 2
        )

    # ==================== 五、优化做空策略 (6个) ====================
    def _run_volume_climax_fade_v2(self):
        def detector(row, i):
            return (
                row.get("volume_ratio", 0) >= 2.0 and
                row.get("wick_ratio", 0) >= 0.3 and
                abs(row.get("return_5m", 0)) >= 0.003 and
                row.get("return_5m", 0) > 0 and
                row.get("regime", "") == "volatile"
            )
        
        # 需要添加wick_ratio
        df = self.df_5m
        df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.0001)
        
        self.results["volume_climax_fade_v2"] = self._run_strategy(
            "Volume Climax Fade V2", "优化做空策略", "做空", detector, 0.015, 0.02, 2
        )
    
    def _run_weak_bounce_short_v2(self):
        def detector(row, i):
            if i < 60:
                return False
            df = self.df_5m
            close_4h_ago = df.iloc[i-48]["close"]
            close_1h_ago = df.iloc[i-12]["close"]
            
            drop_4h_pct = (close_4h_ago - close_1h_ago) / close_4h_ago
            bounce_pct = (row["close"] - close_1h_ago) / close_1h_ago
            
            if drop_4h_pct >= 0.02 and 0.003 <= bounce_pct <= 0.015 and row.get("volume_ratio", 0) >= 1.5:
                # 上下文过滤
                if row.get("high_funding", False):
                    return True
                if row.get("regime", "") == "volatile":
                    return True
                if row.get("session", "") == "europe":
                    return True
            return False
        
        self.results["weak_bounce_short_v2"] = self._run_strategy(
            "Weak Bounce Short V2", "优化做空策略", "做空", detector, 0.018, 0.025, 4
        )
    
    def _run_fake_breakout_trap_v2(self):
        def detector(row, i):
            if i < 24:
                return False
            df = self.df_5m
            rolling_high = df.iloc[i-24:i]["high"].max()
            breakout = row.get("high", 0) > rolling_high * 1.005
            volume_ok = row.get("volume_ratio", 1) <= 1.2
            price_rejected = row.get("close", 0) < row.get("high", 0) * 0.998
            return breakout and volume_ok and price_rejected and row.get("regime", "") == "ranging"
        
        self.results["fake_breakout_trap_v2"] = self._run_strategy(
            "Fake Breakout Trap V2", "优化做空策略", "做空", detector, 0.02, 0.025, 2
        )
    
    def _run_weekend_liquidity_trap_v2(self):
        def detector(row, i):
            is_weekend_or_early = row.get("is_weekend", False) or row.get("hour", 0) in [0, 1, 2, 3, 4, 5, 6, 7]
            low_volume = row.get("volume_ratio", 1) <= 0.5
            price_spike = abs(row.get("return_5m", 0)) >= 0.003
            return is_weekend_or_early and low_volume and price_spike
        
        self.results["weekend_liquidity_trap_v2"] = self._run_strategy(
            "Weekend Liquidity Trap V2", "优化做空策略", "双向", detector, 0.015, 0.02, 2
        )
    
    def _run_short_squeeze_hunt_v2(self):
        def detector(row, i):
            return (
                row.get("funding_rate", 0) <= -0.00005 and
                row.get("return_1h", 0) >= 0.008 and
                row.get("state_squeeze", 0) > 0
            )
        
        self.results["short_squeeze_hunt_v2"] = self._run_strategy(
            "Short Squeeze Hunt V2", "优化做空策略", "做多", detector, 0.02, 0.03, 2
        )
    
    def _run_funding_reset_v2(self):
        def detector(row, i):
            return (
                row.get("funding_rate", 0) >= 0.0003 and
                row.get("funding_delta", 0) <= -0.00005 and
                row.get("high_funding", False)
            )
        
        self.results["funding_reset_v2"] = self._run_strategy(
            "Funding Reset V2", "优化做空策略", "做空", detector, 0.02, 0.025, 2
        )

    # ==================== 运行所有策略 ====================
    def run_all_strategies(self):
        logger.info("=" * 60)
        logger.info("开始运行所有策略回测...")
        logger.info("=" * 60)
        
        # 一、BTC Swing
        logger.info("1. BTC Swing 基础策略...")
        self._run_btc_swing()
        
        # 二、经典技术指标
        logger.info("2. 经典技术指标策略 (3个)...")
        self._run_bollinger_bands()
        self._run_ma_cross()
        self._run_rsi_macd()
        
        # 三、创新策略
        logger.info("3. 创新策略研究矩阵 (8个)...")
        self._run_leveraged_short_squeeze()
        self._run_micro_range_ripples()
        self._run_cascade_flip()
        self._run_funding_exhaustion_trap()
        self._run_meme_mania_rotation()
        self._run_session_gap_exploit()
        self._run_dead_cat_echo()
        self._run_liquidity_vacuum_breakout()
        
        # 四、Behavioral Playbooks
        logger.info("4. Crypto Behavioral Playbooks (7个)...")
        self._run_panic_reversal()
        self._run_fake_breakout()
        self._run_oi_flush()
        self._run_weekend_manipulation()
        self._run_short_squeeze()
        self._run_liquidation_cascade()
        self._run_volume_climax()
        
        # 五、优化做空策略
        logger.info("5. 优化做空策略 (6个)...")
        self._run_volume_climax_fade_v2()
        self._run_weak_bounce_short_v2()
        self._run_fake_breakout_trap_v2()
        self._run_weekend_liquidity_trap_v2()
        self._run_short_squeeze_hunt_v2()
        self._run_funding_reset_v2()
        
        logger.info("=" * 60)
        logger.info(f"完成！共测试 {len(self.results)} 个策略")
        logger.info("=" * 60)
    
    def print_report(self):
        print("\n" + "=" * 120)
        print("📊 完整策略回测报告 - 所有25个策略 + 上下文过滤")
        print("=" * 120)
        print(f"数据范围: {self.df_5m['timestamp'].min()} ~ {self.df_5m['timestamp'].max()}")
        print(f"初始资金: ${self.config.initial_capital:,.0f} | 杠杆: {self.config.leverage}x")
        
        categories = ["经典技术", "创新策略", "Behavioral Playbook", "优化做空策略"]
        
        for cat in categories:
            cat_results = [(k, v) for k, v in self.results.items() if v.category == cat]
            if not cat_results:
                continue
            
            print(f"\n{'=' * 120}")
            print(f"📁 {cat}")
            print("=" * 120)
            print(f"{'策略名称':<35} | {'方向':<6} | {'交易数':>6} | {'胜率':>8} | {'收益率':>12} | {'最大回撤':>10} | {'盈亏比':>8} | {'夏普':>8}")
            print("-" * 120)
            
            for key, r in sorted(cat_results, key=lambda x: -x[1].total_return):
                print(f"{r.name:<35} | {r.direction:<6} | {r.total_trades:>6} | "
                      f"{r.win_rate*100:>7.1f}% | {r.total_return_pct*100:>+11.2f}% | "
                      f"{r.max_drawdown*100:>9.2f}% | {r.profit_factor:>8.2f} | {r.sharpe:>8.2f}")
        
        print("\n" + "=" * 120)
        print("🏆 TOP 10 策略 (按总收益排序)")
        print("=" * 120)
        
        sorted_results = sorted(self.results.items(), key=lambda x: -x[1].total_return)
        for i, (key, r) in enumerate(sorted_results[:10], 1):
            if r.total_trades == 0:
                continue
            print(f"{i:>2}. {r.name:<35} | {r.category:<20} | {r.direction:<4} | "
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
    
    def save_results(self, filename: str = "full_backtest_results.json"):
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
                    "max_drawdown": r.max_drawdown,
                    "profit_factor": r.profit_factor,
                    "sharpe": r.sharpe,
                    "avg_hold_hours": r.avg_hold_hours,
                } for key, r in self.results.items()
            }
        }
        
        output_path = output_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 结果已保存: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=None, help="Number of months to backtest (default: all data)")
    args = parser.parse_args()
    
    if args.months:
        print(f"🚀 完整策略回测 - 近{args.months}个月数据 + 上下文过滤")
    else:
        print("🚀 完整策略回测 - 所有25个策略 + 上下文过滤")
    print()
    
    config = BacktestConfig(initial_capital=10000, leverage=50)
    
    tester = FullBacktester(config)
    
    df = tester.load_data(months=args.months)
    
    if df.empty:
        print("❌ 无法加载数据，退出")
        return
    
    tester.prepare_5m_data()
    
    tester.run_all_strategies()
    
    tester.print_report()
    
    filename = f"full_backtest_results_{args.months}months.json" if args.months else "full_backtest_results.json"
    tester.save_results(filename)
    
    print("\n✅ 回测完成！")


if __name__ == "__main__":
    main()
