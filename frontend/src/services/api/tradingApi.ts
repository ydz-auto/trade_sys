
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const EXECUTION_BASE = '/execution/api/v1'

import type { PriceData, RegimeState, RiskIndex, Signal, Factor, Position, WeightVersion, DataSourceStatus, Trader, SocialPost, NewsItem } from '../../types'

export interface FearGreedData {
  value: number
  classification: string
  timestamp: string
}

export interface MacroData {
  gold: { price: number; change: number }
  usd_index: { value: number; change: number }
  oil: { price: number; change: number }
}

export interface EtfData {
  symbol: string
  net_flow: number
  inflow: number
  outflow: number
  confidence: number
}

export interface TradingData {
  prices: PriceData[]
  compositeScore: number
  regime: RegimeState
  risk: RiskIndex
  signal: Signal
  factors: Factor[]
  positions: Position[]
  weightVersions: WeightVersion[]
  dataSources: DataSourceStatus[]
  traders: Trader[]
  socialPosts: SocialPost[]
  news: NewsItem[]
  fearGreed?: FearGreedData
  macro?: MacroData
  etf?: EtfData
}

export interface ExecuteOrderRequest {
  symbol: string
  side: string
  quantity: number
  price?: number
  orderType?: string
  exchange?: string
  marketType?: string
  leverage?: number
  reduceOnly?: boolean
}

export interface ExecuteOrderResponse {
  success: boolean
  orderId?: string
  error?: string
  status?: string
}

async function fetchReal<T>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options)
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error(`Fetch error for ${endpoint}:`, error)
    throw error
  }
}

async function fetchExecution<T>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${EXECUTION_BASE}${endpoint}`, options)
    if (!response.ok) {
      throw new Error(`Execution API Error: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error(`Execution fetch error for ${endpoint}:`, error)
    throw error
  }
}

export async function fetchAllTradingData(): Promise<TradingData> {
  try {
    const data = await fetchReal<TradingData>('/trading/dashboard')
    
    // 处理字段名映射
    const mappedData: TradingData = {
      ...data,
      prices: (data.prices || []).map(p => ({
        ...p,
        change24h: p.change24h ?? p.change_24h ?? 0
      }))
    }
    
    return mappedData
  } catch (error) {
    console.error('Error fetching trading data:', error)
    // 返回安全的默认值
    return {
      prices: [],
      compositeScore: 0,
      regime: { state: 'UNCERTAIN', confidence: 0 },
      risk: { total: 0, level: 'low', components: { volatility: 0, flow: 0, sentiment: 0, macro: 0 } },
      signal: { action: 'HOLD', confidence: 0, riskLevel: 'LOW', reason: '' },
      factors: [],
      positions: [],
      weightVersions: [],
      dataSources: [],
      traders: [],
      socialPosts: [],
      news: []
    }
  }
}

export async function fetchNews(limit: number = 20): Promise<NewsItem[]> {
  try {
    return await fetchReal<NewsItem[]>(`/news?limit=${limit}`)
  } catch (error) {
    console.error('Error fetching news:', error)
    return []
  }
}

export async function fetchPrices(): Promise<PriceData[]> {
  try {
    const data = await fetchReal<PriceData[]>('/prices')
    return (data || []).map(p => ({
      ...p,
      change24h: p.change24h ?? (p as any).change_24h ?? 0
    }))
  } catch (error) {
    console.error('Error fetching prices:', error)
    return []
  }
}

export async function fetchFactors(): Promise<Factor[]> {
  try {
    return await fetchReal<Factor[]>('/factors')
  } catch (error) {
    console.error('Error fetching factors:', error)
    return []
  }
}

export async function fetchRegime(): Promise<RegimeState | null> {
  try {
    return await fetchReal<RegimeState>('/regime')
  } catch (error) {
    console.error('Error fetching regime:', error)
    return null
  }
}

export async function fetchRisk(): Promise<RiskIndex | null> {
  try {
    return await fetchReal<RiskIndex>('/risk')
  } catch (error) {
    console.error('Error fetching risk:', error)
    return null
  }
}

export async function fetchSignal(): Promise<Signal | null> {
  try {
    return await fetchReal<Signal>('/signal')
  } catch (error) {
    console.error('Error fetching signal:', error)
    return null
  }
}

export async function fetchPositions(): Promise<Position[]> {
  try {
    try {
      return await fetchExecution<Position[]>('/positions')
    } catch {
      return await fetchReal<Position[]>('/positions')
    }
  } catch (error) {
    console.error('Error fetching positions:', error)
    return []
  }
}

export async function fetchWeightVersions(): Promise<WeightVersion[]> {
  try {
    return await fetchReal<WeightVersion[]>('/weights/versions')
  } catch (error) {
    console.error('Error fetching weight versions:', error)
    return []
  }
}

// === 多数据源价格 API ===
import type { PriceComparison, PriceSourceStatus } from '../../types'

/**
 * 获取所有交易所的同一交易对价格（用于对比显示）
 * @param symbols 交易对列表，如 "BTC,ETH"
 */
export async function fetchPricesFromAllSources(symbols: string = 'BTC,ETH,SOL'): Promise<PriceData[]> {
  try {
    return await fetchReal<PriceData[]>(`/prices?symbols=${symbols}&all_sources=true`)
  } catch (error) {
    console.error('Error fetching prices from all sources:', error)
    return []
  }
}

/**
 * 获取指定交易对的多交易所价格对比分析
 * @param symbol 交易对，如 "BTC"
 */
export async function fetchPriceComparison(symbol: string = 'BTC'): Promise<PriceComparison | null> {
  try {
    return await fetchReal<PriceComparison>(`/prices/compare?symbol=${symbol}`)
  } catch (error) {
    console.error('Error fetching price comparison:', error)
    return null
  }
}

/**
 * 获取价格数据源状态（熔断器状态、可用性等）
 */
export async function fetchPriceSourcesStatus(): Promise<Record<string, PriceSourceStatus>> {
  try {
    const response = await fetchReal<{ sources: Record<string, PriceSourceStatus> }>('/prices/sources')
    return response.sources || {}
  } catch (error) {
    console.error('Error fetching price sources status:', error)
    return {}
  }
}

export async function updateFactorWeight(type: string, weight: number): Promise<void> {
  try {
    await fetch(`${API_BASE}/factors/${type}/weight`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weight }),
    })
  } catch (error) {
    console.error('Error updating factor weight:', error)
    throw error
  }
}

// === 执行服务新增API ===
export async function executeOrder(request: ExecuteOrderRequest): Promise<ExecuteOrderResponse> {
  try {
    return await fetchExecution<ExecuteOrderResponse>('/orders/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    })
  } catch (error) {
    console.error('Error executing order:', error)
    return { success: false, error: String(error) }
  }
}

export async function fetchOrders(): Promise<any[]> {
  try {
    return await fetchExecution<any[]>('/orders')
  } catch (error) {
    console.error('Error fetching orders:', error)
    return []
  }
}

export async function closePosition(symbol: string, _exchange: string = 'BINANCE', _marketType: string = 'USDT_FUTURES'): Promise<ExecuteOrderResponse> {
  try {
    return await fetchExecution<ExecuteOrderResponse>(`/positions/${symbol}/close`, {
      method: 'POST'
    })
  } catch (error) {
    console.error('Error closing position:', error)
    return { success: false, error: String(error) }
  }
}
