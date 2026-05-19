#!/usr/bin/env python3
"""
Step 4: Outcome Engine - 事件结果统计引擎

功能：
- 统计事件后市场表现
- 计算未来收益
- 统计延续/反转概率
- 计算最大回撤/最大涨幅

Output: Outcome Table
- event_id
- future_ret_5m/15m/1h/2h/4h
- max_drawdown
- max_runup
- continuation_prob
- reversal_prob
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import timedelta
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("outcome_engine")


@dataclass
class OutcomeMetrics:
    """事件结果指标"""
    event_id: str
    
    future_ret_5m: float = 0.0
    future_ret_15m: float = 0.0
    future_ret_30m: float = 0.0
    future_ret_1h: float = 0.0
    future_ret_2h: float = 0.0
    future_ret_4h: float = 0.0
    
    max_runup: float = 0.0
    max_drawdown: float = 0.0
    time_to_peak: int = 0
    time_to_trough: int = 0
    
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0
    
    volume_after: float = 0.0
    volatility_after: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "future_ret_5m": self.future_ret_5m,
            "future_ret_15m": self.future_ret_15m,
            "future_ret_30m": self.future_ret_30m,
            "future_ret_1h": self.future_ret_1h,
            "future_ret_2h": self.future_ret_2h,
            "future_ret_4h": self.future_ret_4h,
            "max_runup": self.max_runup,
            "max_drawdown": self.max_drawdown,
            "time_to_peak": self.time_to_peak,
            "time_to_trough": self.time_to_trough,
            "continuation_prob": self.continuation_prob,
            "reversal_prob": self.reversal_prob,
            "volume_after": self.volume_after,
            "volatility_after": self.volatility_after,
        }


@dataclass
class OutcomeStats:
    """Outcome统计汇总"""
    event_type: str
    context_filter: str
    
    count: int = 0
    
    avg_return_5m: float = 0.0
    avg_return_15m: float = 0.0
    avg_return_1h: float = 0.0
    avg_return_2h: float = 0.0
    avg_return_4h: float = 0.0
    
    positive_rate_5m: float = 0.0
    positive_rate_15m: float = 0.0
    positive_rate_1h: float = 0.0
    
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0
    
    avg_max_runup: float = 0.0
    avg_max_drawdown: float = 0.0
    
    best_entry_delay: str = "immediate"
    best_exit_window: str = "1h"
    
    sharpe_like: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "context_filter": self.context_filter,
            "count": self.count,
            "avg_return_5m": self.avg_return_5m,
            "avg_return_15m": self.avg_return_15m,
            "avg_return_1h": self.avg_return_1h,
            "avg_return_2h": self.avg_return_2h,
            "avg_return_4h": self.avg_return_4h,
            "positive_rate_5m": self.positive_rate_5m,
            "positive_rate_15m": self.positive_rate_15m,
            "positive_rate_1h": self.positive_rate_1h,
            "continuation_prob": self.continuation_prob,
            "reversal_prob": self.reversal_prob,
            "avg_max_runup": self.avg_max_runup,
            "avg_max_drawdown": self.avg_max_drawdown,
            "best_entry_delay": self.best_entry_delay,
            "best_exit_window": self.best_exit_window,
            "sharpe_like": self.sharpe_like,
        }


class OutcomeEngine:
    """
    Outcome Engine - 事件结果统计引擎
    
    功能：
    1. 给事件计算后续市场表现
    2. 按Context分组统计
    3. 生成Outcome Table
    """
    
    def __init__(self):
        self.look_forward_windows = {
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
        }
        logger.info("OutcomeEngine initialized")
    
    def compute_outcomes(
        self,
        events: List[Dict],
        price_data: pd.DataFrame,
        leverage: float = 1.0
    ) -> List[OutcomeMetrics]:
        """
        计算所有事件的结果
        
        Args:
            events: 事件列表，每个包含 timestamp, price, event_type, direction
            price_data: 价格数据（timestamp, close, high, low, volume）
            leverage: 合约杠杆倍数
            
        Returns:
            Outcome列表
        """
        outcomes = []
        
        price_data = price_data.set_index("timestamp").sort_index()
        
        for event in events:
            outcome = self._compute_single_outcome(event, price_data, leverage)
            outcomes.append(outcome)
        
        return outcomes
    
    def _compute_single_outcome(
        self,
        event: Dict,
        price_data: pd.DataFrame,
        leverage: float
    ) -> OutcomeMetrics:
        """计算单个事件的结果"""
        event_id = event.get("event_id", "unknown")
        entry_time = event["timestamp"]
        entry_price = event["price"]
        direction = event.get("direction", 1)
        
        outcome = OutcomeMetrics(event_id=event_id)
        
        price_data_after = price_data[price_data.index > entry_time]
        
        max_price = entry_price
        min_price = entry_price
        time_to_peak = 0
        time_to_trough = 0
        
        current_idx = 0
        for window_name, bars in self.look_forward_windows.items():
            future_data = price_data_after.iloc[min(current_idx + bars, len(price_data_after) - 1):min(current_idx + bars + 5, len(price_data_after))]
            
            if len(future_data) == 0:
                continue
            
            future_price = future_data["close"].iloc[-1]
            future_ret = ((future_price - entry_price) / entry_price) * direction * leverage
            
            if window_name == "5m":
                outcome.future_ret_5m = future_ret
            elif window_name == "15m":
                outcome.future_ret_15m = future_ret
            elif window_name == "30m":
                outcome.future_ret_30m = future_ret
            elif window_name == "1h":
                outcome.future_ret_1h = future_ret
            elif window_name == "2h":
                outcome.future_ret_2h = future_ret
            elif window_name == "4h":
                outcome.future_ret_4h = future_ret
            
            future_max = future_data["high"].max() if "high" in future_data.columns else future_price
            future_min = future_data["low"].min() if "low" in future_data.columns else future_price
            
            if direction > 0:
                runup = (future_max - entry_price) / entry_price
                drawdown = (entry_price - future_min) / entry_price
            else:
                runup = (entry_price - future_min) / entry_price
                drawdown = (future_max - entry_price) / entry_price
            
            if runup > outcome.max_runup:
                outcome.max_runup = runup
                outcome.time_to_peak = window_name
            
            if drawdown > outcome.max_drawdown:
                outcome.max_drawdown = drawdown
                outcome.time_to_trough = window_name
            
            current_idx += bars
        
        if "volume" in price_data_after.columns and len(price_data_after) > 0:
            outcome.volume_after = price_data_after["volume"].mean()
        
        if len(price_data_after) > 0:
            returns_after = price_data_after["close"].pct_change().dropna()
            if len(returns_after) > 0:
                outcome.volatility_after = returns_after.std()
        
        if direction > 0:
            outcome.continuation_prob = 1.0 if outcome.future_ret_5m > 0 else 0.0
            outcome.reversal_prob = 1.0 if outcome.future_ret_5m < 0 else 0.0
        else:
            outcome.continuation_prob = 1.0 if outcome.future_ret_5m < 0 else 0.0
            outcome.reversal_prob = 1.0 if outcome.future_ret_5m > 0 else 0.0
        
        return outcome
    
    def aggregate_stats(
        self,
        outcomes: List[OutcomeMetrics],
        event_type: str,
        context_filter: str = "all"
    ) -> OutcomeStats:
        """
        聚合统计结果
        
        Args:
            outcomes: Outcome列表
            event_type: 事件类型
            context_filter: Context过滤条件
            
        Returns:
            统计汇总
        """
        stats = OutcomeStats(
            event_type=event_type,
            context_filter=context_filter,
            count=len(outcomes)
        )
        
        if not outcomes:
            return stats
        
        returns_5m = [o.future_ret_5m for o in outcomes if o.future_ret_5m != 0]
        returns_15m = [o.future_ret_15m for o in outcomes if o.future_ret_15m != 0]
        returns_1h = [o.future_ret_1h for o in outcomes if o.future_ret_1h != 0]
        returns_2h = [o.future_ret_2h for o in outcomes if o.future_ret_2h != 0]
        returns_4h = [o.future_ret_4h for o in outcomes if o.future_ret_4h != 0]
        
        if returns_5m:
            stats.avg_return_5m = np.mean(returns_5m)
            stats.positive_rate_5m = np.mean([r > 0 for r in returns_5m])
        
        if returns_15m:
            stats.avg_return_15m = np.mean(returns_15m)
            stats.positive_rate_15m = np.mean([r > 0 for r in returns_15m])
        
        if returns_1h:
            stats.avg_return_1h = np.mean(returns_1h)
            stats.positive_rate_1h = np.mean([r > 0 for r in returns_1h])
        
        if returns_2h:
            stats.avg_return_2h = np.mean(returns_2h)
        
        if returns_4h:
            stats.avg_return_4h = np.mean(returns_4h)
        
        runups = [o.max_runup for o in outcomes]
        drawdowns = [o.max_drawdown for o in outcomes]
        continuations = [o.continuation_prob for o in outcomes]
        reversals = [o.reversal_prob for o in outcomes]
        
        stats.avg_max_runup = np.mean(runups)
        stats.avg_max_drawdown = np.mean(drawdowns)
        stats.continuation_prob = np.mean(continuations)
        stats.reversal_prob = np.mean(reversals)
        
        if stats.positive_rate_1h > stats.positive_rate_5m:
            stats.best_entry_delay = "immediate"
            stats.best_exit_window = "1h"
        else:
            stats.best_entry_delay = "wait_15m"
            stats.best_exit_window = "15m"
        
        if stats.avg_max_drawdown > 0:
            stats.sharpe_like = stats.avg_return_1h / stats.avg_max_drawdown
        
        return stats
    
    def compute_context_stats(
        self,
        events: List[Dict],
        outcomes: List[OutcomeMetrics],
        context_key: str
    ) -> Dict[str, OutcomeStats]:
        """按Context分组统计"""
        stats_by_context = {}
        
        outcomes_by_id = {o.event_id: o for o in outcomes}
        
        events_by_context: Dict[str, List] = {}
        for event in events:
            ctx = event.get("context_tags", "")
            ctx_parts = ctx.split("|") if ctx else []
            
            for part in ctx_parts:
                if context_key in part:
                    ctx_value = part.replace(f"{context_key}_", "")
                    if ctx_value not in events_by_context:
                        events_by_context[ctx_value] = []
                    events_by_context[ctx_value].append(event)
        
        for ctx_value, ctx_events in events_by_context.items():
            ctx_outcomes = [
                outcomes_by_id[e["event_id"]] 
                for e in ctx_events 
                if e["event_id"] in outcomes_by_id
            ]
            
            if ctx_outcomes:
                event_type = ctx_events[0].get("event_type", "unknown") if ctx_events else "unknown"
                stats = self.aggregate_stats(
                    ctx_outcomes, 
                    event_type, 
                    f"{context_key}={ctx_value}"
                )
                stats_by_context[ctx_value] = stats
        
        return stats_by_context
    
    def create_outcome_table(
        self,
        events: List[Dict],
        outcomes: List[OutcomeMetrics]
    ) -> pd.DataFrame:
        """
        创建Outcome Table
        
        Returns:
            DataFrame with columns:
            - event_id
            - future_ret_5m, future_ret_15m, future_ret_1h, future_ret_2h, future_ret_4h
            - max_runup, max_drawdown
            - continuation_prob, reversal_prob
        """
        event_outcome_map = {o.event_id: o for o in outcomes}
        
        rows = []
        for event in events:
            outcome = event_outcome_map.get(event["event_id"])
            if outcome:
                row = outcome.to_dict()
                row["event_type"] = event.get("event_type", "unknown")
                row["context_tags"] = event.get("context_tags", "")
                rows.append(row)
        
        return pd.DataFrame(rows)
    
    def get_outcome_summary(
        self,
        outcome_table: pd.DataFrame
    ) -> Dict[str, Any]:
        """获取Outcome汇总"""
        return {
            "total_events": len(outcome_table),
            "avg_return_1h": outcome_table["future_ret_1h"].mean() if "future_ret_1h" in outcome_table.columns else 0,
            "positive_rate_1h": (outcome_table["future_ret_1h"] > 0).mean() if "future_ret_1h" in outcome_table.columns else 0,
            "avg_max_runup": outcome_table["max_runup"].mean() if "max_runup" in outcome_table.columns else 0,
            "avg_max_drawdown": outcome_table["max_drawdown"].mean() if "max_drawdown" in outcome_table.columns else 0,
        }
