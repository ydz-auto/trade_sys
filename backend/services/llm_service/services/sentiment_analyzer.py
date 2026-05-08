"""
Sentiment Analyzer - 情绪分析服务
"""

import json
from typing import Dict
from . import llm


class SentimentAnalyzer:
    """情绪分析器"""

    SENTIMENT_PROMPT = """你是一个专业的加密货币市场情绪分析师。
分析以下文本的情绪倾向，返回JSON格式：
{
    "sentiment": "bullish/bearish/neutral",
    "confidence": 0.0-1.0,
    "score": -1.0到1.0（正数看涨，负数看跌）
}

文本: {text}
"""

    async def analyze(self, text: str, model: str = "gpt-4o-mini") -> Dict:
        """分析文本情绪"""
        try:
            messages = [
                {"role": "system", "content": "你是一个专业的加密货币市场情绪分析师。"},
                {"role": "user", "content": self.SENTIMENT_PROMPT.format(text=text)}
            ]

            client = llm.openai_client.OpenAIClient()
            response = await client.chat(messages, model=model)

            result = json.loads(response.content)
            return {
                "sentiment": result.get("sentiment", "neutral"),
                "confidence": result.get("confidence", 0.5),
                "score": result.get("score", 0.0)
            }

        except Exception as e:
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "score": 0.0,
                "error": str(e)
            }
