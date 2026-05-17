"""
External API 配置 - 外部服务 API 端点配置

所有外部 API 端点统一管理，方便：
1. 环境切换（开发/测试/生产）
2. 代理配置
3. API 版本管理
"""

import os

# =============================================================================
# 交易所 REST API 端点
# =============================================================================

EXCHANGE_REST_APIS = {
    "binance": {
        "spot": os.environ.get("BINANCE_SPOT_API_URL", "https://api.binance.com"),
        "futures": os.environ.get("BINANCE_FUTURES_API_URL", "https://fapi.binance.com"),
        "testnet_spot": os.environ.get("BINANCE_TESTNET_SPOT_URL", "https://testnet.binance.vision"),
        "testnet_futures": os.environ.get("BINANCE_TESTNET_FUTURES_URL", "https://testnet.binancefuture.com"),
    },
    "okx": {
        "api": os.environ.get("OKX_API_URL", "https://www.okx.com"),
        "demo": os.environ.get("OKX_DEMO_URL", "https://www.okx.com"),
    },
    "bybit": {
        "api": os.environ.get("BYBIT_API_URL", "https://api.bybit.com"),
        "testnet": os.environ.get("BYBIT_TESTNET_URL", "https://api-testnet.bybit.com"),
    },
    "gate": {
        "api": os.environ.get("GATE_API_URL", "https://api.gateio.ws"),
    },
    "coinbase": {
        "api": os.environ.get("COINBASE_API_URL", "https://api.exchange.coinbase.com"),
    },
    "coingecko": {
        "api": os.environ.get("COINGECKO_API_URL", "https://api.coingecko.com"),
    },
    "hyperliquid": {
        "api": os.environ.get("HYPERLIQUID_API_URL", "https://api.hyperliquid.xyz"),
    },
}

# =============================================================================
# 交易所 WebSocket 端点
# =============================================================================

EXCHANGE_WS_APIS = {
    "binance": {
        "spot": os.environ.get("BINANCE_SPOT_WS_URL", "wss://stream.binance.com:9443/ws"),
        "futures": os.environ.get("BINANCE_FUTURES_WS_URL", "wss://stream.binancefuture.com/ws"),
        "testnet_spot": os.environ.get("BINANCE_TESTNET_SPOT_WS_URL", "wss://testnet.binance.vision/ws"),
        "testnet_futures": os.environ.get("BINANCE_TESTNET_FUTURES_WS_URL", "wss://stream.binancefuture.com/ws"),
    },
    "okx": {
        "public": os.environ.get("OKX_PUBLIC_WS_URL", "wss://ws.okx.com:8443/ws/public"),
        "private": os.environ.get("OKX_PRIVATE_WS_URL", "wss://ws.okx.com:8443/ws/private"),
        "demo_public": os.environ.get("OKX_DEMO_PUBLIC_WS_URL", "wss://wspap.okx.com:8443/ws/public?brokerId=9999"),
        "demo_private": os.environ.get("OKX_DEMO_PRIVATE_WS_URL", "wss://wspap.okx.com:8443/ws/private?brokerId=9999"),
    },
    "bybit": {
        "public": os.environ.get("BYBIT_PUBLIC_WS_URL", "wss://stream.bybit.com/v5/public/spot"),
        "private": os.environ.get("BYBIT_PRIVATE_WS_URL", "wss://stream.bybit.com/v5/private"),
    },
}

# =============================================================================
# LLM API 端点
# =============================================================================

LLM_APIS = {
    "openai": {
        "api_url": os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1"),
    },
    "anthropic": {
        "api_url": os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1"),
    },
    "zhipu": {
        "api_url": os.environ.get("ZHIPU_API_URL", "https://open.bigmodel.cn/api/paas/v4"),
    },
    "siliconflow": {
        "api_url": os.environ.get("SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1"),
    },
    "deepseek": {
        "api_url": os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1"),
    },
    "qianfan": {
        "api_url": os.environ.get("QIANFAN_API_URL", "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop"),
    },
    "dashscope": {
        "api_url": os.environ.get("DASHSCOPE_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    },
    "minimax": {
        "api_url": os.environ.get("MINIMAX_API_URL", "https://api.minimax.chat/v1"),
    },
    "ollama": {
        "api_url": os.environ.get("OLLAMA_API_URL", "http://localhost:11434"),
    },
}

# =============================================================================
# 新闻源 API 端点
# =============================================================================

NEWS_APIS = {
    "odaily": {
        "base_url": os.environ.get("ODAILY_BASE_URL", "https://www.odaily.news"),
        "flash_api": os.environ.get("ODAILY_FLASH_API", "https://www.odaily.news/api/post/flash"),
        "list_api": os.environ.get("ODAILY_LIST_API", "https://www.odaily.news/api/post/list"),
    },
    "cointelegraph": {
        "rss_url": os.environ.get("COINTELEGRAPH_RSS_URL", "https://cointelegraph.com/rss"),
    },
    "coindesk": {
        "rss_url": os.environ.get("COINDESK_RSS_URL", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    },
    "cryptopanic": {
        "api_url": os.environ.get("CRYPTOPANIC_API_URL", "https://cryptopanic.com/api/v1/posts/"),
    },
}

# =============================================================================
# 宏观数据 API 端点
# =============================================================================

MACRO_APIS = {
    "gold": {
        "api_url": os.environ.get("GOLD_API_URL", "https://api.metals.live/v1/spot/gold"),
    },
    "oil": {
        "api_url": os.environ.get("OIL_API_URL", "https://api.metals.live/v1/spot/oil"),
    },
    "yahoo_finance": {
        "api_url": os.environ.get("YAHOO_FINANCE_API_URL", "https://api.yahoofinance.com/v1/finance"),
    },
}

# =============================================================================
# ETF 数据 API 端点
# =============================================================================

ETF_APIS = {
    "farside": {
        "api_url": os.environ.get("FARSIDE_API_URL", "https://api.farside.io/etf/flow"),
    },
    "sosovalue": {
        "api_url": os.environ.get("SOSOVALUE_API_URL", "https://api.sosovalue.com/etf/bitcoin"),
    },
    "coinglass": {
        "api_url": os.environ.get("COINGLASS_API_URL", "https://open-api-v4.coinglass.com/api/etf/bitcoin/flow-history"),
    },
}

# =============================================================================
# 便捷访问常量
# =============================================================================

BINANCE_REST_API = EXCHANGE_REST_APIS["binance"]["spot"]
BINANCE_WS_URL = EXCHANGE_WS_APIS["binance"]["spot"]
OKX_REST_API = EXCHANGE_REST_APIS["okx"]["api"]
OKX_WS_PUBLIC_URL = EXCHANGE_WS_APIS["okx"]["public"]
BYBIT_REST_API = EXCHANGE_REST_APIS["bybit"]["api"]
GATE_REST_API = EXCHANGE_REST_APIS["gate"]["api"]
COINGECKO_REST_API = EXCHANGE_REST_APIS["coingecko"]["api"]

OPENAI_API_URL = LLM_APIS["openai"]["api_url"]
ANTHROPIC_API_URL = LLM_APIS["anthropic"]["api_url"]
ZHIPU_API_URL = LLM_APIS["zhipu"]["api_url"]
DEEPSEEK_API_URL = LLM_APIS["deepseek"]["api_url"]
OLLAMA_API_URL = LLM_APIS["ollama"]["api_url"]

ODAILY_BASE_URL = NEWS_APIS["odaily"]["base_url"]
COINTELEGRAPH_RSS_URL = NEWS_APIS["cointelegraph"]["rss_url"]
