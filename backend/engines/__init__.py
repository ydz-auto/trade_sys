"""无状态计算与外部 IO 适配器。

engines/ 是无状态计算和外部 IO 适配器的目的地。

允许：
  - 纯计算（纯函数、确定性输出）
  - 向量化 / GPU 计算
  - exchange / websocket / Kafka / storage / database 适配器
  - 无状态辅助代码

禁止：
  - replay cursor、pending orders、positions
  - feature availability、signal sequence/cooldown
  - 可变运行时状态

迁移规则：
  - 持有可变交易状态的模块先移到 runtime/
  - 只提取无状态计算或 IO 适配器到 engines/
  - Runtime 调用 Engine；Engine 永不调用 Runtime

子目录：
  adapters/      外部 IO 适配器（数据采集、交易所）
  compute/       无状态纯计算（详见 compute/README.md）
  execution/     执行引擎与订单/仓位管理
  ingestion/     数据摄入管道
  ml/            机器学习计算
  narrative/     叙事引擎
  optimization/  参数优化与回测 Worker
  replay/        回放引擎（内核回放、现实模拟）
  strategy/      策略注册表
"""

__all__: list[str] = []
