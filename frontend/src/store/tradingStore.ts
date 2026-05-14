import { create } from 'zustand'
import type { Factor, PriceData, RegimeState, RiskIndex, Signal, SystemMode, Position, WeightVersion, DataSourceStatus, Trader, SocialPost, NewsItem } from '../types'

interface FearGreedData {
  value: number
  classification: string
  timestamp: string
}

interface MacroData {
  gold: { price: number; change: number }
  usd_index: { value: number; change: number }
  oil: { price: number; change: number }
}

interface EtfData {
  symbol: string
  net_flow: number
  inflow: number
  outflow: number
  confidence: number
}

interface TradingState {
  mode: SystemMode
  setMode: (mode: SystemMode) => void

  prices: PriceData[]
  setPrices: (prices: PriceData[]) => void

  compositeScore: number
  setCompositeScore: (score: number) => void

  regime: RegimeState
  setRegime: (regime: RegimeState | null) => void

  risk: RiskIndex
  setRisk: (risk: RiskIndex | null) => void

  signal: Signal
  setSignal: (signal: Signal | null) => void

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

  fearGreed: FearGreedData | null
  setFearGreed: (data: FearGreedData | null) => void

  macro: MacroData | null
  setMacro: (data: MacroData | null) => void

  etf: EtfData | null
  setEtf: (data: EtfData | null) => void

  isConnected: boolean
  setConnected: (connected: boolean) => void

  lastUpdate: Date
  setLastUpdate: (date: Date) => void
}

const DEFAULT_REGIME: RegimeState = { state: 'UNCERTAIN', confidence: 0 }
const DEFAULT_RISK: RiskIndex = {
  total: 0,
  level: 'medium',
  components: { volatility: 0, flow: 0, sentiment: 0, macro: 0 }
}
const DEFAULT_SIGNAL: Signal = {
  action: 'HOLD',
  confidence: 0,
  riskLevel: 'LOW',
  reason: ''
}

export const useTradingStore = create<TradingState>((set) => ({
  mode: 'LIVE',
  setMode: (mode) => set({ mode }),

  prices: [],
  setPrices: (prices) => set({ prices: prices || [] }),

  compositeScore: 0,
  setCompositeScore: (compositeScore) => set({ compositeScore: compositeScore || 0 }),

  regime: DEFAULT_REGIME,
  setRegime: (regime) => set({ regime: regime || DEFAULT_REGIME }),

  risk: DEFAULT_RISK,
  setRisk: (risk) => set({ risk: risk || DEFAULT_RISK }),

  signal: DEFAULT_SIGNAL,
  setSignal: (signal) => set({ signal: signal || DEFAULT_SIGNAL }),

  factors: [],
  setFactors: (factors) => set({ factors: factors || [] }),
  updateFactorWeight: (type, weight) =>
    set((state) => ({
      factors: state.factors.map((f) =>
        f.type === type ? { ...f, weight } : f
      ),
    })),

  positions: [],
  setPositions: (positions) => set({ positions: positions || [] }),

  weightVersions: [],
  setWeightVersions: (weightVersions) => set({ weightVersions: weightVersions || [] }),
  currentVersion: '',
  setCurrentVersion: (currentVersion) => set({ currentVersion }),

  dataSources: [],
  setDataSources: (dataSources) => set({ dataSources: dataSources || [] }),

  traders: [],
  setTraders: (traders) => set({ traders: traders || [] }),

  socialPosts: [],
  setSocialPosts: (socialPosts) => set({ socialPosts: socialPosts || [] }),

  news: [],
  setNews: (news) => set({ news: news || [] }),

  fearGreed: null,
  setFearGreed: (fearGreed) => set({ fearGreed }),

  macro: null,
  setMacro: (macro) => set({ macro }),

  etf: null,
  setEtf: (etf) => set({ etf }),

  isConnected: false,
  setConnected: (isConnected) => set({ isConnected }),

  lastUpdate: new Date(),
  setLastUpdate: (lastUpdate) => set({ lastUpdate }),
}))
