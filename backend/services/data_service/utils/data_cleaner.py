"""
Data Cleaner - 统一的数据清洗和标准化工具
所有采集器共用
"""
import re
import string
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

from infrastructure.logging import get_logger

logger = get_logger("utils.data_cleaner")


@dataclass
class CleanedData:
    """清洗后的数据"""
    text: str
    original_text: str
    removed_entities: List[str] = None
    changes_made: int = 0
    
    def __post_init__(self):
        if self.removed_entities is None:
            self.removed_entities = []


class DataCleaner:
    """统一的数据清洗器
    
    所有采集器共用的数据清洗和标准化能力
    """
    
    # 常见的不需要的模式
    AD_PATTERNS = [
        r"\b(?:ad|advertisement|sponsored|promoted)\s*:\s*",
        r"\b(?:paid content|paid promotion|paid post)\s*:\s*",
        r"\b(?:disclosure|disclaimer)\s*:\s*",
    ]
    
    # URL 模式
    URL_PATTERN = re.compile(
        r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+",
        re.IGNORECASE
    )
    
    # 邮箱模式
    EMAIL_PATTERN = re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    )
    
    # 电话号码模式
    PHONE_PATTERN = re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    )
    
    # 空白字符规范化
    WHITESPACE_PATTERN = re.compile(r"\s+")
    
    # 特殊字符去除
    SPECIAL_CHARS = r"[]{}()<>'\"|\\"
    
    def __init__(self):
        self._ad_patterns = [re.compile(p, re.IGNORECASE) for p in self.AD_PATTERNS]
    
    def clean_text(
        self,
        text: str,
        remove_urls: bool = True,
        remove_emails: bool = True,
        remove_phones: bool = True,
        remove_ads: bool = True,
        normalize_whitespace: bool = True,
        strip_chars: bool = True
    ) -> CleanedData:
        """清洗文本
        
        Args:
            text: 要清洗的文本
            remove_urls: 是否移除 URL
            remove_emails: 是否移除邮箱
            remove_phones: 是否移除电话
            remove_ads: 是否移除广告标记
            normalize_whitespace: 是否规范化空白
            strip_chars: 是否去除特殊字符
            
        Returns:
            CleanedData 包含清洗后的文本和变更信息
        """
        if not text:
            return CleanedData(text="", original_text="")
        
        original_text = text
        cleaned_text = text
        changes = 0
        removed = []
        
        # 1. 移除广告标记
        if remove_ads:
            for pattern in self._ad_patterns:
                new_text, count = pattern.subn("", cleaned_text)
                if count > 0:
                    changes += count
                    cleaned_text = new_text
        
        # 2. 移除 URL
        if remove_urls:
            new_text, count = self.URL_PATTERN.subn("", cleaned_text)
            if count > 0:
                changes += count
                removed.append(f"urls({count})")
                cleaned_text = new_text
        
        # 3. 移除邮箱
        if remove_emails:
            new_text, count = self.EMAIL_PATTERN.subn("", cleaned_text)
            if count > 0:
                changes += count
                removed.append(f"emails({count})")
                cleaned_text = new_text
        
        # 4. 移除电话
        if remove_phones:
            new_text, count = self.PHONE_PATTERN.subn("", cleaned_text)
            if count > 0:
                changes += count
                removed.append(f"phones({count})")
                cleaned_text = new_text
        
        # 5. 规范化空白
        if normalize_whitespace:
            new_text = self.WHITESPACE_PATTERN.sub(" ", cleaned_text).strip()
            if new_text != cleaned_text:
                cleaned_text = new_text
        
        # 6. 去除首尾特殊字符
        if strip_chars:
            cleaned_text = cleaned_text.strip(string.whitespace + self.SPECIAL_CHARS)
        
        return CleanedData(
            text=cleaned_text,
            original_text=original_text,
            removed_entities=removed,
            changes_made=changes
        )
    
    def truncate_text(
        self,
        text: str,
        max_length: int = 5000,
        at_word_boundary: bool = True,
        suffix: str = "..."
    ) -> str:
        """截断文本
        
        Args:
            text: 要截断的文本
            max_length: 最大长度
            at_word_boundary: 是否在单词边界截断
            suffix: 截断后的后缀
            
        Returns:
            截断后的文本
        """
        if not text or len(text) <= max_length:
            return text
        
        if at_word_boundary:
            # 找最近的单词边界
            cutoff = max_length - len(suffix)
            if cutoff <= 0:
                return suffix
            
            # 向前找空格
            while cutoff > 0 and not text[cutoff].isspace():
                cutoff -= 1
            
            if cutoff == 0:
                # 没有空格，直接截断
                return text[:max_length - len(suffix)] + suffix
            else:
                return text[:cutoff] + suffix
        else:
            return text[:max_length - len(suffix)] + suffix
    
    def normalize_case(
        self,
        text: str,
        mode: str = "sentence"
    ) -> str:
        """标准化大小写
        
        Args:
            text: 要标准化的文本
            mode: "sentence" (首字母大写), "lower", "upper", "title"
            
        Returns:
            标准化后的文本
        """
        if not text:
            return text
        
        if mode == "lower":
            return text.lower()
        elif mode == "upper":
            return text.upper()
        elif mode == "title":
            return text.title()
        elif mode == "sentence":
            # 句首大写
            if not text:
                return text
            return text[0].upper() + text[1:].lower()
        else:
            return text
    
    def remove_stopwords(
        self,
        text: str,
        stopwords: List[str] = None,
        language: str = "english"
    ) -> str:
        """移除停用词（简单实现）"""
        if not text:
            return text
        
        default_stopwords = {
            "english": {
                "the", "a", "an", "and", "or", "but", "is", "are",
                "was", "were", "be", "been", "being", "have", "has",
                "had", "do", "does", "did", "will", "would", "could",
                "should", "may", "might", "must", "shall", "can"
            }
        }
        
        stopwords_set = set(stopwords or default_stopwords.get(language, []))
        
        words = text.split()
        filtered_words = [w for w in words if w.lower() not in stopwords_set]
        
        return " ".join(filtered_words)
    
    def clean_price_text(self, price_text: str) -> Optional[float]:
        """从价格文本中提取数值
        
        Args:
            price_text: 价格文本，如 "$1,234.56"
            
        Returns:
            提取的浮点数或 None
        """
        if not price_text:
            return None
        
        try:
            # 移除货币符号和千分位分隔符
            cleaned = re.sub(r"[$,\s]", "", price_text)
            
            # 提取数字
            match = re.search(r"-?\d+\.?\d*", cleaned)
            
            if match:
                return float(match.group(0))
        except Exception:
            pass
        
        return None
    
    def clean_percentage_text(self, pct_text: str) -> Optional[float]:
        """从百分比文本中提取数值
        
        Args:
            pct_text: 百分比文本，如 "+5.2%"
            
        Returns:
            提取的浮点数（带符号）或 None
        """
        if not pct_text:
            return None
        
        try:
            # 移除百分号
            cleaned = re.sub(r"[%\s]", "", pct_text)
            
            # 提取数字
            match = re.search(r"-?\d+\.?\d*", cleaned)
            
            if match:
                return float(match.group(0))
        except Exception:
            pass
        
        return None


# 全局单例
_cleaner: Optional[DataCleaner] = None

def get_data_cleaner() -> DataCleaner:
    """获取数据清洗器单例"""
    global _cleaner
    if _cleaner is None:
        _cleaner = DataCleaner()
    return _cleaner
