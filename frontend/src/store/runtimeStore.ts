/**
 * Runtime Store - 统一的 Runtime 状态管理
 *
 * 不再单独 fetch API，而是订阅统一 Runtime State
 * 多页面共享 Runtime State，避免重复请求和推送风暴
 */

import { create } from 'zustand'
import { runtimeManager } from '../runtime/runtimeManager'
import type { 
  RuntimeState, 
  RuntimeType, 
  RuntimeConfig 
} from '../../types'
import { wsService, type ChannelType } from '../websocket/wsService'

interface RuntimeStore {
  // Current active runtime
  activeRuntimeId: string | null
  activeRuntimeState: RuntimeState | null
  availableRuntimes: RuntimeConfig[]

  // Actions
  switchRuntime: (runtimeId: string) => void
  createRuntime: (config: RuntimeConfig) => string
  destroyRuntime: (runtimeId: string) => boolean

  // Quick access to state parts
  getMarketState: () => RuntimeState['market'] | null
  getSignalsState: () => RuntimeState['signals'] | null
  getRiskState: () => RuntimeState['risk'] | null
  getPnLState: () => RuntimeState['pnl'] | null
  getAIState: () => RuntimeState['ai'] | null
  getFeaturesState: () => RuntimeState['features'] | null

  // Initialization
  initialize: () => void
}

export const useRuntimeStore = create<RuntimeStore>((set, get) => {
  let unsubscribeRuntime: (() => void) | null = null

  const updateActiveState = () => {
    const activeState = runtimeManager.getActiveState()
    set({ activeRuntimeState: activeState || null })
  }

  return {
    activeRuntimeId: null,
    activeRuntimeState: null,
    availableRuntimes: [],

    switchRuntime: (runtimeId: string) => {
      const success = runtimeManager.activateRuntime(runtimeId)
      if (success) {
        const runtimes = runtimeManager.getAllRuntimes().map(r => r.config)
        set({
          activeRuntimeId: runtimeId,
          availableRuntimes: runtimes,
        })
        updateActiveState()
      }
    },

    createRuntime: (config: RuntimeConfig) => {
      const id = runtimeManager.createRuntime(config)
      const runtimes = runtimeManager.getAllRuntimes().map(r => r.config)
      set({ availableRuntimes: runtimes })
      return id
    },

    destroyRuntime: (runtimeId: string) => {
      const success = runtimeManager.destroyRuntime(runtimeId)
      const runtimes = runtimeManager.getAllRuntimes().map(r => r.config)
      set({ availableRuntimes: runtimes })
      return success
    },

    getMarketState: () => get().activeRuntimeState?.market || null,
    getSignalsState: () => get().activeRuntimeState?.signals || null,
    getRiskState: () => get().activeRuntimeState?.risk || null,
    getPnLState: () => get().activeRuntimeState?.pnl || null,
    getAIState: () => get().activeRuntimeState?.ai || null,
    getFeaturesState: () => get().activeRuntimeState?.features || null,

    initialize: () => {
      // Initialize available runtimes
      const runtimes = runtimeManager.getAllRuntimes().map(r => r.config)
      const active = runtimeManager.getActiveRuntime()

      set({
        activeRuntimeId: active?.config.id || null,
        activeRuntimeState: active?.state || null,
        availableRuntimes: runtimes,
      })

      // Subscribe to runtime updates
      unsubscribeRuntime = runtimeManager.subscribeToUpdates((_, __) => {
        updateActiveState()
      })

      // Setup WebSocket listeners for live runtime
      setupWebSocketListeners()
    },
  }
})

// Setup WebSocket listeners for live runtime
function setupWebSocketListeners() {
  wsService.on('channel:dashboard', (data) => {
    if (data.type === 'data_update' || data.type === 'state_update') {
      const runtimeId = 'live'
      const runtime = runtimeManager.getRuntime(runtimeId)
      
      if (runtime?.isActive) {
        if (data.data?.prices) {
          runtimeManager.updateMarketState(runtimeId, {
            prices: data.data.prices,
          })
        }
        if (data.data?.regime) {
          // Regime goes to market or risk state
        }
        if (data.data?.compositeScore !== undefined) {
          // Composite score can go to signals or risk
        }
      }
    }
  })

  wsService.on('channel:decision', (data) => {
    const runtimeId = 'live'
    const runtime = runtimeManager.getRuntime(runtimeId)
    
    if (runtime?.isActive) {
      if (data.type === 'new_decision' || data.type === 'data_update') {
        const decision = data.decision || data.data
        if (decision) {
          // Map decision to signal
          runtimeManager.updateSignalsState(runtimeId, {
            // Update signals state with new decision
          })
        }
      }
    }
  })

  wsService.on('channel:risk', (data) => {
    const runtimeId = 'live'
    const runtime = runtimeManager.getRuntime(runtimeId)
    
    if (runtime?.isActive) {
      if (data.type === 'data_update') {
        runtimeManager.updateRiskState(runtimeId, data.data)
      }
    }
  })

  wsService.on('channel:position', (data) => {
    const runtimeId = 'live'
    const runtime = runtimeManager.getRuntime(runtimeId)
    
    if (runtime?.isActive) {
      if (data.type === 'position_update' || data.type === 'data_update') {
        const position = data.position || data.data
        if (position) {
          // Update positions and PnL
          runtimeManager.updatePnLState(runtimeId, {
            // Update PnL
          })
        }
      }
    }
  })

  wsService.on('channel:timeline', (data) => {
    const runtimeId = 'live'
    const runtime = runtimeManager.getRuntime(runtimeId)
    
    if (runtime?.isActive) {
      if (data.type === 'new_event' || data.type === 'data_update') {
        const event = data.event || data.data
        if (event) {
          // Update timeline in state
          const currentTimeline = runtime.state.timeline
          runtimeManager.updateRuntimeState(runtimeId, {
            timeline: [event, ...currentTimeline].slice(0, 100),
          })
        }
      }
    }
  })
}

// Initialize on import
let initialized = false
export function initializeRuntime() {
  if (initialized) return
  initialized = true
  
  wsService.connect()
    .then(() => {
      useRuntimeStore.getState().initialize()
    })
    .catch(console.error)
}
