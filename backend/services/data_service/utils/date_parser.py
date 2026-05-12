"""
Date Parser - 统一的日期解析工具
所有采集器共用的日期解析和转换能力
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass

from infrastructure.logging import get_logger

logger = get_logger("utils.date_parser")


@dataclass
class ParsedDate:
    """解析的日期"""
    datetime: Optional[datetime]
    raw_text: str
    confidence: float = 1.0
    format_used: Optional[str] = None
    timezone_info: Optional[str] = None


class DateParser:
    """统一的日期解析器
    
    所有采集器共用的日期解析和转换能力
    """
    
    # 常见日期格式
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y年%m月%d日",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M",
    ]
    
    # 相对时间词
    RELATIVE_PATTERNS = {
        r"(\d+)\s*(?:second|seconds|sec|secs)": "seconds",
        r"(\d+)\s*(?:minute|minutes|min|mins)": "minutes",
        r"(\d+)\s*(?:hour|hours|hr|hrs)": "hours",
        r"(\d+)\s*(?:day|days|dy|dys)": "days",
        r"(\d+)\s*(?:week|weeks|wk|wks)": "weeks",
        r"(\d+)\s*(?:month|months|mo|mos)": "months",
        r"(\d+)\s*(?:year|years|yr|yrs)": "years",
    }
    
    # "ago" 模式
    AGO_PATTERNS = [
        r"(\d+)\s*(?:second|seconds|sec|secs)\s+ago",
        r"(\d+)\s*(?:minute|minutes|min|mins)\s+ago",
        r"(\d+)\s*(?:hour|hours|hr|hrs)\s+ago",
        r"(\d+)\s*(?:day|days|dy|dys)\s+ago",
        r"(\d+)\s*(?:week|weeks|wk|wks)\s+ago",
        r"(\d+)\s*(?:month|months|mo|mos)\s+ago",
        r"(\d+)\s*(?:year|years|yr|yrs)\s+ago",
    ]
    
    # "just now" 等
    INSTANT_PATTERNS = [
        r"just\s+now",
        r"right\s+now",
        r"a\s+moment\s+ago",
        r"moments?\s+ago",
    ]
    
    def __init__(self):
        self._date_format_regexes = self._compile_date_format_regexes()
    
    def _compile_date_format_regexes(self) -> List[re.Pattern]:
        """编译日期格式的正则表达式
        
        用于快速判断文本是否可能是日期
        """
        patterns = []
        
        # 基础日期模式
        patterns.append(re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"))
        patterns.append(re.compile(r"\d{1,2}[-/]\d{1,2}[-/]\d{4}"))
        patterns.append(re.compile(r"\w+\s+\d{1,2},\s+\d{4}"))
        patterns.append(re.compile(r"\d{4}\s*\w+\s*\d{1,2}"))
        
        return patterns
    
    def parse(
        self,
        date_text: str,
        default_timezone: str = "UTC",
        reference_time: Optional[datetime] = None
    ) -> ParsedDate:
        """解析日期
        
        Args:
            date_text: 日期文本
            default_timezone: 默认时区
            reference_time: 参考时间，用于相对时间计算
            
        Returns:
            ParsedDate 对象
        """
        if not date_text or not date_text.strip():
            return ParsedDate(
                datetime=None,
                raw_text=date_text,
                confidence=0
            )
        
        date_text = date_text.strip()
        
        # 1. 尝试相对时间解析
        relative_result = self._parse_relative_date(date_text, reference_time)
        if relative_result:
            return relative_result
        
        # 2. 尝试绝对日期格式
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(date_text, fmt)
                return ParsedDate(
                    datetime=dt,
                    raw_text=date_text,
                    confidence=0.9,
                    format_used=fmt
                )
            except ValueError:
                continue
        
        # 3. 尝试 ISO 格式
        try:
            dt = datetime.fromisoformat(date_text)
            return ParsedDate(
                datetime=dt,
                raw_text=date_text,
                confidence=0.9,
                format_used="isoformat"
            )
        except (ValueError, TypeError):
            pass
        
        # 4. 尝试使用 dateutil.parser (如果可用)
        try:
            from dateutil import parser
            dt = parser.parse(date_text, fuzzy=True)
            return ParsedDate(
                datetime=dt,
                raw_text=date_text,
                confidence=0.8,
                format_used="dateutil_parser"
            )
        except ImportError:
            pass
        except Exception:
            pass
        
        return ParsedDate(
            datetime=None,
            raw_text=date_text,
            confidence=0
        )
    
    def _parse_relative_date(
        self,
        date_text: str,
        reference_time: Optional[datetime] = None
    ) -> Optional[ParsedDate]:
        """解析相对日期
        
        Args:
            date_text: 日期文本
            reference_time: 参考时间
            
        Returns:
            ParsedDate 或 None
        """
        if not reference_time:
            reference_time = datetime.now()
        
        # 检查 "just now"
        for pattern in self.INSTANT_PATTERNS:
            if re.search(pattern, date_text, re.IGNORECASE):
                return ParsedDate(
                    datetime=reference_time,
                    raw_text=date_text,
                    confidence=0.9,
                    format_used="instant"
                )
        
        # 检查 "X [time unit] ago"
        for pattern in self.AGO_PATTERNS:
            match = re.search(pattern, date_text, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                
                # 确定时间单位
                unit = None
                if "second" in pattern:
                    unit = "seconds"
                elif "minute" in pattern:
                    unit = "minutes"
                elif "hour" in pattern:
                    unit = "hours"
                elif "day" in pattern:
                    unit = "days"
                elif "week" in pattern:
                    unit = "weeks"
                elif "month" in pattern:
                    unit = "months"
                elif "year" in pattern:
                    unit = "years"
                
                if unit:
                    dt = self._subtract_time(reference_time, value, unit)
                    return ParsedDate(
                        datetime=dt,
                        raw_text=date_text,
                        confidence=0.85,
                        format_used=f"relative_{unit}_ago"
                    )
        
        return None
    
    def _subtract_time(
        self,
        dt: datetime,
        value: int,
        unit: str
    ) -> datetime:
        """从日期中减去时间
        
        Args:
            dt: 基础日期
            value: 值
            unit: 单位
            
        Returns:
            计算后的日期
        """
        if unit == "seconds":
            return dt - timedelta(seconds=value)
        elif unit == "minutes":
            return dt - timedelta(minutes=value)
        elif unit == "hours":
            return dt - timedelta(hours=value)
        elif unit == "days":
            return dt - timedelta(days=value)
        elif unit == "weeks":
            return dt - timedelta(weeks=value)
        elif unit == "months":
            # 简单的月份减法（假设 30 天）
            return dt - timedelta(days=value * 30)
        elif unit == "years":
            # 简单的年份减法（假设 365 天）
            return dt - timedelta(days=value * 365)
        else:
            return dt
    
    def format_date(
        self,
        dt: datetime,
        output_format: str = "%Y-%m-%d %H:%M:%S"
    ) -> Optional[str]:
        """格式化日期
        
        Args:
            dt: datetime 对象
            output_format: 输出格式
            
        Returns:
            格式化的字符串或 None
        """
        if not dt:
            return None
        
        try:
            return dt.strftime(output_format)
        except Exception:
            return None
    
    def to_timestamp(
        self,
        dt: datetime,
        in_ms: bool = False
    ) -> Optional[int]:
        """转换为时间戳
        
        Args:
            dt: datetime 对象
            in_ms: 是否返回毫秒
            
        Returns:
            时间戳或 None
        """
        if not dt:
            return None
        
        try:
            ts = dt.timestamp()
            if in_ms:
                return int(ts * 1000)
            else:
                return int(ts)
        except Exception:
            return None
    
    def from_timestamp(
        self,
        timestamp: int,
        in_ms: bool = False
    ) -> Optional[datetime]:
        """从时间戳创建日期
        
        Args:
            timestamp: 时间戳
            in_ms: 是否是毫秒
            
        Returns:
            datetime 对象或 None
        """
        try:
            if in_ms:
                return datetime.fromtimestamp(timestamp / 1000)
            else:
                return datetime.fromtimestamp(timestamp)
        except Exception:
            return None
    
    def is_date_like(self, text: str) -> bool:
        """判断文本是否可能是日期
        
        Args:
            text: 文本
            
        Returns:
            是否是日期
        """
        if not text or len(text) < 5:
            return False
        
        # 检查是否匹配日期模式
        for pattern in self._date_format_regexes:
            if pattern.search(text):
                return True
        
        # 检查是否有相对时间词
        for pattern in self.AGO_PATTERNS + self.INSTANT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False


# 全局单例
_date_parser: Optional[DateParser] = None

def get_date_parser() -> DateParser:
    """获取日期解析器单例"""
    global _date_parser
    if _date_parser is None:
        _date_parser = DateParser()
    return _date_parser
