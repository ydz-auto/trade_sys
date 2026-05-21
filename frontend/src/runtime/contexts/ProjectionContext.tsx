import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { useRuntimeStream } from '../streams/runtimeStream.tsx'
import { api } from '../../services/api/client'

export interface ProjectionState {
  market: Record<string, unknown>
  signal: Record<string, unknown>
  execution: Record<string, unknown>
  portfolio: Record<string, unknown>
  risk: Record<string, unknown>
  runtime: Record<string, unknown>
}

interface ProjectionContextValue {
  state: ProjectionState
  isLoading: boolean
  error: string | null
  lastUpdate: string | null
  
  getMarketState: () => Record<string, unknown>
  getSignalState: () => Record<string, unknown>
  getExecutionState: () => Record<string, unknown>
  getPortfolioState: () => Record<string, unknown>
  getRiskState: () => Record<string, unknown>
  
  refresh: () => Promise<void>
}

const ProjectionContext = createContext<ProjectionContextValue | null>(null)

const initialState: ProjectionState = {
  market: {},
  signal: {},
  execution: {},
  portfolio: {},
  risk: {},
  runtime: {},
}

export function ProjectionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ProjectionState>(initialState)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)

  const { isConnected } = useRuntimeStream()

  const refresh = useCallback(async () => {
    try {
      const response = await api.get('/runtime/state')
      
      if (response && response.state) {
        setState({
          market: response.state.market || {},
          signal: response.state.signal || {},
          execution: response.state.execution || {},
          portfolio: response.state.portfolio || {},
          risk: response.state.risk || {},
          runtime: response.state.runtime || {},
        })
        setLastUpdate(new Date().toISOString())
        setError(null)
      }
    } catch (err) {
      console.error('[Projection] Refresh error:', err)
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

  const getMarketState = useCallback(() => state.market, [state.market])
  const getSignalState = useCallback(() => state.signal, [state.signal])
  const getExecutionState = useCallback(() => state.execution, [state.execution])
  const getPortfolioState = useCallback(() => state.portfolio, [state.portfolio])
  const getRiskState = useCallback(() => state.risk, [state.risk])

  const value: ProjectionContextValue = {
    state,
    isLoading,
    error,
    lastUpdate,
    getMarketState,
    getSignalState,
    getExecutionState,
    getPortfolioState,
    getRiskState,
    refresh,
  }

  return (
    <ProjectionContext.Provider value={value}>
      {children}
    </ProjectionContext.Provider>
  )
}

export function useProjection() {
  const context = useContext(ProjectionContext)
  if (!context) {
    throw new Error('useProjection must be used within ProjectionProvider')
  }
  return context
}

export function useMarketState() {
  const { getMarketState, isLoading } = useProjection()
  return { state: getMarketState(), isLoading }
}

export function useSignalState() {
  const { getSignalState, isLoading } = useProjection()
  return { state: getSignalState(), isLoading }
}

export function useExecutionState() {
  const { getExecutionState, isLoading } = useProjection()
  return { state: getExecutionState(), isLoading }
}

export function usePortfolioState() {
  const { getPortfolioState, isLoading } = useProjection()
  return { state: getPortfolioState(), isLoading }
}

export function useRiskState() {
  const { getRiskState, isLoading } = useProjection()
  return { state: getRiskState(), isLoading }
}
