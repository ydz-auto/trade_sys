import { api } from './client'

export type OrderSide = 'BUY' | 'SELL'
export type OrderType = 'MARKET' | 'LIMIT' | 'STOP' | 'TAKE_PROFIT' | 'TRAILING_STOP'
export type OrderStatus = 'PENDING' | 'ACKED' | 'PARTIAL_FILL' | 'FILLED' | 'CANCELLED' | 'REJECTED'
export type ExchangeType = 'binance' | 'okx'

export interface OrderRequest {
  symbol: string
  side: OrderSide
  type: OrderType
  quantity: number
  exchange: ExchangeType
  price?: number
  stopPrice?: number
  leverage?: number
  stopLoss?: {
    type: 'MARKET' | 'LIMIT'
    price?: number
    trailing?: number
  }
  takeProfit?: {
    type: 'MARKET' | 'LIMIT'
    price?: number
  }
}

export interface OrderEvent {
  eventId: string
  orderId: string
  eventType: 'ORDER_CREATED' | 'ORDER_ACKED' | 'PARTIAL_FILL' | 'FILLED' | 'CANCELLED' | 'REJECTED'
  timestamp: string
  data?: Order
}

export interface Order {
  id: string
  clientId?: string
  symbol: string
  exchange: ExchangeType
  side: OrderSide
  type: OrderType
  status: OrderStatus
  quantity: number
  filledQuantity: number
  price?: number
  avgFillPrice?: number
  leverage: number
  stopLoss?: Order
  takeProfit?: Order
  createdAt: string
  updatedAt: string
}

export interface Position {
  id: string
  symbol: string
  exchange: ExchangeType
  side: 'LONG' | 'SHORT'
  quantity: number
  entryPrice: number
  markPrice?: number
  unrealizedPnL: number
  margin: number
  leverage: number
  liquidationPrice?: number
  createdAt: string
  updatedAt: string
}

export interface ExecutionState {
  orders: Order[]
  positions: Position[]
  openOrdersCount: number
  activePositionsCount: number
}

export interface SignalAction {
  signalId: string
  strategyId: string
  symbol: string
  exchange: ExchangeType
  action: 'OPEN_LONG' | 'OPEN_SHORT' | 'CLOSE'
  leverage: number
  stopLoss?: number
  takeProfit?: number
  confidence: number
}

// Order APIs
export const createOrder = async (request: OrderRequest): Promise<Order> => {
  const response = await api.post('/execution/orders', request)
  return response.data
}

export const getOrder = async (orderId: string): Promise<Order> => {
  const response = await api.get(`/execution/orders/${orderId}`)
  return response.data
}

export const cancelOrder = async (orderId: string): Promise<void> => {
  await api.delete(`/execution/orders/${orderId}`)
}

export const getOpenOrders = async (symbol?: string): Promise<Order[]> => {
  const params = symbol ? { symbol } : {}
  const response = await api.get('/execution/orders/open', { params })
  return response.data
}

export const getOrderHistory = async (
  symbol?: string,
  limit: number = 100
): Promise<Order[]> => {
  const params = { symbol, limit }
  const response = await api.get('/execution/orders/history', { params })
  return response.data
}

// Position APIs
export const getPositions = async (symbol?: string): Promise<Position[]> => {
  const params = symbol ? { symbol } : {}
  const response = await api.get('/execution/positions', { params })
  return response.data
}

export const closePosition = async (positionId: string): Promise<void> => {
  await api.post(`/execution/positions/${positionId}/close`)
}

export const modifyPosition = async (
  positionId: string,
  updates: Partial<{ stopLoss: number; takeProfit: number; leverage: number }>
): Promise<Position> => {
  const response = await api.put(`/execution/positions/${positionId}`, updates)
  return response.data
}

// Signal-based Trading
export const executeSignal = async (signalAction: SignalAction): Promise<Order> => {
  const response = await api.post('/execution/signals/execute', signalAction)
  return response.data
}

export const batchExecuteSignals = async (signals: SignalAction[]): Promise<Order[]> => {
  const response = await api.post('/execution/signals/batch', signals)
  return response.data
}

// Execution State
export const getExecutionState = async (): Promise<ExecutionState> => {
  const response = await api.get('/execution/state')
  return response.data
}
