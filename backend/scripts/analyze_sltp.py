#!/usr/bin/env python3
"""
止损止盈合理性分析
- 记录每笔止损/止盈平仓后的价格走势
- 分析止损后价格是否继续下跌（止损是否合理）
- 分析止盈后价格是否继续上涨（止盈是否过早）
"""

from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

import pandas as pd
import numpy as np


# ============================================================
# 数据结构 (复用回测引擎)
# ============================================================

class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    features: Dict = field(default_factory=dict)


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 1.0
    leverage: float = 50.0
    stop_loss_capital_pct: float = 0.10
    take_profit_min_capital_pct: float = 0.60
    take_profit_max_capital_pct: float = 10.0
    trailing_stop_drawdown_pct: float = 0.10
    max_hold_hours: int = 48


# ============================================================
# 止损止盈分析引擎
# ============================================================

class SLTPAnalyzer:
    """止损止盈合理性分析引擎"""

    # 平仓后跟踪的bar数量 (5分钟bar)
    # 12 = 1小时, 48 = 4小时, 288 = 24小时, 576 = 48小时
    TRACK_BARS = [6, 12, 24, 48, 96, 144, 288, 576]

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.bars: List[Bar] = []
        self.position: Optional[Dict] = None
        self.capital: float = 0.0
        # 分析数据
        self.sl_events: List[Dict] = []   # 止损事件
        self.tp_events: List[Dict] = []   # 止盈事件 (trailing_stop + max_take_profit)
        self.all_trades: List[Dict] = []

    def load_df(self, df: pd.DataFrame):
        self.bars = []
        for _, row in df.iterrows():
            bar = Bar(
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                features=row.to_dict(),
            )
            self.bars.append(bar)

    def prepare_features(self):
        n = len(self.bars)
        BARS_1H = 12
        BARS_24H = 288

        volumes = np.array([b.volume for b in self.bars])
        avg_volumes = np.full(n, volumes[0])
        for i in range(1, n):
            start = max(0, i - BARS_24H)
            avg_volumes[i] = np.mean(volumes[start:i + 1])

        highs = np.array([b.high for b in self.bars])
        rolling_highs = np.full(n, highs[0])
        for i in range(1, n):
            start = max(0, i - BARS_24H)
            rolling_highs[i] = np.max(highs[start:i])

        for i in range(n):
            bar = self.bars[i]
            f = bar.features

            if i >= BARS_1H:
                f["return_1h"] = (bar.close - self.bars[i - BARS_1H].close) / self.bars[i - BARS_1H].close
            else:
                f["return_1h"] = 0.0
            if i >= 1:
                f["return_5m"] = (bar.close - self.bars[i - 1].close) / self.bars[i - 1].close
            else:
                f["return_5m"] = 0.0

            f["intrabar_volatility"] = (bar.high - bar.low) / bar.close if bar.close > 0 else 0
            f["volume_ratio"] = bar.volume / avg_volumes[i] if avg_volumes[i] > 0 else 1.0
            f["hour"] = bar.timestamp.hour
            f["day_of_week"] = bar.timestamp.dayofweek
            f["is_weekend"] = bar.timestamp.dayofweek >= 5

            if 0 <= f["hour"] < 8:
                f["session"] = "asia"
            elif 8 <= f["hour"] < 16:
                f["session"] = "europe"
            else:
                f["session"] = "us"
            f["session_open"] = f["hour"] in [0, 8, 16]

            for key in ["funding_rate", "funding_zscore", "funding_delta", "trend_exhaustion"]:
                val = f.get(key, 0)
                if pd.isna(val):
                    val = 0
                f[key] = val

            f["breakout_strength_24h"] = (bar.high - rolling_highs[i]) / rolling_highs[i] if rolling_highs[i] > 0 else 0

            for key in ["spike_up", "spike_down"]:
                val = f.get(key, False)
                f[key] = bool(val) if not pd.isna(val) else False

            f["volume_spike"] = f["volume_ratio"] > 2.5
            f["low_liquidity"] = f["volume_ratio"] < 0.7
            f["spread_widening"] = f["intrabar_volatility"] / (f["volume_ratio"] + 0.01) > 0.03

            regime = f.get("regime", "ranging")
            if pd.isna(regime):
                regime = "ranging"
            f["regime"] = regime

            # RSI
            if "rsi_14" not in f or pd.isna(f.get("rsi_14")):
                if i >= 14:
                    prices = [b.close for b in self.bars[i-14:i+1]]
                    deltas = np.diff(prices)
                    gains = np.where(deltas > 0, deltas, 0)
                    losses = np.where(deltas < 0, -deltas, 0)
                    avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 1e-10
                    avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 1e-10
                    rs = avg_gain / avg_loss if avg_loss > 0 else 0
                    f["rsi_14"] = 100 - (100 / (1 + rs))
                else:
                    f["rsi_14"] = 50.0

            # MACD
            if "macd" not in f or pd.isna(f.get("macd")):
                if i >= 26:
                    prices = [b.close for b in self.bars[i-26:i+1]]
                    ema12 = np.mean(prices[-12:])
                    ema26 = np.mean(prices[-26:])
                    f["macd"] = ema12 - ema26
                    f["macd_signal"] = f["macd"] * 0.9
                else:
                    f["macd"] = 0.0
                    f["macd_signal"] = 0.0

    # ----------------------------------------------------------
    # 策略检测 (复用)
    # ----------------------------------------------------------

    def detect_rsi(self, bar, i):
        f = bar.features
        rsi = f.get("rsi_14", 50)
        if rsi < 30: return "rsi_14_long"
        elif rsi > 70: return "rsi_14_short"
        return None

    def detect_macd(self, bar, i):
        f = bar.features
        macd = f.get("macd", 0)
        macd_signal = f.get("macd_signal", 0)
        if macd > macd_signal and macd > 0: return "macd_12_26_9_long"
        elif macd < macd_signal and macd < 0: return "macd_12_26_9_short"
        return None

    def detect_panic_reversal(self, bar, i):
        f = bar.features
        if f.get("return_1h", 0) < -0.015 and f.get("volume_ratio", 1) > 1.5:
            return "panic_reversal"
        return None

    def detect_long_liquidation_bounce(self, bar, i):
        f = bar.features
        if f.get("return_1h", 0) < -0.02 and f.get("volume_ratio", 1) > 2.0:
            return "long_liquidation_bounce"
        return None

    def detect_volume_climax_fade(self, bar, i):
        f = bar.features
        if f.get("volume_ratio", 1) > 2.0 and f.get("intrabar_volatility", 0) > 0.025:
            wick = (bar.high - bar.close) / (bar.high - bar.low + 0.001)
            if wick > 0.3: return "volume_climax_fade"
        return None

    def detect_weak_bounce_short(self, bar, i):
        f = bar.features
        if i < 48: return None
        drop_4h = (self.bars[i-48].close - bar.close) / self.bars[i-48].close
        bounce_1h = (bar.close - self.bars[i-12].close) / self.bars[i-12].close if i >= 12 else 0
        if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015:
            return "weak_bounce_short"
        return None

    def detect_leveraged_short_squeeze(self, bar, i):
        f = bar.features
        if i < 288: return None
        score = 0
        fz = f.get("funding_zscore", 0)
        if not pd.isna(fz) and fz > 1.5: score += 3
        elif not pd.isna(fz) and fz > 1.0: score += 1
        funding = f.get("funding_rate", 0)
        if not pd.isna(funding) and funding > 0.0003: score += 2
        ret_1h = f.get("return_1h", 0)
        if ret_1h > 0.01: score += 2
        elif ret_1h > 0.005: score += 1
        vr = f.get("volume_ratio", 1)
        if vr > 2.5: score += 2
        elif vr > 1.5: score += 1
        if f.get("volume_spike", False): score += 1
        if f.get("spread_widening", False): score += 1
        wick = (bar.high - bar.close) / (bar.high - bar.low + 0.001)
        if wick > 0.6: score += 1
        return "leveraged_short_squeeze" if score >= 5 else None

    def detect_micro_range_ripples(self, bar, i):
        f = bar.features
        if i < 288: return None
        if f.get("bb_width", 0.02) < 0.015 and f.get("breakout_strength_24h", 0) > 0.003 and f.get("volume_ratio", 1) > 1.2:
            return "micro_range_ripples"
        return None

    def detect_cascade_flip(self, bar, i):
        f = bar.features
        if i < 288: return None
        if f.get("volume_ratio", 1) > 3.0 and f.get("return_1h", 0) < -0.02 and f.get("funding_rate", 0) > 0.0002:
            return "cascade_flip"
        return None

    def detect_funding_exhaustion_trap(self, bar, i):
        f = bar.features
        if i < 288: return None
        if f.get("funding_zscore", 0) > 2.5 and f.get("funding_delta", 0) < 0 and f.get("return_1h", 0) < 0.005:
            return "funding_exhaustion_trap"
        return None

    def detect_meme_mania_rotation(self, bar, i):
        f = bar.features
        if i < 288: return None
        if f.get("volume_spike", False) and (f.get("spike_up", False) or f.get("return_1h", 0) > 0.02) and f.get("intrabar_volatility", 0) > 0.02:
            return "meme_mania_rotation"
        return None

    def detect_session_gap_exploit(self, bar, i):
        f = bar.features
        if i < 288: return None
        if f.get("session_open", False) and f.get("low_liquidity", False) and f.get("intrabar_volatility", 0) > 0.015:
            return "session_gap_exploit"
        return None

    def detect_dead_cat_echo(self, bar, i):
        f = bar.features
        if i < 288: return None
        price_4h_ago = self.bars[i - 48].close
        drop_4h = (price_4h_ago - bar.close) / price_4h_ago
        price_1h_ago = self.bars[i - 12].close
        bounce_1h = (bar.close - price_1h_ago) / price_1h_ago
        if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015 and f.get("trend_exhaustion", 0) > 0 and f.get("volume_ratio", 1) < 1.0:
            return "dead_cat_echo"
        return None

    def detect_liquidity_vacuum_breakout(self, bar, i):
        f = bar.features
        if i < 288: return None
        if f.get("low_liquidity", False) and f.get("spread_widening", False) and f.get("breakout_strength_24h", 0) > 0.002 and f.get("volume_ratio", 1) > 1.0:
            return "liquidity_vacuum_breakout"
        return None

    # ----------------------------------------------------------
    # 开仓/平仓
    # ----------------------------------------------------------

    def _open_position(self, bar, strategy, direction):
        leverage = self.config.leverage
        sl_price_pct = self.config.stop_loss_capital_pct / leverage
        tp_price_pct = self.config.take_profit_min_capital_pct / leverage
        margin = self.config.initial_capital * self.config.position_size
        value = margin * leverage
        qty = value / bar.close

        if direction == "long":
            cost = margin * (1 + self.config.commission + self.config.slippage)
            stop_loss_price = bar.close * (1 - sl_price_pct)
            take_profit_price = bar.close * (1 + tp_price_pct)
        else:
            cost = margin * (1 + self.config.commission + self.config.slippage)
            stop_loss_price = bar.close * (1 + sl_price_pct)
            take_profit_price = bar.close * (1 - tp_price_pct)

        self.position = {
            "type": direction,
            "entry_price": bar.close,
            "qty": qty,
            "capital": cost,
            "margin": margin,
            "leverage": leverage,
            "entry_time": bar.timestamp,
            "entry_bar_idx": self._current_idx,
            "strategy": strategy,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "highest_price": bar.close,
            "lowest_price": bar.close,
            "trailing_stop_price": stop_loss_price,
            "max_favorable_excursion": 0.0,  # 最大有利偏移
            "max_adverse_excursion": 0.0,     # 最大不利偏移
        }
        self.capital -= cost

    def _close(self, bar, reason, bar_idx):
        if not self.position:
            return

        leverage = self.position.get("leverage", 1.0)
        entry_price = self.position["entry_price"]
        qty = self.position["qty"]
        margin = self.position.get("margin", self.position["capital"])

        if self.position["type"] == "long":
            price_pnl_pct = (bar.close - entry_price) / entry_price
            pnl = margin * price_pnl_pct * leverage
        else:
            price_pnl_pct = (entry_price - bar.close) / entry_price
            pnl = margin * price_pnl_pct * leverage

        pnl -= margin * (self.config.commission + self.config.slippage)
        pnl_pct = pnl / margin if margin > 0 else 0

        # 计算最大有利/不利偏移
        mfe = self.position.get("max_favorable_excursion", 0)
        mae = self.position.get("max_adverse_excursion", 0)

        trade = {
            "type": self.position["type"],
            "strategy": self.position["strategy"],
            "entry": entry_price,
            "exit": bar.close,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "margin": margin,
            "leverage": leverage,
            "close_reason": reason,
            "entry_time": self.position["entry_time"],
            "exit_time": bar.timestamp,
            "hold_hours": (bar.timestamp - self.position["entry_time"]).total_seconds() / 3600,
            "stop_loss_price": self.position["stop_loss_price"],
            "take_profit_price": self.position["take_profit_price"],
            "trailing_stop_price": self.position["trailing_stop_price"],
            "highest_price": self.position["highest_price"],
            "lowest_price": self.position["lowest_price"],
            "mfe": mfe,  # 最大有利偏移 (价格%)
            "mae": mae,  # 最大不利偏移 (价格%)
            "exit_bar_idx": bar_idx,
        }

        # 收集后续价格数据
        post_prices = self._collect_post_prices(bar_idx, entry_price, self.position["type"])
        trade["post_prices"] = post_prices

        # 分类收集
        if reason == "stop_loss":
            self.sl_events.append(trade)
        elif reason in ("trailing_stop", "max_take_profit"):
            self.tp_events.append(trade)

        self.all_trades.append(trade)
        self.capital += margin + pnl
        self.position = None

    def _collect_post_prices(self, exit_bar_idx, exit_price, pos_type):
        """收集平仓后N根bar的价格走势"""
        result = {}
        for bars_ahead in self.TRACK_BARS:
            future_idx = exit_bar_idx + bars_ahead
            if future_idx < len(self.bars):
                future_bar = self.bars[future_idx]
                future_price = future_bar.close
                # 计算相对于平仓价格的变化
                if pos_type == "long":
                    # 多头止损后，看价格是否继续下跌
                    # 多头止盈后，看价格是否继续上涨
                    price_change_pct = (future_price - exit_price) / exit_price
                else:
                    # 空头止损后，看价格是否继续上涨
                    # 空头止盈后，看价格是否继续下跌
                    price_change_pct = (exit_price - future_price) / exit_price

                result[f"{bars_ahead}_bars"] = {
                    "bars": bars_ahead,
                    "minutes": bars_ahead * 5,
                    "hours": bars_ahead * 5 / 60,
                    "future_price": future_price,
                    "price_change_pct": price_change_pct,
                    # 如果是止损，价格继续同方向走 = 止损合理
                    # 如果是止盈，价格继续同方向走 = 止盈过早
                }
        return result

    # ----------------------------------------------------------
    # 回测主循环
    # ----------------------------------------------------------

    def run_analysis(self) -> Dict:
        self.sl_events = []
        self.tp_events = []
        self.all_trades = []
        self.position = None
        self.capital = self.config.initial_capital

        detectors = {
            "rsi_14_long": (self.detect_rsi, "long"),
            "rsi_14_short": (self.detect_rsi, "short"),
            "macd_12_26_9_long": (self.detect_macd, "long"),
            "macd_12_26_9_short": (self.detect_macd, "short"),
            "panic_reversal": (self.detect_panic_reversal, "long"),
            "long_liquidation_bounce": (self.detect_long_liquidation_bounce, "long"),
            "volume_climax_fade": (self.detect_volume_climax_fade, "short"),
            "weak_bounce_short": (self.detect_weak_bounce_short, "short"),
            "leveraged_short_squeeze": (self.detect_leveraged_short_squeeze, "short"),
            "micro_range_ripples": (self.detect_micro_range_ripples, "long"),
            "cascade_flip": (self.detect_cascade_flip, "long"),
            "funding_exhaustion_trap": (self.detect_funding_exhaustion_trap, "short"),
            "meme_mania_rotation": (self.detect_meme_mania_rotation, "long"),
            "session_gap_exploit": (self.detect_session_gap_exploit, "long"),
            "dead_cat_echo": (self.detect_dead_cat_echo, "short"),
            "liquidity_vacuum_breakout": (self.detect_liquidity_vacuum_breakout, "long"),
        }

        for i, bar in enumerate(self.bars):
            if i < 288:
                continue

            self._current_idx = i
            f = bar.features

            signals = []
            for strategy_key, (detector, default_direction) in detectors.items():
                result = detector(bar, i)
                if result:
                    if "_long" in result:
                        direction = "long"
                        strategy = result.replace("_long", "")
                    elif "_short" in result:
                        direction = "short"
                        strategy = result.replace("_short", "")
                    else:
                        direction = default_direction
                        strategy = result
                    signals.append((strategy, direction))

            if self.position:
                elapsed = (bar.timestamp - self.position["entry_time"]).total_seconds() / 3600
                max_hold = self.config.max_hold_hours

                # 更新最高/最低价
                if self.position["type"] == "long":
                    if bar.high > self.position["highest_price"]:
                        self.position["highest_price"] = bar.high
                        drawdown_pct = self.config.trailing_stop_drawdown_pct / self.position["leverage"]
                        new_trailing_stop = self.position["highest_price"] * (1 - drawdown_pct)
                        if new_trailing_stop > self.position["stop_loss_price"]:
                            self.position["trailing_stop_price"] = new_trailing_stop
                    # MFE/MAE
                    favorable = (bar.high - self.position["entry_price"]) / self.position["entry_price"]
                    adverse = (self.position["entry_price"] - bar.low) / self.position["entry_price"]
                    self.position["max_favorable_excursion"] = max(self.position["max_favorable_excursion"], favorable)
                    self.position["max_adverse_excursion"] = max(self.position["max_adverse_excursion"], adverse)
                else:
                    if bar.low < self.position["lowest_price"]:
                        self.position["lowest_price"] = bar.low
                        drawdown_pct = self.config.trailing_stop_drawdown_pct / self.position["leverage"]
                        new_trailing_stop = self.position["lowest_price"] * (1 + drawdown_pct)
                        if new_trailing_stop < self.position["stop_loss_price"]:
                            self.position["trailing_stop_price"] = new_trailing_stop
                    favorable = (self.position["entry_price"] - bar.low) / self.position["entry_price"]
                    adverse = (bar.high - self.position["entry_price"]) / self.position["entry_price"]
                    self.position["max_favorable_excursion"] = max(self.position["max_favorable_excursion"], favorable)
                    self.position["max_adverse_excursion"] = max(self.position["max_adverse_excursion"], adverse)

                max_tp_price_pct = self.config.take_profit_max_capital_pct / self.position["leverage"]
                max_tp_price = self.position["entry_price"] * (1 + max_tp_price_pct) if self.position["type"] == "long" else self.position["entry_price"] * (1 - max_tp_price_pct)

                close_reason = None
                if elapsed >= max_hold:
                    close_reason = "time_exit"
                elif self.position["type"] == "long" and bar.low <= self.position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif self.position["type"] == "short" and bar.high >= self.position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif self.position["type"] == "long" and bar.low <= self.position["trailing_stop_price"]:
                    close_reason = "trailing_stop"
                elif self.position["type"] == "short" and bar.high >= self.position["trailing_stop_price"]:
                    close_reason = "trailing_stop"
                elif self.position["type"] == "long" and bar.high >= max_tp_price:
                    close_reason = "max_take_profit"
                elif self.position["type"] == "short" and bar.low <= max_tp_price:
                    close_reason = "max_take_profit"
                elif signals:
                    for sig_strategy, sig_direction in signals:
                        if self.position["type"] != sig_direction:
                            close_reason = "reverse_signal"
                            break

                if close_reason:
                    self._close(bar, close_reason, i)

            if not self.position and signals:
                strategy, direction = signals[0]
                self._open_position(bar, strategy, direction)

        if self.position:
            self._close(self.bars[-1], "end_of_data", len(self.bars) - 1)

        return self._analyze()

    # ----------------------------------------------------------
    # 分析
    # ----------------------------------------------------------

    def _analyze(self) -> Dict:
        """分析止损止盈合理性"""

        # === 止损分析 ===
        sl_analysis = self._analyze_sl()
        # === 止盈分析 ===
        tp_analysis = self._analyze_tp()
        # === MFE/MAE 分析 ===
        mae_analysis = self._analyze_mae()

        return {
            "stop_loss": sl_analysis,
            "take_profit": tp_analysis,
            "mae_mfe": mae_analysis,
            "summary": self._generate_summary(sl_analysis, tp_analysis, mae_analysis),
        }

    def _analyze_sl(self) -> Dict:
        """分析止损合理性
        核心逻辑：
        - 多头止损后，价格继续下跌 → 止损合理 ✅
        - 多头止损后，价格反弹上涨 → 止损过早/太紧 ❌
        - 空头止损后，价格继续上涨 → 止损合理 ✅
        - 空头止损后，价格回落下跌 → 止损过早/太紧 ❌
        """
        if not self.sl_events:
            return {"total": 0}

        total = len(self.sl_events)
        by_strategy = defaultdict(list)

        # 按时间窗口分析
        time_window_results = {}

        for bars_ahead in self.TRACK_BARS:
            key = f"{bars_ahead}_bars"
            reasonable = 0  # 止损合理次数
            unreasonable = 0  # 止损不合理次数
            avg_change = 0.0
            changes = []

            for event in self.sl_events:
                post = event.get("post_prices", {})
                if key in post:
                    change = post[key]["price_change_pct"]
                    changes.append(change)
                    # change > 0 表示价格继续朝不利方向走 = 止损合理
                    if change > 0:
                        reasonable += 1
                    else:
                        unreasonable += 1

                by_strategy[event["strategy"]].append(event)

            if changes:
                avg_change = np.mean(changes)
                median_change = np.median(changes)
                pct_reasonable = reasonable / (reasonable + unreasonable) * 100 if (reasonable + unreasonable) > 0 else 0
            else:
                median_change = 0
                pct_reasonable = 0

            time_window_results[key] = {
                "bars": bars_ahead,
                "minutes": bars_ahead * 5,
                "hours": round(bars_ahead * 5 / 60, 1),
                "reasonable": reasonable,
                "unreasonable": unreasonable,
                "pct_reasonable": round(pct_reasonable, 2),
                "avg_price_change_pct": round(avg_change * 100, 4),
                "median_price_change_pct": round(median_change * 100, 4),
            }

        # 按策略统计
        strategy_stats = {}
        for strat, events in by_strategy.items():
            # 用24bar(2小时)作为主要判断窗口
            key_24 = "24_bars"
            reasonable_24 = 0
            total_24 = 0
            avg_pnl = np.mean([e["pnl"] for e in events])
            avg_mae = np.mean([e["mae"] for e in events]) if events else 0
            avg_mfe = np.mean([e["mfe"] for e in events]) if events else 0

            for event in events:
                post = event.get("post_prices", {})
                if key_24 in post:
                    total_24 += 1
                    if post[key_24]["price_change_pct"] > 0:
                        reasonable_24 += 1

            strategy_stats[strat] = {
                "count": len(events),
                "avg_pnl": round(avg_pnl, 2),
                "avg_mae_pct": round(avg_mae * 100, 4),
                "avg_mfe_pct": round(avg_mfe * 100, 4),
                "reasonable_pct_2h": round(reasonable_24 / total_24 * 100, 2) if total_24 > 0 else 0,
            }

        # 止损距离分析
        sl_distances = []
        for event in self.sl_events:
            entry = event["entry"]
            sl_price = event["stop_loss_price"]
            if event["type"] == "long":
                dist = (entry - sl_price) / entry
            else:
                dist = (sl_price - entry) / entry
            sl_distances.append(dist)

        return {
            "total": total,
            "avg_pnl": round(np.mean([e["pnl"] for e in self.sl_events]), 2),
            "avg_hold_hours": round(np.mean([e["hold_hours"] for e in self.sl_events]), 2),
            "avg_sl_distance_pct": round(np.mean(sl_distances) * 100, 4) if sl_distances else 0,
            "by_time_window": time_window_results,
            "by_strategy": strategy_stats,
        }

    def _analyze_tp(self) -> Dict:
        """分析止盈合理性
        核心逻辑：
        - 多头止盈后，价格继续上涨 → 止盈过早 ❌ (少赚了)
        - 多头止盈后，价格回落下跌 → 止盈合理 ✅ (卖在高位)
        - 空头止盈后，价格继续下跌 → 止盈过早 ❌
        - 空头止盈后，价格反弹上涨 → 止盈合理 ✅
        """
        if not self.tp_events:
            return {"total": 0}

        total = len(self.tp_events)
        by_strategy = defaultdict(list)

        time_window_results = {}

        for bars_ahead in self.TRACK_BARS:
            key = f"{bars_ahead}_bars"
            reasonable = 0  # 止盈合理 (价格反转了)
            premature = 0   # 止盈过早 (价格继续走)
            changes = []

            for event in self.tp_events:
                post = event.get("post_prices", {})
                if key in post:
                    change = post[key]["price_change_pct"]
                    changes.append(change)
                    # change < 0 表示价格反转 = 止盈合理
                    # change > 0 表示价格继续走 = 止盈过早
                    if change < 0:
                        reasonable += 1
                    else:
                        premature += 1

                by_strategy[event["strategy"]].append(event)

            if changes:
                avg_change = np.mean(changes)
                median_change = np.median(changes)
                pct_reasonable = reasonable / (reasonable + premature) * 100 if (reasonable + premature) > 0 else 0
            else:
                median_change = 0
                pct_reasonable = 0

            time_window_results[key] = {
                "bars": bars_ahead,
                "minutes": bars_ahead * 5,
                "hours": round(bars_ahead * 5 / 60, 1),
                "reasonable": reasonable,
                "premature": premature,
                "pct_reasonable": round(pct_reasonable, 2),
                "avg_price_change_pct": round(avg_change * 100, 4),
                "median_price_change_pct": round(median_change * 100, 4),
                # 止盈后平均多走了多少 (如果是过早的话)
                "avg_extra_move_pct": round(max(0, avg_change) * 100, 4),
            }

        # 按策略统计
        strategy_stats = {}
        for strat, events in by_strategy.items():
            key_24 = "24_bars"
            reasonable_24 = 0
            total_24 = 0
            avg_pnl = np.mean([e["pnl"] for e in events])
            avg_mfe = np.mean([e["mfe"] for e in events]) if events else 0

            for event in events:
                post = event.get("post_prices", {})
                if key_24 in post:
                    total_24 += 1
                    if post[key_24]["price_change_pct"] < 0:
                        reasonable_24 += 1

            strategy_stats[strat] = {
                "count": len(events),
                "avg_pnl": round(avg_pnl, 2),
                "avg_mfe_pct": round(avg_mfe * 100, 4),
                "reasonable_pct_2h": round(reasonable_24 / total_24 * 100, 2) if total_24 > 0 else 0,
            }

        # 止盈类型分布
        trailing_count = len([e for e in self.tp_events if e["close_reason"] == "trailing_stop"])
        max_tp_count = len([e for e in self.tp_events if e["close_reason"] == "max_take_profit"])

        return {
            "total": total,
            "trailing_stop_count": trailing_count,
            "max_take_profit_count": max_tp_count,
            "avg_pnl": round(np.mean([e["pnl"] for e in self.tp_events]), 2),
            "avg_hold_hours": round(np.mean([e["hold_hours"] for e in self.tp_events]), 2),
            "by_time_window": time_window_results,
            "by_strategy": strategy_stats,
        }

    def _analyze_mae(self) -> Dict:
        """MAE/MFE 分析 - 评估止损止盈位置"""
        if not self.all_trades:
            return {}

        # 按平仓原因分组的MAE/MFE
        by_reason = defaultdict(lambda: {"mae": [], "mfe": [], "pnl": []})

        for trade in self.all_trades:
            reason = trade["close_reason"]
            by_reason[reason]["mae"].append(trade["mae"])
            by_reason[reason]["mfe"].append(trade["mfe"])
            by_reason[reason]["pnl"].append(trade["pnl"])

        result = {}
        for reason, data in by_reason.items():
            result[reason] = {
                "count": len(data["mae"]),
                "avg_mae_pct": round(np.mean(data["mae"]) * 100, 4),
                "max_mae_pct": round(np.max(data["mae"]) * 100, 4),
                "avg_mfe_pct": round(np.mean(data["mfe"]) * 100, 4),
                "max_mfe_pct": round(np.max(data["mfe"]) * 100, 4),
                "avg_pnl": round(np.mean(data["pnl"]), 2),
            }

        # 止损交易的MAE分布 (看止损是否太紧)
        sl_trades = [t for t in self.all_trades if t["close_reason"] == "stop_loss"]
        if sl_trades:
            maes = [t["mae"] for t in sl_trades]
            # MAE vs 止损距离
            sl_distances = []
            for t in sl_trades:
                entry = t["entry"]
                sl_price = t["stop_loss_price"]
                if t["type"] == "long":
                    dist = (entry - sl_price) / entry
                else:
                    dist = (sl_price - entry) / entry
                sl_distances.append(dist)

            result["stop_loss_mae_detail"] = {
                "avg_mae": round(np.mean(maes) * 100, 4),
                "median_mae": round(np.median(maes) * 100, 4),
                "avg_sl_distance": round(np.mean(sl_distances) * 100, 4),
                # MAE / 止损距离 比率 - 越接近1说明止损刚好被打
                "mae_to_sl_ratio": round(np.mean(maes) / np.mean(sl_distances), 4) if np.mean(sl_distances) > 0 else 0,
                # 有多少比例的止损交易 MAE 超过了止损距离的2倍 (说明止损太紧)
                "pct_mae_2x_sl": round(sum(1 for m, s in zip(maes, sl_distances) if m > s * 2) / len(maes) * 100, 2),
            }

        return result

    def _generate_summary(self, sl_analysis, tp_analysis, mae_analysis) -> Dict:
        """生成总结和建议"""
        recommendations = []

        # 止损分析
        if sl_analysis.get("total", 0) > 0:
            tw = sl_analysis.get("by_time_window", {})
            # 看1小时后的合理性
            key_12 = "12_bars"
            if key_12 in tw:
                pct = tw[key_12]["pct_reasonable"]
                if pct < 50:
                    recommendations.append({
                        "type": "stop_loss",
                        "severity": "high",
                        "finding": f"止损1小时后仅{pct:.1f}%合理（价格反弹）",
                        "suggestion": "止损太紧，建议放宽至本金的15-20%"
                    })
                elif pct < 60:
                    recommendations.append({
                        "type": "stop_loss",
                        "severity": "medium",
                        "finding": f"止损1小时后{pct:.1f}%合理",
                        "suggestion": "止损略紧，可以考虑动态止损"
                    })
                else:
                    recommendations.append({
                        "type": "stop_loss",
                        "severity": "low",
                        "finding": f"止损1小时后{pct:.1f}%合理",
                        "suggestion": "止损设置基本合理"
                    })

            # 看24小时后的合理性
            key_288 = "288_bars"
            if key_288 in tw:
                pct_24h = tw[key_288]["pct_reasonable"]
                recommendations.append({
                    "type": "stop_loss",
                    "severity": "info",
                    "finding": f"止损24小时后{pct_24h:.1f}%合理",
                    "suggestion": "长期来看止损方向判断" + ("较好" if pct_24h > 55 else "需要优化")
                })

        # 止盈分析
        if tp_analysis.get("total", 0) > 0:
            tw = tp_analysis.get("by_time_window", {})
            key_12 = "12_bars"
            if key_12 in tw:
                pct = tw[key_12]["pct_reasonable"]
                extra = tw[key_12].get("avg_extra_move_pct", 0)
                if pct < 40:
                    recommendations.append({
                        "type": "take_profit",
                        "severity": "high",
                        "finding": f"止盈1小时后仅{pct:.1f}%合理（{extra:.3f}%额外空间被错过）",
                        "suggestion": "止盈过早，建议放宽追踪止盈回撤至15-20%"
                    })
                elif pct < 55:
                    recommendations.append({
                        "type": "take_profit",
                        "severity": "medium",
                        "finding": f"止盈1小时后{pct:.1f}%合理",
                        "suggestion": "追踪止盈回撤可以适当放宽"
                    })
                else:
                    recommendations.append({
                        "type": "take_profit",
                        "severity": "low",
                        "finding": f"止盈1小时后{pct:.1f}%合理",
                        "suggestion": "止盈设置基本合理"
                    })

        # MAE分析
        if "stop_loss_mae_detail" in mae_analysis:
            detail = mae_analysis["stop_loss_mae_detail"]
            ratio = detail["mae_to_sl_ratio"]
            pct_2x = detail["pct_mae_2x_sl"]
            if ratio > 1.5:
                recommendations.append({
                    "type": "stop_loss",
                    "severity": "high",
                    "finding": f"MAE/止损距离比={ratio:.2f}，{pct_2x:.1f}%的交易MAE超过止损距离2倍",
                    "suggestion": "止损明显太紧，价格经常先打止损再反转"
                })
            elif ratio > 1.2:
                recommendations.append({
                    "type": "stop_loss",
                    "severity": "medium",
                    "finding": f"MAE/止损距离比={ratio:.2f}",
                    "suggestion": "部分交易止损太紧，可以考虑ATR动态止损"
                })

        return recommendations


# ============================================================
# 报告输出
# ============================================================

def print_analysis_report(analysis: Dict):
    print("\n" + "=" * 100)
    print("📊 止损止盈合理性分析报告")
    print("=" * 100)

    # 止损分析
    sl = analysis["stop_loss"]
    print(f"\n{'='*60}")
    print(f"🔴 止损分析 (共 {sl.get('total', 0)} 笔止损)")
    print(f"{'='*60}")
    print(f"   平均亏损: ${sl.get('avg_pnl', 0):,.2f}")
    print(f"   平均持仓: {sl.get('avg_hold_hours', 0):.2f} 小时")
    print(f"   平均止损距离: {sl.get('avg_sl_distance_pct', 0):.4f}%")

    print(f"\n   止损后价格走势 (价格继续朝不利方向走 = 止损合理):")
    print(f"   {'时间窗口':<12} | {'合理次数':>8} | {'不合理次数':>10} | {'合理率':>8} | {'平均价格变化':>12} | {'中位数变化':>12}")
    print(f"   {'-'*75}")

    tw = sl.get("by_time_window", {})
    for key in ["6_bars", "12_bars", "24_bars", "48_bars", "96_bars", "144_bars", "288_bars", "576_bars"]:
        if key in tw:
            d = tw[key]
            print(f"   {d['hours']:>5.1f}h ({d['minutes']:>4.0f}m) | {d['reasonable']:>8} | {d['unreasonable']:>10} | {d['pct_reasonable']:>7.1f}% | {d['avg_price_change_pct']:>11.4f}% | {d['median_price_change_pct']:>11.4f}%")

    # 止损按策略
    print(f"\n   按策略止损分析 (2小时窗口):")
    print(f"   {'策略':<30} | {'次数':>6} | {'平均亏损':>10} | {'平均MAE':>10} | {'合理率':>8}")
    print(f"   {'-'*75}")
    for strat, data in sorted(sl.get("by_strategy", {}).items(), key=lambda x: -x[1]["count"]):
        print(f"   {strat:<30} | {data['count']:>6} | ${data['avg_pnl']:>9,.2f} | {data['avg_mae_pct']:>9.4f}% | {data['reasonable_pct_2h']:>7.1f}%")

    # 止盈分析
    tp = analysis["take_profit"]
    print(f"\n{'='*60}")
    print(f"🟢 止盈分析 (共 {tp.get('total', 0)} 笔止盈)")
    print(f"{'='*60}")
    print(f"   追踪止盈: {tp.get('trailing_stop_count', 0)} 笔")
    print(f"   最大止盈: {tp.get('max_take_profit_count', 0)} 笔")
    print(f"   平均盈利: ${tp.get('avg_pnl', 0):,.2f}")
    print(f"   平均持仓: {tp.get('avg_hold_hours', 0):.2f} 小时")

    print(f"\n   止盈后价格走势 (价格反转 = 止盈合理, 价格继续走 = 止盈过早):")
    print(f"   {'时间窗口':<12} | {'合理次数':>8} | {'过早次数':>8} | {'合理率':>8} | {'平均价格变化':>12} | {'错过空间':>10}")
    print(f"   {'-'*75}")

    tw = tp.get("by_time_window", {})
    for key in ["6_bars", "12_bars", "24_bars", "48_bars", "96_bars", "144_bars", "288_bars", "576_bars"]:
        if key in tw:
            d = tw[key]
            print(f"   {d['hours']:>5.1f}h ({d['minutes']:>4.0f}m) | {d['reasonable']:>8} | {d['premature']:>8} | {d['pct_reasonable']:>7.1f}% | {d['avg_price_change_pct']:>11.4f}% | {d['avg_extra_move_pct']:>9.4f}%")

    # 止盈按策略
    print(f"\n   按策略止盈分析 (2小时窗口):")
    print(f"   {'策略':<30} | {'次数':>6} | {'平均盈利':>10} | {'平均MFE':>10} | {'合理率':>8}")
    print(f"   {'-'*75}")
    for strat, data in sorted(tp.get("by_strategy", {}).items(), key=lambda x: -x[1]["count"]):
        print(f"   {strat:<30} | {data['count']:>6} | ${data['avg_pnl']:>9,.2f} | {data['avg_mfe_pct']:>9.4f}% | {data['reasonable_pct_2h']:>7.1f}%")

    # MAE/MFE 分析
    mae = analysis.get("mae_mfe", {})
    if mae:
        print(f"\n{'='*60}")
        print(f"📈 MAE/MFE 分析")
        print(f"{'='*60}")
        print(f"   {'平仓原因':<20} | {'次数':>6} | {'平均MAE':>10} | {'最大MAE':>10} | {'平均MFE':>10} | {'最大MFE':>10}")
        print(f"   {'-'*80}")
        for reason, data in mae.items():
            if reason == "stop_loss_mae_detail":
                continue
            print(f"   {reason:<20} | {data['count']:>6} | {data['avg_mae_pct']:>9.4f}% | {data['max_mae_pct']:>9.4f}% | {data['avg_mfe_pct']:>9.4f}% | {data['max_mfe_pct']:>9.4f}%")

        if "stop_loss_mae_detail" in mae:
            d = mae["stop_loss_mae_detail"]
            print(f"\n   🔍 止损交易MAE详情:")
            print(f"   平均MAE: {d['avg_mae']:.4f}%")
            print(f"   中位数MAE: {d['median_mae']:.4f}%")
            print(f"   平均止损距离: {d['avg_sl_distance']:.4f}%")
            print(f"   MAE/止损距离比: {d['mae_to_sl_ratio']:.2f} (>1.5 说明止损太紧)")
            print(f"   MAE超过止损2倍的比例: {d['pct_mae_2x_sl']:.1f}%")

    # 总结建议
    summary = analysis.get("summary", [])
    if summary:
        print(f"\n{'='*60}")
        print(f"💡 总结与建议")
        print(f"{'='*60}")
        for i, rec in enumerate(summary, 1):
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(rec["severity"], "•")
            print(f"\n   {severity_icon} [{rec['severity'].upper()}] {rec['finding']}")
            print(f"   → 建议: {rec['suggestion']}")


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 100)
    print("🔍 止损止盈合理性分析")
    print("=" * 100)

    data_path = Path("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return

    df = pd.read_parquet(data_path)
    print(f"\n📊 原始数据: {len(df)} 行, {len(df.columns)} 列")

    five_months_ago = df["timestamp"].max() - pd.Timedelta(days=150)
    df_recent = df[df["timestamp"] >= five_months_ago].copy().reset_index(drop=True)
    print(f"   近5个月数据: {len(df_recent)} 行 ({df_recent['timestamp'].min().date()} ~ {df_recent['timestamp'].max().date()})")

    df_5m = df_recent.set_index("timestamp").resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
        "funding_rate": "last", "funding_zscore": "last", "funding_delta": "last",
        "bb_upper": "last", "bb_lower": "last", "bb_middle": "last", "bb_position": "last",
        "rsi_14": "last", "macd": "last", "macd_signal": "last", "macd_hist": "last",
        "regime": "last", "regime_code": "last", "spike_up": "max", "spike_down": "max",
        "trend_exhaustion": "last", "state_squeeze": "max", "state_panic_dump": "max",
        "state_breakout": "max", "state_accumulation": "max",
        "breakout_high_24h": "max", "breakout_low_24h": "max", "breakout_strength_24h": "max",
    }).dropna(subset=["close"]).reset_index()
    print(f"   5分钟数据: {len(df_5m)} 行")

    config = BacktestConfig(
        initial_capital=10000,
        commission=0.0005,
        slippage=0.0002,
        position_size=1.0,
        leverage=50.0,
        stop_loss_capital_pct=0.10,
        take_profit_min_capital_pct=0.60,
        take_profit_max_capital_pct=10.0,
        trailing_stop_drawdown_pct=0.10,
        max_hold_hours=48,
    )

    print(f"\n📊 回测配置:")
    print(f"   本金: ${config.initial_capital:,.0f}")
    print(f"   杠杆: {config.leverage}x")
    print(f"   止损: 本金 {config.stop_loss_capital_pct*100:.0f}% (价格 {config.stop_loss_capital_pct/config.leverage*100:.2f}%)")
    print(f"   止盈: 动态 {config.take_profit_min_capital_pct*100:.0f}% ~ {config.take_profit_max_capital_pct*100:.0f}%")
    print(f"   追踪止盈回撤: {config.trailing_stop_drawdown_pct*100:.0f}%")

    analyzer = SLTPAnalyzer(config)
    print(f"\n⏳ 加载数据...")
    analyzer.load_df(df_5m)

    print(f"⏳ 准备特征...")
    analyzer.prepare_features()

    print(f"\n⏳ 运行分析...")
    analysis = analyzer.run_analysis()

    print_analysis_report(analysis)

    # 保存结果
    output_dir = Path("data_lake/research")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 精简保存 (去掉post_prices详情)
    save_analysis = {
        "stop_loss": {k: v for k, v in analysis["stop_loss"].items() if k != "by_strategy"},
        "take_profit": {k: v for k, v in analysis["take_profit"].items() if k != "by_strategy"},
        "mae_mfe": analysis["mae_mfe"],
        "summary": analysis["summary"],
    }

    output_path = output_dir / "sltp_analysis_2025_2026.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_analysis, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 分析结果已保存: {output_path}")
    print(f"\n{'=' * 100}")
    print("✅ 分析完成！")
    print("=" * 100)

    return analysis


if __name__ == "__main__":
    main()
