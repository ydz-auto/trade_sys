"""
Auto Factor Generator - 自动因子生成器

功能：
1. 模板化因子生成 - 基于模板批量生成因子变体
2. 遗传编程因子进化 - 自动组合基础算子生成新因子
3. 因子组合优化 - 自动搜索最优因子组合
4. 特征重要性分析 - 评估因子预测能力

这是P3 Auto Research Pipeline的核心模块。
"""

import random
import itertools
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np
import pandas as pd
from scipy import stats

from infrastructure.logging import get_logger

logger = get_logger("research.factor_generator")

# =============================================================================
# 基础算子定义
# =============================================================================

class OperatorType(str, Enum):
    """算子类型"""
    PRICE = "price"
    VOLUME = "volume"
    RETURNS = "returns"
    MOVING_AVG = "ma"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    RATIO = "ratio"
    NORMALIZE = "normalize"


@dataclass
class Operator:
    """算子定义"""
    name: str
    func: Callable
    inputs: List[str]
    output_type: str = "float"
    description: str = ""


class OperatorLibrary:
    """算子库"""
    
    @staticmethod
    def get_library() -> Dict[str, Operator]:
        return {
            # 价格类算子
            "close": Operator("close", lambda x: x["close"], [], "price", "收盘价"),
            "open": Operator("open", lambda x: x["open"], [], "price", "开盘价"),
            "high": Operator("high", lambda x: x["high"], [], "price", "最高价"),
            "low": Operator("low", lambda x: x["low"], [], "price", "最低价"),
            "hl2": Operator("hl2", lambda x: (x["high"] + x["low"]) / 2, ["high", "low"], "price", "高低均价"),
            "ohlc4": Operator("ohlc4", lambda x: (x["open"] + x["high"] + x["low"] + x["close"]) / 4, 
                             ["open", "high", "low", "close"], "price", "OHLC均价"),
            
            # 收益率算子
            "returns_1": Operator("returns_1", lambda x: x["close"] / x["close"].shift(1) - 1, ["close"], "returns", "1期收益率"),
            "returns_n": Operator("returns_n", lambda x, n=5: x["close"] / x["close"].shift(n) - 1, ["close"], "returns", "N期收益率"),
            
            # 移动平均算子
            "sma_5": Operator("sma_5", lambda x: x["close"].rolling(5).mean(), ["close"], "ma", "5日均线"),
            "sma_10": Operator("sma_10", lambda x: x["close"].rolling(10).mean(), ["close"], "ma", "10日均线"),
            "sma_20": Operator("sma_20", lambda x: x["close"].rolling(20).mean(), ["close"], "ma", "20日均线"),
            "sma_60": Operator("sma_60", lambda x: x["close"].rolling(60).mean(), ["close"], "ma", "60日均线"),
            "ema_5": Operator("ema_5", lambda x: x["close"].ewm(span=5).mean(), ["close"], "ma", "5日指数均线"),
            "ema_20": Operator("ema_20", lambda x: x["close"].ewm(span=20).mean(), ["close"], "ma", "20日指数均线"),
            
            # 动量算子
            "momentum_5": Operator("momentum_5", lambda x: x["close"] - x["close"].shift(5), ["close"], "momentum", "5期动量"),
            "momentum_10": Operator("momentum_10", lambda x: x["close"] - x["close"].shift(10), ["close"], "momentum", "10期动量"),
            "momentum_20": Operator("momentum_20", lambda x: x["close"] - x["close"].shift(20), ["close"], "momentum", "20期动量"),
            
            # 波动率算子
            "std_10": Operator("std_10", lambda x: x["close"].pct_change().rolling(10).std(), ["close"], "volatility", "10期波动率"),
            "std_20": Operator("std_20", lambda x: x["close"].pct_change().rolling(20).std(), ["close"], "volatility", "20期波动率"),
            "atr_14": Operator("atr_14", lambda x: (x["high"] - x["low"]).rolling(14).mean(), ["high", "low"], "volatility", "ATR指标"),
            
            # RSI算子
            "rsi_6": Operator("rsi_6", lambda x: _compute_rsi(x["close"], 6), ["close"], "momentum", "RSI(6)"),
            "rsi_14": Operator("rsi_14", lambda x: _compute_rsi(x["close"], 14), ["close"], "momentum", "RSI(14)"),
            "rsi_28": Operator("rsi_28", lambda x: _compute_rsi(x["close"], 28), ["close"], "momentum", "RSI(28)"),
            
            # MACD算子
            "macd_line": Operator("macd_line", lambda x: _compute_macd(x["close"])[0], ["close"], "momentum", "MACD线"),
            "macd_signal": Operator("macd_signal", lambda x: _compute_macd(x["close"])[1], ["close"], "momentum", "MACD信号"),
            "macd_hist": Operator("macd_hist", lambda x: _compute_macd(x["close"])[2], ["close"], "momentum", "MACD柱"),
            
            # 布林带算子
            "bb_upper": Operator("bb_upper", lambda x: _compute_bollinger(x["close"], 20)[1], ["close"], "volatility", "布林上轨"),
            "bb_lower": Operator("bb_lower", lambda x: _compute_bollinger(x["close"], 20)[0], ["close"], "volatility", "布林下轨"),
            "bb_width": Operator("bb_width", lambda x: _compute_bollinger(x["close"], 20)[2], ["close"], "volatility", "布林带宽"),
            
            # 成交量算子
            "volume": Operator("volume", lambda x: x["volume"], [], "volume", "成交量"),
            "volume_sma_10": Operator("volume_sma_10", lambda x: x["volume"].rolling(10).mean(), ["volume"], "volume", "成交量均线"),
            "volume_ratio": Operator("volume_ratio", lambda x: x["volume"] / x["volume"].rolling(10).mean(), ["volume"], "ratio", "量比"),
            
            # 比率算子
            "price_to_sma20": Operator("price_to_sma20", lambda x: x["close"] / x["close"].rolling(20).mean(), ["close"], "ratio", "价格/均线比"),
            "high_low_ratio": Operator("high_low_ratio", lambda x: (x["high"] - x["low"]) / x["close"], ["high", "low", "close"], "ratio", "振幅比"),
        }


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """计算RSI"""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """计算MACD"""
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def _compute_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """计算布林带"""
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
    """因子模板"""
    name: str
    description: str
    expression: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    category: str = "technical"


class FactorTemplateLibrary:
    """因子模板库"""
    
    TEMPLATES = [
        # 动量类
        FactorTemplate("momentum", "动量因子", "close - close.shift({period})", {"period": [5, 10, 20]}),
        FactorTemplate("momentum_pct", "动量百分比", "(close - close.shift({period})) / close.shift({period})", {"period": [5, 10, 20]}),
        FactorTemplate("acceleration", "动量加速度", "momentum - momentum.shift({period})", {"period": [5, 10]}),
        
        # 均值回归类
        FactorTemplate("ma_cross", "均线交叉", "sma({fast}) - sma({slow})", {"fast": [5, 7, 10], "slow": [20, 30, 60]}),
        FactorTemplate("price_to_ma", "价格均线比", "close / sma({period})", {"period": [10, 20, 60]}),
        FactorTemplate("z_score", "Z-Score", "(close - sma({period})) / std({period})", {"period": [20, 60]}),
        
        # 波动率类
        FactorTemplate("volatility_ratio", "波动率比", "std({short}) / std({long})", {"short": [5, 10], "long": [20, 60]}),
        FactorTemplate("atr_ratio", "ATR相对波动", "atr({period}) / close", {"period": [14, 28]}),
        
        # 成交量类
        FactorTemplate("volume_price_trend", "量价趋势", "(close - close.shift(1)) * volume", {}),
        FactorTemplate("volume_momentum", "成交量动量", "volume / volume_sma({period})", {"period": [5, 10, 20]}),
        
        # RSI变体
        FactorTemplate("rsi_divergence", "RSI背离", "rsi({period}) - rsi({period}).shift({shift})", {"period": [14], "shift": [5, 10]}),
        FactorTemplate("rsi_zscore", "RSI Z-Score", "(rsi({period}) - rsi({period}).mean()) / rsi({period}).std()", {"period": [14]}),
        
        # MACD变体
        FactorTemplate("macd_slope", "MACD斜率", "macd_hist - macd_hist.shift({period})", {"period": [5]}),
        FactorTemplate("macd_crossover", "MACD穿越信号", "macd_line - macd_signal", {}),
    ]
    
    @classmethod
    def generate_variants(cls) -> List[FactorTemplate]:
        """从模板生成所有变体"""
        variants = []
        for template in cls.TEMPLATES:
            if not template.parameters:
                variants.append(template)
            else:
                keys = list(template.parameters.keys())
                values = list(template.parameters.values())
                for combo in itertools.product(*values):
                    params = dict(zip(keys, combo))
                    variant = FactorTemplate(
                        name=f"{template.name}_{'_'.join(str(v) for v in combo)}",
                        description=template.description,
                        expression=template.expression.format(**params),
                        parameters=params,
                        category=template.category
                    )
                    variants.append(variant)
        return variants


# =============================================================================
# 遗传编程因子进化
# =============================================================================

@dataclass
class Gene:
    """基因"""
    operator: str
    params: Dict[str, Any] = field(default_factory=dict)
    children: List["Gene"] = field(default_factory=list)


class GeneticFactorGenerator:
    """遗传编程因子生成器"""
    
    def __init__(
        self,
        population_size: int = 100,
        generations: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7
    ):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.operators = OperatorLibrary.get_library()
        
    def generate_random_gene(self, depth: int = 2) -> Gene:
        """随机生成基因"""
        if depth <= 0:
            op = random.choice(["close", "open", "volume"])
            return Gene(operator=op)
        
        # 50%概率是叶子节点
        if random.random() < 0.5:
            return self.generate_random_gene(depth - 1)
        
        # 选择复合算子
        compound_ops = ["sma_5", "sma_10", "sma_20", "std_10", "std_20", 
                       "momentum_5", "momentum_10", "rsi_14", "macd_hist"]
        op = random.choice(compound_ops)
        child = self.generate_random_gene(depth - 1)
        return Gene(operator=op, children=[child])
    
    def crossover(self, gene1: Gene, gene2: Gene) -> Tuple[Gene, Gene]:
        """交叉"""
        g1, g2 = self._copy_gene(gene1), self._copy_gene(gene2)
        # 简单实现：交换根节点的第一个子节点
        if g1.children and g2.children:
            g1.children[0], g2.children[0] = g2.children[0], g1.children[0]
        return g1, g2
    
    def mutate(self, gene: Gene) -> Gene:
        """变异"""
        g = self._copy_gene(gene)
        if random.random() < self.mutation_rate:
            g.operator = random.choice(list(self.operators.keys()))
        for child in g.children:
            self._mutate_recursive(child)
        return g
    
    def _mutate_recursive(self, gene: Gene):
        if random.random() < self.mutation_rate:
            gene.operator = random.choice(list(self.operators.keys()))
        for child in gene.children:
            self._mutate_recursive(child)
    
    def _copy_gene(self, gene: Gene) -> Gene:
        return Gene(
            operator=gene.operator,
            params=dict(gene.params),
            children=[self._copy_gene(c) for c in gene.children]
        )


# =============================================================================
# 自动因子生成器主类
# =============================================================================

@dataclass
class GeneratedFactor:
    """生成的因子"""
    name: str
    formula: str
    description: str
    category: str
    ic: float = 0.0
    rank_ic: float = 0.0
    ir: float = 0.0
    sharpe: float = 0.0
    turnover: float = 0.0
    score: float = 0.0


class AutoFactorGenerator:
    """自动因子生成器
    
    使用方法:
    generator = AutoFactorGenerator()
    generator.load_data(df)  # 加载数据
    factors = generator.generate_from_templates()  # 从模板生成
    factors = generator.generate_genetic(n_generations=20)  # 遗传编程
    factors = generator.select_top(factors, n=10)  # 筛选top因子
    """
    
    def __init__(
        self,
        min_ic: float = 0.02,
        min_ir: float = 0.3,
        top_n: int = 50
    ):
        self.min_ic = min_ic
        self.min_ir = min_ir
        self.top_n = top_n
        self.data: Optional[pd.DataFrame] = None
        self.templates = FactorTemplateLibrary.generate_variants()
        self.genetic_generator = GeneticFactorGenerator()
        
    def load_data(self, df: pd.DataFrame) -> "AutoFactorGenerator":
        """加载数据"""
        self.data = df.copy()
        return self
    
    def generate_from_templates(self) -> List[GeneratedFactor]:
        """从模板批量生成因子"""
        if self.data is None:
            raise ValueError("请先加载数据: load_data(df)")
        
        logger.info(f"从 {len(self.templates)} 个模板生成因子...")
        factors = []
        
        for template in self.templates:
            try:
                factor = self._compute_factor_from_template(template)
                if factor is not None:
                    factors.append(factor)
            except Exception as e:
                logger.warning(f"模板 {template.name} 计算失败: {e}")
        
        logger.info(f"生成了 {len(factors)} 个候选因子")
        return factors
    
    def _compute_factor_from_template(self, template: FactorTemplate) -> Optional[GeneratedFactor]:
        """根据模板计算因子"""
        df = self.data.copy()
        
        # 计算基础指标
        df["returns_1"] = df["close"].pct_change()
        
        # 预处理
        for period in [5, 10, 20, 60]:
            df[f"sma_{period}"] = df["close"].rolling(period).mean()
            df[f"std_{period}"] = df["close"].pct_change().rolling(period).std()
            df[f"momentum_{period}"] = df["close"] - df["close"].shift(period)
        
        df["rsi_14"] = _compute_rsi(df["close"], 14)
        df["macd_line"], df["macd_signal"], df["macd_hist"] = _compute_macd(df["close"])
        df["bb_lower"], df["bb_upper"], df["bb_width"] = _compute_bollinger(df["close"])
        
        # 计算模板表达式
        try:
            # 安全地计算表达式
            factor_values = self._safe_eval(template.expression, df)
            
            if factor_values is None or factor_values.isna().all():
                return None
            
            # 计算IC/IR
            forward_returns = df["close"].pct_change(5).shift(-5)
            ic = self._compute_ic(factor_values, forward_returns)
            rank_ic = self._compute_rank_ic(factor_values, forward_returns)
            
            # 计算因子换手率
            turnover = self._compute_turnover(factor_values)
            
            factor = GeneratedFactor(
                name=template.name,
                formula=template.expression,
                description=template.description,
                category=template.category,
                ic=ic,
                rank_ic=rank_ic,
                turnover=turnover
            )
            
            # 计算综合评分
            factor.score = self._compute_score(factor)
            
            return factor
            
        except Exception as e:
            logger.debug(f"计算 {template.name} 失败: {e}")
            return None
    
    def _safe_eval(self, expr: str, df: pd.DataFrame) -> Optional[pd.Series]:
        """安全地计算表达式"""
        # 替换函数名
        expr = expr.replace("sma(", "df['sma_")
        expr = expr.replace("std(", "df['std_")
        expr = expr.replace("momentum(", "df['momentum_")
        expr = expr.replace("rsi(", "df['rsi_")
        expr = expr.replace("macd(", "df['macd_")
        
        # 处理括号匹配
        replacements = {
            "df['sma_": "df['sma_",
            "df['std_": "df['std_",
            "df['momentum_": "df['momentum_",
            "df['rsi_": "df['rsi_",
            "df['macd_": "df['macd_",
        }
        
        try:
            # 简单替换
            for old, new in replacements.items():
                if old in expr:
                    pass  # 已经处理过了
            
            # 替换标准列名
            result = df.eval(expr, inplace=False)
            return result
        except:
            return None
    
    def generate_genetic(self, n_generations: int = 20) -> List[GeneratedFactor]:
        """使用遗传编程生成因子"""
        if self.data is None:
            raise ValueError("请先加载数据: load_data(df)")
        
        logger.info(f"使用遗传编程生成因子，{n_generations} 代...")
        factors = []
        
        population = [self.genetic_generator.generate_random_gene() for _ in range(50)]
        
        for gen in range(n_generations):
            # 评估
            for gene in population:
                try:
                    factor = self._compute_factor_from_gene(gene)
                    if factor and factor.ic > self.min_ic:
                        factors.append(factor)
                except:
                    pass
            
            # 选择
            population = sorted(population, key=lambda g: self._evaluate_gene(g), reverse=True)[:30]
            
            # 交叉变异
            new_population = list(population)
            for _ in range(20):
                p1, p2 = random.sample(population, 2)
                if random.random() < self.genetic_generator.crossover_rate:
                    c1, c2 = self.genetic_generator.crossover(p1, p2)
                    new_population.extend([c1, c2])
                else:
                    new_population.append(self.genetic_generator.mutate(p1))
            
            population = new_population[:self.genetic_generator.population_size]
            
            if gen % 5 == 0:
                logger.info(f"  Generation {gen}: {len(factors)} 候选因子")
        
        logger.info(f"遗传编程生成了 {len(factors)} 个候选因子")
        return factors
    
    def _compute_factor_from_gene(self, gene: Gene) -> Optional[GeneratedFactor]:
        """从基因计算因子"""
        df = self.data.copy()
        
        # 预处理
        for period in [5, 10, 20]:
            df[f"sma_{period}"] = df["close"].rolling(period).mean()
        df["rsi_14"] = _compute_rsi(df["close"], 14)
        df["macd_hist"] = _compute_macd(df["close"])[2]
        
        try:
            value = self._eval_gene(gene, df)
            if value is None or value.isna().all():
                return None
            
            forward_returns = df["close"].pct_change(5).shift(-5)
            ic = self._compute_ic(value, forward_returns)
            
            return GeneratedFactor(
                name=f"genetic_{gene.operator}",
                formula=str(gene),
                description="遗传编程生成",
                category="genetic",
                ic=ic,
                rank_ic=self._compute_rank_ic(value, forward_returns)
            )
        except:
            return None
    
    def _eval_gene(self, gene: Gene, df: pd.DataFrame) -> Optional[pd.Series]:
        """计算基因表达式"""
        op = self.genetic_generator.operators.get(gene.operator)
        if op is None:
            return None
        
        try:
            if gene.children:
                result = op.func(df, **gene.params)
                for child in gene.children:
                    child_result = self._eval_gene(child, df)
                    if child_result is not None:
                        result = result * child_result  # 默认组合方式
                return result
            else:
                return op.func(df)
        except:
            return None
    
    def _evaluate_gene(self, gene: Gene) -> float:
        """评估基因"""
        factor = self._compute_factor_from_gene(gene)
        return factor.score if factor else 0.0
    
    def select_top(self, factors: List[GeneratedFactor], n: int = 10) -> List[GeneratedFactor]:
        """筛选top因子"""
        valid = [f for f in factors if abs(f.ic) >= self.min_ic]
        sorted_factors = sorted(valid, key=lambda x: x.score, reverse=True)
        return sorted_factors[:n]
    
    def _compute_ic(self, factor: pd.Series, returns: pd.Series) -> float:
        """计算IC"""
        valid = ~(factor.isna() | returns.isna())
        if valid.sum() < 30:
            return 0.0
        return factor[valid].corr(returns[valid])
    
    def _compute_rank_ic(self, factor: pd.Series, returns: pd.Series) -> float:
        """计算RankIC"""
        valid = ~(factor.isna() | returns.isna())
        if valid.sum() < 30:
            return 0.0
        try:
            return stats.spearmanr(factor[valid], returns[valid])[0]
        except:
            return 0.0
    
    def _compute_turnover(self, factor: pd.Series, bins: int = 10) -> float:
        """计算换手率"""
        if len(factor) < bins * 2:
            return 0.0
        
        deciles = pd.qcut(factor, bins, labels=False, duplicates="drop")
        turnover = (deciles != deciles.shift()).mean()
        return turnover
    
    def _compute_score(self, factor: GeneratedFactor) -> float:
        """计算综合评分"""
        # IC * IR * (1 - turnover)
        ir = abs(factor.ic) / (factor.turnover + 0.01)
        score = abs(factor.ic) * min(ir, 2) * (1 - factor.turnover)
        return score
    
    def generate_report(self, factors: List[GeneratedFactor]) -> pd.DataFrame:
        """生成因子报告"""
        rows = []
        for f in factors:
            rows.append({
                "名称": f.name,
                "描述": f.description,
                "类别": f.category,
                "IC": f"{f.ic:.4f}",
                "RankIC": f"{f.rank_ic:.4f}",
                "换手率": f"{f.turnover:.2%}",
                "评分": f"{f.score:.4f}"
            })
        return pd.DataFrame(rows)


# =============================================================================
# 快速使用函数
# =============================================================================

def auto_generate_factors(
    df: pd.DataFrame,
    method: str = "templates",
    n_factors: int = 20,
    min_ic: float = 0.02
) -> Tuple[List[GeneratedFactor], pd.DataFrame]:
    """
    一键自动生成因子
    
    Args:
        df: 包含 OHLCV 的 DataFrame
        method: "templates" 或 "genetic"
        n_factors: 返回的因子数量
        min_ic: 最小IC阈值
    
    Returns:
        (选中的因子列表, 因子报告DataFrame)
    
    Example:
        >>> data = generate_mock_data()
        >>> factors, report = auto_generate_factors(data, n_factors=20)
        >>> print(report)
    """
    generator = AutoFactorGenerator(min_ic=min_ic)
    generator.load_data(df)
    
    if method == "templates":
        candidates = generator.generate_from_templates()
    else:
        candidates = generator.generate_genetic(n_generations=10)
    
    top_factors = generator.select_top(candidates, n=n_factors)
    report = generator.generate_report(top_factors)
    
    return top_factors, report


def generate_mock_data(n: int = 500) -> pd.DataFrame:
    """生成模拟数据"""
    dates = pd.date_range(end=datetime.now(), periods=n, freq="1h")
    
    np.random.seed(42)
    price = 50000.0
    prices = [price]
    for i in range(1, n):
        price = price * (1 + np.random.normal(0.001, 0.02))
        prices.append(price)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p * (1 + np.random.uniform(0, 0.01)) for p in prices],
        "low": [p * (1 - np.random.uniform(0, 0.01)) for p in prices],
        "close": prices,
        "volume": np.random.lognormal(10, 0.5, n)
    })
    return df


if __name__ == "__main__":
    # 测试
    print("="*80)
    print("  Auto Factor Generator 测试")
    print("="*80)
    
    # 生成数据
    data = generate_mock_data(500)
    print(f"\n数据: {len(data)} 条")
    
    # 自动生成因子
    factors, report = auto_generate_factors(data, method="templates", n_factors=15)
    
    print("\n" + "="*80)
    print("  Top 15 因子")
    print("="*80)
    print(report.to_string(index=False))
    
    print("\n✅ 因子自动生成完成！")

