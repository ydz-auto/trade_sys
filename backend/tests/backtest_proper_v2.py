#!/usr/bin/env python3
"""
正确的回测框架 V2

修复问题：
1. 夏普比率计算错误 - 用正确的时间序列
2. 手续费
3. 滑点
4. 持仓管理和浮盈计算
5. 保证金和强平
6. 更真实的策略逻辑
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class Position:
    """持仓"""
    strategy_id: str
    direction: str  # long/short
    entry_price: float
    entry_timestamp: pd.Timestamp
    size_usd: float
    size_coin: float
    entry_fee: float
    entry_slippage: float
    
@dataclass
class Trade:
    """交易"""
    strategy_id: str
    direction: str
    entry_price: float
    entry_timestamp: pd.Timestamp
    exit_price: float
    exit_timestamp: pd.Timestamp
    profit_usd: float
    profit_pct: float
    entry_fee: float
    exit_fee: float
    entry_slippage: float
    exit_slippage: float
    stopped_out: bool
    liquidated: bool

class BacktestEngine:
    """真实的回测引擎"""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        leverage: int = 50,
        fee_taker: float = 0.0004,
        fee_maker: float = 0.0002,
        slippage: float = 0.0005,
        maintenance_margin: float = 0.005,
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        self.fee_taker = fee_taker
        self.fee_maker = fee_maker
        self.slippage = slippage
        self.maintenance_margin = maintenance_margin
        
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.capital_history = []
        
    def calculate_available_margin(self) -> float:
        """计算可用保证金"""
        used_margin = 0
        for pos in self.positions.values():
            used_margin += pos.size_usd / self.leverage
        return self.current_capital - used_margin
    
    def enter_position(
        self,
        strategy_id: str,
        direction: str,
        price: float,
        timestamp: pd.Timestamp,
        risk_pct: float = 0.05,
    ) -> Optional[Position]:
        """开仓"""
        available_margin = self.calculate_available_margin()
        if available_margin <= 0:
            return None
            
        size_usd = min(
            self.initial_capital * risk_pct,
            available_margin * 0.9,
        )
        
        slippage_price = price * (1 + self.slippage) if direction == "long" else price * (1 - self.slippage)
        fee = size_usd * self.fee_taker
        
        size_coin = size_usd / slippage_price
        
        position = Position(
            strategy_id=strategy_id,
            direction=direction,
            entry_price=slippage_price,
            entry_timestamp=timestamp,
            size_usd=size_usd,
            size_coin=size_coin,
            entry_fee=fee,
            entry_slippage=self.slippage,
        )
        
        self.current_capital -= fee
        self.positions[strategy_id] = position
        return position
    
    def check_liquidation(self, position: Position, current_price: float) -> bool:
        """检查是否强平"""
        if position.direction == "long":
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
            
        pnl = pnl_pct * position.size_usd
        margin_used = position.size_usd / self.leverage
        margin_left = margin_used + pnl
        
        # 低于维持保证金就强平
        if margin_left / margin_used <= self.maintenance_margin:
            return True
        return False
    
    def exit_position(
        self,
        strategy_id: str,
        price: float,
        timestamp: pd.Timestamp,
        reason: str = "normal",
    ) -> Optional[Trade]:
        """平仓"""
        if strategy_id not in self.positions:
            return None
            
        position = self.positions.pop(strategy_id)
        
        slippage_price = price * (1 - self.slippage) if position.direction == "long" else price * (1 + self.slippage)
        fee = position.size_usd * self.fee_taker
        
        if position.direction == "long":
            pnl = (slippage_price - position.entry_price) * position.size_coin
        else:
            pnl = (position.entry_price - slippage_price) * position.size_coin
            
        trade = Trade(
            strategy_id=strategy_id,
            direction=position.direction,
            entry_price=position.entry_price,
            entry_timestamp=position.entry_timestamp,
            exit_price=slippage_price,
            exit_timestamp=timestamp,
            profit_usd=pnl - fee,
            profit_pct=pnl / (position.size_usd / self.leverage),
            entry_fee=position.entry_fee,
            exit_fee=fee,
            entry_slippage=position.entry_slippage,
            exit_slippage=self.slippage,
            stopped_out=reason == "stop_loss",
            liquidated=reason == "liquidation",
        )
        
        self.current_capital += trade.profit_usd
        self.trades.append(trade)
        return trade
        
    def record_capital(self, timestamp: pd.Timestamp, current_price: float):
        """记录资本"""
        total_value = self.current_capital
        
        # 加上持仓浮盈
        for pos in self.positions.values():
            if pos.direction == "long":
                unrealized_pnl = (current_price - pos.entry_price) * pos.size_coin
            else:
                unrealized_pnl = (pos.entry_price - current_price) * pos.size_coin
            total_value += unrealized_pnl
            
        self.capital_history.append({"timestamp": timestamp, "capital": total_value})
        
    def get_results(self) -> Dict:
        """计算回测结果"""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_profit_pct": 0.0,
                "total_profit_usd": 0.0,
                "sharpe": 0.0,
                "calmar": 0.0,
                "sortino": 0.0,
                "max_drawdown": 0.0,
                "final_capital": self.current_capital,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }
            
        # 基础统计
        wins = sum(1 for t in self.trades if t.profit_usd > 0)
        total_profit = sum(t.profit_usd for t in self.trades if t.profit_usd > 0)
        total_loss = abs(sum(t.profit_usd for t in self.trades if t.profit_usd < 0))
        
        win_rate = wins / len(self.trades) if self.trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        expectancy = (total_profit - total_loss) / len(self.trades)
        
        # 收益计算
        total_profit_pct = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        total_profit_usd = self.current_capital - self.initial_capital
        
        # 时间序列分析
        sharpe = 0.0
        sortino = 0.0
        max_drawdown = 0.0
        calmar = 0.0
        
        if self.capital_history and len(self.capital_history) > 1:
            df_cap = pd.DataFrame(self.capital_history).set_index('timestamp')
            df_cap = df_cap.resample('1h').last().ffill()
            
            # 计算收益率
            returns = df_cap['capital'].pct_change().dropna()
            
            # 夏普比率
            if len(returns) > 0 and returns.std() > 0:
                annual_factor = np.sqrt(365 * 24)
                sharpe = returns.mean() / returns.std() * annual_factor
                
            # 最大回撤
            peak = df_cap['capital'].cummax()
            drawdown = (df_cap['capital'] - peak) / peak
            if len(drawdown) > 0:
                max_drawdown = drawdown.min()
                
            # Sortino
            if len(returns) > 0:
                downside_returns = returns[returns < 0]
                if len(downside_returns) > 0 and downside_returns.std() > 0:
                    sortino = returns.mean() / downside_returns.std() * np.sqrt(365 * 24)
                else:
                    sortino = sharpe
                    
            # Calmar
            if max_drawdown != 0 and max_drawdown < 0:
                calmar = -total_profit_pct / (max_drawdown * 100)
        
        return {
            "total_trades": len(self.trades),
            "win_rate": win_rate,
            "total_profit_pct": total_profit_pct,
            "total_profit_usd": total_profit_usd,
            "sharpe": sharpe,
            "calmar": calmar,
            "sortino": sortino,
            "max_drawdown": max_drawdown,
            "final_capital": self.current_capital,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
        }

# =============================================================================
# 简单策略 - 只有一个基础RSI策略，用于测试回测逻辑
# =============================================================================
class SimpleRSIStrategy:
    """简单RSI策略"""
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.rsi_window = 14
        self.oversold = 30
        self.overbought = 70
        self.in_position = False
        self.position_direction = None
        
    def calculate_rsi(self, prices: np.ndarray) -> float:
        if len(prices) < self.rsi_window + 1:
            return 50
            
        deltas = np.diff(prices)
        gains = np.maximum(deltas[-self.rsi_window:], 0)
        losses = np.maximum(-deltas[-self.rsi_window:], 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - 100 / (1 + rs)
        
    def signal(self, prices: np.ndarray) -> Optional[str]:
        """返回 'long', 'short', 'close', or None"""
        rsi = self.calculate_rsi(prices)
        
        if not self.in_position:
            if rsi < self.oversold:
                return "long"
            elif rsi > self.overbought:
                return "short"
        else:
            # 简单反转平仓
            if self.position_direction == "long" and rsi > 50:
                return "close"
            elif self.position_direction == "short" and rsi < 50:
                return "close"
                
        return None
        
    def on_position_opened(self, direction: str):
        self.in_position = True
        self.position_direction = direction
        
    def on_position_closed(self):
        self.in_position = False
        self.position_direction = None


def main():
    print("=" * 120)
    print("PROPER BACKTEST V2 - FIXED ISSUES")
    print("=" * 120)
    
    DATA_LAKE_ROOT = Path("/Volumes/00_crypto/00_code/backend/data_lake")
    symbol = "BTCUSDT"
    
    # 加载2022-01数据
    df_list = []
    for month in ["01"]:
        path = DATA_LAKE_ROOT / f"crypto/binance/klines/symbol={symbol}/year=2022/month={month}/data.parquet"
        if path.exists():
            df_month = pd.read_parquet(path)
            df_list.append(df_month)
            
    if not df_list:
        print("No data")
        return
        
    df_raw = pd.concat(df_list)
    df_raw = df_raw.set_index('timestamp').sort_index()
    
    # 重采样到5分钟
    ohlc = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df = df_raw.resample('5min').agg(ohlc).dropna().reset_index()
    
    print(f"Data: {len(df)} bars, {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # 初始化回测
    engine = BacktestEngine(
        initial_capital=10000,
        leverage=50,
        fee_taker=0.0004,
        slippage=0.0005,
    )
    
    # 策略
    strategy = SimpleRSIStrategy(strategy_id="simple_rsi")
    
    # 回测循环
    for i in range(100, len(df)):
        ts = df.iloc[i]['timestamp']
        price = df.iloc[i]['close']
        prices = df['close'].iloc[max(0, i-200):i+1].values
        
        # 检查强平
        if strategy.strategy_id in engine.positions:
            pos = engine.positions[strategy.strategy_id]
            if engine.check_liquidation(pos, price):
                engine.exit_position(strategy.strategy_id, price, ts, reason="liquidation")
                strategy.on_position_closed()
                
        # 策略信号
        signal = strategy.signal(prices)
        
        if signal == "long" and strategy.strategy_id not in engine.positions:
            pos = engine.enter_position(strategy.strategy_id, "long", price, ts)
            if pos:
                strategy.on_position_opened("long")
                
        elif signal == "short" and strategy.strategy_id not in engine.positions:
            pos = engine.enter_position(strategy.strategy_id, "short", price, ts)
            if pos:
                strategy.on_position_opened("short")
                
        elif signal == "close" and strategy.strategy_id in engine.positions:
            engine.exit_position(strategy.strategy_id, price, ts, reason="normal")
            strategy.on_position_closed()
            
        # 记录资金
        engine.record_capital(ts, price)
        
    # 结果
    results = engine.get_results()
    
    print("\n" + "=" * 120)
    print("RESULTS")
    print("=" * 120)
    print(f"Initial Capital: $10,000.00")
    print(f"Final Capital:   ${results['final_capital']:.2f}")
    print()
    print(f"Total Trades:    {results['total_trades']}")
    print(f"Win Rate:        {results['win_rate']:.1%}")
    print()
    print(f"Total Profit:    {results['total_profit_pct']:.2f}% (${results['total_profit_usd']:.2f})")
    print(f"Max Drawdown:    {results['max_drawdown']:.1%}")
    print()
    print(f"Sharpe Ratio:    {results['sharpe']:.2f}")
    print(f"Sortino Ratio:   {results['sortino']:.2f}")
    print(f"Calmar Ratio:    {results['calmar']:.2f}")
    print(f"Profit Factor:   {results['profit_factor']:.2f}")
    print(f"Expectancy:      ${results['expectancy']:.2f}")
    print()
    print("=" * 120)
    
    # 显示前20笔交易
    if engine.trades:
        print("\nFirst 10 trades:")
        for t in engine.trades[:10]:
            direction = "🔴 SHORT" if t.direction == "short" else "🟢 LONG"
            status = "💥 LIQUIDATED" if t.liquidated else "💥 STOPPED" if t.stopped_out else "✅"
            print(f"  {t.entry_timestamp} {direction} -> {t.exit_timestamp} | Profit: ${t.profit_usd:,.2f} | {status}")

if __name__ == "__main__":
    main()
