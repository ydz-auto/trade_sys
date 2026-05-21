/**
 * Runtime Module - 统一的 Runtime Visualization Layer
 *
 * 核心概念：
 * 1. 多页面共享 Runtime State - 避免重复请求和推送风暴
 * 2. 独立的 Runtime 管理 - Live/Backtest/Replay/AI 互不阻塞
 * 3. 统一的订阅机制 - 不再单独 fetch API
 *
 * 使用方式：
 * 1. 用 <RuntimeProvider> 包裹 App
 * 2. 用 useRuntime() Hook 获取状态
 * 3. 用 useRuntimeSwitcher() 切换 Runtime
 *
 * 示例：
 * ```tsx
 * import { useRuntime, useMarketState, useSignalsState } from './runtime'
 *
 * function Dashboard() {
 *   const { isConnected, isLive } = useRuntime()
 *   const market = useMarketState()
 *   const signals = useSignalsState()
 *
 *   return (...)
 * }
 * ```
 */

// Export Runtime Manager
export { RuntimeManager, runtimeManager } from './runtimeManager'
export type { RuntimeInstance } from './runtimeManager'

// Export Runtime Store
export { useRuntimeStore, initializeRuntime } from '../../store/runtimeStore'

// Export Runtime Provider & Hooks
export {
  RuntimeProvider,
  useRuntime,
  useRuntimeState,
  useMarketState,
  useSignalsState,
  useRiskState,
  usePnLState,
  useAIState,
  useFeaturesState,
  useRuntimeStatus,
  useActiveRuntime,
  useRuntimeSwitcher,
} from './RuntimeProvider'

// Export Projection Provider & Hooks (唯一状态源)
export {
  ProjectionProvider,
  useProjection,
  useMarketState as useProjectionMarketState,
  useSignalState,
  useExecutionState,
  usePortfolioState,
  useRiskState as useProjectionRiskState,
} from '../../runtime/contexts/ProjectionContext'

// Export types
export * from '../../types'
