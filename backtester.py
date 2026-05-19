import numpy as np
import pandas as pd

class Backtester:
    def __init__(self, initial_capital=100000, transaction_cost=0.001, slippage=0.0005):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.slippage = slippage
    
    def run(self, signals, prices):
        capital = self.initial_capital
        position = 0.0
        entry_price = 0.0
        trades = []
        equity_curve = [capital]
        
        for i, signal in enumerate(signals):
            if signal == 1 and position == 0:
                position = capital / prices[i]
                entry_price = prices[i] * (1 + self.slippage)
            elif signal == -1 and position == 0:
                position = -capital / prices[i]
                entry_price = prices[i] * (1 - self.slippage)
            elif signal == 0 and position != 0:
                exit_price = prices[i] * (1 - self.slippage if position > 0 else 1 + self.slippage)
                pnl = position * (exit_price - entry_price)
                cost = abs(position) * entry_price * self.transaction_cost
                pnl -= cost
                capital += pnl
                trades.append({'pnl': pnl, 'hold_time': i})
                position = 0
            
            if position != 0:
                unrealized = position * (prices[i] - entry_price)
                equity_curve.append(capital + unrealized)
            else:
                equity_curve.append(capital)
        
        equity = np.array(equity_curve)
        returns = np.diff(equity) / equity[:-1]
        max_dd = self.calculate_max_drawdown(equity)
        sharpe = np.sqrt(252) * np.mean(returns) / np.std(returns) if np.std(returns) != 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': capital,
            'total_return': (capital - self.initial_capital) / self.initial_capital,
            'num_trades': len(trades),
            'win_rate': sum(1 for t in trades if t['pnl'] > 0) / len(trades) if trades else 0,
            'avg_pnl': np.mean([t['pnl'] for t in trades]) if trades else 0,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe
        }
    
    def calculate_max_drawdown(self, equity):
        peak = equity[0]
        max_dd = 0.0
        for value in equity[1:]:
            if value > peak:
                peak = value
            else:
                max_dd = max(max_dd, (peak - value) / peak)
        return max_dd
    
    def print_report(self, metrics):
        print("\n" + "="*50)
        print("回测报告")
        print("="*50)
        print(f"初始资金: ${metrics['initial_capital']:,.2f}")
        print(f"最终资金: ${metrics['final_capital']:,.2f}")
        print(f"总收益率: {metrics['total_return']*100:.2f}%")
        print(f"交易次数: {metrics['num_trades']}")
        print(f"胜率: {metrics['win_rate']*100:.2f}%")
        print(f"平均盈亏: ${metrics['avg_pnl']:,.2f}")
        print(f"最大回撤: {metrics['max_drawdown']*100:.2f}%")
        print(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
        print("="*50)

def generate_signals(predictions, threshold=0.6):
    signals = np.zeros(len(predictions))
    prob_long = predictions[:, 1] if predictions.ndim == 2 else predictions
    signals[prob_long > threshold] = 1
    signals[prob_long < (1 - threshold)] = -1
    return signals
