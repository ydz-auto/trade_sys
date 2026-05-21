"""
机器学习策略训练脚本（XGBoost/LightGBM 版本）
更轻量，更适合部署
"""

import os
import sys
import pandas as pd
import numpy as np
import json
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.data_lake import get_features_path, get_models_path


def load_data():
    """加载特征数据"""
    print("📊 加载数据...")
    features_path = get_features_path("binance", "BTCUSDT") / "features_with_structure.parquet"
    
    if not features_path.exists():
        print(f"❌ 文件不存在: {features_path}")
        return None
    
    df = pd.read_parquet(features_path)
    print(f"✅ 数据加载完成: {len(df)} 条记录")
    return df


def prepare_features(df):
    """准备特征和目标（防止数据泄漏版本）
    
    重要改进：
    1. Future return 不会被加入 df，防止误用
    2. Scaler 将在 train_model 中只在训练集上 fit
    3. 时间序列分割，不打乱数据
    """
    print("\n🔧 准备特征（防泄漏版本）...")
    
    base_features = [
        'rsi_14', 'macd', 'volume_ratio', 'funding_rate', 'funding_zscore',
        'volatility_1h', 'bb_position', 'return_5m', 'return_1h', 'return_15m'
    ]
    
    features = []
    for f in base_features:
        if f in df.columns:
            features.append(f)
    
    print(f"📈 使用特征: {features}")
    
    if 'return_5m' in df.columns:
        target = df['return_5m'].shift(-12).rolling(12).sum()
        y = (target > 0).astype(int)
    else:
        target = df['close'].pct_change(12).shift(-12)
        y = (target > 0).astype(int)
    
    valid_idx = ~(df[features].isna().any(axis=1) | y.isna())
    df_clean = df[valid_idx].copy()
    y_clean = y[valid_idx].copy()
    
    print(f"✅ 训练样本: {len(df_clean)}")
    print(f"🔒 Target 未加入 DataFrame，防止特征泄漏")
    
    return df_clean, features, y_clean


def train_model(df, features, y):
    """训练模型（防止数据泄漏版本）
    
    重要改进：
    1. Scaler 只在训练集上 fit
    2. 时间序列分割，不打乱数据
    """
    print("\n🚀 开始训练...")
    
    X = df[features].fillna(0)
    
    train_size = int(0.8 * len(X))
    X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
    y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]
    
    from sklearn.preprocessing import StandardScaler
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print(f"🔒 Scaler 仅在训练集上 fit，防止数据泄漏")
    
    try:
        print("🎯 尝试 LightGBM...")
        import lightgbm as lgb
        
        model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.05,
            random_state=42,
            verbose=-1
        )
        
        model.fit(X_train_scaled, y_train)
        
        train_acc = model.score(X_train_scaled, y_train)
        test_acc = model.score(X_test_scaled, y_test)
        
        print(f"✅ LightGBM 训练完成！")
        print(f"   - 训练集准确率: {train_acc:.3f}")
        print(f"   - 验证集准确率: {test_acc:.3f}")
        
        feature_importance = dict(zip(features, model.feature_importances_))
        sorted_importance = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        print("\n🔝 特征重要性 Top 5:")
        for f, imp in sorted_importance[:5]:
            print(f"   - {f}: {imp}")
        
        return model, scaler, {
            'model_type': 'lightgbm',
            'train_acc': train_acc,
            'test_acc': test_acc
        }
        
    except ImportError:
        print("⚠️ LightGBM 未安装，尝试 XGBoost...")
        try:
            import xgboost as xgb
            
            model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                random_state=42
            )
            
            model.fit(X_train_scaled, y_train)
            
            train_acc = model.score(X_train_scaled, y_train)
            test_acc = model.score(X_test_scaled, y_test)
            
            print(f"✅ XGBoost 训练完成！")
            print(f"   - 训练集准确率: {train_acc:.3f}")
            print(f"   - 验证集准确率: {test_acc:.3f}")
            
            return model, scaler, {
                'model_type': 'xgboost',
                'train_acc': train_acc,
                'test_acc': test_acc
            }
            
        except ImportError:
            print("⚠️ XGBoost 未安装，使用随机森林...")
            from sklearn.ensemble import RandomForestClassifier
            
            model = RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                random_state=42
            )
            
            model.fit(X_train_scaled, y_train)
            
            train_acc = model.score(X_train_scaled, y_train)
            test_acc = model.score(X_test_scaled, y_test)
            
            print(f"✅ RandomForest 训练完成！")
            print(f"   - 训练集准确率: {train_acc:.3f}")
            print(f"   - 验证集准确率: {test_acc:.3f}")
            
            return model, scaler, {
                'model_type': 'random_forest',
                'train_acc': train_acc,
                'test_acc': test_acc
            }


def save_model(model, scaler, features, model_info):
    """保存模型"""
    output_dir = get_models_path()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 保存模型到: {output_dir}")
    
    import joblib
    joblib.dump(model, output_dir / "ml_trading_model.pkl")
    joblib.dump(scaler, output_dir / "ml_scaler.pkl")
    
    model_config = {
        'features': features,
        'target_shift': 12,
        'model_type': model_info['model_type'],
        'train_acc': float(model_info['train_acc']),
        'test_acc': float(model_info['test_acc']),
        'leakage_protection': True
    }
    
    with open(output_dir / "ml_model_config.json", 'w') as f:
        json.dump(model_config, f, indent=2)
    
    print("✅ 模型保存成功！")


def main():
    print("=" * 60)
    print("🚀 ML策略训练脚本（防泄漏版本）")
    print("=" * 60)
    
    df = load_data()
    if df is None:
        return
    
    df, features, y = prepare_features(df)
    
    model, scaler, model_info = train_model(df, features, y)
    
    if model is not None:
        save_model(model, scaler, features, model_info)
        print("\n🎉 训练完成！")
    else:
        print("\n❌ 训练失败")


if __name__ == "__main__":
    main()
