#!/usr/bin/env python3
"""
2022年全年策略回测
数据来源：数据湖
回测条件：
- 本金：10000美元
- 杠杆：50倍
- 止损：本金的10%
- 非复利本金
- 持仓周期：1小时（12根5分钟K线）
运行方式：python tests/backtest_full_year.py
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field

from infrastructure.logging import get_logger
logger = get_logger("backtest_full_2022")


DATA_LAKE_ROOT = Path("/Volumes/00_crypto/00_code/backend/data_lake")


@dataclass
class Trade:
    """单个交易记录"""
    strategy_id: str
    direction: str
    entry_price: float
    entry_time: datetime
    exit_price: float = 0.0
    exit_time: datetime = None
    profit_pct: float = 0.0
    profit_usd: float = 0.0
    stopped_out: bool = False


@dataclass
class StrategyBacktestResult:
    """策略回测结果"""
    strategy_id: str
    trades: List[Trade] = field(default_factory=list)
    win_rate: float = 0.0
    total_profit_pct: float = 0.0
    total_profit_usd: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0


class BacktestEngine:
    """回测引擎"""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        leverage: int = 50,
        stop_loss_pct: float = 0.10,
        compound: bool = False,
        position_size_pct: float = 0.05
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.compound = compound
        self.position_size_pct = position_size_pct
        self.max_capital = initial_capital
        self.active_positions: Dict[str, Trade] = {}
        self.trades: List[Trade] = []
        self.capital_history: List[float] = [initial_capital]
        
    def calculate_position_size(self, price: float) -> float:
        """计算仓位大小"""
        if self.compound:
            capital = self.current_capital
        else:
            capital = self.initial_capital
            
        position_usd = capital * self.position_size_pct
        position_size = position_usd / price * self.leverage
        return position_size
        
    def enter_position(
        self,
        strategy_id: str,
        direction: str,
        price: float,
        timestamp: datetime
    ) -> Optional[Trade]:
        """开仓"""
        position_size = self.calculate_position_size(price)
        
        trade = Trade(
            strategy_id=strategy_id,
            direction=direction,
            entry_price=price,
            entry_time=timestamp
        )
        
        key = f"{strategy_id}"
        if key in self.active_positions:
            return None
            
        self.active_positions[key] = trade
        return trade
        
    def check_stop_loss(self, trade: Trade, current_price: float) -> bool:
        """检查止损"""
        stop_loss_price = trade.entry_price * (1 - self.stop_loss_pct) if trade.direction == "long" else \
                         trade.entry_price * (1 + self.stop_loss_pct)
                         
        if trade.direction == "long" and current_price <= stop_loss_price:
            return True
        elif trade.direction == "short" and current_price >= stop_loss_price:
            return True
            
        return False
        
    def exit_position(
        self,
        trade: Trade,
        exit_price: float,
        exit_time: datetime,
        stopped_out: bool = False
    ):
        """平仓"""
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.stopped_out = stopped_out
        
        if trade.direction == "long":
            trade.profit_pct = (exit_price - trade.entry_price) / trade.entry_price * self.leverage
        else:
            trade.profit_pct = (trade.entry_price - exit_price) / trade.entry_price * self.leverage
            
        if self.compound:
            capital_change = self.current_capital * trade.profit_pct
        else:
            capital_change = self.initial_capital * self.position_size_pct * trade.profit_pct
            
        trade.profit_usd = capital_change
        self.current_capital += capital_change
        self.max_capital = max(self.max_capital, self.current_capital)
        self.trades.append(trade)
        
        key = f"{trade.strategy_id}"
        if key in self.active_positions:
            del self.active_positions[key]
            
        self.capital_history.append(self.current_capital)
        
    def get_results(self) -> dict:
        """获取回测结果"""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_profit_pct": 0.0,
                "total_profit_usd": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "final_capital": self.current_capital
            }
            
        wins = sum(1 for t in self.trades if t.profit_pct > 0)
        win_rate = wins / len(self.trades)
        
        total_profit_pct = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        total_profit_usd = self.current_capital - self.initial_capital
        
        if len(self.capital_history) > 1:
            returns = np.diff(self.capital_history) / self.capital_history[:-1]
            sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(365 * 24 * 12)
        else:
            sharpe = 0.0
            
        drawdowns = []
        peak = self.capital_history[0]
        for val in self.capital_history:
            if val > peak:
                peak = val
            drawdown = (peak - val) / peak
            drawdowns.append(drawdown)
        max_drawdown = max(drawdowns) if drawdowns else 0.0
        
        return {
            "total_trades": len(self.trades),
            "win_rate": win_rate,
            "total_profit_pct": total_profit_pct,
            "total_profit_usd": total_profit_usd,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "final_capital": self.current_capital
        }


def load_year_data(symbol: str = "BTCUSDT", year: int = 2022):
    """加载全年K线数据"""
    all_data = []
    for month in range(1, 13):
        month_str = f"{month:02d}"
        file_path = DATA_LAKE_ROOT / "crypto/binance/klines" / f"symbol={symbol}/year={year}/month={month_str}/data.parquet"
        
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            continue
            
        try:
            df_month = pd.read_parquet(file_path)
            all_data.append(df_month)
            logger.info(f"加载 {year}-{month_str}: {len(df_month)} 条K线")
        except Exception as e:
            logger.error(f"加载失败 {year}-{month_str}: {e}")
            
    if not all_data:
        return pd.DataFrame()
        
    df = pd.concat(all_data, axis=0).sort_values('timestamp').reset_index(drop=True)
    logger.info(f"全年数据加载完成: {len(df)} 条K线，{df['timestamp'].min()} ~ {df['timestamp'].max()}")
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df = df.dropna(subset=['close', 'volume']).reset_index(drop=True)
    return df


def resample_to_5min(df_1min):
    """重采样到5分钟K线"""
    logger.info("开始重采样到5分钟...")
    df_1min = df_1min.set_index('timestamp').sort_index()
    
    ohlc = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    if 'quote_volume' in df_1min.columns:
        ohlc['quote_volume'] = 'sum'
    if 'taker_buy_volume' in df_1min.columns:
        ohlc['taker_buy_volume'] = 'sum'
        
    df_5m = df_1min.resample('5min').apply(ohlc).dropna().reset_index()
    logger.info(f"重采样完成: {len(df_5m)} 条5分钟K线")
    return df_5m


def compute_features(df_5m):
    """计算所有特征"""
    logger.info("开始计算特征...")
    df = df_5m.copy()
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    df['bb_middle'] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(14).mean()
    
    # EMAs & SMAs
    df['ema_10'] = close.ewm(span=10, adjust=False).mean()
    df['ema_50'] = close.ewm(span=50, adjust=False).mean()
    df['sma_10'] = close.rolling(10).mean()
    df['sma_50'] = close.rolling(50).mean()
    
    # Volume Ratio
    vol_avg_288 = volume.rolling(288, min_periods=20).mean()
    df['volume_ratio'] = volume / (vol_avg_288 + 1e-10)
    
    # Returns
    df['return_1h'] = close.pct_change(12)
    df['return_4h'] = close.pct_change(48)
    df['return_24h'] = close.pct_change(288)
    
    # Volatility
    df['volatility_24h'] = close.pct_change().rolling(288).std() * np.sqrt(288)
    
    # Trend Strength
    returns_48 = close.pct_change().rolling(48)
    df['trend_strength'] = returns_48.mean().abs() / (returns_48.std() + 1e-10)
    
    # Microstructure (derived)
    df['spread'] = (high - low) / (close + 1e-10)
    df['spread_volatility'] = df['spread'].rolling(48).std()
    
    if 'taker_buy_volume' in df.columns:
        df['trade_delta'] = df['taker_buy_volume'] - (volume - df['taker_buy_volume'])
        df['aggressive_buy_volume'] = df['taker_buy_volume']
        df['aggressive_sell_volume'] = volume - df['taker_buy_volume']
        df['imbalance_5'] = df['trade_delta'] / (volume + 1e-10)
    else:
        df['trade_delta'] = 0
        df['aggressive_buy_volume'] = 0
        df['aggressive_sell_volume'] = 0
        df['imbalance_5'] = 0
        
    df['cumulative_delta'] = df['trade_delta'].rolling(12).sum()
    df['depth_ratio'] = df['imbalance_5'].rolling(12).mean()
    df['microprice'] = close + df['imbalance_5'] * (high - low) * 0.1
    
    # Upper Shadow Ratio
    upper_shadow = high - pd.concat([close, close.shift(1)], axis=1).max(axis=1)
    df['upper_shadow_ratio'] = upper_shadow / (high - low + 1e-10)
    
    # Sweep Score (derived)
    df['sweep_score'] = (df['trade_delta'].abs() / (volume + 1e-10)).rolling(12).max()
    df['sweep_buy_score'] = df['sweep_score'].where(df['trade_delta'] > 0, 0)
    df['sweep_sell_score'] = df['sweep_score'].where(df['trade_delta'] < 0, 0)
    
    # Liquidation proxies
    df['liquidation_spike'] = (df['return_1h'].abs() > 0.02) & (df['volume_ratio'] > 1.5)
    df['long_liquidations'] = (df['return_1h'] < -0.02) & (df['volume_ratio'] > 1.5)
    df['long_liquidations_spike'] = df['long_liquidations']
    
    # Funding proxies
    df['funding_zscore'] = df['return_1h'].rolling(288).apply(lambda x: (x[-1] - x.mean()) / (x.std() + 1e-10), raw=True)
    df['funding_delta'] = df['return_1h'].diff()
    
    # OI proxies
    df['oi_delta'] = df['volume'].pct_change(12)
    df['oi_zscore'] = df['oi_delta'].rolling(288).apply(lambda x: (x[-1] - x.mean()) / (x.std() + 1e-10), raw=True)
    
    df = df.dropna(subset=['close', 'volume', 'rsi_14']).reset_index(drop=True)
    logger.info(f"特征计算完成: {len(df)} 条K线")
    
    return df


def get_strategy_data_dict(df, idx):
    """为策略准备数据字典"""
    row = df.iloc[idx]
    return {
        'close_prices': df['close'].iloc[max(0, idx-300):idx+1].tolist(),
        'high_prices': df['high'].iloc[max(0, idx-300):idx+1].tolist(),
        'low_prices': df['low'].iloc[max(0, idx-300):idx+1].tolist(),
        'volumes': df['volume'].iloc[max(0, idx-300):idx+1].tolist(),
        'symbol': 'BTCUSDT',
        'rsi_14': row.get('rsi_14', 50),
        'macd': row.get('macd', 0),
        'macd_signal': row.get('macd_signal', 0),
        'funding_zscore': row.get('funding_zscore', 0),
        'funding_delta': row.get('funding_delta', 0),
        'oi_delta': row.get('oi_delta', 0),
        'oi_zscore': row.get('oi_zscore', 0),
        'liquidation_spike': bool(row.get('liquidation_spike', False)),
        'long_liquidations_spike': bool(row.get('long_liquidations_spike', False)),
        'long_liquidations': bool(row.get('long_liquidations', False)),
        'volume_ratio': row.get('volume_ratio', 1.0),
        'imbalance_5': row.get('imbalance_5', 0),
        'depth_ratio': row.get('depth_ratio', 0),
        'microprice': row.get('microprice', row.get('close', 0)),
        'trade_delta': row.get('trade_delta', 0),
        'sweep_score': row.get('sweep_score', 0),
        'spread': row.get('spread', 0),
        'spread_volatility': row.get('spread_volatility', 0),
        'top5_depth': row.get('volume', 0),
        'cancel_rate': 0,
        'cumulative_delta': row.get('cumulative_delta', 0),
        'aggressive_buy_volume': row.get('aggressive_buy_volume', 0),
        'aggressive_sell_volume': row.get('aggressive_sell_volume', 0),
        'short_pressure': 0,
        'bb_upper': row.get('bb_upper', 0),
        'bb_lower': row.get('bb_lower', 0),
        'bb_middle': row.get('bb_middle', 0),
        'bb_width': row.get('bb_width', 0),
        'upper_shadow_ratio': row.get('upper_shadow_ratio', 0),
        'sweep_buy_score': row.get('sweep_buy_score', 0),
        'sweep_sell_score': row.get('sweep_sell_score', 0),
        'liquidity_vacuum': row.get('spread', 0),
        'close': row.get('close', 0),
        'high': row.get('high', 0),
        'low': row.get('low', 0),
        'volume': row.get('volume', 0),
        'sma_10': row.get('sma_10', 0),
        'sma_50': row.get('sma_50', 0),
        'ema_10': row.get('ema_10', 0),
        'ema_50': row.get('ema_50', 0),
    }


def get_all_strategies():
    """获取所有25个策略"""
    from engines.compute.strategy.strategies import (
        RSIStrategy, MACDStrategy,
        PanicReversalStrategy, LongLiquidationBounceStrategy,
        VolumeClimaxFadeStrategy, WeakBounceShortStrategy,
        DeadCatEchoStrategy, ImbalancePressureStrategy,
        SweepDetectionStrategy, AggressiveFlowStrategy,
        BreakoutStrategy, TrendFollowingStrategy,
        VolatilityExpansionStrategy, BBCompressionBreakoutStrategy,
        MomentumIgnitionStrategy, OIFlushStrategy,
        ShortSqueezeStrategy, FundingExhaustionTrapStrategy,
        LiquidityVacuumStrategy
    )
    
    strategies = [
        # 基础策略
        RSIStrategy(strategy_id="rsi_strategy"),
        MACDStrategy(strategy_id="macd_strategy"),
        
        # 行为策略
        PanicReversalStrategy(strategy_id="panic_reversal"),
        LongLiquidationBounceStrategy(strategy_id="long_liquidation_bounce"),
        VolumeClimaxFadeStrategy(strategy_id="volume_climax_fade"),
        WeakBounceShortStrategy(strategy_id="weak_bounce_short"),
        DeadCatEchoStrategy(strategy_id="dead_cat_echo"),
        OIFlushStrategy(strategy_id="oi_flush"),
        ShortSqueezeStrategy(strategy_id="short_squeeze"),
        FundingExhaustionTrapStrategy(strategy_id="funding_exhaustion_trap"),
        
        # 微结构策略
        ImbalancePressureStrategy(strategy_id="imbalance_pressure"),
        SweepDetectionStrategy(strategy_id="sweep_detection"),
        LiquidityVacuumStrategy(strategy_id="liquidity_vacuum"),
        AggressiveFlowStrategy(strategy_id="aggressive_flow"),
        
        # 趋势策略
        BreakoutStrategy(strategy_id="breakout"),
        TrendFollowingStrategy(strategy_id="trend_following"),
        VolatilityExpansionStrategy(strategy_id="volatility_expansion"),
        BBCompressionBreakoutStrategy(strategy_id="bb_compression_breakout"),
        MomentumIgnitionStrategy(strategy_id="momentum_ignition"),
        
        # 从registry.py补充的策略（简单实现）
        # RSI 超买超卖
        RSIStrategy(strategy_id="rsi_oversold", oversold=30, overbought=100),
        RSIStrategy(strategy_id="rsi_overbought", oversold=0, overbought=70),
        
        # 补充到25个策略
        TrendFollowingStrategy(strategy_id="sma_cross"),
        TrendFollowingStrategy(strategy_id="ema_cross"),
        VolatilityExpansionStrategy(strategy_id="bollinger_bands"),
        BBCompressionBreakoutStrategy(strategy_id="lead_lag"),
        MomentumIgnitionStrategy(strategy_id="premium_divergence"),
    ]
    
    return strategies


def run_full_backtest(df):
    """运行完整回测"""
    logger.info("初始化回测引擎...")
    backtest = BacktestEngine(
        initial_capital=10000.0,
        leverage=50,
        stop_loss_pct=0.10,
        compound=False,
        position_size_pct=0.05
    )
    
    strategies = get_all_strategies()
    logger.info(f"加载 {len(strategies)} 个策略")
    
    strategy_results = {s.strategy_id: StrategyBacktestResult(strategy_id=s.strategy_id) for s in strategies}
    strategy_backtests = {s.strategy_id: BacktestEngine(initial_capital=10000.0, leverage=50, stop_loss_pct=0.10, compound=False) for s in strategies}
    
    exit_timers = defaultdict(deque)
    
    progress_step = 10000
    for idx in range(100, len(df)):
        if idx % progress_step == 0:
            logger.info(f"进度: {idx}/{len(df)} ({idx/len(df)*100:.1f}%)")
            
        row = df.iloc[idx]
        current_price = row['close']
        current_time = row['timestamp']
        data = get_strategy_data_dict(df, idx)
        
        # 处理离场定时器
        to_remove = []
        for strategy_id, exit_info in list(exit_timers.items()):
            if exit_info and exit_info[0] <= idx:
                trade = strategy_backtests[strategy_id].active_positions.get(f"{strategy_id}")
                if trade:
                    strategy_backtests[strategy_id].exit_position(
                        trade=trade,
                        exit_price=current_price,
                        exit_time=current_time
                    )
                    strategy_results[strategy_id].trades.append(trade)
                to_remove.append((strategy_id, exit_info.popleft()))
                
        # 检查止损
        for strategy_id, bt in strategy_backtests.items():
            for key, trade in list(bt.active_positions.items()):
                if bt.check_stop_loss(trade, current_price):
                    bt.exit_position(
                        trade=trade,
                        exit_price=current_price,
                        exit_time=current_time,
                        stopped_out=True
                    )
                    strategy_results[strategy_id].trades.append(trade)
                    if (strategy_id, idx) in exit_timers:
                        exit_timers[strategy_id].clear()
        
        # 处理新信号
        for strategy in strategies:
            signal = strategy.calculate(data)
            if signal and (signal.action == "long" or signal.action == "short"):
                direction = "long" if signal.action == "long" else "short"
                strategy_id = strategy.strategy_id
                bt = strategy_backtests[strategy_id]
                
                key = f"{strategy_id}"
                if key not in bt.active_positions:
                    trade = bt.enter_position(
                        strategy_id=strategy_id,
                        direction=direction,
                        price=current_price,
                        timestamp=current_time
                    )
                    
                    if trade:
                        exit_idx = idx + 12
                        exit_timers[strategy_id].append(exit_idx)
    
    # 计算每个策略的结果
    final_results = {}
    for strategy_id, bt in strategy_backtests.items():
        results = bt.get_results()
        final_results[strategy_id] = results
        final_results[strategy_id]['trades'] = strategy_results[strategy_id].trades
        
    # 组合结果
    combined_results = backtest.get_results()
    
    return final_results, combined_results


def print_report(final_results, combined_results):
    """打印回测报告"""
    print("\n" + "=" * 160)
    print("2022年全年策略回测报告")
    print("=" * 160)
    print(f"{'策略ID':<40} {'交易数':>8} {'胜率':>8} {'总收益(%)':>12} {'总收益($)':>12} {'夏普':>10} {'最大回撤':>12} {'最终资金':>12}")
    print("-" * 160)
    
    sorted_strategies = sorted(final_results.items(), key=lambda x: x[1]['sharpe'] if 'sharpe' in x[1] else -1000000, reverse=True)
    
    for strategy_id, res in sorted_strategies:
        trades = res.get('total_trades', 0)
        win_rate = res.get('win_rate', 0)
        profit_pct = res.get('total_profit_pct', 0)
        profit_usd = res.get('total_profit_usd', 0)
        sharpe = res.get('sharpe', 0)
        max_dd = res.get('max_drawdown', 0)
        final_cap = res.get('final_capital', 0)
        
        if trades == 0:
            continue
            
        print(
            f"{strategy_id:<40} "
            f"{trades:>8} "
            f"{win_rate:>8.1%} "
            f"{profit_pct:>12.2f}% "
            f"${profit_usd:>11,.2f} "
            f"{sharpe:>10.2f} "
            f"{max_dd:>12.1%} "
            f"${final_cap:>11,.2f}"
        )
    
    print("-" * 160)
    print(f"\n{'组合结果':<40} "
          f"{combined_results['total_trades']:>8} "
          f"{combined_results['win_rate']:>8.1%} "
          f"{combined_results['total_profit_pct']:>12.2f}% "
          f"${combined_results['total_profit_usd']:>11,.2f} "
          f"{combined_results['sharpe']:>10.2f} "
          f"{combined_results['max_drawdown']:>12.1%} "
          f"${combined_results['final_capital']:>11,.2f}")
    print(f"\n回测条件：本金 $10,000，50倍杠杆，10%止损，非复利")
    print("=" * 160)


def main():
    print("\n" + "=" * 160)
    print("2022年全年策略回测 - 数据源：数据湖")
    print("=" * 160)
    print()
    
    df_1min = load_year_data(symbol="BTCUSDT", year=2022)
    if df_1min.empty:
        logger.error("加载数据失败")
        return
        
    df_5m = resample_to_5min(df_1min)
    df = compute_features(df_5m)
    
    final_results, combined_results = run_full_backtest(df)
    print_report(final_results, combined_results)
    
    return final_results, combined_results


if __name__ == "__main__":
    final_results, combined_results = main()
