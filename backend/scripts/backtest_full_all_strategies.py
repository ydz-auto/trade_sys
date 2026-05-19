#!/usr/bin/env python3
"""
全策略统一回测 - 包含系统中所有 35+ 策略
每个策略独立统计，统一参数：$10,000本金, 50x杠杆, 止损15%, 追踪止盈60%~1000%(回撤15%)
数据范围: 近5个月 (2025-12 ~ 2026-04)
"""

import sys
from pathlib import Path
script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from collections import defaultdict
import pandas as pd
import numpy as np


# ============================================================
# 数据结构
# ============================================================

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
    leverage: float = 50.0
    stop_loss_capital_pct: float = 0.15
    take_profit_min_capital_pct: float = 0.60
    take_profit_max_capital_pct: float = 10.0
    trailing_stop_drawdown_pct: float = 0.15
    max_hold_hours: int = 48


# ============================================================
# 全策略回测引擎
# ============================================================

class FullStrategyBacktester:
    """全策略统一回测 - 每个策略独立运行"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.bars: List[Bar] = []

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
        volumes = np.array([b.volume for b in self.bars])
        avg_volumes = np.full(n, volumes[0])
        for i in range(1, n):
            start = max(0, i - 288)
            avg_volumes[i] = np.mean(volumes[start:i + 1])

        highs = np.array([b.high for b in self.bars])
        rolling_highs_24 = np.full(n, highs[0])
        for i in range(1, n):
            start = max(0, i - 288)
            rolling_highs_24[i] = np.max(highs[start:i])

        for i in range(n):
            bar = self.bars[i]
            f = bar.features

            # 基础收益率
            f["return_1h"] = (bar.close - self.bars[i-12].close) / self.bars[i-12].close if i >= 12 else 0.0
            f["return_4h"] = (bar.close - self.bars[i-48].close) / self.bars[i-48].close if i >= 48 else 0.0
            f["return_5m"] = (bar.close - self.bars[i-1].close) / self.bars[i-1].close if i >= 1 else 0.0

            # 波动率
            f["intrabar_volatility"] = (bar.high - bar.low) / bar.close if bar.close > 0 else 0
            f["volume_ratio"] = bar.volume / avg_volumes[i] if avg_volumes[i] > 0 else 1.0

            # 时间特征
            f["hour"] = bar.timestamp.hour
            f["day_of_week"] = bar.timestamp.dayofweek
            f["is_weekend"] = bar.timestamp.dayofweek >= 5
            f["session"] = "asia" if f["hour"] < 8 else ("europe" if f["hour"] < 16 else "us")
            f["session_open"] = f["hour"] in [0, 8, 16]

            # K线形态
            body = abs(bar.close - bar.open)
            total = bar.high - bar.low + 0.001
            f["wick_ratio"] = (bar.high - bar.close) / total if bar.close > bar.open else (bar.high - bar.open) / total
            f["lower_wick_ratio"] = (bar.open - bar.low) / total if bar.open > bar.close else (bar.close - bar.low) / total

            # 清理 NaN
            for key in ["funding_rate", "funding_zscore", "funding_delta", "trend_exhaustion",
                        "rsi_14", "macd", "macd_signal", "macd_hist",
                        "bb_upper", "bb_lower", "bb_middle", "bb_position", "bb_width",
                        "regime", "regime_code", "spike_up", "spike_down",
                        "breakout_strength_24h", "oi_change_1h"]:
                val = f.get(key, 0)
                if pd.isna(val): val = 0
                f[key] = val

            f["volume_spike"] = f["volume_ratio"] > 2.5
            f["low_liquidity"] = f["volume_ratio"] < 0.7
            f["spread_widening"] = f["intrabar_volatility"] / (f["volume_ratio"] + 0.01) > 0.03

            # RSI
            if f["rsi_14"] == 0 and i >= 14:
                prices = [b.close for b in self.bars[i-14:i+1]]
                deltas = np.diff(prices)
                gains = np.where(deltas > 0, deltas, 0)
                losses = np.where(deltas < 0, -deltas, 0)
                avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 1e-10
                avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 1e-10
                rs = avg_gain / avg_loss if avg_loss > 0 else 0
                f["rsi_14"] = 100 - (100 / (1 + rs))

            # MACD
            if f["macd"] == 0 and i >= 26:
                prices = [b.close for b in self.bars[i-26:i+1]]
                ema12 = np.mean(prices[-12:])
                ema26 = np.mean(prices[-26:])
                f["macd"] = ema12 - ema26
                f["macd_signal"] = f["macd"] * 0.9

            # 布林带宽度
            if f.get("bb_width", 0) == 0 and i >= 20:
                prices = [b.close for b in self.bars[i-20:i+1]]
                std = np.std(prices)
                mean = np.mean(prices)
                f["bb_width"] = (4 * std) / mean if mean > 0 else 0.02
                f["bb_position"] = (bar.close - (mean - 2*std)) / (4*std + 0.001)

            # 均线
            if i >= 200:
                ma50 = np.mean([b.close for b in self.bars[i-50:i+1]])
                ma200 = np.mean([b.close for b in self.bars[i-200:i+1]])
                f["ma50"] = ma50
                f["ma200"] = ma200
                f["ma_cross"] = "golden" if ma50 > ma200 else "death"
            else:
                f["ma50"] = bar.close
                f["ma200"] = bar.close
                f["ma_cross"] = "none"

            # EMA
            if i >= 50:
                ema20 = np.mean([b.close for b in self.bars[i-20:i+1]])
                ema50 = np.mean([b.close for b in self.bars[i-50:i+1]])
                f["ema20"] = ema20
                f["ema50"] = ema50
            else:
                f["ema20"] = bar.close
                f["ema50"] = bar.close

    # ----------------------------------------------------------
    # 所有策略检测器 (35+)
    # ----------------------------------------------------------

    def detect_all(self, bar, i) -> List[Tuple[str, str]]:
        """返回 [(strategy_id, direction), ...]"""
        f = bar.features
        signals = []

        # === 一、经典技术指标策略 (6个) ===

        # 1. RSI (14)
        rsi = f.get("rsi_14", 50)
        if rsi < 30: signals.append(("rsi_14", "long"))
        elif rsi > 70: signals.append(("rsi_14", "short"))

        # 2. MACD (12/26/9)
        macd = f.get("macd", 0)
        macd_signal = f.get("macd_signal", 0)
        if macd > macd_signal and macd > 0: signals.append(("macd_12_26_9", "long"))
        elif macd < macd_signal and macd < 0: signals.append(("macd_12_26_9", "short"))

        # 3. Bollinger Bands
        bb_pos = f.get("bb_position", 0.5)
        if bb_pos < 0: signals.append(("bollinger_bands", "long"))
        elif bb_pos > 1: signals.append(("bollinger_bands", "short"))

        # 4. MA Cross (50/200)
        ma_cross = f.get("ma_cross", "none")
        if ma_cross == "golden": signals.append(("ma_cross", "long"))
        elif ma_cross == "death": signals.append(("ma_cross", "short"))

        # 5. RSI+MACD 组合
        if rsi < 35 and macd > macd_signal: signals.append(("rsi_macd_combo", "long"))
        elif rsi > 65 and macd < macd_signal: signals.append(("rsi_macd_combo", "short"))

        # 6. EMA Cross (20/50)
        ema20 = f.get("ema20", bar.close)
        ema50 = f.get("ema50", bar.close)
        if i >= 2:
            prev_ema20 = self.bars[i-2].features.get("ema20", ema20)
            prev_ema50 = self.bars[i-2].features.get("ema50", ema50)
            if prev_ema20 <= prev_ema50 and ema20 > ema50: signals.append(("ema_cross", "long"))
            elif prev_ema20 >= prev_ema50 and ema20 < ema50: signals.append(("ema_cross", "short"))

        # === 二、事件驱动策略 (6个) ===

        # 7. Panic Reversal
        if f["return_1h"] < -0.015 and f["volume_ratio"] > 1.5:
            signals.append(("panic_reversal", "long"))

        # 8. Long Liquidation Bounce
        if f["return_1h"] < -0.02 and f["volume_ratio"] > 2.0 and f.get("rsi_14", 50) < 25:
            signals.append(("long_liquidation_bounce", "long"))

        # 9. Volume Climax Fade
        if f["volume_ratio"] > 2.0 and f["wick_ratio"] > 0.3 and f["return_1h"] > 0.003:
            signals.append(("volume_climax_fade", "short"))

        # 10. Weak Bounce Short
        if i >= 48:
            drop_4h = (self.bars[i-48].close - bar.close) / self.bars[i-48].close
            bounce_1h = f["return_1h"]
            if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015:
                signals.append(("weak_bounce_short", "short"))

        # 11. Fake Breakout Trap
        if i >= 24:
            rolling_high = max(b.high for b in self.bars[i-24:i])
            if bar.high > rolling_high * 1.005 and f["volume_ratio"] < 1.0:
                signals.append(("fake_breakout_trap", "short"))

        # 12. Short Squeeze Hunt
        if f.get("funding_rate", 0) < -0.0001 and f.get("oi_change_1h", 0) > 0.02 and f["return_1h"] > 0.015:
            signals.append(("short_squeeze_hunt", "long"))

        # === 三、策略地图策略 (6个额外) ===

        # 13. Compression Breakout
        if f.get("bb_width", 0.02) < 0.015 and f.get("breakout_strength_24h", 0) > 0.003 and f["volume_ratio"] > 1.2:
            signals.append(("compression_breakout", "long"))

        # 14. Funding Reset
        if abs(f.get("funding_rate", 0)) > 0.0005 and f.get("funding_delta", 0) < -0.0001:
            signals.append(("funding_reset", "short"))

        # 15. OI Flush
        if f.get("oi_change_1h", 0) < -0.05 and abs(f["return_1h"]) < 0.02:
            signals.append(("oi_flush", "short"))

        # 16. Weekend Liquidity Trap
        if f["is_weekend"] and f["volume_ratio"] < 0.7:
            if i >= 24:
                rh = max(b.high for b in self.bars[i-24:i])
                rl = min(b.low for b in self.bars[i-24:i])
                if bar.high > rh * 1.005 or bar.low < rl * 0.995:
                    signals.append(("weekend_liquidity_trap", "short"))

        # 17. Session Rotation (Asia→US)
        if f["hour"] in [15, 16, 17] and i >= 12:
            asia_vol = np.mean([self.bars[i-12+j].features.get("volume_ratio", 1) for j in range(12)])
            if asia_vol < 0.8 and f["return_1h"] > -0.01:
                signals.append(("session_rotation", "long"))

        # 18. Macro Shock Recovery
        if i >= 48:
            drop_4h = (self.bars[i-48].close - bar.close) / self.bars[i-48].close
            if drop_4h > 0.05 and abs(f["return_1h"]) < 0.005:
                signals.append(("macro_shock_recovery", "long"))

        # === 四、创新策略 (8个) ===

        # 19. Leveraged Short Squeeze
        score = 0
        if f.get("funding_zscore", 0) > 1.5: score += 3
        elif f.get("funding_zscore", 0) > 1.0: score += 1
        if f.get("funding_rate", 0) > 0.0003: score += 2
        if f["return_1h"] > 0.01: score += 2
        elif f["return_1h"] > 0.005: score += 1
        if f["volume_ratio"] > 2.5: score += 2
        elif f["volume_ratio"] > 1.5: score += 1
        if f["volume_spike"]: score += 1
        if f["spread_widening"]: score += 1
        if f["wick_ratio"] > 0.6: score += 1
        if score >= 5: signals.append(("leveraged_short_squeeze", "short"))

        # 20. Micro Range Ripples
        if f.get("bb_width", 0.02) < 0.015 and f.get("breakout_strength_24h", 0) > 0.003 and f["volume_ratio"] > 1.2:
            signals.append(("micro_range_ripples", "long"))

        # 21. Cascade Flip
        if f["volume_ratio"] > 3.0 and f["return_1h"] < -0.02 and f.get("funding_rate", 0) > 0.0002:
            signals.append(("cascade_flip", "long"))

        # 22. Funding Exhaustion Trap
        if f.get("funding_zscore", 0) > 2.5 and f.get("funding_delta", 0) < 0 and f["return_1h"] < 0.005:
            signals.append(("funding_exhaustion_trap", "short"))

        # 23. Meme Mania Rotation
        if f["volume_spike"] and (f.get("spike_up", False) or f["return_1h"] > 0.02) and f["intrabar_volatility"] > 0.02:
            signals.append(("meme_mania_rotation", "long"))

        # 24. Session Gap Exploit
        if f["session_open"] and f["low_liquidity"] and f["intrabar_volatility"] > 0.015:
            signals.append(("session_gap_exploit", "long"))

        # 25. Dead Cat Echo
        if i >= 48:
            drop_4h = (self.bars[i-48].close - bar.close) / self.bars[i-48].close
            bounce_1h = f["return_1h"]
            if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015 and f.get("trend_exhaustion", 0) > 0 and f["volume_ratio"] < 1.0:
                signals.append(("dead_cat_echo", "short"))

        # 26. Liquidity Vacuum Breakout
        if f["low_liquidity"] and f["spread_widening"] and f.get("breakout_strength_24h", 0) > 0.002 and f["volume_ratio"] > 1.0:
            signals.append(("liquidity_vacuum_breakout", "long"))

        # === 五、Playbook 行为策略 (7个) ===

        # 27. Playbook: Panic Reversal (放宽版)
        if f["return_1h"] < -0.015 and f["volume_ratio"] > 1.3:
            signals.append(("pb_panic_reversal", "long"))

        # 28. Playbook: Fake Breakout
        if i >= 60:
            rh60 = max(b.high for b in self.bars[i-60:i])
            if bar.high > rh60 * 1.005:
                signals.append(("pb_fake_breakout", "short"))

        # 29. Playbook: OI Flush
        if f.get("funding_rate", 0) > 0.0002 and f["volume_ratio"] > 1.5 and f["return_5m"] > 0.01:
            signals.append(("pb_oi_flush", "long"))

        # 30. Playbook: Weekend Manipulation
        if f["is_weekend"] and f["volume_ratio"] < 0.9 and f["intrabar_volatility"] > 0.005:
            signals.append(("pb_weekend_manipulation", "long"))

        # 31. Playbook: Short Squeeze
        if f.get("funding_rate", 0) > 0.0003 and f["return_5m"] > 0.01 and f["volume_ratio"] > 1.5:
            signals.append(("pb_short_squeeze", "long"))

        # 32. Playbook: Volume Climax
        if f["volume_ratio"] > 1.8 and f["intrabar_volatility"] > 0.015:
            signals.append(("pb_volume_climax", "long"))

        # 33. Playbook: Liquidation Cascade (proxy via extreme drop)
        if f["return_1h"] < -0.03 and f["volume_ratio"] > 3.0:
            signals.append(("pb_liquidation_cascade", "long"))

        # === 六、V2 优化策略 (6个) ===

        # 34. Volume Climax Fade V2
        if f["volume_ratio"] > 2.0 and f["wick_ratio"] > 0.3 and f["return_1h"] > 0.003:
            signals.append(("v2_volume_climax_fade", "short"))

        # 35. Weak Bounce Short V2
        if i >= 48:
            drop_4h = (self.bars[i-48].close - bar.close) / self.bars[i-48].close
            if drop_4h > 0.02 and 0.003 < f["return_1h"] < 0.015 and f["volume_ratio"] > 1.5:
                signals.append(("v2_weak_bounce_short", "short"))

        # 36. Fake Breakout Trap V2
        if i >= 24:
            rh = max(b.high for b in self.bars[i-24:i])
            if bar.high > rh * 1.005 and f["volume_ratio"] < 1.2:
                signals.append(("v2_fake_breakout_trap", "short"))

        # 37. Weekend Liquidity Trap V2
        if f["is_weekend"] and f["volume_ratio"] < 0.5 and f["intrabar_volatility"] > 0.003 and f["hour"] < 8:
            signals.append(("v2_weekend_trap", "short"))

        # 38. Short Squeeze Hunt V2
        if f.get("funding_rate", 0) < -0.00005 and f.get("oi_change_1h", 0) > 0.01 and f["return_1h"] > 0.008:
            signals.append(("v2_short_squeeze_hunt", "long"))

        # 39. Funding Reset V2
        if f.get("funding_rate", 0) > 0.0003 and f.get("funding_delta", 0) < -0.00005:
            signals.append(("v2_funding_reset", "short"))

        return signals

    # ----------------------------------------------------------
    # 市场环境检测
    # ----------------------------------------------------------

    def detect_market_env(self, bar, i) -> str:
        """检测当前市场环境: panic_drop / slow_drop / bounce / normal"""
        if i < 48:
            return "normal"
        return_4h = (bar.close - self.bars[i-48].close) / self.bars[i-48].close
        if return_4h < -0.08:
            return "panic_drop"
        elif return_4h < -0.02:
            return "slow_drop"
        elif return_4h > 0.02:
            return "bounce"
        return "normal"

    def detect_regime(self, bar) -> str:
        """获取当前 regime"""
        r = bar.features.get("regime", "ranging")
        if pd.isna(r): r = "ranging"
        return str(r)

    def check_context(self, strategy_id: str, bar, i) -> bool:
        """
        检查策略是否在合适的上下文中触发
        返回 True = 允许触发, False = 过滤掉
        """
        f = bar.features
        env = self.detect_market_env(bar, i)
        regime = self.detect_regime(bar)

        # === 经典技术指标：只在 normal/bounce 环境触发 ===
        if strategy_id in ("rsi_14", "macd_12_26_9", "bollinger_bands", "ma_cross", "rsi_macd_combo", "ema_cross"):
            # 趋势策略在震荡市中关闭
            if strategy_id in ("macd_12_26_9", "ma_cross", "ema_cross"):
                if regime == "ranging":
                    return False
            # RSI/布林带在恐慌暴跌中关闭（假信号太多）
            if env == "panic_drop":
                return False
            return True

        # === 事件驱动策略：需要对应的市场环境 ===
        if strategy_id == "panic_reversal":
            return env in ("panic_drop", "slow_drop")
        if strategy_id == "pb_panic_reversal":
            return env in ("panic_drop", "slow_drop")
        if strategy_id == "long_liquidation_bounce":
            return env in ("panic_drop", "slow_drop")
        if strategy_id == "pb_liquidation_cascade":
            return env == "panic_drop"
        if strategy_id == "macro_shock_recovery":
            return env in ("panic_drop", "slow_drop")

        # 做空策略：在 bounce/normal 中更有效
        if strategy_id in ("volume_climax_fade", "v2_volume_climax_fade"):
            return env in ("bounce", "normal")
        if strategy_id in ("weak_bounce_short", "v2_weak_bounce_short"):
            return env in ("slow_drop", "normal")
        if strategy_id in ("fake_breakout_trap", "v2_fake_breakout_trap"):
            return env in ("bounce", "normal")
        if strategy_id in ("pb_fake_breakout"):
            return env in ("bounce", "normal")
        if strategy_id == "dead_cat_echo":
            return env in ("bounce", "normal")
        if strategy_id in ("funding_reset", "v2_funding_reset"):
            return env in ("normal", "bounce")
        if strategy_id == "funding_exhaustion_trap":
            return env in ("normal", "bounce")

        # 做多事件策略：在下跌环境中更有效
        if strategy_id in ("short_squeeze_hunt", "v2_short_squeeze_hunt"):
            return env in ("slow_drop", "normal")
        if strategy_id == "pb_short_squeeze":
            return env in ("slow_drop", "normal")
        if strategy_id == "cascade_flip":
            return env in ("panic_drop", "slow_drop")
        if strategy_id == "pb_oi_flush":
            return env in ("panic_drop", "slow_drop")
        if strategy_id == "oi_flush":
            return env in ("slow_drop", "normal")

        # 突破类策略：在 normal/ranging 中更有效
        if strategy_id in ("compression_breakout", "micro_range_ripples"):
            return regime in ("ranging", "normal")
        if strategy_id == "session_rotation":
            return env == "normal"
        if strategy_id == "session_gap_exploit":
            return env == "normal"
        if strategy_id == "liquidity_vacuum_breakout":
            return regime == "ranging"

        # 杠杆空头挤压：在高funding环境中
        if strategy_id == "leveraged_short_squeeze":
            return f.get("funding_zscore", 0) > 0.5 or env in ("bounce", "normal")

        # Meme/周末策略：保持原样
        if strategy_id in ("meme_mania_rotation", "pb_weekend_manipulation", "weekend_liquidity_trap", "v2_weekend_trap"):
            return True

        # Playbook
        if strategy_id == "pb_volume_climax":
            return env in ("bounce", "normal")

        # 默认允许
        return True

    # ----------------------------------------------------------
    # 单策略回测
    # ----------------------------------------------------------

    def backtest_strategy(self, strategy_id: str, direction_filter: str = None) -> Dict:
        """对单个策略独立回测"""
        position = None
        capital = self.config.initial_capital
        trades = []

        for i, bar in enumerate(self.bars):
            if i < 288:
                continue

            signals = self.detect_all(bar, i)

            # 过滤出当前策略的信号 + 上下文检查
            strategy_signals = [(s, d) for s, d in signals if s == strategy_id]
            if direction_filter:
                strategy_signals = [(s, d) for s, d in strategy_signals if d == direction_filter]
            # 上下文过滤
            strategy_signals = [(s, d) for s, d in strategy_signals if self.check_context(s, bar, i)]

            if position:
                elapsed = (bar.timestamp - position["entry_time"]).total_seconds() / 3600
                max_hold = self.config.max_hold_hours
                leverage = position["leverage"]

                # 更新追踪止盈
                if position["type"] == "long":
                    if bar.high > position["highest_price"]:
                        position["highest_price"] = bar.high
                        dd = self.config.trailing_stop_drawdown_pct / leverage
                        new_ts = position["highest_price"] * (1 - dd)
                        if new_ts > position["trailing_stop_price"]:
                            position["trailing_stop_price"] = new_ts
                else:
                    if bar.low < position["lowest_price"]:
                        position["lowest_price"] = bar.low
                        dd = self.config.trailing_stop_drawdown_pct / leverage
                        new_ts = position["lowest_price"] * (1 + dd)
                        if new_ts < position["trailing_stop_price"]:
                            position["trailing_stop_price"] = new_ts

                max_tp_pct = self.config.take_profit_max_capital_pct / leverage
                max_tp = position["entry_price"] * (1 + max_tp_pct) if position["type"] == "long" else position["entry_price"] * (1 - max_tp_pct)

                close_reason = None
                if elapsed >= max_hold:
                    close_reason = "time_exit"
                elif position["type"] == "long" and bar.low <= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif position["type"] == "short" and bar.high >= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif position["type"] == "long" and bar.low <= position["trailing_stop_price"]:
                    close_reason = "trailing_stop"
                elif position["type"] == "short" and bar.high >= position["trailing_stop_price"]:
                    close_reason = "trailing_stop"
                elif position["type"] == "long" and bar.high >= max_tp:
                    close_reason = "max_take_profit"
                elif position["type"] == "short" and bar.low <= max_tp:
                    close_reason = "max_take_profit"

                if close_reason:
                    margin = position["margin"]
                    if position["type"] == "long":
                        pnl = margin * ((bar.close - position["entry_price"]) / position["entry_price"]) * leverage
                    else:
                        pnl = margin * ((position["entry_price"] - bar.close) / position["entry_price"]) * leverage
                    # 平仓手续费 (taker 0.05% + 滑点 0.02%)
                    close_fee = margin * (self.config.commission + self.config.slippage)
                    pnl -= close_fee

                    trades.append({
                        "pnl": pnl,
                        "pnl_pct": pnl / margin if margin > 0 else 0,
                        "close_reason": close_reason,
                        "hold_hours": elapsed,
                        "type": position["type"],
                    })
                    capital += margin + pnl
                    position = None

            if not position and strategy_signals:
                _, direction = strategy_signals[0]
                leverage = self.config.leverage
                sl_pct = self.config.stop_loss_capital_pct / leverage
                # 开仓手续费 (taker 0.05% + 滑点 0.02%)
                open_fee = self.config.initial_capital * (self.config.commission + self.config.slippage)
                margin = self.config.initial_capital - open_fee  # 扣除开仓手续费后的实际保证金
                value = margin * leverage
                qty = value / bar.close

                if direction == "long":
                    sl_price = bar.close * (1 - sl_pct)
                else:
                    sl_price = bar.close * (1 + sl_pct)

                position = {
                    "type": direction,
                    "entry_price": bar.close,
                    "qty": qty,
                    "margin": margin,
                    "leverage": leverage,
                    "entry_time": bar.timestamp,
                    "stop_loss_price": sl_price,
                    "trailing_stop_price": sl_price,
                    "highest_price": bar.high,
                    "lowest_price": bar.low,
                }

        if position:
            margin = position["margin"]
            if position["type"] == "long":
                pnl = margin * ((self.bars[-1].close - position["entry_price"]) / position["entry_price"]) * position["leverage"]
            else:
                pnl = margin * ((position["entry_price"] - self.bars[-1].close) / position["entry_price"]) * position["leverage"]
            pnl -= margin * (self.config.commission + self.config.slippage)
            trades.append({
                "pnl": pnl, "pnl_pct": pnl / margin if margin > 0 else 0,
                "close_reason": "end_of_data", "hold_hours": 0, "type": position["type"],
            })

        # 统计
        if not trades:
            return {"strategy": strategy_id, "total_trades": 0, "status": "no_trades"}

        pnls = [t["pnl"] for t in trades]
        wins = [t for t in trades if t["pnl"] > 0]
        total_pnl = sum(pnls)
        win_rate = len(wins) / len(trades) if trades else 0
        avg_pnl = np.mean(pnls)
        avg_hold = np.mean([t["hold_hours"] for t in trades])

        # 最大回撤
        peak = self.config.initial_capital
        max_dd = 0
        running = self.config.initial_capital
        for p in pnls:
            running += p
            if running > peak: peak = running
            dd = (peak - running) / peak
            if dd > max_dd: max_dd = dd

        # 按平仓原因分组
        by_reason = defaultdict(lambda: {"count": 0, "pnl": 0})
        for t in trades:
            by_reason[t["close_reason"]]["count"] += 1
            by_reason[t["close_reason"]]["pnl"] += t["pnl"]

        return {
            "strategy": strategy_id,
            "total_trades": len(trades),
            "wins": len(wins),
            "win_rate": round(win_rate, 4),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(avg_pnl, 2),
            "max_pnl": round(max(pnls), 2),
            "min_pnl": round(min(pnls), 2),
            "avg_hold_hours": round(avg_hold, 2),
            "max_drawdown_pct": round(max_dd, 4),
            "by_close_reason": {k: {"count": v["count"], "pnl": round(v["pnl"], 2)} for k, v in by_reason.items()},
            "longs": len([t for t in trades if t["type"] == "long"]),
            "shorts": len([t for t in trades if t["type"] == "short"]),
        }

    def run_all(self) -> Dict:
        """运行所有策略"""
        # 策略列表 (去重后的所有独立策略)
        all_strategies = [
            # 经典技术指标 (6)
            ("rsi_14", None),
            ("macd_12_26_9", None),
            ("bollinger_bands", None),
            ("ma_cross", None),
            ("rsi_macd_combo", None),
            ("ema_cross", None),
            # 事件驱动 (6)
            ("panic_reversal", None),
            ("long_liquidation_bounce", None),
            ("volume_climax_fade", None),
            ("weak_bounce_short", None),
            ("fake_breakout_trap", None),
            ("short_squeeze_hunt", None),
            # 策略地图 (6)
            ("compression_breakout", None),
            ("funding_reset", None),
            ("oi_flush", None),
            ("weekend_liquidity_trap", None),
            ("session_rotation", None),
            ("macro_shock_recovery", None),
            # 创新 (8)
            ("leveraged_short_squeeze", None),
            ("micro_range_ripples", None),
            ("cascade_flip", None),
            ("funding_exhaustion_trap", None),
            ("meme_mania_rotation", None),
            ("session_gap_exploit", None),
            ("dead_cat_echo", None),
            ("liquidity_vacuum_breakout", None),
            # Playbook (7)
            ("pb_panic_reversal", None),
            ("pb_fake_breakout", None),
            ("pb_oi_flush", None),
            ("pb_weekend_manipulation", None),
            ("pb_short_squeeze", None),
            ("pb_volume_climax", None),
            ("pb_liquidation_cascade", None),
            # V2 优化 (6)
            ("v2_volume_climax_fade", None),
            ("v2_weak_bounce_short", None),
            ("v2_fake_breakout_trap", None),
            ("v2_weekend_trap", None),
            ("v2_short_squeeze_hunt", None),
            ("v2_funding_reset", None),
        ]

        results = []
        for strategy_id, direction in all_strategies:
            r = self.backtest_strategy(strategy_id, direction)
            results.append(r)
            status = "✅" if r.get("total_pnl", 0) > 0 else "❌" if r.get("total_pnl", 0) < 0 else "⚪"
            trades = r.get("total_trades", 0)
            pnl = r.get("total_pnl", 0)
            wr = r.get("win_rate", 0)
            if trades > 0:
                print(f"   {status} {strategy_id:<35} | {trades:>6} 笔 | 胜率 {wr:>6.1%} | 收益 ${pnl:>12,.2f}")
            else:
                print(f"   ⚪ {strategy_id:<35} | 无交易")

        return {"strategies": results, "config": {
            "initial_capital": self.config.initial_capital,
            "leverage": self.config.leverage,
            "stop_loss_pct": self.config.stop_loss_capital_pct,
            "trailing_drawdown_pct": self.config.trailing_stop_drawdown_pct,
        }}


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 110)
    print("🚀 全策略统一回测 - 系统内所有 39 个策略")
    print("=" * 110)

    data_path = Path("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return

    df = pd.read_parquet(data_path)
    print(f"\n📊 原始数据: {len(df)} 行")

    five_months_ago = df["timestamp"].max() - pd.Timedelta(days=150)
    df_recent = df[df["timestamp"] >= five_months_ago].copy().reset_index(drop=True)
    print(f"   近5个月: {len(df_recent)} 行 ({df_recent['timestamp'].min().date()} ~ {df_recent['timestamp'].max().date()})")

    df_5m = df_recent.set_index("timestamp").resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
        "funding_rate": "last", "funding_zscore": "last", "funding_delta": "last",
        "bb_upper": "last", "bb_lower": "last", "bb_middle": "last", "bb_position": "last",
        "rsi_14": "last", "macd": "last", "macd_signal": "last", "macd_hist": "last",
        "regime": "last", "regime_code": "last", "spike_up": "max", "spike_down": "max",
        "trend_exhaustion": "last", "state_squeeze": "max", "state_panic_dump": "max",
        "state_breakout": "max", "state_accumulation": "max",
        "breakout_high_24h": "max", "breakout_low_24h": "max", "breakout_strength_24h": "max",
        "oi_change_1h": "last",
    }).dropna(subset=["close"]).reset_index()
    print(f"   5分钟数据: {len(df_5m)} 行")

    config = BacktestConfig(
        initial_capital=10000, leverage=50.0,
        stop_loss_capital_pct=0.15, trailing_stop_drawdown_pct=0.15,
    )

    print(f"\n📊 配置: 本金${config.initial_capital:,.0f} | {config.leverage}x杠杆 | 止损{config.stop_loss_capital_pct*100:.0f}% | 追踪回撤{config.trailing_stop_drawdown_pct*100:.0f}%")
    print(f"\n{'='*110}")
    print(f"📋 回测结果 (每个策略独立统计)")
    print(f"{'='*110}")

    bt = FullStrategyBacktester(config)
    print(f"\n⏳ 加载数据...")
    bt.load_df(df_5m)
    print(f"⏳ 准备特征...")
    bt.prepare_features()

    print(f"\n⏳ 运行回测...\n")
    result = bt.run_all()

    # 汇总
    profitable = [r for r in result["strategies"] if r.get("total_pnl", 0) > 0]
    losing = [r for r in result["strategies"] if r.get("total_pnl", 0) < 0]
    no_trades = [r for r in result["strategies"] if r.get("total_trades", 0) == 0]

    print(f"\n{'='*110}")
    print(f"📊 汇总")
    print(f"{'='*110}")
    print(f"   总策略数: {len(result['strategies'])}")
    print(f"   盈利策略: {len(profitable)}")
    print(f"   亏损策略: {len(losing)}")
    print(f"   无交易:   {len(no_trades)}")

    if profitable:
        print(f"\n   🏆 盈利策略排行:")
        for r in sorted(profitable, key=lambda x: -x["total_pnl"]):
            print(f"      {r['strategy']:<35} | {r['total_trades']:>5} 笔 | 胜率 {r['win_rate']:>6.1%} | ${r['total_pnl']:>12,.2f}")

    if losing:
        print(f"\n   ❌ 亏损策略排行:")
        for r in sorted(losing, key=lambda x: x["total_pnl"]):
            print(f"      {r['strategy']:<35} | {r['total_trades']:>5} 笔 | 胜率 {r['win_rate']:>6.1%} | ${r['total_pnl']:>12,.2f}")

    if no_trades:
        print(f"\n   ⚪ 无交易策略:")
        for r in no_trades:
            print(f"      {r['strategy']}")

    # 保存
    output_dir = Path("data_lake/research")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "full_all_strategies_backtest.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 结果已保存: {output_path}")


if __name__ == "__main__":
    main()
