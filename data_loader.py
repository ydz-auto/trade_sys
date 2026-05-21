import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from torch.utils.data import Dataset, DataLoader

class TimeSeriesDataset(Dataset):
    def __init__(self, X, y, seq_len):
        self.X = X.astype(np.float32)
        self.y = y.astype(np.int64)
        self.seq_len = seq_len
    
    def __len__(self):
        return len(self.X) - self.seq_len
    
    def __getitem__(self, idx):
        return self.X[idx:idx+self.seq_len], self.y[idx+self.seq_len]

def generate_synthetic_data(n_samples=50000):
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n_samples, freq='1min')
    prices = 50000 + np.cumsum(np.random.randn(n_samples) * 100)
    volumes = np.random.rand(n_samples) * 1000 + 500
    rsi = np.random.rand(n_samples) * 100
    macd = np.random.randn(n_samples) * 2
    future_returns = np.roll(prices, -60) / prices - 1
    labels = (future_returns > 0).astype(int)
    labels[-60:] = 0
    return pd.DataFrame({
        'timestamp': dates, 'close': prices, 'volume': volumes,
        'rsi': rsi, 'macd': macd, 'label': labels
    })

def preprocess(df, feature_cols, label_col, seq_len=60, train_ratio=0.8):
    """
    预处理数据（防止数据泄漏版本）
    
    重要改进：
    1. Scaler 只在训练集上 fit
    2. 返回训练好的 scaler 用于后续 transform
    """
    X = df[feature_cols].values.astype(np.float32)
    y = df[label_col].values.astype(np.int64)
    
    split = int(len(X) * train_ratio)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train).astype(np.float32)
    X_test_scaled = scaler.transform(X_test).astype(np.float32)
    
    X_scaled = np.concatenate([X_train_scaled, X_test_scaled], axis=0)
    
    train_ds = TimeSeriesDataset(X_scaled[:split], y[:split], seq_len)
    test_ds = TimeSeriesDataset(X_scaled[split:], y[split:], seq_len)
    
    return DataLoader(train_ds, batch_size=256, shuffle=False), \
           DataLoader(test_ds, batch_size=256, shuffle=False), scaler
