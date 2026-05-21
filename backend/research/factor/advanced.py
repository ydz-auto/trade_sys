"""
高级因子实现 - 真正的系统因子

因子类型：
1. Sentiment (情绪因子) - 市场情绪、资金流向
2. OnChain (链上因子) - 链上数据
3. Macro (宏观因子) - 宏观经济
4. Composite (复合因子) - 多因子组合
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass


# =============================================================================
# 情绪因子 (Sentiment Factors)
# =============================================================================

class SentimentFactors:
    """情绪因子 - 捕捉市场参与者的情绪状态"""
    
    @staticmethod
    def fear_greed_index(close: pd.Series, volume: pd.Series, volatility: pd.Series) -> pd.Series:
        """
        恐惧贪婪指数
        
        综合指标：
        - 价格动量 (动量因子)
        - 波动率 (恐慌指标)
        - 成交量变化 (情绪强度)
        
        范围: 0-100, 50为中性
        """
        # 价格动量 (0-40分)
        returns = close.pct_change(7)
        momentum = (returns - returns.mean()) / (returns.std() + 1e-10)
        momentum_score = 20 + momentum * 20  # 归一化到0-40
        
        # 波动率因子 (0-30分) - 高波动=恐惧
        vol_score = 15 - np.clip(volatility / volatility.mean() * 15, 0, 15)
        
        # 成交量因子 (0-30分) - 放量=情绪强烈
        vol_ratio = volume / volume.rolling(20).mean()
        vol_score = np.clip(vol_ratio * 15, 0, 30)
        
        # 综合
        fear_greed = momentum_score + vol_score + vol_score
        
        return np.clip(fear_greed, 0, 100)
    
    @staticmethod
    def funding_rate_sentiment(funding_rates: pd.Series) -> pd.Series:
        """
        资金费率情绪因子
        
        - 正资金费率 → 多头情绪过度 → 反向信号
        - 负资金费率 → 空头情绪过度 → 反向信号
        """
        # 资金费率偏离均值 → 极端情绪
        deviation = funding_rates - funding_rates.rolling(24).mean()
        return -deviation * 10  # 反向指标
    
    @staticmethod
    def whale_wallet_flow(
        large_transfers: pd.Series,  # 大额转账
        exchange_flow: pd.Series       # 交易所净流入
    ) -> pd.Series:
        """
        巨鲸资金流向
        
        - 大额转入交易所 → 卖出信号 (负面)
        - 大额转出交易所 → 买入信号 (正面)
        """
        whale_signal = -large_transfers + exchange_flow
        return whale_signal
    
    @staticmethod
    def social_volume_sentiment(social_positive: pd.Series, social_negative: pd.Series) -> pd.Series:
        """
        社交媒体情绪因子
        
        - 正向讨论 / 负向讨论 比率
        """
        total = social_positive + social_negative + 1
        sentiment = (social_positive - social_negative) / total
        return sentiment
    
    @staticmethod
    def long_short_ratio(long_pos: pd.Series, short_pos: pd.Series) -> pd.Series:
        """
        多空比率因子
        
        - 高多空比 → 过度看多 → 反向信号
        """
        ratio = long_pos / (short_pos + 1)
        z_score = (ratio - ratio.rolling(24).mean()) / (ratio.rolling(24).std() + 1e-10)
        return -z_score  # 反向指标


# =============================================================================
# 链上因子 (OnChain Factors)
# =============================================================================

class OnChainFactors:
    """链上因子 - 基于区块链数据的因子"""
    
    @staticmethod
    def holder_growth(new_addresses: pd.Series) -> pd.Series:
        """
        持币地址增长
        
        - 地址数增加 → 散户入场 → 潜在见顶
        - 地址数减少 → 筹码集中 → 潜在见底
        """
        growth_rate = new_addresses.pct_change(7)
        return growth_rate
    
    @staticmethod
    def exchange_reserve_flow(
        exchange_inflow: pd.Series,
        exchange_outflow: pd.Series
    ) -> pd.Series:
        """
        交易所准备金流量
        
        - 净流入增加 → 抛压增大
        - 净流出增加 → 积累信号
        """
        net_flow = exchange_inflow - exchange_outflow
        inflow_mean = exchange_inflow.rolling(window=24, min_periods=1).mean()
        flow_signal = -net_flow / (inflow_mean + 1e-10)
        return flow_signal
    
    @staticmethod
    def mining_difficulty_adjustment(difficulty_change: pd.Series) -> pd.Series:
        """
        挖矿难度调整因子
        
        - 难度上调 → 网络健康，但可能已过挖矿利润高点
        - 难度下调 → 网络压力减轻
        """
        return difficulty_change * -1  # 反向
    
    @staticmethod
    def gas_price_network_usage(
        gas_price: pd.Series,
        gas_used: pd.Series
    ) -> pd.Series:
        """
        Gas价格与网络使用率
        
        - 高Gas + 高使用 → 网络繁忙 → 价格支撑
        """
        gas_mean = gas_price.rolling(window=24, min_periods=1).mean()
        gas_std = gas_price.rolling(window=24, min_periods=1).std()
        usage_mean = gas_used.rolling(window=24, min_periods=1).mean()
        usage_std = gas_used.rolling(window=24, min_periods=1).std()
        
        gas_normalized = (gas_price - gas_mean) / (gas_std + 1e-10)
        usage_normalized = (gas_used - usage_mean) / (usage_std + 1e-10)
        return (gas_normalized + usage_normalized) / 2
    
    @staticmethod
    def realized_cap_hodl_wave(
        short_term_hodl: pd.Series,
        long_term_hodl: pd.Series
    ) -> pd.Series:
        """
        已实现cap与HODL波浪
        
        反映持币者结构
        """
        hodl_ratio = long_term_hodl / (short_term_hodl + long_term_hodl + 1)
        return hodl_ratio


# =============================================================================
# 宏观因子 (Macro Factors)
# =============================================================================

class MacroFactors:
    """宏观因子 - 与传统市场相关的因子"""
    
    @staticmethod
    def correlation_with_stocks(
        btc_returns: pd.Series,
        spy_returns: pd.Series  # S&P 500
    ) -> pd.Series:
        """
        与美股相关性
        
        - 相关性升高 → 风险资产属性增强
        - 相关性降低 → 避险资产属性
        """
        window = 20
        corr = btc_returns.rolling(window).corr(spy_returns)
        return corr
    
    @staticmethod
    def dollar_index_relationship(
        btc_price: pd.Series,
        dxy: pd.Series  # 美元指数
    ) -> pd.Series:
        """
        美元指数关系
        
        - 美元走强 → 风险资产承压
        - 美元走弱 → 风险资产受益
        """
        dxy_change = dxy.pct_change()
        btc_change = btc_price.pct_change()
        return -btc_change.corr(dxy_change) * dxy_change
    
    @staticmethod
    def interest_rate_environment(
        real_yield: pd.Series,  # 实际利率
        risk_on: pd.Series       # 风险偏好
    ) -> pd.Series:
        """
        利率环境因子
        
        - 低实际利率 → 利好BTC
        - 高实际利率 → 压力BTC
        """
        return -real_yield + risk_on
    
    @staticmethod
    def cross_asset_momentum(
        btc_returns: pd.Series,
        gold_returns: pd.Series,
        spy_returns: pd.Series
    ) -> pd.Series:
        """
        跨资产动量
        
        多资产动量共振
        """
        avg_momentum = (btc_returns + gold_returns * 0.5 + spy_returns * 0.3) / 2.8
        return avg_momentum


# =============================================================================
# 复合因子 (Composite Factors)
# =============================================================================

class CompositeFactors:
    """复合因子 - 组合多个基础因子"""
    
    @staticmethod
    def sentiment_momentum_combo(
        fear_greed: pd.Series,
        funding_rate: pd.Series,
        whale_flow: pd.Series,
        window: int = 24
    ) -> pd.Series:
        """
        情绪-动量组合
        
        综合市场情绪 + 资金费率 + 巨鲸流向
        """
        fg_mean = fear_greed.rolling(window=window, min_periods=1).mean()
        fg_std = fear_greed.rolling(window=window, min_periods=1).std()
        fr_mean = funding_rate.rolling(window=window, min_periods=1).mean()
        fr_std = funding_rate.rolling(window=window, min_periods=1).std()
        wf_mean = whale_flow.rolling(window=window, min_periods=1).mean()
        wf_std = whale_flow.rolling(window=window, min_periods=1).std()
        
        fg_norm = (fear_greed - fg_mean) / (fg_std + 1e-10)
        fr_norm = (funding_rate - fr_mean) / (fr_std + 1e-10)
        wf_norm = (whale_flow - wf_mean) / (wf_std + 1e-10)
        
        return 0.4 * fg_norm + 0.3 * fr_norm + 0.3 * wf_norm
    
    @staticmethod
    def onchain_accumulation_score(
        holder_growth: pd.Series,
        exchange_flow: pd.Series,
        difficulty: pd.Series
    ) -> pd.Series:
        """
        链上积累评分
        
        综合地址增长 + 交易所流量 + 挖矿难度
        """
        hg_norm = (holder_growth - holder_growth.mean()) / (holder_growth.std() + 1e-10)
        ef_norm = (exchange_flow - exchange_flow.mean()) / (exchange_flow.std() + 1e-10)
        df_norm = (difficulty - difficulty.mean()) / (difficulty.std() + 1e-10)
        
        return 0.4 * hg_norm + 0.35 * ef_norm + 0.25 * df_norm
    
    @staticmethod
    def macro_risk_regime(
        correlation: pd.Series,
        dxy_relation: pd.Series,
        interest_env: pd.Series
    ) -> pd.Series:
        """
        宏观风险状态
        
        综合相关性 + 美元 + 利率
        """
        corr_norm = (correlation - correlation.mean()) / (correlation.std() + 1e-10)
        dxy_norm = (dxy_relation - dxy_relation.mean()) / (dxy_relation.std() + 1e-10)
        int_norm = (interest_env - interest_env.mean()) / (interest_env.std() + 1e-10)
        
        # 风险状态: 正=风险偏好, 负=风险规避
        return corr_norm + dxy_norm + int_norm
    
    @staticmethod
    def cross_asset_rotation(
        btc_momentum: pd.Series,
        eth_momentum: pd.Series,
        defi_momentum: pd.Series
    ) -> pd.Series:
        """
        跨资产轮动因子
        
        捕捉资金在不同加密资产间的流动
        """
        # 相对强弱
        btc_str = btc_momentum - eth_momentum
        eth_defi = eth_momentum - defi_momentum
        
        return btc_str * 0.5 + eth_defi * 0.5


# =============================================================================
# 高级因子计算器
# =============================================================================

@dataclass
class SystemFactor:
    """系统级因子"""
    name: str
    category: str  # sentiment, onchain, macro, composite
    values: pd.Series
    ic: float = 0.0
    rank_ic: float = 0.0
    description: str = ""


class AdvancedFactorCalculator:
    """高级因子计算器
    
    完整系统因子计算，支持：
    - 情绪因子
    - 链上因子
    - 宏观因子
    - 复合因子
    """
    
    def __init__(self):
        self.sentiment = SentimentFactors()
        self.onchain = OnChainFactors()
        self.macro = MacroFactors()
        self.composite = CompositeFactors()
        self.factors: Dict[str, SystemFactor] = {}
    
    def calculate_sentiment_factors(
        self,
        close: pd.Series,
        volume: pd.Series,
        volatility: pd.Series,
        funding_rates: Optional[pd.Series] = None,
        large_transfers: Optional[pd.Series] = None,
        exchange_inflow: Optional[pd.Series] = None,
        exchange_outflow: Optional[pd.Series] = None,
    ) -> Dict[str, SystemFactor]:
        """计算情绪因子"""
        factors = {}
        
        # 恐惧贪婪指数
        if volatility is not None:
            fg = self.sentiment.fear_greed_index(close, volume, volatility)
            factors['fear_greed_index'] = SystemFactor(
                name='fear_greed_index',
                category='sentiment',
                values=fg,
                description='市场恐惧贪婪指数 (0-100)'
            )
        
        # 资金费率情绪
        if funding_rates is not None:
            fr = self.sentiment.funding_rate_sentiment(funding_rates)
            factors['funding_rate_sentiment'] = SystemFactor(
                name='funding_rate_sentiment',
                category='sentiment',
                values=fr,
                description='资金费率情绪 (反向指标)'
            )
        
        # 巨鲸资金流向
        if large_transfers is not None and exchange_inflow is not None:
            wf = self.sentiment.whale_wallet_flow(large_transfers, exchange_inflow)
            factors['whale_flow'] = SystemFactor(
                name='whale_flow',
                category='sentiment',
                values=wf,
                description='巨鲸资金流向'
            )
        
        return factors
    
    def calculate_onchain_factors(
        self,
        new_addresses: Optional[pd.Series] = None,
        exchange_inflow: Optional[pd.Series] = None,
        exchange_outflow: Optional[pd.Series] = None,
        gas_price: Optional[pd.Series] = None,
        gas_used: Optional[pd.Series] = None,
    ) -> Dict[str, SystemFactor]:
        """计算链上因子"""
        factors = {}
        
        if new_addresses is not None:
            hg = self.onchain.holder_growth(new_addresses)
            factors['holder_growth'] = SystemFactor(
                name='holder_growth',
                category='onchain',
                values=hg,
                description='持币地址增长'
            )
        
        if exchange_inflow is not None and exchange_outflow is not None:
            ef = self.onchain.exchange_reserve_flow(exchange_inflow, exchange_outflow)
            factors['exchange_flow'] = SystemFactor(
                name='exchange_flow',
                category='onchain',
                values=ef,
                description='交易所准备金流量'
            )
        
        if gas_price is not None and gas_used is not None:
            gn = self.onchain.gas_price_network_usage(gas_price, gas_used)
            factors['gas_network'] = SystemFactor(
                name='gas_network',
                category='onchain',
                values=gn,
                description='Gas价格与网络使用'
            )
        
        return factors
    
    def calculate_macro_factors(
        self,
        btc_returns: pd.Series,
        spy_returns: Optional[pd.Series] = None,
        dxy: Optional[pd.Series] = None,
        gold_returns: Optional[pd.Series] = None,
    ) -> Dict[str, SystemFactor]:
        """计算宏观因子"""
        factors = {}
        
        if spy_returns is not None:
            corr = self.macro.correlation_with_stocks(btc_returns, spy_returns)
            factors['stock_correlation'] = SystemFactor(
                name='stock_correlation',
                category='macro',
                values=corr,
                description='与美股相关性'
            )
        
        if dxy is not None and spy_returns is not None:
            cam = self.macro.cross_asset_momentum(
                btc_returns, gold_returns or btc_returns, spy_returns
            )
            factors['cross_asset_momentum'] = SystemFactor(
                name='cross_asset_momentum',
                category='macro',
                values=cam,
                description='跨资产动量'
            )
        
        return factors
    
    def calculate_composite_factors(
        self,
        fear_greed: Optional[pd.Series] = None,
        funding_rate: Optional[pd.Series] = None,
        whale_flow: Optional[pd.Series] = None,
        holder_growth: Optional[pd.Series] = None,
        exchange_flow: Optional[pd.Series] = None,
        correlation: Optional[pd.Series] = None,
    ) -> Dict[str, SystemFactor]:
        """计算复合因子"""
        factors = {}
        
        # 情绪-动量组合
        if all(v is not None for v in [fear_greed, funding_rate, whale_flow]):
            smc = self.composite.sentiment_momentum_combo(
                fear_greed, funding_rate, whale_flow
            )
            factors['sentiment_momentum'] = SystemFactor(
                name='sentiment_momentum',
                category='composite',
                values=smc,
                description='情绪动量组合'
            )
        
        # 链上积累评分
        if all(v is not None for v in [holder_growth, exchange_flow]):
            # 用fear_greed代替difficulty
            difficulty = fear_greed * 0.01 if fear_greed is not None else None
            if difficulty is not None:
                eas = self.composite.onchain_accumulation_score(
                    holder_growth, exchange_flow, difficulty
                )
                factors['accumulation_score'] = SystemFactor(
                    name='accumulation_score',
                    category='composite',
                    values=eas,
                    description='链上积累评分'
                )
        
        return factors
    
    def evaluate_factors(
        self,
        factors: Dict[str, SystemFactor],
        forward_returns: pd.Series
    ) -> Dict[str, SystemFactor]:
        """评估因子IC"""
        for name, factor in factors.items():
            valid = ~(factor.values.isna() | forward_returns.isna())
            if valid.sum() > 30:
                factor.ic = factor.values[valid].corr(forward_returns[valid])
                
                try:
                    from scipy import stats
                    factor.rank_ic = stats.spearmanr(
                        factor.values[valid], forward_returns[valid]
                    )[0]
                except:
                    factor.rank_ic = 0.0
        
        return factors


# =============================================================================
# 演示
# =============================================================================

def generate_mock_data() -> Dict[str, pd.Series]:
    """生成模拟数据"""
    n = 500
    dates = pd.date_range(end=datetime.now(), periods=n, freq="1h")
    
    np.random.seed(42)
    price = 50000.0
    prices = [price]
    for i in range(1, n):
        price = price * (1 + np.random.normal(0.0005, 0.02))
        prices.append(price)
    
    close = pd.Series(prices, index=dates)
    returns = close.pct_change()
    
    # 生成各种模拟数据
    data = {
        'close': close,
        'volume': pd.Series(np.random.lognormal(10, 0.5, n), index=dates),
        'volatility': pd.Series(np.random.uniform(0.01, 0.05, n), index=dates),
        'funding_rates': pd.Series(np.random.normal(0.001, 0.003, n), index=dates),
        'large_transfers': pd.Series(np.random.lognormal(8, 1, n), index=dates),
        'exchange_inflow': pd.Series(np.random.lognormal(9, 0.5, n), index=dates),
        'exchange_outflow': pd.Series(np.random.lognormal(9, 0.5, n), index=dates),
        'new_addresses': pd.Series(np.random.lognormal(6, 0.3, n), index=dates),
        'gas_price': pd.Series(np.random.uniform(20, 100, n), index=dates),
        'spy_returns': pd.Series(np.random.normal(0.0003, 0.01, n), index=dates),
        'dxy': pd.Series(np.random.uniform(95, 110, n), index=dates),
    }
    
    return data


def main():
    print("\n" + "="*80)
    print("  🚀 系统因子计算 - 高级因子演示")
    print("="*80)
    
    # 1. 生成数据
    print("\n[1/4] 生成模拟数据...")
    data = generate_mock_data()
    print(f"      数据点: {len(data['close'])}")
    
    # 2. 计算因子
    print("\n[2/4] 计算系统因子...")
    calculator = AdvancedFactorCalculator()
    
    # 情绪因子
    sentiment_factors = calculator.calculate_sentiment_factors(
        close=data['close'],
        volume=data['volume'],
        volatility=data['volatility'],
        funding_rates=data['funding_rates'],
        large_transfers=data['large_transfers'],
        exchange_inflow=data['exchange_inflow'],
        exchange_outflow=data['exchange_outflow'],
    )
    
    # 链上因子
    onchain_factors = calculator.calculate_onchain_factors(
        new_addresses=data['new_addresses'],
        exchange_inflow=data['exchange_inflow'],
        exchange_outflow=data['exchange_outflow'],
        gas_price=data['gas_price'],
        gas_used=data['volume'] / 1000,
    )
    
    # 宏观因子
    macro_factors = calculator.calculate_macro_factors(
        btc_returns=data['close'].pct_change(),
        spy_returns=data['spy_returns'],
        dxy=data['dxy'],
    )
    
    # 复合因子
    composite_factors = calculator.calculate_composite_factors(
        fear_greed=sentiment_factors.get('fear_greed_index', pd.Series()).values,
        funding_rate=sentiment_factors.get('funding_rate_sentiment', pd.Series()).values,
        whale_flow=sentiment_factors.get('whale_flow', pd.Series()).values,
        holder_growth=onchain_factors.get('holder_growth', pd.Series()).values,
        exchange_flow=onchain_factors.get('exchange_flow', pd.Series()).values,
    )
    
    # 3. 评估因子
    print("\n[3/4] 评估因子表现...")
    forward_returns = data['close'].pct_change(5).shift(-5)
    
    all_factors = {}
    all_factors.update(sentiment_factors)
    all_factors.update(onchain_factors)
    all_factors.update(macro_factors)
    all_factors.update(composite_factors)
    
    all_factors = calculator.evaluate_factors(all_factors, forward_returns)
    
    # 4. 展示结果
    print("\n[4/4] 因子表现排名:")
    print(f"\n      {'因子名称':<30} {'类别':<12} {'IC':>10} {'RankIC':>10}")
    print("      " + "-"*70)
    
    sorted_factors = sorted(
        all_factors.items(),
        key=lambda x: abs(x[1].ic),
        reverse=True
    )
    
    for name, factor in sorted_factors[:10]:
        print(f"      {factor.name:<30} {factor.category:<12} {factor.ic:>10.4f} {factor.rank_ic:>10.4f}")
    
    # 总结
    print("\n" + "="*80)
    print("  ✅ 系统因子计算完成！")
    print("="*80)
    print("\n系统真正的因子类型:")
    print("  📊 Sentiment (情绪): 恐惧贪婪、巨鲸流向、资金费率")
    print("  🔗 OnChain (链上): 地址增长、交易所流量、Gas价格")
    print("  🌐 Macro (宏观): 与美股相关性、跨资产动量")
    print("  🔀 Composite (复合): 多因子组合")
    print("\n技术指标 (MACD/RSI) 只是计算这些因子的'底层原料'!")


if __name__ == "__main__":
    main()

