/**
 * Runtime Provider - 统一的 Runtime Provider 组件
 *
 * 为所有页面提供 Runtime State
 */

import React, { createContext, useContext, useEffect, ReactNode } from 'react'
import { useRuntimeStore, initializeRuntime } from '../store/runtimeStore'
import type { RuntimeState, RuntimeConfig } from '../types'

interface RuntimeContextType {
  // State
  activeRuntimeId: string | null
  activeRuntimeState: RuntimeState | null
  availableRuntimes: RuntimeConfig[]

  // Quick access
  market: RuntimeState['market'] | null
  signals: RuntimeState['signals'] | null
  risk: RuntimeState['risk'] | null
  pnl: RuntimeState['pnl'] | null
  ai: RuntimeState['ai'] | null
  features: RuntimeState['features'] | null

  // Actions
  switchRuntime: (runtimeId: string) => void
  createRuntime: (config: RuntimeConfig) => string
  destroyRuntime: (runtimeId: string) => boolean

  // Status
  isConnected: boolean
  isLive: boolean
}

const RuntimeContext = createContext<RuntimeContextType | undefined>(undefined)

interface RuntimeProviderProps {
  children: ReactNode
  autoInitialize?: boolean
}

export function RuntimeProvider({ 
  children, 
  autoInitialize = true 
}: RuntimeProviderProps) {
  const {
    activeRuntimeId,
    activeRuntimeState,
    availableRuntimes,
    switchRuntime,
    createRuntime,
    destroyRuntime,
    getMarketState,
    getSignalsState,
    getRiskState,
    getPnLState,
    getAIState,
    getFeaturesState,
    initialize,
  } = useRuntimeStore()

  useEffect(() => {
    if (autoInitialize) {
      initializeRuntime()
    }
  }, [autoInitialize])

  const value: RuntimeContextType = {
    activeRuntimeId,
    activeRuntimeState,
    availableRuntimes,
    market: getMarketState(),
    signals: getSignalsState(),
    risk: getRiskState(),
    pnl: getPnLState(),
    ai: getAIState(),
    features: getFeaturesState(),
    switchRuntime,
    createRuntime,
    destroyRuntime,
    isConnected: activeRuntimeState?.status.status !== 'error' && activeRuntimeState?.status.status !== 'idle',
    isLive: activeRuntimeState?.status.type === 'live',
  }

  return (
    <RuntimeContext.Provider value={value}>
      {children}
    </RuntimeContext.Provider>
  )
}

export function useRuntime(): RuntimeContextType {
  const context = useContext(RuntimeContext)
  if (context === undefined) {
    throw new Error('useRuntime must be used within a RuntimeProvider')
  }
  return context
}

export function useRuntimeState<T extends keyof RuntimeState>(
  key: T
): RuntimeState[T] | null {
  const { activeRuntimeState } = useRuntime()
  return activeRuntimeState ? activeRuntimeState[key] : null
}

export function useMarketState() {
  return useRuntimeState('market')
}

export function useSignalsState() {
  return useRuntimeState('signals')
}

export function useRiskState() {
  return useRuntimeState('risk')
}

export function usePnLState() {
  return useRuntimeState('pnl')
}

export function useAIState() {
  return useRuntimeState('ai')
}

export function useFeaturesState() {
  return useRuntimeState('features')
}

export function useRuntimeStatus() {
  return useRuntimeState('status')
}

export function useActiveRuntime() {
  const { activeRuntimeId, activeRuntimeState, availableRuntimes } = useRuntime()
  return {
    id: activeRuntimeId,
    state: activeRuntimeState,
    config: availableRuntimes.find(r => r.id === activeRuntimeId),
  }
}

export function useRuntimeSwitcher() {
  const { availableRuntimes, activeRuntimeId, switchRuntime } = useRuntime()
  return {
    availableRuntimes,
    activeRuntimeId,
    switchRuntime,
  }
}
