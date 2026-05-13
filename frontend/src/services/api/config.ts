export interface RiskConfig {
  max_position_value: number
  max_position_count: number
  max_leverage: number
  daily_loss_limit_pct: number
  drawdown_limit_pct: number
  order_size_limit: number
  cooldown_seconds: number
  symbol_blacklist: string[]
  stop_loss_default_pct: number
  take_profit_default_pct: number
}

export interface StrategyConfig {
  trend_weight: number
  flow_weight: number
  sentiment_weight: number
  macro_weight: number
  signal_threshold: number
  min_confidence: number
}

export interface SystemConfig {
  log_level: string
  metrics_enabled: boolean
  health_check_interval: number
  replay_speed: number
}

export interface ExchangeConfig {
  exchange: string
  enabled: boolean
  testnet: boolean
  priority: number
  symbols: string[]
  timeout: number
}

export interface ConfigResponse<T> {
  config: T
  updated_at?: string
}

export interface ExchangeListResponse {
  exchanges: Record<string, ExchangeConfig>
}
