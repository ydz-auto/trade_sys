"""
HTML Parser - 统一的 HTML 解析工具
所有采集器共用的 HTML 解析和提取能力
"""
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from infrastructure.logging import get_logger

logger = get_logger("utils.html_parser")


@dataclass
class ExtractedLink:
    """提取的链接"""
    url: str
    text: str
    title: Optional[str] = None
    is_external: bool = False


@dataclass
class ExtractedImage:
    """提取的图片"""
    url: str
    alt: Optional[str] = None
    title: Optional[str] = None


@dataclass
class ParsedArticle:
    """解析的文章内容"""
    title: Optional[str]
    content: Optional[str]
    summary: Optional[str]
    author: Optional[str]
    publish_date: Optional[str]
    images: List[ExtractedImage] = None
    links: List[ExtractedLink] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.links is None:
            self.links = []


class HTMLParser:
    """统一的 HTML 解析器
    
    所有采集器共用的 HTML 解析和提取能力
    """
    
    # 常见的内容选择器
    CONTENT_SELECTORS = [
        "article",
        "main",
        ".article-content",
        ".post-content",
        ".content-body",
        "#content",
        "[role='main']",
        "div[class*='content']",
        "div[class*='article']",
        "div[class*='post']",
        "section[class*='content']",
    ]
    
    # 标题选择器
    TITLE_SELECTORS = [
        "h1",
        ".article-title",
        ".post-title",
        "[class*='title']",
        "title",
    ]
    
    # 日期选择器
    DATE_SELECTORS = [
        "time",
        ".date",
        ".published",
        "[datetime]",
        "[class*='date']",
        "[class*='time']",
    ]
    
    # 作者选择器
    AUTHOR_SELECTORS = [
        ".author",
        "[rel='author']",
        "[class*='author']",
        ".byline",
    ]
    
    def __init__(self):
        pass
    
    def parse(
        self,
        html: str,
        parser: str = "html.parser",
        base_url: Optional[str] = None
    ) -> BeautifulSoup:
        """解析 HTML
        
        Args:
            html: HTML 字符串
            parser: 解析器，默认 html.parser
            base_url: 用于解析相对链接的基础 URL
            
        Returns:
            BeautifulSoup 对象
        """
        return BeautifulSoup(html, parser)
    
    def extract_article(
        self,
        html: str,
        base_url: Optional[str] = None
    ) -> ParsedArticle:
        """从 HTML 中提取文章内容
        
        Args:
            html: HTML 字符串
            base_url: 用于解析相对链接的基础 URL
            
        Returns:
            ParsedArticle 对象
        """
        soup = self.parse(html, base_url=base_url)
        
        result = ParsedArticle(
            title=self._extract_title(soup),
            content=self._extract_content(soup),
            summary=None,
            author=self._extract_author(soup),
            publish_date=self._extract_date(soup),
            images=self._extract_images(soup, base_url),
            links=self._extract_links(soup, base_url)
        )
        
        # 从内容中提取摘要
        if result.content:
            summary = self._extract_summary_from_content(result.content)
            result.summary = summary
        
        return result
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """提取标题"""
        for selector in self.TITLE_SELECTORS:
            elements = soup.select(selector)
            if elements:
                title = elements[0].get_text(strip=True)
                if title:
                    return title
        
        # 回退：找第一个 h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """提取内容"""
        # 尝试各种选择器
        for selector in self.CONTENT_SELECTORS:
            elements = soup.select(selector)
            if elements:
                content = elements[0].get_text(separator="\n", strip=True)
                if content and len(content) > 100:
                    return content
        
        # 回退：获取所有段落
        paragraphs = soup.find_all("p")
        if paragraphs:
            texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            if texts:
                return "\n\n".join(texts)
        
        # 最后回退：整个 body
        body = soup.body
        if body:
            return body.get_text(separator="\n", strip=True)
        
        return None
    
    def _extract_summary_from_content(self, content: str, max_length: int = 300) -> Optional[str]:
        """从内容中提取摘要"""
        if not content:
            return None
        
        # 简单截断
        if len(content) <= max_length:
            return content
        
        # 找第一个句子结束的地方
        cutoff = content[:max_length].rfind(".")
        if cutoff > 100:
            return content[:cutoff + 1]
        else:
            return content[:max_length] + "..."
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """提取作者"""
        for selector in self.AUTHOR_SELECTORS:
            elements = soup.select(selector)
            if elements:
                author = elements[0].get_text(strip=True)
                if author:
                    return author
        
        return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """提取日期"""
        # 找 time 标签的 datetime 属性
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            return time_tag.get("datetime")
        
        # 尝试其他选择器
        for selector in self.DATE_SELECTORS:
            elements = soup.select(selector)
            if elements:
                date_text = elements[0].get_text(strip=True)
                if date_text:
                    return date_text
        
        return None
    
    def _extract_images(
        self,
        soup: BeautifulSoup,
        base_url: Optional[str] = None
    ) -> List[ExtractedImage]:
        """提取图片"""
        images = []
        
        img_tags = soup.find_all("img")
        
        for img in img_tags:
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            
            # 解析相对 URL
            if base_url and not src.startswith(("http://", "https://")):
                src = urljoin(base_url, src)
            
            images.append(ExtractedImage(
                url=src,
                alt=img.get("alt"),
                title=img.get("title")
            ))
        
        return images
    
    def _extract_links(
        self,
        soup: BeautifulSoup,
        base_url: Optional[str] = None
    ) -> List[ExtractedLink]:
        """提取链接"""
        links = []
        
        a_tags = soup.find_all("a", href=True)
        
        for a in a_tags:
            href = a["href"]
            
            # 解析相对 URL
            if base_url and not href.startswith(("http://", "https://", "#", "mailto:", "tel:")):
                href = urljoin(base_url, href)
            
            is_external = href.startswith(("http://", "https://")) and base_url and base_url not in href
            
            links.append(ExtractedLink(
                url=href,
                text=a.get_text(strip=True),
                title=a.get("title"),
                is_external=is_external
            ))
        
        return links
    
    def extract_all_text(self, html: str) -> str:
        """从 HTML 中提取所有文本
        
        Args:
            html: HTML 字符串
            
        Returns:
            纯文本
        """
        soup = self.parse(html)
        return soup.get_text(separator="\n", strip=True)
    
    def extract_by_selector(
        self,
        html: str,
        selector: str,
        extract_attribute: Optional[str] = None
    ) -> List[str]:
        """通过选择器提取内容
        
        Args:
            html: HTML 字符串
            selector: CSS 选择器
            extract_attribute: 如果指定，提取该属性值，否则提取文本
            
        Returns:
            提取的内容列表
        """
        soup = self.parse(html)
        elements = soup.select(selector)
        
        results = []
        
        for elem in elements:
            if extract_attribute:
                value = elem.get(extract_attribute)
                if value:
                    results.append(value)
            else:
                text = elem.get_text(strip=True)
                if text:
                    results.append(text)
        
        return results
    
    def remove_tags(
        self,
        html: str,
        tags_to_remove: List[str] = None
    ) -> str:
        """移除指定的标签
        
        Args:
            html: HTML 字符串
            tags_to_remove: 要移除的标签列表，默认 ["script", "style"]
            
        Returns:
            清理后的 HTML
        """
        soup = self.parse(html)
        
        if not tags_to_remove:
            tags_to_remove = ["script", "style"]
        
        for tag in tags_to_remove:
            for elem in soup.find_all(tag):
                elem.decompose()
        
        return str(soup)
    
    def clean_html(
        self,
        html: str
    ) -> str:
        """清理 HTML，移除不需要的标签
        
        Args:
            html: HTML 字符串
            
        Returns:
            清理后的 HTML
        """
        cleaned = self.remove_tags(html)
        
        # 额外清理：移除注释
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
        
        return cleaned


# 全局单例
_html_parser: Optional[HTMLParser] = None

def get_html_parser() -> HTMLParser:
    """获取 HTML 解析器单例"""
    global _html_parser
    if _html_parser is None:
        _html_parser = HTMLParser()
    return _html_parser
