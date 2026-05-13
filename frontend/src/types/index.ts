export type FactorType = 'trend' | 'flow' | 'sentiment' | 'macro' | 'behavioral' | 'historical'

export interface Factor {
  type: FactorType
  name: string
  nameEn?: string
  weight: number
  value: number
  confidence: number
  color?: string
}

export interface PriceData {
  symbol: string
  price: number
  change24h: number
  change_24h?: number
  exchange: string
}

export interface RegimeState {
  state: 'TRENDING' | 'RANGE' | 'PANIC' | 'EUPHORIA' | 'RISK_OFF' | 'RISK_ON' | 'NEUTRAL' | 'TRANSITIONAL' | 'UNCERTAIN'
  confidence: number
  trendStrength?: number
}

export interface RiskIndex {
  total: number
  level: 'low' | 'medium' | 'high' | 'extreme'
  components: {
    volatility: number
    flow: number
    sentiment: number
    macro: number
  }
}

export interface Signal {
  action: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH'
  reason: string
}

export type SystemMode = 'BACKTEST' | 'SIMULATION' | 'LIVE'

export interface Position {
  symbol: string
  side: 'LONG' | 'SHORT' | 'NONE'
  size: number
  entryPrice?: number
  leverage?: number
  pnl: number
  stopLoss?: number
  takeProfit?: number
}

export interface WeightVersion {
  version: string
  status?: 'production' | 'testing' | 'archived'
  weights?: Record<FactorType, number>
  factors?: Record<FactorType, number>
  sharpe?: number
  winRate?: number
  createdAt: string
  createdBy?: 'LLM优化' | '手动调整' | 'A/B测试' | '初始版本'
}

export interface DataSourceStatus {
  name: string
  status: 'normal' | 'delayed' | 'error' | 'connected'
  delay?: string
  lastUpdate?: string
  recordsCount?: number
}

export interface Trader {
  id?: string
  name: string
  platform?: 'Twitter' | 'Telegram' | 'YouTube'
  followers: number
  sentiment?: number
  recentPosition?: 'LONG' | 'SHORT' | 'FLAT'
  symbol?: string
  winRate: number
  avatar?: string
}

export interface SocialPost {
  id: string
  platform: 'Twitter' | 'Telegram' | 'YouTube' | 'twitter' | 'reddit'
  author: string
  authorAvatar?: string
  content: string
  sentiment: number | 'bullish' | 'bearish' | 'neutral'
  likes?: number
  time?: string
  timestamp?: string
  symbols?: string[]
}

export interface NewsItem {
  id: string
  title: string
  content: string
  source: string
  sentiment: string
  sentiment_score: number
  published: number
}

// === 多数据源价格对比 ===
export interface ExchangePrice {
  exchange: string
  price: number
  change24h: number
  volume24h: number
  latencyMs: number
}

export interface PriceComparison {
  symbol: string
  prices: ExchangePrice[]
  priceSpread: number
  bestBid: string | null
  bestAsk: string | null
  timestamp: string
}

export interface PriceSourceStatus {
  name: string
  priority: number
  circuitBreaker: {
    state: 'closed' | 'open' | 'half-open'
    failureCount: number
  }
  status: {
    available: boolean
    lastSuccess?: string
    lastFailure?: string
    latencyMs: number
  }
}
