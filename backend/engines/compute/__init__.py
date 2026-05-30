"""无状态纯计算层。

engines/compute/ 是项目的无状态纯计算层，所有函数必须是确定性的、无副作用的。

架构边界：
  domain/ → engines/compute/ → runtime/
  compute 只依赖 domain，永不调用 runtime。

子目录：
  aggregation/    K 线聚合与事件分组
  context/        MarketContext 构建与校验
  correlation/    相关性计算
  feature/        特征计算与特征矩阵
  risk/           风险计算与检查器
  scoring/        LLM 打分
  signal/         信号融合与打分
  strategy/       策略计算器（纯计算）
  strategy_v2/    策略 V2（MarketContext 驱动）
  trade_flow/     交易流计算

严格禁止：
  - 有状态对象（self._prev_* 等可变状态）
  - 跨层调用 runtime
  - 副作用 / IO
  - 全局单例

已完成的迁移：
  - models/ 已删除，数据模型由 domain/ 统一定义
  - schemas/ 已迁移到 domain/
  - kline_loader / funding_loader 已迁移到 infrastructure/repositories/
"""

__all__: list[str] = []
