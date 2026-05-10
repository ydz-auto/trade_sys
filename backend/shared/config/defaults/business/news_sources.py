"""
扩展版新闻源配置 - 20+主流来源
按地区和类型分类，覆盖全球主要加密货币媒体
"""

RSS_NEWS_SOURCES = {
    # 英文媒体
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "cryptonews": "https://cryptonews.com/news/feed/",
    "theblock": "https://www.theblock.co/rss.xml",
    "decrypt": "https://decrypt.co/feed",
    "coinmarketcap": "https://coinmarketcap.com/alexandria RSS",
    "bitcoinist": "https://bitcoinist.com/feed/",
    " CCN": "https://www.ccn.com/feed/",
    "newsBTC": "https://www.newsbtc.com/feed/",
    "dailyHODL": "https://dailyhodl.com/feed/",
    "blockworks": "https://blockworks.co/news/feed",

    # 中文媒体
    "jinse": "https://jinse.cc/rss",
    "odaily": "https://www.odaily.com/feed",
    "chainnews": "https://www.chainnews.com/rss",
    "aicoin": "https://www.aicoin.com/rss/news",
    "bihu": "https://mp.weixin.qq.com/rss?openid=",

    # DeFi / 合约
    "defiprime": "https://defiprime.com/feed.xml",
    "thedefiant": "https://thedefiant.io/feed/",

    # 监管
    "cointelegraph_regulation": "https://cointelegraph.com/rss",
}

# REST API 来源
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
