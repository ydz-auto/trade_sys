"""
Social Analyzer - 社交媒体分析服务
"""

import json
from typing import Dict
from . import llm


class SocialAnalyzer:
    """社交媒体分析器"""

    TRADER_ANALYSIS_PROMPT = """你是一个加密货币交易员言论分析专家。
从以下交易员的社交媒体文本中提取结构化信息，返回JSON格式：
{
    "观点": "一句话概括核心观点",
    "情绪": "bullish/bearish/neutral",
    "情绪置信度": 0.0-1.0,
    "资产": ["BTC", "ETH", ...],
    "时间预期": "short/medium/long",
    "论据": ["理由1", "理由2"],
    "影响力评分": 0.0-1.0
}

交易员: {trader_name}
平台: {platform}
内容: {content}
"""

    async def analyze(self, content: str, platform: str = "twitter", trader_name: str = "Unknown") -> Dict:
        """分析社交媒体内容"""
        try:
            messages = [
                {"role": "system", "content": "你是一个加密货币交易员言论分析专家。"},
                {"role": "user", "content": self.TRADER_ANALYSIS_PROMPT.format(
                    trader_name=trader_name,
                    platform=platform,
                    content=content
                )}
            ]

            client = llm.openai_client.OpenAIClient()
            response = await client.chat(messages, model="gpt-4o-mini")

            result = json.loads(response.content)
            return {
                "观点": result.get("观点", ""),
                "情绪": result.get("情绪", "neutral"),
                "情绪置信度": result.get("情绪置信度", 0.5),
                "资产": result.get("资产", []),
                "时间预期": result.get("时间预期", "medium"),
                "论据": result.get("论据", []),
                "影响力评分": result.get("影响力评分", 0.5),
                "platform": platform
            }

        except Exception as e:
            return {
                "观点": "",
                "情绪": "neutral",
                "情绪置信度": 0.5,
                "资产": [],
                "时间预期": "medium",
                "论据": [],
                "影响力评分": 0.0,
                "platform": platform,
                "error": str(e)
            }
