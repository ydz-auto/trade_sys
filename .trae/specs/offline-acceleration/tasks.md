# Tasks

## Phase 1: 基础设施层 - 内存与资源感知

- [x] Task 1: 创建 `infrastructure/acceleration/memory_optimizer.py`
  - [x] 1.1: `MemoryOptimizer` 类，`downcast_float(df, target="float32")` / `downcast_int(df)` / `optimize_dtypes(df)`
  - [x] 1.2: `release_columns(df, columns)` 删除指定列 + `gc.collect()`
  - [x] 1.3: `estimate_dataframe_memory(df) -> int` 估算内存占用
  - [x] 1.4: `read_parquet_batch(path, columns, row_groups) -> Iterator[pd.DataFrame]` 分批读取
  - [x] 1.5: `write_parquet_batch(path, dfs) -> Path` 分批写入

- [x] Task 2: 修改 `infrastructure/acceleration/device_manager.py`，增加系统内存检测
  - [x] 2.1: `get_system_memory() -> int` 类方法（psutil / os.sysconf fallback）
  - [x] 2.2: `get_available_memory() -> int` 类方法
  - [x] 2.3: `DeviceInfo` 增加 `system_memory_gb: Optional[float]` 字段
  - [x] 2.4: `_auto_detect` / `_detect_cpu` 中填充 `system_memory_gb`

- [x] Task 3: 创建 `infrastructure/acceleration/resource_scheduler.py`
  - [x] 3.1: `TaskProfile` dataclass：`estimated_rows_per_task`, `estimated_columns`, `dtype_size`, `cpu_intensive`
  - [x] 3.2: `ExecutionPlan` dataclass：`max_workers`, `use_gpu`, `batch_size`, `executor_type`, `memory_budget_per_worker`
  - [x] 3.3: `ResourceScheduler` 类，`estimate_memory_per_worker(rows, columns, dtype_size) -> int`
  - [x] 3.4: `compute_max_workers(estimated_mem_per_worker, safety_factor=0.8) -> int`
  - [x] 3.5: `plan_execution(task_profile) -> ExecutionPlan`，整合内存、CPU、GPU 信息

## Phase 2: GPU 矩阵运算

- [x] Task 4: 创建 `infrastructure/acceleration/gpu_matrix_ops.py`
  - [x] 4.1: `GPUMatrixOps` 类，构造时检测 GPU 可用性
  - [x] 4.2: `zscore(matrix, axis=0) -> np.ndarray`，GPU torch / CPU numpy fallback
  - [x] 4.3: `rolling_zscore(series, window) -> np.ndarray`，GPU torch conv1d / CPU pandas fallback
  - [x] 4.4: `compute_ic(features, returns) -> np.ndarray`，GPU torch 向量化 / CPU numpy fallback
  - [x] 4.5: `compute_rank_ic(features, returns) -> np.ndarray`，GPU torch 排序 / CPU scipy fallback
  - [x] 4.6: `compute_correlation_matrix(matrix) -> np.ndarray`，GPU torch.matmul / CPU numpy fallback
  - [x] 4.7: `compute_forward_returns(prices, horizons) -> np.ndarray`，GPU 向量化 / CPU numpy fallback
  - [x] 4.8: 所有方法输入输出统一为 numpy ndarray，内部自动 GPU tensor 转换

## Phase 3: CPUExecutor 内存感知

- [x] Task 5: 修改 `infrastructure/acceleration/cpu_executor.py`
  - [x] 5.1: `CPUExecutor.__init__` 增加 `memory_budget: Optional[int] = None` 参数
  - [x] 5.2: `execute` / `submit_map` 内部根据 `memory_budget` 约束 `max_workers`
  - [x] 5.3: 新增 `set_memory_budget(budget: int)` 方法

## Phase 4: AccelerationService 集成

- [x] Task 6: 修改 `infrastructure/acceleration/acceleration_service.py`
  - [x] 6.1: `AccelerationService.__init__` 创建 `ResourceScheduler` 实例
  - [x] 6.2: 新增 `parallel_map_with_plan(func, tasks, task_profile)` 方法
  - [x] 6.3: 新增 `submit_map_with_plan(func, kwargs_list, task_profile)` 方法
  - [x] 6.4: 原有 `parallel_map` / `submit_map` 内部使用默认 `TaskProfile` 保持兼容

- [x] Task 7: 修改 `infrastructure/acceleration/__init__.py`
  - [x] 7.1: 导出 `ResourceScheduler`, `TaskProfile`, `ExecutionPlan`
  - [x] 7.2: 导出 `GPUMatrixOps`
  - [x] 7.3: 导出 `MemoryOptimizer`

## Phase 5: TradeFlowEngine 内存优化

- [x] Task 8: 修改 `engines/compute/feature/trade_flow_engine.py`
  - [x] 8.1: `aggregate` 方法中聚合完成后 `del` 中间列 + `gc.collect()`
  - [x] 8.2: `_aggregate_single_month` 读取数据后调用 `MemoryOptimizer.optimize_dtypes`
  - [x] 8.3: 输出 DataFrame 所有数值列使用 float32

## Phase 6: Feature Matrix GPU 加速

- [x] Task 9: 修改 `research/alpha/feature_matrix.py`
  - [x] 9.1: `_compute_tech_indicators` 中 zscore / rolling 计算委托 `GPUMatrixOps.rolling_zscore`
  - [x] 9.2: `_merge_trades` 中大 trades 数据（> 5M 行）使用 `MemoryOptimizer` 优化 dtype 和释放中间列
  - [x] 9.3: `build_feature_matrix_from_df` 中使用 `MemoryOptimizer.optimize_dtypes` 优化最终 DataFrame

- [x] Task 10: 修改 `research/alpha/ic_analysis.py`
  - [x] 10.1: IC / Rank IC 计算委托 `GPUMatrixOps.compute_ic` / `GPUMatrixOps.compute_rank_ic`
  - [x] 10.2: 当 GPU 可用且数据量 > 1000 行时自动启用 GPU

## Phase 7: 验证

- [x] Task 11: 端到端验证
  - [x] 11.1: 验证 `ResourceScheduler` 在不同内存配置下正确计算 `max_workers`
  - [x] 11.2: 验证 `GPUMatrixOps` GPU/CPU 结果数值一致（误差 < 1e-5）
  - [x] 11.3: 验证 `MemoryOptimizer.downcast_float` 内存减少约 50%
  - [x] 11.4: 验证 `TradeFlowEngine.aggregate` 中间列已释放
  - [x] 11.5: 验证 IC Analysis GPU 加速路径正常工作

## Phase 8: 审计模块加速

- [x] Task 12: 修改 `research/alpha/feature_availability_audit.py`
  - [x] 12.1: `check_data_source_availability` 使用 `AccelerationService.parallel_map` 并行加载各数据源（IO 密集型，线程执行器）
  - [x] 12.2: `run_availability_audit` 中逐 feature 非空率循环改为批量向量化 `fm.notna().sum() / len(fm)`
  - [x] 12.3: `build_feature_matrix` 返回的 fm 使用 `MemoryOptimizer.optimize_dtypes` 降级 dtype
  - [x] 12.4: 审计结果 DataFrame 使用 `MemoryOptimizer.downcast_float` 优化

- [x] Task 13: 修改 `research/alpha/leakage_audit.py`
  - [x] 13.1: `_check_all_python_files` 使用 `AccelerationService.parallel_map` 并行处理文件
  - [x] 13.2: 每个 worker 处理一个文件，返回 `List[LeakageIssue]`
  - [x] 13.3: 主线程汇总所有 worker 结果到 `LeakageAuditResult`

- [x] Task 14: 修改 `research/leakage_audit/audit.py`
  - [x] 14.1: `_check_no_future_data_in_timeline` O(n²) 双重循环优化为 O(n log n) 排序 + O(n) 单次遍历
  - [x] 14.2: 验证优化后结果与原始实现一致

## Phase 9: 审计加速验证

- [x] Task 15: 审计模块端到端验证
  - [x] 15.1: 验证 `feature_availability_audit` 并行数据源加载正常
  - [x] 15.2: 验证批量非空率计算结果与逐列循环一致
  - [x] 15.3: 验证 `leakage_audit` 并行文件扫描结果与串行一致
  - [x] 15.4: 验证 `audit.py` O(n) 时序检查结果与 O(n²) 一致

# Task Dependencies

- Task 2 depends on Task 1 (ResourceScheduler 需要 DeviceManager 内存信息)
- Task 3 depends on Task 2 (ResourceScheduler 依赖 DeviceManager.get_system_memory)
- Task 4 可与 Task 1-3 并行（GPU 矩阵运算与资源调度互不依赖）
- Task 5 depends on Task 3 (CPUExecutor memory_budget 需要 ExecutionPlan 定义)
- Task 6 depends on Task 3, Task 5 (AccelerationService 集成 ResourceScheduler)
- Task 7 depends on Task 1, Task 3, Task 4, Task 6 (统一导出)
- Task 8 depends on Task 1 (TradeFlowEngine 使用 MemoryOptimizer)
- Task 9 depends on Task 1, Task 4 (Feature Matrix 使用 MemoryOptimizer + GPUMatrixOps)
- Task 10 depends on Task 4 (IC Analysis 使用 GPUMatrixOps)
- Task 11 depends on Task 8, Task 9, Task 10
- Task 12 depends on Task 6, Task 1 (使用 AccelerationService + MemoryOptimizer)
- Task 13 depends on Task 6 (使用 AccelerationService)
- Task 14 无外部依赖（纯算法优化）
- Task 15 depends on Task 12, Task 13, Task 14

# Parallelizable Work

- Task 1 + Task 4 可并行（内存优化与 GPU 矩阵运算互不依赖）
- Task 8 + Task 9 + Task 10 可并行（三个业务模块的修改互不依赖，但都依赖 Phase 1-4 的基础设施）
- Task 12 + Task 13 + Task 14 可并行（三个审计模块的修改互不依赖）
