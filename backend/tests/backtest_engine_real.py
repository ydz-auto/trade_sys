#!/usr/bin/env python3
"""
真实回测引擎
- 10000美元本金
- 50倍杠杆
- 10%止损
- 非复利
- 根据信号止盈
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from infrastructure.logging import get_logger
logger = get_logger("real_backtest")


DATA_LAKE_ROOT = Path("/Volumes/00_crypto/00_code/backend/data_lake")


@dataclass
class Position:
    """持仓"""
    strategy_id: str
    direction: str  # "long" or "short"
    entry_price: float
    entry_time: pd.Timestamp
    size_usd: float
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass
class Trade:
    """交易记录"""
    strategy_id: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    size_usd: float
    pnl: float
    pnl_pct: float
    exit_reason: str


class BacktestEngine:
    """
    回测引擎
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        leverage: int = 50,
        stop_loss_pct: float = 0.10,
        position_size_pct: float = 0.10,
        compound: bool = False,
        min_position_size: float = 10.0
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.position_size_pct = position_size_pct
        self.compound = compound
        self.min_position_size = min_position_size
        
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.timestamp_history: List[pd.Timestamp] = []
        
        self._strategy_stats: Dict[str, Dict] = defaultdict(lambda: {
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "trades": []
        })
        
    def calculate_position_size(self, current_price: float) -> float:
        """计算仓位大小"""
        capital_for_position = self.initial_capital if not self.compound else self.current_capital
        position_size_usd = max(capital_for_position * self.position_size_pct, self.min_position_size)
        return position_size_usd
    
    def enter_position(
        self,
        strategy_id: str,
        direction: str,
        entry_price: float,
        entry_time: pd.Timestamp
    ) -> Optional[Position]:
        """开仓"""
        if strategy_id in self.positions:
            return None
            
        position_size_usd = self.calculate_position_size(entry_price)
        if position_size_usd > self.current_capital * 1.5:
            logger.warning(f"资金不足: {self.current_capital:.2f} < {position_size_usd:.2f}")
            return None
            
        stop_loss_price = None
        if direction == "long":
            stop_loss_price = entry_price * (1 - self.stop_loss_pct / self.leverage)
        else:
            stop_loss_price = entry_price * (1 + self.stop_loss_pct / self.leverage)
            
        position = Position(
            strategy_id=strategy_id,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            size_usd=position_size_usd,
            stop_loss_price=stop_loss_price
        )
        
        self.positions[strategy_id] = position
        logger.debug(f"开仓: {strategy_id} {direction} @ {entry_price:.2f}, 规模 ${position_size_usd:.2f}")
        
        return position
    
    def exit_position(
        self,
        strategy_id: str,
        exit_price: float,
        exit_time: pd.Timestamp,
        exit_reason: str = "signal"
    ) -> Optional[Trade]:
        """平仓"""
        if strategy_id not in self.positions:
            return None
            
        position = self.positions.pop(strategy_id)
        
        if position.direction == "long":
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - exit_price) / position.entry_price
            
        pnl = pnl_pct * position.size_usd * self.leverage
        
        self.current_capital += pnl
        
        trade = Trade(
            strategy_id=strategy_id,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=exit_time,
            size_usd=position.size_usd,
            pnl=pnl,
            pnl_pct=pnl_pct * self.leverage,
            exit_reason=exit_reason
        )
        
        self.trades.append(trade)
        
        if pnl > 0:
            self._strategy_stats[strategy_id]["wins"] += 1
        else:
            self._strategy_stats[strategy_id]["losses"] += 1
        self._strategy_stats[strategy_id]["total_pnl"] += pnl
        self._strategy_stats[strategy_id]["trades"].append(trade)
        
        logger.debug(f"平仓: {strategy_id} {position.direction} @ {exit_price:.2f}, P&L ${pnl:.2f} ({pnl_pct*100*self.leverage:.2f}%)")
        
        return trade
    
    def check_stop_loss(self, current_price: float, current_time: pd.Timestamp) -> List[Trade]:
        """检查止损"""
        closed_trades = []
        for strategy_id, position in list(self.positions.items()):
            if position.stop_loss_price is None:
                continue
                
            should_close = False
            if position.direction == "long" and current_price <= position.stop_loss_price:
                should_close = True
            elif position.direction == "short" and current_price >= position.stop_loss_price:
                should_close = True
                
            if should_close:
                trade = self.exit_position(strategy_id, position.stop_loss_price, current_time, "stop_loss")
                if trade:
                    closed_trades.append(trade)
                    
        return closed_trades
    
    def update_equity(self, current_price: float, current_time: pd.Timestamp):
        """更新权益曲线"""
        unrealized_pnl = 0.0
        
        for position in self.positions.values():
            if position.direction == "long":
                unrealized_pnl_pct = (current_price - position.entry_price) / position.entry_price
            else:
                unrealized_pnl_pct = (position.entry_price - current_price) / position.entry_price
            unrealized_pnl += unrealized_pnl_pct * position.size_usd * self.leverage
            
        total_equity = self.current_capital + unrealized_pnl
        self.equity_curve.append(total_equity)
        self.timestamp_history.append(current_time)
    
    def get_summary(self) -> Dict:
        """获取回测摘要"""
        if not self.equity_curve:
            return {}
            
        equity_series = pd.Series(self.equity_curve, index=self.timestamp_history)
        initial = self.initial_capital
        final = self.equity_curve[-1]
        
        returns = equity_series.pct_change().dropna()
        
        total_return = (final - initial) / initial
        daily_returns = equity_series.resample('D').last().pct_change().dropna()
        
        sharpe = 0.0
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(365)
            
        max_drawdown = 0.0
        if len(equity_series) > 1:
            rolling_max = equity_series.cummax()
            drawdown = (equity_series - rolling_max) / rolling_max
            max_drawdown = drawdown.min()
            
        win_rate = 0.0
        if len(self.trades) > 0:
            win_rate = sum(1 for t in self.trades if t.pnl > 0) / len(self.trades)
            
        return {
            "initial_capital": initial,
            "final_equity": final,
            "total_return_pct": total_return * 100,
            "total_trades": len(self.trades),
            "win_rate": win_rate * 100,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_drawdown * 100,
            "avg_trade_pnl": np.mean([t.pnl for t in self.trades]) if self.trades else 0,
            "best_trade": max([t.pnl for t in self.trades]) if self.trades else 0,
            "worst_trade": min([t.pnl for t in self.trades]) if self.trades else 0,
            "strategy_stats": dict(self._strategy_stats)
        }


def load_year_data(symbol: str = "BTCUSDT", year: int = 2022) -> pd.DataFrame:
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


def resample_to_5min(df_1min: pd.DataFrame) -> pd.DataFrame:
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


def compute_features(df_5m: pd.DataFrame) -> pd.DataFrame:
    """计算所有特征"""
    logger.info("开始计算特征...")
    df = df_5m.copy()
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd_line'] = ema12 - ema26
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd_line'] - df['macd_signal']
    
    df['bb_middle'] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(14).mean()
    
    df['ema_10'] = close.ewm(span=10, adjust=False).mean()
    df['ema_50'] = close.ewm(span=50, adjust=False).mean()
    df['sma_10'] = close.rolling(10).mean()
    df['sma_50'] = close.rolling(50).mean()
    
    vol_avg_288 = volume.rolling(288, min_periods=20).mean()
    df['volume_ratio'] = volume / (vol_avg_288 + 1e-10)
    
    df['return_1h'] = close.pct_change(12)
    df['return_4h'] = close.pct_change(48)
    df['return_24h'] = close.pct_change(288)
    
    df['volatility_24h'] = close.pct_change().rolling(288).std() * np.sqrt(288)
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
    df['upper_shadow_ratio'] = (high - pd.concat([close, close.shift(1)], axis=1).max(axis=1)) / (high - low + 1e-10)
    df['sweep_score'] = (df['trade_delta'].abs() / (volume + 1e-10)).rolling(12).max()
    df['liquidation_spike'] = (df['return_1h'].abs() > 0.015) & (df['volume_ratio'] > 1.5)
    df['long_liquidations_spike'] = (df['return_1h'] < -0.015) & (df['volume_ratio'] > 1.5)
    
    df = df.dropna(subset=['close', 'volume', 'rsi_14']).reset_index(drop=True)
    logger.info(f"特征计算完成: {len(df)} 条K线")
    
    return df


def initialize_strategies():
    """初始化所有策略"""
    from engines.compute.strategy.strategies import (
        RSIStrategy, MACDStrategy,
        PanicReversalStrategy, LongLiquidationBounceStrategy,
        VolumeClimaxFadeStrategy, WeakBounceShortStrategy,
        OIFlushStrategy, ShortSqueezeStrategy,
        FundingExhaustionTrapStrategy, DeadCatEchoStrategy,
        ImbalancePressureStrategy, SweepDetectionStrategy,
        LiquidityVacuumStrategy, AggressiveFlowStrategy,
        BreakoutStrategy, TrendFollowingStrategy,
        VolatilityExpansionStrategy, BBCompressionBreakoutStrategy,
        MomentumIgnitionStrategy
    )
    
    strategies = [
        RSIStrategy(strategy_id="rsi_14"),
        MACDStrategy(strategy_id="macd"),
        PanicReversalStrategy(strategy_id="panic_reversal"),
        LongLiquidationBounceStrategy(strategy_id="long_liquidation_bounce"),
        VolumeClimaxFadeStrategy(strategy_id="volume_climax_fade"),
        WeakBounceShortStrategy(strategy_id="weak_bounce_short"),
        OIFlushStrategy(strategy_id="oi_flush"),
        ShortSqueezeStrategy(strategy_id="short_squeeze"),
        FundingExhaustionTrapStrategy(strategy_id="funding_exhaustion_trap"),
        DeadCatEchoStrategy(strategy_id="dead_cat_echo"),
        ImbalancePressureStrategy(strategy_id="imbalance_pressure"),
        SweepDetectionStrategy(strategy_id="sweep_detection"),
        LiquidityVacuumStrategy(strategy_id="liquidity_vacuum"),
        AggressiveFlowStrategy(strategy_id="aggressive_flow"),
        BreakoutStrategy(strategy_id="breakout"),
        TrendFollowingStrategy(strategy_id="trend_following"),
        VolatilityExpansionStrategy(strategy_id="volatility_expansion"),
        BBCompressionBreakoutStrategy(strategy_id="bb_compression_breakout"),
        MomentumIgnitionStrategy(strategy_id="momentum_ignition"),
    ]
    
    return strategies


def get_strategy_data_dict(df: pd.DataFrame, idx: int) -> Dict:
    """为策略准备数据字典"""
    row = df.iloc[idx]
    return {
        'close_prices': df['close'].iloc[max(0, idx-300):idx+1].tolist(),
        'high_prices': df['high'].iloc[max(0, idx-300):idx+1].tolist(),
        'low_prices': df['low'].iloc[max(0, idx-300):idx+1].tolist(),
        'volumes': df['volume'].iloc[max(0, idx-300):idx+1].tolist(),
        'symbol': 'BTCUSDT',
        'rsi_14': row.get('rsi_14', 50),
        'funding_zscore': 0,
        'funding_delta': 0,
        'oi_delta': 0,
        'oi_zscore': 0,
        'liquidation_spike': bool(row.get('liquidation_spike', False)),
        'long_liquidations_spike': bool(row.get('long_liquidations_spike', False)),
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
        'sweep_buy_score': row.get('sweep_score', 0),
        'sweep_sell_score': row.get('sweep_score', 0),
        'liquidity_vacuum': row.get('spread', 0),
        'close': row.get('close', 0),
        'high': row.get('high', 0),
        'low': row.get('low', 0),
        'volume': row.get('volume', 0),
        'macd_line': row.get('macd_line', 0),
        'macd_signal': row.get('macd_signal', 0),
        'ema_10': row.get('ema_10', 0),
        'ema_50': row.get('ema_50', 0),
        'sma_10': row.get('sma_10', 0),
        'sma_50': row.get('sma_50', 0),
        'return_1h': row.get('return_1h', 0),
        'return_4h': row.get('return_4h', 0),
    }


def run_backtest(df: pd.DataFrame, strategies, engine: BacktestEngine):
    """运行回测"""
    from engines.compute.strategy.strategies import ActionType
    
    logger.info(f"开始回测，时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    
    HOLDING_PERIOD_K = 48  # 4小时止盈
    
    for idx in range(200, len(df)):
        current_time = df['timestamp'].iloc[idx]
        current_price = df['close'].iloc[idx]
        
        engine.check_stop_loss(current_price, current_time)
        
        data = get_strategy_data_dict(df, idx)
        
        for strategy in strategies:
            if not strategy.is_enabled:
                continue
                
            signal = strategy.calculate(data)
            
            if signal is None:
                continue
                
            strategy_id = strategy.strategy_id
            direction = "long" if signal.action == ActionType.LONG else "short"
            
            if strategy_id in engine.positions:
                existing_position = engine.positions[strategy_id]
                if (existing_position.direction == "long" and direction == "short") or \
                   (existing_position.direction == "short" and direction == "long"):
                    engine.exit_position(strategy_id, current_price, current_time, "reversal")
                    engine.enter_position(strategy_id, direction, current_price, current_time)
                continue
                
            engine.enter_position(strategy_id, direction, current_price, current_time)
        
        for strategy_id, position in list(engine.positions.items()):
            holding_period = (current_time - position.entry_time).total_seconds() / 60 / 5
            if holding_period >= HOLDING_PERIOD_K:
                engine.exit_position(strategy_id, current_price, current_time, "time_stop")
                
        engine.update_equity(current_price, current_time)
        
        if idx % 5000 == 0:
            logger.info(f"进度: {idx}/{len(df)}, 权益: ${engine.current_capital:.2f}, 持仓: {len(engine.positions)}")
            
    logger.info("回测完成")


def print_summary(summary: Dict):
    """打印回测摘要"""
    print("\n" + "=" * 120)
    print("真实回测结果")
    print("=" * 120)
    print(f"初始本金: ${summary['initial_capital']:.2f}")
    print(f"最终权益: ${summary['final_equity']:.2f}")
    print(f"总收益率: {summary['total_return_pct']:.2f}%")
    print(f"夏普比率: {summary['sharpe_ratio']:.2f}")
    print(f"最大回撤: {summary['max_drawdown_pct']:.2f}%")
    print(f"总交易次数: {summary['total_trades']}")
    print(f"胜率: {summary['win_rate']:.2f}%")
    print(f"平均交易盈亏: ${summary['avg_trade_pnl']:.2f}")
    print(f"最佳交易: ${summary['best_trade']:.2f}")
    print(f"最差交易: ${summary['worst_trade']:.2f}")
    
    print("\n各策略表现:")
    print("-" * 80)
    print(f"{'策略':<30} {'交易':>8} {'胜':>8} {'负':>8} {'总盈亏':>12} {'胜率':>10}")
    print("-" * 80)
    
    for strategy_id, stats in summary['strategy_stats'].items():
        wins = stats['wins']
        losses = stats['losses']
        total = wins + losses
        total_pnl = stats['total_pnl