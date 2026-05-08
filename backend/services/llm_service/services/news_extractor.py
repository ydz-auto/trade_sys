"""
News Extractor - 新闻结构化提取与黑天鹅检测
"""

import json
from typing import Dict, Optional
from . import llm


class NewsExtractor:
    """新闻提取器"""

    NEWS_ANALYSIS_PROMPT = """你是一个专业的加密货币新闻分析专家。
分析以下新闻，返回JSON格式：
{
    "sentiment": "bullish/bearish/neutral",
    "confidence": 0.0-1.0,
    "score": -1.0到1.0,
    "event_type": "black_swan/white_swan/regulatory/security/geopolitical/market/technology/macro/normal",
    "black_swan_score": 0.0-1.0,
    "urgency": "critical/urgent/normal/low",
    "affected_markets": ["BTC", "ETH", ...],
    "affected_symbols": ["BTC", "ETH", ...],
    "summary": "一句话摘要"
}

标题: {title}
内容: {content}
"""

    EXTRACTION_PROMPT = """从以下内容中提取结构化数据。
{prompt}

内容:
{content}
"""

    async def analyze_news(self, title: str, content: str) -> Dict:
        """分析新闻"""
        try:
            messages = [
                {"role": "system", "content": "你是一个专业的加密货币新闻分析专家。"},
                {"role": "user", "content": self.NEWS_ANALYSIS_PROMPT.format(title=title, content=content[:3000])}
            ]

            client = llm.openai_client.OpenAIClient()
            response = await client.chat(messages, model="gpt-4o-mini")

            result = json.loads(response.content)
            return {
                "sentiment": result.get("sentiment", "neutral"),
                "confidence": result.get("confidence", 0.5),
                "score": result.get("score", 0.0),
                "event_type": result.get("event_type", "normal"),
                "black_swan_score": result.get("black_swan_score", 0.0),
                "urgency": result.get("urgency", "normal"),
                "affected_markets": result.get("affected_markets", []),
                "affected_symbols": result.get("affected_symbols", []),
                "summary": result.get("summary", "")
            }

        except Exception as e:
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "score": 0.0,
                "event_type": "normal",
                "black_swan_score": 0.0,
                "urgency": "normal",
                "affected_markets": [],
                "affected_symbols": [],
                "summary": "",
                "error": str(e)
            }

    async def extract(self, content: str, prompt: str, schema: Optional[Dict] = None, model: str = "gpt-4o-mini") -> Dict:
        """结构化数据提取"""
        try:
            messages = [
                {"role": "system", "content": "你是一个专业的数据提取专家。"},
                {"role": "user", "content": self.EXTRACTION_PROMPT.format(prompt=prompt, content=content[:8000])}
            ]

            client = llm.openai_client.OpenAIClient()
            response = await client.chat(messages, model=model)

            result = json.loads(response.content)
            return result

        except Exception as e:
            return {"error": str(e)}
