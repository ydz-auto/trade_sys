#!/usr/bin/env python3
"""
带上下文过滤的综合策略回测 - 充分利用系统里的上下文体系
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

logger = get_logger("context_aware_backtest")


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
    trades: List[Dict] = field(default_factory=list)
    context_analysis: Dict = field(default_factory=dict)


class ContextAwareBacktester:
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.df: pd.DataFrame = None
        self.df_5m: pd.DataFrame = None
        self.results: Dict[str, StrategyResult] = {}
    
    def load_data(self) -> pd.DataFrame:
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
            "trend_direction_12h": "last",
            "trend_strength_12h": "last",
            "volatility_1h": "last",
            "oi_change_1h": "last",
        }
        
        available_cols = [c for c in agg_dict.keys() if c in self.df.columns]
        agg_dict_filtered = {k: v for k, v in agg_dict.items() if k in available_cols}
        
        self.df_5m = self.df.set_index("timestamp").resample("5min", origin="start").agg(agg_dict_filtered).ffill()
        self.df_5m = self.df_5m.dropna(subset=["close"]).reset_index()
        
        self._add_features()
        logger.info(f"Prepared 5m data: {len(self.df_5m)} rows")
    
    def _add_features(self):
        df = self.df_5m
        
        # 时间特征
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        def get_session(hour):
            if 0 <= hour < 8: return "asia"
            elif 8 <= hour < 16: return "europe"
            else: return "us"
        df["session"] = df["hour"].apply(get_session)
        
        # 成交量比率
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(288).mean().fillna(1)
        df["low_liquidity"] = df["volume_ratio"] < 0.7
        
        # Funding上下文
        df["high_funding"] = df["funding_rate"] > 0.0001
        df["low_funding"] = df["funding_rate"] < -0.0001
        
        # 收益率
        df["return_5m"] = df["close"].pct_change(1)
        df["return_15m"] = df["close"].pct_change(3)
        df["return_1h"] = df["close"].pct_change(12)
        
        # 布林带宽度
        if "bb_upper" in df.columns and "bb_lower" in df.columns:
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["bb_middle"] + 0.0001)
        
        self.df_5m = df
    
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
            # 保存上下文信息
            "context": {
                "regime": row.get("regime", "unknown"),
                "session": row.get("session", "unknown"),
                "is_weekend": row.get("is_weekend", False),
                "high_funding": row.get("high_funding", False),
                "low_funding": row.get("low_funding", False),
                "low_liquidity": row.get("low_liquidity", False),
                "volume_ratio": row.get("volume_ratio", 1),
            }
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
        
        # 上下文分析
        context_analysis = defaultdict(lambda: {"trades": 0, "win_rate": 0, "avg_return": 0})
        for t in trades:
            ctx = t.get("context", {})
            for ctx_key, ctx_val in ctx.items():
                key = f"{ctx_key}={ctx_val}"
                if ctx_val in [True, False, "ranging", "volatile", "asia", "europe", "us"]:
                    stats = context_analysis[key]
                    stats["trades"] += 1
                    stats["avg_return"] += t.get("pnl_pct", 0)
                    if t.get("pnl", 0) > 0:
                        stats["win_rate"] += 1
        
        for key in context_analysis:
            cnt = context_analysis[key]["trades"]
            if cnt > 0:
                context_analysis[key]["win_rate"] /= cnt
                context_analysis[key]["avg_return"] /= cnt
        
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
            trades=trades,
            context_analysis=dict(context_analysis)
        )
    
    def _run_fake_breakout(self):
        df = self.df_5m
        trades = []
        position = None
        
        for i in range(288, len(df)):
            row = df.iloc[i]
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 4:
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
                    trade = {**position, "exit_price": row["close"], "exit_time": row["timestamp"], 
                             "close_reason": close_reason, **pnl}
                    trades.append(trade)
                    position = None
            
            if not position:
                # Fake Breakout 检测
                if i >= 24:
                    rolling_high = df.iloc[i-24:i]["high"].max()
                    if row["high"] > rolling_high * 1.003:
                        # 检查上下文过滤 - 优化：只在特定上下文下交易
                        good_context = True
                        # 1. 避免在squeeze状态下做空
                        if row.get("state_squeeze", 0) > 0:
                            good_context = False
                        # 2. 低成交量环境更容易假突破
                        if row.get("volume_ratio", 1) < 1.2:
                            good_context = True
                        # 3. 震荡市场假突破更多
                        if row.get("regime", "") == "ranging":
                            good_context = True
                        
                        if good_context:
                            position = self._open_position(row, "short", "fake_breakout", 0.015, 0.025)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trade = {**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], 
                     "close_reason": "end_of_data", **pnl}
            trades.append(trade)
        
        return self._compile_result("Fake Breakout (Context Aware)", "Behavioral Playbook", "做空", trades)
    
    def _run_panic_reversal(self):
        df = self.df_5m
        trades = []
        position = None
        
        for i in range(288, len(df)):
            row = df.iloc[i]
            
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
                    trade = {**position, "exit_price": row["close"], "exit_time": row["timestamp"], 
                             "close_reason": close_reason, **pnl}
                    trades.append(trade)
                    position = None
            
            if not position:
                # Panic Reversal 检测 + 上下文过滤
                if row.get("return_1h", 0) < -0.015 and row.get("volume_ratio", 0) > 1.3:
                    # 上下文优化
                    good_context = True
                    # panic dump状态效果更好
                    if row.get("state_panic_dump", 0) > 0:
                        good_context = True
                    # 高波动率环境下反弹更好
                    if row.get("regime", "") == "volatile":
                        good_context = True
                    # 避免在趋势下跌时抄底
                    if row.get("trend_direction_12h", 0) < -0.5:
                        good_context = False
                    
                    if good_context:
                        position = self._open_position(row, "long", "panic_reversal", 0.03, 0.05)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trade = {**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], 
                     "close_reason": "end_of_data", **pnl}
            trades.append(trade)
        
        return self._compile_result("Panic Reversal (Context Aware)", "Behavioral Playbook", "做多", trades)
    
    def _run_leveraged_short_squeeze(self):
        df = self.df_5m
        trades = []
        position = None
        
        for i in range(288, len(df)):
            row = df.iloc[i]
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 2:
                    close_reason = "time_exit"
                elif row["high"] >= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif row["low"] <= position["take_profit_price"]:
                    close_reason = "take_profit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trade = {**position, "exit_price": row["close"], "exit_time": row["timestamp"], 
                             "close_reason": close_reason, **pnl}
                    trades.append(trade)
                    position = None
            
            if not position:
                # 检测 + 上下文过滤
                score = 0
                fz = row.get("funding_zscore", 0)
                if not pd.isna(fz) and fz > 1.5:
                    score += 3
                
                funding = row.get("funding_rate", 0)
                if not pd.isna(funding) and funding > 0.0003:
                    score += 2
                
                ret_1h = row.get("return_1h", 0)
                if ret_1h > 0.01:
                    score += 2
                
                vr = row.get("volume_ratio", 1)
                if vr > 2.5:
                    score += 2
                elif vr > 1.5:
                    score += 1
                
                # 上下文过滤
                good_context = True
                # state_squeeze状态更有效
                if row.get("state_squeeze", 0) > 0:
                    score += 2
                # 高funding + volatile regime
                if row.get("high_funding", False) and row.get("regime", "") == "volatile":
                    good_context = True
                # 避开低流动性时段
                if row.get("low_liquidity", False) and row.get("is_weekend", False):
                    good_context = False
                
                if score >= 5 and good_context:
                    position = self._open_position(row, "short", "leveraged_short_squeeze", 0.02, 0.015)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trade = {**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], 
                     "close_reason": "end_of_data", **pnl}
            trades.append(trade)
        
        return self._compile_result("Leveraged Short Squeeze (Context Aware)", "创新策略", "做空", trades)
    
    def _run_weak_bounce_short_v2(self):
        df = self.df_5m
        trades = []
        position = None
        
        for i in range(288, len(df)):
            row = df.iloc[i]
            
            if position:
                elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
                close_reason = None
                
                if elapsed >= 6:
                    close_reason = "time_exit"
                elif row["high"] >= position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif row["low"] <= position["take_profit_price"]:
                    close_reason = "take_profit"
                
                if close_reason:
                    pnl = self._calculate_pnl(position, row["close"], close_reason)
                    trade = {**position, "exit_price": row["close"], "exit_time": row["timestamp"], 
                             "close_reason": close_reason, **pnl}
                    trades.append(trade)
                    position = None
            
            if not position:
                if i >= 60:
                    close_4h_ago = df.iloc[i-48]["close"]
                    close_1h_ago = df.iloc[i-12]["close"]
                    
                    drop_4h_pct = (close_4h_ago - close_1h_ago) / close_4h_ago
                    bounce_pct = (row["close"] - close_1h_ago) / close_1h_ago
                    
                    if drop_4h_pct >= 0.02 and 0.003 <= bounce_pct <= 0.015 and row.get("volume_ratio", 0) >= 1.5:
                        # 上下文过滤
                        good_context = True
                        # 震荡市场弱反弹做空更好
                        if row.get("regime", "") == "ranging":
                            good_context = True
                        # US时段效果更好
                        if row.get("session", "") == "us":
                            good_context = True
                        # 避免周末低流动性
                        if row.get("is_weekend", False):
                            good_context = False
                        
                        if good_context:
                            position = self._open_position(row, "short", "weak_bounce_short_v2", 0.018, 0.025)
        
        if position:
            pnl = self._calculate_pnl(position, df.iloc[-1]["close"], "end_of_data")
            trade = {**position, "exit_price": df.iloc[-1]["close"], "exit_time": df.iloc[-1]["timestamp"], 
                     "close_reason": "end_of_data", **pnl}
            trades.append(trade)
        
        return self._compile_result("Weak Bounce Short V2 (Context Aware)", "优化做空策略", "做空", trades)
    
    def run_all_strategies(self):
        logger.info("Running Fake Breakout with context...")
        self.results["fake_breakout_context"] = self._run_fake_breakout()
        
        logger.info("Running Panic Reversal with context...")
        self.results["panic_reversal_context"] = self._run_panic_reversal()
        
        logger.info("Running Leveraged Short Squeeze with context...")
        self.results["leveraged_short_squeeze_context"] = self._run_leveraged_short_squeeze()
        
        logger.info("Running Weak Bounce Short V2 with context...")
        self.results["weak_bounce_short_context"] = self._run_weak_bounce_short_v2()
    
    def print_report(self):
        print("\n" + "=" * 120)
        print("📊 带上下文过滤的策略回测报告 - 全部数据 (2024-2026)")
        print("=" * 120)
        print(f"数据范围: {self.df_5m['timestamp'].min()} to {self.df_5m['timestamp'].max()}")
        print(f"初始资金: ${self.config.initial_capital:,.0f} | 杠杆: {self.config.leverage}x")
        
        print("\n" + "=" * 120)
        print("🏆 策略表现排序")
        print("=" * 120)
        print(f"{'策略名称':<40} | {'方向':<8} | {'交易数':>8} | {'胜率':>8} | {'收益率':>12} | {'最大回撤':>10} | {'夏普':>8}")
        print("-" * 120)
        
        sorted_results = sorted(self.results.items(), key=lambda x: -x[1].total_return)
        for key, r in sorted_results:
            if r.total_trades == 0:
                continue
            print(f"{r.name:<40} | {r.direction:<8} | {r.total_trades:>8} | {r.win_rate*100:>7.1f}% | "
                  f"{r.total_return_pct*100:>+11.2f}% | {r.max_drawdown*100:>9.2f}% | {r.sharpe:>8.2f}")
        
        print("\n" + "=" * 120)
        print("🔍 上下文优化分析 - 最佳上下文条件")
        print("=" * 120)
        
        for key, r in sorted_results:
            if not r.context_analysis or r.total_trades == 0:
                continue
            
            print(f"\n【{r.name}】")
            
            best_contexts = sorted(
                [(k, v) for k, v in r.context_analysis.items() if v["trades"] >= 5],
                key=lambda x: -x[1]["avg_return"]
            )
            
            if best_contexts:
                print(f"  Top 3 最佳上下文：")
                for ctx_name, ctx_stats in best_contexts[:3]:
                    print(f"    {ctx_name:<25} | 交易: {ctx_stats['trades']:>4} | "
                          f"胜率: {ctx_stats['win_rate']*100:>5.1f}% | 平均收益: {ctx_stats['avg_return']*100:>+6.2f}%")
        
        print("\n" + "=" * 120)
    
    def save_results(self):
        output_dir = get_research_path()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_data = {
            "backtest_info": {
                "timestamp": datetime.now().isoformat(),
                "data_range": f"{self.df_5m['timestamp'].min()} to {self.df_5m['timestamp'].max()}",
                "initial_capital": self.config.initial_capital,
                "leverage": self.config.leverage,
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
                    "sharpe": r.sharpe,
                    "context_analysis": r.context_analysis
                } for key, r in self.results.items()
            }
        }
        
        output_path = output_dir / "context_aware_backtest_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 结果已保存: {output_path}")


def main():
    print("🚀 带上下文过滤的综合策略回测")
    print()
    
    config = BacktestConfig(initial_capital=10000, leverage=50)
    
    tester = ContextAwareBacktester(config)
    
    df = tester.load_data()
    
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
