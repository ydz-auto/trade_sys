"""
相关性分析主入口 - 整合所有分析步骤
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

from .types import SignalDirection
from .data_preparation import DataPreparation, FeatureMatrix
from .univariate_analysis import UnivariateAnalyzer
from .multivariate_analysis import MultivariateAnalyzer
from .llm_enhancement import LLMEnhancement
from .scoring import CorrelationScorer, SignalAssessment
from .visualization import CorrelationVisualizer

logger = get_logger("research.correlation")


@dataclass
class CorrelationConfig:
    """相关性分析配置"""
    # 数据配置
    symbol: str = "BTC"
    timeframe: str = "1h"
    
    # 滞后窗口配置
    lag_windows: List[int] = field(default_factory=lambda: [1, 5, 10, 15])
    
    # 分析配置
    significance_level: float = 0.05
    min_correlation: float = 0.1
    
    # 特征选择
    structured_features: List[str] = field(default_factory=list)
    unstructured_sources: List[str] = field(default_factory=lambda: ["news", "social"])
    
    # 输出配置
    output_dir: str = "./correlation_output"
    generate_visualization: bool = True
    
    def __post_init__(self):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)


@dataclass
class CorrelationResult:
    """相关性分析结果"""
    symbol: str
    timeframe: str
    timestamp: datetime
    
    # 各信号评估结果
    signal_assessments: Dict[str, SignalAssessment] = field(default_factory=dict)
    
    # 综合统计
    positive_signals: List[str] = field(default_factory=list)
    negative_signals: List[str] = field(default_factory=list)
    neutral_signals: List[str] = field(default_factory=list)
    
    # 详细分析结果
    univariate_results: Dict[str, Any] = field(default_factory=dict)
    multivariate_results: Dict[str, Any] = field(default_factory=dict)
    llm_results: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "signal_assessments": {
                k: v.to_dict() for k, v in self.signal_assessments.items()
            },
            "positive_signals": self.positive_signals,
            "negative_signals": self.negative_signals,
            "neutral_signals": self.neutral_signals,
            "summary": {
                "total_signals": len(self.signal_assessments),
                "positive_count": len(self.positive_signals),
                "negative_count": len(self.negative_signals),
                "neutral_count": len(self.neutral_signals),
            }
        }
    
    def save(self, filepath: Optional[str] = None):
        """保存结果到文件"""
        if filepath is None:
            filename = f"correlation_{self.symbol}_{self.timeframe}_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = Path(self.metadata.get("output_dir", "./correlation_output")) / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Correlation result saved to {filepath}")
        return filepath


class CorrelationAnalyzer:
    """
    多数据源正负相关性分析器
    
    使用流程：
    1. 准备数据（结构化 + 非结构化）
    2. 单变量分析（相关性、互信息、Granger）
    3. 多变量分析（回归、树模型、SHAP）
    4. LLM情感增强
    5. 综合评分
    6. 可视化输出
    """
    
    def __init__(self, config: Optional[CorrelationConfig] = None):
        self.config = config or CorrelationConfig()
        
        # 初始化各模块
        self.data_prep = DataPreparation()
        self.univariate = UnivariateAnalyzer()
        self.multivariate = MultivariateAnalyzer()
        self.llm_enhance = LLMEnhancement()
        self.scorer = CorrelationScorer()
        self.visualizer = CorrelationVisualizer(output_dir=self.config.output_dir)
        
        logger.info(f"CorrelationAnalyzer initialized for {self.config.symbol} {self.config.timeframe}")
    
    async def analyze(
        self,
        feature_df: Optional[pd.DataFrame] = None,
        news_data: Optional[List[Dict]] = None,
        target_col: str = "returns"
    ) -> CorrelationResult:
        """
        执行完整的相关性分析流程
        
        Args:
            feature_df: 特征DataFrame（从feature_pipeline获取）
            news_data: 新闻数据列表（从news_collector获取）
            target_col: 目标变量列名（通常是收益率）
        
        Returns:
            CorrelationResult: 分析结果
        """
        start_time = datetime.now()
        logger.info("Starting correlation analysis...")
        
        # Step 1: 数据准备
        logger.info("Step 1: Data preparation...")
        feature_matrix = await self._prepare_data(feature_df, news_data, target_col)
        
        # Step 2: 单变量分析
        logger.info("Step 2: Univariate analysis...")
        univariate_results = await self._univariate_analysis(feature_matrix)
        
        # Step 3: 多变量分析
        logger.info("Step 3: Multivariate analysis...")
        multivariate_results = await self._multivariate_analysis(feature_matrix)
        
        # Step 4: LLM增强（如果有新闻数据）
        llm_results = {}
        if news_data:
            logger.info("Step 4: LLM enhancement...")
            llm_results = await self._llm_enhancement(news_data, feature_matrix)
        
        # Step 5: 综合评分
        logger.info("Step 5: Scoring...")
        signal_assessments = self._comprehensive_scoring(
            univariate_results,
            multivariate_results,
            llm_results
        )
        
        # Step 6: 分类信号
        positive, negative, neutral = self._classify_signals(signal_assessments)
        
        # 构建结果
        result = CorrelationResult(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            timestamp=datetime.now(),
            signal_assessments=signal_assessments,
            positive_signals=positive,
            negative_signals=negative,
            neutral_signals=neutral,
            univariate_results=univariate_results,
            multivariate_results=multivariate_results,
            llm_results=llm_results,
            metadata={
                "output_dir": self.config.output_dir,
                "analysis_duration_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "config": {
                    "lag_windows": self.config.lag_windows,
                    "significance_level": self.config.significance_level,
                }
            }
        )
        
        # Step 7: 可视化
        if self.config.generate_visualization:
            logger.info("Step 6: Generating visualizations...")
            await self._generate_visualizations(result, feature_matrix)
        
        logger.info(f"Correlation analysis completed. Total signals: {len(signal_assessments)}")
        logger.info(f"  Positive: {len(positive)}, Negative: {len(negative)}, Neutral: {len(neutral)}")
        
        return result
    
    async def _prepare_data(
        self,
        feature_df: Optional[pd.DataFrame],
        news_data: Optional[List[Dict]],
        target_col: str
    ) -> FeatureMatrix:
        """准备数据"""
        # 如果没有提供数据，尝试从系统获取
        if feature_df is None:
            feature_df = await self.data_prep.fetch_from_pipeline(
                self.config.symbol,
                self.config.timeframe
            )
        
        # 处理非结构化数据
        sentiment_series = None
        if news_data:
            sentiment_series = await self.data_prep.process_unstructured_data(
                news_data,
                feature_df.index if feature_df is not None else None
            )
        
        # 构建特征矩阵
        feature_matrix = self.data_prep.build_feature_matrix(
            feature_df,
            sentiment_series,
            target_col=target_col,
            lag_windows=self.config.lag_windows
        )
        
        return feature_matrix
    
    async def _univariate_analysis(self, feature_matrix: FeatureMatrix) -> Dict[str, Any]:
        """单变量分析"""
        results = {}
        
        feature_cols = [c for c in feature_matrix.data.columns if c != feature_matrix.target_col]
        
        for feature in feature_cols:
            corr_result = self.univariate.correlation_analysis(
                feature_matrix.data, feature, feature_matrix.target_col
            )
            mi_result = self.univariate.mutual_information(
                feature_matrix.data, feature, feature_matrix.target_col
            )
            granger_result = self.univariate.granger_causality(
                feature_matrix.data, feature, feature_matrix.target_col
            )
            lag_result = self.univariate.lag_correlation(
                feature_matrix.data, feature, feature_matrix.target_col,
                max_lag=max(self.config.lag_windows)
            )
            
            results[feature] = {
                "correlation": corr_result.to_dict() if hasattr(corr_result, 'to_dict') else corr_result,
                "mutual_info": mi_result.to_dict() if hasattr(mi_result, 'to_dict') else mi_result,
                "granger": {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in granger_result.items()} if isinstance(granger_result, dict) else granger_result,
                "lag_correlation": lag_result.to_dict() if hasattr(lag_result, 'to_dict') else lag_result,
            }
        
        return results
    
    async def _multivariate_analysis(self, feature_matrix: FeatureMatrix) -> Dict[str, Any]:
        """多变量分析"""
        feature_cols = [c for c in feature_matrix.data.columns if c != feature_matrix.target_col]
        
        results = {}
        
        lasso_result = self.multivariate.lasso_regression(
            feature_matrix.data, feature_cols, feature_matrix.target_col
        )
        results["lasso"] = lasso_result.to_dict() if hasattr(lasso_result, 'to_dict') else lasso_result
        
        xgboost_result = self.multivariate.xgboost_with_shap(
            feature_matrix.data, feature_cols, feature_matrix.target_col
        )
        results["xgboost"] = xgboost_result.to_dict() if hasattr(xgboost_result, 'to_dict') else xgboost_result
        
        rf_result = self.multivariate.random_forest_importance(
            feature_matrix.data, feature_cols, feature_matrix.target_col
        )
        results["random_forest"] = rf_result.to_dict() if hasattr(rf_result, 'to_dict') else rf_result
        
        return results
    
    async def _llm_enhancement(
        self,
        news_data: List[Dict],
        feature_matrix: FeatureMatrix
    ) -> Dict[str, Any]:
        """LLM增强分析"""
        results = {}
        
        # LLM情感趋势分析
        results["sentiment_trend"] = await self.llm_enhance.analyze_sentiment_trend(news_data)
        
        # LLM因果推断
        results["causal_inference"] = await self.llm_enhance.causal_inference(
            news_data, feature_matrix
        )
        
        # LLM预测评分
        results["predictions"] = await self.llm_enhance.generate_predictions(news_data)
        
        return results
    
    def _comprehensive_scoring(
        self,
        univariate_results: Dict[str, Any],
        multivariate_results: Dict[str, Any],
        llm_results: Dict[str, Any]
    ) -> Dict[str, SignalAssessment]:
        """综合评分"""
        assessments = {}
        
        for feature, uni_result in univariate_results.items():
            assessment = self.scorer.calculate_score(
                feature,
                uni_result,
                multivariate_results,
                llm_results.get("sentiment_trend") if llm_results else None
            )
            assessments[feature] = assessment
        
        return assessments
    
    def _classify_signals(
        self,
        assessments: Dict[str, SignalAssessment]
    ) -> Tuple[List[str], List[str], List[str]]:
        """分类信号方向"""
        positive = []
        negative = []
        neutral = []
        
        for feature, assessment in assessments.items():
            if assessment.direction == SignalDirection.POSITIVE:
                positive.append(feature)
            elif assessment.direction == SignalDirection.NEGATIVE:
                negative.append(feature)
            else:
                neutral.append(feature)
        
        return positive, negative, neutral
    
    async def _generate_visualizations(
        self,
        result: CorrelationResult,
        feature_matrix: FeatureMatrix
    ):
        """生成可视化"""
        # 滞后相关性热力图
        self.visualizer.plot_lag_correlation_heatmap(
            result.univariate_results,
            save_path=f"{self.config.output_dir}/lag_correlation_heatmap.png"
        )
        
        # 信号贡献柱状图
        self.visualizer.plot_signal_contribution(
            result.signal_assessments,
            save_path=f"{self.config.output_dir}/signal_contribution.png"
        )
        
        # SHAP重要性图
        if "xgboost" in result.multivariate_results:
            self.visualizer.plot_shap_importance(
                result.multivariate_results["xgboost"],
                save_path=f"{self.config.output_dir}/shap_importance.png"
            )
        
        # 综合评分雷达图
        self.visualizer.plot_comprehensive_radar(
            result.signal_assessments,
            save_path=f"{self.config.output_dir}/comprehensive_radar.png"
        )
        
        logger.info(f"Visualizations saved to {self.config.output_dir}")


# 便捷函数
async def analyze_correlation(
    feature_df: Optional[pd.DataFrame] = None,
    news_data: Optional[List[Dict]] = None,
    symbol: str = "BTC",
    timeframe: str = "1h",
    **kwargs
) -> CorrelationResult:
    """
    便捷函数：快速执行相关性分析
    
    Example:
        result = await analyze_correlation(
            feature_df=df,
            news_data=news,
            symbol="BTC",
            timeframe="1h"
        )
    """
    config = CorrelationConfig(symbol=symbol, timeframe=timeframe, **kwargs)
    analyzer = CorrelationAnalyzer(config)
    return await analyzer.analyze(feature_df, news_data)
