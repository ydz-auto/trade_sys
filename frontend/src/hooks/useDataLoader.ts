import { useEffect, useState, useRef } from 'react'
import {
  fetchPrices,
  fetchPositions,
  fetchRegime,
  fetchRisk,
  fetchSignal,
  fetchFactors,
  fetchCompositeScore,
  fetchNews,
  fetchSocialPosts,
  fetchDataSources,
  fetchTraders,
  fetchMacro,
  fetchFearGreed,
  fetchEtf,
} from '../services/api/dashboardApi'
import { useTradingStore } from '../store/tradingStore'
import { wsService } from '../services/websocket/wsService'

const POLL_INTERVAL = 60000 // 60秒轮询一次（中频数据）
const PRICE_POLL_INTERVAL = 5000 // 5秒轮询价格（WebSocket 失败时的降级方案）

export function useDataLoader() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const store = useTradingStore()
  const isFirstRender = useRef(true)
  const wsConnectedRef = useRef(false)

  // WebSocket 连接和价格订阅
  useEffect(() => {
    let mounted = true

    wsService.connect()
      .then(() => {
        if (!mounted) return
        wsConnectedRef.current = true
        store.setConnected(true)
        
        // 订阅价格频道
        wsService.subscribe(['channel:prices', 'channel:position'])
        
        // 监听价格更新
        wsService.on('channel:prices', (data) => {
          if (data.type === 'price_update') {
            const priceData = data.data
            const currentPrices = useTradingStore.getState().prices
            const existingIndex = currentPrices.findIndex(p => p.symbol === priceData.symbol)
            if (existingIndex >= 0) {
              const newPrices = [...currentPrices]
              newPrices[existingIndex] = priceData
              store.setPrices(newPrices)
            } else {
              store.setPrices([...currentPrices, priceData])
            }
          } else if (data.type === 'prices_snapshot') {
            const snapshot = data.data as Record<string, any>
            const pricesList = Object.values(snapshot)
            store.setPrices(pricesList)
          }
        })
        
        // 监听持仓更新
        wsService.on('channel:position', (data) => {
          if (data.type === 'position_update' && data.positions) {
            store.setPositions(data.positions)
          }
        })
        
        console.log('[DataLoader] WebSocket connected')
      })
      .catch((err) => {
        console.error('[DataLoader] WebSocket connection failed:', err)
        wsConnectedRef.current = false
        store.setConnected(false)
      })

    return () => {
      mounted = false
      wsService.unsubscribe(['channel:prices', 'channel:position'])
      wsService.disconnect()
    }
  }, [])

  // 加载其他数据（非高频）
  useEffect(() => {
    let mounted = true
    let intervalId: number | null = null
    let priceIntervalId: number | null = null

    async function loadData() {
      try {
        setLoading(true)
        
        // 并行加载所有数据
        const [
          pricesData,
          positionsData,
          regimeData,
          riskData,
          signalData,
          factorsData,
          compositeScoreData,
          newsData,
          socialData,
          dataSourcesData,
          tradersData,
          macroData,
          fearGreedData,
          etfData,
        ] = await Promise.all([
          wsConnectedRef.current ? Promise.resolve(null) : fetchPrices(),
          wsConnectedRef.current ? Promise.resolve(null) : fetchPositions(),
          fetchRegime(),
          fetchRisk(),
          fetchSignal(),
          fetchFactors(),
          fetchCompositeScore(),
          fetchNews(),
          fetchSocialPosts(),
          fetchDataSources(),
          fetchTraders(),
          fetchMacro(),
          fetchFearGreed(),
          fetchEtf(),
        ])

        if (!mounted) return

        // 更新 store
        if (pricesData) store.setPrices(pricesData)
        if (positionsData) store.setPositions(positionsData)
        if (regimeData) store.setRegime(regimeData)
        if (riskData) store.setRisk(riskData)
        if (signalData) store.setSignal(signalData)
        if (factorsData) store.setFactors(factorsData)
        store.setCompositeScore(compositeScoreData)
        store.setNews(newsData.items)
        store.setSocialPosts(socialData.items)
        store.setDataSources(dataSourcesData)
        store.setTraders(tradersData)
        if (macroData) store.setMacro(macroData)
        if (fearGreedData) store.setFearGreed(fearGreedData)
        if (etfData) store.setEtf(etfData)
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

    async function loadPricesOnly() {
      try {
        const [pricesData, positionsData] = await Promise.all([
          fetchPrices(),
          fetchPositions(),
        ])
        if (!mounted) return
        if (pricesData) store.setPrices(pricesData)
        if (positionsData) store.setPositions(positionsData)
      } catch (err) {
        console.error('Price loading error:', err)
      }
    }

    if (isFirstRender.current) {
      isFirstRender.current = false
      loadData()
    }

    // 中频数据轮询
    intervalId = window.setInterval(() => {
      if (mounted) {
        loadData()
      }
    }, POLL_INTERVAL)

    // 价格轮询（WebSocket 失败时的降级）
    priceIntervalId = window.setInterval(() => {
      if (mounted && !wsConnectedRef.current) {
        loadPricesOnly()
      }
    }, PRICE_POLL_INTERVAL)

    return () => {
      mounted = false
      if (intervalId !== null) {
        clearInterval(intervalId)
      }
      if (priceIntervalId !== null) {
        clearInterval(priceIntervalId)
      }
    }
  }, [])

  return { loading, error }
}
