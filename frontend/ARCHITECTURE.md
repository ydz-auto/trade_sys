# Runtime Visualization Layer - 架构文档

## 概述

本次重构实现了统一的 Runtime Visualization Layer，解决了以下问题：

1. **避免重复请求和推送风暴** - 多页面共享 Runtime State
2. **独立的 Runtime 管理** - Live/Backtest/Replay/AI 互不阻塞
3. **简化的订阅机制** - 不再单独 fetch API，而是订阅统一 Runtime State

## 核心架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend Pages                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Dashboard   │  │ FeatureCon- │  │ ReplayPage  │  │  Alpha Lab  │ │
│  │             │  │ figPage     │  │             │  │             │ │
│  └───────┬─────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
└──────────┼──────────────────┼──────────────────┼──────────────────┼───┘
           │                  │                  │                  │
           └──────────────────┼──────────────────┼──────────────────┘
                              │
                              ▼
              ┌─────────────────────────────────────┐
              │         RuntimeProvider             │
              │  (Context for shared state)        │
              └───────────────┬─────────────────────┘
                              │
              ┌───────────────▼─────────────────────┐
              │         useRuntime() Hooks          │
              │  - useMarketState()                 │
              │  - useSignalsState()                │
              │  - useRiskState()                   │
              │  - usePnLState()                    │
              │  - useAIState()                     │
              │  - useFeaturesState()               │
              │  - useRuntimeSwitcher()             │
              └───────────────┬─────────────────────┘
                              │
              ┌───────────────▼─────────────────────┐
              │       useRuntimeStore (Zustand)     │
              └───────────────┬─────────────────────┘
                              │
              ┌───────────────▼─────────────────────┐
              │      RuntimeManager (Singleton)     │
              │  ┌───────────────────────────────┐ │
              │  │ Live Runtime                  │ │
              │  │ Backtest Runtime              │ │
              │  │ Replay Runtime                │ │
              │  │ AI Runtime                    │ │
              │  └───────────────────────────────┘ │
              └───────────────┬─────────────────────┘
                              │
              ┌───────────────▼─────────────────────┐
              │      WebSocket Service              │
              └─────────────────────────────────────┘
```

## 目录结构

```
frontend/src/
├── services/
│   └── runtime/
│       ├── index.ts              # 导出文件
│       ├── runtimeManager.ts     # Runtime Manager 单例
│       └── RuntimeProvider.tsx   # React Provider & Hooks
├── store/
│   └── runtimeStore.ts          # Zustand Runtime Store
└── types/
    └── index.ts                  # RuntimeState 类型定义
```

## 使用方式

### 1. 初始化 RuntimeProvider

```tsx
// App.tsx
import { RuntimeProvider } from './services/runtime'

function App() {
  return (
    <RuntimeProvider>
      {/* 你的应用 */}
    </RuntimeProvider>
  )
}
```

### 2. 在页面中使用

```tsx
import { 
  useRuntime, 
  useMarketState, 
  useSignalsState,
  useRuntimeSwitcher
} from '../services/runtime'

function Dashboard() {
  const { isConnected, isLive } = useRuntime()
  const market = useMarketState()
  const signals = useSignalsState()
  
  const { availableRuntimes, switchRuntime } = useRuntimeSwitcher()
  
  return (
    <div>
      <h1>Dashboard</h1>
      <p>Connected: {isConnected ? 'Yes' : 'No'}</p>
      <p>Mode: {isLive ? 'Live' : 'Replay/Backtest'}</p>
      
      <select onChange={(e) => switchRuntime(e.target.value)}>
        {availableRuntimes.map(r => (
          <option key={r.id} value={r.id}>{r.name}</option>
        ))}
      </select>
    </div>
  )
}
```

### 3. 所有可用的 Hooks

```ts
// 基础 Hook
useRuntime()

// 状态访问 Hooks
useRuntimeState(key)      // 获取任意状态
useMarketState()          // 获取市场状态
useSignalsState()         // 获取信号状态
useRiskState()            // 获取风险状态
usePnLState()             // 获取盈亏状态
useAIState()              // 获取 AI 洞察状态
useFeaturesState()        // 获取特征矩阵状态
useRuntimeStatus()        // 获取 Runtime 状态

// 功能 Hooks
useActiveRuntime()        // 当前 Runtime 详情
useRuntimeSwitcher()      // Runtime 切换器
```

## Runtime State 结构

```typescript
interface RuntimeState {
  // Status
  status: RuntimeStatus
  
  // Feature Matrix
  features: {
    metadata: FeatureMetadata[]
    values: Record<string, FeatureValue[]>
    summaries: Record<string, FeatureMatrixSummary>
  }
  
  // Market
  market: MarketState
  
  // Signals
  signals: SignalsState
  
  // Risk
  risk: RiskState
  
  // PnL
  pnl: PnLState
  
  // AI
  ai: AIState
  
  // Replay
  replay: ReplayState
  
  // Positions & Timeline
  positions: Position[]
  timeline: TimelineEvent[]
}
```

## Runtime Manager

### 支持的 4 个独立 Runtime

| Runtime | 描述 | WebSocket |
|---------|------|-----------|
| live | 实时交易 | ✅ 订阅 |
| backtest | 策略回测 | ❌ 本地运行 |
| replay | 历史回放 | ❌ 本地播放 |
| ai | AI 研究 | ❌ 本地分析 |

### 设计特点

1. **单例模式** - 全局共享一个 `RuntimeManager`
2. **独立运行** - 每个 Runtime 有自己的状态，互不影响
3. **切换轻量** - Runtime 切换只是 Store 更新，页面自动重渲染
4. **向后兼容** - 旧的 realtimeStore 仍然保留

## 与旧架构的对比

### 旧架构

```
Page1 -> fetch API / subscribe WebSocket
Page2 -> fetch API / subscribe WebSocket
Page3 -> fetch API / subscribe WebSocket
...
问题：重复请求、推送风暴、状态不一致
```

### 新架构

```
Page1 ─┐
Page2 ─┼─> useRuntime() ──> 共享 Runtime State
Page3 ─┘
优势：单一数据源、状态一致、零重复请求
```

## 下一步

- 集成 RuntimeProvider 到 App 组件
- 更新现有页面使用新的 Hooks
- 完善 WebSocket 监听逻辑
- 实现 Backtest 和 Replay Runtime 的具体功能
