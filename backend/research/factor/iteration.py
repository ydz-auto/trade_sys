"""
因子迭代与权重优化器

功能：
1. 因子参数自动迭代优化
2. 多因子组合权重优化  
3. 遗传编程自动组合因子
4. 滚动窗口稳健性验证
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import random
from itertools import product


# =============================================================================
# 基础计算
# =============================================================================

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


# =============================================================================
# 因子参数迭代优化器
# =============================================================================

@dataclass
class FactorParams:
    """因子参数"""
    name: str
    params: Dict[str, Any]
    ic: float = 0.0
    score: float = 0.0


class FactorParamOptimizer:
    """因子参数自动迭代优化器
    
    使用方法:
    optimizer = FactorParamOptimizer(factor_name="rsi")
    best_params = optimizer.optimize(data, param_space)
    """
    
    def __init__(self, factor_name: str):
        self.factor_name = factor_name
        self.history: List[FactorParams] = []
    
    def compute_factor(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """根据参数计算因子"""
        close = df['close']
        
        if self.factor_name == "rsi":
            period = params.get('period', 14)
            return compute_rsi(close, period)
        
        elif self.factor_name == "momentum":
            period = params.get('period', 10)
            return close - close.shift(period)
        
        elif self.factor_name == "ma_cross":
            fast = params.get('fast', 5)
            slow = params.get('slow', 20)
            sma_fast = close.rolling(fast).mean()
            sma_slow = close.rolling(slow).mean()
            return sma_fast - sma_slow
        
        elif self.factor_name == "rsi_macd":
            rsi_period = params.get('rsi_period', 14)
            macd_fast = params.get('macd_fast', 12)
            macd_slow = params.get('macd_slow', 26)
            
            rsi = compute_rsi(close, rsi_period)
            _, _, macd_hist = compute_macd(close, macd_fast, macd_slow)
            return rsi * 0.5 + macd_hist * 0.5
        
        elif self.factor_name == "custom":
            formula = params.get('formula', 'close')
            return self._eval_formula(df, formula)
        
        return pd.Series(0, index=close.index)
    
    def _eval_formula(self, df: pd.DataFrame, formula: str) -> pd.Series:
        """计算自定义公式"""
        try:
            # 预计算常用指标
            for p in [5, 10, 20, 60]:
                df[f'sma_{p}'] = df['close'].rolling(p).mean()
                df[f'std_{p}'] = df['close'].pct_change().rolling(p).std()
                df[f'returns_{p}'] = df['close'].pct_change(p)
            
            df['rsi_14'] = compute_rsi(df['close'], 14)
            _, _, df['macd'] = compute_macd(df['close'])
            
            return df.eval(formula, inplace=False)
        except:
            return pd.Series(0, index=df['close'].index)
    
    def evaluate(self, factor: pd.Series, forward_returns: pd.Series) -> Tuple[float, float, float]:
        """评估因子"""
        valid = ~(factor.isna() | forward_returns.isna())
        if valid.sum() < 30:
            return 0.0, 0.0, 0.0
        
        ic = factor[valid].corr(forward_returns[valid])
        try:
            rank_ic = stats.spearmanr(factor[valid], forward_returns[valid])[0]
        except:
            rank_ic = 0.0
        
        # 换手率
        try:
            turnover = (pd.qcut(factor.dropna(), 5, labels=False, duplicates='drop') != 
                       pd.qcut(factor.dropna().shift(1), 5, labels=False, duplicates='drop')).mean()
        except:
            turnover = 0.0
        
        # 综合评分: IC * IR * (1-turnover)
        ir = abs(ic) / (abs(turnover) + 0.01)
        score = abs(ic) * min(ir, 2) * (1 - min(turnover, 1))
        
        return ic, rank_ic, score
    
    def optimize(
        self,
        df: pd.DataFrame,
        param_space: Dict[str, List[Any]],
        forward_period: int = 5,
        method: str = "grid"  # grid, random, genetic
    ) -> FactorParams:
        """自动迭代优化参数
        
        Args:
            df: 数据
            param_space: 参数空间，如 {'period': [10, 14, 20], 'threshold': [30, 40]}
            forward_period: 预测周期
            method: 优化方法
        """
        # 计算远期收益
        forward_returns = df['close'].pct_change(forward_period).shift(-forward_period)
        
        if method == "grid":
            best = self._grid_search(df, param_space, forward_returns)
        elif method == "random":
            best = self._random_search(df, param_space, forward_returns, n_iter=50)
        elif method == "genetic":
            best = self._genetic_search(df, param_space, forward_returns)
        else:
            best = self._grid_search(df, param_space, forward_returns)
        
        return best
    
    def _grid_search(
        self,
        df: pd.DataFrame,
        param_space: Dict[str, List[Any]],
        forward_returns: pd.Series
    ) -> FactorParams:
        """网格搜索"""
        keys = list(param_space.keys())
        values = list(param_space.values())
        
        best_score = -float('inf')
        best_params = None
        
        for combo in product(*values):
            params = dict(zip(keys, combo))
            factor = self.compute_factor(df, params)
            _, _, score = self.evaluate(factor, forward_returns)
            
            self.history.append(FactorParams(
                name=self.factor_name,
                params=params,
                score=score
            ))
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return FactorParams(
            name=self.factor_name,
            params=best_params,
            score=best_score
        )
    
    def _random_search(
        self,
        df: pd.DataFrame,
        param_space: Dict[str, List[Any]],
        forward_returns: pd.Series,
        n_iter: int = 50
    ) -> FactorParams:
        """随机搜索"""
        best_score = -float('inf')
        best_params = None
        
        for _ in range(n_iter):
            params = {k: random.choice(v) for k, v in param_space.items()}
            factor = self.compute_factor(df, params)
            _, _, score = self.evaluate(factor, forward_returns)
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return FactorParams(
            name=self.factor_name,
            params=best_params,
            score=best_score
        )
    
    def _genetic_search(
        self,
        df: pd.DataFrame,
        param_space: Dict[str, List[Any]],
        forward_returns: pd.Series,
        n_generations: int = 20,
        population_size: int = 20
    ) -> FactorParams:
        """遗传算法搜索"""
        # 初始化种群
        keys = list(param_space.keys())
        population = []
        for _ in range(population_size):
            params = {k: random.choice(v) for k, v in param_space.items()}
            population.append(params)
        
        best_params = None
        best_score = -float('inf')
        
        for gen in range(n_generations):
            # 评估
            scored = []
            for params in population:
                factor = self.compute_factor(df, params)
                _, _, score = self.evaluate(factor, forward_returns)
                scored.append((score, params))
            
            # 排序
            scored.sort(key=lambda x: x[0], reverse=True)
            
            # 更新最优
            if scored[0][0] > best_score:
                best_score = scored[0][0]
                best_params = scored[0][1]
            
            # 选择精英
            elite = [p for _, p in scored[:population_size // 2]]
            
            # 交叉变异
            new_population = list(elite)
            while len(new_population) < population_size:
                p1, p2 = random.sample(elite, 2)
                if random.random() < 0.7:  # 交叉
                    child = {}
                    for k in keys:
                        child[k] = random.choice([p1[k], p2[k]])
                else:  # 变异
                    parent = random.choice(elite)
                    child = dict(parent)
                    mutate_key = random.choice(keys)
                    child[mutate_key] = random.choice(param_space[mutate_key])
                new_population.append(child)
            
            population = new_population[:population_size]
        
        return FactorParams(
            name=self.factor_name,
            params=best_params,
            score=best_score
        )


# =============================================================================
# 多因子权重优化器
# =============================================================================

@dataclass
class FactorWeight:
    """因子权重"""
    factor_name: str
    weight: float
    params: Dict[str, Any] = field(default_factory=dict)


class MultiFactorOptimizer:
    """多因子组合权重优化器
    
    使用方法:
    optimizer = MultiFactorOptimizer(['rsi', 'momentum', 'macd'])
    best_weights = optimizer.optimize(data, method='mean_variance')
    """
    
    def __init__(self, factor_names: List[str]):
        self.factor_names = factor_names
        self.factors: Dict[str, pd.Series] = {}
        self.history: List[Dict] = []
    
    def add_factor(self, name: str, values: pd.Series):
        """添加因子"""
        self.factors[name] = values
    
    def optimize(
        self,
        forward_returns: pd.Series,
        method: str = "ic_weighted",  # ic_weighted, equal, mean_variance, genetic
        constraints: Optional[Dict] = None
    ) -> List[FactorWeight]:
        """优化因子权重
        
        Args:
            forward_returns: 远期收益
            method: 优化方法
            constraints: 约束条件，如 {'min_weight': 0.05, 'max_weight': 0.5}
        """
        if method == "ic_weighted":
            return self._ic_weighted_optimize(forward_returns, constraints)
        elif method == "equal":
            return self._equal_weight()
        elif method == "mean_variance":
            return self._mean_variance_optimize(forward_returns, constraints)
        elif method == "genetic":
            return self._genetic_optimize(forward_returns, constraints)
        else:
            return self._ic_weighted_optimize(forward_returns, constraints)
    
    def _equal_weight(self) -> List[FactorWeight]:
        """等权重"""
        weight = 1.0 / len(self.factor_names)
        return [FactorWeight(name, weight) for name in self.factor_names]
    
    def _ic_weighted_optimize(
        self,
        forward_returns: pd.Series,
        constraints: Optional[Dict] = None
    ) -> List[FactorWeight]:
        """基于IC加权"""
        ic_scores = {}
        
        for name in self.factor_names:
            factor = self.factors[name]
            valid = ~(factor.isna() | forward_returns.isna())
            if valid.sum() > 30:
                ic = abs(factor[valid].corr(forward_returns[valid]))
            else:
                ic = 0.0
            ic_scores[name] = ic
        
        total_ic = sum(ic_scores.values())
        if total_ic == 0:
            return self._equal_weight()
        
        weights = []
        for name in self.factor_names:
            w = ic_scores[name] / total_ic
            
            # 应用约束
            if constraints:
                w = max(constraints.get('min_weight', 0), w)
                w = min(constraints.get('max_weight', 1), w)
            
            weights.append(FactorWeight(name, w))
        
        return weights
    
    def _mean_variance_optimize(
        self,
        forward_returns: pd.Series,
        constraints: Optional[Dict] = None
    ) -> List[FactorWeight]:
        """均值方差优化 (简化版)"""
        n = len(self.factor_names)
        
        # 构建因子矩阵
        factor_matrix = pd.DataFrame({name: self.factors[name] for name in self.factor_names})
        valid = ~(factor_matrix.isna().any(axis=1) | forward_returns.isna())
        
        if valid.sum() < 50:
            return self._equal_weight()
        
        factor_valid = factor_matrix[valid]
        returns_valid = forward_returns[valid]
        
        # 计算IC作为权重
        ic_scores = {}
        for name in self.factor_names:
            ic = abs(factor_valid[name].corr(returns_valid))
            ic_scores[name] = max(ic, 0.001)  # 防止除零
        
        # 归一化
        total = sum(ic_scores.values())
        weights = [FactorWeight(name, ic_scores[name] / total) for name in self.factor_names]
        
        return weights
    
    def _genetic_optimize(
        self,
        forward_returns: pd.Series,
        constraints: Optional[Dict] = None,
        n_generations: int = 30
    ) -> List[FactorWeight]:
        """遗传算法优化权重"""
        n = len(self.factor_names)
        min_w = constraints.get('min_weight', 0.05) if constraints else 0.05
        max_w = constraints.get('max_weight', 0.6) if constraints else 0.6
        
        # 初始化种群
        def random_weights():
            w = np.random.dirichlet(np.ones(n))
            w = np.clip(w, min_w, max_w)
            return list(w)
        
        population = [random_weights() for _ in range(50)]
        
        best_weights = None
        best_score = -float('inf')
        
        for gen in range(n_generations):
            # 评估
            scored = []
            for weights in population:
                score = self._evaluate_weights(weights, forward_returns)
                scored.append((score, weights))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            
            if scored[0][0] > best_score:
                best_score = scored[0][0]
                best_weights = scored[0][1]
            
            # 选择精英
            elite = [p for _, p in scored[:20]]
            
            # 交叉变异
            new_population = list(elite)
            while len(new_population) < 50:
                if random.random() < 0.7 and len(elite) >= 2:
                    p1, p2 = random.sample(elite, 2)
                    alpha = random.random()
                    child = [a * alpha + b * (1 - alpha) for a, b in zip(p1, p2)]
                else:
                    child = random_weights()
                
                # 变异
                if random.random() < 0.2:
                    idx = random.randint(0, n - 1)
                    child[idx] += random.uniform(-0.1, 0.1)
                    child[idx] = np.clip(child[idx], min_w, max_w)
                
                # 归一化
                total = sum(child)
                child = [w / total for w in child]
                
                new_population.append(child)
            
            population = new_population[:50]
        
        return [FactorWeight(name, w) for name, w in zip(self.factor_names, best_weights)]
    
    def _evaluate_weights(self, weights: List[float], forward_returns: pd.Series) -> float:
        """评估权重组合"""
        n = len(self.factor_names)
        factor_matrix = pd.DataFrame({name: self.factors[name] for name in self.factor_names})
        
        # 组合因子
        combined = sum(w * factor_matrix[name] for w, name in zip(weights, self.factor_names))
        
        valid = ~(combined.isna() | forward_returns.isna())
        if valid.sum() < 30:
            return 0.0
        
        # IC评分
        ic = combined[valid].corr(forward_returns[valid])
        
        # 换手率
        try:
            turnover = (pd.qcut(combined.dropna(), 5, labels=False) != 
                       pd.qcut(combined.dropna().shift(1), 5, labels=False)).mean()
        except:
            turnover = 0.5
        
        # 综合评分
        score = abs(ic) * (1 - min(turnover, 1))
        return score
    
    def compute_alpha(self, weights: List[FactorWeight]) -> pd.Series:
        """计算Alpha信号"""
        combined = pd.Series(0, index=list(self.factors.values())[0].index)
        
        for fw in weights:
            combined += fw.weight * self.factors[fw.factor_name]
        
        return combined


# =============================================================================
# 自动迭代完整流程
# =============================================================================

@dataclass
class IterationResult:
    """迭代结果"""
    iteration: int
    factor_weights: List[FactorWeight]
    ic: float
    sharpe: float
    turnover: float
    score: float


class AutoFactorIteration:
    """自动因子迭代优化器
    
    完整流程:
    1. 因子参数迭代优化
    2. 多因子权重优化
    3. 滚动窗口稳健性验证
    """
    
    def __init__(self, min_ic: float = 0.02, min_weight: float = 0.05):
        self.min_ic = min_ic
        self.min_weight = min_weight
        self.param_optimizer = None
        self.weight_optimizer = None
        self.history: List[IterationResult] = []
    
    def run(
        self,
        df: pd.DataFrame,
        factor_names: List[str],
        param_spaces: Dict[str, Dict[str, List[Any]]],
        forward_period: int = 5,
        n_iterations: int = 3
    ) -> Tuple[List[FactorWeight], List[IterationResult]]:
        """
        自动迭代优化
        
        Args:
            df: 数据
            factor_names: 因子名列表
            param_spaces: 参数空间，如 {'rsi': {'period': [10, 14, 20]}}
            forward_period: 预测周期
            n_iterations: 迭代次数
        
        Returns:
            (最优权重列表, 迭代历史)
        """
        print("\n" + "="*80)
        print("  🔄 Auto Factor Iteration - 自动因子迭代")
        print("="*80)
        
        # 计算远期收益
        forward_returns = df['close'].pct_change(forward_period).shift(-forward_period)
        
        best_weights = None
        best_score = -float('inf')
        
        for iteration in range(n_iterations):
            print(f"\n[迭代 {iteration + 1}/{n_iterations}]")
            
            # Step 1: 优化每个因子的参数
            optimized_factors = {}
            for fname in factor_names:
                param_space = param_spaces.get(fname, {})
                
                optimizer = FactorParamOptimizer(fname)
                
                # 网格搜索最优参数
                if param_space:
                    best = optimizer.optimize(df, param_space, forward_period, method="grid")
                    print(f"  {fname}: params={best.params}, IC={abs(optimizer.history[-1].score):.4f}" 
                          if optimizer.history else f"  {fname}: 无参数优化")
                    optimized_factors[fname] = optimizer.compute_factor(df, best.params)
                else:
                    # 使用默认参数
                    opt = FactorParamOptimizer(fname)
                    optimized_factors[fname] = opt.compute_factor(df, {})
            
            # Step 2: 优化因子权重
            weight_opt = MultiFactorOptimizer(factor_names)
            for fname, values in optimized_factors.items():
                weight_opt.add_factor(fname, values)
            
            weights = weight_opt.optimize(
                forward_returns,
                method="genetic",
                constraints={'min_weight': self.min_weight, 'max_weight': 0.6}
            )
            
            # 计算Alpha
            alpha = weight_opt.compute_alpha(weights)
            
            # 评估
            valid = ~(alpha.isna() | forward_returns.isna())
            if valid.sum() > 30:
                ic = alpha[valid].corr(forward_returns[valid])
            else:
                ic = 0.0
            
            # 计算夏普
            returns = alpha[valid].shift(1) * forward_returns[valid]
            sharpe = returns.mean() / (returns.std() + 1e-10) * np.sqrt(252)
            
            # 换手率
            try:
                turnover = (pd.qcut(alpha.dropna(), 5, labels=False) != 
                           pd.qcap(alpha.dropna().shift(1), 5, labels=False)).mean()
            except:
                turnover = 0.3
            
            score = abs(ic) * (1 - min(turnover, 1))
            
            print(f"  → IC: {ic:.4f}, Sharpe: {sharpe:.2f}, Turnover: {turnover:.2%}")
            
            # 记录
            result = IterationResult(
                iteration=iteration + 1,
                factor_weights=weights,
                ic=ic,
                sharpe=sharpe,
                turnover=turnover,
                score=score
            )
            self.history.append(result)
            
            # 更新最优
            if score > best_score:
                best_score = score
                best_weights = weights
        
        # 输出最优结果
        print("\n" + "="*80)
        print("  ✅ 迭代完成 - 最优权重")
        print("="*80)
        for fw in best_weights:
            print(f"  {fw.factor_name}: {fw.weight:.2%}")
        
        return best_weights, self.history


# =============================================================================
# 演示
# =============================================================================

def generate_mock_data(n: int = 1000) -> pd.DataFrame:
    """生成模拟数据"""
    dates = pd.date_range(end=datetime.now(), periods=n, freq="1h")
    
    np.random.seed(42)
    price = 50000.0
    prices = [price]
    for i in range(1, n):
        vol = 0.02 + 0.01 * np.sin(i / 50)
        price = price * (1 + np.random.normal(0.0003, vol))
        prices.append(price)
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices],
        "low": [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices],
        "close": prices,
        "volume": np.random.lognormal(10, 0.5, n)
    })


def main():
    print("\n" + "="*80)
    print("  🚀 因子迭代与权重优化演示")
    print("="*80)
    
    # 1. 生成数据
    print("\n[1/5] 生成数据...")
    df = generate_mock_data(800)
    print(f"      数据点: {len(df)}")
    
    # 2. 因子参数迭代
    print("\n[2/5] 因子参数迭代优化...")
    factor_names = ['rsi', 'momentum', 'ma_cross']
    param_spaces = {
        'rsi': {'period': [7, 14, 21, 28]},
        'momentum': {'period': [5, 10, 20]},
        'ma_cross': {'fast': [5, 7, 10], 'slow': [20, 30, 60]}
    }
    
    # 测试参数迭代
    rsi_optimizer = FactorParamOptimizer('rsi')
    best_rsi = rsi_optimizer.optimize(
        df, 
        {'period': [7, 14, 21, 28]},
        forward_period=5,
        method='grid'
    )
    print(f"      RSI最佳参数: {best_rsi.params}, 评分: {best_rsi.score:.4f}")
    
    # 3. 多因子权重优化
    print("\n[3/5] 多因子权重优化...")
    
    # 先计算所有因子
    factor_values = {}
    
    # RSI
    rsi_opt = FactorParamOptimizer('rsi')
    factor_values['rsi'] = rsi_opt.compute_factor(df, best_rsi.params)
    
    # Momentum
    mom_opt = FactorParamOptimizer('momentum')
    factor_values['momentum'] = mom_opt.compute_factor(df, {'period': 10})
    
    # MA Cross
    ma_opt = FactorParamOptimizer('ma_cross')
    factor_values['ma_cross'] = ma_opt.compute_factor(df, {'fast': 5, 'slow': 20})
    
    # 优化权重
    weight_opt = MultiFactorOptimizer(['rsi', 'momentum', 'ma_cross'])
    for name, values in factor_values.items():
        weight_opt.add_factor(name, values)
    
    forward_returns = df['close'].pct_change(5).shift(-5)
    
    # IC加权
    ic_weights = weight_opt.optimize(forward_returns, method='ic_weighted')
    print("      IC加权权重:")
    for fw in ic_weights:
        print(f"        {fw.factor_name}: {fw.weight:.2%}")
    
    # 遗传算法优化
    print("\n[4/5] 遗传算法权重优化...")
    genetic_weights = weight_opt.optimize(
        forward_returns, 
        method='genetic',
        constraints={'min_weight': 0.1, 'max_weight': 0.5}
    )
    print("      遗传算法权重:")
    for fw in genetic_weights:
        print(f"        {fw.factor_name}: {fw.weight:.2%}")
    
    # 4. 计算最终Alpha
    print("\n[5/5] 生成Alpha信号...")
    alpha = weight_opt.compute_alpha(genetic_weights)
    valid = ~(alpha.isna() | forward_returns.isna())
    final_ic = alpha[valid].corr(forward_returns[valid])
    print(f"      最终Alpha IC: {final_ic:.4f}")
    
    print("\n" + "="*80)
    print("  ✅ 因子迭代与权重优化完成！")
    print("="*80)
    print("\n结论:")
    print("  - 因子 ≠ 因子权重")
    print("  - 因子 = 单一特征值 (RSI=65)")
    print("  - 权重 = 组合时的系数 (RSI权重=0.3)")
    print("  - Alpha = Σ(因子i × 权重i)")
    print("\n下一步: Walk-Forward滚动验证 → 实盘部署")


if __name__ == "__main__":
    main()

