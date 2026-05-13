export const mockPrices = [
  { symbol: 'BTC', price: 105000, change24h: 2.5, change_24h: 2.5, volume_24h: 30e9, exchange: 'binance' },
  { symbol: 'BTC', price: 105010, change24h: 2.5, change_24h: 2.5, volume_24h: 24e9, exchange: 'okx' },
  { symbol: 'BTC', price: 104990, change24h: 2.5, change_24h: 2.5, volume_24h: 18e9, exchange: 'coinbase' },
  { symbol: 'ETH', price: 3500, change24h: 1.8, change_24h: 1.8, volume_24h: 15e9, exchange: 'binance' },
  { symbol: 'ETH', price: 3505, change24h: 1.8, change_24h: 1.8, volume_24h: 10e9, exchange: 'okx' },
  { symbol: 'SOL', price: 180, change24h: 3.2, change_24h: 3.2, volume_24h: 5e9, exchange: 'binance' },
]

export const mockCompositeScore = 18.0

export const mockRegime = { state: 'RISK_OFF', confidence: 85, trendStrength: 0.25 }

export const mockRisk = {
  total: 58,
  level: 'medium' as const,
  components: { volatility: 0.65, flow: 0.30, sentiment: 0.75, macro: 0.50 },
}

export const mockSignal = {
  action: 'BUY',
  confidence: 78,
  riskLevel: 'MEDIUM',
  reason: 'ETF持续流入 + 宏观风险偏好上升',
}

export const mockFactors = [
  { type: 'trend' as const, name: '趋势因子', nameEn: 'Trend', weight: 30, value: 0.55, confidence: 85, color: '#3B82F6' },
  { type: 'flow' as const, name: '资金流因子', nameEn: 'Flow', weight: 25, value: -0.20, confidence: 80, color: '#F59E0B' },
  { type: 'sentiment' as const, name: '情绪因子', nameEn: 'Sentiment', weight: 20, value: -0.60, confidence: 70, color: '#EC4899' },
  { type: 'macro' as const, name: '宏观因子', nameEn: 'Macro', weight: 15, value: 0.30, confidence: 80, color: '#10B981' },
  { type: 'behavioral' as const, name: '行为因子', nameEn: 'Behavioral', weight: 7, value: 0.40, confidence: 65, color: '#8B5CF6' },
  { type: 'historical' as const, name: '历史因子', nameEn: 'Historical', weight: 3, value: -0.10, confidence: 45, color: '#6B7280' },
]

export const mockPositions = [
  { symbol: 'BTC/USDT', side: 'LONG' as const, size: 0.18, entryPrice: 66500, leverage: 3, pnl: 132, stopLoss: 64000, takeProfit: 70000 },
  { symbol: 'ETH/USDT', side: 'NONE' as const, size: 0, entryPrice: 0, leverage: 0, pnl: 0, stopLoss: 0, takeProfit: 0 },
]

export const mockWeightVersions = [
  { version: 'v2.1.0', status: 'production' as const, weights: { trend: 30, flow: 25, sentiment: 20, macro: 15, behavioral: 7, historical: 3 }, factors: { trend: 30, flow: 25, sentiment: 20, macro: 15, behavioral: 7, historical: 3 }, sharpe: 1.8, winRate: 67, createdAt: '2024-01-15', createdBy: 'LLM优化' },
  { version: 'v2.0.0', status: 'archived' as const, weights: { trend: 25, flow: 30, sentiment: 20, macro: 15, behavioral: 5, historical: 5 }, factors: { trend: 25, flow: 30, sentiment: 20, macro: 15, behavioral: 5, historical: 5 }, sharpe: 1.6, winRate: 62, createdAt: '2024-01-01', createdBy: '手动调整' },
  { version: 'v1.5.0', status: 'testing' as const, weights: { trend: 35, flow: 25, sentiment: 15, macro: 15, behavioral: 10, historical: 0 }, factors: { trend: 35, flow: 25, sentiment: 15, macro: 15, behavioral: 10, historical: 0 }, sharpe: 1.2, winRate: 55, createdAt: '2023-12-20', createdBy: 'A/B测试' },
  { version: 'v1.0.0', status: 'archived' as const, weights: { trend: 20, flow: 30, sentiment: 25, macro: 15, behavioral: 5, historical: 5 }, factors: { trend: 20, flow: 30, sentiment: 25, macro: 15, behavioral: 5, historical: 5 }, sharpe: 1.4, winRate: 58, createdAt: '2023-12-01', createdBy: '初始版本' },
]

export const mockDataSources = [
  { name: 'Binance价格', status: 'normal' },
  { name: 'OKX价格', status: 'normal' },
  { name: 'Coinbase价格', status: 'normal' },
  { name: 'ETF资金流', status: 'delayed', delay: '2h' },
  { name: '黄金价格', status: 'normal' },
  { name: 'CoinDesk RSS', status: 'normal' },
  { name: 'Twitter KOL', status: 'error' },
]

export const mockTraders = [
  { id: '1', name: 'Crypto Rover', platform: 'Twitter', followers: 125000, sentiment: 0.75, recentPosition: 'LONG', symbol: 'BTC', winRate: 0.68, avatar: null },
  { id: '2', name: 'BitBoy Crypto', platform: 'YouTube', followers: 890000, sentiment: 0.82, recentPosition: 'LONG', symbol: 'ETH', winRate: 0.72, avatar: null },
  { id: '3', name: 'The Moon', platform: 'Twitter', followers: 456000, sentiment: 0.65, recentPosition: 'FLAT', symbol: 'BTC', winRate: 0.61, avatar: null },
  { id: '4', name: 'Crypto Banter', platform: 'Telegram', followers: 78000, sentiment: -0.20, recentPosition: 'SHORT', symbol: 'BTC', winRate: 0.55, avatar: null },
  { id: '5', name: 'Michaël van de Poppe', platform: 'Twitter', followers: 234000, sentiment: 0.45, recentPosition: 'LONG', symbol: 'BTC', winRate: 0.64, avatar: null },
]

export const mockSocialPosts = [
  { id: '1', platform: 'Twitter', author: 'Cathie Wood', authorAvatar: null, content: 'Bitcoin will reach $1M by 2030. The institutional adoption is just beginning.', sentiment: 0.9, likes: 15200, time: '15分钟前', timestamp: new Date().toISOString(), symbols: ['BTC'] },
  { id: '2', platform: 'Twitter', author: 'Elon Musk', authorAvatar: null, content: 'Tesla Bitcoin holdings remain unchanged.', sentiment: 0.3, likes: 45000, time: '1小时前', timestamp: new Date().toISOString(), symbols: ['BTC'] },
  { id: '3', platform: 'Telegram', author: 'Whale Alert', authorAvatar: null, content: 'Large transfer: 2,500 BTC moved from unknown wallet to Coinbase', sentiment: -0.4, likes: 3200, time: '30分钟前', timestamp: new Date().toISOString(), symbols: ['BTC'] },
  { id: '4', platform: 'YouTube', author: 'Coin Bureau', authorAvatar: null, content: 'ETH 2.0 staking yields looking attractive as network upgrades progress', sentiment: 0.7, likes: 8900, time: '2小时前', timestamp: new Date().toISOString(), symbols: ['ETH'] },
]
