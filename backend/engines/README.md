# Engines — 无状态计算与外部 IO 适配器

`engines/` 是无状态计算和外部 IO 适配器的目的地。

## 允许

- 纯计算（纯函数、确定性输出）
- 向量化 / GPU 计算
- exchange / websocket / Kafka / storage / database 适配器
- 无状态辅助代码（不持有可变运行时状态）

## 禁止

- replay cursor
- pending orders
- positions
- feature availability
- signal sequence / cooldown
- 可变运行时状态

## 迁移规则

1. 如果模块持有可变交易状态，先将状态移到 `runtime/`
2. 只提取无状态计算或 IO 适配器到 `engines/`
3. Runtime 调用 Engine；Engine 永不调用 Runtime
4. 对 Runtime 访问的任何状态添加所有权检查

## 当前目录结构

```
engines/
├── adapters/              # 外部 IO 适配器
│   ├── data/              # 数据采集适配器
│   │   ├── collectors/    # 各类数据采集器（新闻、社交媒体、OI、ETF 等）
│   │   ├── feeds/         # 数据源适配器（Cryptopanic、Twitter、QQ 等）
│   │   └── sources/       # 实时数据源（QQ、Telegram）
│   └── exchange/          # 交易所适配器（Binance、OKX、Mock、Paper Trading）
├── compute/               # 无状态纯计算（详见 compute/README.md）
│   ├── aggregation/       # K 线聚合与事件分组
│   ├── context/           # MarketContext 构建与校验
│   ├── correlation/       # 相关性计算
│   ├── feature/           # 特征计算与特征矩阵
│   ├── risk/              # 风险计算与检查器
│   ├── scoring/           # LLM 打分
│   ├── signal/            # 信号融合与打分
│   ├── strategy/          # 策略计算器（纯计算）
│   ├── strategy_v2/       # 策略 V2（MarketContext 驱动）
│   └── trade_flow/        # 交易流计算
├── execution/             # 执行引擎与订单/仓位管理
├── ingestion/             # 数据摄入管道
├── ml/                    # 机器学习计算（LSTM）
├── narrative/             # 叙事引擎
├── optimization/          # 参数优化与回测 Worker
├── replay/                # 回放引擎
│   ├── kernel_replay/     # 内核回放（事件日志、快照、确定性校验）
│   └── realism/           # 现实模拟（手续费、滑点、延迟、爆仓）
└── strategy/              # 策略注册表
```

## 架构依赖方向

```
domain/   → 定义领域模型、事件、核心业务概念
  ↑
engines/  → 实现无状态计算逻辑和 IO 适配器
  ↑
runtime/  → 持有可变状态，编排引擎调用
```

Engine 只依赖 `domain/`，不依赖 `runtime/`。
