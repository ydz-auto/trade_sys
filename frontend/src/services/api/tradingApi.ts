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
    }
  }

  const [data] = await Promise.all([
    fetchReal<TradingData>('/trading/dashboard'),
  ])
  return data
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
  return fetchReal<Position[]>('/positions')
}

export async function fetchWeightVersions(): Promise<WeightVersion[]> {
  if (USE_MOCK) {
    return mockData.mockWeightVersions as WeightVersion[]
  }
  return fetchReal<WeightVersion[]>('/weights/versions')
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
