"""
QQ Adapter - 中文加密社区重要来源

监控：
- QQ 群
- QQ 频道
- QQ 私聊

推荐使用：
- go-cqhttp (https://github.com/Mrs4s/go-cqhttp)

QQ 在中文加密社区非常重要！
"""

import os
import re
import random
from datetime import datetime
from typing import Dict, List, Optional, Any

from domain.contracts import (
    StandardEvent,
    EventType,
    Sentiment,
    Source,
    create_news_event
)
from infrastructure.logging import get_logger
from .skill_adapter import SkillAdapter, AdapterConfig

logger = get_logger("qq.adapter")


class QQAdapter(SkillAdapter):
    """QQ 适配器
    
    支持 go-cqhttp 或模拟模式
    """
    
    def __init__(self, config: AdapterConfig = None):
        if not config:
            config = AdapterConfig(
                name="QQAdapter",
                source_type="qq"
            )
        super().__init__(config)
        
        # 环境变量配置
        self.http_api_url = os.getenv("QQ_HTTP_API_URL", "http://127.0.0.1:5700")
        self.use_mock = os.getenv("QQ_USE_MOCK", "true").lower() == "true"
        
        # 监控的群列表
        self.watch_groups = [
            int(g) for g in os.getenv("QQ_WATCH_GROUPS", "").split(",") if g.strip()
        ]
        
        # 币种关键词
        self.crypto_keywords = [
            "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT",
            "AVAX", "LINK", "MATIC", "UNI", "ATOM", "LTC", "BCH",
            "SHIB", "PEPE", "WIF", "BONK", "SUI", "SEI", "APT", "ARB", "OP",
            "比特币", "以太坊", "狗狗币", "币安", "火币", "OKX",
            "做多", "做空", "牛市", "熊市", "暴涨", "暴跌", "拉升", "砸盘"
        ]
        
        logger.info(f"QQAdapter initialized (mock={self.use_mock})")
    
    async def fetch_raw_data(self) -> Dict:
        """获取 QQ 数据"""
        if self.use_mock:
            return self._generate_mock_data()
        
        return await self._fetch_from_go_cqhttp()
    
    async def _fetch_from_go_cqhttp(self) -> Dict:
        """从 go-cqhttp 获取数据"""
        try:
            import aiohttp
            
            messages = []
            
            # 获取群消息
            for group_id in self.watch_groups:
                try:
                    url = f"{self.http_api_url}/get_group_msg_history"
                    params = {"group_id": group_id, "count": 20}
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("retcode") == 0:
                                    for msg in data.get("data", {}).get("messages", []):
                                        messages.append(self._parse_cq_message(msg, group_id))
                except Exception as e:
                    logger.warning(f"Failed to fetch from group {group_id}: {e}")
            
            return {
                "source": "qq",
                "timestamp": int(datetime.now().timestamp()),
                "messages": messages
            }
            
        except ImportError:
            logger.warning("aiohttp not installed, using mock mode")
            return self._generate_mock_data()
        except Exception as e:
            logger.error(f"Failed to fetch from go-cqhttp: {e}")
            return self._generate_mock_data()
    
    def _parse_cq_message(self, msg: Dict, group_id: int = None) -> Dict:
        """解析 go-cqhttp 消息格式"""
        sender = msg.get("sender", {})
        
        return {
            "message_id": msg.get("message_id"),
            "group_id": group_id,
            "group_name": str(group_id) if group_id else "私聊",
            "user_id": sender.get("user_id"),
            "sender": sender.get("nickname", "匿名"),
            "content": msg.get("raw_message", ""),
            "time": msg.get("time", int(datetime.now().timestamp()))
        }
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        for msg in raw_data.get("messages", []):
            event = self._message_to_event(msg)
            if event:
                events.append(event)
        
        return events
    
    def _message_to_event(self, msg: Dict) -> Optional[StandardEvent]:
        """将单条消息转换为 StandardEvent"""
        content = msg.get("content", "")
        
        # 提取币种
        symbols = self._extract_symbols(content)
        
        # 检查是否加密相关
        if not symbols and not self._is_crypto_related(content):
            return None
        
        # 解析情绪
        sentiment = self._parse_sentiment(content)
        
        # 计算重要性
        importance = self._calculate_importance(content, symbols)
        
        # 构建事件
        event = create_news_event(
            source=Source.QQ.value,
            title=f"[{msg.get('group_name', '私聊')}] {msg.get('sender', '匿名')}",
            content=content[:500],
            sentiment=sentiment,
            importance=importance,
            symbols=symbols[:10],
            tags=["qq", msg.get('group_name', 'private')]
        )
        
        event.metadata = {
            "platform": "qq",
            "group_id": msg.get("group_id"),
            "group_name": msg.get("group_name"),
            "user_id": msg.get("user_id"),
            "sender": msg.get("sender"),
            "message_id": msg.get("message_id")
        }
        
        event.timestamp = msg.get("time", event.timestamp)
        
        return event
    
    def _extract_symbols(self, text: str) -> List[str]:
        """从文本中提取币种"""
        symbols = []
        
        crypto_patterns = [
            r'\bBTC\b', r'\bETH\b', r'\bSOL\b', r'\bBNB\b', r'\bXRP\b',
            r'\bADA\b', r'\bDOGE\b', r'\bDOT\b', r'\bAVAX\b', r'\bLINK\b',
            r'\bMATIC\b', r'\bUNI\b', r'\bATOM\b', r'\bLTC\b', r'\bBCH\b',
            r'\bSHIB\b', r'\bPEPE\b', r'\bWIF\b', r'\bBONK\b', r'\bSUI\b',
            r'\bSEI\b', r'\bAPT\b', r'\bARB\b', r'\bOP\b'
        ]
        
        for pattern in crypto_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized = match.upper()
                if normalized not in symbols:
                    symbols.append(normalized)
        
        # 中文关键词
        if "比特币" in text and "BTC" not in symbols:
            symbols.append("BTC")
        if "以太坊" in text and "ETH" not in symbols:
            symbols.append("ETH")
        
        return symbols[:5]
    
    def _is_crypto_related(self, text: str) -> bool:
        """检查是否加密相关"""
        keywords = [
            "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE",
            "比特币", "以太坊", "加密", "区块链", "币安", "火币", "OKX",
            "做多", "做空", "牛市", "熊市", "暴涨", "暴跌", "合约", "杠杆",
            "拉升", "砸盘", "抄底", "逃顶", "建仓", "清仓"
        ]
        
        text_upper = text.upper()
        return any(kw in text_upper or kw in text for kw in keywords)
    
    def _parse_sentiment(self, text: str) -> str:
        """解析情绪"""
        bullish_words = [
            "涨", "多", "买入", "看涨", "做多", "暴涨", "拉升", "牛",
            "利好", "突破", "新高", "抄底", "建仓", "看好", " bull "
        ]
        bearish_words = [
            "跌", "空", "卖出", "看跌", "做空", "暴跌", "砸盘", "熊",
            "利空", "崩盘", "新低", "逃顶", "清仓", "看空", " bear "
        ]
        
        bullish_count = sum(1 for word in bullish_words if word in text)
        bearish_count = sum(1 for word in bearish_words if word in text)
        
        if bullish_count > bearish_count:
            return Sentiment.BULLISH.value
        elif bearish_count > bullish_count:
            return Sentiment.BEARISH.value
        return Sentiment.NEUTRAL.value
    
    def _calculate_importance(self, text: str, symbols: List[str]) -> float:
        """计算重要性"""
        importance = 0.4
        
        # 币种数量
        if len(symbols) >= 3:
            importance += 0.1
        
        # 关键词强度
        strong_words = [
            "突破", "崩盘", "暴涨", "暴跌", "重大", "紧急", "全部", "满仓",
            "跑路", "黑客", "被盗", "监管", "SEC", "政策"
        ]
        for word in strong_words:
            if word in text:
                importance += 0.2
                break
        
        return min(importance, 1.0)
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据"""
        now = int(datetime.now().timestamp())
        
        mock_messages = [
            {
                "message_id": random.randint(100000, 999999),
                "group_id": 123456789,
                "group_name": "币圈讨论群",
                "user_id": 666666,
                "sender": "小韭菜",
                "content": "今天 BTC 突破 70000 了！太猛了！",
                "time": now - 60
            },
            {
                "message_id": random.randint(100000, 999999),
                "group_id": 123456789,
                "group_name": "币圈讨论群",
                "user_id": 888888,
                "sender": "老韭菜",
                "content": "ETH 也要起飞了，准备做多！",
                "time": now - 120
            },
            {
                "message_id": random.randint(100000, 999999),
                "group_id": 987654321,
                "group_name": "DeFi 研究群",
                "user_id": 999999,
                "sender": "链上分析师",
                "content": "SOL 生态最近很活跃，值得关注",
                "time": now - 180
            },
            {
                "message_id": random.randint(100000, 999999),
                "group_id": 123456789,
                "group_name": "币圈讨论群",
                "user_id": 777777,
                "sender": "合约大神",
                "content": "现在点位有点高，注意风险，别追高",
                "time": now - 240
            }
        ]
        
        return {
            "source": "qq",
            "timestamp": now,
            "messages": mock_messages
        }

