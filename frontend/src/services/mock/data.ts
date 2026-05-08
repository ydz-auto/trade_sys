export const mockPrices = [
  { symbol: 'BTC/USDT', price: 67234, change24h: 2.3, exchange: 'Binance' },
  { symbol: 'BTC/USDT', price: 67218, change24h: 2.2, exchange: 'OKX' },
  { symbol: 'BTC/USDT', price: 67256, change24h: 2.4, exchange: 'Coinbase' },
  { symbol: 'BTC/USDT', price: 67205, change24h: 2.1, exchange: 'Bybit' },
  { symbol: 'ETH/USDT', price: 3842, change24h: 1.8, exchange: 'Binance' },
  { symbol: 'ETH/USDT', price: 3838, change24h: 1.7, exchange: 'OKX' },
  { symbol: 'ETH/USDT', price: 3845, change24h: 1.9, exchange: 'Coinbase' },
  { symbol: 'ETH/USDT', price: 3835, change24h: 1.6, exchange: 'Bybit' },
]

export const mockCompositeScore = 0.18

export const mockRegime = { state: 'RISK_OFF', confidence: 85 }

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
  { type: 'trend' as const, name: '趋势因子', nameEn: 'Trend', weight: 30, value: 0.55, confidence: 100, color: 'primary' },
  { type: 'flow' as const, name: '资金流因子', nameEn: 'Flow', weight: 25, value: -0.20, confidence: 80, color: 'neutral' },
  { type: 'sentiment' as const, name: '情绪因子', nameEn: 'Sentiment', weight: 20, value: -0.60, confidence: 70, color: 'accent' },
  { type: 'macro' as const, name: '宏观因子', nameEn: 'Macro', weight: 15, value: 0.30, confidence: 80, color: 'bullish' },
  { type: 'behavioral' as const, name: '行为因子', nameEn: 'Behavioral', weight: 10, value: 0.40, confidence: 65, color: 'warning' },
  { type: 'historical' as const, name: '历史因子', nameEn: 'Historical', weight: 5, value: -0.10, confidence: 45, color: 'text-secondary' },
]

export const mockPositions = [
  { symbol: 'BTC/USDT', side: 'LONG' as const, size: 0.18, entryPrice: 66500, leverage: 3, pnl: 132, stopLoss: 64000, takeProfit: 70000 },
  { symbol: 'ETH/USDT', side: 'NONE' as const, size: 0, entryPrice: 0, leverage: 0, pnl: 0, stopLoss: 0, takeProfit: 0 },
]

export const mockWeightVersions = [
  { version: 'v2.1.0', status: 'production' as const, weights: { trend: 30, flow: 25, sentiment: 20, macro: 15, behavioral: 10, historical: 5 }, sharpe: 1.8, winRate: 67, createdAt: '2024-01-15', createdBy: 'LLM优化' },
  { version: 'v2.0.0', status: 'archived' as const, weights: { trend: 25, flow: 30, sentiment: 20, macro: 15, behavioral: 5, historical: 5 }, sharpe: 1.6, winRate: 62, createdAt: '2024-01-01', createdBy: '手动调整' },
  { version: 'v1.5.0', status: 'testing' as const, weights: { trend: 35, flow: 25, sentiment: 15, macro: 15, behavioral: 10, historical: 0 }, sharpe: 1.2, winRate: 55, createdAt: '2023-12-20', createdBy: 'A/B测试' },
  { version: 'v1.0.0', status: 'archived' as const, weights: { trend: 20, flow: 30, sentiment: 25, macro: 15, behavioral: 5, historical: 5 }, sharpe: 1.4, winRate: 58, createdAt: '2023-12-01', createdBy: '初始版本' },
]

export const mockDataSources = [
  { name: 'Binance价格', status: 'normal' },
  { name: 'OKX价格', status: 'normal' },
  { name: 'Coinbase价格', status: 'normal' },
  { name: 'Bybit价格', status: 'normal' },
  { name: 'ETF资金流', status: 'delayed', delay: '2h' },
  { name: '黄金价格', status: 'normal' },
  { name: 'CoinDesk RSS', status: 'normal' },
  { name: 'Twitter KOL', status: 'error' },
]

export const mockTraders = [
  { name: 'Crypto Rover', platform: 'Twitter', followers: 125000, sentiment: 0.75, recentPosition: 'LONG', symbol: 'BTC', winRate: 68 },
  { name: 'BitBoy Crypto', platform: 'YouTube', followers: 890000, sentiment: 0.82, recentPosition: 'LONG', symbol: 'ETH', winRate: 72 },
  { name: 'The Moon', platform: 'Twitter', followers: 456000, sentiment: 0.65, recentPosition: 'FLAT', symbol: 'BTC', winRate: 61 },
  { name: 'Crypto Banter', platform: 'Telegram', followers: 78000, sentiment: -0.20, recentPosition: 'SHORT', symbol: 'BTC', winRate: 55 },
  { name: 'Michaël van de Poppe', platform: 'Twitter', followers: 234000, sentiment: 0.45, recentPosition: 'LONG', symbol: 'BTC', winRate: 64 },
]

export const mockSocialPosts = [
  { id: '1', platform: 'Twitter', author: 'Cathie Wood', content: 'Bitcoin will reach $1M by 2030. The institutional adoption is just beginning.', sentiment: 0.9, likes: 15200, time: '15分钟前', symbols: ['BTC'] },
  { id: '2', platform: 'Twitter', author: 'Elon Musk', content: 'Tesla Bitcoin holdings remain unchanged.', sentiment: 0.3, likes: 45000, time: '1小时前', symbols: ['BTC'] },
  { id: '3', platform: 'Telegram', author: 'Whale Alert', content: 'Large transfer: 2,500 BTC moved from unknown wallet to Coinbase', sentiment: -0.4, likes: 3200, time: '30分钟前', symbols: ['BTC'] },
  { id: '4', platform: 'YouTube', author: 'Coin Bureau', content: 'ETH 2.0 staking yields looking attractive as network upgrades progress', sentiment: 0.7, likes: 8900, time: '2小时前', symbols: ['ETH'] },
]
