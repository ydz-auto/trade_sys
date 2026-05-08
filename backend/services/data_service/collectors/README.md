# Data Collectors

多数据源采集器模块，支持交易所、ETF、宏观、新闻、社交媒体等数据。

## 架构

```
collectors/
├── base_collector.py       # 收集器基类
├── multi_source.py         # 多源融合引擎
├── llm_scraper.py        # LLM爬虫
├── exchange_collector.py  # 交易所价格
├── etf_collector.py       # ETF资金流
├── macro_collector.py     # 宏观数据
├── news_collector.py      # 新闻资讯
├── social_media_collector.py  # 社交媒体
├── crypto_stock_collector.py  # 加密股票
└── trader_collector.py    # KOL观点追踪
```

## 安装依赖

```bash
cd backend/services/data_service
pip install -r requirements.txt
```

额外依赖：
```bash
pip install ccxt feedparser beautifulsoup4 lxml
```

## 使用示例

### 交易所价格

```python
from collectors import ExchangeCollector

collector = ExchangeCollector(
    symbols=["BTC", "ETH", "SOL"],
    exchanges=["binance", "okx", "coinbase", "hyperliquid"]
)

prices = await collector.collect()

# 各交易所分别保存
for symbol, multi_prices in prices.items():
    print(f"{symbol}:")
    for exchange, price in multi_prices.prices.items():
        print(f"  {exchange}: ${price.price}")

# 检查套利机会
arb = collector.check_arbitrage("BTC", threshold_percent=0.5)
if arb:
    print(f"套利: 在{arb['buy_exchange']}买入，在{arb['sell_exchange']}卖出")
```

### ETF资金流（多源融合）

```python
from collectors import ETFCollector

collector = ETFCollector()
flows = await collector.collect()

for symbol, result in flows.items():
    print(f"{symbol} ETF:")
    print(f"  融合后净流入: ${result.net_flow:,.0f}")
    print(f"  数据源: {result.sources_used}")
    print(f"  置信度: {result.confidence:.2f}")

    # 各源对比
    comparison = collector.compare_sources(symbol)
    for source, data in comparison.items():
        print(f"  {source}: ${data['net_flow']:,.0f} (偏差: {data['diff_from_fused']:,.0f})")
```

### 新闻 + 黑天鹅检测

```python
from collectors import NewsCollector

collector = NewsCollector()
news = await collector.collect()

# 获取最新新闻
latest = collector.get_latest_news(limit=10)

# 获取黑天鹅事件
black_swan = collector.get_black_swan_news()

# 按情绪筛选
bullish = collector.get_news_by_sentiment("bullish")
bearish = collector.get_news_by_sentiment("bearish")
```

### KOL观点追踪

```python
from collectors import TraderDataCollector

collector = TraderDataCollector()
data = await collector.collect()

# 聚合情绪
sentiment = collector.get_aggregate_sentiment()
print(f"整体情绪: {sentiment['sentiment']}")
print(f"看涨KOL: {sentiment['bullish_count']}")
print(f"看跌KOL: {sentiment['bearish_count']}")

# 按资产查看观点
btc_opinions = collector.get_opinions_by_asset("BTC")
```

### 加密股票

```python
from collectors import CryptoStockCollector

collector = CryptoStockCollector()
stocks = await collector.collect()

for symbol, stock in stocks.items():
    print(f"{symbol}: ${stock.price} ({stock.change_1d:+.2f}%)")

# 涨幅排行
top_movers = collector.get_top_movers()

# 与BTC相关性
corr = collector.get_corrrelation_with_btc()
```

## 多源融合

各收集器支持多源融合：

| 收集器 | 数据源 | 融合策略 |
|--------|--------|----------|
| ExchangeCollector | Binance, OKX, Coinbase, Gate, Bybit | Failover + 优先级 |
| ETFCollector | Farside, SoSoValue, CoinGlass | 加权平均 (0.45, 0.30, 0.25) |
| MacroCollector | Yahoo Finance, Metals.live, CME | 加权平均 (0.50, 0.30, 0.20) |
| NewsCollector | RSS + REST + LLM爬虫 | 置信度加权 |

## 环境变量

```bash
# LLM Service (调用情绪分析等)
LLM_SERVICE_URL=http://localhost:8001
LLM_SERVICE_API_KEY=...

# 第三方API
FIRECRAWL_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
DUNE_API_KEY=...

# Twitter API
TWITTER_BEARER_TOKEN=...

# Reddit API
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

## 配置

KOL列表在 `shared/config/defaults/datasource.py` 中配置：

```python
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
                "known_for": ["BTC", "BNB"],
            },
            # ...
        ]
    }
}
```

## 测试

```bash
cd backend/services/data_service

# 安装测试依赖
pip install pytest pytest-asyncio

# 运行所有测试
pytest

# 运行特定测试
pytest collectors/tests/test_exchange.py
pytest collectors/tests/test_news.py

# 查看详细输出
pytest -v
```

### 测试结构

```
collectors/tests/
├── __init__.py
├── conftest.py          # pytest fixtures
├── test_exchange.py      # 交易所测试
├── test_etf.py          # ETF测试
├── test_news.py          # 新闻+黑天鹅测试
└── test_trader.py       # KOL追踪测试
```

### 编写新测试

```python
# collectors/tests/test_new.py
import pytest
from collectors import NewCollector

class TestNewCollector:
    @pytest.fixture
    def collector(self):
        return NewCollector()

    @pytest.mark.asyncio
    async def test_collect(self, collector):
        result = await collector.collect()
        assert result is not None
```
