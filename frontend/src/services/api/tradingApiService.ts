import { api } from './client';

export interface OrderRequest {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  order_type?: 'market' | 'limit';
  price?: number;
  leverage?: number;
  position_size_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  exchange?: 'binance' | 'okx';
  market_type?: 'spot' | 'usdt_futures' | 'coin_futures';
}

export interface OrderResponse {
  order_id: string;
  symbol: string;
  side: string;
  quantity: number;
  price?: number;
  filled_quantity: number;
  avg_fill_price?: number;
  status: string;
  order_type: string;
  market_type: string;
  exchange: string;
  leverage: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  created_at: string;
}

export interface PositionResponse {
  position_id: string;
  symbol: string;
  side: 'long' | 'short';
  quantity: number;
  entry_price: number;
  current_price: number;
  mark_price?: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  leverage: number;
  margin: number;
  liquidation_price?: number;
  liquidation_distance_pct?: number;
  margin_ratio?: number;
  risk_level?: 'SAFE' | 'CAUTION' | 'WARNING' | 'DANGER' | 'CRITICAL';
  market_type: string;
  exchange: string;
  stop_loss_price?: number;
  take_profit_price?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  opened_at: string;
}

export interface TradingStatus {
  mode: string;
  auto_approve_threshold: number;
  total_equity: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  daily_pnl: number;
  total_position_value: number;
  margin_balance: number;
  available_balance: number;
  positions_count: number;
  open_orders_count: number;
  timestamp: string;
}

export interface AccountInfo {
  exchange: string;
  market_type: string;
  balance: number;
  available_balance: number;
  margin_balance: number;
  unrealized_pnl: number;
  positions_count: number;
}

export interface AccountsResponse {
  total_equity: number;
  accounts: AccountInfo[];
}

class TradingApiService {
  async getStatus(): Promise<TradingStatus> {
    return api.get<TradingStatus>('/trading/status');
  }

  async getPositions(): Promise<PositionResponse[]> {
    return api.get<PositionResponse[]>('/trading/positions');
  }

  async getOrders(): Promise<OrderResponse[]> {
    return api.get<OrderResponse[]>('/trading/orders');
  }

  async getAccounts(): Promise<AccountsResponse> {
    return api.get<AccountsResponse>('/trading/accounts');
  }

  async placeOrder(order: OrderRequest): Promise<OrderResponse> {
    return api.post<OrderResponse>('/trading/order', order);
  }

  async closePosition(symbol: string, quantity?: number): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>('/trading/close', { 
      symbol, 
      quantity,
      market_type: 'usdt_futures',
      exchange: 'binance'
    });
  }

  async setLeverage(symbol: string, leverage: number): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>('/trading/leverage', {
      symbol,
      leverage,
      market_type: 'usdt_futures',
      exchange: 'binance'
    });
  }

  async setStopLossTakeProfit(
    symbol: string, 
    stopLossPct?: number, 
    takeProfitPct?: number
  ): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>('/trading/stop-loss-take-profit', {
      symbol,
      stop_loss_pct: stopLossPct,
      take_profit_pct: takeProfitPct,
      market_type: 'usdt_futures',
      exchange: 'binance'
    });
  }

  async adjustPosition(
    symbol: string, 
    newQuantity: number, 
    newLeverage?: number
  ): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>('/trading/adjust-position', {
      symbol,
      new_quantity: newQuantity,
      new_leverage: newLeverage,
      market_type: 'usdt_futures',
      exchange: 'binance'
    });
  }

  async setMode(mode: 'auto' | 'manual' | 'hybrid', threshold?: number): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>('/trading/mode', { 
      mode, 
      auto_approve_threshold: threshold 
    });
  }

  async healthCheck(): Promise<{ status: string }> {
    return api.get<{ status: string }>('/trading/health');
  }
}

export const tradingApi = new TradingApiService();
