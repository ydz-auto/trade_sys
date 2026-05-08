export type FactorType = 'trend' | 'flow' | 'sentiment' | 'macro' | 'behavioral' | 'historical'

export interface Factor {
  type: FactorType
  name: string
  nameEn: string
  weight: number
  value: number
  confidence: number
  color: string
}

export interface PriceData {
  symbol: string
  price: number
  change24h: number
  exchange: string
}

export interface RegimeState {
  state: 'TRENDING' | 'RANGE' | 'PANIC' | 'EUPHORIA' | 'RISK_OFF' | 'UNCERTAIN'
  confidence: number
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
  entryPrice: number
  leverage: number
  pnl: number
  stopLoss: number
  takeProfit: number
}

export interface WeightVersion {
  version: string
  status: 'production' | 'testing' | 'archived'
  weights: Record<FactorType, number>
  sharpe: number
  winRate: number
  createdAt: string
  createdBy: 'LLM优化' | '手动调整' | 'A/B测试' | '初始版本'
}

export interface DataSourceStatus {
  name: string
  status: 'normal' | 'delayed' | 'error'
  delay?: string
}

export interface Trader {
  name: string
  platform: 'Twitter' | 'Telegram' | 'YouTube'
  followers: number
  sentiment: number
  recentPosition: 'LONG' | 'SHORT' | 'FLAT'
  symbol: string
  winRate: number
  avatar?: string
}

export interface SocialPost {
  id: string
  platform: 'Twitter' | 'Telegram' | 'YouTube'
  author: string
  authorAvatar?: string
  content: string
  sentiment: number
  likes: number
  time: string
  symbols: string[]
}
