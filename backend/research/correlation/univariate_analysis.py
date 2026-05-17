"""
单变量分析模块 - 相关性、互信息、Granger因果检验
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import pandas as pd
import numpy as np
from scipy import stats
from scipy.spatial.distance import jensenshannon

from infrastructure.logging import get_logger

logger = get_logger("research.correlation.univariate")


@dataclass
class CorrelationResult:
    """相关性分析结果"""
    feature: str
    target: str
    pearson_r: float
    pearson_p: float
    spearman_r: float
    spearman_p: float
    kendall_tau: float
    kendall_p: float
    is_significant: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "target": self.target,
            "pearson": {"r": self.pearson_r, "p_value": self.pearson_p},
            "spearman": {"r": self.spearman_r, "p_value": self.spearman_p},
            "kendall": {"tau": self.kendall_tau, "p_value": self.kendall_p},
            "is_significant": self.is_significant,
            "strongest_correlation": max(abs(self.pearson_r), abs(self.spearman_r)),
        }


@dataclass
class MutualInfoResult:
    """互信息分析结果"""
    feature: str
    target: str
    mutual_info: float
    normalized_mi: float  # 归一化到 [0, 1]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "target": self.target,
            "mutual_info": self.mutual_info,
            "normalized_mi": self.normalized_mi,
        }


@dataclass
class GrangerResult:
    """Granger因果检验结果"""
    feature: str
    target: str
    lag: int
    f_statistic: float
    p_value: float
    is_causal: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "target": self.target,
            "lag": self.lag,
            "f_statistic": self.f_statistic,
            "p_value": self.p_value,
            "is_causal": self.is_causal,
        }


@dataclass
class LagCorrelationResult:
    """滞后相关性结果"""
    feature: str
    target: str
    lag_correlations: Dict[int, float]  # lag -> correlation
    best_lag: int
    best_correlation: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "target": self.target,
            "lag_correlations": self.lag_correlations,
            "best_lag": self.best_lag,
            "best_correlation": self.best_correlation,
        }


class UnivariateAnalyzer:
    """
    单变量分析器
    
    功能：
    1. Pearson/Spearman/Kendall 相关性
    2. 互信息（非线性依赖）
    3. Granger 因果检验
    4. 滞后相关性分析
    """
    
    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level
    
    def correlation_analysis(
        self,
        df: pd.DataFrame,
        feature_col: str,
        target_col: str
    ) -> CorrelationResult:
        """
        多维度相关性分析
        
        Returns:
            CorrelationResult: 包含 Pearson、Spearman、Kendall 相关性
        """
        x = df[feature_col].dropna()
        y = df[target_col].dropna()
        
        # 对齐数据
        aligned = pd.concat([x, y], axis=1).dropna()
        if len(aligned) < 10:
            logger.warning(f"Insufficient data for correlation: {len(aligned)} samples")
            return CorrelationResult(
                feature=feature_col,
                target=target_col,
                pearson_r=0, pearson_p=1,
                spearman_r=0, spearman_p=1,
                kendall_tau=0, kendall_p=1,
                is_significant=False
            )
        
        x_aligned = aligned[feature_col]
        y_aligned = aligned[target_col]
        
        # Pearson 相关性（线性）
        pearson_r, pearson_p = stats.pearsonr(x_aligned, y_aligned)
        
        # Spearman 相关性（单调）
        spearman_r, spearman_p = stats.spearmanr(x_aligned, y_aligned)
        
        # Kendall Tau（序数相关性）
        kendall_tau, kendall_p = stats.kendalltau(x_aligned, y_aligned)
        
        # 判断显著性
        is_significant = min(pearson_p, spearman_p, kendall_p) < self.significance_level
        
        return CorrelationResult(
            feature=feature_col,
            target=target_col,
            pearson_r=pearson_r,
            pearson_p=pearson_p,
            spearman_r=spearman_r,
            spearman_p=spearman_p,
            kendall_tau=kendall_tau,
            kendall_p=kendall_p,
            is_significant=is_significant
        )
    
    def mutual_information(
        self,
        df: pd.DataFrame,
        feature_col: str,
        target_col: str,
        n_bins: int = 10
    ) -> MutualInfoResult:
        """
        计算互信息（非线性依赖度量）
        
        使用分箱离散化后计算互信息
        """
        x = df[feature_col].dropna()
        y = df[target_col].dropna()
        
        aligned = pd.concat([x, y], axis=1).dropna()
        if len(aligned) < 10:
            return MutualInfoResult(
                feature=feature_col,
                target=target_col,
                mutual_info=0,
                normalized_mi=0
            )
        
        x_aligned = aligned[feature_col]
        y_aligned = aligned[target_col]
        
        # 分箱离散化
        x_discrete = pd.cut(x_aligned, bins=n_bins, labels=False)
        y_discrete = pd.cut(y_aligned, bins=n_bins, labels=False)
        
        # 计算互信息
        mi = self._calculate_mi(x_discrete, y_discrete)
        
        # 归一化互信息 (0-1)
        h_x = self._calculate_entropy(x_discrete)
        h_y = self._calculate_entropy(y_discrete)
        normalized_mi = mi / np.sqrt(h_x * h_y) if h_x * h_y > 0 else 0
        
        return MutualInfoResult(
            feature=feature_col,
            target=target_col,
            mutual_info=mi,
            normalized_mi=normalized_mi
        )
    
    def _calculate_mi(self, x: pd.Series, y: pd.Series) -> float:
        """计算互信息"""
        joint_prob = pd.crosstab(x, y, normalize=True)
        x_marginal = joint_prob.sum(axis=1)
        y_marginal = joint_prob.sum(axis=0)
        
        mi = 0.0
        for i in joint_prob.index:
            for j in joint_prob.columns:
                p_xy = joint_prob.loc[i, j]
                p_x = x_marginal[i]
                p_y = y_marginal[j]
                if p_xy > 0 and p_x > 0 and p_y > 0:
                    mi += p_xy * np.log2(p_xy / (p_x * p_y))
        
        return mi
    
    def _calculate_entropy(self, x: pd.Series) -> float:
        """计算熵"""
        probs = x.value_counts(normalize=True)
        return -np.sum(probs * np.log2(probs + 1e-10))
    
    def granger_causality(
        self,
        df: pd.DataFrame,
        feature_col: str,
        target_col: str,
        max_lag: int = 5
    ) -> Dict[int, GrangerResult]:
        """
        Granger 因果检验
        
        检验 feature 是否能预测 target（即 feature 的过去值是否有助于预测 target）
        
        Returns:
            Dict[int, GrangerResult]: 各滞后阶数的检验结果
        """
        try:
            from statsmodels.tsa.stattools import grangercausalitytests
        except ImportError:
            logger.warning("statsmodels not installed, skipping Granger causality test")
            return {}
        
        results = {}
        
        # 准备数据
        data = df[[target_col, feature_col]].dropna()
        
        if len(data) < max_lag + 10:
            logger.warning(f"Insufficient data for Granger test: {len(data)} samples")
            return {}
        
        try:
            # 执行 Granger 检验
            gc_results = grangercausalitytests(data, maxlag=max_lag, verbose=False)
            
            for lag in range(1, max_lag + 1):
                if lag in gc_results:
                    test_result = gc_results[lag][0]['ssr_ftest']
                    f_stat = test_result[0]
                    p_value = test_result[1]
                    
                    results[lag] = GrangerResult(
                        feature=feature_col,
                        target=target_col,
                        lag=lag,
                        f_statistic=f_stat,
                        p_value=p_value,
                        is_causal=p_value < self.significance_level
                    )
        
        except Exception as e:
            logger.warning(f"Granger causality test failed: {e}")
        
        return results
    
    def lag_correlation(
        self,
        df: pd.DataFrame,
        feature_col: str,
        target_col: str,
        max_lag: int = 20,
        method: str = "pearson"
    ) -> LagCorrelationResult:
        """
        滞后相关性分析
        
        计算 feature 的滞后值与 target 当前值的相关性
        用于发现领先-滞后关系
        """
        lag_correlations = {}
        
        for lag in range(0, max_lag + 1):
            # feature 滞后 lag 期
            feature_lagged = df[feature_col].shift(lag)
            target_current = df[target_col]
            
            # 对齐并计算相关性
            aligned = pd.concat([feature_lagged, target_current], axis=1).dropna()
            
            if len(aligned) < 10:
                lag_correlations[lag] = 0
                continue
            
            if method == "pearson":
                corr, _ = stats.pearsonr(aligned.iloc[:, 0], aligned.iloc[:, 1])
            elif method == "spearman":
                corr, _ = stats.spearmanr(aligned.iloc[:, 0], aligned.iloc[:, 1])
            else:
                corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
            
            lag_correlations[lag] = corr
        
        # 找到最佳滞后
        best_lag = max(lag_correlations.keys(), key=lambda k: abs(lag_correlations[k]))
        best_correlation = lag_correlations[best_lag]
        
        return LagCorrelationResult(
            feature=feature_col,
            target=target_col,
            lag_correlations=lag_correlations,
            best_lag=best_lag,
            best_correlation=best_correlation
        )
    
    def cross_correlation(
        self,
        df: pd.DataFrame,
        feature_col: str,
        target_col: str,
        max_lag: int = 20
    ) -> Dict[str, Any]:
        """
        互相关分析（Cross-correlation）
        
        同时考虑正负滞后，找出最强相关性
        """
        x = df[feature_col].dropna()
        y = df[target_col].dropna()
        
        # 对齐
        aligned = pd.concat([x, y], axis=1).dropna()
        x_aligned = aligned[feature_col]
        y_aligned = aligned[target_col]
        
        # 标准化
        x_norm = (x_aligned - x_aligned.mean()) / x_aligned.std()
        y_norm = (y_aligned - y_aligned.mean()) / y_aligned.std()
        
        # 计算互相关
        correlations = {}
        for lag in range(-max_lag, max_lag + 1):
            if lag == 0:
                corr = np.corrcoef(x_norm, y_norm)[0, 1]
            elif lag > 0:
                # feature 领先 target
                corr = np.corrcoef(x_norm[:-lag], y_norm[lag:])[0, 1]
            else:
                # target 领先 feature
                corr = np.corrcoef(x_norm[-lag:], y_norm[:lag])[0, 1]
            
            correlations[lag] = corr if not np.isnan(corr) else 0
        
        # 找到最佳滞后
        best_lag = max(correlations.keys(), key=lambda k: abs(correlations[k]))
        
        return {
            "feature": feature_col,
            "target": target_col,
            "correlations": correlations,
            "best_lag": best_lag,
            "best_correlation": correlations[best_lag],
            "lead_lag_relation": "feature_leads" if best_lag > 0 else "target_leads" if best_lag < 0 else "synchronous"
        }
