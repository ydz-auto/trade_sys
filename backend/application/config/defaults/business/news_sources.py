"""
扩展版新闻源配置 - 20+主流来源
按地区和类型分类，覆盖全球主要加密货币媒体
"""

# RSS Feed 源
RSS_NEWS_SOURCES = {
    # 英文媒体
    "cointelegraph": "https://cointelegraph.com/rss",
    "cryptonews": "https://cryptonews.com/news/feed/",
    "theblock": "https://www.theblock.co/rss.xml",
    "decrypt": "https://decrypt.co/feed",
    "bitcoinist": "https://bitcoinist.com/feed/",
    "defiprime": "https://defiprime.com/feed.xml",
    
    # 中文加密媒体 - 使用正确的源
    "odaily": "https://www.odaily.news/feed",
    
    # 监管
    "cointelegraph_regulation": "https://cointelegraph.com/rss",
}

# 中文加密媒体配置（有些需要专门适配器）
CHINESE_MEDIA_CONFIG = {
    "odaily": {
        "name": "星球日报",
        "url": "https://www.odaily.news",
        "api_path": "/api/v1/news",
        "enabled": True
    },
    "jinse": {
        "name": "金色财经", 
        "url": "https://www.jinse.com",
        "api_path": "/openapi/v1/information",
        "enabled": True
    },
    "chainnews": {
        "name": "链闻",
        "url": "https://www.chainnews.com",
        "enabled": True
    },
    "panews": {
        "name": "PANews",
        "url": "https://www.panews.com",
        "enabled": True
    },
    "theblockbeats": {
        "name": "区块律动",
        "url": "https://www.theblockbeats.info",
        "enabled": True
    },
    "aicoin": {
        "name": "AICoin",
        "url": "https://www.aicoin.com",
        "enabled": True
    },
    "8btc": {
        "name": "巴比特",
        "url": "https://www.8btc.com",
        "enabled": True
    },
    "techflow": {
        "name": "深潮",
        "url": "https://www.techflowpost.com",
        "enabled": True
    }
}

# REST API 源
REST_NEWS_SOURCES = [
    {
        "name": "cryptopanic",
        "url": "https://cryptopanic.com/api/v1/posts/",
        "params": {
            "auth_token": "public",
            "currencies": "BTC,ETH",
            "kind": "news"
        }
    },
    {
        "name": "coingecko_news",
        "url": "https://www.coingecko.com/en/posts",
    },
]

# Twitter/X 关键词监控
TWITTER_KEYWORDS = [
    "Bitcoin OR BTC",
    "Ethereum OR ETH",
    "ETF approval",
    "crypto regulation",
    "BlackRock OR Fidelity ETF",
    "SEC crypto",
    "institutional adoption",
]

# Reddit 关键词
REDDIT_KEYWORDS = [
    "bitcoin",
    "ethereum",
    "cryptocurrency",
    "blockchain",
]

# 中文加密媒体预设列表
CHINESE_CRYPTO_MEDIA = [
    "Odaily 星球日报",
    "Jinse 金色财经",
    "ChainNews 链闻",
    "PANews",
    "TheBlockBeats 律动",
    "AICoin",
    "8BTC 巴比特",
    "CryptoForecast",
    "TechFlow 深潮",
    "BlockBeats 区块律动",
]
