import { api } from './client';
import type {
  NewsSource,
  CreateNewsSource,
  UpdateNewsSource,
  ApiKey,
  CreateApiKey,
  UpdateApiKey,
  LlmConfig,
  NewsSourceListResponse,
  ApiKeyListResponse,
} from './configApi';

export interface TwitterAccount {
  username: string;
  display_name?: string;
  enabled: boolean;
  priority: number;
  keywords: string[];
  is_p0: boolean;
}

export interface TwitterConfig {
  enabled: boolean;
  poll_interval: number;
  has_auth: boolean;
  accounts: TwitterAccount[];
  stats: Record<string, unknown>;
}

export interface TelegramChannel {
  channel_id: string;
  channel_name?: string;
  enabled: boolean;
  priority: number;
  keywords: string[];
}

export interface TelegramConfig {
  enabled: boolean;
  has_api_credentials: boolean;
  channels: TelegramChannel[];
  keywords: string[];
  crypto_keywords: string[];
  stats: Record<string, unknown>;
}

class ConfigApiService {
  async listNewsSources(): Promise<NewsSourceListResponse> {
    return api.get<NewsSourceListResponse>('/config/news-sources');
  }

  async createNewsSource(source: CreateNewsSource): Promise<NewsSource> {
    return api.post<NewsSource>('/config/news-sources', source);
  }

  async updateNewsSource(id: string, source: UpdateNewsSource): Promise<NewsSource> {
    return api.put<NewsSource>(`/config/news-sources/${id}`, source);
  }

  async deleteNewsSource(id: string): Promise<void> {
    return api.delete(`/config/news-sources/${id}`);
  }

  async listApiKeys(): Promise<ApiKeyListResponse> {
    return api.get<ApiKeyListResponse>('/config/api-keys');
  }

  async createApiKey(key: CreateApiKey): Promise<ApiKey> {
    return api.post<ApiKey>('/config/api-keys', key);
  }

  async updateApiKey(id: string, key: UpdateApiKey): Promise<ApiKey> {
    return api.put<ApiKey>(`/config/api-keys/${id}`, key);
  }

  async deleteApiKey(id: string): Promise<void> {
    return api.delete(`/config/api-keys/${id}`);
  }

  async getLlmConfig(): Promise<LlmConfig> {
    return api.get<LlmConfig>('/config/llm-config');
  }

  async updateLlmConfig(provider: string, config: Partial<LlmConfig>): Promise<LlmConfig> {
    return api.put<LlmConfig>(`/config/llm-config/${provider}`, config);
  }

  async getTwitterConfig(): Promise<TwitterConfig> {
    return api.get<TwitterConfig>('/config/twitter');
  }

  async updateTwitterConfig(config: Partial<TwitterConfig>): Promise<{ success: boolean; config: TwitterConfig }> {
    return api.put('/config/twitter', config);
  }

  async getTwitterAccounts(): Promise<{ accounts: TwitterAccount[]; total: number }> {
    return api.get('/config/twitter/accounts');
  }

  async createTwitterAccount(account: Partial<TwitterAccount>): Promise<{ success: boolean; account: TwitterAccount }> {
    return api.post('/config/twitter/accounts', account);
  }

  async updateTwitterAccount(username: string, updates: Partial<TwitterAccount>): Promise<{ success: boolean; account: TwitterAccount }> {
    return api.put(`/config/twitter/accounts/${username}`, updates);
  }

  async deleteTwitterAccount(username: string): Promise<{ success: boolean }> {
    return api.delete(`/config/twitter/accounts/${username}`);
  }

  async getTelegramConfig(): Promise<TelegramConfig> {
    return api.get<TelegramConfig>('/config/telegram');
  }

  async updateTelegramConfig(config: Partial<TelegramConfig>): Promise<{ success: boolean; config: TelegramConfig }> {
    return api.put('/config/telegram', config);
  }

  async getTelegramChannels(): Promise<{ channels: TelegramChannel[]; total: number }> {
    return api.get('/config/telegram/channels');
  }

  async createTelegramChannel(channel: Partial<TelegramChannel>): Promise<{ success: boolean; channel: TelegramChannel }> {
    return api.post('/config/telegram/channels', channel);
  }

  async updateTelegramChannel(channelId: string, updates: Partial<TelegramChannel>): Promise<{ success: boolean; channel: TelegramChannel }> {
    return api.put(`/config/telegram/channels/${channelId}`, updates);
  }

  async deleteTelegramChannel(channelId: string): Promise<{ success: boolean }> {
    return api.delete(`/config/telegram/channels/${channelId}`);
  }
}

export const configApi = new ConfigApiService();
