## 基础设施层 - 内存优化

- [x] MemoryOptimizer.downcast_float() 将 float64 降级为 float32
- [x] MemoryOptimizer.downcast_int() 将 int64 降级为 int32/int8
- [x] MemoryOptimizer.optimize_dtypes() 自动检测并降级所有可优化列
- [x] MemoryOptimizer.release_columns() 删除指定列并触发 gc.collect()
- [x] MemoryOptimizer.estimate_dataframe_memory() 返回 DataFrame 内存估算
- [x] MemoryOptimizer.read_parquet_batch() 分批读取 Parquet，按 row group 迭代
- [x] MemoryOptimizer.write_parquet_batch() 分批写入 Parquet

## 基础设施层 - 资源调度

- [x] DeviceManager.get_system_memory() 返回系统总物理内存
- [x] DeviceManager.get_available_memory() 返回当前可用内存
- [x] DeviceInfo 包含 system_memory_gb 字段
- [x] TaskProfile dataclass 包含 estimated_rows_per_task / estimated_columns / dtype_size / cpu_intensive
- [x] ExecutionPlan dataclass 包含 max_workers / use_gpu / batch_size / executor_type / memory_budget_per_worker
- [x] ResourceScheduler.estimate_memory_per_worker() 正确估算单 worker 内存
- [x] ResourceScheduler.compute_max_workers() 根据 CPU 核心和内存约束计算 max_workers
- [x] ResourceScheduler.plan_execution() 返回完整 ExecutionPlan

## 基础设施层 - GPU 矩阵运算

- [x] GPUMatrixOps.zscore() GPU/CPU 双路径实现
- [x] GPUMatrixOps.rolling_zscore() GPU torch conv1d / CPU pandas 双路径
- [x] GPUMatrixOps.compute_ic() GPU torch 向量化 / CPU numpy 双路径
- [x] GPUMatrixOps.compute_rank_ic() GPU torch 排序 / CPU scipy 双路径
- [x] GPUMatrixOps.compute_correlation_matrix() GPU torch.matmul / CPU numpy 双路径
- [x] GPUMatrixOps.compute_forward_returns() GPU 向量化 / CPU numpy 双路径
- [x] 所有 GPUMatrixOps 方法输入输出为 numpy ndarray，内部自动 GPU 转换
- [x] GPU 不可用时所有方法 fallback 到 CPU，结果数值一致（误差 < 1e-5）

## CPUExecutor 内存感知

- [x] CPUExecutor.__init__ 支持 memory_budget 参数
- [x] CPUExecutor.execute/submit_map 根据 memory_budget 约束 max_workers
- [x] CPUExecutor.set_memory_budget() 允许运行时调整

## AccelerationService 集成

- [x] AccelerationService 创建 ResourceScheduler 实例
- [x] AccelerationService.parallel_map_with_plan() 使用 TaskProfile 规划执行
- [x] AccelerationService.submit_map_with_plan() 使用 TaskProfile 规划执行
- [x] 原有 parallel_map/submit_map 保持兼容
- [x] __init__.py 导出 ResourceScheduler / TaskProfile / ExecutionPlan / GPUMatrixOps / MemoryOptimizer

## TradeFlowEngine 内存优化

- [x] TradeFlowEngine.aggregate() 聚合后 del 中间列 + gc.collect()
- [x] _aggregate_single_month 读取后调用 MemoryOptimizer.optimize_dtypes
- [x] 输出 DataFrame 数值列使用 float32

## Feature Matrix GPU 加速

- [x] _compute_tech_indicators 中 zscore/rolling 委托 GPUMatrixOps.rolling_zscore
- [x] _merge_trades 大数据量时使用 MemoryOptimizer 优化
- [x] build_feature_matrix_from_df 使用 MemoryOptimizer.optimize_dtypes 优化最终 DataFrame

## IC Analysis GPU 加速

- [x] IC / Rank IC 计算委托 GPUMatrixOps
- [x] GPU 可用且数据量 > 1000 行时自动启用 GPU

## 端到端验证

- [x] ResourceScheduler 在不同内存配置下正确计算 max_workers
- [x] GPUMatrixOps GPU/CPU 结果数值一致（误差 < 1e-5）
- [x] MemoryOptimizer.downcast_float 内存减少约 50%
- [x] TradeFlowEngine.aggregate 中间列已释放
- [x] IC Analysis GPU 加速路径正常工作

## Feature Availability Audit 并行加速

- [x] check_data_source_availability 使用 AccelerationService.parallel_map 并行加载
- [x] run_availability_audit 批量向量化计算非空率
- [x] build_feature_matrix 返回的 fm 使用 MemoryOptimizer.optimize_dtypes
- [x] 审计结果 DataFrame 使用 MemoryOptimizer.downcast_float

## Leakage Audit 并行文件扫描

- [x] _check_all_python_files 使用 AccelerationService.parallel_map 并行处理
- [x] 每个 worker 返回 List[LeakageIssue]
- [x] 主线程汇总结果到 LeakageAuditResult

## Timeline Leakage Audit O(n) 优化

- [x] _check_no_future_data_in_timeline O(n²) 优化为 O(n log n)
- [x] 优化后结果与原始实现一致

## 审计加速验证

- [x] feature_availability_audit 并行数据源加载正常
- [x] 批量非空率计算结果与逐列循环一致
- [x] leakage_audit 并行文件扫描结果与串行一致
- [x] audit.py O(n) 时序检查结果与 O(n²) 一致
