"""
Replay Domain - 回放真实性领域

这个模块包含回测真实性核心模型，用于确保回测结果可信。

包含：
- slippage: 滑点模型
- latency: 延迟模型
- partial_fill: 部分成交模型
- fee_model: 手续费模型
- funding: 资金费率模型
- liquidation: 爆仓模型

这是核心领域模型，不包含：
- 基础设施（使用 infrastructure/replay/）
- 运行时编排（使用 runtime/replay_runtime/）
- 回放管理服务（使用 shared/replay/）
"""
