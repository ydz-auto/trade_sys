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
}

export const configApi = new ConfigApiService();
