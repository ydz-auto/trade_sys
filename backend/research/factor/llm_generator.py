"""
LLM Factor Generator - LLM辅助因子生成

功能：
1. LLM生成因子表达式
2. LLM生成参数空间
3. LLM生成金融逻辑组合
4. LLM分析因子表现

这是AI-assisted Quant Research的核心。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass
class FactorExpression:
    """LLM生成的因子表达式"""
    expression: str
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    category: str = "technical"


@dataclass
class FactorHypothesis:
    """LLM生成的因子假设"""
    hypothesis: str
    factor_expression: FactorExpression
    rationale: str
    test_predicate: str
    confidence: float = 0.5


@dataclass
class FactorAnalysis:
    """LLM生成的因子分析"""
    factor_name: str
    ic: float
    rank_ic: float
    turnover: float
    decay: float
    
    analysis_summary: str
    potential_improvements: List[str]
    regime_sensitivity: Dict[str, str] = field(default_factory=dict)


class LLMFactorGenerator:
    """
    LLM因子生成器
    
    注意：实际使用时需要接入LLM API
    这里用示例演示逻辑架构
    """
    
    def __init__(self):
        self.generated_factors: List[FactorHypothesis] = []
        self.analysis_history: List[FactorAnalysis] = []
    
    def generate_factor_expression(
        self,
        available_columns: List[str],
        factor_category: str = "technical",
        style: str = "momentum"
    ) -> FactorExpression:
        """
        基于可用列生成因子表达式
        
        实际使用时调用LLM API
        """
        
        # 示例：模拟LLM生成的结果
        if factor_category == "derivatives":
            return FactorExpression(
                expression="(funding_rate_zscore * oi_growth) / (volatility + 1e-6)",
                name="funding_oi_pressure",
                description="资金费率与持仓量综合压力",
                parameters={"zscore_window": 24, "oi_window": 12},
                category="derivatives"
            )
        
        elif factor_category == "microstructure":
            return FactorExpression(
                expression="(taker_buy_ratio - taker_sell_ratio) / (spread + 1e-6)",
                name="taker_flow_pressure",
                description="主动买卖压力",
                parameters={"ratio_window": 5},
                category="microstructure"
            )
        
        else:
            # 技术因子示例
            return FactorExpression(
                expression="(rsi_14 - 50) * momentum_10",
                name="rsi_momentum_combo",
                description="RSI与动量组合因子",
                parameters={"rsi_period": 14, "mom_period": 10},
                category="technical"
            )
    
    def generate_parameter_space(
        self,
        factor_name: str,
        market_regime: str = "volatile"
    ) -> Dict[str, List[Any]]:
        """
        根据市场特征生成参数空间
        
        实际使用时调用LLM API
        """
        
        if market_regime == "volatile":
            return {
                "lookback": [3, 5, 8, 13],
                "vol_multiplier": [1.5, 2.0, 2.5],
                "confidence": [0.1, 0.2, 0.3]
            }
        elif market_regime == "low_vol":
            return {
                "lookback": [21, 34, 55],
                "vol_multiplier": [0.8, 1.0, 1.2],
                "confidence": [0.05, 0.1, 0.15]
            }
        else:
            return {
                "lookback": [5, 10, 20],
                "vol_multiplier": [1.0, 1.5, 2.0],
                "confidence": [0.1, 0.2]
            }
    
    def generate_composite_factor(
        self,
        existing_factors: List[str],
        investment_theme: str = "squeeze"
    ) -> FactorHypothesis:
        """
        生成组合因子假设
        
        实际使用时调用LLM API
        """
        
        if investment_theme == "squeeze":
            return FactorHypothesis(
                hypothesis="当资金费率极端正且持仓量增长时，可能存在挤压风险",
                factor_expression=FactorExpression(
                    expression="funding_rate_zscore * oi_growth / abs(price_return)",
                    name="squeeze_risk_factor",
                    description="挤压风险因子",
                    parameters={"zscore_window": 24, "oi_window": 12}
                ),
                rationale="高资金费率表明多头情绪过度，持仓量增长表明杠杆增加，横盘表明可能是陷阱",
                test_predicate="当squeeze_factor > 2.0时，未来24小时应该下跌"
            )
        
        elif investment_theme == "smart_money":
            return FactorHypothesis(
                hypothesis="交易所流出大额增加但价格不涨，可能是聪明钱积累",
                factor_expression=FactorExpression(
                    expression="exchange_outflow_magnitude / (volatility + abs(price_return))",
                    name="smart_money_accumulation",
                    description="聪明钱积累因子",
                    parameters={"flow_window": 12}
                ),
                rationale="大量资金流出交易所，但价格不涨，可能是长期持有者积累",
                test_predicate="当accumulation_factor > 1.5时，未来7天应该上涨"
            )
        
        else:
            return FactorHypothesis(
                hypothesis="技术指标组合可能有更好效果",
                factor_expression=FactorExpression(
                    expression="rsi_zscore * macd_signal",
                    name="rsi_macd_combo",
                    description="RSI与MACD组合",
                    parameters={}
                ),
                rationale="",
                test_predicate=""
            )
    
    def analyze_factor_performance(
        self,
        factor_name: str,
        factor_metrics: Dict[str, float],
        history_data: Optional[pd.DataFrame] = None
    ) -> FactorAnalysis:
        """
        分析因子表现
        
        实际使用时调用LLM API
        """
        
        ic = factor_metrics.get("ic", 0)
        turnover = factor_metrics.get("turnover", 0)
        
        summary = ""
        improvements = []
        
        if abs(ic) < 0.02:
            summary = "因子IC过低，预测能力有限"
            improvements = [
                "尝试更长预测周期",
                "考虑因子标准化方式",
                "尝试市场状态条件"
            ]
        elif turnover > 0.5:
            summary = "因子IC不错，但换手率过高，交易成本会吃掉收益"
            improvements = [
                "降低调仓频率",
                "增加信号平滑",
                "结合波动率过滤器"
            ]
        else:
            summary = "因子表现良好，可以考虑进一步优化"
            improvements = [
                "尝试参数优化",
                "考虑市场状态",
                "组合其他因子"
            ]
        
        return FactorAnalysis(
            factor_name=factor_name,
            ic=ic,
            rank_ic=factor_metrics.get("rank_ic", 0),
            turnover=turnover,
            decay=factor_metrics.get("decay", 0),
            analysis_summary=summary,
            potential_improvements=improvements
        )


class FactorExpressionParser:
    """
    安全解析因子表达式
    
    支持安全计算LLM生成的因子
    """
    
    def __init__(self):
        self.allowed_functions = {
            "rsi": self._compute_rsi,
            "macd": self._compute_macd,
            "sma": self._compute_sma,
            "ema": self._compute_ema,
            "std": self._compute_std,
            "zscore": self._compute_zscore,
            "momentum": self._compute_momentum,
            "return": self._compute_return
        }
    
    def compute_expression(
        self,
        df: pd.DataFrame,
        expression: str
    ) -> pd.Series:
        """
        安全计算因子表达式
        
        简单实现，实际需要更严格的安全检查
        """
        
        try:
            # 简单替换
            expr = expression.lower()
            
            # 替换列名
            for col in df.columns:
                if col in expr:
                    expr = expr.replace(col, f"df['{col}']")
            
            # 替换简单函数
            expr = expr.replace("sma", "df['close'].rolling")
            expr = expr.replace("ema", "df['close'].ewm")
            
            # 安全计算（实际应该更严格）
            # 这里简化处理
            result = pd.Series(index=df.index, dtype=float)
            
            # 预计算基础指标
            returns = df['close'].pct_change()
            rsi = self._compute_rsi(df['close'])
            sma_10 = df['close'].rolling(10).mean()
            
            # 简单预定义表达式支持
            if "rsi" in expression and "momentum" in expression:
                result = (rsi - 50) * (df['close'] / df['close'].shift(10) - 1)
            elif "funding" in expression and "oi" in expression:
                result = (df.get('funding_rate', 0) * 1000) * df.get('oi_change', 0)
            elif "taker" in expression:
                result = (df.get('taker_buy', 0) - df.get('taker_sell', 0))
            else:
                result = df['close'].pct_change()
            
            return result
            
        except Exception as e:
            print(f"计算因子表达式失败: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def _compute_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))
    
    def _compute_macd(self, close: pd.Series) -> pd.Series:
        fast = close.ewm(span=12).mean()
        slow = close.ewm(span=26).mean()
        return fast - slow
    
    def _compute_sma(self, close: pd.Series, period: int = 10) -> pd.Series:
        return close.rolling(period).mean()
    
    def _compute_ema(self, close: pd.Series, period: int = 12) -> pd.Series:
        return close.ewm(span=period).mean()
    
    def _compute_std(self, close: pd.Series, period: int = 20) -> pd.Series:
        return close.pct_change().rolling(period).std()
    
    def _compute_zscore(self, data: pd.Series, period: int = 20) -> pd.Series:
        mean = data.rolling(period).mean()
        std = data.rolling(period).std()
        return (data - mean) / (std + 1e-10)
    
    def _compute_momentum(self, close: pd.Series, period: int = 10) -> pd.Series:
        return close / close.shift(period) - 1
    
    def _compute_return(self, close: pd.Series, period: int = 1) -> pd.Series:
        return close.pct_change(period)


# 示例使用
if __name__ == "__main__":
    print("="*80)
    print("  LLM Factor Generator 示例")
    print("="*80)
    
    # 1. 创建生成器
    generator = LLMFactorGenerator()
    parser = FactorExpressionParser()
    
    # 2. 生成技术因子
    print("\n[1] 生成技术因子...")
    tech_factor = generator.generate_factor_expression(
        available_columns=["close", "volume", "high", "low"],
        factor_category="technical"
    )
    print(f"    名称: {tech_factor.name}")
    print(f"    表达式: {tech_factor.expression}")
    print(f"    描述: {tech_factor.description}")
    
    # 3. 生成衍生品因子
    print("\n[2] 生成衍生品因子...")
    deriv_factor = generator.generate_factor_expression(
        available_columns=["funding_rate", "oi", "price"],
        factor_category="derivatives"
    )
    print(f"    名称: {deriv_factor.name}")
    print(f"    表达式: {deriv_factor.expression}")
    
    # 4. 生成金融假设
    print("\n[3] 生成因子假设...")
    hypothesis = generator.generate_composite_factor(
        existing_factors=["funding_rate", "oi"],
        investment_theme="squeeze"
    )
    print(f"    假设: {hypothesis.hypothesis}")
    print(f"    因子: {hypothesis.factor_expression.name}")
    print(f"    测试: {hypothesis.test_predicate}")
    
    # 5. 生成参数空间
    print("\n[4] 生成参数空间...")
    params = generator.generate_parameter_space("squeeze_factor", market_regime="volatile")
    print(f"    参数空间: {params}")
    
    # 6. 分析因子
    print("\n[5] 分析因子表现...")
    analysis = generator.analyze_factor_performance(
        factor_name="squeeze_risk_factor",
        factor_metrics={"ic": 0.035, "rank_ic": 0.028, "turnover": 0.45}
    )
    print(f"    总结: {analysis.analysis_summary}")
    print(f"    改进建议: {analysis.potential_improvements}")
    
    print("\n" + "="*80)
    print("  示例完成")
    print("="*80)
    print("""
    架构说明:
    
    LLMFactorGenerator → 生成因子表达式/假设
         ↓
    FactorExpressionParser → 安全计算因子
         ↓
    FactorEvaluator → IC/IR评估
         ↓
    WalkForwardEngine → 验证
         ↓
    AlphaPipeline → 部署
    """)

