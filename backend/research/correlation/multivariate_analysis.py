"""
多变量分析模块 - LASSO/Ridge回归、XGBoost+SHAP、随机森林
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("research.correlation.multivariate")


@dataclass
class RegressionResult:
    """回归分析结果"""
    model_type: str
    coefficients: Dict[str, float]  # 特征系数
    intercept: float
    r2_score: float
    mse: float
    significant_features: List[str]  # 显著非零的特征
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": self.model_type,
            "coefficients": self.coefficients,
            "intercept": self.intercept,
            "r2_score": self.r2_score,
            "mse": self.mse,
            "significant_features": self.significant_features,
        }


@dataclass
class SHAPResult:
    """SHAP分析结果"""
    feature: str
    mean_shap_value: float
    shap_std: float
    direction: str  # "positive" or "negative"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "mean_shap_value": self.mean_shap_value,
            "shap_std": self.shap_std,
            "direction": self.direction,
        }


@dataclass
class TreeModelResult:
    """树模型分析结果"""
    model_type: str
    feature_importance: Dict[str, float]
    shap_results: Dict[str, SHAPResult]
    r2_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": self.model_type,
            "feature_importance": self.feature_importance,
            "shap_results": {k: v.to_dict() for k, v in self.shap_results.items()},
            "r2_score": self.r2_score,
        }


class MultivariateAnalyzer:
    """
    多变量分析器
    
    功能：
    1. LASSO/Ridge 回归（带正则化，自动特征选择）
    2. XGBoost + SHAP（非线性 + 可解释性）
    3. 随机森林特征重要性
    """
    
    def __init__(self, test_size: float = 0.2, random_state: int = 42):
        self.test_size = test_size
        self.random_state = random_state
    
    def lasso_regression(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        alphas: Optional[List[float]] = None
    ) -> RegressionResult:
        """
        LASSO 回归分析
        
        LASSO 倾向于产生稀疏解，自动进行特征选择
        正系数 -> 正相关，负系数 -> 负相关
        """
        try:
            from sklearn.linear_model import LassoCV
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import r2_score, mean_squared_error
        except ImportError:
            logger.warning("scikit-learn not installed, skipping LASSO regression")
            return self._empty_regression_result("lasso")
        
        # 准备数据
        X = df[feature_cols].fillna(0)
        y = df[target_col].fillna(0)
        
        if len(X) < 10:
            logger.warning(f"Insufficient data for LASSO: {len(X)} samples")
            return self._empty_regression_result("lasso")
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state
        )
        
        # 交叉验证选择最佳 alpha
        if alphas is None:
            alphas = np.logspace(-4, 1, 50)
        
        model = LassoCV(alphas=alphas, cv=5, random_state=self.random_state)
        model.fit(X_train, y_train)
        
        # 预测和评估
        y_pred = model.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        
        # 提取系数
        coefficients = dict(zip(feature_cols, model.coef_))
        significant_features = [f for f, coef in coefficients.items() if abs(coef) > 1e-6]
        
        logger.info(f"LASSO: alpha={model.alpha_:.6f}, R²={r2:.4f}, {len(significant_features)} significant features")
        
        return RegressionResult(
            model_type="lasso",
            coefficients=coefficients,
            intercept=model.intercept_,
            r2_score=r2,
            mse=mse,
            significant_features=significant_features
        )
    
    def ridge_regression(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        alphas: Optional[List[float]] = None
    ) -> RegressionResult:
        """
        Ridge 回归分析
        
        Ridge 使用 L2 正则化，系数会收缩但不会为零
        适合处理多重共线性
        """
        try:
            from sklearn.linear_model import RidgeCV
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import r2_score, mean_squared_error
        except ImportError:
            logger.warning("scikit-learn not installed, skipping Ridge regression")
            return self._empty_regression_result("ridge")
        
        X = df[feature_cols].fillna(0)
        y = df[target_col].fillna(0)
        
        if len(X) < 10:
            return self._empty_regression_result("ridge")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state
        )
        
        if alphas is None:
            alphas = np.logspace(-3, 2, 50)
        
        model = RidgeCV(alphas=alphas, cv=5)
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        
        coefficients = dict(zip(feature_cols, model.coef_))
        # Ridge 没有真正的"稀疏"特征，但可以根据系数大小判断重要性
        significant_features = [f for f, coef in coefficients.items() if abs(coef) > 0.01]
        
        logger.info(f"Ridge: alpha={model.alpha_:.6f}, R²={r2:.4f}")
        
        return RegressionResult(
            model_type="ridge",
            coefficients=coefficients,
            intercept=model.intercept_,
            r2_score=r2,
            mse=mse,
            significant_features=significant_features
        )
    
    def xgboost_with_shap(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        n_estimators: int = 100,
        max_depth: int = 5
    ) -> TreeModelResult:
        """
        XGBoost + SHAP 分析
        
        SHAP 值可以量化每个特征对预测的贡献和方向
        """
        try:
            import xgboost as xgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import r2_score
        except ImportError:
            logger.warning("xgboost not installed, skipping XGBoost analysis")
            return self._empty_tree_result("xgboost")
        
        X = df[feature_cols].fillna(0)
        y = df[target_col].fillna(0)
        
        if len(X) < 10:
            return self._empty_tree_result("xgboost")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state
        )
        
        # 训练 XGBoost
        model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.1,
            random_state=self.random_state,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        
        # 评估
        y_pred = model.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        
        # 特征重要性
        importance = model.feature_importances_
        feature_importance = dict(zip(feature_cols, importance))
        
        # SHAP 分析
        shap_results = self._calculate_shap_values(model, X_test, feature_cols)
        
        logger.info(f"XGBoost: R²={r2:.4f}, SHAP calculated for {len(shap_results)} features")
        
        return TreeModelResult(
            model_type="xgboost",
            feature_importance=feature_importance,
            shap_results=shap_results,
            r2_score=r2
        )
    
    def _calculate_shap_values(
        self,
        model,
        X: pd.DataFrame,
        feature_cols: List[str]
    ) -> Dict[str, SHAPResult]:
        """计算 SHAP 值"""
        try:
            import shap
        except ImportError:
            logger.warning("shap not installed, using approximate SHAP")
            return self._approximate_shap(model, X, feature_cols)
        
        try:
            # 使用 TreeExplainer
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)
            
            shap_results = {}
            for i, feature in enumerate(feature_cols):
                mean_shap = np.mean(shap_values[:, i])
                shap_std = np.std(shap_values[:, i])
                direction = "positive" if mean_shap > 0 else "negative"
                
                shap_results[feature] = SHAPResult(
                    feature=feature,
                    mean_shap_value=float(mean_shap),
                    shap_std=float(shap_std),
                    direction=direction
                )
            
            return shap_results
            
        except Exception as e:
            logger.warning(f"SHAP calculation failed: {e}, using approximation")
            return self._approximate_shap(model, X, feature_cols)
    
    def _approximate_shap(
        self,
        model,
        X: pd.DataFrame,
        feature_cols: List[str]
    ) -> Dict[str, SHAPResult]:
        """近似 SHAP 值（使用置换重要性）"""
        shap_results = {}
        baseline_pred = model.predict(X.mean().values.reshape(1, -1))[0]
        
        for feature in feature_cols:
            # 置换该特征，观察预测变化
            X_permuted = X.copy()
            X_permuted[feature] = np.random.permutation(X_permuted[feature])
            
            permuted_pred = model.predict(X_permuted)
            original_pred = model.predict(X)
            
            # 近似 SHAP 值为预测变化的均值
            shap_values = original_pred - permuted_pred
            mean_shap = np.mean(shap_values)
            shap_std = np.std(shap_values)
            
            shap_results[feature] = SHAPResult(
                feature=feature,
                mean_shap_value=float(mean_shap),
                shap_std=float(shap_std),
                direction="positive" if mean_shap > 0 else "negative"
            )
        
        return shap_results
    
    def random_forest_importance(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        n_estimators: int = 100
    ) -> TreeModelResult:
        """
        随机森林特征重要性分析
        """
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import r2_score
        except ImportError:
            logger.warning("scikit-learn not installed, skipping Random Forest")
            return self._empty_tree_result("random_forest")
        
        X = df[feature_cols].fillna(0)
        y = df[target_col].fillna(0)
        
        if len(X) < 10:
            return self._empty_tree_result("random_forest")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state
        )
        
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=self.random_state,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        
        # 特征重要性
        importance = model.feature_importances_
        feature_importance = dict(zip(feature_cols, importance))
        
        # 近似 SHAP
        shap_results = self._approximate_shap(model, X_test, feature_cols)
        
        logger.info(f"Random Forest: R²={r2:.4f}")
        
        return TreeModelResult(
            model_type="random_forest",
            feature_importance=feature_importance,
            shap_results=shap_results,
            r2_score=r2
        )
    
    def _empty_regression_result(self, model_type: str) -> RegressionResult:
        """空回归结果"""
        return RegressionResult(
            model_type=model_type,
            coefficients={},
            intercept=0,
            r2_score=0,
            mse=0,
            significant_features=[]
        )
    
    def _empty_tree_result(self, model_type: str) -> TreeModelResult:
        """空树模型结果"""
        return TreeModelResult(
            model_type=model_type,
            feature_importance={},
            shap_results={},
            r2_score=0
        )
