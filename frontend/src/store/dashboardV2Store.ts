/**
 * Dashboard V2 Store - 拆分后的状态管理
 * 
 * 不同模块使用不同刷新频率：
 * - WebSocket 实时：prices, positions
 * - 高频（每秒）：prices, positions
 * - 中频（每分钟）：regime, risk, signal, factors
 * - 低频（每5分钟）：news, social, data-sources, traders, macro, etf
 */

import { create } from 'zustand'
import {
  fetchPrices,
  fetchPositions,
  fetchRegime,
  fetchRisk,
  fetchSignal,
  fetchFactors,
  fetchCompositeScore,
  fetchNews,
  fetchSocialPosts,
  fetchDataSources,
  fetchTraders,
  fetchMacro,
  fetchFearGreed,
  fetchEtf,
  type PriceData,
  type RegimeData,
  type RiskData,
  type SignalData,
  type PositionData,
  type NewsItem,
  type SocialPost,
  type FactorData,
  type DataSourceStatus,
  type TraderData,
  type MacroData,
  type FearGreedData,
  type EtfData,
} from '../services/api/dashboardApi'
import { wsService } from '../services/websocket/wsService'

interface DashboardV2State {
  // WebSocket 连接状态
  wsConnected: boolean
  setWsConnected: (connected: boolean) => void
  
  // 高频数据（每秒）
  prices: PriceData[]
  positions: PositionData[]
  
  // 中频数据（每分钟）
  regime: RegimeData | null
  risk: RiskData | null
  signal: SignalData | null
  factors: FactorData[]
  compositeScore: number
  
  // 低频数据（每5分钟）
  newsPage: { items: NewsItem[]; total: number; hasMore: boolean; page: number }
  socialPage: { items: SocialPost[]; total: number; hasMore: boolean; page: number }
  dataSources: DataSourceStatus[]
  traders: TraderData[]
  macro: MacroData | null
  fearGreed: FearGreedData | null
  etf: EtfData | null
  
  // 加载状态
  loading: {
    prices: boolean
    positions: boolean
    regime: boolean
    risk: boolean
    signal: boolean
    factors: boolean
    news: boolean
    social: boolean
  }
  
  // 最后更新时间
  lastUpdate: {
    prices: Date | null
    positions: Date | null
    regime: Date | null
    risk: Date | null
    signal: Date | null
    factors: Date | null
    news: Date | null
    social: Date | null
  }
  
  // WebSocket 订阅
  subscribeWebSocket: () => void
  unsubscribeWebSocket: () => void
  
  // Actions - 高频
  refreshPrices: () => Promise<void>
  refreshPositions: () => Promise<void>
  
  // Actions - 中频
  refreshRegime: (symbol?: string) => Promise<void>
  refreshRisk: () => Promise<void>
  refreshSignal: (symbol?: string) => Promise<void>
  refreshFactors: () => Promise<void>
  refreshCompositeScore: () => Promise<void>
  
  // Actions - 低频
  loadNews: (page?: number, pageSize?: number) => Promise<void>
  loadMoreNews: () => Promise<void>
  loadSocial: (page?: number, pageSize?: number) => Promise<void>
  loadMoreSocial: () => Promise<void>
  refreshDataSources: () => Promise<void>
  refreshTraders: () => Promise<void>
  refreshMacro: () => Promise<void>
  refreshFearGreed: () => Promise<void>
  refreshEtf: () => Promise<void>
  
  // 批量刷新
  refreshHighFrequency: () => Promise<void>
  refreshMediumFrequency: () => Promise<void>
  refreshLowFrequency: () => Promise<void>
}

export const useDashboardV2Store = create<DashboardV2State>((set, get) => ({
  // 初始状态
  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),
  
  prices: [],
  positions: [],
  regime: null,
  risk: null,
  signal: null,
  factors: [],
  compositeScore: 0.5,
  newsPage: { items: [], total: 0, hasMore: false, page: 0 },
  socialPage: { items: [], total: 0, hasMore: false, page: 0 },
  dataSources: [],
  traders: [],
  macro: null,
  fearGreed: null,
  etf: null,
  
  loading: {
    prices: false,
    positions: false,
    regime: false,
    risk: false,
    signal: false,
    factors: false,
    news: false,
    social: false,
  },
  
  lastUpdate: {
    prices: null,
    positions: null,
    regime: null,
    risk: null,
    signal: null,
    factors: null,
    news: null,
    social: null,
  },
  
  // WebSocket 订阅
  subscribeWebSocket: () => {
    if (wsService.isConnected) {
      wsService.subscribe(['channel:prices', 'channel:position'])
      
      wsService.on('channel:prices', (data) => {
        if (data.type === 'price_update') {
          const priceData = data.data as PriceData
          set(state => {
            const existingIndex = state.prices.findIndex(p => p.symbol === priceData.symbol)
            if (existingIndex >= 0) {
              const newPrices = [...state.prices]
              newPrices[existingIndex] = priceData
              return { prices: newPrices, lastUpdate: { ...state.lastUpdate, prices: new Date() } }
            }
            return { prices: [...state.prices, priceData], lastUpdate: { ...state.lastUpdate, prices: new Date() } }
          })
        } else if (data.type === 'prices_snapshot') {
          const snapshot = data.data as Record<string, PriceData>
          const pricesList = Object.values(snapshot)
          set(state => ({
            prices: pricesList,
            lastUpdate: { ...state.lastUpdate, prices: new Date() },
          }))
        }
      })
      
      wsService.on('channel:position', (data) => {
        if (data.type === 'position_update') {
          get().refreshPositions()
        }
      })
      
      set({ wsConnected: true })
    }
  },
  
  unsubscribeWebSocket: () => {
    wsService.unsubscribe(['channel:prices', 'channel:position'])
    set({ wsConnected: false })
  },
  
  // 高频刷新
  refreshPrices: async () => {
    set(state => ({ loading: { ...state.loading, prices: true } }))
    try {
      const prices = await fetchPrices()
      set(state => ({
        prices,
        loading: { ...state.loading, prices: false },
        lastUpdate: { ...state.lastUpdate, prices: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, prices: false } }))
    }
  },
  
  refreshPositions: async () => {
    set(state => ({ loading: { ...state.loading, positions: true } }))
    try {
      const positions = await fetchPositions()
      set(state => ({
        positions,
        loading: { ...state.loading, positions: false },
        lastUpdate: { ...state.lastUpdate, positions: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, positions: false } }))
    }
  },
  
  // 中频刷新
  refreshRegime: async (symbol = 'BTC') => {
    set(state => ({ loading: { ...state.loading, regime: true } }))
    try {
      const regime = await fetchRegime(symbol)
      set(state => ({
        regime,
        loading: { ...state.loading, regime: false },
        lastUpdate: { ...state.lastUpdate, regime: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, regime: false } }))
    }
  },
  
  refreshRisk: async () => {
    set(state => ({ loading: { ...state.loading, risk: true } }))
    try {
      const risk = await fetchRisk()
      set(state => ({
        risk,
        loading: { ...state.loading, risk: false },
        lastUpdate: { ...state.lastUpdate, risk: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, risk: false } }))
    }
  },
  
  refreshSignal: async (symbol = 'BTC') => {
    set(state => ({ loading: { ...state.loading, signal: true } }))
    try {
      const signal = await fetchSignal(symbol)
      set(state => ({
        signal,
        loading: { ...state.loading, signal: false },
        lastUpdate: { ...state.lastUpdate, signal: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, signal: false } }))
    }
  },
  
  refreshFactors: async () => {
    set(state => ({ loading: { ...state.loading, factors: true } }))
    try {
      const factors = await fetchFactors()
      set(state => ({
        factors,
        loading: { ...state.loading, factors: false },
        lastUpdate: { ...state.lastUpdate, factors: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, factors: false } }))
    }
  },
  
  refreshCompositeScore: async () => {
    try {
      const compositeScore = await fetchCompositeScore()
      set({ compositeScore })
    } catch {}
  },
  
  // 低频刷新
  loadNews: async (page = 1, pageSize = 10) => {
    set(state => ({ loading: { ...state.loading, news: true } }))
    try {
      const result = await fetchNews(page, pageSize)
      set(state => ({
        newsPage: {
          items: result.items,
          total: result.total,
          hasMore: result.hasMore,
          page: result.page,
        },
        loading: { ...state.loading, news: false },
        lastUpdate: { ...state.lastUpdate, news: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, news: false } }))
    }
  },
  
  loadMoreNews: async () => {
    const { newsPage, loading } = get()
    if (loading.news || !newsPage.hasMore) return
    
    set(state => ({ loading: { ...state.loading, news: true } }))
    try {
      const result = await fetchNews(newsPage.page + 1, 10)
      set(state => ({
        newsPage: {
          items: [...state.newsPage.items, ...result.items],
          total: result.total,
          hasMore: result.hasMore,
          page: result.page,
        },
        loading: { ...state.loading, news: false },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, news: false } }))
    }
  },
  
  loadSocial: async (page = 1, pageSize = 10) => {
    set(state => ({ loading: { ...state.loading, social: true } }))
    try {
      const result = await fetchSocialPosts(page, pageSize)
      set(state => ({
        socialPage: {
          items: result.items,
          total: result.total,
          hasMore: result.hasMore,
          page: result.page,
        },
        loading: { ...state.loading, social: false },
        lastUpdate: { ...state.lastUpdate, social: new Date() },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, social: false } }))
    }
  },
  
  loadMoreSocial: async () => {
    const { socialPage, loading } = get()
    if (loading.social || !socialPage.hasMore) return
    
    set(state => ({ loading: { ...state.loading, social: true } }))
    try {
      const result = await fetchSocialPosts(socialPage.page + 1, 10)
      set(state => ({
        socialPage: {
          items: [...state.socialPage.items, ...result.items],
          total: result.total,
          hasMore: result.hasMore,
          page: result.page,
        },
        loading: { ...state.loading, social: false },
      }))
    } catch {
      set(state => ({ loading: { ...state.loading, social: false } }))
    }
  },
  
  refreshDataSources: async () => {
    try {
      const dataSources = await fetchDataSources()
      set({ dataSources })
    } catch {}
  },
  
  refreshTraders: async () => {
    try {
      const traders = await fetchTraders()
      set({ traders })
    } catch {}
  },
  
  refreshMacro: async () => {
    try {
      const macro = await fetchMacro()
      set({ macro })
    } catch {}
  },
  
  refreshFearGreed: async () => {
    try {
      const fearGreed = await fetchFearGreed()
      set({ fearGreed })
    } catch {}
  },
  
  refreshEtf: async () => {
    try {
      const etf = await fetchEtf()
      set({ etf })
    } catch {}
  },
  
  // 批量刷新
  refreshHighFrequency: async () => {
    await Promise.all([
      get().refreshPrices(),
      get().refreshPositions(),
    ])
  },
  
  refreshMediumFrequency: async () => {
    await Promise.all([
      get().refreshRegime(),
      get().refreshRisk(),
      get().refreshSignal(),
      get().refreshFactors(),
      get().refreshCompositeScore(),
    ])
  },
  
  refreshLowFrequency: async () => {
    await Promise.all([
      get().loadNews(),
      get().loadSocial(),
      get().refreshDataSources(),
      get().refreshTraders(),
      get().refreshMacro(),
      get().refreshFearGreed(),
      get().refreshEtf(),
    ])
  },
}))
