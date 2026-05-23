"""
LLM Scraper - LLM爬虫封装（通过llm_service微服务调用）
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.http.client import HTTPClient, HTTPRequest, HTTPMethod
from infrastructure.llm.client import LLMServiceClient, StreamChunk
from infrastructure.logging import get_logger

logger = get_logger("collectors.llm_scraper")


class ScraperType(Enum):
    FIRECRAWL = "firecrawl"
    CRAWL4AI = "crawl4ai"
    BEAUTIFULSOUP = "beautifulsoup"
    REST_API = "rest_api"


@dataclass
class ScrapedContent:
    """爬取的内容"""
    url: str
    content: str
    markdown: Optional[str] = None
    metadata: Optional[Dict] = None
    success: bool = True
    error: Optional[str] = None
    scraper_type: str = ""


class LLMScraperBase:
    """LLM爬虫基类"""

    def __init__(self):
        self.llm_client: Optional[LLMServiceClient] = None

    def set_llm_client(self, client: LLMServiceClient):
        """设置LLM服务客户端"""
        self.llm_client = client

    async def scrape(self, url: str, **kwargs) -> ScrapedContent:
        """抓取单个URL"""
        raise NotImplementedError

    async def batch_scrape(self, urls: List[str], **kwargs) -> List[ScrapedContent]:
        """批量抓取"""
        tasks = [self.scrape(url, **kwargs) for url in urls]
        return await asyncio.gather(*tasks)


class FireCrawlScraper(LLMScraperBase):
    """FireCrawl爬虫"""

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.base_url = "https://api.firecrawl.dev/v0"
        self.scraper_type = ScraperType.FIRECRAWL

    async def scrape(self, url: str, formats: List[str] = None) -> ScrapedContent:
        """使用FireCrawl抓取"""
        if not self.api_key:
            return ScrapedContent(
                url=url,
                content="",
                success=False,
                error="FIRECRAWL_API_KEY not set",
                scraper_type=self.scraper_type.value
            )

        try:
            http = HTTPClient()
            request = HTTPRequest(
                url=f"{self.base_url}/scrape",
                method=HTTPMethod.POST,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json_data={
                    "url": url,
                    "formats": formats or ["markdown", "html"]
                },
                timeout=30.0
            )

            async with http:
                response = await http.request(request)

            if response.success and response.body:
                data = response.body
                return ScrapedContent(
                    url=url,
                    content=data.get("content", ""),
                    markdown=data.get("markdown"),
                    metadata=data.get("metadata"),
                    success=True,
                    scraper_type=self.scraper_type.value
                )
            else:
                return ScrapedContent(
                    url=url,
                    content="",
                    success=False,
                    error=f"HTTP {response.status_code}",
                    scraper_type=self.scraper_type.value
                )

        except Exception as e:
            logger.error(f"FireCrawl scrape error: {e}")
            return ScrapedContent(
                url=url,
                content="",
                success=False,
                error=str(e),
                scraper_type=self.scraper_type.value
            )

    async def crawl(self, urls: List[str]) -> List[ScrapedContent]:
        """批量抓取"""
        if not self.api_key:
            return [ScrapedContent(
                url=u,
                content="",
                success=False,
                error="FIRECRAWL_API_KEY not set"
            ) for u in urls]

        try:
            http = HTTPClient()
            request = HTTPRequest(
                url=f"{self.base_url}/crawl",
                method=HTTPMethod.POST,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json_data={"urls": urls},
                timeout=60.0
            )

            async with http:
                response = await http.request(request)

            if response.success and response.body:
                data = response.body
                return [
                    ScrapedContent(
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        markdown=item.get("markdown"),
                        success=True,
                        scraper_type=self.scraper_type.value
                    )
                    for item in data.get("data", [])
                ]

        except Exception as e:
            logger.error(f"FireCrawl crawl error: {e}")

        return [ScrapedContent(
            url=u,
            content="",
            success=False,
            error="Crawl failed"
        ) for u in urls]


class BeautifulSoupScraper(LLMScraperBase):
    """传统BeautifulSoup爬虫（备选）"""

    def __init__(self):
        super().__init__()
        self.scraper_type = ScraperType.BEAUTIFULSOUP

    async def scrape(self, url: str, selector: str = None) -> ScrapedContent:
        """使用BeautifulSoup抓取"""
        try:
            http = HTTPClient()
            request = HTTPRequest(url=url, timeout=10.0)

            async with http:
                response = await http.request(request)

            if not response.success:
                return ScrapedContent(
                    url=url,
                    content="",
                    success=False,
                    error=f"HTTP {response.status_code}",
                    scraper_type=self.scraper_type.value
                )

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            if selector:
                elements = soup.select(selector)
                content = "\n".join([elem.get_text(strip=True) for elem in elements])
            else:
                content = soup.get_text(separator="\n", strip=True)

            return ScrapedContent(
                url=url,
                content=content[:5000],
                success=True,
                scraper_type=self.scraper_type.value
            )

        except ImportError as e:
            return ScrapedContent(
                url=url,
                content="",
                success=False,
                error=f"Missing dependency: {e}",
                scraper_type=self.scraper_type.value
            )
        except Exception as e:
            logger.error(f"BeautifulSoup scrape error: {e}")
            return ScrapedContent(
                url=url,
                content="",
                success=False,
                error=str(e),
                scraper_type=self.scraper_type.value
            )


class LLMStructuredExtractor:
    """LLM结构化数据提取器（通过llm_service）"""

    def __init__(self, llm_client: LLMServiceClient = None):
        self.llm_client = llm_client or LLMServiceClient()

    async def extract(
        self,
        content: str,
        prompt: str,
        output_schema: Dict = None
    ) -> Dict:
        """使用LLM从内容中提取结构化数据"""
        try:
            return await self.llm_client.structured_extraction(
                content=content,
                prompt=prompt,
                output_schema=output_schema
            )
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            return {"error": str(e)}

    async def extract_etf_data(self, content: str) -> Dict:
        """从ETF页面提取数据"""
        prompt = """
        从以下比特币ETF资金流页面内容中提取今日数据。
        请提取：
        1. 日期
        2. 各ETF净流入（IBIT, FBTC, ARKB等）
        3. 总净流入
        输出JSON格式，包含date, total_flow, etf_flows字段。
        """
        return await self.extract(content, prompt, {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "total_flow": {"type": "number"},
                "etf_flows": {"type": "object"}
            }
        })

    async def extract_trader_statement(self, content: str) -> Dict:
        """从交易员言论中提取观点"""
        prompt = """
        从以下交易员社交媒体文本中提取结构化信息：
        1. 核心观点（用一句话概括）
        2. 情绪倾向（看涨/看跌/中性）
        3. 情绪置信度（0-1）
        4. 提到的资产（BTC/ETH等）
        5. 时间预期（短期/中期/长期）
        """
        return await self.extract(content, prompt, {
            "type": "object",
            "properties": {
                "观点": {"type": "string"},
                "情绪": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                "情绪置信度": {"type": "number"},
                "资产": {"type": "array", "items": {"type": "string"}},
                "时间预期": {"type": "string"}
            }
        })

    async def stream_extract(
        self,
        content: str,
        prompt: str
    ) -> AsyncIterator[StreamChunk]:
        """流式提取"""
        messages = [
            {"role": "system", "content": "你是一个专业的数据提取专家。请根据用户提供的prompt从内容中提取结构化数据。"},
            {"role": "user", "content": f"Prompt: {prompt}\n\n内容:\n{content[:8000]}"}
        ]

        async for chunk in self.llm_client.stream_chat(messages):
            yield chunk


class ScraperFactory:
    """爬虫工厂"""

    _scrapers = {
        ScraperType.FIRECRAWL: FireCrawlScraper,
        ScraperType.BEAUTIFULSOUP: BeautifulSoupScraper,
    }

    @classmethod
    def create(cls, scraper_type: str, **kwargs):
        """创建爬虫实例"""
        try:
            stype = ScraperType(scraper_type)
            scraper_class = cls._scrapers.get(stype)
            if scraper_class:
                return scraper_class(**kwargs)
        except ValueError:
            pass
        return BeautifulSoupScraper(**kwargs)

    @classmethod
    def create_all(cls, **kwargs) -> Dict[str, LLMScraperBase]:
        """创建所有可用爬虫"""
        result = {}
        for stype, scraper_class in cls._scrapers.items():
            try:
                result[stype.value] = scraper_class(**kwargs)
            except Exception as e:
                logger.warning(f"Failed to create {stype.value}: {e}")
        return result
