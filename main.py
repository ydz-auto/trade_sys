from models import LSTMClassifier
from data_loader import generate_synthetic_data, preprocess
from trainer import LSTMTrainer
from backtester import Backtester, generate_signals

print("="*50)
print("LSTM 训练和回测系统")
print("="*50)

print("\n1. 生成数据...")
df = generate_synthetic_data(n_samples=50000)
print(f"数据样本: {len(df):,}")

print("\n2. 预处理数据...")
train_loader, test_loader, _ = preprocess(df, ['close', 'volume', 'rsi', 'macd'], 'label', seq_len=60)
print(f"训练样本: {len(train_loader.dataset):,}")
print(f"测试样本: {len(test_loader.dataset):,}")

print("\n3. 创建模型...")
model = LSTMClassifier(input_size=4, hidden_size=64, num_layers=1)
print("模型: LSTM分类器 (64单元, 1层)")

print("\n4. 训练模型...")
trainer = LSTMTrainer()
model = trainer.train(model, train_loader, test_loader, epochs=10)

print("\n5. 生成预测...")
predictions = trainer.predict(model, test_loader)
print(f"预测样本: {len(predictions)}")

print("\n6. 生成交易信号...")
signals = generate_signals(predictions, threshold=0.6)
print(f"多头信号: {(signals == 1).sum()}")
print(f"空头信号: {(signals == -1).sum()}")

print("\n7. 回测...")
test_prices = df['close'].values[-len(predictions):]
backtester = Backtester(initial_capital=100000, transaction_cost=0.001)
metrics = backtester.run(signals, test_prices)
backtester.print_report(metrics)

print("\n8. 保存结果...")
import pandas as pd
pd.DataFrame({'prediction': predictions[:, 1], 'signal': signals}).to_csv('results.csv', index=False)
print("结果已保存到 results.csv")
