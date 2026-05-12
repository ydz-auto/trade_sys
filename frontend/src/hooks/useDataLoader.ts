import { useEffect, useState } from 'react'
import { fetchAllTradingData } from '../services/api/tradingApi'
import { useTradingStore } from '../store/tradingStore'

export function useDataLoader() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const store = useTradingStore()

  useEffect(() => {
    let mounted = true

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
        data.factors.forEach(f => {
          store.updateFactorWeight(f.type, f.weight)
        })
        store.setPositions(data.positions)
        store.setDataSources(data.dataSources)
        store.setTraders(data.traders)
        store.setSocialPosts(data.socialPosts)
        store.setNews(data.news)
        store.setLastUpdate(new Date())

        setError(null)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    loadData()

    return () => {
      mounted = false
    }
  }, [])

  return { loading, error }
}
