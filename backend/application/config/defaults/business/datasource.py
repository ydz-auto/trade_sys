"""
DataSource 配置 - 业务配置
"""

DATASOURCE_CONFIGS = {
    "datasource.symbols": ["BTC", "ETH", "SOL", "DOGE"],
    "datasource.exchanges": ["binance", "okx", "hyperliquid", "coinbase", "gate"],
    "datasource.check_interval": 60,

    "datasource.exchange.binance.enabled": True,
    "datasource.exchange.okx.enabled": True,
    "datasource.exchange.hyperliquid.enabled": True,
    "datasource.exchange.coinbase.enabled": True,
    "datasource.exchange.gate.enabled": True,

    "datasource.news.feeds": {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "cryptopanic": "https://cryptopanic.com/api/v1/posts/",
    },
    "datasource.news.check_interval": 300,
    "datasource.news.black_swan_enabled": True,

    "datasource.macro.gold_api": "https://api.metals.live/v1/spot/gold",
    "datasource.macro.oil_api": "https://api.metals.live/v1/spot/oil",
    "datasource.macro.dxy_api": "https://api.yahoofinance.com/v1/finance",
    "datasource.macro.check_interval": 3600,

    "datasource.etf.enabled": True,
    "datasource.etf.check_interval": 3600,
    "datasource.etf.symbols": ["BTC", "ETH"],
    "datasource.etf.api_farside": "https://api.farside.io/etf/flow",
    "datasource.etf.api_sosovalue": "https://api.sosovalue.com/etf/bitcoin",
    "datasource.etf.api_coinglass": "https://open-api-v4.coinglass.com/api/etf/bitcoin/flow-history",

    "datasource.social.enabled": False,
    "datasource.social.twitter.enabled": True,
    "datasource.social.twitter.check_interval": 300,
    "datasource.social.reddit.enabled": True,
    "datasource.social.reddit.check_interval": 600,
    "datasource.social.telegram.enabled": False,

    "datasource.crypto_stocks.enabled": True,
    "datasource.crypto_stocks.check_interval": 60,
    "datasource.crypto_stocks.symbols": ["MSTR", "COIN", "MARA", "RIOT", "CRCL", "HOOD"],

    "datasource.trader.enabled": False,
    "datasource.trader.check_interval": 300,
}


DATASOURCE_SCHEMAS = {
    "datasource.symbols": {
        "value_type": "list",
        "default": ["BTC", "ETH", "SOL", "DOGE"],
        "description": "Trading symbols to monitor",
    },
    "datasource.exchanges": {
        "value_type": "list",
        "default": ["binance", "okx", "hyperliquid"],
        "description": "Exchanges to collect data from",
        "options": ["binance", "okx", "hyperliquid", "coinbase", "gate", "bybit"],
    },
    "datasource.check_interval": {
        "value_type": "int",
        "default": 60,
        "description": "Data collection check interval in seconds",
        "min_value": 10,
        "max_value": 3600,
    },
    "datasource.news.feeds": {
        "value_type": "dict",
        "default": {
            "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "cointelegraph": "https://cointelegraph.com/rss"
        },
        "description": "News RSS feed URLs",
    },
    "datasource.news.black_swan_enabled": {
        "value_type": "bool",
        "default": True,
        "description": "Enable black swan event detection",
    },
    "datasource.social.enabled": {
        "value_type": "bool",
        "default": False,
        "description": "Enable social media data collection",
    },
    "datasource.social.twitter.kol_handles": {
        "value_type": "list",
        "default": ["@cz_binance", "@saylor", "@PeterBrandt"],
        "description": "Twitter KOL handles to track",
    },
    "datasource.crypto_stocks.enabled": {
        "value_type": "bool",
        "default": True,
        "description": "Enable crypto-related stocks collection",
    },
    "datasource.crypto_stocks.symbols": {
        "value_type": "list",
        "default": ["MSTR", "COIN", "MARA", "RIOT"],
        "description": "Crypto-related stock symbols",
    },
    "datasource.trader.enabled": {
        "value_type": "bool",
        "default": False,
        "description": "Enable trader data (KOL) collection",
    },
    "datasource.trader.kol_list": {
        "value_type": "list",
        "default": [
            {"id": "cz_binance", "twitter": "@cz_binance", "name": "CZ", "followers": 5000000, "credibility": 0.9},
            {"id": "saylor", "twitter": "@saylor", "name": "Michael Saylor", "followers": 2000000, "credibility": 0.85},
            {"id": "peter_brandt", "twitter": "@PeterBrandt", "name": "Peter Brandt", "followers": 1500000, "credibility": 0.80},
        ],
        "description": "KOL list for trader data collection",
    },
}


KOL_TRADER_LIST = {
    "whale_trackers": {
        "description": "巨鲸追踪",
        "traders": [
            {
                "id": "cz_binance",
                "name": "CZ",
                "platforms": {"twitter": "@cz_binance"},
                "followers": 5000000,
                "credibility": 0.9,
                "historical_accuracy": 0.75,
                "known_for": ["BTC", "BNB"],
                "wallet_addresses": []
            },
            {
                "id": "saylor",
                "name": "Michael Saylor",
                "platforms": {"twitter": "@saylor"},
                "followers": 2000000,
                "credibility": 0.85,
                "historical_accuracy": 0.80,
                "known_for": ["BTC"],
                "wallet_addresses": []
            },
            {
                "id": "peter_brandt",
                "name": "Peter Brandt",
                "platforms": {"twitter": "@PeterBrandt"},
                "followers": 1500000,
                "credibility": 0.80,
                "historical_accuracy": 0.70,
                "known_for": ["BTC", "ETH", "技术分析"],
                "wallet_addresses": []
            },
        ]
    },
    "defi_traders": {
        "description": "DeFi交易员",
        "traders": [
            {
                "id": "herb_chronos",
                "name": "Herb",
                "platforms": {"twitter": "@Herb_Chronos"},
                "followers": 100000,
                "credibility": 0.75,
                "historical_accuracy": 0.65,
                "known_for": ["DeFi", "Arbitrage"],
                "wallet_addresses": []
            }
        ]
    }
}


MULTI_SOURCE_CONFIG = {
    "market": {
        "sources": [
            {"name": "binance", "type": "rest_api", "priority": 1, "collector": "CCXTCollector"},
            {"name": "okx", "type": "rest_api", "priority": 2, "collector": "CCXTCollector"},
            {"name": "hyperliquid", "type": "rest_api", "priority": 3, "collector": "CCXTCollector"},
            {"name": "coinbase", "type": "rest_api", "priority": 4, "collector": "RESTCollector"},
        ],
        "strategy": {"method": "failover", "health_check": True}
    },
    "etf": {
        "sources": [
            {"name": "farside", "type": "llm_scraper", "priority": 1, "weight": 0.45},
            {"name": "sosovalue", "type": "npm_package", "priority": 2, "weight": 0.30},
            {"name": "coinglass", "type": "rest_api", "priority": 3, "weight": 0.25},
        ],
        "fusion": {"method": "weighted_average", "diff_threshold_percent": 10}
    },
    "macro": {
        "sources": [
            {"name": "yahoo_finance", "type": "rest_api", "priority": 1, "weight": 0.50},
            {"name": "metals_live", "type": "rest_api", "priority": 2, "weight": 0.30},
            {"name": "jinshi", "type": "llm_scraper", "priority": 3, "weight": 0.20},
        ],
        "fusion": {"method": "weighted_average", "diff_threshold_percent": 5}
    },
    "news": {
        "sources": [
            {"name": "coindesk_rss", "type": "rss", "priority": 1, "weight": 0.25},
            {"name": "cryptopanic", "type": "rest_api", "priority": 2, "weight": 0.25},
            {"name": "cointelegraph", "type": "llm_scraper", "priority": 3, "weight": 0.25},
            {"name": "jinshi", "type": "llm_scraper", "priority": 4, "weight": 0.25},
        ],
        "fusion": {"method": "confidence_weighted", "dedup": {"enabled": True}}
    },
    "crypto_stocks": {
        "sources": [
            {"name": "yahoo_finance", "type": "rest_api", "priority": 1, "weight": 0.70},
            {"name": "alpha_vantage", "type": "rest_api", "priority": 2, "weight": 0.30},
        ],
        "fusion": {"method": "weighted_average", "diff_threshold_percent": 2}
    },
    "trader": {
        "sources": [
            {"name": "twitter_kol", "type": "llm_scraper", "priority": 1, "weight": 0.35},
            {"name": "dune_analytics", "type": "rest_api", "priority": 2, "weight": 0.25},
            {"name": "nansen", "type": "rest_api", "priority": 3, "weight": 0.20},
            {"name": "telegram_signals", "type": "llm_scraper", "priority": 4, "weight": 0.15},
        ],
        "fusion": {"method": "llm_confidence_weighted"}
    }
}
