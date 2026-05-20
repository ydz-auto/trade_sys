import { apiClient } from './client'

export interface StrategyPattern {
  id: string
  name: string
  description: string
  category: string
  confidence: number
  features: string[]
  performance?: {
    winRate: number
    avgReturn: number
    sharpeRatio: number
    maxDrawdown: number
  }
  isEnabled: boolean
  createdAt: string
  updatedAt: string
}

export interface BacktestConfig {
  symbol: string
  startDate: string
  endDate: string
  initialCapital: number
  strategyIds: string[]
}

export interface BacktestResult {
  id: string
  config: BacktestConfig
  performance: {
    totalReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    totalTrades: number
    avgTradeDuration: number
    profitFactor: number
  }
  equity: Array<{ timestamp: string; value: number }>
  trades: Array<{
    id: string
    entryTime: string
    exitTime: string
    action: 'BUY' | 'SELL'
    entryPrice: number
    exitPrice: number
    pnl: number
  }>
  status: 'running' | 'completed' | 'failed'
  createdAt: string
}

export interface StrategyConfig {
  strategyId: string
  symbol: string
  parameters: Record<string, number>
  enabled: boolean
  priority: number
}

export interface StrategyPerformance {
  strategyId: string
  symbol: string
  period: string
  totalTrades: number
  winRate: number
  avgReturn: number
  totalReturn: number
  maxDrawdown: number
  sharpeRatio: number
  lastUpdated: string
}

// Strategy Discovery APIs
export const discoverStrategies = async (symbol: string): Promise<StrategyPattern[]> => {
  const response = await apiClient.post('/strategy/discover', { symbol })
  return response.data
}

export const getDiscoveredStrategies = async (symbol: string): Promise<StrategyPattern[]> => {
  const response = await apiClient.get(`/strategy/discovered/${symbol}`)
  return response.data
}

export const addStrategyToWatchlist = async (strategyId: string): Promise<void> => {
  await apiClient.post(`/strategy/watchlist/${strategyId}`)
}

export const removeStrategyFromWatchlist = async (strategyId: string): Promise<void> => {
  await apiClient.delete(`/strategy/watchlist/${strategyId}`)
}

// Backtest APIs
export const startBacktest = async (config: BacktestConfig): Promise<BacktestResult> => {
  const response = await apiClient.post('/strategy/backtest', config)
  return response.data
}

export const getBacktestResult = async (backtestId: string): Promise<BacktestResult> => {
  const response = await apiClient.get(`/strategy/backtest/${backtestId}`)
  return response.data
}

export const getBacktestHistory = async (): Promise<BacktestResult[]> => {
  const response = await apiClient.get('/strategy/backtest/history')
  return response.data
}

// Strategy Config APIs
export const getAllStrategyConfigs = async (): Promise<Record<string, StrategyConfig[]>> => {
  const response = await apiClient.get('/strategy/configs')
  return response.data
}

export const getStrategyConfig = async (strategyId: string, symbol: string): Promise<StrategyConfig> => {
  const response = await apiClient.get(`/strategy/configs/${strategyId}/${symbol}`)
  return response.data
}

export const updateStrategyConfig = async (
  strategyId: string,
  symbol: string,
  config: Partial<StrategyConfig>
): Promise<void> => {
  await apiClient.put(`/strategy/configs/${strategyId}/${symbol}`, config)
}

export const enableStrategy = async (strategyId: string, symbol: string): Promise<void> => {
  await apiClient.post(`/strategy/enable/${strategyId}/${symbol}`)
}

export const disableStrategy = async (strategyId: string, symbol: string): Promise<void> => {
  await apiClient.post(`/strategy/disable/${strategyId}/${symbol}`)
}

// Strategy Performance APIs
export const getStrategyPerformance = async (
  strategyId: string,
  symbol: string
): Promise<StrategyPerformance[]> => {
  const response = await apiClient.get(`/strategy/performance/${strategyId}/${symbol}`)
  return response.data
}

export const getActiveStrategies = async (): Promise<StrategyPattern[]> => {
  const response = await apiClient.get('/strategy/active')
  return response.data
}
