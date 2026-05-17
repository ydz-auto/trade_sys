export enum NewsSourceType {
  RSS = 'rss',
  API = 'api',
  WEBSITE = 'website',
}

export enum NewsSourceStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  ERROR = 'error',
}

export enum ApiKeyType {
  LLM = 'llm',
  EXCHANGE = 'exchange',
  DATA = 'data',
  OTHER = 'other',
}

export interface NewsSource {
  id: string
  name: string
  type: NewsSourceType
  url: string
  enabled: boolean
  priority: number
  keywords: string[]
  blacklist: string[]
  update_interval: number
  status: NewsSourceStatus
  last_update?: string
  article_count?: number
  error_message?: string
  created_at: string
  updated_at: string
}

export interface CreateNewsSource {
  name: string
  type: NewsSourceType
  url: string
  enabled?: boolean
  priority?: number
  keywords?: string[]
  blacklist?: string[]
  update_interval?: number
}

export interface UpdateNewsSource {
  name?: string
  type?: NewsSourceType
  url?: string
  enabled?: boolean
  priority?: number
  keywords?: string[]
  blacklist?: string[]
  update_interval?: number
}

export interface ApiKey {
  id: string
  name: string
  type: ApiKeyType
  provider: string
  key_hint: string
  enabled: boolean
  is_valid?: boolean
  last_used?: string
  created_at: string
  updated_at: string
}

export interface CreateApiKey {
  name: string
  type: ApiKeyType
  provider: string
  api_key: string
  secret?: string
  enabled?: boolean
}

export interface UpdateApiKey {
  name?: string
  enabled?: boolean
  api_key?: string
  secret?: string
}

export interface LlmProvider {
  name: string
  provider: string
  base_url: string
  enabled: boolean
  priority: number
  models: string[]
  rate_limit_rpm: number
  rate_limit_tpm: number
  fallback_to?: string
}

export interface LlmConfig {
  providers: LlmProvider[]
  active_provider?: string
  fallback_chain: string[]
}

export interface DataSource {
  name: string
  type: string
  enabled: boolean
  config: Record<string, unknown>
}

export interface NewsSourceListResponse {
  sources: NewsSource[]
  total: number
}

export interface ApiKeyListResponse {
  keys: ApiKey[]
  total: number
}
