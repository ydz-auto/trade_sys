"""
Execution Analytics - 执行分析

分析执行质量:
1. 执行统计
2. 滑点分析
3. 时间分析
4. 成本分析
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np

from domain.logging import get_logger

logger = get_logger("execution.analytics")


@dataclass
class ExecutionRecord:
    timestamp: datetime
    symbol: str
    side: str
    
    requested_size: float
    requested_price: float
    
    filled_size: float
    filled_price: float
    
    slippage_bps: float
    latency_ms: float
    fee: float


@dataclass
class ExecutionStats:
    total_orders: int
    total_volume: float
    
    fill_rate: float
    avg_fill_ratio: float
    
    avg_slippage_bps: float
    worst_slippage_bps: float
    
    avg_latency_ms: float
    p99_latency_ms: float
    
    total_fees: float
    total_slippage_cost: float
    
    execution_score: float


class ExecutionAnalytics:
    def __init__(self, history_size: int = 1000):
        self._history_size = history_size
        self._records: Dict[str, List[ExecutionRecord]] = {}
        
        logger.info("ExecutionAnalytics initialized")
    
    def record(
        self,
        symbol: str,
        side: str,
        requested_size: float,
        requested_price: float,
        filled_size: float,
        filled_price: float,
        latency_ms: float,
        fee: float,
    ) -> ExecutionRecord:
        timestamp = datetime.now()
        
        if requested_price > 0:
            slippage_pct = (filled_price - requested_price) / requested_price
            if side == "sell":
                slippage_pct = -slippage_pct
            slippage_bps = abs(slippage_pct) * 10000
        else:
            slippage_bps = 0.0
        
        record = ExecutionRecord(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            requested_size=requested_size,
            requested_price=requested_price,
            filled_size=filled_size,
            filled_price=filled_price,
            slippage_bps=slippage_bps,
            latency_ms=latency_ms,
            fee=fee,
        )
        
        if symbol not in self._records:
            self._records[symbol] = []
        
        self._records[symbol].append(record)
        
        if len(self._records[symbol]) > self._history_size:
            self._records[symbol] = self._records[symbol][-self._history_size:]
        
        return record
    
    def get_stats(
        self,
        symbol: str,
        period_hours: Optional[float] = None,
    ) -> ExecutionStats:
        records = self._records.get(symbol, [])
        
        if period_hours:
            cutoff = datetime.now() - timedelta(hours=period_hours)
            records = [r for r in records if r.timestamp >= cutoff]
        
        if not records:
            return self._empty_stats()
        
        total_orders = len(records)
        total_volume = sum(r.filled_size * r.filled_price for r in records)
        
        fill_ratios = [
            r.filled_size / r.requested_size
            for r in records if r.requested_size > 0
        ]
        avg_fill_ratio = np.mean(fill_ratios) if fill_ratios else 0.0
        fill_rate = sum(1 for r in fill_ratios if r >= 0.99) / total_orders
        
        slippages = [r.slippage_bps for r in records]
        avg_slippage = np.mean(slippages)
        worst_slippage = max(slippages)
        
        latencies = [r.latency_ms for r in records]
        avg_latency = np.mean(latencies)
        p99_latency = np.percentile(latencies, 99) if len(latencies) >= 100 else max(latencies)
        
        total_fees = sum(r.fee for r in records)
        total_slippage_cost = sum(
            r.slippage_bps / 10000 * r.filled_size * r.filled_price
            for r in records
        )
        
        execution_score = self._calculate_score(
            fill_rate, avg_slippage, avg_latency
        )
        
        return ExecutionStats(
            total_orders=total_orders,
            total_volume=total_volume,
            fill_rate=fill_rate,
            avg_fill_ratio=avg_fill_ratio,
            avg_slippage_bps=avg_slippage,
            worst_slippage_bps=worst_slippage,
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
            total_fees=total_fees,
            total_slippage_cost=total_slippage_cost,
            execution_score=execution_score,
        )
    
    def _calculate_score(
        self,
        fill_rate: float,
        avg_slippage: float,
        avg_latency: float,
    ) -> float:
        score = 0.0
        
        score += fill_rate * 0.4
        
        if avg_slippage < 5:
            score += 0.3
        elif avg_slippage < 10:
            score += 0.2
        elif avg_slippage < 20:
            score += 0.1
        
        if avg_latency < 100:
            score += 0.3
        elif avg_latency < 200:
            score += 0.2
        elif avg_latency < 500:
            score += 0.1
        
        return score
    
    def _empty_stats(self) -> ExecutionStats:
        return ExecutionStats(
            total_orders=0,
            total_volume=0.0,
            fill_rate=0.0,
            avg_fill_ratio=0.0,
            avg_slippage_bps=0.0,
            worst_slippage_bps=0.0,
            avg_latency_ms=0.0,
            p99_latency_ms=0.0,
            total_fees=0.0,
            total_slippage_cost=0.0,
            execution_score=0.0,
        )
    
    def get_report(
        self,
        symbol: str,
        period_hours: float = 24.0,
    ) -> Dict[str, Any]:
        stats = self.get_stats(symbol, period_hours)
        
        return {
            "symbol": symbol,
            "period_hours": period_hours,
            "summary": {
                "total_orders": stats.total_orders,
                "total_volume": stats.total_volume,
                "fill_rate": f"{stats.fill_rate * 100:.1f}%",
                "avg_fill_ratio": f"{stats.avg_fill_ratio * 100:.1f}%",
            },
            "slippage": {
                "avg_bps": f"{stats.avg_slippage_bps:.2f}",
                "worst_bps": f"{stats.worst_slippage_bps:.2f}",
                "total_cost": stats.total_slippage_cost,
            },
            "latency": {
                "avg_ms": f"{stats.avg_latency_ms:.1f}",
                "p99_ms": f"{stats.p99_latency_ms:.1f}",
            },
            "costs": {
                "total_fees": stats.total_fees,
                "total_slippage": stats.total_slippage_cost,
                "total_cost": stats.total_fees + stats.total_slippage_cost,
            },
            "score": {
                "value": f"{stats.execution_score:.2f}",
                "rating": self._get_rating(stats.execution_score),
            },
        }
    
    def _get_rating(self, score: float) -> str:
        if score >= 0.9:
            return "Excellent"
        elif score >= 0.7:
            return "Good"
        elif score >= 0.5:
            return "Fair"
        else:
            return "Poor"
