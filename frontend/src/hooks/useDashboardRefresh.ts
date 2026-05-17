/**
 * useDashboardRefresh - Dashboard 数据刷新 Hook
 * 
 * 架构：
 * - WebSocket 实时：prices（每30秒推送快照，实时更新单个价格）
 * - 中频（每分钟）：regime, risk, signal, factors, positions
 * - 低频（每5分钟）：news, social, data-sources, traders, macro, etf
 * 
 * WebSocket 连接后，价格数据通过 WebSocket 实时推送，
 * 无需高频轮询，减少服务器压力
 */

import { useEffect, useRef, useCallback } from 'react'
import { useDashboardV2Store } from '../store/dashboardV2Store'
import { wsService } from '../services/websocket/wsService'

export function useDashboardRefresh(options?: {
  highFrequencyMs?: number
  mediumFrequencyMs?: number
  lowFrequencyMs?: number
  enabled?: boolean
  useWebSocket?: boolean
}) {
  const {
    highFrequencyMs = 1000,
    mediumFrequencyMs = 60000,
    lowFrequencyMs = 300000,
    enabled = true,
    useWebSocket = true,
  } = options || {}

  const {
    refreshHighFrequency,
    refreshMediumFrequency,
    refreshLowFrequency,
    subscribeWebSocket,
    unsubscribeWebSocket,
    setWsConnected,
  } = useDashboardV2Store()

  const highFreqRef = useRef<NodeJS.Timeout | null>(null)
  const mediumFreqRef = useRef<NodeJS.Timeout | null>(null)
  const lowFreqRef = useRef<NodeJS.Timeout | null>(null)

  // 初始化 WebSocket 连接
  useEffect(() => {
    if (!useWebSocket) return

    wsService.connect()
      .then(() => {
        setWsConnected(true)
        subscribeWebSocket()
      })
      .catch((err) => {
        console.error('[Dashboard] WebSocket connection failed:', err)
        setWsConnected(false)
      })

    return () => {
      unsubscribeWebSocket()
      wsService.disconnect()
    }
  }, [useWebSocket])

  // 启动定时刷新
  const startRefresh = useCallback(() => {
    if (!enabled) return

    refreshMediumFrequency()
    refreshLowFrequency()

    if (!useWebSocket) {
      refreshHighFrequency()
      highFreqRef.current = setInterval(() => {
        refreshHighFrequency()
      }, highFrequencyMs)
    }

    mediumFreqRef.current = setInterval(() => {
      refreshMediumFrequency()
    }, mediumFrequencyMs)

    lowFreqRef.current = setInterval(() => {
      refreshLowFrequency()
    }, lowFrequencyMs)
  }, [enabled, useWebSocket, refreshHighFrequency, refreshMediumFrequency, refreshLowFrequency, highFrequencyMs, mediumFrequencyMs, lowFrequencyMs])

  // 停止定时刷新
  const stopRefresh = useCallback(() => {
    if (highFreqRef.current) {
      clearInterval(highFreqRef.current)
      highFreqRef.current = null
    }
    if (mediumFreqRef.current) {
      clearInterval(mediumFreqRef.current)
      mediumFreqRef.current = null
    }
    if (lowFreqRef.current) {
      clearInterval(lowFreqRef.current)
      lowFreqRef.current = null
    }
  }, [])

  // 组件挂载时启动刷新
  useEffect(() => {
    startRefresh()
    return () => stopRefresh()
  }, [startRefresh, stopRefresh])

  // 页面可见性变化时暂停/恢复刷新
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopRefresh()
      } else {
        startRefresh()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [startRefresh, stopRefresh])

  return {
    startRefresh,
    stopRefresh,
    refreshHighFrequency,
    refreshMediumFrequency,
    refreshLowFrequency,
  }
}

/**
 * useDashboardData - 获取 Dashboard 数据的便捷 Hook
 */
export function useDashboardData() {
  const store = useDashboardV2Store()
  useDashboardRefresh()
  return store
}
