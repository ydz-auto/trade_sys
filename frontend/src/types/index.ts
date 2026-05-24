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
  currentPrice?: number
  leverage?: number
  pnl: number
  pnlPct?: number
  stopLoss?: number
  takeProfit?: number
  // 爆仓相关
  liquidationPrice?: number
  liquidationDistancePct?: number
  margin?: number
  marginRatio?: number
  riskLevel?: 'SAFE' | 'CAUTION' | 'WARNING' | 'DANGER' | 'CRITICAL'
  // 资金费率
  fundingRate?: number  // 当前资金费率
  fundingFeeEstimate?: number  // 预估资金费（USDT）
  nextFundingTime?: string  // 下次结算时间
  // 元数据
  marketType?: string
  exchange?: string
  openedAt?: string
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
  url?: string
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

// === Feature Matrix Types ===
export type FeatureCategory = 'raw' | 'derived' | 'microstructure' | 'cross_market' | 'event'

export interface FeatureMetadata {
  name: string
  nameEn: string
  category: FeatureCategory
  description: string
  dataType: string
  normalizationRange?: [number, number]
  isFactor: boolean
  source: string
  defaultWeight: number
  lastUpdated: string
}

export interface FeatureValue {
  name: string
  category: FeatureCategory
  value: number
  normalizedValue?: number
  weight: number
  confidence: number
}

export interface FeatureMatrixSummary {
  symbol: string
  rows: number
  featuresTotal: number
  featuresRaw: number
  featuresDerived: number
  featuresMicrostructure: number
  featuresCrossMarket: number
  featuresEvent: number
  dateRange?: { [key: string]: any }
}

export interface StrategyPerformance {
  strategyId: string
  winRate: number
  avgReturn: number
  maxDrawdown: number
  totalTrades: number
  lastUpdated: string
}

export interface OptimizationSuggestion {
  type: string
  feature: string
  currentValue: number
  suggestedValue: number
  reason: string
  expectedImprovement?: number
}

export interface SymbolConfig {
  symbol: string
  weights: Record<string, number>
  thresholds: Record<string, number>
  enabledStrategies: string[]
  performance?: Record<string, StrategyPerformance>
  optimizationSuggestions?: OptimizationSuggestion[]
  lastUpdated: string
}

export interface SymbolConfigsResponse {
  configs: Record<string, SymbolConfig>
}

// Runtime State Types - Unified Runtime Visualization Layer
export type RuntimeType = 'live' | 'paper' | 'backtest' | 'replay' | 'ai'

export interface RuntimeStatus {
  type: RuntimeType
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error'
  startTime?: string
  endTime?: string
  currentTimestamp?: string
  progress?: number
  error?: string
}

// Market State
export interface MarketState {
  prices: Record<string, PriceData>
  orderbook?: Record<string, any>
  lastUpdate: string
}

// Signals State
export interface SignalItem {
  signalId: string
  strategyId: string
  symbol: string
  action: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reason: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface SignalsState {
  latest: Record<string, SignalItem[]>
  history: SignalItem[]
  summary: {
    total: number
    long: number
    short: number
    hold: number
    avgConfidence: number
  }
}

// Risk State
export interface RiskState {
  level: 'low' | 'medium' | 'high' | 'extreme'
  score: number
  components: {
    volatility: number
    flow: number
    sentiment: number
    macro: number
    liquidity: number
  }
  warnings: string[]
  alerts: string[]
}

// PnL State
export interface PositionPnL {
  symbol: string
  unrealizedPnL: number
  realizedPnL: number
  totalPnL: number
  pnlPercent: number
  entryPrice: number
  currentPrice: number
  size: number
}

export interface PnLState {
  total: {
    unrealized: number
    realized: number
    total: number
  }
  positions: PositionPnL[]
  history: {
    timestamp: string
    totalPnL: number
  }[]
  performance: {
    winRate: number
    sharpeRatio: number
    maxDrawdown: number
  }
}

// AI State
export interface AIInsight {
  insightId: string
  type: 'prediction' | 'analysis' | 'alert' | 'recommendation'
  title: string
  content: string
  confidence: number
  timestamp: string
  relatedSymbols: string[]
  metadata?: Record<string, any>
}

export interface AIState {
  latestInsight: AIInsight | null
  recentInsights: AIInsight[]
  modelStatus: {
    isRunning: boolean
    lastUpdate: string
    version: string
  }
}

// Replay State
export interface ReplayState {
  config: {
    startDate: string
    endDate: string
    speed: number
    symbols: string[]
  } | null
  currentIndex: number
  isPlaying: boolean
  playbackSpeed: number
}

// Combined Runtime State
export interface RuntimeState {
  status: RuntimeStatus
  
  // Feature Matrix
  features: {
    metadata: FeatureMetadata[]
    values: Record<string, FeatureValue[]>
    summaries: Record<string, FeatureMatrixSummary>
  }
  
  // Market
  market: MarketState
  
  // Signals
  signals: SignalsState
  
  // Risk
  risk: RiskState
  
  // PnL
  pnl: PnLState
  
  // AI
  ai: AIState
  
  // Replay
  replay: ReplayState
  
  // Positions
  positions: Position[]
  
  // Timeline
  timeline: TimelineEvent[]
}

// Runtime Config
export interface RuntimeConfig {
  type: RuntimeType
  id: string
  name: string
  autoSubscribe: boolean
  channels: string[]
  symbolWhitelist?: string[]
}

// Initial State Factory
export const createInitialRuntimeState = (type: RuntimeType): RuntimeState => ({
  status: {
    type,
    status: 'idle',
  },
  features: {
    metadata: [],
    values: {},
    summaries: {},
  },
  market: {
    prices: {},
    lastUpdate: new Date().toISOString(),
  },
  signals: {
    latest: {},
    history: [],
    summary: {
      total: 0,
      long: 0,
      short: 0,
      hold: 0,
      avgConfidence: 0,
    },
  },
  risk: {
    level: 'low',
    score: 0,
    components: {
      volatility: 0,
      flow: 0,
      sentiment: 0,
      macro: 0,
      liquidity: 0,
    },
    warnings: [],
    alerts: [],
  },
  pnl: {
    total: {
      unrealized: 0,
      realized: 0,
      total: 0,
    },
    positions: [],
    history: [],
    performance: {
      winRate: 0,
      sharpeRatio: 0,
      maxDrawdown: 0,
    },
  },
  ai: {
    latestInsight: null,
    recentInsights: [],
    modelStatus: {
      isRunning: false,
      lastUpdate: new Date().toISOString(),
      version: '1.0.0',
    },
  },
  replay: {
    config: null,
    currentIndex: 0,
    isPlaying: false,
    playbackSpeed: 1,
  },
  positions: [],
  timeline: [],
})
