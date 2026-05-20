import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { api } from '../services/api/client'

export type TradingMode = 'backtest' | 'paper' | 'live'
export type RuntimeState = 'starting' | 'running' | 'paused' | 'degraded' | 'stopped' | 'failed' | 'recovering'

export interface RuntimeInfo {
  id: string
  type: string
  state: RuntimeState
  mode?: TradingMode
  priority: number
}

export interface RuntimeModeStatus {
  mode: TradingMode
  state: string
  previous_mode?: TradingMode
  config: {
    market_data_source: string
    order_execution: string
    risk_engine: string
    color: string
    warning?: string
  }
  is_safe_to_trade: [boolean, string]
}

export interface OrchestratorStatus {
  is_running: boolean
  mode: TradingMode
  active_runtimes: number
  failed_runtimes: number
  uptime_seconds: number
  started_at?: string
}

interface RuntimeContextValue {
  mode: TradingMode
  modeStatus: RuntimeModeStatus | null
  orchestratorStatus: OrchestratorStatus | null
  runtimes: RuntimeInfo[]
  isLoading: boolean
  error: string | null
  
  switchMode: (targetMode: TradingMode, reason?: string) => Promise<boolean>
  startOrchestrator: () => Promise<boolean>
  stopOrchestrator: () => Promise<boolean>
  refresh: () => Promise<void>
}

const RuntimeContext = createContext<RuntimeContextValue | null>(null)

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<TradingMode>('paper')
  const [modeStatus, setModeStatus] = useState<RuntimeModeStatus | null>(null)
  const [orchestratorStatus, setOrchestratorStatus] = useState<OrchestratorStatus | null>(null)
  const [runtimes, setRuntimes] = useState<RuntimeInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [modeRes, orchestratorRes, runtimesRes] = await Promise.all([
        api.get('/trading-mode'),
        api.get('/runtime/orchestrator/status'),
        api.get('/runtime/orchestrator/runtimes'),
      ])

      if (modeRes) {
        setMode(modeRes.mode)
        setModeStatus(modeRes)
      }

      if (orchestratorRes) {
        setOrchestratorStatus(orchestratorRes)
      }

      if (runtimesRes && Array.isArray(runtimesRes)) {
        setRuntimes(runtimesRes)
      }

      setError(null)
    } catch (err) {
      console.error('Failed to refresh runtime status:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  const switchMode = useCallback(async (targetMode: TradingMode, reason: string = ''): Promise<boolean> => {
    try {
      setIsLoading(true)
      const result = await api.post('/trading-mode/transition', {
        target_mode: targetMode,
        reason,
        confirmed: targetMode === 'live',
      })

      if (result.success) {
        setMode(targetMode)
        await refresh()
        return true
      }

      setError(result.error || 'Failed to switch mode')
      return false
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return false
    } finally {
      setIsLoading(false)
    }
  }, [refresh])

  const startOrchestrator = useCallback(async (): Promise<boolean> => {
    try {
      setIsLoading(true)
      const result = await api.post('/runtime/orchestrator/start')
      
      if (result.success) {
        await refresh()
        return true
      }
      
      setError(result.error || 'Failed to start')
      return false
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return false
    } finally {
      setIsLoading(false)
    }
  }, [refresh])

  const stopOrchestrator = useCallback(async (): Promise<boolean> => {
    try {
      setIsLoading(true)
      const result = await api.post('/runtime/orchestrator/stop')
      
      if (result.success) {
        await refresh()
        return true
      }
      
      setError(result.error || 'Failed to stop')
      return false
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return false
    } finally {
      setIsLoading(false)
    }
  }, [refresh])

  const value: RuntimeContextValue = {
    mode,
    modeStatus,
    orchestratorStatus,
    runtimes,
    isLoading,
    error,
    switchMode,
    startOrchestrator,
    stopOrchestrator,
    refresh,
  }

  return (
    <RuntimeContext.Provider value={value}>
      {children}
    </RuntimeContext.Provider>
  )
}

export function useRuntime() {
  const context = useContext(RuntimeContext)
  if (!context) {
    throw new Error('useRuntime must be used within RuntimeProvider')
  }
  return context
}

export function useRuntimeMode() {
  const { mode, modeStatus, switchMode } = useRuntime()
  return { mode, modeStatus, switchMode }
}

export function useOrchestrator() {
  const { orchestratorStatus, runtimes, startOrchestrator, stopOrchestrator } = useRuntime()
  return { orchestratorStatus, runtimes, startOrchestrator, stopOrchestrator }
}
