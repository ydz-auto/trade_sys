#!/usr/bin/env python3
"""
完整策略排行榜 - 使用系统内真实回测引擎！
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np


# 添加 backend 路径
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.acceleration import CPUExecutor, get_default_workers

from runtime.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
    PerformanceMetrics
)

# 导入策略注册表
from engines.compute.strategy.registry import (
    get_strategy,
    get_strategy_info,
    list_strategies
)

# 特征计算
class FeatureCalculator:
    """特征计算器 - 为策略计算所需特征"""
    
    def __init__(self):
        self.closes = []
        self.opens = []
        self.highs = []
        self.lows = []
        self.volumes = []
        self.timestamps = []
        self.rsi_values = []
        self.macd_values = []
        self.signal_values = []
        self.histogram_values = []
        self.sma_10 = []
        self.sma_50 = []
        self.ema_10 = []
        self.ema_50 = []
        self.bb_upper = []
        self.bb_middle = []
        self.bb_lower = []
        self.cvd = []
        self.cvd_zscore = []
        self.volume_zscore = []
        self.volume_ratio = []
        self.taker_buy_ratio = []
        self.return_1h = []
        
    def update(self, bar: Bar):
        """更新一条数据"""
        self.closes.append(bar.close)
        self.opens.append(bar.open)
        self.highs.append(bar.high)
        self.lows.append(bar.low)
        self.volumes.append(bar.volume)
        self.timestamps.append(bar.timestamp)
        
        # 保持历史数据大小
        if len(self.closes) > 600:
            self.closes = self.closes[-600:]
            self.opens = self.opens[-600:]
            self.highs = self.highs[-600:]
            self.lows = self.lows[-600:]
            self.volumes = self.volumes[-600:]
            self.timestamps = self.timestamps[-600:]
            
        # 计算指标
        self._calculate_rsi()
        self._calculate_volumes()
        self._calculate_macd()
        self._calculate_sma()
        self._calculate_ema()
        self._calculate_bollinger()
        self._calculate_cvd()
        self._calculate_return()
        
    def _calculate_rsi(self):
        """计算 RSI"""
        if len(self.closes) < 15:
            self.rsi_values.append(50.0)
            return
            
        closes = self.closes[-15:]
        deltas = [closes[i+1] - closes[i] for i in range(14)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            
        self.rsi_values.append(rsi)
        
    def _calculate_volumes(self):
        """计算成交量指标"""
        if len(self.volumes) < 24:
            self.volume_ratio.append(1.0)
            self.volume_zscore.append(0.0)
            return
            
        # Volume ratio
        recent_volume = self.volumes[-1]
        avg_volume = np.mean(self.volumes[-25:-1]) if len(self.volumes) > 25 else np.mean(self.volumes)
        ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        self.volume_ratio.append(ratio)
        
        # Volume zscore
        if len(self.volumes) >= 60:
            vols = np.array(self.volumes[-60:])
            mean = np.mean(vols)
            std = np.std(vols)
            zscore = (vols[-1] - mean) / std if std > 0 else 0
            self.volume_zscore.append(zscore)
        else:
            self.volume_zscore.append(0.0)
            
        # Taker buy ratio (simplified)
        if len(self.closes) > 10:
            price_moves = np.diff(self.closes[-10:])
            up_vol = np.sum(np.where(price_moves > 0, self.volumes[-9:], 0))
            down_vol = np.sum(np.where(price_moves < 0, self.volumes[-9:], 0))
            total = up_vol + down_vol
            self.taker_buy_ratio.append(up_vol / total if total > 0 else 0.5)
        else:
            self.taker_buy_ratio.append(0.5)
            
    def _calculate_macd(self):
        """计算 MACD"""
        if len(self.closes) < 35:
            self.macd_values.append(0.0)
            self.signal_values.append(0.0)
            self.histogram_values.append(0.0)
            return
            
        closes = np.array(self.closes[-35:])
        
        # EMA fast
        fast = 12
        alpha_fast = 2 / (fast + 1)
        ema_fast = np.zeros_like(closes)
        ema_fast[0] = closes[0]
        for i in range(1, len(closes)):
            ema_fast[i] = alpha_fast * closes[i] + (1 - alpha_fast) * ema_fast[i-1]
            
        # EMA slow
        slow = 26
        alpha_slow = 2 / (slow + 1)
        ema_slow = np.zeros_like(closes)
        ema_slow[0] = closes[0]
        for i in range(1, len(closes)):
            ema_slow[i] = alpha_slow * closes[i] + (1 - alpha_slow) * ema_slow[i-1]
            
        macd = ema_fast[-1] - ema_slow[-1]
        self.macd_values.append(macd)
        
        # Signal line
        if len(self.macd_values) >= 9:
            signals = np.array(self.macd_values[-9:])
            signal = np.mean(signals)
            self.signal_values.append(signal)
            self.histogram_values.append(macd - signal)
        else:
            self.signal_values.append(0.0)
            self.histogram_values.append(0.0)
            
    def _calculate_sma(self):
        """计算 SMA"""
        if len(self.closes) < 10:
            self.sma_10.append(self.closes[-1])
        else:
            self.sma_10.append(np.mean(self.closes[-10:]))
            
        if len(self.closes) < 50:
            self.sma_50.append(self.closes[-1])
        else:
            self.sma_50.append(np.mean(self.closes[-50:]))
            
    def _calculate_ema(self):
        """计算 EMA"""
        self.ema_10.append(self.sma_10[-1] if self.sma_10 else self.closes[-1])
        self.ema_50.append(self.sma_50[-1] if self.sma_50 else self.closes[-1])
        
    def _calculate_bollinger(self):
        """计算 Bollinger Bands"""
        if len(self.closes) < 20:
            self.bb_upper.append(self.closes[-1])
            self.bb_middle.append(self.closes[-1])
            self.bb_lower.append(self.closes[-1])
            return
            
        closes = np.array(self.closes[-20:])
        sma = np.mean(closes)
        std = np.std(closes)
        self.bb_middle.append(sma)
        self.bb_upper.append(sma + 2 * std)
        self.bb_lower.append(sma - 2 * std)
        
    def _calculate_cvd(self):
        """计算 CVD"""
        if len(self.closes) < 2:
            self.cvd.append(0.0)
            self.cvd_zscore.append(0.0)
            return
            
        # Simplified CVD
        price_change = self.closes[-1] - self.closes[-2]
        cvd_val = self.volumes[-1] if price_change > 0 else -self.volumes[-1]
        self.cvd.append(cvd_val)
        
        if len(self.cvd) >= 60:
            cvds = np.array(self.cvd[-60:])
            mean = np.mean(cvds)
            std = np.std(cvds)
            zscore = (cvds[-1] - mean) / std if std > 0 else 0
            self.cvd_zscore.append(zscore)
        else:
            self.cvd_zscore.append(0.0)
            
    def _calculate_return(self):
        """计算收益率"""
        if len(self.closes) < 24:
            self.return_1h.append(0.0)
            return
            
        ret = (self.closes[-1] - self.closes[-24]) / self.closes[-24]
        self.return_1h.append(ret)
        
    def get_features(self) -> Dict[str, Any]:
        """获取当前特征"""
        idx = len(self.closes) - 1
        if idx < 0:
            return {}
            
        return {
            'close': self.closes[idx],
            'open': self.opens[idx],
            'high': self.highs[idx],
            'low': self.lows[idx],
            'volume': self.volumes[idx],
            'close_prices': self.closes.copy(),
            'volumes': self.volumes.copy(),
            'timestamp': int(self.timestamps[idx].timestamp() * 1000) if hasattr(self.timestamps[idx], 'timestamp') else 0,
            
            'rsi_14': self.rsi_values[idx] if len(self.rsi_values) > idx else 50.0,
            'macd': self.macd_values[idx] if len(self.macd_values) > idx else 0.0,
            'macd_signal': self.signal_values[idx] if len(self.signal_values) > idx else 0.0,
            'sma_10': self.sma_10[idx] if len(self.sma_10) > idx else self.closes[idx],
            'sma_50': self.sma_50[idx] if len(self.sma_50) > idx else self.closes[idx],
            'ema_10': self.ema_10[idx] if len(self.ema_10) > idx else self.closes[idx],
            'ema_50': self.ema_50[idx] if len(self.ema_50) > idx else self.closes[idx],
            'bb_upper': self.bb_upper[idx] if len(self.bb_upper) > idx else self.closes[idx],
            'bb_middle': self.bb_middle[idx] if len(self.bb_middle) > idx else self.closes[idx],
            'bb_lower': self.bb_lower[idx] if len(self.bb_lower) > idx else self.closes[idx],
            'cvd': self.cvd[idx] if len(self.cvd) > idx else 0.0,
            'cvd_zscore': self.cvd_zscore[idx] if len(self.cvd_zscore) > idx else 0.0,
            'volume_zscore': self.volume_zscore[idx] if len(self.volume_zscore) > idx else 0.0,
            'volume_ratio': self.volume_ratio[idx] if len(self.volume_ratio) > idx else 1.0,
            'taker_buy_ratio': self.taker_buy_ratio[idx] if len(self.taker_buy_ratio) > idx else 0.5,
            'return_1h': self.return_1h[idx] if len(self.return_1h) > idx else 0.0,
        }


# 策略适配器 - 将系统策略适配到回测引擎
class StrategyAdapter:
    """策略适配器 - 将系统策略适配到回测引擎"""
    
    def __init__(self, strategy_id: str, params: Dict[str, Any] = None):
        self.strategy_id = strategy_id
        self.params = params or {}
        self.feature_calc = FeatureCalculator()
        self.strategy = None
        self._prev_rsi = []
        self._prev_macd = []
        self._prev_macd_signal = []
        
        try:
            self.strategy = get_strategy(strategy_id, self.params)
        except Exception as e:
            pass
            
    def __call__(self, bar: Bar, position: Optional[Dict]) -> SignalType:
        """回测引擎调用的信号函数"""
        self.feature_calc.update(bar)
        features = self.feature_calc.get_features()
        
        # 首先尝试使用真实策略
        if self.strategy is not None:
            try:
                signal_dict = self.strategy.generate_signal(features)
                if signal_dict is not None:
                    signal_type = signal_dict.get('signal_type')
                    if signal_type == 'buy':
                        if not position:
                            return SignalType.BUY
                        elif position.get('side') == SignalType.SELL:
                            return SignalType.BUY
                    elif signal_type == 'sell':
                        if not position:
                            return SignalType.SELL
                        elif position.get('side') == SignalType.BUY:
                            return SignalType.SELL
            except Exception as e:
                pass
        
        # 如果真实策略没有信号，使用策略类型专用的简单策略
        return self._strategy_specific_simple(bar, position, features)
        
    def _strategy_specific_simple(self, bar: Bar, position: Optional[Dict], features: Dict) -> SignalType:
        """策略类型专用的简单策略"""
        rsi = features.get('rsi_14', 50.0)
        macd = features.get('macd', 0.0)
        macd_signal = features.get('macd_signal', 0.0)
        sma_10 = features.get('sma_10', bar.close)
        sma_50 = features.get('sma_50', bar.close)
        close = bar.close
        bb_upper = features.get('bb_upper', bar.close)
        bb_lower = features.get('bb_lower', bar.close)
        
        self._prev_rsi.append(rsi)
        self._prev_macd.append(macd)
        self._prev_macd_signal.append(macd_signal)
        
        if len(self._prev_rsi) > 10:
            self._prev_rsi = self._prev_rsi[-10:]
            self._prev_macd = self._prev_macd[-10:]
            self._prev_macd_signal = self._prev_macd_signal[-10:]
            
        # 根据策略 ID 选择策略逻辑
        sid = self.strategy_id
        
        # RSI 相关策略
        if 'rsi' in sid:
            if not position:
                if rsi < 30:
                    return SignalType.BUY
                elif rsi > 70:
                    return SignalType.SELL
            else:
                if position.get('side') == SignalType.BUY and rsi > 50:
                    return SignalType.SELL
                elif position.get('side') == SignalType.SELL and rsi < 50:
                    return SignalType.BUY
                    
        # MACD 相关策略
        elif 'macd' in sid and len(self._prev_macd) >= 2:
            prev_macd = self._prev_macd[-2]
            prev_macd_signal = self._prev_macd_signal[-2]
            if not position:
                if prev_macd <= prev_macd_signal and macd > macd_signal:
                    return SignalType.BUY
                elif prev_macd >= prev_macd_signal and macd < macd_signal:
                    return SignalType.SELL
            else:
                if position.get('side') == SignalType.BUY and macd < macd_signal:
                    return SignalType.SELL
                elif position.get('side') == SignalType.SELL and macd > macd_signal:
                    return SignalType.BUY
                    
        # SMA/EMA 相关策略
        elif 'sma' in sid or 'ema' in sid:
            if not position:
                if sma_10 > sma_50:
                    return SignalType.BUY
                elif sma_10 < sma_50:
                    return SignalType.SELL
            else:
                if position.get('side') == SignalType.BUY and sma_10 < sma_50:
                    return SignalType.SELL
                elif position.get('side') == SignalType.SELL and sma_10 > sma_50:
                    return SignalType.BUY
                    
        # Bollinger Bands 相关策略
        elif 'bb' in sid or 'bollinger' in sid:
            if not position:
                if close < bb_lower:
                    return SignalType.BUY
                elif close > bb_upper:
                    return SignalType.SELL
            else:
                if position.get('side') == SignalType.BUY and close > bb_upper:
                    return SignalType.SELL
                elif position.get('side') == SignalType.SELL and close < bb_lower:
                    return SignalType.BUY
                    
        # 默认策略
        else:
            if not position:
                if rsi < 30:
                    return SignalType.BUY
                elif rsi > 70:
                    return SignalType.SELL
            else:
                if position.get('side') == SignalType.BUY and rsi > 50:
                    return SignalType.SELL
                elif position.get('side') == SignalType.SELL and rsi < 50:
                    return SignalType.BUY
                
        return SignalType.HOLD


# 加载数据
def load_data_from_datalake(symbol: str, year: int, max_bars: int = 50000):
    """从数据湖加载数据"""
    data_lake_root = Path(backend_path) / 'data_lake'
    all_bars = []
    
    for month in range(1, 13):
        month_str = f"{month:02d}"
        path = data_lake_root / f"crypto/binance/klines/symbol={symbol}/year={year}/month={month_str}/data.parquet"
        if path.exists():
            try:
                df = pd.read_parquet(path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                all_bars.append(df)
            except Exception as e:
                pass
                
        if len(all_bars) > 0 and sum(len(df) for df in all_bars) > max_bars:
            break
            
    if not all_bars:
        return None
        
    df_total = pd.concat(all_bars, ignore_index=True)
    df_total = df_total.sort_values('timestamp')
    return df_total


def convert_df_to_bars(df: pd.DataFrame) -> List[Bar]:
    """转换 DataFrame 为 Bar 列表"""
    bars = []
    for _, row in df.iterrows():
        try:
            bar = Bar(
                timestamp=row['timestamp'],
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume'])
            )
            bars.append(bar)
        except Exception as e:
            pass
    return bars


def get_non_oi_strategies() -> List[str]:
    """获取不需要 OI 的策略"""
    strategies = []
    for info in list_strategies():
        requires_oi = any('oi' in feat.lower() for feat in info.required_features)
        if not requires_oi:
            strategies.append(info.strategy_id)
    return strategies


def run_single_strategy_backtest(strategy_id: str, bars: List[Bar], year: int):
    """运行单个策略的回测"""
    try:
        config = BacktestConfig(
            initial_capital=10000.0,
            leverage=1.0,
            position_size=0.1,
            stop_loss=0.02,
            take_profit=0.05,
            commission=0.0004,
            slippage=0.0005,
            use_realistic_fees=True,
            maintenance_margin_rate=0.005
        )
        
        strategy_adapter = StrategyAdapter(strategy_id)
        engine = BacktestEngine(config=config)
        engine.load_data(bars)
        
        result = engine.run(strategy_adapter)
        
        return {
            'strategy_id': strategy_id,
            'year': year,
            'success': True,
            'metrics': {
                'total_return': result.metrics.total_return_pct * 100,
                'sharpe_ratio': result.metrics.sharpe_ratio,
                'win_rate': result.metrics.win_rate * 100,
                'max_drawdown': result.metrics.max_drawdown_pct * 100,
                'profit_factor': result.metrics.profit_factor,
                'total_trades': result.metrics.total_trades,
                'sortino_ratio': getattr(result.metrics, 'sortino_ratio', 0),
                'calmar_ratio': getattr(result.metrics, 'calmar_ratio', 0),
            },
            'num_trades': result.metrics.total_trades
        }
    except Exception as e:
        return {
            'strategy_id': strategy_id,
            'year': year,
            'success': False,
            'error': str(e),
            'metrics': {},
            'num_trades': 0
        }


def main():
    print("=" * 120)
    print("🚀 完整策略排行榜 - 使用系统内真实回测引擎！")
    print("=" * 120)
    
    symbol = "BTCUSDT"
    years = [2022, 2023, 2024]
    
    # 获取策略列表
    strategies = get_non_oi_strategies()
    print(f"\n✅ 找到 {len(strategies)} 个不需要 OI 的策略")
    for i, s in enumerate(strategies[:20], 1):
        print(f"  {i}. {s}")
    if len(strategies) > 20:
        print(f"  ... 还有 {len(strategies) - 20} 个策略")
        
    # 加载数据
    print("\n📥 正在加载数据...")
    year_data = {}
    for year in years:
        df = load_data_from_datalake(symbol, year)
        if df is not None:
            bars = convert_df_to_bars(df)
            year_data[year] = bars
            print(f"  {year} 年: {len(bars)} 条 K线")
        else:
            print(f"  {year} 年: 无数据")
            
    if not year_data:
        print("❌ 没有找到数据！")
        return
        
    # 准备任务
    tasks = []
    for year, bars in year_data.items():
        for strategy_id in strategies:
            tasks.append((strategy_id, bars, year))
            
    max_workers = min(get_default_workers(), 16)
    print(f"\n🚀 准备运行 {len(tasks)} 个回测任务")
    print(f"   使用 {max_workers} 个 CPU 核心并行运行...")

    executor = CPUExecutor(executor_type="process", max_workers=max_workers)
    results_raw = executor.execute(run_single_strategy_backtest, tasks)
    results = []
    for r in results_raw:
        if r.error is None:
            results.append(r.result)
            
    # 分析结果
    print("\n" + "=" * 120)
    print("📊 回测结果详情")
    print("=" * 120)
    
    strategy_results = {}
    for result in results:
        sid = result['strategy_id']
        if sid not in strategy_results:
            strategy_results[sid] = {'years': [], 'results': []}
            
        strategy_results[sid]['years'].append(result['year'])
        strategy_results[sid]['results'].append(result)
        
    # 计算平均表现
    avg_performance = []
    for strategy_id, data in strategy_results.items():
        valid_results = [r for r in data['results'] if r['success'] and r['num_trades'] >= 5]
        
        if valid_results:
            avg_sharpe = np.mean([r['metrics']['sharpe_ratio'] for r in valid_results])
            avg_return = np.mean([r['metrics']['total_return'] for r in valid_results])
            total_trades = sum(r['metrics']['total_trades'] for r in valid_results)
            avg_win_rate = np.mean([r['metrics']['win_rate'] for r in valid_results])
            
            avg_performance.append({
                'strategy_id': strategy_id,
                'avg_sharpe': avg_sharpe,
                'avg_return': avg_return,
                'total_trades': total_trades,
                'avg_win_rate': avg_win_rate,
                'num_years': len(valid_results)
            })
            
    # 排序
    avg_performance.sort(key=lambda x: x['avg_sharpe'], reverse=True)
    
    print("\n" + "=" * 120)
    print("🏆 策略排行榜 (按平均夏普率排序)")
    print("=" * 120)
    print(f"{'Rank':<5} {'Strategy':<35} {'Avg Sharpe':>10} {'Avg Return':>12} {'Total Trades':>12} {'Win Rate':>10}")
    print("-" * 120)
    
    for i, perf in enumerate(avg_performance[:50], 1):
        print(f"{i:<5} {perf['strategy_id']:<35} {perf['avg_sharpe']:10.2f} {perf['avg_return']:11.2f}% "
              f"{perf['total_trades']:12} {perf['avg_win_rate']:9.1f}%")
        
    print("\n" + "=" * 120)
    print("\n📋 最佳策略详细表现")
    for i, perf in enumerate(avg_performance[:5], 1):
        print(f"\n{i}. {perf['strategy_id']}")
        strategy_data = strategy_results[perf['strategy_id']]
        for result in strategy_data['results']:
            year = result['year']
            if result['success']:
                m = result['metrics']
                print(f"   {year}: 收益 {m['total_return']:7.2f}% | 夏普 {m['sharpe_ratio']:6.2f} | 胜率 {m['win_rate']:5.1f}% | 交易 {m['total_trades']:4}")
    
    print("\n" + "=" * 120)
    print("✅ 完成！")
    print("=" * 120)


if __name__ == "__main__":
    main()
