#!/usr/bin/env python3
"""
高杠杆波动捕获系统 - TOP 3 策略回测 (内存优化版)
===================================================

策略:
  1. Liquidation Cascade  - 爆仓级联（做多反弹）
  2. Short Squeeze        - 空头挤仓（做多追涨）
  3. Fake Breakout Trap   - 假突破陷阱（做空反杀）

核心参数:
  - 杠杆: 50x
  - 止损: 本金 10% (价格波动 0.2%)
  - 止盈: 移动止盈 500→3000 点
  - 仓位: 全仓复利 (每笔用当前总资金100%)
  - 数据: BTCUSDT 1分钟, 2024-01 ~ 2026-04

内存优化:
  - 用 numpy 数组代替 dict list
  - 特征直接从 DataFrame 列提取为 numpy 数组
  - 避免创建 Bar 对象
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple
import gc

import pandas as pd
import numpy as np


# ============================================================
# 回测配置
# ============================================================

@dataclass
class Config:
    initial_capital: float = 10000.0
    leverage: float = 50.0
    stop_loss_capital_pct: float = 0.10
    trailing_tp_start: float = 500.0
    trailing_tp_max: float = 3000.0
    trailing_tp_step: float = 500.0
    max_hold_hours: int = 48
    commission: float = 0.0005
    slippage: float = 0.0002
    cooldown_bars: int = 6


# ============================================================
# 特征提取器 (向量化)
# ============================================================

class FeatureExtractor:
    """从 DataFrame 提取 numpy 数组，避免逐行操作"""

    def __init__(self, df: pd.DataFrame):
        self.n = len(df)
        self.timestamps = df["timestamp"].values
        self.opens = df["open"].values.astype(np.float64)
        self.highs = df["high"].values.astype(np.float64)
        self.lows = df["low"].values.astype(np.float64)
        self.closes = df["close"].values.astype(np.float64)
        self.volumes = df["volume"].values.astype(np.float64)

        # volume_ratio
        if "volume_ratio" in df.columns:
            self.volume_ratio = df["volume_ratio"].fillna(1.0).values.astype(np.float64)
        else:
            vr = np.ones(self.n, dtype=np.float64)
            for i in range(288, self.n):
                avg_vol = np.mean(self.volumes[max(0, i-288):i])
                if avg_vol > 0:
                    vr[i] = self.volumes[i] / avg_vol
            self.volume_ratio = vr

        # returns_1h
        if "returns_1h" in df.columns:
            self.return_1h = df["returns_1h"].fillna(0.0).values.astype(np.float64)
        else:
            r1h = np.zeros(self.n, dtype=np.float64)
            for i in range(12, self.n):
                r1h[i] = (self.closes[i] - self.closes[i-12]) / self.closes[i-12]
            self.return_1h = r1h

        # return_5m
        if "returns_5m" in df.columns:
            self.return_5m = df["returns_5m"].fillna(0.0).values.astype(np.float64)
        elif "return_5m" in df.columns:
            self.return_5m = df["return_5m"].fillna(0.0).values.astype(np.float64)
        else:
            r5m = np.zeros(self.n, dtype=np.float64)
            for i in range(1, self.n):
                r5m[i] = (self.closes[i] - self.closes[i-1]) / self.closes[i-1]
            self.return_5m = r5m

        # funding_rate
        if "funding_rate" in df.columns:
            self.funding_rate = df["funding_rate"].fillna(0.0).values.astype(np.float64)
        else:
            self.funding_rate = np.zeros(self.n, dtype=np.float64)

        # funding_zscore
        if "funding_zscore" in df.columns:
            self.funding_zscore = df["funding_zscore"].fillna(0.0).values.astype(np.float64)
        else:
            self.funding_zscore = np.zeros(self.n, dtype=np.float64)

        # bool 特征
        bool_cols = {
            "volatility_surge": False,
            "spike_down": False,
            "state_panic_dump": False,
            "state_breakout": False,
            "trend_exhaustion": False,
            "spike_up": False,
        }
        for col, default in bool_cols.items():
            if col in df.columns:
                arr = df[col].fillna(default).values
                setattr(self, col, arr.astype(bool) if arr.dtype == object else arr.astype(bool))
            else:
                setattr(self, col, np.zeros(self.n, dtype=bool))

        # breakout_strength_24h
        if "breakout_strength_24h" in df.columns:
            self.breakout_strength_24h = df["breakout_strength_24h"].fillna(0.0).values.astype(np.float64)
        else:
            self.breakout_strength_24h = np.zeros(self.n, dtype=np.float64)


# ============================================================
# 策略检测器 (直接用 numpy 数组)
# ============================================================

def detect_liquidation_cascade(fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
    """爆仓级联 → 做多"""
    score = 0.0

    vr = fe.volume_ratio[i]
    if vr > 3.0:
        score += 3
    elif vr > 2.0:
        score += 2

    r1h = fe.return_1h[i]
    if r1h < -0.015:
        score += 2
    elif r1h < -0.01:
        score += 1

    if fe.funding_rate[i] > 0.0002:
        score += 1

    if fe.volatility_surge[i]:
        score += 1

    if fe.state_panic_dump[i]:
        score += 1

    if fe.spike_down[i]:
        score += 1

    return score >= 5, score


def detect_short_squeeze(fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
    """空头挤仓 → 做多"""
    score = 0.0

    fz = fe.funding_zscore[i]
    if fz > 1.5:
        score += 3
    elif fz > 1.0:
        score += 1

    fr = fe.funding_rate[i]
    if fr > 0.0003:
        score += 2
    elif fr > 0.0002:
        score += 1

    r1h = fe.return_1h[i]
    if r1h > 0.01:
        score += 2
    elif r1h > 0.005:
        score += 1

    vr = fe.volume_ratio[i]
    if vr > 2.5:
        score += 2
    elif vr > 1.5:
        score += 1

    if fe.volatility_surge[i]:
        score += 1

    if fe.state_breakout[i]:
        score += 1

    return score >= 5, score


def detect_fake_breakout_trap(fe: FeatureExtractor, i: int) -> Tuple[bool, float]:
    """假突破陷阱 → 做空"""
    score = 0.0

    bs = fe.breakout_strength_24h[i]
    if abs(bs) > 0.003:
        score += 2

    vr = fe.volume_ratio[i]
    if vr < 1.0:
        score += 2
    elif vr < 1.3:
        score += 1

    # 上影线比例
    h, l, c = fe.highs[i], fe.lows[i], fe.closes[i]
    candle_range = h - l
    if candle_range > 0:
        wick_ratio = (h - c) / candle_range
    else:
        wick_ratio = 0
    if wick_ratio > 0.6:
        score += 2
    elif wick_ratio > 0.4:
        score += 1

    if fe.return_5m[i] < -0.001:
        score += 1

    if fe.trend_exhaustion[i]:
        score += 1

    if fe.state_breakout[i]:
        score += 1

    return score >= 4, score


# ============================================================
# 回测引擎
# ============================================================

def run_backtest(
    fe: FeatureExtractor,
    config: Config,
    detect_func,
    strategy_name: str,
    direction: str,
) -> Tuple[List[Dict], Dict]:
    """
    运行回测

    移动止盈逻辑:
    1. 入场时: trailing_tp = 500 点
    2. 每根bar: 价格向有利方向每移动500点 → trailing_tp += 500点
    3. trailing_tp 上限 = 3000 点
    4. 价格回撤到 trailing_tp → 止盈平仓
    5. 止损始终在入场价 ± 0.2%
    """
    price_sl_pct = config.stop_loss_capital_pct / config.leverage
    n = fe.n
    trades = []
    capital = config.initial_capital
    initial_capital = config.initial_capital

    last_signal_bar = -999
    i = 288  # 预热期

    while i < n:
        # 信号冷却
        if i - last_signal_bar < config.cooldown_bars:
            i += 1
            continue

        # 检测信号
        triggered, score = detect_func(fe, i)
        if not triggered:
            i += 1
            continue

        last_signal_bar = i
        entry_price = fe.closes[i]
        entry_time = fe.timestamps[i]
        margin = capital

        # 止损价
        if direction == "long":
            sl_price = entry_price * (1 - price_sl_pct)
        else:
            sl_price = entry_price * (1 + price_sl_pct)

        # 移动止盈初始
        trailing_tp_points = config.trailing_tp_start
        if direction == "long":
            trailing_tp_price = entry_price + trailing_tp_points
        else:
            trailing_tp_price = entry_price - trailing_tp_points

        max_favorable = 0.0
        max_adverse = 0.0

        exit_price = None
        exit_reason = None
        j = i + 1
        max_bars = int(config.max_hold_hours * 60)  # 48h * 60 bars/h (1min)

        while j < n and (j - i) < max_bars:
            h = fe.highs[j]
            l = fe.lows[j]

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

            # 移动止盈更新
            new_tp_points = int(max_favorable / config.trailing_tp_step) * config.trailing_tp_step + config.trailing_tp_start
            new_tp_points = min(new_tp_points, config.trailing_tp_max)
            if new_tp_points > trailing_tp_points:
                trailing_tp_points = new_tp_points
                if direction == "long":
                    trailing_tp_price = entry_price + trailing_tp_points
                else:
                    trailing_tp_price = entry_price - trailing_tp_points

            # 检查止损
            if direction == "long":
                if l <= sl_price:
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
                if l <= trailing_tp_price:
                    exit_price = trailing_tp_price
                    exit_reason = "trailing_tp"
                    break
            else:
                if h >= sl_price:
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
                if h >= trailing_tp_price:
                    exit_price = trailing_tp_price
                    exit_reason = "trailing_tp"
                    break

            j += 1

        if exit_price is None:
            exit_price = fe.closes[min(j, n-1)]
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
        new_capital = margin + pnl

        trades.append({
            "entry_time": str(entry_time),
            "exit_time": str(fe.timestamps[j]),
            "entry_price": round(float(entry_price), 1),
            "exit_price": round(float(exit_price), 1),
            "pnl_pct": round(float(leveraged_pnl_pct), 4),
            "capital_before": round(float(capital), 2),
            "capital_after": round(float(new_capital), 2),
            "exit_reason": exit_reason,
            "hold_bars": int(j - i),
            "max_favorable": round(float(max_favorable), 1),
            "max_adverse": round(float(max_adverse), 1),
            "trailing_tp_hit": float(trailing_tp_points),
        })

        capital = new_capital

        if capital <= 0:
            print(f"   💀 资金归零于第 {len(trades)} 笔交易")
            break

        i = j + 1

    # 分析
    stats = analyze_trades(trades, initial_capital)
    return trades, stats


def analyze_trades(trades: List[Dict], initial_capital: float) -> Dict:
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "total_return_pct": 0, "max_drawdown_pct": 0,
            "avg_win_pct": 0, "avg_loss_pct": 0, "profit_factor": 0,
            "avg_hold_bars": 0, "avg_max_favorable": 0, "avg_max_adverse": 0,
            "sl_count": 0, "tp_count": 0, "time_count": 0,
            "initial_capital": initial_capital, "final_capital": initial_capital,
        }

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]

    # 最大回撤
    peak = trades[0]["capital_before"]
    max_dd = 0
    for t in trades:
        eq = t["capital_before"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    # 最后交易后
    final_eq = trades[-1]["capital_after"]
    if final_eq < peak:
        dd = (peak - final_eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    total_pnl = sum((t["capital_after"] - t["capital_before"]) for t in trades)
    final = trades[-1]["capital_after"]
    total_return_pct = (final - initial_capital) / initial_capital if initial_capital > 0 else 0

    total_wins = sum((t["capital_after"] - t["capital_before"]) for t in wins)
    total_losses = abs(sum((t["capital_after"] - t["capital_before"]) for t in losses))

    return {
        "total_trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd,
        "avg_win_pct": float(np.mean([t["pnl_pct"] for t in wins])) if wins else 0,
        "avg_loss_pct": float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0,
        "profit_factor": total_wins / total_losses if total_losses > 0 else 999,
        "avg_hold_bars": float(np.mean([t["hold_bars"] for t in trades])),
        "avg_max_favorable": float(np.mean([t["max_favorable"] for t in trades])),
        "avg_max_adverse": float(np.mean([t["max_adverse"] for t in trades])),
        "sl_count": sum(1 for t in trades if t["exit_reason"] == "stop_loss"),
        "tp_count": sum(1 for t in trades if t["exit_reason"] == "trailing_tp"),
        "time_count": sum(1 for t in trades if t["exit_reason"] == "time_exit"),
        "initial_capital": initial_capital,
        "final_capital": final,
    }


# ============================================================
# 报告
# ============================================================

def print_report(all_results: Dict, config: Config):
    print("\n" + "=" * 120)
    print("  高杠杆波动捕获系统 - TOP 3 策略回测报告")
    print("=" * 120)
    price_sl_pct = config.stop_loss_capital_pct / config.leverage
    print(f"  杠杆: {config.leverage}x | 止损: 本金{config.stop_loss_capital_pct*100:.0f}% (价格{price_sl_pct*100:.2f}%)")
    print(f"  止盈: 移动止盈 {config.trailing_tp_start:.0f}→{config.trailing_tp_max:.0f} 点 (步长{config.trailing_tp_step:.0f}点)")
    print(f"  仓位: 全仓复利 | 最大持仓: {config.max_hold_hours}h | 手续费: {config.commission*100:.3f}% | 滑点: {config.slippage*100:.3f}%")
    print("=" * 120)

    # 总览
    print(f"\n{'策略':<25} | {'交易数':>6} | {'胜率':>7} | {'总收益':>14} | {'收益率':>10} | {'最大回撤':>8} | {'盈亏比':>7} | {'止损':>5} | {'止盈':>5} | {'超时':>5}")
    print("-" * 120)

    for name, result in all_results.items():
        s = result["stats"]
        if s["total_trades"] == 0:
            print(f"{name:<25} | {'N/A':>6} | {'N/A':>7} | {'N/A':>14} | {'N/A':>10} | {'N/A':>8} | {'N/A':>7} | {'N/A':>5} | {'N/A':>5} | {'N/A':>5}")
            continue
        print(f"{name:<25} | {s['total_trades']:>6} | {s['win_rate']*100:>6.1f}% | "
              f"${s['total_pnl']:>12,.0f} | {s['total_return_pct']*100:>9.1f}% | "
              f"{s['max_drawdown_pct']*100:>7.1f}% | {s['profit_factor']:>7.2f} | "
              f"{s['sl_count']:>5} | {s['tp_count']:>5} | {s['time_count']:>5}")

    print("-" * 120)

    # 详细
    for name, result in all_results.items():
        s = result["stats"]

        if s["total_trades"] == 0:
            print(f"\n{'='*100}\n  【{name}】- 无交易触发\n{'='*100}")
            continue

        print(f"\n{'='*100}")
        print(f"  【{name}】")
        print(f"{'='*100}")

        print(f"\n  📊 基础指标:")
        print(f"     交易次数: {s['total_trades']}")
        print(f"     胜率: {s['win_rate']*100:.1f}%")
        print(f"     盈利笔均收益: {s['avg_win_pct']*100:+.2f}%")
        print(f"     亏损笔均亏损: {s['avg_loss_pct']*100:+.2f}%")
        print(f"     盈亏比: {s['profit_factor']:.2f}")
        print(f"     平均持仓: {s['avg_hold_bars']:.0f} bars ({s['avg_hold_bars']/60:.1f}h)")

        print(f"\n  💰 资金曲线:")
        print(f"     初始资金: ${s['initial_capital']:,.2f}")
        print(f"     最终资金: ${s['final_capital']:,.2f}")
        print(f"     总收益: ${s['total_pnl']:,.2f} ({s['total_return_pct']*100:+.1f}%)")
        print(f"     最大回撤: {s['max_drawdown_pct']*100:.1f}%")

        print(f"\n  📈 波动统计:")
        print(f"     平均最大有利波动: {s['avg_max_favorable']:.0f} 点")
        print(f"     平均最大不利波动: {s['avg_max_adverse']:.0f} 点")

        print(f"\n  🎯 退出分析:")
        print(f"     止损退出: {s['sl_count']}笔 ({s['sl_count']/s['total_trades']*100:.1f}%)")
        print(f"     移动止盈: {s['tp_count']}笔 ({s['tp_count']/s['total_trades']*100:.1f}%)")
        print(f"     超时退出: {s['time_count']}笔 ({s['time_count']/s['total_trades']*100:.1f}%)")

    # 综合排名
    print(f"\n{'='*100}")
    print(f"  🏆 综合排名")
    print(f"{'='*100}")

    ranked = sorted(
        [(name, r["stats"]) for name, r in all_results.items() if r["stats"]["total_trades"] > 0],
        key=lambda x: -x[1]["total_return_pct"]
    )

    for rank, (name, s) in enumerate(ranked, 1):
        emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉"
        print(f"\n  {emoji} #{rank} {name}")
        print(f"     收益: {s['total_return_pct']*100:+.1f}% | 胜率: {s['win_rate']*100:.1f}% | "
              f"盈亏比: {s['profit_factor']:.2f} | 回撤: {s['max_drawdown_pct']*100:.1f}%")

    print(f"\n{'='*120}")


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 120)
    print("  高杠杆波动捕获系统 - TOP 3 策略回测")
    print("  Liquidation Cascade | Short Squeeze | Fake Breakout Trap")
    print("=" * 120)

    config = Config()

    data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return

    print(f"\n📥 加载数据 (仅必要列)...")
    usecols = [
        "timestamp", "open", "high", "low", "close", "volume",
        "volume_ratio", "returns_1h", "returns_5m", "return_5m",
        "funding_rate", "funding_zscore",
        "volatility_surge", "spike_down", "spike_up",
        "state_panic_dump", "state_breakout", "trend_exhaustion",
        "breakout_strength_24h",
    ]
    # 只加载存在的列
    import pyarrow.parquet as pq
    schema = pq.read_schema(data_path)
    existing_cols = schema.names
    load_cols = [c for c in usecols if c in existing_cols]
    df = pd.read_parquet(data_path, columns=load_cols)
    print(f"   数据量: {len(df)} 行, {len(df.columns)} 列")
    print(f"   内存: {df.memory_usage(deep=True).sum() / 1024**2:.0f} MB")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 释放原始 DataFrame 引用，只保留 numpy 数组
    print(f"\n⏳ 提取特征 (向量化)...")
    fe = FeatureExtractor(df)
    del df
    gc.collect()
    print(f"   特征提取完成")

    strategies = [
        ("Liquidation Cascade", "long", detect_liquidation_cascade),
        ("Short Squeeze", "long", detect_short_squeeze),
        ("Fake Breakout Trap", "short", detect_fake_breakout_trap),
    ]

    all_results = {}
    all_trades = {}  # 分开存储，节省内存

    output_dir = backend_path / "data_lake/research"
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, direction, detect_func in strategies:
        print(f"\n{'='*100}")
        print(f"  ⏳ 回测: {name} ({direction})")
        print(f"{'='*100}")

        trades, stats = run_backtest(fe, config, detect_func, name, direction)
        all_results[name] = {"stats": stats}

        if stats["total_trades"] > 0:
            print(f"  ✅ 交易: {stats['total_trades']}笔 | 胜率: {stats['win_rate']*100:.1f}% | "
                  f"收益: {stats['total_return_pct']*100:+.1f}% | 回撤: {stats['max_drawdown_pct']*100:.1f}%")
            # 保存交易记录到临时文件
            tmp_path = output_dir / f"_tmp_{name.replace(' ', '_')}_trades.json"
            with open(tmp_path, "w") as f:
                json.dump(trades, f, ensure_ascii=False, default=str)
            all_trades[name] = str(tmp_path)
        else:
            print(f"  ⚠️ 无交易触发")

        del trades
        gc.collect()

    # 报告 (不需要 trades 列表，只需要 stats)
    print_report(all_results, config)

    # 保存
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "leverage": config.leverage,
            "stop_loss_capital_pct": config.stop_loss_capital_pct,
            "trailing_tp_start": config.trailing_tp_start,
            "trailing_tp_max": config.trailing_tp_max,
            "trailing_tp_step": config.trailing_tp_step,
            "max_hold_hours": config.max_hold_hours,
            "position_mode": "full_compound",
            "initial_capital": config.initial_capital,
        },
        "data_range": f"{fe.timestamps[0]} ~ {fe.timestamps[-1]}",
        "data_rows": fe.n,
    }

    for name, result in all_results.items():
        save_data[name] = {
            "stats": {k: (float(v) if isinstance(v, (np.integer, np.floating)) else v)
                      for k, v in result["stats"].items()},
        }
        if name in all_trades:
            save_data[name]["trades_file"] = all_trades[name]

    output_path = output_dir / "volatility_event_top3_backtest.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 结果已保存: {output_path}")
    print("\n✅ 回测完成！")


if __name__ == "__main__":
    main()
