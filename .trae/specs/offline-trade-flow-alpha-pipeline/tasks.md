# Tasks

## Phase 1: Infrastructure 层 - 数据读写

- [ ] Task 1: 创建 `infrastructure/storage/data_lake/raw_trade_reader.py`
  - [ ] 1.1: `RawTradeReader` 类，复用 `FileDataLakeReader` 路径解析
  - [ ] 1.2: `load_month(exchange, symbol, year, month) -> pd.DataFrame`
  - [ ] 1.3: `list_available_months(exchange, symbol) -> List[Tuple[int, int]]`
  - [ ] 1.4: `load_month_range(...) -> Iterator[pd.DataFrame]`，按月迭代避免 OOM

- [ ] Task 2: 创建 `infrastructure/storage/data_lake/trade_flow_writer.py`
  - [ ] 2.1: `TradeFlowWriter` 类
  - [ ] 2.2: `save(exchange, symbol, timeframe, df) -> Path`，ZSTD 压缩
  - [ ] 2.3: `load(exchange, symbol, timeframe, start_ts, end_ts) -> pd.DataFrame`
  - [ ] 2.4: `get_last_timestamp(exchange, symbol, timeframe) -> Optional[pd.Timestamp]`
  - [ ] 2.5: 输出路径 `data_lake/crypto/{exchange}/trade_flow/symbol={symbol}/timeframe={tf}/data.parquet`

## Phase 2: Engine 层 - 特征计算

- [ ] Task 3: 创建 `engines/compute/feature/trade_flow_engine.py`
  - [ ] 3.1: `TradeFlowEngine` 类，核心方法 `aggregate(trades_df, timeframe) -> pd.DataFrame`
  - [ ] 3.2: pandas vectorized 实现（resample + agg），避免逐行遍历
  - [ ] 3.3: 输出特征列与 `domain/feature/trade/trade_feature.py` 的 `TradeFeature` 对齐
  - [ ] 3.4: `_aggregate_single_month()` 模块级函数（可被 pickle），由 CPUExecutor 调用
  - [ ] 3.5: 包含：buy/sell_volume, taker_buy_ratio, trade_imbalance, trade_delta, cvd/cvd_zscore, large_trade, whale, pressure_score, sweep_score, liquidity_vacuum, spread_estimate, imbalance_rolling

## Phase 3: Runtime 层 - 物化流水线

- [ ] Task 4: 创建 `runtime/pipeline/trade_flow_materialization_pipeline.py`
  - [ ] 4.1: `TradeFlowMaterializationPipeline` 类，核心方法 `run(symbol, exchange, timeframe, start, end, force) -> Path`
  - [ ] 4.2: 编排逻辑：RawTradeReader → 增量判断 → CPUExecutor 并行聚合 → 合并 → TradeFlowWriter.save
  - [ ] 4.3: 使用 `CPUExecutor(executor_type="process")` 按月并行调用 `_aggregate_single_month()`
  - [ ] 4.4: 增量更新：通过 `TradeFlowWriter.get_last_timestamp()` 跳过已聚合月份
  - [ ] 4.5: 合并去重排序逻辑

## Phase 4: Application 层 - 命令入口

- [ ] Task 5: 创建 `application/commands/materialize_trade_flow_command.py`
  - [ ] 5.1: CLI 入口 `python -m application.commands.materialize_trade_flow_command`
  - [ ] 5.2: 参数：`--exchange`, `--symbols`, `--timeframe`, `--start`, `--end`, `--force`
  - [ ] 5.3: 调用 `TradeFlowMaterializationPipeline.run()`
  - [ ] 5.4: 进度输出

- [ ] Task 6: 删除临时脚本 `scripts/offline_trade_flow.py`

- [ ] Task 7: 对 4 个标的运行离线聚合（1h 维度）
  - [ ] 7.1: BTCUSDT 1h 聚合
  - [ ] 7.2: SOLUSDT 1h 聚合
  - [ ] 7.3: ETCUSDT 1h 聚合
  - [ ] 7.4: ZECUSDT 1h 聚合
  - [ ] 7.5: 验证输出文件大小和行数合理

## Phase 5: Feature Matrix 适配

- [ ] Task 8: 修改 `feature_matrix.py`，优先读取物化 trade_flow
  - [ ] 8.1: `_fallback_build` 中通过 `TradeFlowWriter.load()` 读取物化数据
  - [ ] 8.2: 当物化文件存在时直接 merge，不存在时回退到原始 trades（带时间范围限制）
  - [ ] 8.3: `build_feature_matrix_from_df` 中根据 `exclude_sources` 跳过 OI/Liquidation/Orderbook 相关特征计算
  - [ ] 8.4: 确保 `_merge_trades` 在有物化数据时直接使用

- [ ] Task 9: 验证 feature_matrix 构建（无 OI + trade_flow）
  - [ ] 9.1: 测试 `build_feature_matrix(symbol="BTCUSDT", days=365, timeframe="1h", exclude_sources=["oi","liquidation","orderbook"])`
  - [ ] 9.2: 确认 order_flow 特征列有数据（非全 NaN）
  - [ ] 9.3: 确认 OI 相关列为 NaN

## Phase 6: Alpha Pipeline 适配

- [ ] Task 10: 完善 `feature_availability_audit.py` exclude_sources 支持
  - [ ] 10.1: 已完成基础 `--exclude-sources` 参数（需验证）
  - [ ] 10.2: 被排除数据源对应的 feature 状态标记为 `DATA_MISSING`

- [ ] Task 11: 完善 `ic_analysis.py` 参数支持
  - [ ] 11.1: 已完成基础 `--families` 参数（需验证）
  - [ ] 11.2: 添加 `--exclude-sources` 参数，传递给 `build_feature_matrix`

- [ ] Task 12: 修改 `pipeline.py`，增加 `--exclude-sources` / `--start` / `--end`
  - [ ] 12.1: CLI 添加 `--exclude-sources` 参数
  - [ ] 12.2: CLI 添加 `--start` / `--end` 参数
  - [ ] 12.3: `AlphaPipeline.__init__` 增加 `exclude_sources` / `start_date` / `end_date`
  - [ ] 12.4: `_run_single` 中使用 `exclude_sources` 和时间范围

- [ ] Task 13: 修改 `leaderboard.py`，增加 `stage_passed` / `fail_reason` 字段
  - [ ] 13.1: Leaderboard CSV 输出增加 `stage_passed` 和 `fail_reason` 列
  - [ ] 13.2: 从 `AlphaValidationResult.stages` 提取通过/失败信息

## Phase 7: 运行无 OI Alpha 验证流程

- [ ] Task 14: Step 1 - Feature Availability Audit
  - [ ] 14.1: 运行 `feature_availability_audit --symbol BTCUSDT --timeframe 1h --days 365 --exclude-sources oi,liquidation,orderbook`
  - [ ] 14.2: 输出到 `reports/alpha/no_oi/feature_audit_BTCUSDT_1h_365d.csv`
  - [ ] 14.3: 确认 READY 特征只来自 price_action / volatility / volume / funding / order_flow / short_exhaustion

- [ ] Task 15: Step 2-3 - IC Analysis
  - [ ] 15.1: 运行 `ic_analysis --symbol BTCUSDT --timeframe 1h --days 365 --families price_action,volatility,volume,funding,order_flow,short_exhaustion --exclude-sources oi,liquidation,orderbook`
  - [ ] 15.2: 输出到 `reports/alpha/no_oi/ic_BTCUSDT_1h_365d.csv`
  - [ ] 15.3: 筛选 abs(rank_ic) > 0.02 且 rank_p_value < 0.05 且 sample_count > 1000

- [ ] Task 16: Step 4-7 - Pipeline + Leaderboard
  - [ ] 16.1: 运行 `pipeline --symbols BTCUSDT,ETCUSDT,SOLUSDT,ZECUSDT --timeframe 1h --days 365 --exclude-sources oi,liquidation,orderbook --fee-mode maker`
  - [ ] 16.2: 输出 leaderboard 到 `reports/alpha/no_oi/leaderboard.csv`

- [ ] Task 17: Step 8 - OOS 2026 验证
  - [ ] 17.1: 运行 `pipeline --symbols BTCUSDT,ETCUSDT,SOLUSDT,ZECUSDT --timeframe 1h --start 2026-01-01 --end 2026-05-28 --exclude-sources oi,liquidation,orderbook --fee-mode maker`
  - [ ] 17.2: 输出到 `reports/alpha/no_oi/oos_2026.csv`

- [ ] Task 18: 生成 final_candidates.csv
  - [ ] 18.1: 合并 leaderboard + oos_2026，按决策标准筛选
  - [ ] 18.2: 筛选条件：PF > 1.1, Sharpe > 1, trades >= 100, 至少 2 个 symbol 有效, 2026 OOS 不失效
  - [ ] 18.3: 输出到 `reports/alpha/no_oi/final_candidates.csv`

# Task Dependencies

- Task 2 depends on Task 1 (writer 可独立于 reader，但逻辑上 reader 先)
- Task 3 depends on Task 1 (engine 需要 reader 接口定义)
- Task 4 depends on Task 1, Task 2, Task 3 (pipeline 编排所有层)
- Task 5 depends on Task 4 (command 调用 pipeline)
- Task 6 depends on Task 5 (删除旧脚本前新系统需就绪)
- Task 7 depends on Task 5 (运行新命令)
- Task 8 depends on Task 2 (feature_matrix 使用 writer.load)
- Task 9 depends on Task 7, Task 8
- Task 14 depends on Task 9, Task 10
- Task 15 depends on Task 14, Task 11
- Task 16 depends on Task 15, Task 12, Task 13
- Task 17 depends on Task 16
- Task 18 depends on Task 17

# Parallelizable Work

- Task 1 + Task 2 可并行（reader 和 writer 互不依赖）
- Task 3 可与 Task 2 并行（engine 只需 reader 接口定义）
- Task 10 / Task 11 / Task 12 / Task 13 可与 Phase 1-4 并行（Pipeline 适配与物化系统互不依赖）
