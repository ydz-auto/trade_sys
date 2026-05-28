## Infrastructure 层

- [ ] RawTradeReader.load_month() 按月读取 trade parquet
- [ ] RawTradeReader.list_available_months() 列出可用月份
- [ ] RawTradeReader.load_month_range() 按月迭代避免 OOM
- [ ] TradeFlowWriter.save() 写入 ZSTD 压缩 parquet
- [ ] TradeFlowWriter.load() 读取物化结果，支持时间范围过滤
- [ ] TradeFlowWriter.get_last_timestamp() 返回已有数据最后时间戳
- [ ] 输出路径 data_lake/crypto/{exchange}/trade_flow/symbol={symbol}/timeframe={tf}/data.parquet

## Engine 层

- [ ] TradeFlowEngine.aggregate() 使用 pandas vectorized resample+agg
- [ ] _aggregate_single_month() 是模块级函数（可被 pickle）
- [ ] 输出特征列与 TradeFeature dataclass 完全对齐
- [ ] 包含 buy/sell_volume, taker_buy_ratio, trade_imbalance, trade_delta, cvd/cvd_zscore
- [ ] 包含 large_trade, whale_buy/sell, pressure_score, sweep_score, liquidity_vacuum
- [ ] 包含 spread_estimate, imbalance_1/10/slope

## Runtime 层

- [ ] TradeFlowMaterializationPipeline.run() 编排完整物化流程
- [ ] 使用 CPUExecutor(executor_type="process") 按月并行聚合
- [ ] 增量更新：跳过已聚合月份
- [ ] 合并去重排序逻辑正确

## Application 层

- [ ] CLI 入口 python -m application.commands.materialize_trade_flow_command 可用
- [ ] CLI 支持 --exchange/--symbols/--timeframe/--start/--end/--force 参数
- [ ] scripts/offline_trade_flow.py 已删除

## 数据验证

- [ ] 4 个标的（BTC/SOL/ETC/ZEC）1h trade_flow parquet 已生成
- [ ] feature_matrix.py 优先从 TradeFlowWriter.load() 读取
- [ ] feature_matrix.py exclude_sources=["oi","liquidation","orderbook"] 时 OI 列为 NaN
- [ ] feature_matrix.py exclude_sources 生效时，order_flow 特征列有数据（非全 NaN）

## Alpha Pipeline 适配

- [ ] feature_availability_audit.py --exclude-sources 参数正常工作
- [ ] ic_analysis.py --families 参数正常工作
- [ ] ic_analysis.py --exclude-sources 参数传递给 build_feature_matrix
- [ ] pipeline.py --exclude-sources 参数传递给 build_feature_matrix
- [ ] pipeline.py --start / --end 参数支持 OOS 时间范围
- [ ] leaderboard.csv 包含 stage_passed 和 fail_reason 字段

## Alpha 验证结果

- [ ] Feature Audit 输出 READY 特征不含 open_interest / liquidity family
- [ ] IC Analysis 筛选出 abs(rank_ic) > 0.02 且 p < 0.05 的 feature
- [ ] Leaderboard 包含 4 个标的的结果
- [ ] OOS 2026 验证结果独立于训练集
- [ ] final_candidates.csv 满足决策标准（PF>1.1, Sharpe>1, trades>=100, 2+ symbol 有效）
