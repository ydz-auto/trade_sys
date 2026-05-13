
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const EXECUTION_BASE = '/execution/api/v1'
const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true'

import * as mockData from '../mock'
import type { PriceData, RegimeState, RiskIndex, Signal, Factor, Position, WeightVersion, DataSourceStatus, Trader, SocialPost, NewsItem } from '../../types'

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
  const response = await fetch(`${API_BASE}${endpoint}`, options)
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }
  return response.json()
}

async function fetchExecution<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${EXECUTION_BASE}${endpoint}`, options)
  if (!response.ok) {
    throw new Error(`Execution API Error: ${response.statusText}`)
  }
  return response.json()
}

export async function fetchAllTradingData(): Promise<TradingData> {
  if (USE_MOCK) {
    return {
      prices: mockData.mockPrices as PriceData[],
      compositeScore: mockData.mockCompositeScore,
      regime: mockData.mockRegime as RegimeState,
      risk: mockData.mockRisk as RiskIndex,
      signal: mockData.mockSignal as Signal,
      factors: mockData.mockFactors as Factor[],
      positions: mockData.mockPositions as Position[],
      weightVersions: mockData.mockWeightVersions as WeightVersion[],
      dataSources: mockData.mockDataSources as DataSourceStatus[],
      traders: mockData.mockTraders as Trader[],
      socialPosts: mockData.mockSocialPosts as SocialPost[],
      news: []
    }
  }

  const [data] = await Promise.all([
    fetchReal<TradingData>('/trading/dashboard'),
  ])
  return data
}

export async function fetchNews(limit: number = 20): Promise<NewsItem[]> {
  if (USE_MOCK) {
    return []
  }
  return fetchReal<NewsItem[]>(`/news?limit=${limit}`)
}

export async function fetchPrices(): Promise<PriceData[]> {
  if (USE_MOCK) {
    return mockData.mockPrices as PriceData[]
  }
  return fetchReal<PriceData[]>('/prices')
}

export async function fetchFactors(): Promise<Factor[]> {
  if (USE_MOCK) {
    return mockData.mockFactors as Factor[]
  }
  return fetchReal<Factor[]>('/factors')
}

export async function fetchRegime(): Promise<RegimeState> {
  if (USE_MOCK) {
    return mockData.mockRegime as RegimeState
  }
  return fetchReal<RegimeState>('/regime')
}

export async function fetchRisk(): Promise<RiskIndex> {
  if (USE_MOCK) {
    return mockData.mockRisk as RiskIndex
  }
  return fetchReal<RiskIndex>('/risk')
}

export async function fetchSignal(): Promise<Signal> {
  if (USE_MOCK) {
    return mockData.mockSignal as Signal
  }
  return fetchReal<Signal>('/signal')
}

export async function fetchPositions(): Promise<Position[]> {
  if (USE_MOCK) {
    return mockData.mockPositions as Position[]
  }
  try {
    return await fetchExecution<Position[]>('/positions')
  } catch {
    return fetchReal<Position[]>('/positions')
  }
}

export async function fetchWeightVersions(): Promise<WeightVersion[]> {
  if (USE_MOCK) {
    return mockData.mockWeightVersions as WeightVersion[]
  }
  return fetchReal<WeightVersion[]>('/weights/versions')
}

// === 多数据源价格 API ===
import type { PriceComparison, PriceSourceStatus } from '../../types'

/**
 * 获取所有交易所的同一交易对价格（用于对比显示）
 * @param symbols 交易对列表，如 "BTC,ETH"
 */
export async function fetchPricesFromAllSources(symbols: string = 'BTC,ETH,SOL'): Promise<PriceData[]> {
  if (USE_MOCK) {
    // 模拟多数据源数据
    const basePrices = mockData.mockPrices as PriceData[]
    const exchanges = ['binance', 'coingecko', 'okx']
    const result: PriceData[] = []
    
    basePrices.forEach(price => {
      exchanges.forEach(exchange => {
        result.push({
          symbol: price.symbol,
          price: price.price * (1 + (Math.random() - 0.5) * 0.001), // 微小差异
          change24h: price.change24h,
          exchange
        })
      })
    })
    
    return result
  }
  
  return fetchReal<PriceData[]>(`/prices?symbols=${symbols}&all_sources=true`)
}

/**
 * 获取指定交易对的多交易所价格对比分析
 * @param symbol 交易对，如 "BTC"
 */
export async function fetchPriceComparison(symbol: string = 'BTC'): Promise<PriceComparison> {
  if (USE_MOCK) {
    // 模拟价格对比数据
    return {
      symbol: `${symbol}/USDT`,
      prices: [
        { exchange: 'binance', price: 81018.18, change24h: -0.20, volume24h: 966464900, latencyMs: 586 },
        { exchange: 'coingecko', price: 81000.00, change24h: -0.20, volume24h: 31609042937, latencyMs: 610 },
        { exchange: 'okx', price: 81015.20, change24h: 0.00, volume24h: 940010508, latencyMs: 721 }
      ],
      priceSpread: 0.0224,
      bestBid: 'binance',
      bestAsk: 'coingecko',
      timestamp: new Date().toISOString()
    }
  }
  
  return fetchReal<PriceComparison>(`/prices/compare?symbol=${symbol}`)
}

/**
 * 获取价格数据源状态（熔断器状态、可用性等）
 */
export async function fetchPriceSourcesStatus(): Promise<Record<string, PriceSourceStatus>> {
  if (USE_MOCK) {
    return {
      binance: {
        name: 'Binance',
        priority: 1,
        circuitBreaker: { state: 'closed', failureCount: 0 },
        status: { available: true, latencyMs: 586 }
      },
      coingecko: {
        name: 'CoinGecko',
        priority: 2,
        circuitBreaker: { state: 'closed', failureCount: 0 },
        status: { available: true, latencyMs: 610 }
      },
      okx: {
        name: 'OKX',
        priority: 3,
        circuitBreaker: { state: 'closed', failureCount: 0 },
        status: { available: true, latencyMs: 721 }
      }
    }
  }
  
  const response = await fetchReal<{ sources: Record<string, PriceSourceStatus> }>('/prices/sources')
  return response.sources
}

export async function updateFactorWeight(type: string, weight: number): Promise<void> {
  if (USE_MOCK) {
    return
  }
  await fetch(`${API_BASE}/factors/${type}/weight`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weight }),
  })
}

// === 执行服务新增API ===
export async function executeOrder(request: ExecuteOrderRequest): Promise<ExecuteOrderResponse> {
  if (USE_MOCK) {
    return {
      success: true,
      orderId: 'mock-' + Date.now(),
      status: 'filled'
    }
  }
  return fetchExecution<ExecuteOrderResponse>('/orders/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  })
}

export async function fetchOrders(): Promise<any[]> {
  if (USE_MOCK) {
    return []
  }
  return fetchExecution<any[]>('/orders')
}

export async function closePosition(symbol: string, _exchange: string = 'BINANCE', _marketType: string = 'USDT_FUTURES'): Promise<ExecuteOrderResponse> {
  if (USE_MOCK) {
    return {
      success: true,
      orderId: 'close-' + Date.now()
    }
  }
  return fetchExecution<ExecuteOrderResponse>(`/positions/${symbol}/close`, {
    method: 'POST'
  })
}
