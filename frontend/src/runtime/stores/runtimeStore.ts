import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

export type TradingMode = 'backtest' | 'paper' | 'live'
export type RuntimeState = 'starting' | 'running' | 'paused' | 'degraded' | 'stopped' | 'failed' | 'recovering'

export interface RuntimeInfo {
  id: string
  type: string
  state: RuntimeState
  mode?: TradingMode
  priority: number
}

interface RuntimeStore {
  mode: TradingMode
  modeColor: string
  modeWarning: string | null
  isRunning: boolean
  activeRuntimes: number
  failedRuntimes: number
  uptimeSeconds: number
  runtimes: RuntimeInfo[]
  lastUpdate: string | null
  
  setMode: (mode: TradingMode) => void
  setModeConfig: (color: string, warning: string | null) => void
  setOrchestratorStatus: (status: {
    isRunning: boolean
    activeRuntimes: number
    failedRuntimes: number
    uptimeSeconds: number
  }) => void
  setRuntimes: (runtimes: RuntimeInfo[]) => void
  updateRuntime: (id: string, state: RuntimeState) => void
}

const modeColors: Record<TradingMode, string> = {
  backtest: '#3B82F6',
  paper: '#F59E0B',
  live: '#EF4444',
}

const modeWarnings: Record<TradingMode, string | null> = {
  backtest: null,
  paper: 'Paper Trading: 真实行情 + 模拟下单',
  live: '⚠️ LIVE MODE: 真实交易',
}

export const useRuntimeStore = create<RuntimeStore>()(
  subscribeWithSelector((set, get) => ({
    mode: 'paper',
    modeColor: modeColors.paper,
    modeWarning: modeWarnings.paper,
    isRunning: false,
    activeRuntimes: 0,
    failedRuntimes: 0,
    uptimeSeconds: 0,
    runtimes: [],
    lastUpdate: null,

    setMode: (mode) => set({
      mode,
      modeColor: modeColors[mode],
      modeWarning: modeWarnings[mode],
      lastUpdate: new Date().toISOString(),
    }),

    setModeConfig: (color, warning) => set({
      modeColor: color,
      modeWarning: warning,
      lastUpdate: new Date().toISOString(),
    }),

    setOrchestratorStatus: (status) => set({
      ...status,
      lastUpdate: new Date().toISOString(),
    }),

    setRuntimes: (runtimes) => set({
      runtimes,
      lastUpdate: new Date().toISOString(),
    }),

    updateRuntime: (id, state) => set((s) => ({
      runtimes: s.runtimes.map((r) =>
        r.id === id ? { ...r, state } : r
      ),
      lastUpdate: new Date().toISOString(),
    })),
  }))
)

export function getModeBadgeClass(mode: TradingMode): string {
  switch (mode) {
    case 'backtest':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    case 'paper':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
    case 'live':
      return 'bg-red-500/20 text-red-400 border-red-500/30'
  }
}

export function getModeLabel(mode: TradingMode): string {
  switch (mode) {
    case 'backtest':
      return 'BACKTEST'
    case 'paper':
      return 'PAPER'
    case 'live':
      return 'LIVE'
  }
}
