"""
可视化模块 - 生成相关性分析图表
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from .types import SignalDirection
from .scoring import SignalAssessment

logger = get_logger("research.correlation.viz")


class CorrelationVisualizer:
    """
    相关性可视化器
    
    生成：
    1. 滞后相关性热力图
    2. 信号贡献柱状图
    3. SHAP重要性图
    4. 综合评分雷达图
    """
    
    def __init__(self, output_dir: str = "./correlation_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def plot_lag_correlation_heatmap(
        self,
        univariate_results: Dict[str, Any],
        save_path: Optional[str] = None,
        top_n: int = 15
    ) -> str:
        """
        绘制滞后相关性热力图
        """
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
        except ImportError:
            logger.warning("matplotlib/seaborn not installed, skipping heatmap")
            return ""
        
        # 提取滞后相关性数据
        lag_data = {}
        for feature, results in univariate_results.items():
            lag_corr = results.get("lag_correlation", {})
            if lag_corr:
                lag_data[feature] = lag_corr.get("lag_correlations", {})
        
        if not lag_data:
            logger.warning("No lag correlation data available")
            return ""
        
        # 选择相关性最强的特征
        max_corrs = {f: max(abs(v) for v in lags.values()) for f, lags in lag_data.items()}
        top_features = sorted(max_corrs.items(), key=lambda x: x[1], reverse=True)[:top_n]
        top_feature_names = [f[0] for f in top_features]
        
        # 构建热力图数据
        df_heatmap = pd.DataFrame({
            f: lag_data[f] for f in top_feature_names if f in lag_data
        }).T
        
        # 绘图
        fig, ax = plt.subplots(figsize=(14, 10))
        sns.heatmap(
            df_heatmap,
            annot=True,
            fmt=".2f",
            cmap="RdBu_r",
            center=0,
            vmin=-1,
            vmax=1,
            ax=ax,
            cbar_kws={"label": "Correlation"}
        )
        ax.set_title("Lag Correlation Heatmap", fontsize=14, fontweight='bold')
        ax.set_xlabel("Lag Periods")
        ax.set_ylabel("Features")
        
        if save_path is None:
            save_path = self.output_dir / "lag_correlation_heatmap.png"
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Lag correlation heatmap saved to {save_path}")
        return str(save_path)
    
    def plot_signal_contribution(
        self,
        signal_assessments: Dict[str, SignalAssessment],
        save_path: Optional[str] = None,
        top_n: int = 20
    ) -> str:
        """
        绘制信号贡献柱状图
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not installed, skipping contribution plot")
            return ""
        
        # 准备数据
        features = []
        directions = []
        scores = []
        colors = []
        
        for feature, assessment in signal_assessments.items():
            features.append(feature)
            directions.append(assessment.direction.value)
            scores.append(assessment.strength * (1 if assessment.direction == SignalDirection.POSITIVE else -1))
            
            if assessment.direction == SignalDirection.POSITIVE:
                colors.append('#2ecc71')  # 绿色
            elif assessment.direction == SignalDirection.NEGATIVE:
                colors.append('#e74c3c')  # 红色
            else:
                colors.append('#95a5a6')  # 灰色
        
        # 按绝对值排序
        sorted_indices = np.argsort(np.abs(scores))[::-1][:top_n]
        features = [features[i] for i in sorted_indices]
        scores = [scores[i] for i in sorted_indices]
        colors = [colors[i] for i in sorted_indices]
        
        # 绘图
        fig, ax = plt.subplots(figsize=(12, max(6, len(features) * 0.4)))
        
        bars = ax.barh(features, scores, color=colors, alpha=0.8)
        ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
        ax.set_xlabel("Correlation Strength (Positive = Green, Negative = Red)")
        ax.set_title("Signal Contribution Analysis", fontsize=14, fontweight='bold')
        
        # 添加数值标签
        for bar, score in zip(bars, scores):
            width = bar.get_width()
            ax.text(
                width + (0.02 if width >= 0 else -0.02),
                bar.get_y() + bar.get_height()/2,
                f'{score:.3f}',
                ha='left' if width >= 0 else 'right',
                va='center',
                fontsize=8
            )
        
        if save_path is None:
            save_path = self.output_dir / "signal_contribution.png"
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Signal contribution plot saved to {save_path}")
        return str(save_path)
    
    def plot_shap_importance(
        self,
        xgboost_results: Dict[str, Any],
        save_path: Optional[str] = None,
        top_n: int = 15
    ) -> str:
        """
        绘制 SHAP 重要性图
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not installed, skipping SHAP plot")
            return ""
        
        shap_results = xgboost_results.get("shap_results", {})
        
        if not shap_results:
            logger.warning("No SHAP results available")
            return ""
        
        # 提取 SHAP 值
        features = []
        shap_values = []
        colors = []
        
        for feature, result in shap_results.items():
            features.append(feature)
            shap_val = result.mean_shap_value
            shap_values.append(shap_val)
            
            if result.direction == "positive":
                colors.append('#3498db')
            else:
                colors.append('#e67e22')
        
        # 按绝对值排序
        sorted_indices = np.argsort(np.abs(shap_values))[::-1][:top_n]
        features = [features[i] for i in sorted_indices]
        shap_values = [shap_values[i] for i in sorted_indices]
        colors = [colors[i] for i in sorted_indices]
        
        # 绘图
        fig, ax = plt.subplots(figsize=(12, max(6, len(features) * 0.4)))
        
        bars = ax.barh(features, shap_values, color=colors, alpha=0.8)
        ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
        ax.set_xlabel("Mean SHAP Value (Impact on Prediction)")
        ax.set_title("SHAP Feature Importance", fontsize=14, fontweight='bold')
        
        if save_path is None:
            save_path = self.output_dir / "shap_importance.png"
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"SHAP importance plot saved to {save_path}")
        return str(save_path)
    
    def plot_comprehensive_radar(
        self,
        signal_assessments: Dict[str, SignalAssessment],
        save_path: Optional[str] = None
    ) -> str:
        """
        绘制综合评分雷达图
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not installed, skipping radar plot")
            return ""
        
        # 计算各类别的平均得分
        categories = {
            "Statistical": [],
            "ML (LASSO)": [],
            "ML (XGBoost)": [],
            "ML (Random Forest)": [],
            "LLM Enhancement": [],
        }
        
        for assessment in signal_assessments.values():
            categories["Statistical"].append(assessment.statistical_score)
            categories["ML (LASSO)"].append(assessment.ml_score * 0.3)  # 近似
            categories["ML (XGBoost)"].append(assessment.ml_score * 0.4)
            categories["ML (Random Forest)"].append(assessment.ml_score * 0.3)
            categories["LLM Enhancement"].append(assessment.llm_score)
        
        # 计算平均值
        values = [np.mean(v) if v else 0 for v in categories.values()]
        labels = list(categories.keys())
        
        # 雷达图
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        values += values[:1]  # 闭合
        angles += angles[:1]
        
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
        ax.fill(angles, values, color='#3498db', alpha=0.25)
        ax.plot(angles, values, color='#3498db', linewidth=2)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, size=10)
        ax.set_ylim(0, 1)
        ax.set_title("Comprehensive Scoring Radar", fontsize=14, fontweight='bold', pad=20)
        
        if save_path is None:
            save_path = self.output_dir / "comprehensive_radar.png"
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Comprehensive radar plot saved to {save_path}")
        return str(save_path)
    
    def generate_summary_report(
        self,
        positive_signals: List[str],
        negative_signals: List[str],
        neutral_signals: List[str],
        save_path: Optional[str] = None
    ) -> str:
        """
        生成文本摘要报告
        """
        lines = [
            "=" * 60,
            "多数据源正负相关性评估报告",
            "=" * 60,
            "",
            f"正相关信号 ({len(positive_signals)}个):",
            "-" * 40,
        ]
        
        for sig in positive_signals[:10]:  # 最多显示10个
            lines.append(f"  + {sig}")
        
        lines.extend([
            "",
            f"负相关信号 ({len(negative_signals)}个):",
            "-" * 40,
        ])
        
        for sig in negative_signals[:10]:
            lines.append(f"  - {sig}")
        
        lines.extend([
            "",
            f"无相关信号 ({len(neutral_signals)}个):",
            "-" * 40,
        ])
        
        for sig in neutral_signals[:10]:
            lines.append(f"  ~ {sig}")
        
        lines.extend([
            "",
            "=" * 60,
            f"总计: {len(positive_signals) + len(negative_signals) + len(neutral_signals)} 个信号",
            "=" * 60,
        ])
        
        report = "\n".join(lines)
        
        if save_path is None:
            save_path = self.output_dir / "correlation_summary.txt"
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Summary report saved to {save_path}")
        return report
