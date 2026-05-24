#!/usr/bin/env python3
"""
全策略真实数据回测

使用 2026-04 一个月的 BTCUSDT 1m K线 + funding + OI 数据
构建 5m 特征，跑全部 21 个策略 + Confluence + Regime
"""

import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_LAKE = Path('/Volumes/00_crypto/00_code/backend/data_lake')


def load_klines(symbol: str = 'BTCUSDT', year: int = 2026, month: int = 4) -> pd.DataFrame:
    path = DATA_LAKE / f'crypto/binance/klines/symbol={symbol}/year={year}/month={month:02d}/data.parquet'
    if not path.exists():
        raise FileNotFoundError(f'Klines not found: {path}')
    df = pd.read_parquet(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df = df.sort_values('timestamp').reset_index(drop=True)
    print(f'Loaded klines: {len(df)} rows, {df["timestamp"].min()} ~ {df["timestamp"].max()}')
    return df


def load_funding(symbol: str = 'BTCUSDT') -> pd.DataFrame:
    path = DATA_LAKE / f'crypto/binance/funding/symbol={symbol}/data.parquet'
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['fundingRate'] = pd.to_numeric(df['fundingRate'], errors='coerce')
    df['markPrice'] = pd.to_numeric(df['markPrice'], errors='coerce')
    df = df.dropna(subset=['fundingRate']).reset_index(drop=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    print(f'Loaded funding: {len(df)} rows, {df["timestamp"].min()} ~ {df["timestamp"].max()}')
    return df


def load_oi(symbol: str = 'BTCUSDT') -> pd.DataFrame:
    path = DATA_LAKE / f'crypto/binance/oi/symbol={symbol}/data.parquet'
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['sumOpenInterest'] = pd.to_numeric(df['sumOpenInterest'], errors='coerce')
    df['sumOpenInterestValue'] = pd.to_numeric(df['sumOpenInterestValue'], errors='coerce')
    df = df.dropna(subset=['sumOpenInterest']).reset_index(drop=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    print(f'Loaded OI: {len(df)} rows, {df["timestamp"].min()} ~ {df["timestamp"].max()}')
    return df


def resample_5m(klines: pd.DataFrame) -> pd.DataFrame:
    df = klines.set_index('timestamp')
    ohlc = df['close'].resample('5min').ohlc()
    ohlc.columns = ['open', 'high', 'low', 'close']
    ohlc['high'] = df['high'].resample('5min').max()
    ohlc['low'] = df['low'].resample('5min').min()
    ohlc['open'] = df['open'].resample('5min').first()
    ohlc['volume'] = df['volume'].resample('5min').sum()
    ohlc['quote_volume'] = df['quote_volume'].resample('5min').sum() if 'quote_volume' in df.columns else 0
    ohlc['taker_buy_volume'] = df['taker_buy_volume'].resample('5min').sum() if 'taker_buy_volume' in df.columns else 0
    ohlc = ohlc.dropna().reset_index()
    print(f'Resampled to 5m: {len(ohlc)} rows')
    return ohlc


def compute_features(df_5m: pd.DataFrame, funding: pd.DataFrame, oi: pd.DataFrame) -> pd.DataFrame:
    df = df_5m.copy()

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['rsi_14'] = 100.0 - (100.0 / (1.0 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd_line'] = ema12 - ema26
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd_line'] - df['macd_signal']

    # Bollinger Bands
    df['bb_middle'] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std

    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(14).mean()

    # EMA
    df['ema_10'] = close.ewm(span=10, adjust=False).mean()
    df['ema_50'] = close.ewm(span=50, adjust=False).mean()

    # SMA
    df['sma_10'] = close.rolling(10).mean()
    df['sma_50'] = close.rolling(50).mean()

    # Volume ratio
    df['volume_ratio'] = volume / (volume.rolling(288, min_periods=20).mean() + 1e-10)

    # Returns
    df['return_1h'] = close.pct_change(12)
    df['return_4h'] = close.pct_change(48)
    df['return_24h'] = close.pct_change(288)

    # Volatility
    df['volatility_24h'] = close.pct_change().rolling(288).std() * np.sqrt(288)

    # Trend strength
    returns = close.pct_change()
    df['trend_strength'] = returns.rolling(48).mean().abs() / (returns.rolling(48).std() + 1e-10)

    # Funding features
    if not funding.empty:
        fund_5m = funding.set_index('timestamp')['fundingRate'].resample('5min').ffill().dropna()
        fund_5m = fund_5m.reindex(df['timestamp'], method='ffill')
        df['funding_rate'] = fund_5m.values
        df['funding_zscore'] = (df['funding_rate'] - df['funding_rate'].rolling(288, min_periods=20).mean()) / (df['funding_rate'].rolling(288, min_periods=20).std() + 1e-10)
        df['funding_delta'] = df['funding_rate'].diff(12)
    else:
        df['funding_rate'] = 0.0
        df['funding_zscore'] = 0.0
        df['funding_delta'] = 0.0

    # OI features
    if not oi.empty:
        oi_5m = oi.set_index('timestamp')['sumOpenInterest'].resample('5min').ffill().dropna()
        oi_5m = oi_5m.reindex(df['timestamp'], method='ffill')
        df['open_interest'] = oi_5m.values
        df['oi_delta'] = df['open_interest'].pct_change(288)
        df['oi_zscore'] = (df['oi_delta'] - df['oi_delta'].rolling(288, min_periods=20).mean()) / (df['oi_delta'].rolling(288, min_periods=20).std() + 1e-10)
    else:
        df['open_interest'] = 0.0
        df['oi_delta'] = 0.0
        df['oi_zscore'] = 0.0

    # Microstructure proxy features (from kline data)
    df['spread'] = (high - low) / (close + 1e-10)
    df['imbalance_5'] = (df['taker_buy_volume'] - (volume - df['taker_buy_volume'])) / (volume + 1e-10)
    df['trade_delta'] = df['taker_buy_volume'] - (volume - df['taker_buy_volume'])
    df['cumulative_delta'] = df['trade_delta'].rolling(12).sum()
    df['aggressive_buy_volume'] = df['taker_buy_volume']
    df['aggressive_sell_volume'] = volume - df['taker_buy_volume']
    df['depth_ratio'] = df['imbalance_5'].rolling(12).mean()
    df['microprice'] = close + df['imbalance_5'] * (high - low) * 0.1
    df['sweep_score'] = (df['trade_delta'].abs() / (volume + 1e-10)).rolling(12).max()
    df['liquidity_vacuum'] = df['spread'].rolling(12).max() / (df['spread'].rolling(288).mean() + 1e-10)
    df['cancel_rate'] = 0.0
    df['top5_depth'] = volume.rolling(12).mean()

    # Upper shadow ratio
    df['upper_shadow_ratio'] = (high - pd.concat([close, close.shift(1)], axis=1).max(axis=1)) / (high - low + 1e-10)

    # Short pressure proxy
    df['short_pressure'] = (-df['funding_zscore']).clip(lower=0) / 3.0

    # Liquidation spike proxy
    df['liquidation_spike'] = (df['return_1h'].abs() > 0.02) & (df['volume_ratio'] > 2.0)
    df['long_liquidations_spike'] = (df['return_1h'] < -0.02) & (df['volume_ratio'] > 2.0)

    # BB width for compression
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['bb_middle'] + 1e-10)

    # Future return for backtesting
    df['future_ret_1h'] = close.shift(-12) / close - 1
    df['future_ret_4h'] = close.shift(-48) / close - 1

    df = df.dropna(subset=['close', 'volume', 'rsi_14'])
    print(f'Features computed: {len(df)} rows, {len(df.columns)} columns')
    return df


def run_backtest(df: pd.DataFrame) -> dict:
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
        MomentumIgnitionStrategy,
        LeadLagStrategy, PremiumDivergenceStrategy,
        ActionType,
    )

    strategies = [
        RSIStrategy(strategy_id='rsi'),
        MACDStrategy(strategy_id='macd'),
        PanicReversalStrategy(strategy_id='panic_reversal'),
        LongLiquidationBounceStrategy(strategy_id='long_liquidation_bounce'),
        VolumeClimaxFadeStrategy(strategy_id='volume_climax_fade'),
        WeakBounceShortStrategy(strategy_id='weak_bounce_short'),
        OIFlushStrategy(strategy_id='oi_flush'),
        ShortSqueezeStrategy(strategy_id='short_squeeze'),
        FundingExhaustionTrapStrategy(strategy_id='funding_exhaustion_trap'),
        DeadCatEchoStrategy(strategy_id='dead_cat_echo'),
        ImbalancePressureStrategy(strategy_id='imbalance_pressure'),
        SweepDetectionStrategy(strategy_id='sweep_detection'),
        LiquidityVacuumStrategy(strategy_id='liquidity_vacuum'),
        AggressiveFlowStrategy(strategy_id='aggressive_flow'),
        BreakoutStrategy(strategy_id='breakout'),
        TrendFollowingStrategy(strategy_id='trend_following'),
        VolatilityExpansionStrategy(strategy_id='volatility_expansion'),
        BBCompressionBreakoutStrategy(strategy_id='bb_compression_breakout'),
        MomentumIgnitionStrategy(strategy_id='momentum_ignition'),
        LeadLagStrategy(strategy_id='lead_lag'),
        PremiumDivergenceStrategy(strategy_id='premium_divergence'),
    ]

    results = {}

    for strategy in strategies:
        signals = []
        trade_returns = []

        for i in range(100, len(df)):
            row = df.iloc[i]
            data = {
                'close_prices': df['close'].iloc[max(0, i-300):i+1].tolist(),
                'high_prices': df['high'].iloc[max(0, i-300):i+1].tolist(),
                'low_prices': df['low'].iloc[max(0, i-300):i+1].tolist(),
                'volumes': df['volume'].iloc[max(0, i-300):i+1].tolist(),
                'symbol': 'BTCUSDT',
                'rsi_14': row.get('rsi_14', 50),
                'funding_zscore': row.get('funding_zscore', 0),
                'funding_delta': row.get('funding_delta', 0),
                'funding_divergence': row.get('funding_delta', 0),
                'oi_delta': row.get('oi_delta', 0),
                'oi_zscore': row.get('oi_zscore', 0),
                'liquidation_spike': bool(row.get('liquidation_spike', False)),
                'long_liquidations_spike': bool(row.get('long_liquidations_spike', False)),
                'oi_24h_change': row.get('oi_delta', 0),
                'volume_ratio': row.get('volume_ratio', 1.0),
                'imbalance_5': row.get('imbalance_5', 0),
                'depth_ratio': row.get('depth_ratio', 0),
                'microprice': row.get('microprice', row.get('close', 0)),
                'mid_price': row.get('close', 0),
                'trade_delta': row.get('trade_delta', 0),
                'sweep_buy_score': row.get('sweep_score', 0),
                'sweep_sell_score': row.get('sweep_score', 0),
                'liquidity_vacuum': row.get('liquidity_vacuum', 0),
                'spread': row.get('spread', 0),
                'spread_volatility': row.get('spread', 0),
                'top5_depth': row.get('top5_depth', 0),
                'cancel_rate': row.get('cancel_rate', 0),
                'cumulative_delta': row.get('cumulative_delta', 0),
                'aggressive_buy_volume': row.get('aggressive_buy_volume', 0),
                'aggressive_sell_volume': row.get('aggressive_sell_volume', 0),
                'short_pressure': row.get('short_pressure', 0),
                'bb_upper': row.get('bb_upper', 0),
                'bb_lower': row.get('bb_lower', 0),
                'bb_middle': row.get('bb_middle', 0),
                'bb_width': row.get('bb_width', 0),
                'binance_return': row.get('return_1h', 0),
                'okx_return': row.get('return_1h', 0) * 0.98,
                'basis': row.get('funding_rate', 0) * 100,
                'premium': row.get('funding_rate', 0) * 50,
                'spread_cross_exchange': 0.0,
                'upper_shadow_ratio': row.get('upper_shadow_ratio', 0),
            }

            signal = strategy.calculate(data)
            if signal is not None:
                future_ret = row.get('future_ret_1h', None)
                if future_ret is not None and not np.isnan(future_ret):
                    direction = 1 if signal.action == ActionType.LONG else -1
                    trade_ret = future_ret * direction
                    trade_returns.append(trade_ret)
                    signals.append({
                        'timestamp': row.get('timestamp', None),
                        'action': signal.action.value,
                        'confidence': signal.confidence,
                        'reason': signal.reason,
                        'return': trade_ret,
                        'win': trade_ret > 0,
                    })

        if trade_returns:
            wins = sum(1 for r in trade_returns if r > 0)
            results[strategy.strategy_id] = {
                'signals': len(signals),
                'wins': wins,
                'win_rate': wins / len(trade_returns),
                'avg_return': np.mean(trade_returns),
                'total_return': np.sum(trade_returns),
                'sharpe': np.mean(trade_returns) / (np.std(trade_returns) + 1e-8) * np.sqrt(365 * 288),
                'max_return': max(trade_returns),
                'min_return': min(trade_returns),
            }
        else:
            results[strategy.strategy_id] = {
                'signals': 0, 'wins': 0, 'win_rate': 0,
                'avg_return': 0, 'total_return': 0, 'sharpe': 0,
                'max_return': 0, 'min_return': 0,
            }

    return results


def run_confluence_test(df: pd.DataFrame) -> dict:
    from engines.compute.strategy.strategies import (
        StrategySignal, StrategyType, ActionType,
        PanicReversalStrategy, OIFlushStrategy, ShortSqueezeStrategy,
        FundingExhaustionTrapStrategy, DeadCatEchoStrategy,
        BreakoutStrategy, TrendFollowingStrategy,
        MomentumIgnitionStrategy, ImbalancePressureStrategy,
        AggressiveFlowStrategy,
    )
    from engines.compute.signal.confluence_engine import SignalConfluenceEngine

    strategies = [
        PanicReversalStrategy(strategy_id='panic_reversal'),
        OIFlushStrategy(strategy_id='oi_flush'),
        ShortSqueezeStrategy(strategy_id='short_squeeze'),
        FundingExhaustionTrapStrategy(strategy_id='funding_exhaustion_trap'),
        DeadCatEchoStrategy(strategy_id='dead_cat_echo'),
        BreakoutStrategy(strategy_id='breakout'),
        TrendFollowingStrategy(strategy_id='trend_following'),
        MomentumIgnitionStrategy(strategy_id='momentum_ignition'),
        ImbalancePressureStrategy(strategy_id='imbalance_pressure'),
        AggressiveFlowStrategy(strategy_id='aggressive_flow'),
    ]

    engine = SignalConfluenceEngine(min_confidence=0.3)

    confluence_trades = []
    raw_trades = []

    for i in range(100, len(df)):
        row = df.iloc[i]
        data = {
            'close_prices': df['close'].iloc[max(0, i-300):i+1].tolist(),
            'high_prices': df['high'].iloc[max(0, i-300):i+1].tolist(),
            'low_prices': df['low'].iloc[max(0, i-300):i+1].tolist(),
            'volumes': df['volume'].iloc[max(0, i-300):i+1].tolist(),
            'symbol': 'BTCUSDT',
            'rsi_14': row.get('rsi_14', 50),
            'funding_zscore': row.get('funding_zscore', 0),
            'funding_delta': row.get('funding_delta', 0),
            'funding_divergence': row.get('funding_delta', 0),
            'oi_delta': row.get('oi_delta', 0),
            'oi_zscore': row.get('oi_zscore', 0),
            'liquidation_spike': bool(row.get('liquidation_spike', False)),
            'long_liquidations_spike': bool(row.get('long_liquidations_spike', False)),
            'oi_24h_change': row.get('oi_delta', 0),
            'volume_ratio': row.get('volume_ratio', 1.0),
            'imbalance_5': row.get('imbalance_5', 0),
            'depth_ratio': row.get('depth_ratio', 0),
            'microprice': row.get('microprice', row.get('close', 0)),
            'mid_price': row.get('close', 0),
            'trade_delta': row.get('trade_delta', 0),
            'sweep_buy_score': row.get('sweep_score', 0),
            'sweep_sell_score': row.get('sweep_score', 0),
            'liquidity_vacuum': row.get('liquidity_vacuum', 0),
            'spread': row.get('spread', 0),
            'spread_volatility': row.get('spread', 0),
            'top5_depth': row.get('top5_depth', 0),
            'cancel_rate': row.get('cancel_rate', 0),
            'cumulative_delta': row.get('cumulative_delta', 0),
            'aggressive_buy_volume': row.get('aggressive_buy_volume', 0),
            'aggressive_sell_volume': row.get('aggressive_sell_volume', 0),
            'short_pressure': row.get('short_pressure', 0),
            'bb_upper': row.get('bb_upper', 0),
            'bb_lower': row.get('bb_lower', 0),
            'bb_middle': row.get('bb_middle', 0),
            'bb_width': row.get('bb_width', 0),
            'upper_shadow_ratio': row.get('upper_shadow_ratio', 0),
        }

        all_signals = []
        for strategy in strategies:
            signal = strategy.calculate(data)
            if signal is not None:
                all_signals.append(signal)
                future_ret = row.get('future_ret_1h', None)
                if future_ret is not None and not np.isnan(future_ret):
                    direction = 1 if signal.action == ActionType.LONG else -1
                    raw_trades.append(future_ret * direction)

        if all_signals:
            confluence_signals = engine.process_signals(all_signals, regime=None)
            for cs in confluence_signals:
                future_ret = row.get('future_ret_1h', None)
                if future_ret is not None and not np.isnan(future_ret):
                    direction = 1 if cs.direction == 'long' else -1
                    confluence_trades.append({
                        'return': future_ret * direction,
                        'confidence': cs.confidence,
                        'confluence_score': cs.confluence_score,
                        'strategy_count': cs.strategy_count,
                        'has_conflict': cs.has_conflict,
                        'is_strong': cs.is_strong,
                    })

    return {
        'raw': raw_trades,
        'confluence': confluence_trades,
    }


def main():
    print('=' * 80)
    print('全策略真实数据回测 - BTCUSDT 2026-04')
    print('=' * 80)
    print()

    # 1. Load data
    print('[1/4] 加载数据...')
    klines = load_klines('BTCUSDT', 2026, 4)
    funding = load_funding('BTCUSDT')
    oi = load_oi('BTCUSDT')
    print()

    # 2. Resample & compute features
    print('[2/4] 构建5m特征...')
    df_5m = resample_5m(klines)
    df = compute_features(df_5m, funding, oi)
    print()

    # 3. Run individual strategy backtest
    print('[3/4] 运行21个策略回测...')
    results = run_backtest(df)
    print()

    # 4. Print results
    print('=' * 80)
    print('策略回测结果')
    print('=' * 80)
    print(f'{"策略":<30s} {"信号数":>6s} {"胜率":>7s} {"平均收益":>9s} {"总收益":>9s} {"Sharpe":>8s}')
    print('-' * 80)

    categories = {
        '趋势/动量': ['rsi', 'macd', 'breakout', 'trend_following', 'volatility_expansion', 'bb_compression_breakout', 'momentum_ignition'],
        '行为策略': ['panic_reversal', 'long_liquidation_bounce', 'oi_flush', 'short_squeeze', 'funding_exhaustion_trap', 'dead_cat_echo', 'volume_climax_fade', 'weak_bounce_short'],
        '微结构': ['imbalance_pressure', 'sweep_detection', 'liquidity_vacuum', 'aggressive_flow'],
        '跨交易所': ['lead_lag', 'premium_divergence'],
    }

    for cat, ids in categories.items():
        print(f'\n--- {cat} ---')
        for sid in ids:
            r = results.get(sid, {})
            if r.get('signals', 0) > 0:
                print(f'  {sid:<28s} {r["signals"]:>6d} {r["win_rate"]:>6.1%} {r["avg_return"]:>8.4f}% {r["total_return"]:>8.2f}% {r["sharpe"]:>8.2f}')
            else:
                print(f'  {sid:<28s}      0     -        -         -        -')

    # 5. Confluence test
    print()
    print('=' * 80)
    print('[4/4] Confluence Engine 回测...')
    print('=' * 80)
    conf_results = run_confluence_test(df)

    raw = conf_results['raw']
    conf = conf_results['confluence']

    if raw:
        raw_wins = sum(1 for r in raw if r > 0)
        print(f'\n单策略信号汇总:')
        print(f'  总信号数: {len(raw)}')
        print(f'  胜率: {raw_wins/len(raw):.1%}')
        print(f'  平均收益: {np.mean(raw)*100:.4f}%')

    if conf:
        conf_returns = [c['return'] for c in conf]
        conf_wins = sum(1 for c in conf if c['return'] > 0)
        strong_conf = [c for c in conf if c['is_strong']]
        strong_wins = sum(1 for c in strong_conf if c['return'] > 0)

        print(f'\nConfluence 融合信号:')
        print(f'  总信号数: {len(conf)}')
        print(f'  胜率: {conf_wins/len(conf):.1%}')
        print(f'  平均收益: {np.mean(conf_returns)*100:.4f}%')
        print(f'  平均策略数: {np.mean([c["strategy_count"] for c in conf]):.1f}')
        print(f'  冲突比例: {sum(1 for c in conf if c["has_conflict"])/len(conf):.1%}')

        if strong_conf:
            print(f'\n强 Confluence 信号 (confidence>=0.7, 3+策略):')
            print(f'  信号数: {len(strong_conf)}')
            print(f'  胜率: {strong_wins/len(strong_conf):.1%}')
            print(f'  平均收益: {np.mean([c["return"] for c in strong_conf])*100:.4f}%')

    print()
    print('=' * 80)
    print('回测完成!')
    print('=' * 80)


if __name__ == '__main__':
    main()
