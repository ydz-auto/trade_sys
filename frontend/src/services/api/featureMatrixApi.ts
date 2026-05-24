import { api } from './client'
import {
  FeatureMetadata,
  FeatureValue,
  FeatureMatrixSummary,
  SymbolConfig,
  SymbolConfigsResponse,
  OptimizationSuggestion,
} from '../../types'

export interface UpdateFeatureWeightRequest {
  weight: number
}

export interface UpdateSymbolFeaturesRequest {
  features: Record<string, number>
  thresholds?: Record<string, number>
}

export interface UpdateSymbolConfigRequest {
  weights?: Record<string, number>
  thresholds?: Record<string, number>
  enabledStrategies?: string[]
}

export interface SuccessResponse {
  success: boolean
  message?: string
  data?: any
}

// Feature Matrix APIs
export const getFeatureMetadata = async (): Promise<FeatureMetadata[]> => {
  const response = await api.get('/features/metadata')
  return response.data
}

export const getSingleFeatureMetadata = async (featureName: string): Promise<FeatureMetadata> => {
  const response = await api.get(`/features/metadata/${featureName}`)
  return response.data
}

export const getSymbolFeatures = async (symbol: string): Promise<FeatureValue[]> => {
  const response = await api.get(`/features/${symbol}`)
  return response.data
}

export const getFeatureMatrixSummary = async (symbol: string): Promise<FeatureMatrixSummary> => {
  const response = await api.get(`/features/${symbol}/summary`)
  return response.data
}

export const getFeaturesByCategory = async (
  symbol: string,
  category: string
): Promise<FeatureValue[]> => {
  const response = await api.get(`/features/${symbol}/category/${category}`)
  return response.data
}

export const updateFeatureWeight = async (
  symbol: string,
  featureName: string,
  request: UpdateFeatureWeightRequest
): Promise<SuccessResponse> => {
  const response = await api.put(
    `/features/${symbol}/weight/${featureName}`,
    request
  )
  return response.data
}

export const updateSymbolFeatures = async (
  symbol: string,
  request: UpdateSymbolFeaturesRequest
): Promise<SuccessResponse> => {
  const response = await api.put(`/features/${symbol}`, request)
  return response.data
}

export const triggerBacktest = async (symbol: string): Promise<SuccessResponse> => {
  const response = await api.post(`/features/${symbol}/backtest`)
  return response.data
}

// Symbol Config APIs (under /config prefix)
export const getAllSymbolConfigs = async (): Promise<SymbolConfigsResponse> => {
  const response = await api.get('/config/symbols')
  return response.data
}

export const getSymbolConfig = async (symbol: string): Promise<SymbolConfig> => {
  const response = await api.get(`/config/symbols/${symbol}`)
  return response.data
}

export const updateSymbolConfig = async (
  symbol: string,
  request: UpdateSymbolConfigRequest
): Promise<SuccessResponse> => {
  const response = await api.put(`/config/symbols/${symbol}`, request)
  return response.data
}

export const getOptimizationSuggestions = async (
  symbol: string
): Promise<OptimizationSuggestion[]> => {
  const response = await api.get(`/config/symbols/${symbol}/suggestions`)
  return response.data
}
