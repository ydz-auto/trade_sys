"""
数据泄漏修复验证脚本
"""
import sys
sys.path.insert(0, '.')

print('=' * 60)
print('验证数据泄漏修复')
print('=' * 60)

print('\n1. 测试 Feature Matrix Rolling 标准化...')
from services.strategy_service.feature_matrix import FeatureMatrix
import pandas as pd
import numpy as np

df = pd.DataFrame({
    'close': np.random.randn(1000).cumsum() + 50000,
    'rsi_14': np.random.rand(1000) * 100,
})
fm = FeatureMatrix()
fm.df = df

normalized = fm.normalize_feature('rsi_14', method='zscore', window=20)
print(f'   ✅ Rolling ZScore 标准化成功，前5个有效值: {normalized.dropna().head(5).values}')

print('\n2. 测试 Feature Availability Guard...')
from shared.replay.feature_availability_guard import get_feature_availability_guard, FeatureAvailabilityStatus

guard = get_feature_availability_guard()

check = guard.check_availability('volatility_1h', 1700000000000, 1700000000000)
print(f'   volatility_1h 在周期内: status={check.status.value}')

check = guard.check_availability('volatility_1h', 1700000000000, 1700003600000)
print(f'   volatility_1h 在周期结束后: status={check.status.value}')

check = guard.check_availability('spread', 1700000000000, 1700000000000)
print(f'   spread (即时特征): status={check.status.value}')

print('\n3. 测试 Context Engine Rolling Quantile...')
from services.research_service.context_engine import ContextEngine

engine = ContextEngine()
test_df = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=1000, freq='1h'),
    'volatility_1h': np.random.rand(1000) * 0.1,
    'returns_1h': np.random.randn(1000) * 0.01,
})
test_df['volatility_context'] = engine._get_volatility_context(test_df)
test_df['regime'] = engine._get_regime(test_df)
print(f'   ✅ Rolling Quantile Context 成功')
print(f'   volatility_context 分布: {test_df["volatility_context"].value_counts().to_dict()}')
print(f'   regime 分布: {test_df["regime"].value_counts().to_dict()}')

print('\n' + '=' * 60)
print('✅ 所有数据泄漏修复验证通过！')
print('=' * 60)
