"""
Data Service Utilities 完整使用示例
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("utils_example")


async def demo_rss_parser():
    """演示 RSS 解析"""
    logger.info("=" * 60)
    logger.info("RSS Parser 示例")
    logger.info("=" * 60)
    
    from services.data_service.utils import RSSFetcher, PRESET_RSS_SOURCES
    
    # 只使用前 2 个源，避免请求太多
    sources = PRESET_RSS_SOURCES[:2]
    
    logger.info(f"抓取 {len(sources)} 个 RSS 源...")
    fetcher = RSSFetcher()
    articles = await fetcher.fetch_multiple(sources)
    
    logger.info(f"共抓取 {len(articles)} 篇文章")
    
    for i, article in enumerate(articles[:5]):
        logger.info(f"  [{i+1}] {article.title[:80]}...")


async def demo_symbol_extractor():
    """演示符号提取"""
    logger.info("\n" + "=" * 60)
    logger.info("Symbol Extractor 示例")
    logger.info("=" * 60)
    
    from services.data_service.utils import get_symbol_extractor
    
    extractor = get_symbol_extractor()
    
    test_texts = [
        "Bitcoin price today: BTC is up 5%",
        "Ethereum and SOL are rallying",
        "We bought some COIN stock and ETH",
    ]
    
    for text in test_texts:
        symbols = extractor.extract(text)
        
        logger.info(f"\n文本: {text}")
        
        for sym in symbols:
            logger.info(f"  - {sym.symbol} ({sym.category.value}) - {sym.name}")


async def demo_data_cleaner():
    """演示数据清洗"""
    logger.info("\n" + "=" * 60)
    logger.info("Data Cleaner 示例")
    logger.info("=" * 60)
    
    from services.data_service.utils import get_data_cleaner
    
    cleaner = get_data_cleaner()
    
    test_text = """
    Check out https://example.com! Contact us at info@example.com
    This is a sponsored ad: Buy Bitcoin now!
    The price is $45,000.50, up 5.2% today!
    """
    
    cleaned = cleaner.clean_text(
        test_text,
        remove_urls=True,
        remove_emails=True,
        remove_ads=True
    )
    
    logger.info(f"原文本:\n{repr(test_text)}")
    logger.info(f"清洗后:\n{cleaned.text}")
    logger.info(f"变更数: {cleaned.changes_made}")
    
    # 价格解析
    price = cleaner.clean_price_text("$45,000.50")
    pct = cleaner.clean_percentage_text("+5.2%")
    
    logger.info(f"价格: {price}")
    logger.info(f"涨幅: {pct}%")


async def demo_date_parser():
    """演示日期解析"""
    logger.info("\n" + "=" * 60)
    logger.info("Date Parser 示例")
    logger.info("=" * 60)
    
    from services.data_service.utils import get_date_parser
    from datetime import datetime
    
    parser = get_date_parser()
    
    test_dates = [
        "2024-01-15",
        "15 minutes ago",
        "2 hours ago",
        "just now",
        "Jan 20, 2024",
    ]
    
    for date_text in test_dates:
        parsed = parser.parse(date_text)
        
        logger.info(f"文本: {date_text}")
        
        if parsed.datetime:
            logger.info(f"  解析: {parsed.datetime}")
            logger.info(f"  格式: {parsed.format_used}")
        else:
            logger.info("  无法解析")


async def demo_html_parser():
    """演示 HTML 解析"""
    logger.info("\n" + "=" * 60)
    logger.info("HTML Parser 示例")
    logger.info("=" * 60)
    
    from services.data_service.utils import get_html_parser
    
    parser = get_html_parser()
    
    sample_html = """
    <html>
        <body>
            <article>
                <h1>Test Article</h1>
                <p>This is a <a href="https://example.com">test article</a>.</p>
                <p>It has <img src="image.jpg" alt="test image">an image.</p>
            </article>
        </body>
    </html>
    """
    
    article = parser.extract_article(sample_html)
    
    logger.info(f"标题: {article.title}")
    logger.info(f"内容长度: {len(article.content) if article.content else 0}")
    logger.info(f"图片数: {len(article.images)}")
    logger.info(f"链接数: {len(article.links)}")


async def demo_http_client():
    """演示 HTTP 客户端"""
    logger.info("\n" + "=" * 60)
    logger.info("HTTP Client 示例")
    logger.info("=" * 60)
    
    from services.data_service.utils import get_http_client
    
    client = get_http_client()
    
    # 简单 GET 请求
    response = await client.get("https://httpbin.org/json")
    
    if response.success:
        logger.info(f"状态码: {response.status_code}")
        logger.info(f"响应包含 JSON: {bool(response.json)}")
    else:
        logger.warning(f"请求失败: {response.error}")


async def main():
    """主函数"""
    logger.info("Data Service Utilities 使用示例")
    
    await demo_rss_parser()
    await demo_symbol_extractor()
    await demo_data_cleaner()
    await demo_date_parser()
    await demo_html_parser()
    await demo_http_client()
    
    logger.info("\n✅ 所有示例完成!")


if __name__ == "__main__":
    asyncio.run(main())
