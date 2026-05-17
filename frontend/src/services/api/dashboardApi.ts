/**
 * Dashboard V2 API - 拆分后的独立接口
 * 
 * 不同模块使用不同刷新频率：
 * - 高频（每秒）：prices, positions
 * - 中频（每分钟）：regime, risk, signal, factors
 * - 低频（每5分钟）：news, social, data-sources, traders
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// ============ Types ============

export interface PriceData {
  symbol: string
  price: number
  change24h: number
  volume_24h?: number
  exchange: string
}

export interface RegimeData {
  state: string
  confidence: number
  trendStrength?: number
}

export interface RiskData {
  total: number
  level: string
  components: {
    volatility: number
    flow: number
    sentiment: number
    macro: number
  }
}

export interface SignalData {
  action: string
  confidence: number
  riskLevel: string
  reason: string
  leverage?: number
  stop_loss_pct?: number
  take_profit_pct?: number
}

export interface PositionData {
  symbol: string
  side: string
  size: number
  entryPrice: number
  currentPrice?: number
  leverage: number
  pnl: number
  pnlPct?: number
  stopLoss?: number
  takeProfit?: number
  liquidationPrice?: number
  liquidationDistancePct?: number
  margin?: number
  marginRatio?: number
  riskLevel?: string
  fundingRate?: number
  fundingFeeEstimate?: number
}

export interface NewsItem {
  id: string
  title: string
  content: string
  source: string
  sentiment: string
  sentiment_score: number
  published: number
  url?: string
}

export interface SocialPost {
  id: string
  platform: string
  author: string
  authorAvatar?: string
  content: string
  sentiment: number
  likes?: number
  time?: string
  symbols?: string[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

export interface FactorData {
  type: string
  name: string
  nameEn?: string
  weight: number
  value: number
  confidence: number
  color?: string
}

export interface DataSourceStatus {
  name: string
  status: string
  delay?: string
  lastUpdate?: string
  recordsCount?: number
}

export interface TraderData {
  id?: string
  name: string
  platform?: string
  followers: number
  sentiment?: number
  recentPosition?: string
  symbol?: string
  winRate: number
}

export interface MacroData {
  gold: { price: number; change: number }
  usd_index: { value: number; change: number }
  oil: { price: number; change: number }
}

export interface FearGreedData {
  value: number
  classification: string
  timestamp: string
}

export interface EtfData {
  symbol: string
  net_flow: number
  inflow: number
  outflow: number
  confidence: number
}

// ============ Helper ============

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, options)
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }
  return response.json()
}

// ============ High Frequency APIs (每秒刷新) ============

export async function fetchPrices(): Promise<PriceData[]> {
  try {
    return await fetchApi<PriceData[]>('/dashboard/prices')
  } catch (error) {
    console.error('Error fetching prices:', error)
    return []
  }
}

export async function fetchPositions(): Promise<PositionData[]> {
  try {
    return await fetchApi<PositionData[]>('/dashboard/positions')
  } catch (error) {
    console.error('Error fetching positions:', error)
    return []
  }
}

// ============ Medium Frequency APIs (每分钟刷新) ============

export async function fetchRegime(symbol: string = 'BTC'): Promise<RegimeData | null> {
  try {
    return await fetchApi<RegimeData>(`/dashboard/regime?symbol=${symbol}`)
  } catch (error) {
    console.error('Error fetching regime:', error)
    return null
  }
}

export async function fetchRisk(): Promise<RiskData | null> {
  try {
    return await fetchApi<RiskData>('/dashboard/risk')
  } catch (error) {
    console.error('Error fetching risk:', error)
    return null
  }
}

export async function fetchSignal(symbol: string = 'BTC'): Promise<SignalData | null> {
  try {
    return await fetchApi<SignalData>(`/dashboard/signal?symbol=${symbol}`)
  } catch (error) {
    console.error('Error fetching signal:', error)
    return null
  }
}

export async function fetchFactors(): Promise<FactorData[]> {
  try {
    return await fetchApi<FactorData[]>('/dashboard/factors')
  } catch (error) {
    console.error('Error fetching factors:', error)
    return []
  }
}

export async function fetchCompositeScore(): Promise<number> {
  try {
    const data = await fetchApi<{ score: number }>('/dashboard/composite-score')
    return data.score
  } catch (error) {
    console.error('Error fetching composite score:', error)
    return 0.5
  }
}

// ============ Low Frequency APIs (每5分钟刷新) ============

export async function fetchNews(
  page: number = 1,
  pageSize: number = 10,
  source?: string,
  sentiment?: string
): Promise<PaginatedResponse<NewsItem>> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(pageSize),
    })
    if (source) params.append('source', source)
    if (sentiment) params.append('sentiment', sentiment)
    
    return await fetchApi<PaginatedResponse<NewsItem>>(`/dashboard/news?${params}`)
  } catch (error) {
    console.error('Error fetching news:', error)
    return { items: [], total: 0, page, pageSize, hasMore: false }
  }
}

export async function fetchSocialPosts(
  page: number = 1,
  pageSize: number = 10,
  platform?: string
): Promise<PaginatedResponse<SocialPost>> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(pageSize),
    })
    if (platform) params.append('platform', platform)
    
    return await fetchApi<PaginatedResponse<SocialPost>>(`/dashboard/social?${params}`)
  } catch (error) {
    console.error('Error fetching social posts:', error)
    return { items: [], total: 0, page, pageSize, hasMore: false }
  }
}

export async function fetchDataSources(): Promise<DataSourceStatus[]> {
  try {
    return await fetchApi<DataSourceStatus[]>('/dashboard/data-sources')
  } catch (error) {
    console.error('Error fetching data sources:', error)
    return []
  }
}

export async function fetchTraders(limit: number = 10): Promise<TraderData[]> {
  try {
    return await fetchApi<TraderData[]>(`/dashboard/traders?limit=${limit}`)
  } catch (error) {
    console.error('Error fetching traders:', error)
    return []
  }
}

export async function fetchMacro(): Promise<MacroData | null> {
  try {
    return await fetchApi<MacroData>('/dashboard/macro')
  } catch (error) {
    console.error('Error fetching macro:', error)
    return null
  }
}

export async function fetchFearGreed(): Promise<FearGreedData | null> {
  try {
    return await fetchApi<FearGreedData>('/dashboard/fear-greed')
  } catch (error) {
    console.error('Error fetching fear & greed:', error)
    return null
  }
}

export async function fetchEtf(): Promise<EtfData | null> {
  try {
    return await fetchApi<EtfData>('/dashboard/etf')
  } catch (error) {
    console.error('Error fetching ETF:', error)
    return null
  }
}
