#!/usr/bin/env python3
"""
5分钟数据 + 个性化移动止盈 回测
================================

改进:
1. 数据粒度: 1分钟 → 5分钟 (减少噪音)
2. 止盈参数: 统一500点 → 个性化 (根据策略波动特征)
3. 仓位管理: 全仓复利 → 固定10%仓位 (避免溢出)
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
import pandas as pd
import numpy as np
import pyarrow.parquet as pq
from datetime import datetime
from typing import Dict, List, Tuple
import gc

# ============================================================
# 配置
# ============================================================

class Config:
    initial_capital: float = 10000.0
    leverage: float = 50.0
    stop_loss_capital_pct: float = 0.15  # 本金15%止损 (价格0.3%, 约248点)
    position_pct: float = 0.10  # 固定10%仓位
    max_hold_bars: int = 576  # 48h * 12 bars/h (5分钟)
    commission: float = 0.0005
    slippage: float = 0.0002
    cooldown_bars: int = 6  # 30分钟冷却 (减少过度交易)


# ============================================================
# 个性化止盈参数 (基于P75波动)
# ============================================================

STRATEGY_TP_CONFIG = {
    # 基于P90最大有利波动 (5分钟数据, 48h追踪)
    # P90范围: 4295~5383点, 止盈起点=P90×80%, 最大=P90×3(封顶3000)
    
    # A组: 高波动 (P90 > 4500)
    "BTC Swing":              {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 5383},
    "Cascade Flip":           {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4612},
    "Panic Reversal":         {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4840},
    "Bollinger Bands":        {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4772},
    "Volume Climax":          {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4848},
    
    # B组: 中等波动 (P90 4300-4500)
    "Liquidation Cascade":    {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4391},
    "Short Squeeze":          {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4419},
    "MA Cross":               {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 5217},
    "RSI+MACD":               {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 4295},
    
    # C组: 低波动 (样本少)
    "Weekend Manipulation":   {"tp_start": 500, "tp_max": 3000, "tp_step": 500, "p90": 3329},
    
    # 默认
    "default": {"tp_start": 500, "tp_max": 3000, "tp_step": 500},
}


# ============================================================
# 5分钟数据生成
# ============================================================

def generate_5min_data(df_1m: pd.DataFrame) -> pd.DataFrame:
    """从1分钟数据聚合5分钟数据"""
    print("   聚合5分钟数据...")
    
    df = df_1m.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # OHLCV聚合
    ohlcv_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    }
    
    df_5m = df.resample('5min').agg(ohlcv_dict)
    df_5m = df_5m.dropna()
    df_5m = df_5m.reset_index()
    
    print(f"   聚合完成: {len(df_5m)} 行")
    return df_5m


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标特征"""
    print("   计算特征...")
    
    closes = df['close'].values
    volumes = df['volume'].values
    highs = df['high'].values
    lows = df['low'].values
    
    # 收益率
    df['return_5m'] = closes / np.roll(closes, 1) - 1
    df['return_1h'] = closes / np.roll(closes, 12) - 1
    
    # 成交量比率
    vol_ma = pd.Series(volumes).rolling(288, min_periods=1).mean().values
    df['volume_ratio'] = volumes / (vol_ma + 1e-10)
    
    # RSI
    df['rsi'] = calculate_rsi(closes, 14)
    
    # MACD
    macd = calculate_macd(closes, 12, 26, 9)
    df['macd_line'] = macd['macd']
    df['macd_signal'] = macd['signal']
    df['macd_hist'] = macd['histogram']
    
    # EMA
    df['ema_20'] = calculate_ema(closes, 20)
    df['ema_50'] = calculate_ema(closes, 50)
    
    # Bollinger Bands
    bb = calculate_bollinger(closes, 20, 2.0)
    df['bb_upper'] = bb['upper']
    df['bb_lower'] = bb['lower']
    df['bb_middle'] = bb['middle']
    df['bb_width'] = (bb['upper'] - bb['lower']) / (bb['middle'] + 1e-10)
    
    # SMA
    df['sma_50'] = calculate_sma(closes, 50)
    df['sma_200'] = calculate_sma(closes, 200)
    
    # 波动率
    df['volatility_1h'] = pd.Series(df['return_5m']).rolling(12).std().values
    
    # 上影线/下影线比例
    candle_range = highs - lows + 1e-10
    df['upper_wick_ratio'] = (highs - np.maximum(closes, np.roll(closes, 1))) / candle_range
    df['lower_wick_ratio'] = (np.minimum(closes, np.roll(closes, 1)) - lows) / candle_range
    
    # 填充NaN
    df = df.fillna(0)
    
    print(f"   特征计算完成")
    return df


def calculate_rsi(prices, period=14):
    rsi = np.full_like(prices, 50.0)
    deltas = np.diff(prices)
    for i in range(period + 1, len(prices)):
        window = deltas[i-period:i]
        gains = window[window > 0]
        losses = -window[window < 0]
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))
    return rsi


def calculate_macd(prices, fast, slow, signal):
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}


def calculate_ema(prices, period):
    ema = np.zeros_like(prices)
    ema[0] = prices[0]
    k = 2 / (period + 1)
    for i in range(1, len(prices)):
        ema[i] = ema[i-1] * (1 - k) + prices[i] * k
    return ema


def calculate_sma(prices, period):
    sma = np.zeros_like(prices)
    for i in range(period, len(prices)):
        sma[i] = np.mean(prices[i-period:i])
    return sma


def calculate_bollinger(prices, period, std_dev):
    middle = calculate_sma(prices, period)
    upper = np.zeros_like(prices)
    lower = np.zeros_like(prices)
    for i in range(period, len(prices)):
        std = np.std(prices[i-period:i])
        upper[i] = middle[i] + std_dev * std
        lower[i] = middle[i] - std_dev * std
    return {'upper': upper, 'lower': lower, 'middle': middle}


# ============================================================
# 策略定义
# ============================================================

class Strategy:
    def __init__(self, name: str, direction: str):
        self.name = name
        self.direction = direction
        tp_config = STRATEGY_TP_CONFIG.get(name, STRATEGY_TP_CONFIG["default"])
        self.tp_start = tp_config["tp_start"]
        self.tp_max = tp_config["tp_max"]
        self.tp_step = tp_config["tp_step"]
        
    def detect(self, df: pd.DataFrame, i: int) -> Tuple[bool, float]:
        raise NotImplementedError


# BTC Swing
class BTCSwingStrategy(Strategy):
    def __init__(self):
        super().__init__("BTC Swing", "long")
        
    def detect(self, df, i):
        if i < 50:
            return False, 0
        rsi = df['rsi'].iloc[i]
        macd = df['macd_line'].iloc[i]
        signal = df['macd_signal'].iloc[i]
        prev_macd = df['macd_line'].iloc[i-1]
        prev_signal = df['macd_signal'].iloc[i-1]
        
        macd_cross = prev_macd <= prev_signal and macd > signal
        if rsi <= 30 and macd_cross:
            return True, 1.0
        return False, 0


# Bollinger Bands
class BollingerBandsStrategy(Strategy):
    def __init__(self):
        super().__init__("Bollinger Bands", "both")
        
    def detect(self, df, i):
        if i < 20:
            return False, 0
        price = df['close'].iloc[i]
        prev_price = df['close'].iloc[i-1]
        lower = df['bb_lower'].iloc[i]
        upper = df['bb_upper'].iloc[i]
        prev_lower = df['bb_lower'].iloc[i-1]
        prev_upper = df['bb_upper'].iloc[i-1]
        
        if prev_price >= prev_lower and price < lower:
            self.direction = "long"
            return True, 0.7
        if prev_price <= prev_upper and price > upper:
            self.direction = "short"
            return True, 0.7
        return False, 0


# MA Cross
class MACrossStrategy(Strategy):
    def __init__(self):
        super().__init__("MA Cross", "both")
        
    def detect(self, df, i):
        if i < 200:
            return False, 0
        fast = df['sma_50'].iloc[i]
        slow = df['sma_200'].iloc[i]
        prev_fast = df['sma_50'].iloc[i-1]
        prev_slow = df['sma_200'].iloc[i-1]
        
        if prev_fast <= prev_slow and fast > slow:
            self.direction = "long"
            return True, 0.75
        if prev_fast >= prev_slow and fast < slow:
            self.direction = "short"
            return True, 0.75
        return False, 0


# RSI+MACD
class RSIMACDStrategy(Strategy):
    def __init__(self):
        super().__init__("RSI+MACD", "both")
        
    def detect(self, df, i):
        if i < 26:
            return False, 0
        rsi = df['rsi'].iloc[i]
        macd = df['macd_line'].iloc[i]
        signal = df['macd_signal'].iloc[i]
        prev_macd = df['macd_line'].iloc[i-1]
        prev_signal = df['macd_signal'].iloc[i-1]
        
        if rsi <= 30 and prev_macd <= prev_signal and macd > signal:
            self.direction = "long"
            return True, 0.85
        if rsi >= 70 and prev_macd >= prev_signal and macd < signal:
            self.direction = "short"
            return True, 0.85
        return False, 0


# Liquidation Cascade
class LiquidationCascadeStrategy(Strategy):
    def __init__(self):
        super().__init__("Liquidation Cascade", "long")
        
    def detect(self, df, i):
        if i < 12:
            return False, 0
        score = 0
        if df['volume_ratio'].iloc[i] > 3:
            score += 3
        elif df['volume_ratio'].iloc[i] > 2:
            score += 2
        if df['return_1h'].iloc[i] < -0.015:
            score += 2
        elif df['return_1h'].iloc[i] < -0.01:
            score += 1
        if df['volatility_1h'].iloc[i] > df['volatility_1h'].iloc[i-12:i].mean() * 2:
            score += 1
        return score >= 5, score


# Short Squeeze
class ShortSqueezeStrategy(Strategy):
    def __init__(self):
        super().__init__("Short Squeeze", "long")
        
    def detect(self, df, i):
        if i < 12:
            return False, 0
        score = 0
        if df['return_1h'].iloc[i] > 0.01:
            score += 2
        elif df['return_1h'].iloc[i] > 0.005:
            score += 1
        if df['volume_ratio'].iloc[i] > 2.5:
            score += 2
        elif df['volume_ratio'].iloc[i] > 1.5:
            score += 1
        if df['volatility_1h'].iloc[i] > df['volatility_1h'].iloc[i-12:i].mean() * 1.5:
            score += 1
        return score >= 4, score


# Cascade Flip
class CascadeFlipStrategy(Strategy):
    def __init__(self):
        super().__init__("Cascade Flip", "long")
        
    def detect(self, df, i):
        if i < 12:
            return False, 0
        score = 0
        if df['volume_ratio'].iloc[i] > 3:
            score += 3
        if df['return_1h'].iloc[i] < -0.02:
            score += 2
        if df['lower_wick_ratio'].iloc[i] > 0.5:
            score += 2
        return score >= 5, score


# Panic Reversal
class PanicReversalStrategy(Strategy):
    def __init__(self):
        super().__init__("Panic Reversal", "long")
        
    def detect(self, df, i):
        if i < 12:
            return False, 0
        if df['return_1h'].iloc[i] < -0.015 and df['volume_ratio'].iloc[i] > 1.3:
            return True, 0.8
        return False, 0


# Volume Climax
class VolumeClimaxStrategy(Strategy):
    def __init__(self):
        super().__init__("Volume Climax", "short")
        
    def detect(self, df, i):
        if i < 6:
            return False, 0
        volume_spike = df['volume_ratio'].iloc[i] > 2.0
        upper_wick = df['upper_wick_ratio'].iloc[i] > 0.3
        price_up = df['return_5m'].iloc[i] > 0
        
        if volume_spike and upper_wick and price_up:
            return True, 0.8
        return False, 0


# Weekend Manipulation
class WeekendManipulationStrategy(Strategy):
    def __init__(self):
        super().__init__("Weekend Manipulation", "both")
        
    def detect(self, df, i):
        if i < 6:
            return False, 0
        if df['volume_ratio'].iloc[i] < 0.6 and abs(df['return_5m'].iloc[i]) > 0.008:
            self.direction = "long" if df['return_5m'].iloc[i] > 0 else "short"
            return True, 0.6
        return False, 0


# ============================================================
# 回测引擎
# ============================================================

def run_backtest(
    df: pd.DataFrame,
    config: Config,
    strategy: Strategy,
    start_idx: int = 0,
    end_idx: int = None
) -> List[Dict]:
    """运行回测 - 固定仓位 + 个性化移动止盈"""
    
    price_sl_pct = config.stop_loss_capital_pct / config.leverage
    n = len(df) if end_idx is None else end_idx
    trades = []
    capital = config.initial_capital
    
    last_signal_bar = -999
    i = max(288, start_idx)
    
    while i < n:
        if i - last_signal_bar < config.cooldown_bars:
            i += 1
            continue
        
        triggered, score = strategy.detect(df, i)
        if not triggered:
            i += 1
            continue
        
        last_signal_bar = i
        entry_price = df['close'].iloc[i]
        entry_time = df['timestamp'].iloc[i]
        # 修复: both方向策略使用detect中动态设置的direction
        direction = strategy.direction
        
        # 固定仓位
        margin = capital * config.position_pct
        
        # 止损价
        if direction == "long":
            sl_price = entry_price * (1 - price_sl_pct)
        else:
            sl_price = entry_price * (1 + price_sl_pct)
        
        # 个性化移动止盈
        tp_start = strategy.tp_start
        tp_max = strategy.tp_max
        tp_step = strategy.tp_step
        
        trailing_tp_points = tp_start
        if direction == "long":
            trailing_tp_price = entry_price + trailing_tp_points
        else:
            trailing_tp_price = entry_price - trailing_tp_points
        
        max_favorable = 0.0
        max_adverse = 0.0
        
        exit_price = None
        exit_reason = None
        j = i + 1
        max_bars = config.max_hold_bars
        
        while j < n and (j - i) < max_bars:
            h = df['high'].iloc[j]
            l = df['low'].iloc[j]
            
            if direction == "long":
                favorable = h - entry_price
                adverse = entry_price - l
            else:
                favorable = entry_price - l
                adverse = h - entry_price
            
            if favorable > max_favorable:
                max_favorable = favorable
            if adverse > max_adverse:
                max_adverse = adverse
            
            # 更新移动止盈
            # 修复: 当max_favorable超过当前止盈点数时，止盈上移一个步长
            if max_favorable >= trailing_tp_points + tp_step:
                trailing_tp_points = min(trailing_tp_points + tp_step, tp_max)
                if direction == "long":
                    trailing_tp_price = entry_price + trailing_tp_points
                else:
                    trailing_tp_price = entry_price - trailing_tp_points
            
            # 检查止损和止盈 (先检查止盈，再检查止损)
            if direction == "long":
                # 止盈: 价格上涨触及移动止盈线
                if h >= trailing_tp_price:
                    exit_price = trailing_tp_price
                    exit_reason = "trailing_tp"
                    break
                # 止损: 价格下跌触及
                if l <= sl_price:
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
            else:
                # 止盈: 价格下跌触及移动止盈线
                if l <= trailing_tp_price:
                    exit_price = trailing_tp_price
                    exit_reason = "trailing_tp"
                    break
                # 止损: 价格上涨触及
                if h >= sl_price:
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
            
            j += 1
        
        if exit_price is None:
            exit_price = df['close'].iloc[min(j, n-1)]
            exit_reason = "time_exit"
            j = min(j, n-1)
        
        # 计算盈亏
        if direction == "long":
            price_pnl_pct = (exit_price - entry_price) / entry_price
        else:
            price_pnl_pct = (entry_price - exit_price) / entry_price
        
        leveraged_pnl_pct = price_pnl_pct * config.leverage
        fee_pct = (config.commission + config.slippage) * 2 * config.leverage
        leveraged_pnl_pct -= fee_pct
        
        pnl = margin * leveraged_pnl_pct
        new_capital = capital + pnl  # 只用固定仓位，不影响总资金
        
        trades.append({
            "entry_time": str(entry_time),
            "exit_time": str(df['timestamp'].iloc[j]),
            "entry_price": round(float(entry_price), 1),
            "exit_price": round(float(exit_price), 1),
            "direction": direction,
            "pnl_pct": round(float(leveraged_pnl_pct), 4),
            "pnl": round(float(pnl), 2),
            "capital_before": round(float(capital), 2),
            "capital_after": round(float(new_capital), 2),
            "exit_reason": exit_reason,
            "hold_bars": int(j - i),
            "max_favorable": round(float(max_favorable), 1),
            "max_adverse": round(float(max_adverse), 1),
            "trailing_tp_hit": float(trailing_tp_points),
            "tp_start": float(tp_start),
        })
        
        capital = new_capital
        if capital <= 0:
            break
        
        # 修复: 从交易结束的下一根bar继续扫描，不跳过
        i = j + 1
    
    return trades


def analyze_trades(trades: List[Dict], initial_capital: float) -> Dict:
    """分析交易结果"""
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "total_return_pct": 0, "max_drawdown_pct": 0,
            "avg_win_pct": 0, "avg_loss_pct": 0, "profit_factor": 0,
        }
    
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    
    # 最大回撤
    peak = initial_capital
    max_dd = 0
    capital = initial_capital
    for t in trades:
        capital += t["pnl"]
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    total_pnl = sum(t["pnl"] for t in trades)
    total_return_pct = (capital - initial_capital) / initial_capital
    
    total_wins = sum(t["pnl"] for t in wins)
    total_losses = abs(sum(t["pnl"] for t in losses))
    
    return {
        "total_trades": len(trades),
        "win_rate": len(wins) / len(trades) if trades else 0,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd,
        "avg_win_pct": float(np.mean([t["pnl_pct"] for t in wins])) if wins else 0,
        "avg_loss_pct": float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0,
        "profit_factor": total_wins / total_losses if total_losses > 0 else 999,
        "sl_count": sum(1 for t in trades if t["exit_reason"] == "stop_loss"),
        "tp_count": sum(1 for t in trades if t["exit_reason"] == "trailing_tp"),
        "time_count": sum(1 for t in trades if t["exit_reason"] == "time_exit"),
        "initial_capital": initial_capital,
        "final_capital": capital,
        "avg_hold_bars": float(np.mean([t["hold_bars"] for t in trades])),
        "avg_max_favorable": float(np.mean([t["max_favorable"] for t in trades])),
    }


# ============================================================
# 主函数
# ============================================================

def main():
    print("="*120)
    print("  5分钟数据 + 个性化移动止盈 回测")
    print("="*120)
    
    config = Config()
    
    # 加载1分钟数据
    data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return
    
    print(f"\n📥 加载1分钟数据...")
    usecols = ["timestamp", "open", "high", "low", "close", "volume"]
    df_1m = pd.read_parquet(data_path, columns=usecols)
    df_1m = df_1m.sort_values("timestamp").reset_index(drop=True)
    print(f"   1分钟数据: {len(df_1m)} 行")
    print(f"   时间范围: {df_1m['timestamp'].min()} ~ {df_1m['timestamp'].max()}")
    
    # 生成5分钟数据
    print(f"\n⏳ 生成5分钟数据...")
    df = generate_5min_data(df_1m)
    df = calculate_features(df)
    
    # 近5个月索引
    cutoff_date = df['timestamp'].max() - pd.Timedelta(days=150)
    recent_start_idx = df[df['timestamp'] >= cutoff_date].index[0]
    print(f"   近5个月起始: {df.loc[recent_start_idx, 'timestamp']} (索引 {recent_start_idx})")
    
    del df_1m
    gc.collect()
    
    # 定义策略
    strategies = [
        BTCSwingStrategy(),
        BollingerBandsStrategy(),
        MACrossStrategy(),
        RSIMACDStrategy(),
        LiquidationCascadeStrategy(),
        ShortSqueezeStrategy(),
        CascadeFlipStrategy(),
        PanicReversalStrategy(),
        VolumeClimaxStrategy(),
        WeekendManipulationStrategy(),
    ]
    
    print(f"\n📊 共 {len(strategies)} 个策略待回测")
    
    all_results = {}
    recent_results = {}
    
    output_dir = backend_path / "data_lake/research"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for idx, strategy in enumerate(strategies, 1):
        print(f"\n{'='*100}")
        print(f"  [{idx}/{len(strategies)}] {strategy.name}")
        print(f"  止盈: {strategy.tp_start}→{strategy.tp_max}点 (步长{strategy.tp_step})")
        print(f"{'='*100}")
        
        # 全部历史
        trades_all = run_backtest(df, config, strategy, start_idx=0)
        stats_all = analyze_trades(trades_all, config.initial_capital)
        
        # 近5个月
        trades_recent = run_backtest(df, config, strategy, start_idx=recent_start_idx)
        stats_recent = analyze_trades(trades_recent, config.initial_capital)
        
        all_results[strategy.name] = {"stats": stats_all, "trades": trades_all}
        recent_results[strategy.name] = {"stats": stats_recent, "trades": trades_recent}
        
        # 打印结果
        print(f"\n  📊 全部历史:")
        if stats_all["total_trades"] > 0:
            print(f"     交易: {stats_all['total_trades']} | 胜率: {stats_all['win_rate']*100:.1f}% | "
                  f"收益: {stats_all['total_return_pct']*100:+.1f}% | 回撤: {stats_all['max_drawdown_pct']*100:.1f}% | "
                  f"盈亏比: {stats_all['profit_factor']:.2f}")
            print(f"     止损: {stats_all['sl_count']} | 止盈: {stats_all['tp_count']} | 超时: {stats_all['time_count']}")
            print(f"     平均持仓: {stats_all['avg_hold_bars']:.0f} bars ({stats_all['avg_hold_bars']*5:.0f}分钟)")
            print(f"     平均最大波动: {stats_all['avg_max_favorable']:.0f}点")
        else:
            print(f"     无交易")
        
        print(f"\n  📊 近5个月:")
        if stats_recent["total_trades"] > 0:
            print(f"     交易: {stats_recent['total_trades']} | 胜率: {stats_recent['win_rate']*100:.1f}% | "
                  f"收益: {stats_recent['total_return_pct']*100:+.1f}% | 回撤: {stats_recent['max_drawdown_pct']*100:.1f}%")
        else:
            print(f"     无交易")
        
        del trades_all, trades_recent
        gc.collect()
    
    # 汇总报告
    print(f"\n{'='*120}")
    print("  📈 综合回测报告 (5分钟 + P90止盈500→3000 + 15%止损 + 30分钟冷却)")
    print(f"{'='*120}")
    
    print(f"\n{'策略':<25} | {'止盈':>10} | {'全部交易':>8} | {'全部胜率':>8} | {'全部收益':>10} | {'近5月交易':>8} | {'近5月收益':>10}")
    print(f"{'-'*120}")
    
    for name in all_results:
        all_stats = all_results[name]["stats"]
        recent_stats = recent_results[name]["stats"]
        tp_config = STRATEGY_TP_CONFIG.get(name, STRATEGY_TP_CONFIG["default"])
        
        tp_str = f"{tp_config['tp_start']}→{tp_config['tp_max']}"
        all_trades = all_stats["total_trades"]
        all_win = all_stats["win_rate"]*100 if all_stats["total_trades"] > 0 else 0
        all_ret = all_stats["total_return_pct"]*100 if all_stats["total_trades"] > 0 else 0
        
        recent_trades = recent_stats["total_trades"]
        recent_ret = recent_stats["total_return_pct"]*100 if recent_stats["total_trades"] > 0 else 0
        
        if all_stats["total_trades"] > 0 or recent_stats["total_trades"] > 0:
            print(f"{name:<25} | {tp_str:>10} | {all_trades:>8} | {all_win:>7.1f}% | {all_ret:>+9.1f}% | {recent_trades:>8} | {recent_ret:>+9.1f}%")
    
    # 保存结果
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "leverage": config.leverage,
            "stop_loss_capital_pct": config.stop_loss_capital_pct,
            "position_pct": config.position_pct,
            "data_granularity": "5min",
            "data_range": f"{df['timestamp'].min()} ~ {df['timestamp'].max()}",
        },
        "all_history": {k: v["stats"] for k, v in all_results.items()},
        "recent_5months": {k: v["stats"] for k, v in recent_results.items()},
    }
    
    output_path = output_dir / "backtest_5min_personalized_tp.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n💾 结果已保存: {output_path}")
    print("\n✅ 回测完成！")


if __name__ == "__main__":
    main()
