"""
Simple Backtest - 简单回测工具

核心：验证交易规则能否盈利

规则：
- signal long  -> 开多
- signal short -> 开空
- 持有 N 根 bar 或反向 signal 平仓
- 扣手续费和滑点

核心指标：
- win_rate: 胜率
- avg_trade_return: 平均每笔收益
- max_drawdown: 最大回撤
- profit_factor: 盈利因子
- sharpe: 夏普比率
- trade_count: 交易次数

验证的是策略本身的 edge，不是参数调优。
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import pandas as pd
import numpy as np
import argparse

# 自动添加项目根目录到 sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engines.compute.strategy_v2 import StrategyV2, SignalType

try:
    from research.common.loaders import get_strategy_class, save_results_to_json
    from research.common.types import StrategyName
except ImportError:
    from common.loaders import get_strategy_class, save_results_to_json
    from common.types import StrategyName


@dataclass
class TradeResult:
    """单笔交易结果"""
    entry_time: int
    entry_price: float
    direction: str
    exit_time: int
    exit_price: float
    holding_bars: int
    pnl: float
    pnl_pct: float
    confidence: float
    reason: str


@dataclass
class BacktestResult:
    """回测结果"""
    
    strategy_name: str
    symbol: str
    
    total_trades: int
    long_trades: int
    short_trades: int
    
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    avg_trade_return: float
    median_trade_return: float
    avg_win: float
    avg_loss: float
    
    total_pnl: float
    total_pnl_pct: float
    
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    
    avg_holding_bars: float
    longest_trade: int
    shortest_trade: int
    
    fees_paid: float
    slippage_paid: float
    
    trade_details: List[TradeResult]
    
    def __repr__(self):
        return f"""BacktestResult ({self.strategy_name}):
  交易总数: {self.total_trades} (多:{self.long_trades}, 空:{self.short_trades})
  胜率: {self.win_rate:.2%}
  平均收益: {self.avg_trade_return:.4f} ({self.avg_trade_return * 100:.2f}%)
  总盈亏: {self.total_pnl:.2f} ({self.total_pnl_pct * 100:.2f}%)
  最大回撤: {self.max_drawdown:.4f}
  Sharpe: {self.sharpe_ratio:.2f}
  盈利因子: {self.profit_factor:.2f}
  手续费: {self.fees_paid:.2f}
  滑点: {self.slippage_paid:.2f}
"""


class SimpleBacktester:
    """
    简单回测器
    
    核心职责：
    1. 模拟交易执行（不考虑仓位管理）
    2. 计算交易级别的指标
    3. 扣费用和滑点
    """
    
    def __init__(
        self,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
        slippage_bps: float = 2.0,
        max_holding_bars: int = 10
    ):
        """
        Args:
            maker_fee: Maker 手续费率
            taker_fee: Taker 手续费率
            slippage_bps: 滑点（基点）
            max_holding_bars: 最大持仓 bar 数
        """
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage_bps = slippage_bps
        self.max_holding_bars = max_holding_bars
    
    def backtest(
        self,
        strategy: StrategyV2,
        market_contexts: List[Any],
        timestamps: List[int],
        prices: np.ndarray
    ) -> BacktestResult:
        """
        执行回测
        
        Args:
            strategy: 策略实例
            market_contexts: MarketContext 列表
            timestamps: 时间戳列表
            prices: 价格序列
        
        Returns:
            BacktestResult: 回测结果
        """
        if len(market_contexts) != len(timestamps) or len(timestamps) != len(prices):
            raise ValueError("数据长度不一致")
        
        trades: List[TradeResult] = []
        current_position = None
        
        for i, ctx in enumerate(market_contexts[:-1]):
            signal = strategy.generate_signal(ctx)
            
            price = prices[i]
            next_price = prices[i + 1]
            
            if current_position is None:
                if signal.type == SignalType.LONG:
                    entry_price = price * (1 + self.slippage_bps / 10000)
                    fee = entry_price * self.taker_fee
                    current_position = {
                        "direction": "long",
                        "entry_price": entry_price,
                        "entry_time": timestamps[i],
                        "entry_bar": i,
                        "confidence": signal.confidence,
                        "reason": signal.reason,
                        "fees": fee,
                        "slippage": entry_price - price
                    }
                elif signal.type == SignalType.SHORT:
                    entry_price = price * (1 - self.slippage_bps / 10000)
                    fee = entry_price * self.taker_fee
                    current_position = {
                        "direction": "short",
                        "entry_price": entry_price,
                        "entry_time": timestamps[i],
                        "entry_bar": i,
                        "confidence": signal.confidence,
                        "reason": signal.reason,
                        "fees": fee,
                        "slippage": price - entry_price
                    }
            
            elif current_position is not None:
                holding_bars = i - current_position["entry_bar"]
                
                should_close = False
                close_reason = "max_holding"
                
                if current_position["direction"] == "long":
                    if signal.type == SignalType.SHORT:
                        should_close = True
                        close_reason = "reverse_signal"
                    elif holding_bars >= self.max_holding_bars:
                        should_close = True
                        close_reason = "max_holding"
                
                elif current_position["direction"] == "short":
                    if signal.type == SignalType.LONG:
                        should_close = True
                        close_reason = "reverse_signal"
                    elif holding_bars >= self.max_holding_bars:
                        should_close = True
                        close_reason = "max_holding"
                
                if should_close:
                    if current_position["direction"] == "long":
                        exit_price = next_price * (1 - self.slippage_bps / 10000)
                        fee = exit_price * self.taker_fee
                        pnl = (exit_price - current_position["entry_price"]) * (1 - self.taker_fee) - current_position["fees"]
                        pnl_pct = pnl / current_position["entry_price"]
                    else:
                        exit_price = next_price * (1 + self.slippage_bps / 10000)
                        fee = exit_price * self.taker_fee
                        pnl = (current_position["entry_price"] - exit_price) * (1 - self.taker_fee) - current_position["fees"]
                        pnl_pct = pnl / current_position["entry_price"]
                    
                    trades.append(TradeResult(
                        entry_time=current_position["entry_time"],
                        entry_price=current_position["entry_price"],
                        direction=current_position["direction"],
                        exit_time=timestamps[i + 1],
                        exit_price=exit_price,
                        holding_bars=holding_bars,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        confidence=current_position["confidence"],
                        reason=f"{current_position['reason']}->{close_reason}"
                    ))
                    
                    current_position = None
        
        return self._compute_results(strategy, trades)
    
    def _compute_results(
        self,
        strategy: StrategyV2,
        trades: List[TradeResult]
    ) -> BacktestResult:
        """计算回测统计"""
        if not trades:
            return BacktestResult(
                strategy_name=strategy.meta.name,
                symbol=strategy.symbol,
                total_trades=0,
                long_trades=0,
                short_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                avg_trade_return=0,
                median_trade_return=0,
                avg_win=0,
                avg_loss=0,
                total_pnl=0,
                total_pnl_pct=0,
                max_drawdown=0,
                sharpe_ratio=0,
                profit_factor=0,
                avg_holding_bars=0,
                longest_trade=0,
                shortest_trade=0,
                fees_paid=0,
                slippage_paid=0,
                trade_details=trades
            )
        
        pnls = [t.pnl_pct for t in trades]
        
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        
        total_pnl = sum(pnls)
        avg_trade_return = np.mean(pnls)
        median_trade_return = np.median(pnls)
        
        avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl_pct for t in losing_trades]) if losing_trades else 0
        
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        max_drawdown = np.min(cumulative - running_max)
        
        if np.std(pnls) > 0:
            sharpe_ratio = np.mean(pnls) / np.std(pnls) * np.sqrt(len(pnls))
        else:
            sharpe_ratio = 0
        
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        fees_paid = sum(t.pnl_pct * 0.001 for t in trades) * 0.5
        slippage_paid = sum(t.pnl_pct * 0.0002 for t in trades) * 0.5
        
        holding_bars = [t.holding_bars for t in trades]
        
        return BacktestResult(
            strategy_name=strategy.meta.name,
            symbol=strategy.symbol,
            total_trades=len(trades),
            long_trades=len(long_trades),
            short_trades=len(short_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(trades),
            avg_trade_return=avg_trade_return,
            median_trade_return=median_trade_return,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_holding_bars=np.mean(holding_bars),
            longest_trade=max(holding_bars),
            shortest_trade=min(holding_bars),
            fees_paid=fees_paid,
            slippage_paid=slippage_paid,
            trade_details=trades
        )
    
    def get_trades_df(self, trades: List[TradeResult]) -> pd.DataFrame:
        """获取交易记录 DataFrame"""
        if not trades:
            return pd.DataFrame()
        
        data = [{
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "holding_bars": t.holding_bars,
            "confidence": t.confidence,
            "reason": t.reason,
        } for t in trades]
        
        return pd.DataFrame(data)


def run_simple_backtest(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage_bps: float = 2.0,
    max_holding_bars: int = 10
) -> BacktestResult:
    """
    运行简单回测
    
    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        maker_fee: Maker 手续费率
        taker_fee: Taker 手续费率
        slippage_bps: 滑点（基点）
        max_holding_bars: 最大持仓 bar 数
    
    Returns:
        BacktestResult: 回测结果
    """
    backtester = SimpleBacktester(
        maker_fee=maker_fee,
        taker_fee=taker_fee,
        slippage_bps=slippage_bps,
        max_holding_bars=max_holding_bars
    )
    
    return backtester.backtest(strategy, market_contexts, timestamps, prices)


def compare_strategy_backtests(
    strategies: List[StrategyV2],
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray
) -> pd.DataFrame:
    """
    比较多个策略的回测结果
    
    Args:
        strategies: 策略列表
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = []
    
    for strategy in strategies:
        try:
            result = run_simple_backtest(strategy, market_contexts, timestamps, prices)
            results.append({
                "strategy": result.strategy_name,
                "symbol": result.symbol,
                "total_trades": result.total_trades,
                "long_trades": result.long_trades,
                "short_trades": result.short_trades,
                "win_rate": result.win_rate,
                "avg_trade_return": result.avg_trade_return,
                "median_trade_return": result.median_trade_return,
                "total_pnl": result.total_pnl,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "profit_factor": result.profit_factor,
                "avg_holding_bars": result.avg_holding_bars,
            })
        except Exception as e:
            results.append({
                "strategy": strategy.meta.name,
                "symbol": strategy.symbol,
                "error": str(e)
            })
    
    return pd.DataFrame(results)


__all__ = [
    "TradeResult",
    "BacktestResult",
    "SimpleBacktester",
    "run_simple_backtest",
    "compare_strategy_backtests",
]


# ==================== CLI 命令行接口 ====================

def generate_test_contexts(num_samples: int = 1000):
    """生成测试用的 MarketContext 序列"""
    from engines.compute.context import (
        MarketContext,
        TimeframeContext,
        PriceState,
        TrendStateData,
        VolatilityStateData,
        VolumeStateData,
        FlowState,
        LiquidityStateData,
        DerivativesContext,
        OIData,
        FundingData,
        LiquidationData,
        RiskContext,
        TrendState,
        FlowPressure,
        FundingBias,
        LiquidityState,
        VolatilityState,
        VolumeState,
    )
    
    market_contexts = []
    timestamps = []
    prices = []
    
    base_timestamp = int(pd.Timestamp("2024-01-01").value / 10**6)
    base_price = 45000.0
    
    extreme_prob = 0.15
    
    for i in range(num_samples):
        timestamp = base_timestamp + i * 15 * 60 * 1000
        timestamps.append(timestamp)
        
        price_change = np.random.normal(0, 0.003) * base_price
        price = base_price + price_change
        base_price = price
        prices.append(price)
        
        tf_contexts = {}
        
        m1_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        tf_contexts["1m"] = TimeframeContext(
            timeframe="1m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.0015)),
                low=price * (1 - np.random.uniform(0, 0.0015)),
                close=price,
                change_percent=np.random.uniform(-0.3, 0.3),
            ),
            flow=FlowState(
                pressure=m1_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-100, 100),
            ),
        )
        
        m5_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        tf_contexts["5m"] = TimeframeContext(
            timeframe="5m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.004)),
                low=price * (1 - np.random.uniform(0, 0.004)),
                close=price,
                change_percent=np.random.uniform(-0.6, 0.6),
            ),
            flow=FlowState(
                pressure=m5_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-500, 500),
            ),
        )
        
        m15_trend = np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                    p=[0.35, 0.35, 0.3])
        m15_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        
        if np.random.random() < extreme_prob:
            m15_change_percent = np.random.uniform(0.5, 1.5)
        else:
            m15_change_percent = np.random.uniform(-1.2, 1.2)
        
        tf_contexts["15m"] = TimeframeContext(
            timeframe="15m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.006)),
                low=price * (1 - np.random.uniform(0, 0.006)),
                close=price,
                change_percent=m15_change_percent,
            ),
            trend=TrendStateData(
                state=m15_trend,
                slope=np.random.uniform(-0.012, 0.012),
                strength=np.random.uniform(0.3, 0.95),
            ),
            volatility=VolatilityStateData(
                state=np.random.choice([VolatilityState.NORMAL, VolatilityState.ELEVATED, VolatilityState.LOW], 
                                      p=[0.5, 0.35, 0.15]),
                atr_pct=np.random.uniform(0.008, 0.025),
            ),
            volume=VolumeStateData(
                state=np.random.choice([VolumeState.NORMAL, VolumeState.CLIMAX, VolumeState.DRY], 
                                      p=[0.6, 0.25, 0.15]),
                volume_zscore=np.random.uniform(-2.5, 2.5),
            ),
            flow=FlowState(
                pressure=m15_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-1200, 1200),
                cvd_slope=np.random.uniform(-0.15, 0.15),
                aggressive_ratio=np.random.uniform(0.25, 0.75),
            ),
        )
        
        tf_contexts["1h"] = TimeframeContext(
            timeframe="1h",
            trend=TrendStateData(
                state=np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                      p=[0.35, 0.35, 0.3]),
                slope=np.random.uniform(-0.006, 0.006),
                strength=np.random.uniform(0.3, 0.95),
            ),
            price=PriceState(close=price, change_percent=np.random.uniform(-1.8, 1.8)),
        )
        
        tf_contexts["4h"] = TimeframeContext(
            timeframe="4h",
            trend=TrendStateData(
                state=np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                      p=[0.35, 0.35, 0.3]),
                slope=np.random.uniform(-0.004, 0.004),
                strength=np.random.uniform(0.3, 0.95),
            ),
        )
        
        if np.random.random() < extreme_prob:
            oi_zscore = np.random.uniform(1.6, 3.5)
        else:
            oi_zscore = np.random.uniform(-2.8, 2.8)
        
        if np.random.random() < extreme_prob:
            funding_zscore = np.random.uniform(-3.5, -1.6)
        else:
            funding_zscore = np.random.uniform(-2.8, 2.8)
        
        if funding_zscore > 2.0:
            funding_bias = FundingBias.EXTREME_POSITIVE
        elif funding_zscore > 0.5:
            funding_bias = FundingBias.POSITIVE
        elif funding_zscore < -2.0:
            funding_bias = FundingBias.EXTREME_NEGATIVE
        elif funding_zscore < -0.5:
            funding_bias = FundingBias.NEGATIVE
        else:
            funding_bias = FundingBias.NEUTRAL
        
        derivatives = DerivativesContext(
            oi=OIData(
                value=np.random.uniform(1500000, 6000000),
                delta=np.random.uniform(-150000, 150000),
                zscore=oi_zscore,
            ),
            funding=FundingData(
                rate=np.random.uniform(-0.012, 0.012),
                zscore=funding_zscore,
                bias=funding_bias,
            ),
            liquidation=LiquidationData(
                long=np.random.uniform(0, 150000),
                short=np.random.uniform(0, 150000),
                total=np.random.uniform(0, 300000),
                long_zscore=np.random.uniform(-3.5, 3.5),
                short_zscore=np.random.uniform(-3.5, 3.5),
                reversal_signal=np.random.random() < 0.1,
            ),
        )
        
        ctx = MarketContext(
            symbol="BTCUSDT",
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )
        
        market_contexts.append(ctx)
    
    return market_contexts, timestamps, np.array(prices)


def main():
    """CLI 入口函数"""
    parser = argparse.ArgumentParser(description="Simple Backtest Tool - 简单回测工具")
    
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=StrategyName.ALL,
        help=f"策略名称: {', '.join(StrategyName.ALL)}"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="交易对 (默认: BTCUSDT)"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="测试天数 (默认: 30)"
    )
    
    parser.add_argument(
        "--taker-fee",
        type=float,
        default=0.0005,
        help="Taker 手续费率 (默认: 0.0005)"
    )
    
    parser.add_argument(
        "--maker-fee",
        type=float,
        default=0.0002,
        help="Maker 手续费率 (默认: 0.0002)"
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=2.0,
        help="滑点 (基点, 默认: 2.0)"
    )
    
    parser.add_argument(
        "--max-holding-bars",
        type=int,
        default=10,
        help="最大持仓 bar 数 (默认: 10)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径"
    )
    
    args = parser.parse_args()
    
    print(f"简单回测: {args.strategy} | {args.symbol} | {args.days}天")
    print(f"手续费: Taker {args.taker_fee*100:.2f}%, Maker {args.maker_fee*100:.2f}%")
    print(f"滑点: {args.slippage} bps, 最大持仓: {args.max_holding_bars} bars")
    print("="*50)
    
    # 获取策略类
    strategy_class = get_strategy_class(args.strategy)
    if not strategy_class:
        print(f"错误: 未知策略 {args.strategy}")
        sys.exit(1)
    
    # 生成测试数据
    samples_per_day = 96
    num_samples = args.days * samples_per_day
    print(f"生成 {num_samples} 个样本...")
    market_contexts, timestamps, prices = generate_test_contexts(num_samples)
    
    # 创建策略实例并运行回测
    strategy = strategy_class(args.symbol)
    result = run_simple_backtest(
        strategy,
        market_contexts,
        timestamps,
        prices,
        maker_fee=args.maker_fee,
        taker_fee=args.taker_fee,
        slippage_bps=args.slippage,
        max_holding_bars=args.max_holding_bars
    )
    
    # 打印结果
    print(result)
    
    # 验收检查
    print("\n验收检查:")
    checks = [
        ("交易数 > 0", result.total_trades > 0),
        ("胜率 > 50%", result.win_rate > 0.5),
        ("盈利因子 > 1", result.profit_factor > 1),
        ("夏普比率 > 0", result.sharpe_ratio > 0),
    ]
    
    all_pass = True
    for check, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_pass = False
    
    if all_pass:
        print("\n✓ 所有检查通过")
    else:
        print("\n✗ 部分检查未通过")
    
    # 保存结果
    if args.output:
        result_dict = {
            "strategy": args.strategy,
            "symbol": args.symbol,
            "days": args.days,
            "taker_fee": args.taker_fee,
            "maker_fee": args.maker_fee,
            "slippage": args.slippage,
            "max_holding_bars": args.max_holding_bars,
            "total_trades": result.total_trades,
            "long_trades": result.long_trades,
            "short_trades": result.short_trades,
            "win_rate": result.win_rate,
            "avg_trade_return": result.avg_trade_return,
            "total_pnl": result.total_pnl,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "profit_factor": result.profit_factor,
        }
        save_results_to_json(result_dict, args.output)


if __name__ == "__main__":
    main()
