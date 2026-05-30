from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class LLMAnalysisResult:
    title_zh: str = ""
    content_zh: str = ""
    sentiment: str = "neutral"
    importance: float = 0.5
    relevance: float = 0.5
    confidence: float = 0.5
    symbols: List[str] = field(default_factory=list)
    narratives: List[str] = field(default_factory=list)
    actionable: bool = False
    source_quality: float = 0.5
    content_quality: float = 0.5
    timeliness: float = 0.5
    reasoning: str = ""
    scored_by: str = "llm"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title_zh": self.title_zh,
            "content_zh": self.content_zh,
            "sentiment": self.sentiment,
            "importance": self.importance,
            "relevance": self.relevance,
            "confidence": self.confidence,
            "symbols": self.symbols,
            "narratives": self.narratives,
            "actionable": self.actionable,
            "source_quality": self.source_quality,
            "content_quality": self.content_quality,
            "timeliness": self.timeliness,
            "reasoning": self.reasoning,
            "scored_by": self.scored_by
        }


class KeywordScorer:

    SENTIMENT_KEYWORDS = {
        "bullish": [
            "surge", "rally", "soar", "jump", "gain", "rise", "high", "breakout",
            "bull", "buy", "ETF", "approval", "positive", "上涨", "暴涨", "突破", "利好",
            "approved", "success", "growth", "adoption"
        ],
        "bearish": [
            "crash", "plunge", "dump", "drop", "fall", "decline", "low",
            "bear", "sell", "hack", "ban", "negative", "下跌", "暴跌", "跌破", "利空",
            "rejected", "failure", "crisis", "scam"
        ]
    }

    IMPORTANCE_KEYWORDS = {
        "high": [
            "ETF", "SEC", "FDA", "regulation", "hack", "crash", "breakout",
            "批准", "重大", "突破", "崩盘", "暴跌", "黑天鹅"
        ],
        "medium": [
            "update", "launch", "partnership", "upgrade", "listing",
            "升级", "合作", "发布", "上线"
        ]
    }

    SYMBOLS = {
        "BTC": ["BTC", "BITCOIN", "比特币"],
        "ETH": ["ETH", "ETHEREUM", "以太坊"],
        "SOL": ["SOL", "SOLANA"],
        "XRP": ["XRP", "RIPPLE"],
        "BNB": ["BNB", "BINANCE"],
        "ADA": ["ADA", "CARDANO"],
        "DOGE": ["DOGE", "DOGECOIN"],
        "DOT": ["DOT", "POLKADOT"],
        "AVAX": ["AVAX", "AVALANCHE"],
        "LINK": ["LINK", "CHAINLINK"],
    }

    NARRATIVES = {
        "ETF": ["ETF", "SPOT", "BLACKROCK", "Fidelity"],
        "DeFi": ["DeFi", "DEX", "LENDING", "uniswap", "compound"],
        "NFT": ["NFT", "opensea", "blur", "collection"],
        "Layer2": ["Layer2", "L2", "Arbitrum", "Optimism", "Polygon"],
        "Regulation": ["SEC", "CFTC", "regulation", "regulatory", "监管"],
        "Institutional": ["institutional", "bank", "fund", "hedge fund"],
        "Bitcoin": ["bitcoin", "BTC", "halving", "mining"],
        "Ethereum": ["ethereum", "ETH", "merge", "upgrade", "ETH2"],
    }

    KEYWORD_TRANSLATION = {
        "surge": "暴涨",
        "rally": "上涨",
        "soar": "飙升",
        "jump": "跳涨",
        "gain": "上涨",
        "rise": "上升",
        "high": "新高",
        "breakout": "突破",
        "bull": "看涨",
        "buy": "买入",
        "etf": "ETF",
        "approval": "获批",
        "positive": "利好",
        "crash": "暴跌",
        "plunge": "跳水",
        "dump": "砸盘",
        "drop": "下跌",
        "fall": "下跌",
        "decline": "下跌",
        "low": "新低",
        "bear": "看跌",
        "sell": "卖出",
        "hack": "被盗",
        "ban": "禁令",
        "negative": "利空",
        "bitcoin": "比特币",
        "btc": "BTC",
        "ethereum": "以太坊",
        "eth": "ETH",
        "solana": "Solana",
        "sol": "SOL",
    }

    @classmethod
    def _simple_translate_title(cls, title: str) -> str:
        result = title
        for en, zh in cls.KEYWORD_TRANSLATION.items():
            result = result.replace(en, zh, 1)
            result = result.replace(en.title(), zh)
        return result

    @classmethod
    def _simple_summarize(cls, content: str) -> str:
        if not content:
            return ""
        return content[:100].strip()

    @classmethod
    def score(cls, title: str, content: str = "") -> LLMAnalysisResult:
        title_zh = cls._simple_translate_title(title)

        content_zh = cls._simple_summarize(content)

        text = (title + " " + content).lower()

        bullish_count = sum(1 for kw in cls.SENTIMENT_KEYWORDS["bullish"]
                          if kw.lower() in text)
        bearish_count = sum(1 for kw in cls.SENTIMENT_KEYWORDS["bearish"]
                          if kw.lower() in text)

        if bullish_count > bearish_count:
            sentiment = "bullish"
        elif bearish_count > bullish_count:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        importance = 0.5
        if any(kw.lower() in text for kw in cls.IMPORTANCE_KEYWORDS["high"]):
            importance = 0.85
        elif any(kw.lower() in text for kw in cls.IMPORTANCE_KEYWORDS["medium"]):
            importance = 0.65

        symbols = []
        for symbol, keywords in cls.SYMBOLS.items():
            if any(kw.lower() in text for kw in keywords):
                if symbol not in symbols:
                    symbols.append(symbol)

        narratives = []
        for narrative, keywords in cls.NARRATIVES.items():
            if any(kw.lower() in text for kw in keywords):
                narratives.append(narrative)

        actionable = importance > 0.7 and len(symbols) > 0

        confidence = 0.6

        return LLMAnalysisResult(
            title_zh=title_zh,
            content_zh=content_zh,
            sentiment=sentiment,
            importance=importance,
            relevance=0.5,
            confidence=confidence,
            symbols=symbols[:5],
            narratives=narratives[:3],
            actionable=actionable,
            source_quality=0.5,
            content_quality=0.5,
            timeliness=0.5,
            reasoning="Keyword-based scoring (fallback)",
            scored_by="keyword"
        )
