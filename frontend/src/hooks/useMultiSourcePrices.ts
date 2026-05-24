import { useEffect, useState, useCallback } from 'react'
import { fetchPricesFromAllSources, fetchPriceComparison, fetchPriceSourcesStatus } from '../services/api/tradingApi'
import type { PriceData, PriceComparison, PriceSourceStatus } from '../types'

interface UseMultiSourcePricesOptions {
  symbols?: string
  refreshInterval?: number
  enabled?: boolean
}

interface UseMultiSourcePricesReturn {
  prices: PriceData[]
  comparison: PriceComparison | null
  sourceStatus: Record<string, PriceSourceStatus>
  isLoading: boolean
  error: string | null
  lastUpdate: Date | null
  refetch: () => Promise<void>
}

export function useMultiSourcePrices(options: UseMultiSourcePricesOptions = {}): UseMultiSourcePricesReturn {
  const {
    symbols = 'BTC,ETH,SOL',
    refreshInterval = 5000,
    enabled = true
  } = options

  const [prices, setPrices] = useState<PriceData[]>([])
  const [comparison, setComparison] = useState<PriceComparison | null>(null)
  const [sourceStatus, setSourceStatus] = useState<Record<string, PriceSourceStatus>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      // 并行获取所有数据
      const [pricesData, comparisonData, statusData] = await Promise.all([
        fetchPricesFromAllSources(symbols),
        fetchPriceComparison(symbols.split(',')[0]), // 获取第一个交易对的对比
        fetchPriceSourcesStatus()
      ])

      setPrices(pricesData)
      setComparison(comparisonData)
      setSourceStatus(statusData)
      setLastUpdate(new Date())
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取数据失败'
      setError(errorMessage)
      console.error('Multi-source prices fetch error:', err)
    } finally {
      setIsLoading(false)
    }
  }, [symbols])

  useEffect(() => {
    if (!enabled) return

    // 立即获取数据
    fetchData()

    // 设置定时刷新
    const interval = setInterval(fetchData, refreshInterval)

    return () => clearInterval(interval)
  }, [enabled, refreshInterval, fetchData])

  return {
    prices,
    comparison,
    sourceStatus,
    isLoading,
    error,
    lastUpdate,
    refetch: fetchData
  }
}
