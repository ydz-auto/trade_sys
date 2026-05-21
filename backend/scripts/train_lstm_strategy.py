"""
LSTM 策略训练脚本
基于时序数据训练价格预测模型
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
    print(f"📅 时间范围: {df.index[0]} ~ {df.index[-1]}")
    return df


def prepare_training_data(df, sequence_length=24, target_shift=12):
    """准备训练数据（防止数据泄漏版本）
    
    Args:
        df: 特征DataFrame
        sequence_length: 序列长度（24根K线 = 2小时）
        target_shift: 预测未来多少根K线（12根 = 1小时）
    
    重要改进：
    1. Scaler 只在训练集上 fit，防止验证集泄漏
    2. Future return 不会被加入特征
    3. 时间序列分割，不打乱数据
    """
    print("\n🔧 准备训练数据（防泄漏版本）...")
    
    features = [
        'rsi_14', 'macd', 'macd_signal', 'volume_ratio',
        'funding_rate', 'funding_zscore', 'oi_delta',
        'volatility_1h', 'bb_position', 'return_5m',
        'return_1h', 'trend_strength_12h'
    ]
    
    df['regime_code_num'] = df['regime_code'].fillna(0) if 'regime_code' in df.columns else 0
    features = features + ['regime_code_num']
    
    available_features = []
    for f in features:
        if f in df.columns:
            available_features.append(f)
    
    print(f"📈 使用特征: {available_features}")
    
    target_col = 'return_5m'
    if target_col in df.columns:
        target = df[target_col].shift(-target_shift)
        y_raw = (target > 0).astype(int).values
    else:
        target = df['close'].pct_change().shift(-target_shift)
        y_raw = (target > 0).astype(int).values
    
    feature_data = df[available_features].fillna(0).values
    
    valid_start = sequence_length
    valid_end = len(df) - target_shift
    
    X_all = []
    y_all = []
    for i in range(valid_start, valid_end):
        X_all.append(feature_data[i-sequence_length:i])
        y_all.append(y_raw[i])
    
    X_all = np.array(X_all)
    y_all = np.array(y_all)
    
    train_size = int(0.8 * len(X_all))
    X_train_raw = X_all[:train_size]
    X_val_raw = X_all[train_size:]
    y_train = y_all[:train_size]
    y_val = y_all[train_size:]
    
    print(f"📊 训练集: {len(X_train_raw)}, 验证集: {len(X_val_raw)}")
    
    from sklearn.preprocessing import MinMaxScaler
    
    scaler = MinMaxScaler()
    
    n_train_samples, seq_len, n_features = X_train_raw.shape
    X_train_reshaped = X_train_raw.reshape(-1, n_features)
    scaler.fit(X_train_reshaped)
    
    X_train_scaled = scaler.transform(X_train_reshaped).reshape(n_train_samples, seq_len, n_features)
    
    n_val_samples = X_val_raw.shape[0]
    X_val_reshaped = X_val_raw.reshape(-1, n_features)
    X_val_scaled = scaler.transform(X_val_reshaped).reshape(n_val_samples, seq_len, n_features)
    
    print(f"✅ 训练数据准备完成: X_train shape={X_train_scaled.shape}, X_val shape={X_val_scaled.shape}")
    print(f"🔒 Scaler 仅在训练集上 fit，防止数据泄漏")
    
    return X_train_scaled, X_val_scaled, y_train, y_val, scaler, available_features


def build_lstm_model(input_shape):
    """构建LSTM模型"""
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.optimizers import Adam
        
        print("\n🧠 构建LSTM模型...")
        
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        model.summary()
        return model
        
    except ImportError:
        print("⚠️ TensorFlow 未安装，使用简单模型...")
        return None


def train_model(X_train, X_val, y_train, y_val):
    """训练模型"""
    print("\n🚀 开始训练...")
    
    try:
        model = build_lstm_model((X_train.shape[1], X_train.shape[2]))
        
        if model is not None:
            # TensorFlow LSTM
            from tensorflow.keras.callbacks import EarlyStopping
            
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=5,
                restore_best_weights=True
            )
            
            history = model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=30,
                batch_size=64,
                callbacks=[early_stopping]
            )
            
            return model, history
        else:
            # 备用：简单模型
            print("使用随机森林作为备用...")
            from sklearn.ensemble import RandomForestClassifier
            
            # 展平序列用于传统ML
            X_train_flat = X_train.reshape(len(X_train), -1)
            X_val_flat = X_val.reshape(len(X_val), -1)
            
            clf = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            clf.fit(X_train_flat, y_train)
            print(f"✅ 随机森林训练完成，验证准确率: {clf.score(X_val_flat, y_val):.3f}")
            
            return clf, None
            
    except Exception as e:
        print(f"❌ 训练出错: {e}")
        return None, None


def save_model(model, scaler, features, history=None):
    """保存模型和相关文件"""
    output_dir = get_models_path()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 保存模型到: {output_dir}")
    
    # 保存scaler和特征
    import joblib
    joblib.dump(scaler, output_dir / "lstm_scaler.pkl")
    
    model_info = {
        'features': features,
        'sequence_length': 24,
        'target_shift': 12
    }
    
    with open(output_dir / "model_config.json", 'w') as f:
        json.dump(model_info, f, indent=2)
    
    # 保存模型
    if hasattr(model, 'save'):
        model.save(output_dir / "lstm_price_prediction.keras")
    else:
        joblib.dump(model, output_dir / "backup_model.pkl")
    
    print("✅ 模型保存成功！")
    
    # 保存训练历史
    if history:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        
        axes[0].plot(history.history['loss'], label='train_loss')
        axes[0].plot(history.history['val_loss'], label='val_loss')
        axes[0].set_title('Loss')
        axes[0].legend()
        
        axes[1].plot(history.history['accuracy'], label='train_acc')
        axes[1].plot(history.history['val_accuracy'], label='val_acc')
        axes[1].set_title('Accuracy')
        axes[1].legend()
        
        plt.tight_layout()
        plt.savefig(output_dir / "training_history.png")
        print("✅ 训练历史图表已保存")


def main():
    print("=" * 60)
    print("🚀 LSTM 策略训练脚本")
    print("=" * 60)
    
    # 1. 加载数据
    df = load_data()
    if df is None:
        return
    
    # 2. 准备训练数据
    X_train, X_val, y_train, y_val, scaler, features = prepare_training_data(df)
    
    # 3. 训练模型
    model, history = train_model(X_train, X_val, y_train, y_val)
    
    # 4. 保存
    if model is not None:
        save_model(model, scaler, features, history)
        print("\n🎉 训练完成！")
    else:
        print("\n❌ 训练失败")


if __name__ == "__main__":
    main()
