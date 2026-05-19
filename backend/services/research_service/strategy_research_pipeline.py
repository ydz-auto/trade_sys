#!/usr/bin/env python3
"""
Step 5-6: 完整策略研究矩阵 Pipeline

整合所有模块：
1. Feature Engine → Feature Matrix
2. Event Detection → Event Table
3. Context Engine → Context Tags
4. Outcome Engine → Outcome Table
5. Playbook Database → Playbook

支持：
- 分层回测
- 50倍合约模拟
- 完整报告生成
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import json

from infrastructure.logging import get_logger

from services.research_service.context_engine import ContextEngine
from services.research_service.outcome_engine import OutcomeEngine, OutcomeStats

logger = get_logger("strategy_research_pipeline")


@dataclass
class PlaybookAction:
    """Playbook操作步骤"""
    phase: str
    action: str
    condition: str
    risk_management: str


@dataclass
class PlaybookTemplate:
    """Playbook模板"""
    playbook_id: str
    event_type: str
    context_filter: Dict[str, str]
    
    direction: int
    holding_period: str
    
    entry_conditions: List[str]
    exit_conditions: List[str]
    stop_loss: float
    
    stats: Optional[OutcomeStats] = None
    
    leverage: float = 1.0
    position_size: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "event_type": self.event_type,
            "context_filter": self.context_filter,
            "direction": "long" if self.direction > 0 else "short",
            "holding_period": self.holding_period,
            "entry_conditions": self.entry_conditions,
            "exit_conditions": self.exit_conditions,
            "stop_loss": f"{self.stop_loss*100:.1f}%",
            "leverage": self.leverage,
            "position_size": f"{self.position_size*100:.0f}%",
            "stats": self.stats.to_dict() if self.stats else {},
        }


@dataclass
class BacktestResult:
    """回测结果"""
    playbook_id: str
    initial_capital: float
    final_capital: float
    
    total_trades: int
    winning_trades: int
    losing_trades: int
    
    win_rate: float
    avg_win: float
    avg_loss: float
    
    max_drawdown: float
    max_drawdown_pct: float
    
    sharpe_ratio: float
    
    pnl_by_leverage: float = 0.0
    
    liquidation_count: int = 0
    
    equity_curve: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": f"{(self.final_capital / self.initial_capital - 1) * 100:.2f}%",
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "liquidation_count": self.liquidation_count,
            "win_rate": f"{self.win_rate * 100:.1f}%",
            "avg_win": f"{self.avg_win:.2f}",
            "avg_loss": f"{self.avg_loss:.2f}",
            "max_drawdown": f"${self.max_drawdown:.2f}",
            "max_drawdown_pct": f"{self.max_drawdown_pct * 100:.1f}%",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "pnl_50x_leverage": f"${self.pnl_by_leverage:.2f}",
        }


class StrategyResearchPipeline:
    """
    完整策略研究矩阵 Pipeline
    
    执行顺序：
    1. Feature Engine → Feature Matrix
    2. Event Detection → Event Table
    3. Context Engine → Context Tags
    4. Outcome Engine → Outcome Table
    5. Playbook Database → Playbook
    6. Event Study Backtest → 回测报告
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        
        self.context_engine = ContextEngine()
        self.outcome_engine = OutcomeEngine()
        
        self.events: List[Dict] = []
        self.outcomes: List = []
        self.playbooks: Dict[str, PlaybookTemplate] = {}
        
        logger.info("StrategyResearchPipeline initialized")
    
    def _default_config(self) -> Dict:
        return {
            "leverage": 50,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.03,
            "position_size": 0.1,
            "commission_rate": 0.0004,
            "funding_cost_rate": 0.0003,
        }
    
    def run_full_pipeline(
        self,
        df: pd.DataFrame,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        运行完整Pipeline
        
        Args:
            df: 特征数据
            symbols: 交易对列表
            
        Returns:
            完整研究结果
        """
        logger.info(f"Starting full pipeline with {len(df)} rows")
        
        df = self._prepare_data(df)
        
        self._detect_events(df)
        
        self._compute_outcomes(df)
        
        self._generate_playbooks()
        
        result = self._compile_results()
        
        logger.info(f"Pipeline complete: {len(self.events)} events, {len(self.playbooks)} playbooks")
        
        return result
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备数据"""
        df = df.copy()
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        df = self.context_engine.add_context_to_dataframe(df)
        
        return df
    
    def _detect_events(self, df: pd.DataFrame):
        """检测事件"""
        self.events = []
        
        for i, row in df.iterrows():
            if i < 60:
                continue
            
            self.events.extend(self._detect_volume_climax(df, i, row))
            self.events.extend(self._detect_liquidation_cascade(df, i, row))
            self.events.extend(self._detect_panic_reversal(df, i, row))
            self.events.extend(self._detect_fake_breakout(df, i, row))
            self.events.extend(self._detect_trend_exhaustion(df, i, row))
            self.events.extend(self._detect_funding_trap(df, i, row))
            self.events.extend(self._detect_oi_divergence(df, i, row))
            self.events.extend(self._detect_long_liquidation(df, i, row))
            self.events.extend(self._detect_session_short(df, i, row))
        
        logger.info(f"Detected {len(self.events)} events")
    
    def _detect_volume_climax(self, df, i, row) -> List[Dict]:
        """检测Volume Climax"""
        events = []
        
        volume_ratio = row.get("volume_ratio", 1)
        returns_5m = row.get("returns_5m", 0)
        
        if volume_ratio > 2.5 and abs(returns_5m) > 0.01:
            direction = 1 if returns_5m > 0 else -1
            
            events.append({
                "event_id": f"volume_climax_{i}",
                "event_type": "volume_climax",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": -direction,
                "strength": abs(returns_5m),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "volume_ratio": volume_ratio,
                    "returns_5m": returns_5m,
                    "funding_rate": row.get("funding_rate", 0),
                    "oi_change": row.get("oi_change_1h", 0),
                }
            })
        
        return events
    
    def _detect_liquidation_cascade(self, df, i, row) -> List[Dict]:
        """检测Liquidation Cascade"""
        events = []
        
        volume_ratio = row.get("volume_ratio", 1)
        returns_5m = row.get("returns_5m", 0)
        
        if volume_ratio > 3.0 and returns_5m < -0.02:
            events.append({
                "event_id": f"liquidation_cascade_{i}",
                "event_type": "liquidation_cascade",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": 1,
                "strength": abs(returns_5m),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "volume_ratio": volume_ratio,
                    "returns_5m": returns_5m,
                    "funding_rate": row.get("funding_rate", 0),
                }
            })
        
        return events
    
    def _detect_panic_reversal(self, df, i, row) -> List[Dict]:
        """检测Panic Reversal"""
        events = []
        
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        
        if returns_1h < -0.015 and volume_ratio > 1.5:
            events.append({
                "event_id": f"panic_reversal_{i}",
                "event_type": "panic_reversal",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": 1,
                "strength": abs(returns_1h),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "returns_1h": returns_1h,
                    "volume_ratio": volume_ratio,
                    "session": row.get("session", "unknown"),
                }
            })
        
        return events
    
    def _detect_oi_divergence(self, df, i, row) -> List[Dict]:
        """
        OI Divergence - 做空
        价格涨但OI降 → 多头被清理 → 做空机会
        """
        events = []
        
        returns_1h = row.get("returns_1h", 0)
        oi_change = row.get("oi_change_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        
        if returns_1h > 0.01 and oi_change < -0.02:
            events.append({
                "event_id": f"oi_divergence_{i}",
                "event_type": "oi_divergence",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": -1,
                "strength": abs(oi_change),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "returns_1h": returns_1h,
                    "oi_change": oi_change,
                    "volume_ratio": volume_ratio,
                }
            })
        
        return events
    
    def _detect_long_liquidation(self, df, i, row) -> List[Dict]:
        """
        Long Liquidation - 连续爆多 → 下跌延续
        """
        events = []
        
        returns_5m = row.get("returns_5m", 0)
        volume_ratio = row.get("volume_ratio", 1)
        returns_1h = row.get("returns_1h", 0)
        
        if returns_5m < -0.01 and volume_ratio > 2.5:
            events.append({
                "event_id": f"long_liquidation_{i}",
                "event_type": "long_liquidation",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": -1,
                "strength": abs(returns_5m),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "returns_5m": returns_5m,
                    "returns_1h": returns_1h,
                    "volume_ratio": volume_ratio,
                }
            })
        
        return events
    
    def _detect_session_short(self, df, i, row) -> List[Dict]:
        """
        Session Short - 亚洲盘低流动性假突破后做空
        """
        events = []
        
        session = row.get("session", "")
        volume_ratio = row.get("volume_ratio", 1)
        returns_1h = row.get("returns_1h", 0)
        
        if session == "session_asia" and volume_ratio < 0.7 and returns_1h > 0.015:
            events.append({
                "event_id": f"session_short_{i}",
                "event_type": "session_short",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": -1,
                "strength": abs(returns_1h),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "session": session,
                    "volume_ratio": volume_ratio,
                    "returns_1h": returns_1h,
                }
            })
        
        return events
    
    def _detect_trend_exhaustion(self, df, i, row) -> List[Dict]:
        """检测趋势衰竭 - 做空"""
        events = []
        
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        funding = row.get("funding_rate", 0)
        
        if returns_1h > 0.02 and volume_ratio > 1.8:
            events.append({
                "event_id": f"trend_exhaustion_{i}",
                "event_type": "trend_exhaustion",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": -1,
                "strength": abs(returns_1h),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "returns_1h": returns_1h,
                    "volume_ratio": volume_ratio,
                    "funding_rate": funding,
                }
            })
        
        return events
    
    def _detect_funding_trap(self, df, i, row) -> List[Dict]:
        """检测Funding Trap - 做空"""
        events = []
        
        funding = row.get("funding_rate", 0)
        volume_ratio = row.get("volume_ratio", 1)
        
        if funding > 0.0005 and volume_ratio > 2.0:
            events.append({
                "event_id": f"funding_trap_{i}",
                "event_type": "funding_trap",
                "timestamp": row["timestamp"],
                "price": row["close"],
                "direction": -1,
                "strength": abs(funding),
                "context_tags": row.get("context_tags", ""),
                "features": {
                    "funding_rate": funding,
                    "volume_ratio": volume_ratio,
                }
            })
        
        return events
    
    def _detect_fake_breakout(self, df, i, row) -> List[Dict]:
        """检测Fake Breakout"""
        events = []
        
        if i < 65:
            return events
        
        rolling_high = df["high"].iloc[max(0, i-24):i].max()
        rolling_low = df["low"].iloc[max(0, i-24):i].min()
        
        breakout_up = row["high"] > rolling_high * 1.01
        
        if i + 3 < len(df):
            future_low = df["low"].iloc[i+1:i+4].min()
            
            if breakout_up and future_low < rolling_high:
                events.append({
                    "event_id": f"fake_breakout_{i}",
                    "event_type": "fake_breakout",
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "strength": (row["high"] - rolling_high) / rolling_high,
                    "context_tags": row.get("context_tags", ""),
                    "features": {
                        "breakout_strength": (row["high"] - rolling_high) / rolling_high,
                        "volume_ratio": row.get("volume_ratio", 1),
                    }
                })
        
        return events
    
    def _compute_outcomes(self, df: pd.DataFrame):
        """计算结果"""
        price_data = df[["timestamp", "close", "high", "low", "volume"]].copy()
        
        self.outcomes = self.outcome_engine.compute_outcomes(
            self.events, 
            price_data,
            leverage=1.0
        )
        
        logger.info(f"Computed {len(self.outcomes)} outcomes")
    
    def _generate_playbooks(self):
        """生成Playbook"""
        direction_map = {
            "panic_reversal": 1,
            "liquidation_cascade": 1,
            "volume_climax": -1,
            "fake_breakout": -1,
            "trend_exhaustion": -1,
            "funding_trap": -1,
            "oi_divergence": -1,
            "long_liquidation": -1,
            "session_short": -1,
        }
        
        events_by_type: Dict[str, List] = {}
        for event in self.events:
            et = event["event_type"]
            if et not in events_by_type:
                events_by_type[et] = []
            events_by_type[et].append(event)
        
        for event_type, type_events in events_by_type.items():
            if not type_events:
                continue
            
            outcomes_by_id = {o.event_id: o for o in self.outcomes}
            type_outcomes = [
                outcomes_by_id[e["event_id"]] 
                for e in type_events 
                if e["event_id"] in outcomes_by_id
            ]
            
            if not type_outcomes:
                continue
            
            overall_stats = self.outcome_engine.aggregate_stats(
                type_outcomes,
                event_type,
                "all"
            )
            
            fixed_direction = direction_map.get(event_type, 1)
            
            playbook = PlaybookTemplate(
                playbook_id=f"playbook_{event_type}",
                event_type=event_type,
                context_filter={},
                direction=fixed_direction,
                holding_period=overall_stats.best_exit_window,
                entry_conditions=[f"event_type = {event_type}"],
                exit_conditions=[f"exit after {overall_stats.best_exit_window}"],
                stop_loss=self.config["stop_loss_pct"],
                stats=overall_stats,
            )
            
            self.playbooks[event_type] = playbook
            
            for ctx_key in ["session", "funding_context", "regime"]:
                ctx_stats = self.outcome_engine.compute_context_stats(
                    type_events,
                    type_outcomes,
                    ctx_key
                )
                
                for ctx_value, stats in ctx_stats.items():
                    if stats.count >= 5:
                        ctx_playbook = PlaybookTemplate(
                            playbook_id=f"playbook_{event_type}_{ctx_key}_{ctx_value}",
                            event_type=event_type,
                            context_filter={ctx_key: ctx_value},
                            direction=fixed_direction,
                            holding_period=stats.best_exit_window,
                            entry_conditions=[f"event_type = {event_type}", f"{ctx_key} = {ctx_value}"],
                            exit_conditions=[f"exit after {stats.best_exit_window}"],
                            stop_loss=self.config["stop_loss_pct"],
                            stats=stats,
                        )
                        self.playbooks[f"{event_type}_{ctx_key}_{ctx_value}"] = ctx_playbook
    
    def run_backtest(
        self,
        playbook: PlaybookTemplate,
        df: pd.DataFrame,
        leverage: float = 1.0,
        initial_capital: float = 10000
    ) -> BacktestResult:
        """
        运行回测
        
        50倍杠杆特点：
        - 止损距离 = 1/50 = 2%
        - 每次交易用固定比例资金 (position_size)
        - 保证金 = 仓位价值 / leverage
        """
        events = [
            e for e in self.events 
            if e["event_type"] == playbook.event_type
        ]
        
        for key, value in playbook.context_filter.items():
            events = [
                e for e in events 
                if key in e.get("context_tags", "") and value in e.get("context_tags", "")
            ]
        
        outcomes_by_id = {o.event_id: o for o in self.outcomes}
        
        equity = initial_capital
        equity_curve = [equity]
        
        trades = []
        max_drawdown = 0
        peak = equity
        
        liquidation_count = 0
        winning_trades_count = 0
        losing_trades_count = 0
        
        position_size = self.config["position_size"]
        stop_loss_distance = 1.0 / leverage
        
        for event in events:
            outcome = outcomes_by_id.get(event["event_id"])
            if not outcome:
                continue
            
            if equity <= 0:
                break
            
            position_value = equity * position_size
            
            returns_1h = outcome.future_ret_1h
            direction = playbook.direction
            
            position_pnl = position_value * returns_1h * direction
            
            funding_cost = position_value * self.config["funding_cost_rate"] * 1
            position_pnl -= funding_cost
            
            was_liquidated = False
            if returns_1h * direction < -stop_loss_distance:
                position_pnl = -position_value * stop_loss_distance
                was_liquidated = True
                liquidation_count += 1
            
            equity += position_pnl
            
            if equity < 100:
                break
            
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            if position_pnl > 0:
                winning_trades_count += 1
            else:
                losing_trades_count += 1
            
            trades.append({
                "entry_price": event["price"],
                "position_pnl": position_pnl,
                "position_pnl_pct": position_pnl / position_value,
                "equity_after": equity,
                "liquidated": was_liquidated,
            })
            
            equity_curve.append(equity)
        
        returns = [t["position_pnl_pct"] for t in trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0
        
        return BacktestResult(
            playbook_id=playbook.playbook_id,
            initial_capital=initial_capital,
            final_capital=equity,
            total_trades=len(trades),
            winning_trades=winning_trades_count,
            losing_trades=losing_trades_count,
            win_rate=winning_trades_count / len(trades) if trades else 0,
            avg_win=np.mean([t["position_pnl"] for t in trades if t["position_pnl"] > 0]) if winning_trades_count else 0,
            avg_loss=np.mean([t["position_pnl"] for t in trades if t["position_pnl"] <= 0]) if losing_trades_count else 0,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown / peak if peak > 0 else 0,
            sharpe_ratio=sharpe,
            pnl_by_leverage=equity - initial_capital,
            liquidation_count=liquidation_count,
            equity_curve=equity_curve,
        )
    
    def run_all_backtests(
        self,
        df: pd.DataFrame,
        leverage: float = 50,
        initial_capital: float = 10000
    ) -> Dict[str, BacktestResult]:
        """运行所有Playbook回测"""
        results = {}
        
        for playbook_id, playbook in self.playbooks.items():
            logger.info(f"Backtesting: {playbook_id}")
            
            result = self.run_backtest(
                playbook, 
                df, 
                leverage=leverage,
                initial_capital=initial_capital
            )
            results[playbook_id] = result
        
        return results
    
    def _compile_results(self) -> Dict[str, Any]:
        """编译结果"""
        return {
            "total_events": len(self.events),
            "events_by_type": {
                et: len([e for e in self.events if e["event_type"] == et])
                for et in set(e["event_type"] for e in self.events)
            },
            "playbooks": {
                pid: pb.to_dict()
                for pid, pb in self.playbooks.items()
            },
        }
    
    def print_report(self, backtest_results: Dict[str, BacktestResult]):
        """打印回测报告"""
        print("\n" + "="*100)
        print("📊 策略研究矩阵 - 50倍合约回测报告")
        print("="*100)
        
        print(f"\n{'Playbook':<40} {'样本':<6} {'胜率':<8} {'盈亏':<10} {'50x收益':<12} {'爆仓':<6} {'最大回撤':<10}")
        print("-"*100)
        
        for playbook_id, result in sorted(
            backtest_results.items(), 
            key=lambda x: -x[1].pnl_by_leverage
        ):
            win_loss = result.winning_trades - result.losing_trades
            win_loss_str = f"+{win_loss}" if win_loss > 0 else str(win_loss)
            pnl_str = f"${result.pnl_by_leverage:+.2f}"
            
            print(f"{playbook_id:<40} {result.total_trades:<6} "
                  f"{result.win_rate*100:>5.1f}% "
                  f"{win_loss_str:>9} "
                  f"{pnl_str:>11} "
                  f"{result.liquidation_count:<6} "
                  f"{result.max_drawdown_pct*100:>7.1f}%")
        
        print("\n" + "="*100)
        print("✅ 回测完成！")
        print("="*100)
    
    def save_results(
        self, 
        backtest_results: Dict[str, BacktestResult],
        output_dir: Path
    ):
        """保存结果"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = output_dir / "backtest_results.json"
        with open(results_file, "w") as f:
            json.dump(
                {k: v.to_dict() for k, v in backtest_results.items()},
                f, indent=2, default=str
            )
        
        logger.info(f"Results saved to {results_file}")


def run_pipeline(df: pd.DataFrame) -> Dict[str, Any]:
    """运行完整Pipeline"""
    pipeline = StrategyResearchPipeline()
    
    result = pipeline.run_full_pipeline(df)
    
    return result


def run_pipeline_with_backtest(
    df: pd.DataFrame,
    leverage: float = 50
) -> Dict[str, BacktestResult]:
    """运行Pipeline + 回测"""
    pipeline = StrategyResearchPipeline()
    
    pipeline.run_full_pipeline(df)
    
    results = pipeline.run_all_backtests(df, leverage=leverage)
    
    pipeline.print_report(results)
    
    return results
