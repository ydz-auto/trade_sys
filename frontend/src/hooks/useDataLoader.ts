import { useEffect, useState, useRef } from 'react'
import { fetchAllTradingData } from '../services/api/tradingApi'
import { useTradingStore } from '../store/tradingStore'

const POLL_INTERVAL = 30000 // 30秒轮询一次

export function useDataLoader() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const store = useTradingStore()
  const isFirstRender = useRef(true)

  useEffect(() => {
    let mounted = true
    let intervalId: number | null = null

    async function loadData() {
      try {
        setLoading(true)
        const data = await fetchAllTradingData()

        if (!mounted) return

        store.setPrices(data.prices)
        store.setCompositeScore(data.compositeScore)
        store.setRegime(data.regime)
        store.setRisk(data.risk)
        store.setSignal(data.signal)
        store.setFactors(data.factors)
        store.setPositions(data.positions)
        store.setWeightVersions(data.weightVersions)
        store.setDataSources(data.dataSources)
        store.setTraders(data.traders)
        store.setSocialPosts(data.socialPosts)
        store.setNews(data.news)
        if (data.fearGreed) {
          store.setFearGreed(data.fearGreed)
        }
        if (data.macro) {
          store.setMacro(data.macro)
        }
        if (data.etf) {
          store.setEtf(data.etf)
        }
        store.setLastUpdate(new Date())

        setError(null)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load data')
        console.error('Data loading error:', err)
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    // 只在第一次渲染时加载
    if (isFirstRender.current) {
      isFirstRender.current = false
      loadData()
    }

    // 设置轮询
    intervalId = window.setInterval(() => {
      if (mounted) {
        loadData()
      }
    }, POLL_INTERVAL)

    return () => {
      mounted = false
      if (intervalId !== null) {
        clearInterval(intervalId)
      }
    }
    // 空依赖！只执行一次初始化
  }, [])

  return { loading, error }
}
