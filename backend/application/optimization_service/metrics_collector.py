"""
Optimization Metrics Collector - 优化指标收集器

核心职责：
1. 收集回测过程中的指标
2. 计算综合评分
3. 生成优化报告
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("optimization_metrics_collector")


@dataclass
class TradeMetrics:
    """交易指标"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    avg_hold_hours: float = 0.0
    max_hold_hours: float = 0.0
    
    total_slippage: float = 0.0
    avg_slippage: float = 0.0
    
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0


@dataclass
class RiskMetrics:
    """风险指标"""
    max_drawdown: float = 0.0
    max_drawdown_duration_hours: float = 0.0
    
    volatility: float = 0.0
    downside_volatility: float = 0.0
    
    var_95: float = 0.0
    var_99: float = 0.0
    
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0


@dataclass
class ReturnMetrics:
    """收益指标"""
    total_return: float = 0.0
    annualized_return: float = 0.0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    alpha: float = 0.0
    beta: float = 0.0
    
    information_ratio: float = 0.0


@dataclass
class ExecutionMetrics:
    """执行指标"""
    total_commission: float = 0.0
    total_slippage_cost: float = 0.0
    
    fill_rate: float = 1.0
    partial_fill_count: int = 0
    
    avg_execution_latency_ms: float = 0.0
    
    stop_loss_count: int = 0
    take_profit_count: int = 0
    time_exit_count: int = 0


@dataclass
class OptimizationScore:
    """优化评分"""
    total_score: float = 0.0
    
    return_score: float = 0.0
    risk_score: float = 0.0
    consistency_score: float = 0.0
    execution_score: float = 0.0
    
    components: Dict[str, float] = field(default_factory=dict)


class OptimizationMetricsCollector:
    """
    优化指标收集器
    
    收集和计算回测指标，支持：
    1. 多维度指标计算
    2. 综合评分
    3. 风险调整收益
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.0,
        trading_days_per_year: int = 365,
    ):
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
    
    def calculate_all_metrics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[float],
        initial_capital: float = 10000.0,
    ) -> Dict[str, Any]:
        """计算所有指标"""
        trade_metrics = self._calculate_trade_metrics(trades)
        risk_metrics = self._calculate_risk_metrics(equity_curve)
        return_metrics = self._calculate_return_metrics(equity_curve, initial_capital)
        execution_metrics = self._calculate_execution_metrics(trades)
        
        return {
            "trade": trade_metrics,
            "risk": risk_metrics,
            "return": return_metrics,
            "execution": execution_metrics,
        }
    
    def _calculate_trade_metrics(self, trades: List[Dict[str, Any]]) -> TradeMetrics:
        """计算交易指标"""
        if not trades:
            return TradeMetrics()
        
        wins = [t for t in trades if t.get('pnl_pct', 0) > 0]
        losses = [t for t in trades if t.get('pnl_pct', 0) <= 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        total_pnl_pct = sum(t.get('pnl_pct', 0) for t in trades)
        
        win_pnls = [t.get('pnl_pct', 0) for t in wins]
        loss_pnls = [t.get('pnl_pct', 0) for t in losses]
        
        avg_win = np.mean(win_pnls) if win_pnls else 0
        avg_loss = np.mean(loss_pnls) if loss_pnls else 0
        
        max_win = max(win_pnls) if win_pnls else 0
        max_loss = min(loss_pnls) if loss_pnls else 0
        
        win_rate = len(wins) / len(trades) if trades else 0
        
        total_wins = sum(win_pnls)
        total_losses = abs(sum(loss_pnls))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        hold_hours = [t.get('hold_hours', 0) for t in trades if 'hold_hours' in t]
        avg_hold = np.mean(hold_hours) if hold_hours else 0
        max_hold = max(hold_hours) if hold_hours else 0
        
        slippages = [t.get('slippage', 0) for t in trades]
        latencies = [t.get('latency_ms', 0) for t in trades]
        
        return TradeMetrics(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_win=max_win,
            max_loss=max_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_hold_hours=avg_hold,
            max_hold_hours=max_hold,
            total_slippage=sum(slippages),
            avg_slippage=np.mean(slippages) if slippages else 0,
            total_latency_ms=sum(latencies),
            avg_latency_ms=np.mean(latencies) if latencies else 0,
        )
    
    def _calculate_risk_metrics(self, equity_curve: List[float]) -> RiskMetrics:
        """计算风险指标"""
        if len(equity_curve) < 2:
            return RiskMetrics()
        
        peak = equity_curve[0]
        max_dd = 0
        max_dd_duration = 0
        current_dd_start = None
        
        for i, eq in enumerate(equity_curve):
            if eq > peak:
                peak = eq
                if current_dd_start is not None:
                    dd_duration = i - current_dd_start
                    if dd_duration > max_dd_duration:
                        max_dd_duration = dd_duration
                    current_dd_start = None
            else:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
                if current_dd_start is None:
                    current_dd_start = i
        
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        volatility = np.std(returns) * np.sqrt(self.trading_days_per_year)
        
        negative_returns = returns[returns < 0]
        downside_vol = np.std(negative_returns) * np.sqrt(self.trading_days_per_year) if len(negative_returns) > 0 else 0
        
        var_95 = np.percentile(returns, 5) if len(returns) > 0 else 0
        var_99 = np.percentile(returns, 1) if len(returns) > 0 else 0
        
        return RiskMetrics(
            max_drawdown=max_dd,
            max_drawdown_duration_hours=max_dd_duration,
            volatility=volatility,
            downside_volatility=downside_vol,
            var_95=var_95,
            var_99=var_99,
        )
    
    def _calculate_return_metrics(
        self,
        equity_curve: List[float],
        initial_capital: float,
    ) -> ReturnMetrics:
        """计算收益指标"""
        if len(equity_curve) < 2:
            return ReturnMetrics()
        
        total_return = (equity_curve[-1] - initial_capital) / initial_capital
        
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        annualized_return = total_return * (self.trading_days_per_year / len(returns)) if len(returns) > 0 else 0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe = (avg_return - self.risk_free_rate / self.trading_days_per_year) / (std_return + 1e-10) * np.sqrt(self.trading_days_per_year) if std_return > 0 else 0
        
        negative_returns = returns[returns < 0]
        downside_std = np.std(negative_returns) if len(negative_returns) > 0 else std_return
        sortino = (avg_return - self.risk_free_rate / self.trading_days_per_year) / (downside_std + 1e-10) * np.sqrt(self.trading_days_per_year) if downside_std > 0 else 0
        
        peak = equity_curve[0]
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
        
        calmar = annualized_return / max_dd if max_dd > 0 else 0
        
        return ReturnMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
        )
    
    def _calculate_execution_metrics(self, trades: List[Dict[str, Any]]) -> ExecutionMetrics:
        """计算执行指标"""
        if not trades:
            return ExecutionMetrics()
        
        total_commission = sum(t.get('commission', 0) for t in trades)
        total_slippage = sum(t.get('slippage_cost', 0) for t in trades)
        
        stop_loss_count = sum(1 for t in trades if t.get('exit_reason') == 'stop_loss')
        take_profit_count = sum(1 for t in trades if t.get('exit_reason') == 'take_profit')
        time_exit_count = sum(1 for t in trades if t.get('exit_reason') == 'time')
        
        latencies = [t.get('latency_ms', 0) for t in trades]
        
        return ExecutionMetrics(
            total_commission=total_commission,
            total_slippage_cost=total_slippage,
            avg_execution_latency_ms=np.mean(latencies) if latencies else 0,
            stop_loss_count=stop_loss_count,
            take_profit_count=take_profit_count,
            time_exit_count=time_exit_count,
        )
    
    def calculate_score(
        self,
        metrics: Dict[str, Any],
        weights: Dict[str, float] = None,
    ) -> OptimizationScore:
        """计算综合评分"""
        default_weights = {
            "sharpe": 0.3,
            "total_return": 0.2,
            "win_rate": 0.15,
            "profit_factor": 0.15,
            "max_drawdown": 0.1,
            "calmar": 0.1,
        }
        
        weights = weights or default_weights
        
        return_metrics = metrics.get("return", {})
        trade_metrics = metrics.get("trade", {})
        risk_metrics = metrics.get("risk", {})
        
        sharpe = return_metrics.sharpe_ratio
        total_return = return_metrics.total_return
        win_rate = trade_metrics.win_rate
        profit_factor = trade_metrics.profit_factor
        max_dd = risk_metrics.max_drawdown
        calmar = return_metrics.calmar_ratio
        
        sharpe_score = min(max(sharpe / 3.0, 0), 1.0)
        return_score = min(max(total_return, -1), 1.0)
        win_rate_score = win_rate
        pf_score = min(profit_factor / 3.0, 1.0) if profit_factor > 0 else 0
        dd_score = max(1 - max_dd * 5, 0)
        calmar_score = min(max(calmar / 3.0, 0), 1.0)
        
        total_score = (
            weights["sharpe"] * sharpe_score +
            weights["total_return"] * return_score +
            weights["win_rate"] * win_rate_score +
            weights["profit_factor"] * pf_score +
            weights["max_drawdown"] * dd_score +
            weights["calmar"] * calmar_score
        )
        
        return OptimizationScore(
            total_score=total_score,
            return_score=return_score,
            risk_score=dd_score,
            consistency_score=win_rate_score,
            execution_score=pf_score,
            components={
                "sharpe": sharpe_score,
                "return": return_score,
                "win_rate": win_rate_score,
                "profit_factor": pf_score,
                "max_drawdown": dd_score,
                "calmar": calmar_score,
            },
        )
