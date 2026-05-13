import { create } from 'zustand'
import type { Factor, PriceData, RegimeState, RiskIndex, Signal, SystemMode, Position, WeightVersion, DataSourceStatus, Trader, SocialPost, NewsItem } from '../types'

interface TradingState {
  mode: SystemMode
  setMode: (mode: SystemMode) => void

  prices: PriceData[]
  setPrices: (prices: PriceData[]) => void

  compositeScore: number
  setCompositeScore: (score: number) => void

  regime: RegimeState
  setRegime: (regime: RegimeState) => void

  risk: RiskIndex
  setRisk: (risk: RiskIndex) => void

  signal: Signal
  setSignal: (signal: Signal) => void

  factors: Factor[]
  setFactors: (factors: Factor[]) => void
  updateFactorWeight: (type: Factor['type'], weight: number) => void

  positions: Position[]
  setPositions: (positions: Position[]) => void

  weightVersions: WeightVersion[]
  setWeightVersions: (versions: WeightVersion[]) => void
  currentVersion: string
  setCurrentVersion: (version: string) => void

  dataSources: DataSourceStatus[]
  setDataSources: (sources: DataSourceStatus[]) => void

  traders: Trader[]
  setTraders: (traders: Trader[]) => void

  socialPosts: SocialPost[]
  setSocialPosts: (posts: SocialPost[]) => void

  news: NewsItem[]
  setNews: (news: NewsItem[]) => void

  isConnected: boolean
  setConnected: (connected: boolean) => void

  lastUpdate: Date
  setLastUpdate: (date: Date) => void
}

export const useTradingStore = create<TradingState>((set) => ({
  mode: 'LIVE',
  setMode: (mode) => set({ mode }),

  prices: [],
  setPrices: (prices) => set({ prices }),

  compositeScore: 0,
  setCompositeScore: (compositeScore) => set({ compositeScore }),

  regime: { state: 'UNCERTAIN' as const, confidence: 0 },
  setRegime: (regime) => set({ regime }),

  risk: {
    total: 0,
    level: 'medium',
    components: { volatility: 0, flow: 0, sentiment: 0, macro: 0 },
  },
  setRisk: (risk) => set({ risk }),

  signal: {
    action: 'HOLD',
    confidence: 0,
    riskLevel: 'LOW',
    reason: '',
  },
  setSignal: (signal) => set({ signal }),

  factors: [],
  setFactors: (factors) => set({ factors }),
  updateFactorWeight: (type, weight) =>
    set((state) => ({
      factors: state.factors.map((f) =>
        f.type === type ? { ...f, weight } : f
      ),
    })),

  positions: [],
  setPositions: (positions) => set({ positions }),

  weightVersions: [],
  setWeightVersions: (weightVersions) => set({ weightVersions }),
  currentVersion: '',
  setCurrentVersion: (currentVersion) => set({ currentVersion }),

  dataSources: [],
  setDataSources: (dataSources) => set({ dataSources }),

  traders: [],
  setTraders: (traders) => set({ traders }),

  socialPosts: [],
  setSocialPosts: (socialPosts) => set({ socialPosts }),

  news: [],
  setNews: (news) => set({ news }),

  isConnected: false,
  setConnected: (isConnected) => set({ isConnected }),

  lastUpdate: new Date(),
  setLastUpdate: (lastUpdate) => set({ lastUpdate }),
}))
