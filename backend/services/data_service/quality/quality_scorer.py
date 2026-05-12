"""
Quality Scorer - 可信度打分和来源白名单
基于多维度评估新闻质量
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from infrastructure.logging import get_logger

logger = get_logger("quality.scorer")


class SourceTrustLevel(Enum):
    """来源可信等级"""
    TRUSTED = "trusted"
    VERIFIED = "verified"
    COMMUNITY = "community"
    UNKNOWN = "unknown"
    SUSPICIOUS = "suspicious"


@dataclass
class SourceConfig:
    """数据源配置"""
    name: str
    url: str
    trust_level: SourceTrustLevel
    base_score: float
    categories: List[str] = field(default_factory=list)
    language: str = "en"
    update_frequency: int = 60
    enabled: bool = True


@dataclass
class QualityScore:
    """质量评分"""
    total_score: float
    source_score: float
    content_score: float
    trust_score: float
    factors: Dict[str, float] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)
    recommendation: str = "pass"


class QualityScorer:
    """质量打分器
    
    多维度评估新闻质量：
    - 来源可信度
    - 内容质量
    - 信任度指标
    - 可疑特征检测
    """
    
    TRUSTED_SOURCES = {
        "coindesk": SourceConfig(
            name="CoinDesk",
            url="coindesk.com",
            trust_level=SourceTrustLevel.TRUSTED,
            base_score=0.95,
            categories=["crypto", "news"]
        ),
        "cointelegraph": SourceConfig(
            name="CoinTelegraph",
            url="cointelegraph.com",
            trust_level=SourceTrustLevel.TRUSTED,
            base_score=0.90,
            categories=["crypto", "news"]
        ),
        "theblock": SourceConfig(
            name="The Block",
            url="theblock.co",
            trust_level=SourceTrustLevel.TRUSTED,
            base_score=0.90,
            categories=["crypto", "news"]
        ),
        "decrypt": SourceConfig(
            name="Decrypt",
            url="decrypt.co",
            trust_level=SourceTrustLevel.VERIFIED,
            base_score=0.85,
            categories=["crypto", "news"]
        ),
        "bitcoinist": SourceConfig(
            name="Bitcoinist",
            url="bitcoinist.com",
            trust_level=SourceTrustLevel.VERIFIED,
            base_score=0.80,
            categories=["crypto", "news"]
        ),
        "cryptonews": SourceConfig(
            name="CryptoNews",
            url="cryptonews.com",
            trust_level=SourceTrustLevel.VERIFIED,
            base_score=0.75,
            categories=["crypto", "news"]
        ),
        "dailyhodl": SourceConfig(
            name="DailyHODL",
            url="dailyhodl.com",
            trust_level=SourceTrustLevel.COMMUNITY,
            base_score=0.70,
            categories=["crypto", "opinion"]
        ),
    }
    
    SUSPICIOUS_PATTERNS = {
        "clickbait_title": [
            r"you won't believe",
            r"shocking",
            r"unbelievable",
            r"breaking:.*actually",
            r"this.*changed.*everything",
            r"what.*happens.*next",
        ],
        "promotional": [
            r"\b(buy now|limited time|act fast|don't miss)\b",
            r"\b(free|winner|congratulations)\b",
            r"\b(guaranteed|no risk|100%)\b",
        ],
        "emotional": [
            r"!!!{2,}",
            r"\?\?+",
            r"^[^a-z]*[A-Z]{4,}",
        ]
    }
    
    MIN_CONTENT_LENGTH = 100
    MAX_CONTENT_LENGTH = 50000
    MIN_TITLE_LENGTH = 10
    MAX_TITLE_LENGTH = 300
    
    def __init__(self):
        self._sources = self.TRUSTED_SOURCES.copy()
        self._stats = {
            "total_scored": 0,
            "passed": 0,
            "flagged": 0,
            "rejected": 0
        }
    
    def register_source(self, source: SourceConfig):
        """注册数据源"""
        self._sources[source.name.lower()] = source
    
    def score(
        self,
        title: str,
        content: str,
        source: str,
        url: str = "",
        author: str = ""
    ) -> QualityScore:
        """评估内容质量"""
        self._stats["total_scored"] += 1
        
        source_score = self._score_source(source, url)
        content_score = self._score_content(title, content)
        trust_score, factors, flags = self._score_trust(title, content, author)
        
        weights = {
            "source": 0.4,
            "content": 0.35,
            "trust": 0.25
        }
        
        total_score = (
            source_score * weights["source"] +
            content_score * weights["content"] +
            trust_score * weights["trust"]
        )
        
        recommendation = self._get_recommendation(total_score, flags)
        
        if recommendation == "pass":
            self._stats["passed"] += 1
        elif recommendation == "flag":
            self._stats["flagged"] += 1
        else:
            self._stats["rejected"] += 1
        
        return QualityScore(
            total_score=total_score,
            source_score=source_score,
            content_score=content_score,
            trust_score=trust_score,
            factors=factors,
            flags=flags,
            recommendation=recommendation
        )
    
    def _score_source(self, source: str, url: str) -> float:
        """评估来源得分"""
        source_lower = source.lower()
        
        if source_lower in self._sources:
            return self._sources[source_lower].base_score
        
        for name, config in self._sources.items():
            if name in source_lower or name in url.lower():
                return config.base_score * 0.8
        
        return 0.5
    
    def _score_content(
        self,
        title: str,
        content: str
    ) -> float:
        """评估内容质量"""
        factors = {}
        
        title_length_score = self._score_title_length(title)
        content_length_score = self._score_content_length(content)
        structure_score = self._score_structure(content)
        readability_score = self._score_readability(content)
        
        factors["title_length"] = title_length_score
        factors["content_length"] = content_length_score
        factors["structure"] = structure_score
        factors["readability"] = readability_score
        
        total = (
            title_length_score * 0.2 +
            content_length_score * 0.3 +
            structure_score * 0.25 +
            readability_score * 0.25
        )
        
        return total
    
    def _score_title_length(
        self,
        title: str
    ) -> float:
        """标题长度评分"""
        length = len(title)
        
        if length < self.MIN_TITLE_LENGTH:
            return max(0, length / self.MIN_TITLE_LENGTH * 0.5)
        elif length > self.MAX_TITLE_LENGTH:
            return max(0, 1 - (length - self.MAX_TITLE_LENGTH) / 100)
        else:
            return 1.0
    
    def _score_content_length(
        self,
        content: str
    ) -> float:
        """内容长度评分"""
        length = len(content)
        
        if length < self.MIN_CONTENT_LENGTH:
            return max(0, length / self.MIN_CONTENT_LENGTH * 0.3)
        elif length > self.MAX_CONTENT_LENGTH:
            return max(0, 1 - (length - self.MAX_CONTENT_LENGTH) / 10000)
        else:
            return 1.0
    
    def _score_structure(self, content: str) -> float:
        """内容结构评分"""
        score = 1.0
        
        paragraphs = content.split("\n\n")
        if len(paragraphs) < 2:
            score -= 0.2
        
        sentences = re.split(r'[.!?]+', content)
        avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        
        if avg_sentence_len > 50:
            score -= 0.2
        elif avg_sentence_len < 5:
            score -= 0.1
        
        return max(0, score)
    
    def _score_readability(self, content: str) -> float:
        """可读性评分"""
        words = content.split()
        if not words:
            return 0
        
        avg_word_len = sum(len(w) for w in words) / len(words)
        
        if avg_word_len > 10:
            return 0.7
        elif avg_word_len < 3:
            return 0.8
        else:
            return 1.0
    
    def _score_trust(
        self,
        title: str,
        content: str,
        author: str
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """信任度评分"""
        factors = {}
        flags = []
        title_lower = title.lower()
        content_lower = content.lower()
        
        clickbait_score = 1.0
        for pattern in self.SUSPICIOUS_PATTERNS["clickbait_title"]:
            if re.search(pattern, title_lower):
                clickbait_score -= 0.3
                flags.append("clickbait_title")
        
        factors["clickbait"] = clickbait_score
        
        promo_score = 1.0
        for pattern in self.SUSPICIOUS_PATTERNS["promotional"]:
            if re.search(pattern, content_lower):
                promo_score -= 0.2
                flags.append("promotional_content")
        
        factors["promotional"] = promo_score
        
        emotional_score = 1.0
        for pattern in self.SUSPICIOUS_PATTERNS["emotional"]:
            if re.search(pattern, title):
                emotional_score -= 0.2
                flags.append("emotional_title")
        
        factors["emotional"] = emotional_score
        
        has_author = 1.0 if author else 0.7
        factors["has_author"] = has_author
        
        has_data = 1.0
        if not re.search(r'\d+', content):
            has_data = 0.7
            flags.append("no_data")
        
        factors["has_data"] = has_data
        
        total = (
            clickbait_score * 0.25 +
            promo_score * 0.2 +
            emotional_score * 0.15 +
            has_author * 0.15 +
            has_data * 0.25
        )
        
        return total, factors, flags
    
    def _get_recommendation(
        self,
        score: float,
        flags: List[str]
    ) -> str:
        """获取推荐结果"""
        if score < 0.3:
            return "reject"
        elif score < 0.5 or len(flags) >= 3:
            return "flag"
        else:
            return "pass"
    
    def get_trust_level(self, source: str) -> SourceTrustLevel:
        """获取来源信任等级"""
        source_lower = source.lower()
        
        if source_lower in self._sources:
            return self._sources[source_lower].trust_level
        
        for name, config in self._sources.items():
            if name in source_lower:
                return config.trust_level
        
        return SourceTrustLevel.UNKNOWN
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "pass_rate": self._stats["passed"] / max(self._stats["total_scored"], 1),
            "flag_rate": self._stats["flagged"] / max(self._stats["total_scored"], 1),
            "reject_rate": self._stats["rejected"] / max(self._stats["total_scored"], 1)
        }


# 全局打分器
_scorer: Optional[QualityScorer] = None

def get_scorer() -> QualityScorer:
    """获取打分器单例"""
    global _scorer
    if _scorer is None:
        _scorer = QualityScorer()
    return _scorer
