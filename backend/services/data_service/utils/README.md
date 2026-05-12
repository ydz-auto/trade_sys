# Data Service Utilities - 数据服务工具库

统一的基础能力模块，供所有采集器共用。

## 目录

- [概述](#概述)
- [模块说明](#模块说明)
- [使用示例](#使用示例)
- [架构](#架构)

## 概述

这个工具库将所有采集器的通用功能抽取出来，实现：
- **统一接口** - 所有采集器使用相同的基础能力
- **代码复用** - 避免重复实现相同功能
- **易于维护** - 修改一个地方即可影响所有采集器

## 模块说明

### 1. HTTP Client (`http_client.py`)
- **功能** - 带熔断、重试的 HTTP 客户端
- **类**
  - `EnhancedHTTPClient` - 增强的 HTTP 客户端
  - `HTTPResponse` - HTTP 响应
- **函数**
  - `get_http_client()` - 获取单例

### 2. RSS Parser (`rss_parser.py`)
- **功能** - 统一的 RSS 解析和抓取
- **类**
  - `RSSParser` - RSS 解析器
  - `RSSFetcher` - RSS 抓取器（带弹性能力）
  - `RSSArticle` - 文章结构
  - `RSSSource` - 源配置
- **常量**
  - `PRESET_RSS_SOURCES` - 预设源

### 3. Data Cleaner (`data_cleaner.py`)
- **功能** - 数据清洗和标准化
- **类**
  - `DataCleaner` - 数据清洗器
  - `CleanedData` - 清洗后数据
- **函数**
  - `get_data_cleaner()` - 获取单例

### 4. Symbol Extractor (`symbol_extractor.py`)
- **功能** - 加密货币符号识别
- **类**
  - `SymbolExtractor` - 符号提取器
  - `ExtractedSymbol` - 提取的符号
  - `SymbolCategory` - 符号分类枚举
- **函数**
  - `get_symbol_extractor()` - 获取单例

### 5. Date Parser (`date_parser.py`)
- **功能** - 统一的日期解析
- **类**
  - `DateParser` - 日期解析器
  - `ParsedDate` - 解析的日期
- **函数**
  - `get_date_parser()` - 获取单例

### 6. HTML Parser (`html_parser.py`)
- **功能** - HTML 解析和内容提取
- **类**
  - `HTMLParser` - HTML 解析器
  - `ParsedArticle` - 解析的文章
  - `ExtractedLink` - 提取的链接
  - `ExtractedImage` - 提取的图片
- **函数**
  - `get_html_parser()` - 获取单例

## 使用示例

### RSS 解析

```python
from services.data_service.utils import RSSFetcher, PRESET_RSS_SOURCES

fetcher = RSSFetcher()
articles = await fetcher.fetch_multiple(PRESET_RSS_SOURCES)

for article in articles:
    print(f"{article.source}: {article.title}")
```

### 符号提取

```python
from services.data_service.utils import get_symbol_extractor

extractor = get_symbol_extractor()
symbols = extractor.extract("Bitcoin and Ethereum are up today")

for symbol in symbols:
    print(f"{symbol.symbol} ({symbol.category})")
```

### 数据清洗

```python
from services.data_service.utils import get_data_cleaner

cleaner = get_data_cleaner()
cleaned = cleaner.clean_text(text, remove_urls=True)

print(f"Cleaned: {cleaned.text}")
print(f"Removed: {cleaned.removed_entities}")
```

### 日期解析

```python
from services.data_service.utils import get_date_parser

parser = get_date_parser()
parsed = parser.parse("2 hours ago")

if parsed.datetime:
    print(f"Date: {parsed.datetime}")
```

### HTML 解析

```python
from services.data_service.utils import get_html_parser

parser = get_html_parser()
article = parser.extract_article(html)

print(f"Title: {article.title}")
print(f"Content: {article.summary}")
```

### HTTP 请求

```python
from services.data_service.utils import get_http_client

client = get_http_client()
response = await client.get("https://example.com")

if response.success:
    print(response.json or response.text)
```

## 架构

```
data_service/utils/
├── __init__.py
├── http_client.py      - 增强 HTTP 客户端
├── rss_parser.py       - RSS 解析
├── data_cleaner.py     - 数据清洗
├── symbol_extractor.py - 符号提取
├── date_parser.py      - 日期解析
└── html_parser.py      - HTML 解析
```

**设计原则**：
1. **单例模式** - 主要工具使用单例避免重复初始化
2. **纯函数/类** - 尽量无状态，易于测试
3. **完整类型提示** - 便于 IDE 自动补全
4. **默认配置** - 开箱即用，也支持自定义
