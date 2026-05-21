import { useEffect, useRef, useCallback } from 'react'
import { useRuntimeStore } from '../stores/runtimeStore'
import { api } from '../../services/api/client'

export interface ProjectionEvent {
  type: string
  timestamp: string
  data: Record<string, unknown>
}

export interface RuntimeStreamConfig {
  url?: string
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useRuntimeStream(config: RuntimeStreamConfig = {}) {
  const {
    setMode,
    setOrchestratorStatus,
    setRuntimes,
  } = useRuntimeStore()

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const {
    url = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/runtime`,
    reconnectInterval = 5000,
    maxReconnectAttempts = 10,
  } = config

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[RuntimeStream] Connected')
        reconnectAttemptsRef.current = 0
        
        ws.send(JSON.stringify({
          type: 'SUBSCRIBE',
          channels: [
            'runtime.state',
            'runtime.mode',
            'runtime.events',
            'projection.update',
          ],
        }))
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleMessage(message)
        } catch (err) {
          console.error('[RuntimeStream] Parse error:', err)
        }
      }

      ws.onerror = (error) => {
        console.error('[RuntimeStream] Error:', error)
      }

      ws.onclose = () => {
        console.log('[RuntimeStream] Disconnected')
        wsRef.current = null
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          console.log(`[RuntimeStream] Reconnecting (${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.error('[RuntimeStream] Connect error:', err)
    }
  }, [url, reconnectInterval, maxReconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const handleMessage = useCallback((message: { type: string; channel?: string; data?: unknown }) => {
    switch (message.type) {
      case 'STATE_UPDATE':
        handleStateUpdate(message.channel || '', message.data)
        break
      
      case 'MODE_CHANGE':
        if (message.data && typeof message.data === 'object' && 'mode' in message.data) {
          setMode(message.data.mode as 'backtest' | 'paper' | 'live')
        }
        break
      
      case 'RUNTIME_STATUS':
        if (message.data && typeof message.data === 'object') {
          setOrchestratorStatus({
            isRunning: Boolean((message.data as Record<string, unknown>).is_running),
            activeRuntimes: Number((message.data as Record<string, unknown>).active_runtimes || 0),
            failedRuntimes: Number((message.data as Record<string, unknown>).failed_runtimes || 0),
            uptimeSeconds: Number((message.data as Record<string, unknown>).uptime_seconds || 0),
          })
        }
        break
      
      case 'PROJECTION_UPDATE':
        handleProjectionUpdate(message.data)
        break
      
      default:
        console.log('[RuntimeStream] Unknown message type:', message.type)
    }
  }, [setMode, setOrchestratorStatus])

  const handleStateUpdate = useCallback((channel: string, data: unknown) => {
    if (!data || typeof data !== 'object') return
    
    const stateData = data as Record<string, unknown>
    
    switch (channel) {
      case 'runtime.state':
        if (stateData.runtimes && Array.isArray(stateData.runtimes)) {
          setRuntimes(stateData.runtimes as Array<{
            id: string
            type: string
            state: 'starting' | 'running' | 'paused' | 'degraded' | 'stopped' | 'failed' | 'recovering'
            mode?: 'backtest' | 'paper' | 'live'
            priority: number
          }>)
        }
        break
      
      case 'runtime.mode':
        if (stateData.mode && typeof stateData.mode === 'string') {
          setMode(stateData.mode as 'backtest' | 'paper' | 'live')
        }
        break
    }
  }, [setMode, setRuntimes])

  const handleProjectionUpdate = useCallback((data: unknown) => {
    if (!data || typeof data !== 'object') return
    
    console.log('[RuntimeStream] Projection update:', data)
  }, [])

  const sendCommand = useCallback(async (command: string, payload: Record<string, unknown> = {}) => {
    try {
      const result = await api.post('/runtime/command', {
        command,
        payload,
      })
      return result
    } catch (err) {
      console.error('[RuntimeStream] Command error:', err)
      throw err
    }
  }, [])

  useEffect(() => {
    connect()
    
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    connect,
    disconnect,
    sendCommand,
  }
}


// 这个文件被重命名为 runtimeStream.tsx - 请使用 runtimeStream.tsx
