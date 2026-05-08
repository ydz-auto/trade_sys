const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true'

import * as mockData from '../mock'
import type { PriceData, RegimeState, RiskIndex, Signal, Factor, Position, WeightVersion, DataSourceStatus, Trader, SocialPost } from '../../types'

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
}

async function fetchMock<T>(data: T): Promise<T> {
  await new Promise(resolve => setTimeout(resolve, 100))
  return data
}

async function fetchReal<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`)
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }
  return response.json()
}

export async function fetchAllTradingData(): Promise<TradingData> {
  if (USE_MOCK) {
    return {
      prices: await fetchMock(mockData.mockPrices),
      compositeScore: await fetchMock(mockData.mockCompositeScore),
      regime: await fetchMock(mockData.mockRegime),
      risk: await fetchMock(mockData.mockRisk),
      signal: await fetchMock(mockData.mockSignal),
      factors: await fetchMock(mockData.mockFactors),
      positions: await fetchMock(mockData.mockPositions),
      weightVersions: await fetchMock(mockData.mockWeightVersions),
      dataSources: await fetchMock(mockData.mockDataSources),
      traders: await fetchMock(mockData.mockTraders),
      socialPosts: await fetchMock(mockData.mockSocialPosts),
    }
  }

  const [data] = await Promise.all([
    fetchReal<TradingData>('/trading/dashboard'),
  ])
  return data
}

export async function fetchPrices(): Promise<PriceData[]> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockPrices)
  }
  return fetchReal<PriceData[]>('/prices')
}

export async function fetchFactors(): Promise<Factor[]> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockFactors)
  }
  return fetchReal<Factor[]>('/factors')
}

export async function fetchRegime(): Promise<RegimeState> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockRegime)
  }
  return fetchReal<RegimeState>('/regime')
}

export async function fetchRisk(): Promise<RiskIndex> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockRisk)
  }
  return fetchReal<RiskIndex>('/risk')
}

export async function fetchSignal(): Promise<Signal> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockSignal)
  }
  return fetchReal<Signal>('/signal')
}

export async function fetchPositions(): Promise<Position[]> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockPositions)
  }
  return fetchReal<Position[]>('/positions')
}

export async function fetchWeightVersions(): Promise<WeightVersion[]> {
  if (USE_MOCK) {
    return fetchMock(mockData.mockWeightVersions)
  }
  return fetchReal<WeightVersion[]>('/weights/versions')
}

export async function updateFactorWeight(type: string, weight: number): Promise<void> {
  if (USE_MOCK) {
    await fetchMock(null)
    return
  }
  await fetch(`${API_BASE}/factors/${type}/weight`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weight }),
  })
}
