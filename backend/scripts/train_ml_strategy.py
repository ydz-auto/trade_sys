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

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_data():
    """加载特征数据"""
    print("📊 加载数据...")
    features_path = project_root / "data_lake" / "features" / "binance" / "BTCUSDT" / "features_with_structure.parquet"
    
    if not features_path.exists():
        print(f"❌ 文件不存在: {features_path}")
        return None
    
    df = pd.read_parquet(features_path)
    print(f"✅ 数据加载完成: {len(df)} 条记录")
    return df


def prepare_features(df):
    """准备特征和目标"""
    print("\n🔧 准备特征...")
    
    # 选择可用的特征
    base_features = [
        'rsi_14', 'macd', 'volume_ratio', 'funding_rate', 'funding_zscore',
        'volatility_1h', 'bb_position', 'return_5m', 'return_1h', 'return_15m'
    ]
    
    # 检查哪些特征存在
    features = []
    for f in base_features:
        if f in df.columns:
            features.append(f)
    
    print(f"📈 使用特征: {features}")
    
    # 创建目标变量：预测未来1小时的涨跌
    if 'return_5m' in df.columns:
        df['future_return_1h'] = df['return_5m'].shift(-12).rolling(12).sum()
        df['target'] = (df['future_return_1h'] > 0).astype(int)
    else:
        # 备用方案
        df['future_return_1h'] = df['close'].pct_change(12).shift(-12)
        df['target'] = (df['future_return_1h'] > 0).astype(int)
    
    # 处理缺失值
    df = df.dropna(subset=features + ['target'])
    
    print(f"✅ 训练样本: {len(df)}")
    return df, features


def train_model(df, features):
    """训练模型"""
    print("\n🚀 开始训练...")
    
    X = df[features].fillna(0)
    y = df['target']
    
    # 时间序列分割
    train_size = int(0.8 * len(X))
    X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
    y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]
    
    try:
        # 尝试 LightGBM
        print("🎯 尝试 LightGBM...")
        import lightgbm as lgb
        
        model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.05,
            random_state=42,
            verbose=-1
        )
        
        model.fit(X_train, y_train)
        
        train_acc = model.score(X_train, y_train)
        test_acc = model.score(X_test, y_test)
        
        print(f"✅ LightGBM 训练完成！")
        print(f"   - 训练集准确率: {train_acc:.3f}")
        print(f"   - 验证集准确率: {test_acc:.3f}")
        
        # 特征重要性
        feature_importance = dict(zip(features, model.feature_importances_))
        sorted_importance = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        print("\n🔝 特征重要性 Top 5:")
        for f, imp in sorted_importance[:5]:
            print(f"   - {f}: {imp}")
        
        return model, {
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
            
            model.fit(X_train, y_train)
            
            train_acc = model.score(X_train, y_train)
            test_acc = model.score(X_test, y_test)
            
            print(f"✅ XGBoost 训练完成！")
            print(f"   - 训练集准确率: {train_acc:.3f}")
            print(f"   - 验证集准确率: {test_acc:.3f}")
            
            return model, {
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
            
            model.fit(X_train, y_train)
            
            train_acc = model.score(X_train, y_train)
            test_acc = model.score(X_test, y_test)
            
            print(f"✅ RandomForest 训练完成！")
            print(f"   - 训练集准确率: {train_acc:.3f}")
            print(f"   - 验证集准确率: {test_acc:.3f}")
            
            return model, {
                'model_type': 'random_forest',
                'train_acc': train_acc,
                'test_acc': test_acc
            }


def save_model(model, features, model_info):
    """保存模型"""
    output_dir = project_root / "data_lake" / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 保存模型到: {output_dir}")
    
    import joblib
    joblib.dump(model, output_dir / "ml_trading_model.pkl")
    
    model_config = {
        'features': features,
        'target_shift': 12,  # 预测1小时后
        'model_type': model_info['model_type'],
        'train_acc': float(model_info['train_acc']),
        'test_acc': float(model_info['test_acc'])
    }
    
    with open(output_dir / "ml_model_config.json", 'w') as f:
        json.dump(model_config, f, indent=2)
    
    print("✅ 模型保存成功！")


def main():
    print("=" * 60)
    print("🚀 ML策略训练脚本")
    print("=" * 60)
    
    df = load_data()
    if df is None:
        return
    
    df, features = prepare_features(df)
    
    model, model_info = train_model(df, features)
    
    if model is not None:
        save_model(model, features, model_info)
        print("\n🎉 训练完成！")
    else:
        print("\n❌ 训练失败")


if __name__ == "__main__":
    main()
