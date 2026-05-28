# 离线 Trade Flow 物化 + 无 OI Alpha 验证流水线

## Why

原始 Trade 数据量巨大（BTC 单月 1.27 亿行 / 1.2GB，全量 69GB），直接在 feature_matrix 构建时加载会导致 OOM 崩溃。需要先离线聚合成轻量 trade flow 特征，再供 Alpha Pipeline 使用。同时本轮验证排除 OI / Liquidation / Orderbook 数据源，只使用 Kline + Funding + Trades 三类数据。

Trade Flow 物化是核心系统能力，应进入正式分层：`application.commands` → `runtime.pipeline` → `engines.compute.feature` → `infrastructure.storage`。

## What Changes

### 新增文件

- `application/commands/materialize_trade_flow_command.py`：CLI 命令入口
- `runtime/pipeline/trade_flow_materialization_pipeline.py`：离线物化流水线（按月并行编排、增量判断）
- `engines/compute/feature/trade_flow_engine.py`：Trade Flow 特征计算引擎（使用 CPUExecutor 多进程）
- `infrastructure/storage/data_lake/raw_trade_reader.py`：原始 trade 数据读取（按月分片读取，避免 OOM）
- `infrastructure/storage/data_lake/trade_flow_writer.py`：Trade Flow parquet 写入（ZSTD 压缩）

### 修改文件

- `research/alpha/feature_matrix.py`：`build_feature_matrix` 增加 `exclude_sources` 参数；优先从物化后的 trade_flow 读取
- `research/alpha/feature_availability_audit.py`：`run_availability_audit` 增加 `exclude_sources` 参数（已完成基础版）
- `research/alpha/ic_analysis.py`：CLI 增加 `--families` 参数（已完成基础版），增加 `--exclude-sources`
- `research/alpha/pipeline.py`：增加 `--exclude-sources` / `--start` / `--end` 参数
- `research/alpha/leaderboard.py`：增加 `stage_passed` / `fail_reason` 字段

### 删除文件

- `scripts/offline_trade_flow.py`：临时脚本，已被正式模块替代

## Impact

- Affected specs: Alpha Pipeline, Feature Matrix, Data Lake, Feature Materialization, Runtime Pipeline
- Affected code:
  - `application/commands/materialize_trade_flow_command.py`（新建）
  - `runtime/pipeline/trade_flow_materialization_pipeline.py`（新建）
  - `engines/compute/feature/trade_flow_engine.py`（新建）
  - `infrastructure/storage/data_lake/raw_trade_reader.py`（新建）
  - `infrastructure/storage/data_lake/trade_flow_writer.py`（新建）
  - `research/alpha/feature_matrix.py`
  - `research/alpha/feature_availability_audit.py`
  - `research/alpha/ic_analysis.py`
  - `research/alpha/pipeline.py`
  - `research/alpha/leaderboard.py`

---

## ADDED Requirements

### Requirement: 原始 Trade 数据读取器

系统 SHALL 提供 `RawTradeReader`，负责从数据湖按月分片读取原始 trade 数据。

- 位于 `infrastructure/storage/data_lake/raw_trade_reader.py`
- 继承/复用 `FileDataLakeReader` 的路径解析逻辑
- `load_month(exchange, symbol, year, month) -> pd.DataFrame`：读取单月 trade parquet
- `list_available_months(exchange, symbol) -> List[Tuple[int, int]]`：列出所有可用月份
- `load_month_range(exchange, symbol, start_year, start_month, end_year, end_month) -> Iterator[pd.DataFrame]`：按月迭代读取，避免全量加载

#### Scenario: 按月读取
- **WHEN** 调用 `RawTradeReader.load_month("binance", "BTCUSDT", 2025, 1)`
- **THEN** 返回 2025 年 1 月的 trade DataFrame
- **AND** 如果该月文件不存在，返回空 DataFrame

### Requirement: Trade Flow 写入器

系统 SHALL 提供 `TradeFlowWriter`，负责将物化后的 trade flow 写入 parquet。

- 位于 `infrastructure/storage/data_lake/trade_flow_writer.py`
- 输出路径：`data_lake/crypto/{exchange}/trade_flow/symbol={symbol}/timeframe={tf}/data.parquet`
- `save(exchange, symbol, timeframe, df) -> Path`：写入 parquet（ZSTD 压缩）
- `load(exchange, symbol, timeframe, start_ts=None, end_ts=None) -> pd.DataFrame`：读取物化结果
- `get_last_timestamp(exchange, symbol, timeframe) -> Optional[pd.Timestamp]`：获取已有数据的最后时间戳（用于增量判断）

#### Scenario: 增量写入
- **WHEN** 调用 `TradeFlowWriter.save("binance", "BTCUSDT", "1h", df)`
- **THEN** 写入到 `data_lake/crypto/binance/trade_flow/symbol=BTCUSDT/timeframe=1h/data.parquet`
- **AND** 使用 ZSTD 压缩

### Requirement: Trade Flow 聚合引擎

系统 SHALL 提供 `TradeFlowEngine`，将原始 trade 数据预聚合为多时间维度的 trade flow 特征。

- 位于 `engines/compute/feature/trade_flow_engine.py`
- 核心方法 `aggregate(trades_df, timeframe) -> pd.DataFrame`：单月聚合计算
- 使用 pandas vectorized 实现（避免逐行遍历 1.2 亿行）
- 输出特征列与 `domain/feature/trade/trade_feature.py` 中 `TradeFeature` 对齐：
  - 基础量：buy_volume, sell_volume, total_volume, buy_quote, sell_quote, total_quote
  - 交易统计：num_trades, avg_trade_size, max_trade_size
  - 买卖失衡：taker_buy_ratio, buy_sell_ratio, trade_imbalance, trade_delta
  - 累积流：cumulative_delta, cvd, cvd_delta, cvd_zscore
  - 大单：large_trade_volume, large_trade_ratio, whale_buy/sell_volume/count
  - 速度：trade_velocity
  - 压力评分：trade_pressure_score, long/short_pressure_score, squeeze/flush_pressure_score
  - 扫单：sweep_buy/sell_score
  - 流动性：liquidity_vacuum
  - 价差估计：spread_estimate, spread_pct_estimate
  - 失衡滚动：imbalance_1, imbalance_10, imbalance_slope
- `_aggregate_single_month()` 作为模块级函数（可被 pickle），由 CPUExecutor 调用

#### Scenario: 单月聚合
- **WHEN** 调用 `TradeFlowEngine.aggregate(trades_df, "1h")`
- **THEN** 返回按 1h 重采样后的 trade flow 特征 DataFrame
- **AND** 特征列与 `TradeFeature` dataclass 完全对齐

### Requirement: Trade Flow 物化流水线

系统 SHALL 提供 `TradeFlowMaterializationPipeline`，编排离线物化流程。

- 位于 `runtime/pipeline/trade_flow_materialization_pipeline.py`
- 核心方法 `run(symbol, exchange, timeframe, start, end, force) -> Path`
- 编排逻辑：
  1. 通过 `RawTradeReader.list_available_months()` 获取可用月份
  2. 通过 `TradeFlowWriter.get_last_timestamp()` 检查已有数据（增量判断）
  3. 过滤出需要聚合的月份
  4. 使用 `CPUExecutor(executor_type="process")` 按月并行调用 `TradeFlowEngine._aggregate_single_month()`
  5. 合并所有月份结果，去重排序
  6. 通过 `TradeFlowWriter.save()` 写入

#### Scenario: 多进程加速聚合
- **WHEN** 调用 `pipeline.run(symbol="BTCUSDT", timeframe="1h")`
- **THEN** 流水线使用 `CPUExecutor` 按 month 并行聚合 trade 数据
- **AND** 每个 worker 独立加载一个月的 parquet，执行聚合，返回 DataFrame
- **AND** 主进程合并所有月份结果，去重排序后写入 parquet

#### Scenario: 增量更新
- **WHEN** 输出 parquet 已存在
- **THEN** 流水线检查已有数据的最后时间戳，只聚合新增月份

### Requirement: Trade Flow 物化命令

系统 SHALL 提供 CLI 命令入口 `python -m application.commands.materialize_trade_flow_command`。

- 位于 `application/commands/materialize_trade_flow_command.py`
- 参数：`--exchange`, `--symbols`, `--timeframe`, `--start`, `--end`, `--force`
- 调用 `TradeFlowMaterializationPipeline.run()` 执行聚合
- 输出进度信息

#### Scenario: CLI 物化
- **WHEN** 运行 `python -m application.commands.materialize_trade_flow_command --symbols BTCUSDT --timeframe 1h`
- **THEN** 系统执行离线聚合，输出到 `data_lake/crypto/binance/trade_flow/symbol=BTCUSDT/timeframe=1h/data.parquet`

### Requirement: Feature Matrix 使用预聚合 Trade Flow

系统 SHALL 在构建 feature_matrix 时优先从物化后的 trade_flow 读取，而非直接加载原始 trades。

- `build_feature_matrix` 增加 `exclude_sources: Optional[List[str]]` 参数
- 当 `exclude_sources` 包含 "oi" 时，跳过 OI 数据加载和 OI 相关特征计算
- 当 `exclude_sources` 包含 "liquidation" 时，跳过 liquidation 特征
- 当 `exclude_sources` 包含 "orderbook" 时，跳过 orderbook 特征
- 优先从 `TradeFlowWriter.load()` 读取物化结果
- 如果物化文件不存在，回退到原始 trades（带时间范围限制，避免 OOM）

#### Scenario: 无 OI 构建 feature matrix
- **WHEN** 调用 `build_feature_matrix(symbol="BTCUSDT", exclude_sources=["oi", "liquidation", "orderbook"])`
- **THEN** 系统不加载 OI / Liquidation / Orderbook 数据
- **AND** OI 相关特征列填充为 NaN
- **AND** 从物化 trade_flow 读取 order flow 特征

### Requirement: Alpha Pipeline 支持 exclude-sources 和时间范围

系统 SHALL 在 Alpha Pipeline CLI 中支持 `--exclude-sources` 和 `--start` / `--end` 参数。

- `--exclude-sources oi,liquidation,orderbook`：排除指定数据源
- `--start 2026-01-01`：指定开始日期（用于 OOS 验证）
- `--end 2026-05-28`：指定结束日期
- Leaderboard 输出增加 `stage_passed` 和 `fail_reason` 字段

#### Scenario: OOS 验证
- **WHEN** 运行 `python -m research.alpha.pipeline --start 2026-01-01 --end 2026-05-28 --exclude-sources oi,liquidation,orderbook`
- **THEN** 系统只使用指定时间范围内的数据
- **AND** 排除 OI / Liquidation / Orderbook 数据源

### Requirement: IC Analysis 支持多 Family 扫描

系统 SHALL 在 IC Analysis CLI 中支持 `--families` 参数，逗号分隔多个 Alpha Family。

- `--families price_action,volatility,volume,funding,order_flow,short_exhaustion`
- 合并所有指定 family 的 features 进行 IC 计算
- 增加 `--exclude-sources` 参数，传递给 `build_feature_matrix`

#### Scenario: 多 Family IC 扫描
- **WHEN** 运行 `python -m research.alpha.ic_analysis --families price_action,volatility,funding --exclude-sources oi,liquidation,orderbook`
- **THEN** 系统合并这三个 family 的所有 features 进行 IC 分析
- **AND** feature_matrix 构建时排除 OI / Liquidation / Orderbook

---

## MODIFIED Requirements

### Requirement: Feature Availability Audit 排除数据源

`run_availability_audit` 增加 `exclude_sources` 参数，被排除的数据源标记为不可用。

- `check_data_source_availability` 增加 `exclude_sources` 参数
- CLI 增加 `--exclude-sources` 参数
- 被排除的数据源对应的 feature 状态应为 `DATA_MISSING`

### Requirement: Feature Matrix Trade Flow 读取

`_fallback_build` 修改为优先从物化 trade_flow 读取：

1. 通过 `TradeFlowWriter.load()` 检查物化文件
2. 如果存在且非空，直接读取并 merge
3. 如果不存在，回退到原始 trades（带时间范围限制，避免 OOM）

---

## REMOVED Requirements

### Requirement: 临时脚本 offline_trade_flow.py

**Reason**: Trade Flow 物化是核心系统能力，不应放在 scripts/ 临时目录
**Migration**: 已由正式分层替代：
- `application/commands/materialize_trade_flow_command.py`（命令入口）
- `runtime/pipeline/trade_flow_materialization_pipeline.py`（离线物化流水线）
- `engines/compute/feature/trade_flow_engine.py`（特征计算引擎）
- `infrastructure/storage/data_lake/raw_trade_reader.py`（原始数据读取）
- `infrastructure/storage/data_lake/trade_flow_writer.py`（物化结果写入）
