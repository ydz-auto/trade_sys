/**
 * WebSocket Service - 实时状态推送
 * 
 * 连接 WS Gateway，订阅频道，接收实时更新
 */

export type ChannelType = 
  | 'dashboard' 
  | 'decision' 
  | 'risk' 
  | 'position' 
  | 'timeline' 
  | 'signal' 
  | 'order'

export interface WSMessage {
  channel: string
  data: any
  timestamp: string
}

export interface WSEvent {
  type: string
  [key: string]: any
}

type MessageHandler = (message: WSMessage) => void
type EventHandler = (event: WSEvent) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private pingInterval: number | null = null
  private messageHandlers: Set<MessageHandler> = new Set()
  private eventHandlers: Map<string, Set<EventHandler>> = new Map()
  private subscribedChannels: Set<string> = new Set()
  
  isConnected = false
  connectionId: string | null = null

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.url = `${protocol}//${host}/api/ws`
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          console.log('[WS] Connected')
          this.isConnected = true
          this.reconnectAttempts = 0
          this.startPing()
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (error) {
            console.error('[WS] Parse error:', error)
          }
        }

        this.ws.onclose = () => {
          console.log('[WS] Disconnected')
          this.isConnected = false
          this.stopPing()
          this.attemptReconnect()
        }

        this.ws.onerror = (error) => {
          console.error('[WS] Error:', error)
          reject(error)
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  disconnect(): void {
    this.stopPing()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.isConnected = false
  }

  private startPing(): void {
    this.pingInterval = window.setInterval(() => {
      this.send({ type: 'ping' })
    }, 30000)
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    
    setTimeout(() => {
      this.connect().catch(console.error)
    }, delay)
  }

  private handleMessage(message: any): void {
    if (message.type === 'welcome') {
      this.connectionId = message.connection_id
      console.log('[WS] Welcome received, channels:', message.channels)
      
      if (this.subscribedChannels.size > 0) {
        this.subscribe(Array.from(this.subscribedChannels))
      }
      return
    }

    if (message.type === 'subscribed') {
      console.log('[WS] Subscribed to:', message.channels)
      return
    }

    if (message.type === 'pong') {
      return
    }

    const wsMessage: WSMessage = {
      channel: message.channel || '',
      data: message.data || message,
      timestamp: message.timestamp || new Date().toISOString(),
    }

    this.messageHandlers.forEach(handler => handler(wsMessage))

    if (message.channel) {
      const handlers = this.eventHandlers.get(message.channel)
      if (handlers) {
        handlers.forEach(handler => handler(message.data))
      }
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  subscribe(channels: string[]): void {
    channels.forEach(ch => this.subscribedChannels.add(ch))
    this.send({ type: 'subscribe', channels })
  }

  unsubscribe(channels: string[]): void {
    channels.forEach(ch => this.subscribedChannels.delete(ch))
    this.send({ type: 'unsubscribe', channels })
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler)
    return () => this.messageHandlers.delete(handler)
  }

  on(channel: string, handler: EventHandler): () => void {
    if (!this.eventHandlers.has(channel)) {
      this.eventHandlers.set(channel, new Set())
    }
    this.eventHandlers.get(channel)!.add(handler)
    return () => {
      this.eventHandlers.get(channel)?.delete(handler)
    }
  }

  getCurrentState(): void {
    this.send({ type: 'get_state' })
  }
}

export const wsService = new WebSocketService()

export function useWebSocket() {
  return wsService
}
