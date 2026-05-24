"""
Domain Package - 纯交易规则与语义

核心原则：Domain 只包含"交易语义和规则"，不包含：
- Runtime 编排逻辑 → runtime/
- Infrastructure 实现 → infrastructure/
- Data Pipeline / ML → services/
- Application Workflow → application/

包含：
- feature.indicators: 市场行为检测器
- event: 领域事件类型
- execution: 执行域模型与规则
- feature: 特征定义与纯数学计算
- portfolio: 组合域模型
- replay: 回放数学公式（slippage, fee, funding 等）
- risk: 风险规则
- signal: 信号模型与融合
- strategy: 策略配置定义
- trading_mode: 交易模式定义
- analysis: 分析类型定义
"""

__all__ = []
