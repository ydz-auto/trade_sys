/**
 * Runtime Manager - 管理多个独立的 Runtime
 *
 * Live Runtime - 实时交易运行时（真实资金）
 * Paper Runtime - 模拟交易运行时（真实数据+模拟下单）
 * Backtest Runtime - 回测运行时（历史数据）
 * Replay Runtime - 历史回放运行时（历史数据）
 * AI Runtime - AI 研究运行时
 *
 * 每个 Runtime 独立运行，防止互相阻塞
 */

import { 
  RuntimeType, 
  RuntimeState, 
  RuntimeConfig,
  RuntimeStatus,
  createInitialRuntimeState
} from '../../types'
import { wsService, type ChannelType } from '../websocket/wsService'

interface RuntimeInstance {
  config: RuntimeConfig
  state: RuntimeState
  isActive: boolean
  subscriptions: Set<string>
}

export class RuntimeManager {
  private static instance: RuntimeManager
  private runtimes: Map<string, RuntimeInstance> = new Map()
  private activeRuntimeId: string | null = null
  private listeners: Set<(runtimeId: string, state: RuntimeState) => void> = new Set()

  private constructor() {
    this.initializeDefaultRuntimes()
  }

  static getInstance(): RuntimeManager {
    if (!RuntimeManager.instance) {
      RuntimeManager.instance = new RuntimeManager()
    }
    return RuntimeManager.instance
  }

  private initializeDefaultRuntimes() {
    const defaultRuntimes: RuntimeConfig[] = [
      {
        type: 'live',
        id: 'live',
        name: '实时交易',
        autoSubscribe: true,
        channels: ['dashboard', 'decision', 'risk', 'position', 'timeline'],
      },
      {
        type: 'paper',
        id: 'paper',
        name: '模拟交易',
        autoSubscribe: true,
        channels: ['dashboard', 'decision', 'risk', 'position', 'timeline'],
      },
      {
        type: 'backtest',
        id: 'backtest',
        name: '策略回测',
        autoSubscribe: false,
        channels: [],
      },
      {
        type: 'replay',
        id: 'replay',
        name: '历史回放',
        autoSubscribe: false,
        channels: [],
      },
      {
        type: 'ai',
        id: 'ai',
        name: 'AI 研究',
        autoSubscribe: false,
        channels: [],
      },
    ]

    defaultRuntimes.forEach(config => {
      this.createRuntime(config)
    })

    // Set live as active
    this.activateRuntime('live')
  }

  createRuntime(config: RuntimeConfig): string {
    const existing = this.runtimes.get(config.id)
    if (existing) {
      console.warn(`Runtime ${config.id} already exists`)
      return config.id
    }

    const runtime: RuntimeInstance = {
      config,
      state: createInitialRuntimeState(config.type),
      isActive: false,
      subscriptions: new Set(),
    }

    this.runtimes.set(config.id, runtime)

    if (config.autoSubscribe) {
      this.subscribeRuntime(config.id, config.channels)
    }

    console.log(`Runtime ${config.id} created`)
    return config.id
  }

  destroyRuntime(runtimeId: string): boolean {
    const runtime = this.runtimes.get(runtimeId)
    if (!runtime) return false

    this.unsubscribeRuntime(runtimeId)
    
    if (this.activeRuntimeId === runtimeId) {
      this.activeRuntimeId = null
    }

    this.runtimes.delete(runtimeId)
    console.log(`Runtime ${runtimeId} destroyed`)
    return true
  }

  activateRuntime(runtimeId: string): boolean {
    const runtime = this.runtimes.get(runtimeId)
    if (!runtime) return false

    // Deactivate current active runtime
    if (this.activeRuntimeId) {
      const current = this.runtimes.get(this.activeRuntimeId)
      if (current) {
        current.isActive = false
      }
    }

    runtime.isActive = true
    this.activeRuntimeId = runtimeId

    console.log(`Runtime ${runtimeId} activated`)
    this.notifyListeners(runtimeId, runtime.state)
    return true
  }

  subscribeRuntime(runtimeId: string, channels: string[]): boolean {
    const runtime = this.runtimes.get(runtimeId)
    if (!runtime) return false

    channels.forEach(ch => runtime.subscriptions.add(ch))
    
    // Live and Paper runtimes connect to WebSocket for real-time data
    if (runtime.config.type === 'live' || runtime.config.type === 'paper') {
      const channelNames = channels.map(ch => `channel:${ch}`)
      wsService.subscribe(channelNames)
    }

    return true
  }

  unsubscribeRuntime(runtimeId: string): boolean {
    const runtime = this.runtimes.get(runtimeId)
    if (!runtime) return false

    if (runtime.config.type === 'live' || runtime.config.type === 'paper') {
      const channelNames = Array.from(runtime.subscriptions).map(ch => `channel:${ch}`)
      wsService.unsubscribe(channelNames)
    }

    runtime.subscriptions.clear()
    return true
  }

  updateRuntimeState(
    runtimeId: string, 
    partialState: Partial<RuntimeState>
  ): boolean {
    const runtime = this.runtimes.get(runtimeId)
    if (!runtime) return false

    runtime.state = { ...runtime.state, ...partialState }

    if (runtime.isActive) {
      this.notifyListeners(runtimeId, runtime.state)
    }

    return true
  }

  updateRuntimeStatus(
    runtimeId: string, 
    status: Partial<RuntimeStatus>
  ): boolean {
    const runtime = this.runtimes.get(runtimeId)
    if (!runtime) return false

    runtime.state.status = { ...runtime.state.status, ...status }

    if (runtime.isActive) {
      this.notifyListeners(runtimeId, runtime.state)
    }

    return true
  }

  getRuntime(runtimeId: string): RuntimeInstance | undefined {
    return this.runtimes.get(runtimeId)
  }

  getActiveRuntime(): RuntimeInstance | undefined {
    if (!this.activeRuntimeId) return undefined
    return this.runtimes.get(this.activeRuntimeId)
  }

  getActiveState(): RuntimeState | undefined {
    const active = this.getActiveRuntime()
    return active?.state
  }

  getAllRuntimes(): RuntimeInstance[] {
    return Array.from(this.runtimes.values())
  }

  getRuntimeIds(): string[] {
    return Array.from(this.runtimes.keys())
  }

  subscribeToUpdates(
    listener: (runtimeId: string, state: RuntimeState) => void
  ): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notifyListeners(runtimeId: string, state: RuntimeState) {
    this.listeners.forEach(listener => {
      try {
        listener(runtimeId, state)
      } catch (error) {
        console.error('Error in runtime listener:', error)
      }
    })
  }

  // Convenience methods for specific updates
  updateMarketState(runtimeId: string, data: any): boolean {
    return this.updateRuntimeState(runtimeId, {
      market: {
        ...this.getRuntime(runtimeId)?.state.market,
        ...data,
        lastUpdate: new Date().toISOString(),
      }
    })
  }

  updateSignalsState(runtimeId: string, data: any): boolean {
    return this.updateRuntimeState(runtimeId, {
      signals: {
        ...this.getRuntime(runtimeId)?.state.signals,
        ...data,
      }
    })
  }

  updateRiskState(runtimeId: string, data: any): boolean {
    return this.updateRuntimeState(runtimeId, {
      risk: {
        ...this.getRuntime(runtimeId)?.state.risk,
        ...data,
      }
    })
  }

  updatePnLState(runtimeId: string, data: any): boolean {
    return this.updateRuntimeState(runtimeId, {
      pnl: {
        ...this.getRuntime(runtimeId)?.state.pnl,
        ...data,
      }
    })
  }
}

// Initialize singleton on import
export const runtimeManager = RuntimeManager.getInstance()
