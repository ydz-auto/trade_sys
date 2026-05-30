"""
Alpha Research Factory

Feature -> Label -> IC -> Regime -> Strategy

重构后的模块结构:
- features/: 特征计算和管理
- ic/: IC 分析
- signals/: 信号生成
- registry/: 注册中心
- validation/: 验证
- reporting/: 报告

迁移的文件：
- feature_matrix.py -> features/matrix.py
- feature_availability_audit.py -> features/availability.py
- data_quality_check.py -> features/quality.py
- features_short/ -> features/short_features.py
- ic_analysis.py -> ic/analysis.py
- alpha_signal_strategy.py -> signals/alpha_signal_strategy.py
- strategy_alpha_registry.py -> registry/alpha_registry.py
- pipeline.py -> validation/pipeline.py
- leaderboard.py -> reporting/leaderboard.py
- per_symbol_leaderboard.py -> reporting/per_symbol.py
- paper_trading_config.py -> reporting/paper_config.py
- alpha_factory_status.py -> reporting/status.py

向后兼容：
- 所有旧文件仍然可用（通过兼容层）
- 建议使用新的子模块结构
"""

from research.alpha.labels import compute_labels, compute_labels_from_df
from research.alpha.regime_analysis import classify_regime

__all__ = [
    "compute_labels",
    "compute_labels_from_df",
    "classify_regime",
]
