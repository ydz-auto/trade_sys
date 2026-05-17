"""
综合评分模块 - 整合统计、ML、LLM结果，输出信号方向性评估
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from infrastructure.logging import get_logger
from .types import SignalDirection

logger = get_logger("research.correlation.scoring")


@dataclass
class SignalAssessment:
    """信号评估结果"""
    feature: str
    direction: SignalDirection
    confidence: float  # 0-1
    strength: float  # 相关性强度 0-1
    
    # 各维度得分
    statistical_score: float = 0.0  # 统计相关性得分
    ml_score: float = 0.0  # ML模型得分
    llm_score: float = 0.0  # LLM增强得分
    
    # 详细证据
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 4),
            "strength": round(self.strength, 4),
            "scores": {
                "statistical": round(self.statistical_score, 4),
                "ml": round(self.ml_score, 4),
                "llm": round(self.llm_score, 4),
            },
            "evidence": self.evidence,
        }


class CorrelationScorer:
    """
    相关性综合评分器
    
    整合多种分析方法的结果，给出最终的信号方向性判断
    """
    
    def __init__(
        self,
        statistical_weight: float = 0.4,
        ml_weight: float = 0.4,
        llm_weight: float = 0.2,
        confidence_threshold: float = 0.6,
        min_correlation: float = 0.1
    ):
        self.statistical_weight = statistical_weight
        self.ml_weight = ml_weight
        self.llm_weight = llm_weight
        self.confidence_threshold = confidence_threshold
        self.min_correlation = min_correlation
    
    def calculate_score(
        self,
        feature: str,
        univariate_result: Dict[str, Any],
        multivariate_results: Dict[str, Any],
        llm_trend: Optional[List] = None
    ) -> SignalAssessment:
        """
        计算信号综合评分
        
        Args:
            feature: 特征名称
            univariate_result: 单变量分析结果
            multivariate_results: 多变量分析结果
            llm_trend: LLM情感趋势
        
        Returns:
            SignalAssessment: 信号评估结果
        """
        # 1. 统计相关性评分
        stat_score, stat_direction = self._score_statistical(univariate_result)
        
        # 2. ML模型评分
        ml_score, ml_direction = self._score_ml(multivariate_results, feature)
        
        # 3. LLM增强评分
        llm_score, llm_direction = self._score_llm(llm_trend, feature)
        
        # 4. 综合评分
        total_score = (
            stat_score * self.statistical_weight +
            ml_score * self.ml_weight +
            llm_score * self.llm_weight
        )
        
        # 5. 确定方向
        final_direction = self._determine_direction(
            stat_direction, ml_direction, llm_direction,
            stat_score, ml_score, llm_score
        )
        
        # 6. 计算置信度和强度
        confidence = min(total_score, 1.0)
        strength = self._calculate_strength(univariate_result, multivariate_results, feature)
        
        # 7. 收集证据
        evidence = self._collect_evidence(
            univariate_result, multivariate_results, feature
        )
        
        return SignalAssessment(
            feature=feature,
            direction=final_direction,
            confidence=confidence,
            strength=strength,
            statistical_score=stat_score,
            ml_score=ml_score,
            llm_score=llm_score,
            evidence=evidence
        )
    
    def _score_statistical(self, univariate_result: Dict[str, Any]) -> tuple[float, SignalDirection]:
        """统计相关性评分"""
        score = 0.0
        direction = SignalDirection.NEUTRAL
        
        # Pearson 相关性
        corr_data = univariate_result.get("correlation", {})
        pearson_r = abs(corr_data.get("pearson", {}).get("r", 0))
        pearson_p = corr_data.get("pearson", {}).get("p_value", 1)
        
        if pearson_p < 0.05 and pearson_r > self.min_correlation:
            score += pearson_r * 0.3  # Pearson 权重 30%
            direction = self._correlation_to_direction(
                corr_data.get("pearson", {}).get("r", 0)
            )
        
        # Spearman 相关性
        spearman_r = abs(corr_data.get("spearman", {}).get("r", 0))
        spearman_p = corr_data.get("spearman", {}).get("p_value", 1)
        
        if spearman_p < 0.05 and spearman_r > self.min_correlation:
            score += spearman_r * 0.3  # Spearman 权重 30%
            spearman_dir = self._correlation_to_direction(
                corr_data.get("spearman", {}).get("r", 0)
            )
            if direction == SignalDirection.NEUTRAL:
                direction = spearman_dir
        
        # 互信息
        mi_data = univariate_result.get("mutual_info", {})
        normalized_mi = mi_data.get("normalized_mi", 0)
        score += normalized_mi * 0.2  # 互信息权重 20%
        
        # Granger 因果
        granger_data = univariate_result.get("granger", {})
        causal_lags = [g for g in granger_data.values() if g.get("is_causal", False)]
        if causal_lags:
            score += 0.2  # Granger 因果权重 20%
        
        return min(score, 1.0), direction
    
    def _score_llm(
        self,
        llm_trend: Optional[List],
        feature: str
    ) -> tuple[float, SignalDirection]:
        """LLM增强评分"""
        if not llm_trend:
            return 0.0, SignalDirection.NEUTRAL
        
        score = 0.0
        direction = SignalDirection.NEUTRAL
        
        # 如果是情感相关特征
        if "sentiment" in feature.lower():
            # 计算情感趋势的一致性
            sentiments = [t.aggregated_sentiment for t in llm_trend if hasattr(t, 'aggregated_sentiment')]
            if sentiments:
                avg_sentiment = np.mean(sentiments)
                sentiment_std = np.std(sentiments)
                
                # 情感越极端，得分越高
                score = min(abs(avg_sentiment - 0.5) * 2, 1.0)
                
                # 情感波动小说明趋势稳定
                if sentiment_std < 0.2:
                    score *= 1.2
                
                direction = SignalDirection.POSITIVE if avg_sentiment > 0.5 else SignalDirection.NEGATIVE
        
        return min(score, 1.0), direction
    
    def _determine_direction(
        self,
        stat_dir: SignalDirection,
        ml_dir: SignalDirection,
        llm_dir: SignalDirection,
        stat_score: float,
        ml_score: float,
        llm_score: float
    ) -> SignalDirection:
        """综合判断方向"""
        # 加权投票
        votes = {SignalDirection.POSITIVE: 0, SignalDirection.NEGATIVE: 0, SignalDirection.NEUTRAL: 0}
        
        votes[stat_dir] += stat_score * self.statistical_weight
        votes[ml_dir] += ml_score * self.ml_weight
        votes[llm_dir] += llm_score * self.llm_weight
        
        # 选择得分最高的方向
        max_direction = max(votes, key=votes.get)
        max_score = votes[max_direction]
        
        # 如果最高得分低于阈值，返回 NEUTRAL
        if max_score < self.confidence_threshold * 0.5:
            return SignalDirection.NEUTRAL
        
        return max_direction
    
    def _calculate_strength(
        self,
        univariate_result: Dict[str, Any],
        multivariate_results: Dict[str, Any],
        feature: str
    ) -> float:
        """计算相关性强度"""
        strengths = []
        
        # 统计相关性强度
        corr_data = univariate_result.get("correlation", {})
        strongest = corr_data.get("strongest_correlation", 0)
        strengths.append(strongest)
        
        # ML 重要性
        xgboost = multivariate_results.get("xgboost", {})
        shap_results = xgboost.get("shap_results", {})
        if feature in shap_results:
            shap_value = abs(shap_results[feature].get("mean_shap_value", 0))
            strengths.append(min(shap_value, 1.0))
        
        # 随机森林重要性
        rf = multivariate_results.get("random_forest", {})
        rf_importance = rf.get("feature_importance", {}).get(feature, 0)
        strengths.append(rf_importance * 3)  # 放大重要性
        
        return min(np.mean(strengths) if strengths else 0, 1.0)
    
    def _collect_evidence(
        self,
        univariate_result: Dict[str, Any],
        multivariate_results: Dict[str, Any],
        feature: str
    ) -> Dict[str, Any]:
        """收集证据"""
        evidence = {
            "correlation": univariate_result.get("correlation", {}),
            "mutual_info": univariate_result.get("mutual_info", {}),
            "lag_correlation": univariate_result.get("lag_correlation", {}),
        }
        
        # ML 证据
        lasso = multivariate_results.get("lasso", {})
        if feature in lasso.get("coefficients", {}):
            evidence["lasso_coefficient"] = lasso["coefficients"][feature]
        
        xgboost = multivariate_results.get("xgboost", {})
        shap_results = xgboost.get("shap_results", {})
        if feature in shap_results:
            evidence["shap"] = shap_results[feature].to_dict()
        
        return evidence
    
    def _correlation_to_direction(self, r: float) -> SignalDirection:
        """相关系数转方向"""
        if r > self.min_correlation:
            return SignalDirection.POSITIVE
        elif r < -self.min_correlation:
            return SignalDirection.NEGATIVE
        return SignalDirection.NEUTRAL
    
    def _coefficient_to_direction(self, coef: float) -> SignalDirection:
        """回归系数转方向"""
        if coef > 0.01:
            return SignalDirection.POSITIVE
        elif coef < -0.01:
            return SignalDirection.NEGATIVE
        return SignalDirection.NEUTRAL
    
    def _score_ml(
        self,
        multivariate_results: Dict[str, Any],
        feature: str
    ) -> tuple[float, SignalDirection]:
        """ML模型评分"""
        score = 0.0
        direction = SignalDirection.NEUTRAL
        
        # LASSO 系数
        lasso = multivariate_results.get("lasso", {})
        lasso_coef = lasso.get("coefficients", {}).get(feature, 0)
        lasso_r2 = lasso.get("r2_score", 0)
        
        if abs(lasso_coef) > 0.01 and lasso_r2 > 0.1:
            score += min(abs(lasso_coef) * 5, 0.3) * lasso_r2
            if direction == SignalDirection.NEUTRAL:
                direction = self._coefficient_to_direction(lasso_coef)
        
        # XGBoost SHAP
        xgboost = multivariate_results.get("xgboost", {})
        shap_results = xgboost.get("shap_results", {})
        shap_result = shap_results.get(feature)
        xgboost_r2 = xgboost.get("r2_score", 0)
        
        if shap_result:
            shap_value = abs(shap_result.get("mean_shap_value", 0))
            score += min(shap_value * 2, 0.4) * xgboost_r2
            if direction == SignalDirection.NEUTRAL:
                direction = SignalDirection.POSITIVE if shap_result.get("direction") == "positive" else SignalDirection.NEGATIVE
        
        # 随机森林重要性
        rf = multivariate_results.get("random_forest", {})
        rf_importance = rf.get("feature_importance", {}).get(feature, 0)
        rf_r2 = rf.get("r2_score", 0)
        
        if rf_importance > 0.01:
            score += min(rf_importance * 3, 0.3) * rf_r2
        
        return min(score, 1.0), direction
