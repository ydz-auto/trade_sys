"""
独立运行的自动因子生成演示
不依赖其他模块，直接使用
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import stats
import itertools
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import random


# =============================================================================
# 辅助函数
# =============================================================================

def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def _compute_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    width = (upper - lower) / middle
    return lower, upper, width


# =============================================================================
# 因子模板
# =============================================================================

@dataclass
class FactorTemplate:
    name: str
    description: str
    params: Dict[str, List[Any]]


TEMPLATES = [
    FactorTemplate("momentum_5", "5期动量", {"period": [5]}),
    FactorTemplate("momentum_10", "10期动量", {"period": [10]}),
    FactorTemplate("momentum_20", "20期动量", {"period": [20]}),
    FactorTemplate("rsi_6", "RSI(6)", {"period": [6]}),
    FactorTemplate("rsi_14", "RSI(14)", {"period": [14]}),
    FactorTemplate("rsi_28", "RSI(28)", {"period": [28]}),
    FactorTemplate("macd_hist", "MACD柱", {}),
    FactorTemplate("ma_cross_5_20", "MA5/MA20交叉", {"fast": [5], "slow": [20]}),
    FactorTemplate("ma_cross_7_30", "MA7/MA30交叉", {"fast": [7], "slow": [30]}),
    FactorTemplate("price_to_sma20", "价格/MA20比", {"period": [20]}),
    FactorTemplate("price_to_sma60", "价格/MA60比", {"period": [60]}),
    FactorTemplate("volatility_10", "10期波动率", {"period": [10]}),
    FactorTemplate("volatility_20", "20期波动率", {"period": [20]}),
    FactorTemplate("volume_ratio_10", "量比", {"period": [10]}),
    FactorTemplate("z_score_20", "Z-Score(20)", {"period": [20]}),
    FactorTemplate("bb_width", "布林带宽度", {}),
    FactorTemplate("atr_ratio", "ATR相对波动", {"period": [14]}),
]


# =============================================================================
# 因子计算器
# =============================================================================

class FactorCalculator:
    """因子计算器"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._precompute()
    
    def _precompute(self):
        """预计算基础指标"""
        df = self.df
        
        # 价格指标
        for p in [5, 7, 10, 20, 30, 60]:
            df[f'sma_{p}'] = df['close'].rolling(p).mean()
            df[f'std_{p}'] = df['close'].pct_change().rolling(p).std()
            df[f'momentum_{p}'] = df['close'] - df['close'].shift(p)
        
        df['rsi_6'] = _compute_rsi(df['close'], 6)
        df['rsi_14'] = _compute_rsi(df['close'], 14)
        df['rsi_28'] = _compute_rsi(df['close'], 28)
        
        df['macd_line'], df['macd_signal'], df['macd_hist'] = _compute_macd(df['close'])
        
        df['bb_lower'], df['bb_upper'], df['bb_width'] = _compute_bollinger(df['close'])
        
        df['atr_14'] = (df['high'] - df['low']).rolling(14).mean()
        
        df['volume_sma_10'] = df['volume'].rolling(10).mean()
        
        df['returns_1'] = df['close'].pct_change()
    
    def compute(self, template: FactorTemplate) -> Optional[pd.Series]:
        """根据模板计算因子"""
        try:
            p = template.params
            
            if "momentum" in template.name:
                period = p.get('period', [10])[0]
                return self.df[f'momentum_{period}']
            
            elif "rsi" in template.name:
                period = p.get('period', [14])[0]
                return self.df[f'rsi_{period}']
            
            elif "macd_hist" == template.name:
                return self.df['macd_hist']
            
            elif "ma_cross" in template.name:
                fast = p.get('fast', [5])[0]
                slow = p.get('slow', [20])[0]
                return self.df[f'sma_{fast}'] - self.df[f'sma_{slow}']
            
            elif "price_to_sma" in template.name:
                period = p.get('period', [20])[0]
                return self.df['close'] / self.df[f'sma_{period}']
            
            elif "volatility" in template.name:
                period = p.get('period', [20])[0]
                return self.df[f'std_{period}']
            
            elif "volume_ratio" in template.name:
                return self.df['volume'] / self.df['volume_sma_10']
            
            elif "z_score" in template.name:
                period = p.get('period', [20])[0]
                ma = self.df[f'sma_{period}']
                std = self.df[f'std_{period}']
                return (self.df['close'] - ma) / std
            
            elif "bb_width" == template.name:
                return self.df['bb_width']
            
            elif "atr_ratio" == template.name:
                return self.df['atr_14'] / self.df['close']
            
            return None
        except Exception as e:
            return None


# =============================================================================
# 自动因子生成器
# =============================================================================

@dataclass
class GeneratedFactor:
    name: str
    ic: float
    rank_ic: float
    turnover: float
    score: float


class AutoFactorGenerator:
    """自动因子生成器"""
    
    def __init__(self, min_ic: float = 0.02):
        self.min_ic = min_ic
    
    def generate(self, df: pd.DataFrame) -> List[GeneratedFactor]:
        """生成因子"""
        calc = FactorCalculator(df)
        
        # 计算远期收益
        df = df.copy()
        df['forward_5'] = df['close'].pct_change(5).shift(-5)
        
        factors = []
        for template in TEMPLATES:
            factor_values = calc.compute(template)
            if factor_values is None:
                continue
            
            # 计算IC
            ic = self._compute_ic(factor_values, df['forward_5'])
            rank_ic = self._compute_rank_ic(factor_values, df['forward_5'])
            turnover = self._compute_turnover(factor_values)
            
            if abs(ic) >= self.min_ic:
                score = abs(ic) * min(abs(ic) / (turnover + 0.01), 2) * (1 - turnover)
                
                factors.append(GeneratedFactor(
                    name=template.name,
                    ic=ic,
                    rank_ic=rank_ic,
                    turnover=turnover,
                    score=score
                ))
        
        # 按评分排序
        factors.sort(key=lambda x: x.score, reverse=True)
        return factors
    
    def _compute_ic(self, factor: pd.Series, returns: pd.Series) -> float:
        valid = ~(factor.isna() | returns.isna())
        if valid.sum() < 30:
            return 0.0
        return factor[valid].corr(returns[valid])
    
    def _compute_rank_ic(self, factor: pd.Series, returns: pd.Series) -> float:
        valid = ~(factor.isna() | returns.isna())
        if valid.sum() < 30:
            return 0.0
        try:
            return stats.spearmanr(factor[valid], returns[valid])[0]
        except:
            return 0.0
    
    def _compute_turnover(self, factor: pd.Series, bins: int = 5) -> float:
        if len(factor) < bins * 3:
            return 0.0
        try:
            deciles = pd.qcut(factor.dropna(), bins, labels=False, duplicates="drop")
            return (deciles != deciles.shift()).mean()
        except:
            return 0.0


# =============================================================================
# 数据生成
# =============================================================================

def generate_mock_data(n: int = 500) -> pd.DataFrame:
    dates = pd.date_range(end=datetime.now(), periods=n, freq="1h")
    
    np.random.seed(42)
    price = 50000.0
    prices = [price]
    for i in range(1, n):
        # 加入一些趋势和波动率变化
        vol = 0.02 + 0.01 * np.sin(i / 50)
        drift = 0.0003
        shock = np.random.normal(0, vol)
        price = price * (1 + drift + shock)
        prices.append(price)
    
    high = [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices]
    low = [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices]
    volume = np.random.lognormal(10, 0.5, n)
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volume
    })


# =============================================================================
# 主程序
# =============================================================================

def main():
    print("\n" + "="*80)
    print("  🚀 Auto Factor Generator - 自动因子生成")
    print("="*80)
    
    # 1. 生成数据
    print("\n[1/4] 生成历史数据...")
    data = generate_mock_data(800)
    print(f"      数据点: {len(data)}")
    
    # 2. 计算因子
    print("\n[2/4] 自动生成因子...")
    generator = AutoFactorGenerator(min_ic=0.01)
    factors = generator.generate(data)
    print(f"      候选因子: {len(factors)} 个 (IC >= 0.01)")
    
    # 3. 展示结果
    print("\n[3/4] 因子排名:")
    print(f"      {'因子名称':<20} {'IC':>10} {'RankIC':>10} {'换手率':>10} {'评分':>10}")
    print("      " + "-"*65)
    for f in factors[:15]:
        print(f"      {f.name:<20} {f.ic:>10.4f} {f.rank_ic:>10.4f} {f.turnover:>10.2%} {f.score:>10.4f}")
    
    # 4. 最佳因子
    if factors:
        best = factors[0]
        print(f"\n[4/4] 最佳因子: {best.name}")
        print(f"      IC: {best.ic:.4f}")
        print(f"      RankIC: {best.rank_ic:.4f}")
        print(f"      换手率: {best.turnover:.2%}")
        print(f"      评分: {best.score:.4f}")
        
        # 解释
        print("\n      因子解读:")
        if "momentum" in best.name:
            print("      → 动量因子，捕捉价格趋势")
        elif "rsi" in best.name:
            print("      → RSI因子，捕捉超买超卖")
        elif "macd" in best.name:
            print("      → MACD因子，捕捉趋势反转")
        elif "ma_cross" in best.name:
            print("      → 均线交叉因子，金叉死叉信号")
        elif "volatility" in best.name:
            print("      → 波动率因子，捕捉市场恐慌/贪婪")
        elif "z_score" in best.name:
            print("      → Z-Score因子，捕捉均值回归机会")
    
    print("\n" + "="*80)
    print("  ✅ 自动因子生成完成！")
    print("="*80)
    print("\n下一步:")
    print("  1. 用选出的因子构建策略")
    print("  2. 进行Walk-Forward滚动回测")
    print("  3. 放入Alpha Pipeline验证")


if __name__ == "__main__":
    main()

