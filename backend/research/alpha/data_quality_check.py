"""
Data Quality Check - 数据质量检查

验证 kline 数据 + 信号结果的可靠性。
8 项检查: timestamp 连续性/重复、OHLC 合法性、收益极端值、volume 零值、
信号收益集中度、Top10 交易详情、趋势分析。

CLI:
  python -m research.alpha.data_quality_check \
    --symbol ZECUSDT --timeframe 1h --days 365 \
    --feature ret_5 --percentile 95 \
    --holding-bars 20 --taker-fee 0.0002
"""

import sys
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------- 检查函数 ----------

def check_timestamp_continuity(timestamps: pd.Series, timeframe: str) -> dict:
    """1. 检查 timestamp 是否连续。"""
    ts = pd.to_datetime(timestamps).sort_values().reset_index(drop=True)
    diffs = ts.diff().dropna()

    tf_map = {"5m": "5min", "15m": "15min", "30m": "30min",
              "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}
    expected = pd.Timedelta(tf_map.get(timeframe, "1h"))

    gaps = diffs[diffs > expected * 1.5]
    max_gap = diffs.max()

    print(f"\n[Check 1] Timestamp Continuity")
    print(f"  Total bars: {len(ts)}")
    print(f"  Expected interval: {expected}")
    print(f"  Max gap: {max_gap} (expected: {expected})")
    print(f"  Gaps (>1.5x expected): {len(gaps)}")

    if len(gaps) > 0:
        print(f"  Largest gaps:")
        for idx in gaps.nlargest(min(5, len(gaps))).index:
            print(f"    {ts.iloc[idx-1]} -> {ts.iloc[idx]}  gap={diffs.iloc[idx]}")

    return {"gap_count": len(gaps), "max_gap": max_gap}


def check_duplicate_timestamps(timestamps: pd.Series) -> dict:
    """2. 检查重复 timestamp。"""
    ts = pd.to_datetime(timestamps)
    dupes = ts[ts.duplicated()]

    print(f"\n[Check 2] Duplicate Timestamps")
    print(f"  Duplicates: {len(dupes)}")
    if len(dupes) > 0:
        print(f"  Examples: {dupes.head(5).tolist()}")

    return {"dupe_count": len(dupes)}


def check_ohlc_validity(df: pd.DataFrame) -> dict:
    """3. 检查 OHLC 合法性: low <= open/close <= high。"""
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    v_low_open = (df["low"] > df["open"]).sum()
    v_low_close = (df["low"] > df["close"]).sum()
    v_high_open = (df["high"] < df["open"]).sum()
    v_high_close = (df["high"] < df["close"]).sum()
    v_high_low = (df["high"] < df["low"]).sum()
    total = v_low_open + v_low_close + v_high_open + v_high_close + v_high_low

    print(f"\n[Check 3] OHLC Validity")
    print(f"  low > open:   {v_low_open}")
    print(f"  low > close:  {v_low_close}")
    print(f"  high < open:  {v_high_open}")
    print(f"  high < close: {v_high_close}")
    print(f"  high < low:   {v_high_low}")
    print(f"  Total violations: {total}")

    if total > 0:
        mask = ((df["low"] > df["open"]) | (df["low"] > df["close"]) |
                (df["high"] < df["open"]) | (df["high"] < df["close"]) |
                (df["high"] < df["low"]))
        bad = df.loc[mask].head(3)
        print(f"  Examples:")
        for _, row in bad.iterrows():
            print(f"    ts={row.get('timestamp', '?')} "
                  f"O={row['open']:.6f} H={row['high']:.6f} "
                  f"L={row['low']:.6f} C={row['close']:.6f}")

    return {"ohlc_violations": total}


def check_return_extremes(close: pd.Series) -> dict:
    """4. 检查 ret_1 极端值分布。"""
    ret = close.pct_change().dropna()

    print(f"\n[Check 4] Return Extremes (ret_1)")
    print(f"  Total returns: {len(ret)}")
    print(f"  mean={ret.mean():.6f}  std={ret.std():.6f}")
    print(f"  min={ret.min():.6f}   max={ret.max():.6f}")
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        print(f"  p{p}={ret.quantile(p/100):.6f}")

    # 极端值 (|ret| > 10%)
    extreme = ret[ret.abs() > 0.10]
    print(f"  |ret| > 10%: {len(extreme)} ({len(extreme)/len(ret)*100:.2f}%)")
    if len(extreme) > 0:
        print(f"  Extreme examples:")
        for idx in extreme.abs().nlargest(min(5, len(extreme))).index:
            print(f"    idx={idx}  ret={extreme[idx]:.4f}")

    return {"extreme_count": len(extreme), "ret_std": ret.std()}


def check_volume_zeros(volume: pd.Series) -> dict:
    """5. 检查 volume 零值比例。"""
    zero_count = (volume == 0).sum()
    zero_pct = zero_count / len(volume)
    nan_count = volume.isna().sum()

    print(f"\n[Check 5] Volume Zeros")
    print(f"  Total bars: {len(volume)}")
    print(f"  Zero volume: {zero_count} ({zero_pct*100:.2f}%)")
    print(f"  NaN volume: {nan_count}")

    if zero_pct > 0.01:
        # 零值分布位置
        vol_arr = volume.values
        zero_idx = np.where(vol_arr == 0)[0]
        if len(zero_idx) > 0:
            print(f"  Zero volume range: idx {zero_idx[0]} ~ {zero_idx[-1]}")

    return {"volume_zero_pct": zero_pct, "volume_zero_count": zero_count}


def check_signal_concentration(
    close: np.ndarray,
    feature_vals: np.ndarray,
    timestamps: pd.Series,
    percentile: int,
    holding_bars: int,
    taker_fee: float,
) -> dict:
    """6+7. P95 信号收益集中度 + Top10 详情。"""
    valid_mask = ~np.isnan(feature_vals)
    feat_valid = feature_vals[valid_mask]

    if len(feat_valid) == 0:
        print(f"\n[Check 6+7] Signal Concentration: NO VALID FEATURES")
        return {"top10_pct": np.nan}

    threshold = np.percentile(feat_valid, percentile)
    neg_threshold = np.percentile(feat_valid, 100 - percentile)

    n = len(close)
    max_exit = n - holding_bars

    # LONG: feature < -threshold
    signal_mask = valid_mask & (feature_vals < neg_threshold)
    valid_idx = np.where(signal_mask[:max_exit])[0]

    if len(valid_idx) == 0:
        print(f"\n[Check 6+7] Signal Concentration: NO SIGNALS")
        return {"top10_pct": np.nan}

    entry_prices = close[valid_idx]
    exit_prices = close[valid_idx + holding_bars]
    raw_ret = (exit_prices - entry_prices) / entry_prices
    fee = 2.0 * taker_fee
    rets = raw_ret - fee

    total_pnl = rets.sum()
    n_trades = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]

    # Top10 最大盈利
    top_n = min(10, n_trades)
    sorted_idx = np.argsort(rets)[::-1]
    top10_idx = sorted_idx[:top_n]
    top10_pnl = rets[top10_idx].sum()
    top10_pct = top10_pnl / total_pnl if total_pnl != 0 else np.nan

    # Bottom10 最大亏损
    bot10_idx = sorted_idx[-top_n:]
    bot10_pnl = rets[bot10_idx].sum()

    print(f"\n[Check 6] Signal Concentration (LONG p{100-percentile})")
    print(f"  Threshold: feature < {neg_threshold:.6f}")
    print(f"  Total trades: {n_trades}")
    print(f"  Total PnL: {total_pnl:.4f}")
    print(f"  Wins: {len(wins)}  Losses: {len(losses)}")
    print(f"  Avg win: {wins.mean():.4f}  Avg loss: {losses.mean():.4f}" if len(losses) > 0 else "")
    print(f"  Top{top_n} PnL: {top10_pnl:.4f} ({top10_pct*100:.1f}% of total)")
    print(f"  Bot{top_n} PnL: {bot10_pnl:.4f}")

    verdict = "STABLE" if (top10_pct is not np.nan and top10_pct < 0.50) else "UNSTABLE"
    print(f"  Verdict: {verdict} (Top{top_n} {'<' if verdict == 'STABLE' else '>='} 50% of PnL)")

    # Top10 详情
    print(f"\n[Check 7] Top{top_n} Trades Detail")
    print(f"  {'rank':>4} {'timestamp':>20} {'entry':>12} {'exit':>12} "
          f"{'raw_ret':>10} {'net_ret':>10} {'feat_val':>10}")
    print(f"  {'-'*80}")

    ts_arr = pd.to_datetime(timestamps).values
    for rank, idx in enumerate(top10_idx, 1):
        bar_idx = valid_idx[idx]
        ts_str = str(ts_arr[bar_idx])[:19]
        print(f"  {rank:>4} {ts_str:>20} {entry_prices[idx]:>12.4f} "
              f"{exit_prices[idx]:>12.4f} {raw_ret[idx]:>10.4f} "
              f"{rets[idx]:>10.4f} {feature_vals[bar_idx]:>10.4f}")

    return {"top10_pct": top10_pct, "total_trades": n_trades, "total_pnl": total_pnl}


def check_trend_regime(fm: pd.DataFrame, feature_name: str, percentile: int) -> dict:
    """8. 趋势分析: 是否单边牛市 dip-buying。"""
    close = fm["close"].values
    n = len(close)

    # 全周期收益
    total_return = (close[-1] / close[0]) - 1

    # 分段收益 (4 段)
    quarter = n // 4
    q_returns = []
    for i in range(4):
        start = i * quarter
        end = min((i + 1) * quarter - 1, n - 1)
        q_ret = (close[end] / close[start]) - 1
        q_returns.append(q_ret)

    # trend_20 分析
    trend = fm["trend_20"].dropna()
    positive_pct = (trend > 0).mean() if len(trend) > 0 else np.nan

    # 信号触发时的 trend_20 分布
    feat = fm[feature_name].values
    neg_threshold = np.nanpercentile(feat, 100 - percentile)
    valid_mask = ~np.isnan(feat) & (feat < neg_threshold)

    signal_trend = fm.loc[valid_mask, "trend_20"].dropna()
    signal_positive = (signal_trend > 0).mean() if len(signal_trend) > 0 else np.nan
    signal_mean_trend = signal_trend.mean() if len(signal_trend) > 0 else np.nan

    # ret_5 mean (正均值 = 上涨趋势)
    ret5_mean = fm["ret_5"].mean()

    print(f"\n[Check 8] Trend Regime Analysis")
    print(f"  Period: {close[0]:.2f} -> {close[-1]:.2f}")
    print(f"  Total return: {total_return*100:.1f}%")
    print(f"  Quarterly returns: {[f'{r*100:.1f}%' for r in q_returns]}")
    print(f"  ret_5 mean: {ret5_mean:.6f} ({'uptrend' if ret5_mean > 0 else 'downtrend'})")
    print(f"  trend_20 > 0 ratio (all): {positive_pct*100:.1f}%")
    print(f"  trend_20 > 0 ratio (signal): {signal_positive*100:.1f}%" if signal_positive is not np.nan else "")
    print(f"  trend_20 mean (signal): {signal_mean_trend:.4f}" if signal_mean_trend is not np.nan else "")

    # 判定
    is_bull = total_return > 1.0 and positive_pct > 0.70
    is_dip_buying = signal_positive is not np.nan and signal_positive > 0.60

    if is_bull and is_dip_buying:
        verdict = "BULL MARKET DIP-BUYING (not general mean reversion)"
    elif is_bull:
        verdict = "STRONG UPTREND (signal may be regime-specific)"
    elif is_dip_buying:
        verdict = "SIGNAL BIASED TO UPTREND PERIODS"
    else:
        verdict = "OK (not pure bull-market artifact)"

    print(f"  Verdict: {verdict}")

    return {
        "total_return": total_return,
        "trend_positive_pct": positive_pct,
        "signal_trend_positive": signal_positive,
        "ret5_mean": ret5_mean,
    }


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description="Data Quality Check - 数据质量检查")
    parser.add_argument("--symbol", type=str, default="ZECUSDT")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--feature", type=str, default="ret_5")
    parser.add_argument("--percentile", type=int, default=95,
                        help="信号百分位 (默认: 95)")
    parser.add_argument("--holding-bars", type=int, default=20)
    parser.add_argument("--taker-fee", type=float, default=0.0002)

    args = parser.parse_args()

    print(f"Data Quality Check: {args.symbol} | {args.exchange} | {args.timeframe} | {args.days}d")
    print(f"  feature={args.feature}  percentile=p{args.percentile}  "
          f"hold={args.holding_bars}  fee={args.taker_fee}")
    print("=" * 70)

    # 加载数据
    print("\nLoading feature matrix...")
    from research.alpha.feature_matrix import build_feature_matrix
    fm = build_feature_matrix(
        symbol=args.symbol,
        exchange=args.exchange,
        days=args.days,
        timeframe=args.timeframe,
    )
    print(f"  {len(fm)} bars, {len(fm.columns)} columns")

    if args.feature not in fm.columns:
        print(f"ERROR: feature '{args.feature}' not found. Available: {list(fm.columns)}")
        sys.exit(1)

    # 执行 8 项检查
    results = {}

    r1 = check_timestamp_continuity(fm["timestamp"], args.timeframe)
    results.update(r1)

    r2 = check_duplicate_timestamps(fm["timestamp"])
    results.update(r2)

    r3 = check_ohlc_validity(fm)
    results.update(r3)

    r4 = check_return_extremes(fm["close"])
    results.update(r4)

    r5 = check_volume_zeros(fm["volume"])
    results.update(r5)

    r67 = check_signal_concentration(
        close=fm["close"].values.astype(float),
        feature_vals=fm[args.feature].values.astype(float),
        timestamps=fm["timestamp"],
        percentile=args.percentile,
        holding_bars=args.holding_bars,
        taker_fee=args.taker_fee,
    )
    results.update(r67)

    r8 = check_trend_regime(fm, args.feature, args.percentile)
    results.update(r8)

    # 综合判定
    print(f"\n{'='*70}")
    print(f"VERDICT SUMMARY")
    print(f"{'='*70}")

    issues = []
    if results.get("gap_count", 0) > 10:
        issues.append(f"TIMESTAMP GAPS ({results['gap_count']})")
    if results.get("dupe_count", 0) > 0:
        issues.append(f"DUPLICATE TIMESTAMPS ({results['dupe_count']})")
    if results.get("ohlc_violations", 0) > 0:
        issues.append(f"OHLC VIOLATIONS ({results['ohlc_violations']})")
    if results.get("volume_zero_pct", 0) > 0.05:
        issues.append(f"HIGH ZERO VOLUME ({results['volume_zero_pct']*100:.1f}%)")

    top10 = results.get("top10_pct")
    if top10 is not None and not np.isnan(top10) and top10 > 0.50:
        issues.append(f"PnL CONCENTRATION (Top10 = {top10*100:.1f}%)")

    total_ret = results.get("total_return", 0)
    trend_pos = results.get("trend_positive_pct", 0)
    sig_trend = results.get("signal_trend_positive")
    if total_ret > 1.0 and trend_pos > 0.70:
        issues.append(f"BULL MARKET (return={total_ret*100:.0f}%, trend>0 {trend_pos*100:.0f}%)")
    if sig_trend is not None and not np.isnan(sig_trend) and sig_trend > 0.60:
        issues.append(f"SIGNAL IN UPTREND ({sig_trend*100:.0f}% of signals when trend>0)")

    if len(issues) == 0:
        print(f"\nPASS: {args.symbol} data quality OK - alpha appears credible")
    else:
        print(f"\nFAIL: {len(issues)} issue(s) detected:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print(f"\nAlpha may NOT be reliable. Investigate before proceeding.")

    print(f"{'='*70}")


if __name__ == "__main__":
    main()
