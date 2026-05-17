/**
 * useRealtime Hook - 实时数据 Hook
 * 
 * 自动连接 WebSocket，订阅频道，返回实时数据
 */

import { useEffect, useState } from 'react'
import { useRealtimeStore, initializeRealtime } from '../store/realtimeStore'
import { wsService } from '../services/websocket/wsService'
import type { ChannelType } from '../services/websocket/wsService'

export function useRealtime(channels?: ChannelType[]) {
  const connected = useRealtimeStore((s) => s.connected)
  const dashboard = useRealtimeStore((s) => s.dashboard)
  const decisions = useRealtimeStore((s) => s.decisions)
  const risk = useRealtimeStore((s) => s.risk)
  const positions = useRealtimeStore((s) => s.positions)
  const timeline = useRealtimeStore((s) => s.timeline)

  useEffect(() => {
    initializeRealtime()
    
    return () => {
      wsService.disconnect()
    }
  }, [])

  useEffect(() => {
    if (connected && channels) {
      useRealtimeStore.getState().subscribe(channels)
    }
  }, [connected, channels])

  return {
    connected,
    dashboard,
    decisions,
    risk,
    positions,
    timeline,
  }
}

export function useDashboard() {
  return useRealtimeStore((s) => s.dashboard)
}

export function useDecisions() {
  return useRealtimeStore((s) => s.decisions)
}

export function useRisk() {
  return useRealtimeStore((s) => s.risk)
}

export function usePositions() {
  return useRealtimeStore((s) => s.positions)
}

export function useTimeline(limit: number = 50) {
  const timeline = useRealtimeStore((s) => s.timeline)
  return timeline.slice(0, limit)
}

export function useConnectionStatus() {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  
  useEffect(() => {
    const unsub = wsService.onMessage((msg) => {
      if (msg.channel === '') {
        setStatus('connected')
      }
    })

    wsService.connect()
      .then(() => setStatus('connected'))
      .catch(() => setStatus('disconnected'))

    return unsub
  }, [])

  return status
}
