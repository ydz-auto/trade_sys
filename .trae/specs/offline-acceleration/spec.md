# Trade Flow / Feature Matrix 离线加速方案 Spec

## Why

当前 Trade Flow 物化流水线在处理 69GB 原始 trade 数据时，CPUExecutor 的 worker 数量是静态配置的，无法根据内存占用动态调整，容易 OOM；Feature Matrix 构建阶段的 IC / zscore / correlation 计算全部在 CPU 上执行，未利用 GPU 并行能力；整体 pipeline 缺乏统一的资源感知调度，导致 CPU 利用率不足、内存安全无保障、GPU 闲置。

## What Changes

### 新增文件

- `infrastructure/acceleration/resource_scheduler.py`：动态资源调度器（内存感知 worker 规划、GPU/CPU 自动选择）
- `infrastructure/acceleration/gpu_matrix_ops.py`：GPU 矩阵运算库（zscore / IC / correlation / forward return，基于 PyTorch/cupy）
- `infrastructure/acceleration/memory_optimizer.py`：内存优化工具（dtype 降级、中间列释放、批量 Parquet 读写）

### 修改文件

- `infrastructure/acceleration/cpu_executor.py`：`CPUExecutor.__init__` 增加 `memory_budget` 参数，支持动态 worker 数量调整
- `infrastructure/acceleration/device_manager.py`：增加 `get_system_memory()` / `get_available_memory()` 方法
- `infrastructure/acceleration/acceleration_service.py`：集成 `ResourceScheduler`，`parallel_map` / `submit_map` 支持内存感知调度
- `engines/compute/feature/trade_flow_engine.py`：聚合后立即 `del` 中间列 + `gc.collect()`；`_aggregate_single_month` 使用 `memory_optimizer` 降级 dtype
- `research/alpha/feature_matrix.py`：`_compute_tech_indicators` 和 IC 相关计算委托 `gpu_matrix_ops`；`_merge_trades` 使用 `memory_optimizer` 批量处理
- `research/alpha/ic_analysis.py`：IC / Rank IC 计算委托 `gpu_matrix_ops`，GPU 可用时自动加速
- `research/alpha/feature_availability_audit.py`：数据源并行加载、feature 非空率批量计算、MemoryOptimizer 优化
- `research/alpha/leakage_audit.py`：多线程 AST 解析、并行文件扫描
- `research/leakage_audit/audit.py`：O(n²) 时序检查优化为 O(n)

## Impact

- Affected specs: offline-trade-flow-alpha-pipeline, Acceleration Infrastructure, Feature Matrix, IC Analysis
- Affected code:
  - `infrastructure/acceleration/`（新增 3 文件 + 修改 3 文件）
  - `engines/compute/feature/trade_flow_engine.py`
  - `research/alpha/feature_matrix.py`
  - `research/alpha/ic_analysis.py`
  - `research/alpha/feature_availability_audit.py`
  - `research/alpha/leakage_audit.py`
  - `research/leakage_audit/audit.py`

---

## ADDED Requirements

### Requirement: 动态资源调度器

系统 SHALL 提供 `ResourceScheduler`，根据系统资源动态规划 CPU worker 数量和 GPU 使用策略。

- 位于 `infrastructure/acceleration/resource_scheduler.py`
- `estimate_memory_per_worker(rows, columns, dtype_size) -> int`：估算单个 worker 内存占用（bytes）
- `compute_max_workers(estimated_mem_per_worker, safety_factor=0.8) -> int`：`min(cpu_cores, floor(available_memory * safety_factor / estimated_mem_per_worker))`
- `plan_execution(task_profile) -> ExecutionPlan`：返回包含 `max_workers`、`use_gpu`、`batch_size`、`executor_type` 的执行计划
- `ExecutionPlan` dataclass：`max_workers: int`、`use_gpu: bool`、`batch_size: int`、`executor_type: str`、`memory_budget_per_worker: int`
- 自动检测系统内存（通过 `psutil` 或 `os`），CPU 核心数（`multiprocessing.cpu_count()`），GPU 可用性（`DeviceManager`）
- 当 `available_memory < estimated_mem_per_worker` 时，自动切换到分批模式（减小 batch_size）

#### Scenario: 内存受限时自动减少 worker

- **WHEN** 系统有 96GB 内存、16 核 CPU，每个 worker 估算需要 4GB
- **THEN** `compute_max_workers` 返回 `min(16, floor(96 * 0.8 / 4))` = 16
- **AND** `memory_budget_per_worker` = 4GB

#### Scenario: 内存不足时切换分批模式

- **WHEN** 系统有 16GB 内存、16 核 CPU，每个 worker 估算需要 4GB
- **THEN** `compute_max_workers` 返回 `min(16, floor(16 * 0.8 / 4))` = 3
- **AND** `batch_size` 自动调整以确保单批内存安全

### Requirement: GPU 矩阵运算库

系统 SHALL 提供 `GPUMatrixOps`，将 Feature Matrix 构建后的矩阵密集计算卸载到 GPU。

- 位于 `infrastructure/acceleration/gpu_matrix_ops.py`
- `zscore(matrix: np.ndarray, axis: int = 0) -> np.ndarray`：沿指定轴标准化，GPU 可用时用 torch/cupy，否则 numpy fallback
- `rolling_zscore(series: np.ndarray, window: int) -> np.ndarray`：滚动 zscore，GPU 使用 torch conv1d
- `compute_ic(features: np.ndarray, returns: np.ndarray) -> np.ndarray`：批量计算所有特征的 IC（Pearson），一次矩阵运算
- `compute_rank_ic(features: np.ndarray, returns: np.ndarray) -> np.ndarray`：批量计算 Rank IC（Spearman），GPU 使用 torch 排序
- `compute_correlation_matrix(matrix: np.ndarray) -> np.ndarray`：相关系数矩阵，GPU 使用 torch.matmul
- `compute_forward_returns(prices: np.ndarray, horizons: List[int]) -> np.ndarray`：多周期 forward return，GPU 向量化
- 所有方法在 GPU 不可用时自动 fallback 到 numpy/scipy CPU 实现
- 输入输出统一为 numpy ndarray，内部自动处理 GPU tensor 转换

#### Scenario: GPU 加速 IC 计算

- **WHEN** 调用 `GPUMatrixOps.compute_ic(features, returns)`，features shape 为 [10000, 50]，GPU 可用
- **THEN** 使用 torch 在 GPU 上一次计算 50 个特征的 IC
- **AND** 返回 shape 为 [50] 的 numpy ndarray

#### Scenario: CPU fallback

- **WHEN** 调用 `GPUMatrixOps.compute_ic(features, returns)`，GPU 不可用
- **THEN** 使用 numpy/scipy 在 CPU 上计算
- **AND** 结果与 GPU 版本数值一致（允许浮点精度差异 < 1e-5）

### Requirement: 内存优化工具

系统 SHALL 提供 `MemoryOptimizer`，统一管理 dtype 降级、中间列释放和批量 Parquet 读写。

- 位于 `infrastructure/acceleration/memory_optimizer.py`
- `downcast_float(df: pd.DataFrame, target: str = "float32") -> pd.DataFrame`：将 float64 列降级为 float32
- `downcast_int(df: pd.DataFrame) -> pd.DataFrame`：将 int64 列降级为 int32/int8
- `optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame`：自动检测并降级所有可优化列
- `release_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame`：删除指定列并触发 `gc.collect()`
- `estimate_dataframe_memory(df: pd.DataFrame) -> int`：估算 DataFrame 内存占用（bytes）
- `read_parquet_batch(path: Path, columns: Optional[List[str]] = None, row_groups: Optional[int] = None) -> Iterator[pd.DataFrame]`：分批读取 Parquet，按 row group 迭代
- `write_parquet_batch(path: Path, dfs: Iterator[pd.DataFrame]) -> Path`：分批写入 Parquet（append 模式）

#### Scenario: dtype 降级

- **WHEN** 调用 `MemoryOptimizer.downcast_float(df)`，df 包含 float64 列
- **THEN** 所有 float64 列转换为 float32
- **AND** 内存占用减少约 50%

#### Scenario: 分批读取 Parquet

- **WHEN** 调用 `MemoryOptimizer.read_parquet_batch(path, row_groups=10)`
- **THEN** 每次迭代返回最多 10 个 row group 的数据
- **AND** 不会一次性加载整个文件

### Requirement: TradeFlowEngine 内存优化

系统 SHALL 在 `TradeFlowEngine.aggregate` 中集成内存优化。

- 聚合计算完成后，立即 `del` 中间列（`buy_qty`, `sell_qty`, `buy_quote`, `sell_quote`, `large_buy_qty`, `large_sell_qty`, `large_buy_count`, `large_sell_count`）并调用 `gc.collect()`
- `_aggregate_single_month` 函数在读取数据后立即调用 `MemoryOptimizer.optimize_dtypes` 降级 dtype
- 输出 DataFrame 所有数值列使用 float32

#### Scenario: 单月聚合内存优化

- **WHEN** 调用 `_aggregate_single_month` 处理 1.27 亿行数据
- **THEN** 读取后立即将 float64 列降级为 float32
- **AND** 聚合完成后中间列已释放
- **AND** 输出 DataFrame 数值列为 float32

### Requirement: Feature Matrix GPU 加速

系统 SHALL 在 Feature Matrix 构建阶段使用 `GPUMatrixOps` 加速矩阵密集计算。

- `_compute_tech_indicators` 中的 zscore / rolling 计算委托 `GPUMatrixOps.rolling_zscore`
- IC Analysis 中的 `compute_ic` / `compute_rank_ic` 委托 `GPUMatrixOps.compute_ic` / `GPUMatrixOps.compute_rank_ic`
- 当 GPU 可用且数据量 > 1000 行时自动启用 GPU，否则 CPU fallback
- `_merge_trades` 中对大 trades 数据（> 5M 行）使用 `MemoryOptimizer.read_parquet_batch` 分批处理

#### Scenario: GPU 加速 IC 分析

- **WHEN** 运行 IC Analysis，feature matrix 有 10000 行 × 50 特征，GPU 可用
- **THEN** IC 和 Rank IC 计算使用 `GPUMatrixOps` 在 GPU 上执行
- **AND** 计算速度相比纯 CPU 提升显著

### Requirement: AccelerationService 集成 ResourceScheduler

系统 SHALL 在 `AccelerationService` 中集成 `ResourceScheduler`，使 `parallel_map` / `submit_map` 支持内存感知调度。

- `AccelerationService.__init__` 创建 `ResourceScheduler` 实例
- 新增 `parallel_map_with_plan(func, tasks, task_profile) -> List[Any]`：先通过 `ResourceScheduler.plan_execution` 获取执行计划，再按计划执行
- 新增 `submit_map_with_plan(func, kwargs_list, task_profile) -> List[SubmitResult]`：同上
- `TaskProfile` dataclass：`estimated_rows_per_task: int`、`estimated_columns: int`、`dtype_size: int = 4`（float32）、`cpu_intensive: bool = True`
- 原有 `parallel_map` / `submit_map` 保持兼容，内部使用默认 `TaskProfile`

#### Scenario: 内存感知并行执行

- **WHEN** 调用 `parallel_map_with_plan(func, tasks, TaskProfile(estimated_rows_per_task=96000000, estimated_columns=11, dtype_size=4))`
- **THEN** `ResourceScheduler` 自动计算 `max_workers`，避免 OOM
- **AND** 执行使用计算出的 worker 数量

---

## MODIFIED Requirements

### Requirement: CPUExecutor 支持 memory_budget

`CPUExecutor.__init__` 增加 `memory_budget: Optional[int] = None` 参数。

- 当 `memory_budget` 不为 None 时，`max_workers` 取 `min(self.max_workers, floor(memory_budget / estimated_mem_per_task))`
- `execute` / `submit_map` 方法签名不变，内部自动应用内存约束
- 新增 `set_memory_budget(budget: int)` 方法，允许运行时调整

### Requirement: DeviceManager 系统内存检测

`DeviceManager` 增加系统内存检测能力。

- 新增 `get_system_memory() -> int` 类方法：返回系统总物理内存（bytes），通过 `psutil.virtual_memory().total` 或 `os.sysconf` 获取
- 新增 `get_available_memory() -> int` 类方法：返回当前可用内存（bytes），通过 `psutil.virtual_memory().available` 获取
- 当 `psutil` 不可用时，使用 `os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')` 作为 fallback
- `DeviceInfo` 增加 `system_memory_gb: Optional[float]` 字段

---

## REMOVED Requirements

无删除项。

---

## ADDED Requirements (Phase 2: 审计加速)

### Requirement: Feature Availability Audit 并行加速

系统 SHALL 加速 `feature_availability_audit.py` 中的数据源检查和特征审计流程。

- `check_data_source_availability` 使用 `AccelerationService.parallel_map` 并行加载各数据源（kline/funding/OI/trades），IO 密集型使用线程执行器
- `run_availability_audit` 中逐 feature 遍历计算非空率改为批量向量化：`fm.notna().sum() / len(fm)` 一次计算所有列的非空率
- `build_feature_matrix` 返回的 fm 使用 `MemoryOptimizer.optimize_dtypes` 降级 dtype
- 审计结果 DataFrame 使用 `MemoryOptimizer.downcast_float` 优化

#### Scenario: 并行数据源检查

- **WHEN** 调用 `check_data_source_availability`，有 6 个数据源需要检查
- **THEN** 各数据源加载使用线程并行执行（IO 密集型）
- **AND** 总耗时接近最慢的单个数据源加载时间

#### Scenario: 批量非空率计算

- **WHEN** 运行 `run_availability_audit`，feature matrix 有 171 个特征
- **THEN** 非空率通过 `fm.notna().sum()` 一次向量化计算，而非逐列循环
- **AND** 计算速度显著优于逐列循环

### Requirement: Leakage Audit 并行文件扫描

系统 SHALL 加速 `leakage_audit.py` 中的文件扫描和 AST 解析。

- `_check_all_python_files` 使用 `AccelerationService.parallel_map` 并行处理多个 Python 文件的 AST 解析和正则匹配
- 每个 worker 处理一个文件，返回该文件的 `List[LeakageIssue]`
- 主线程汇总所有 worker 的结果到 `LeakageAuditResult`
- 文件读取 + AST 解析是 CPU 密集型，使用进程执行器

#### Scenario: 并行文件扫描

- **WHEN** `_check_all_python_files` 扫描 20+ 个 Python 文件
- **THEN** 文件解析使用多进程并行执行
- **AND** 结果与串行执行一致

### Requirement: Timeline Leakage Audit O(n) 优化

系统 SHALL 将 `research/leakage_audit/audit.py` 中的 O(n²) 时序检查优化为 O(n)。

- `_check_no_future_data_in_timeline` 当前使用双重循环 `for i in range(len(sorted_events)): for j in range(i+1, len(sorted_events))`，复杂度 O(n²)
- 优化为：先按 `timestamp_ms` 排序，然后单次遍历检查相邻事件的时序一致性（排序后只需检查 `sorted_events[i].timestamp_ms <= sorted_events[i+1].timestamp_ms`）
- `_check_feature_signal_chronology` 和 `_check_order_vs_signal_chronology` 已使用 dict 索引，复杂度 O(n)，无需优化

#### Scenario: 大时间线审计性能

- **WHEN** 时间线包含 10000 个事件
- **THEN** 时序检查在 O(n log n) 时间内完成（排序 + 单次遍历）
- **AND** 结果与 O(n²) 版本一致
