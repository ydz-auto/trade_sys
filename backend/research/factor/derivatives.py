"""
Derivatives Factors - 衍生品结构因子

这是crypto最重要的alpha来源之一：
1. Funding Factor (资金费率)
2. OI Factor (持仓量)
3. Liquidation Factor (清算)
4. Basis Factor (基差)

这些是真正的crypto-native alpha。
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class DerivativesMetrics:
    """衍生品市场状态"""
    funding_rate: float
    funding_rate_zscore: float
    oi_change: float
    oi_zscore: float
    liquidation_long: float
    liquidation_short: float
    basis_spread: float
    implied_volatility: float


class DerivativesFactors:
    """
    衍生品结构因子
    
    这是crypto-alpha的核心来源之一
    """
    
    @staticmethod
    def funding_divergence(
        funding_rate: pd.Series,
        price_return: pd.Series,
        window: int = 24
    ) -> pd.Series:
        """
        资金费率与价格背离因子
        
        金融逻辑：
        - 资金费率高，但价格跌 → 多头投机过热
        - 资金费率低，但价格涨 → 空头投机过热
        
        这是经典的alpha因子
        """
        
        # Z-score标准化
        funding_mean = funding_rate.rolling(window).mean()
        funding_std = funding_rate.rolling(window).std()
        funding_z = (funding_rate - funding_mean) / (funding_std + 1e-10)
        
        # 价格偏离
        price_mean = price_return.rolling(window).mean()
        price_std = price_return.rolling(window).std()
        price_z = (price_return - price_mean) / (price_std + 1e-10)
        
        # 背离信号：funding 和 price 方向相反
        divergence = funding_z * price_z
        
        # 只取负相关的情况（funding涨，price跌 或反之）
        return -divergence
    
    @staticmethod
    def oi_momentum(
        open_interest: pd.Series,
        price_change: pd.Series,
        window: int = 12
    ) -> pd.Series:
        """
        持仓量动量因子
        
        金融逻辑：
        - OI增长 + 价格上涨 → 新多单入场，趋势延续
        - OI增长 + 价格下跌 → 新空单入场，趋势延续
        - OI减少 + 价格大幅波动 → 清算驱动
        """
        
        oi_change = open_interest.pct_change(window)
        
        # OI 动量与价格动量的一致性
        oi_price_alignment = oi_change * price_change
        
        return oi_price_alignment
    
    @staticmethod
    def liquidation_pressure(
        long_liquidation: pd.Series,
        short_liquidation: pd.Series,
        price: pd.Series,
        window: int = 6
    ) -> pd.Series:
        """
        清算压力因子
        
        金融逻辑：
        - 多头大量清算 → 价格继续下跌
        - 空头大量清算 → 价格继续上涨
        - 极端清算 → 超跌反弹机会
        """
        
        # 净清算
        net_liquidation = short_liquidation - long_liquidation
        
        # 标准化
        liq_mean = net_liquidation.abs().rolling(window).mean()
        liq_z = net_liquidation / (liq_mean + 1e-10)
        
        # 清算压力 = 标准化净清算 * 价格位置
        # 当liq_z > 0 → 空头被清算 → 看涨
        # 当liq_z < 0 → 多头被清算 → 看跌
        return liq_z
    
    @staticmethod
    def basis_spread(
        spot_price: pd.Series,
        perp_price: pd.Series,
        window: int = 12
    ) -> pd.Series:
        """
        基差因子
        
        金融逻辑：
        - 现货-期货基差扩大 → 套利机会
        - 基差与价格背离 → 过度投机
        """
        
        # 基差百分比
        basis = (perp_price - spot_price) / spot_price
        
        # 基差Z-score
        basis_mean = basis.rolling(window).mean()
        basis_std = basis.rolling(window).std()
        basis_z = (basis - basis_mean) / (basis_std + 1e-10)
        
        return basis_z
    
    @staticmethod
    def squeeze_probability(
        funding_rate: pd.Series,
        open_interest: pd.Series,
        price_range: pd.Series,
        window: int = 24
    ) -> pd.Series:
        """
        挤压概率因子
        
        金融逻辑：
        当同时满足：
        1. 资金费率极高（多头过度）
        2. 持仓量快速增长（新资金入场）
        3. 价格横盘（没有真实上涨）
        
        → 高概率squeeze风险
        """
        
        # 资金费率Z-score
        funding_z = (funding_rate - funding_rate.rolling(window).mean()) / (funding_rate.rolling(window).std() + 1e-10)
        
        # OI增长
        oi_growth = open_interest.pct_change(window)
        oi_z = (oi_growth - oi_growth.rolling(window).mean()) / (oi_growth.rolling(window).std() + 1e-10)
        
        # 价格压缩程度
        range_normalized = price_range / price_range.rolling(window).mean()
        
        # 综合挤压风险
        squeeze_risk = funding_z * oi_z / (range_normalized + 1e-10)
        
        return squeeze_risk
    
    @staticmethod
    def smart_money_liquidity(
        open_interest: pd.Series,
        funding_rate: pd.Series,
        price_change: pd.Series,
        window: int = 12
    ) -> pd.Series:
        """
        聪明钱流动性因子
        
        金融逻辑：
        - OI增长 + funding 正 → 散户做多
        - 但价格没涨 → 聪明钱在卖
        
        这是经典的smart money pattern
        """
        
        # OI与funding同向
        oi_change = open_interest.pct_change(window)
        
        # 一致性信号
        alignment = oi_change * funding_rate
        
        # 但价格背离
        smart_money = alignment * (-price_change)
        
        return smart_money


# 示例使用
if __name__ == "__main__":
    print("="*80)
    print("  衍生品结构因子 - 示例")
    print("="*80)
    
    # 生成模拟数据
    n = 500
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="1H")
    
    # 模拟价格
    np.random.seed(42)
    price = 50000
    prices = [price]
    for _ in range(n-1):
        price *= (1 + np.random.normal(0, 0.02))
        prices.append(price)
    spot = pd.Series(prices, index=dates)
    perp = spot * (1 + np.random.normal(0, 0.001, n))
    
    # 模拟衍生品数据
    funding = pd.Series(np.random.normal(0.0001, 0.0005, n), index=dates)
    oi = pd.Series(np.exp(np.random.normal(10, 0.2, n)), index=dates)
    liq_long = pd.Series(np.abs(np.random.normal(0, 100000, n)), index=dates)
    liq_short = pd.Series(np.abs(np.random.normal(0, 100000, n)), index=dates)
    
    # 计算因子
    print("\n计算衍生品因子...")
    
    # 1. 资金费率背离
    funding_div = DerivativesFactors.funding_divergence(funding, spot.pct_change())
    print(f"  funding_divergence 生成: {len(funding_div.dropna())}个有效数据点")
    
    # 2. OI动量
    oi_mom = DerivativesFactors.oi_momentum(oi, spot.pct_change())
    print(f"  oi_momentum 生成: {len(oi_mom.dropna())}个有效数据点")
    
    # 3. 清算压力
    liq_press = DerivativesFactors.liquidation_pressure(liq_long, liq_short, spot)
    print(f"  liquidation_pressure 生成: {len(liq_press.dropna())}个有效数据点")
    
    # 4. 挤压概率
    price_range = spot.rolling(24).max() - spot.rolling(24).min()
    squeeze = DerivativesFactors.squeeze_probability(funding, oi, price_range)
    print(f"  squeeze_probability 生成: {len(squeeze.dropna())}个有效数据点")
    
    print("\n" + "="*80)
    print("  衍生品因子生成完成")
    print("="*80)
    print("""
    这些是真正的crypto-native alpha：
    
    1. funding_divergence - 资金费率与价格背离
    2. oi_momentum - 持仓量动量
    3. liquidation_pressure - 清算压力
    4. squeeze_probability - 挤压风险
    5. smart_money_liquidity - 聪明钱流动性
    
    这些因子通常比技术指标有更高的alpha价值。
    """)

