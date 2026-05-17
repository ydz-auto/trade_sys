/**
 * Realtime Store - 实时状态管理
 * 
 * 从 WebSocket 接收实时更新，更新 Store
 */

import { create } from 'zustand'
import { wsService, type ChannelType } from '../services/websocket/wsService'
import type { 
  PriceData, 
  RegimeState, 
  Position
} from '../types'

interface TimelineEvent {
  event_id: string
  event_type: string
  symbol: string
  timestamp: string
  display_time?: string
  title: string
  description: string
  severity: string
}

interface Decision {
  decision_id: string
  symbol: string
  action: string
  quantity: number
  confidence: number
  reason: string
  status: string
  approved: boolean | null
  timestamp: string
}

interface RealtimeState {
  connected: boolean
  setConnected: (connected: boolean) => void

  dashboard: {
    prices: Record<string, PriceData>
    signals: Record<string, any>
    regime: Record<string, RegimeState>
    compositeScore: number
    lastUpdate: string | null
  }
  setDashboard: (dashboard: Partial<RealtimeState['dashboard']>) => void

  decisions: {
    latest: Record<string, Decision>
    history: Decision[]
    stats: {
      total: number
      long: number
      short: number
      hold: number
      approved: number
      rejected: number
      avg_confidence: number
    }
  }
  setDecisions: (decisions: Partial<RealtimeState['decisions']>) => void

  risk: {
    level: string
    score: number
    components: {
      volatility: number
      flow: number
      sentiment: number
      macro: number
    }
    warnings: string[]
  }
  setRisk: (risk: Partial<RealtimeState['risk']>) => void

  positions: {
    current: Record<string, Position>
    pnl: {
      total_unrealized: number
      total_realized: number
      total_pnl: number
      positions_count: number
    }
  }
  setPositions: (positions: Partial<RealtimeState['positions']>) => void

  timeline: TimelineEvent[]
  addTimelineEvent: (event: TimelineEvent) => void
  setTimeline: (events: TimelineEvent[]) => void

  subscribe: (channels?: ChannelType[]) => void
  unsubscribe: (channels: ChannelType[]) => void
}

const DEFAULT_DASHBOARD = {
  prices: {},
  signals: {},
  regime: {},
  compositeScore: 0.5,
  lastUpdate: null,
}

const DEFAULT_DECISIONS = {
  latest: {},
  history: [],
  stats: {
    total: 0,
    long: 0,
    short: 0,
    hold: 0,
    approved: 0,
    rejected: 0,
    avg_confidence: 0,
  },
}

const DEFAULT_RISK = {
  level: 'low',
  score: 0,
  components: {
    volatility: 0,
    flow: 0,
    sentiment: 0,
    macro: 0,
  },
  warnings: [],
}

const DEFAULT_POSITIONS = {
  current: {},
  pnl: {
    total_unrealized: 0,
    total_realized: 0,
    total_pnl: 0,
    positions_count: 0,
  },
}

export const useRealtimeStore = create<RealtimeState>((set, get) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),

  dashboard: DEFAULT_DASHBOARD,
  setDashboard: (dashboard) => set((state) => ({
    dashboard: { ...state.dashboard, ...dashboard }
  })),

  decisions: DEFAULT_DECISIONS,
  setDecisions: (decisions) => set((state) => ({
    decisions: { ...state.decisions, ...decisions }
  })),

  risk: DEFAULT_RISK,
  setRisk: (risk) => set((state) => ({
    risk: { ...state.risk, ...risk }
  })),

  positions: DEFAULT_POSITIONS,
  setPositions: (positions) => set((state) => ({
    positions: { ...state.positions, ...positions }
  })),

  timeline: [],
  addTimelineEvent: (event) => set((state) => ({
    timeline: [event, ...state.timeline].slice(0, 100)
  })),
  setTimeline: (events) => set({ timeline: events }),

  subscribe: (channels) => {
    const defaultChannels: ChannelType[] = [
      'dashboard',
      'decision',
      'risk',
      'position',
      'timeline',
    ]
    const subs = channels || defaultChannels
    const channelNames = subs.map(ch => `channel:${ch}`)
    
    wsService.subscribe(channelNames)
    
    wsService.on('channel:dashboard', (data) => {
      if (data.type === 'data_update') {
        set({ dashboard: data.data })
      } else if (data.type === 'state_update') {
        set({ dashboard: data.data })
      }
    })

    wsService.on('channel:decision', (data) => {
      if (data.type === 'data_update') {
        const decision = data.data
        if (decision && decision.symbol) {
          set((state) => ({
            decisions: {
              ...state.decisions,
              latest: {
                ...state.decisions.latest,
                [decision.symbol]: decision,
              },
              history: [decision, ...state.decisions.history].slice(0, 100),
            },
          }))
        }
      } else if (data.type === 'new_decision') {
        const decision = data.decision
        set((state) => ({
          decisions: {
            ...state.decisions,
            latest: {
              ...state.decisions.latest,
              [decision.symbol]: decision,
            },
            history: [decision, ...state.decisions.history].slice(0, 100),
          },
        }))
      }
    })

    wsService.on('channel:risk', (data) => {
      if (data.type === 'data_update') {
        set((state) => ({
          risk: {
            ...state.risk,
            ...data.data,
          },
        }))
      } else if (data.type === 'risk_check') {
        set((state) => ({
          risk: {
            ...state.risk,
            level: data.risk_level,
          },
        }))
      }
    })

    wsService.on('channel:position', (data) => {
      if (data.type === 'data_update') {
        const position = data.data
        const symbol = data.event_type === 'position' ? (position?.symbol || 'BTC') : 'BTC'
        if (position) {
          set((state) => ({
            positions: {
              ...state.positions,
              current: {
                ...state.positions.current,
                [symbol]: position,
              },
            },
          }))
        }
      } else if (data.type === 'position_update') {
        const position = data.position
        if (position) {
          set((state) => ({
            positions: {
              ...state.positions,
              current: {
                ...state.positions.current,
                [data.symbol]: position,
              },
            },
          }))
        }
      }
    })

    wsService.on('channel:timeline', (data) => {
      if (data.type === 'data_update') {
        const event = data.data
        if (event) {
          get().addTimelineEvent(event)
        }
      } else if (data.type === 'new_event') {
        get().addTimelineEvent(data.event)
      }
    })
  },

  unsubscribe: (channels) => {
    const channelNames = channels.map(ch => `channel:${ch}`)
    wsService.unsubscribe(channelNames)
  },
}))

export function initializeRealtime() {
  wsService.connect()
    .then(() => {
      useRealtimeStore.getState().setConnected(true)
      useRealtimeStore.getState().subscribe()
    })
    .catch(console.error)

  wsService.onMessage((msg) => {
    if (!msg.channel) {
      useRealtimeStore.getState().setConnected(true)
    }
  })
}
