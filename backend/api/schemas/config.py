"""
Config Schemas - Configuration Management Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class NewsSourceType(str, Enum):
    """新闻源类型"""
    RSS = "rss"
    API = "api"
    WEBSITE = "website"


class NewsSourceStatus(str, Enum):
    """新闻源状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class NewsSourceBase(BaseModel):
    """新闻源基础模型"""
    name: str = Field(..., description="新闻源名称")
    type: NewsSourceType = Field(default=NewsSourceType.RSS, description="新闻源类型")
    url: str = Field(..., description="新闻源URL")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=1, ge=1, le=10, description="优先级")
    keywords: List[str] = Field(default=[], description="关键词过滤")
    blacklist: List[str] = Field(default=[], description="黑名单关键词")
    update_interval: int = Field(default=300, description="更新间隔(秒)")


class NewsSourceCreate(NewsSourceBase):
    """创建新闻源"""
    pass


class NewsSourceUpdate(BaseModel):
    """更新新闻源"""
    name: Optional[str] = None
    type: Optional[NewsSourceType] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    keywords: Optional[List[str]] = None
    blacklist: Optional[List[str]] = None
    update_interval: Optional[int] = None


class NewsSourceResponse(NewsSourceBase):
    """新闻源响应"""
    id: str
    status: NewsSourceStatus = NewsSourceStatus.ACTIVE
    last_update: Optional[datetime] = None
    article_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class NewsSourceListResponse(BaseModel):
    """新闻源列表响应"""
    sources: List[NewsSourceResponse]
    total: int


class ApiKeyType(str, Enum):
    """API Key类型"""
    LLM = "llm"
    EXCHANGE = "exchange"
    DATA = "data"
    OTHER = "other"


class ApiKeyBase(BaseModel):
    """API Key基础模型"""
    name: str = Field(..., description="名称")
    type: ApiKeyType = Field(..., description="类型")
    provider: str = Field(..., description="提供商")
    key_hint: Optional[str] = Field(None, description="Key提示(如前4后4位)")


class ApiKeyCreate(BaseModel):
    """创建API Key"""
    name: str = Field(..., description="名称")
    type: ApiKeyType = Field(..., description="类型")
    provider: str = Field(..., description="提供商")
    api_key: str = Field(..., description="API Key(加密存储)")
    secret: Optional[str] = Field(None, description="Secret(如适用)")


class ApiKeyUpdate(BaseModel):
    """更新API Key"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    api_key: Optional[str] = None
    secret: Optional[str] = None


class ApiKeyResponse(ApiKeyBase):
    """API Key响应(不返回完整key)"""
    id: str
    enabled: bool = True
    is_valid: Optional[bool] = None
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ApiKeyListResponse(BaseModel):
    """API Key列表响应"""
    keys: List[ApiKeyResponse]
    total: int


class LlmProviderConfig(BaseModel):
    """LLM提供商配置"""
    name: str
    provider: str
    base_url: str
    enabled: bool = True
    priority: int = 1
    models: List[str] = []
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 10000
    fallback_to: Optional[str] = None


class LlmConfigResponse(BaseModel):
    """LLM配置响应"""
    providers: List[LlmProviderConfig]
    active_provider: Optional[str] = None
    fallback_chain: List[str] = []


class DataSourceConfig(BaseModel):
    """数据源配置"""
    name: str
    type: str
    enabled: bool = True
    config: Dict[str, Any] = {}


class DataSourceListResponse(BaseModel):
    """数据源列表响应"""
    sources: List[DataSourceConfig]


class TwitterAccountConfig(BaseModel):
    """Twitter 账号配置"""
    username: str = Field(..., description="Twitter 用户名")
    display_name: Optional[str] = Field(None, description="显示名称")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=1, ge=1, le=10, description="优先级")
    keywords: List[str] = Field(default=[], description="关键词过滤")
    is_p0: bool = Field(default=False, description="是否为 P0 账号")


class TwitterCookieConfigResponse(BaseModel):
    """Twitter Cookie 配置响应"""
    enabled: bool = Field(default=True, description="是否启用 Cookie Monitor")
    poll_interval: int = Field(default=60, description="轮询间隔(秒)")
    has_auth: bool = Field(default=False, description="是否已配置认证")
    accounts: List[TwitterAccountConfig] = Field(default=[], description="监控账号列表")
    stats: Dict[str, Any] = Field(default_factory=dict, description="统计信息")


class TwitterAccountCreate(BaseModel):
    """创建 Twitter 账号"""
    username: str = Field(..., description="Twitter 用户名")
    display_name: Optional[str] = None
    enabled: bool = True
    priority: int = 1
    keywords: List[str] = []
    is_p0: bool = False


class TwitterAccountUpdate(BaseModel):
    """更新 Twitter 账号"""
    display_name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    keywords: Optional[List[str]] = None
    is_p0: Optional[bool] = None


class TwitterConfigUpdate(BaseModel):
    """更新 Twitter 配置"""
    enabled: Optional[bool] = None
    poll_interval: Optional[int] = None


class TelegramChannelConfig(BaseModel):
    """Telegram 频道配置"""
    channel_id: str = Field(..., description="频道 ID 或用户名")
    channel_name: Optional[str] = Field(None, description="频道名称")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=1, ge=1, le=10, description="优先级")
    keywords: List[str] = Field(default=[], description="关键词过滤")


class TelegramConfigResponse(BaseModel):
    """Telegram 配置响应"""
    enabled: bool = Field(default=False, description="是否启用")
    has_api_credentials: bool = Field(default=False, description="是否已配置 API 凭证")
    channels: List[TelegramChannelConfig] = Field(default=[], description="监控频道列表")
    keywords: List[str] = Field(default=[], description="全局关键词")
    crypto_keywords: List[str] = Field(default=[], description="加密货币关键词")
    stats: Dict[str, Any] = Field(default_factory=dict, description="统计信息")


class TelegramChannelCreate(BaseModel):
    """创建 Telegram 频道"""
    channel_id: str = Field(..., description="频道 ID 或用户名")
    channel_name: Optional[str] = None
    enabled: bool = True
    priority: int = 1
    keywords: List[str] = []


class TelegramChannelUpdate(BaseModel):
    """更新 Telegram 频道"""
    channel_name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    keywords: Optional[List[str]] = None


class TelegramConfigUpdate(BaseModel):
    """更新 Telegram 配置"""
    enabled: Optional[bool] = None
    keywords: Optional[List[str]] = None
    crypto_keywords: Optional[List[str]] = None
