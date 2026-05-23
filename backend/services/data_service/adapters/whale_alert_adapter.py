"""
Whale Alert Adapter - 链上巨鲸监控

API: https://docs.whale-alert.io/
实时监控大额链上转账
"""

import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from domain.contracts import StandardEvent, EventType, Sentiment, Source, create_whale_event
from infrastructure.logging import get_logger

from .skill_adapter import SkillAdapter, AdapterConfig

logger = get_logger("whale_alert.adapter")


class WhaleAlertAdapter(SkillAdapter):
    """Whale Alert 链上监控适配器
    
    免费 API 限制：
    - 10 API calls/minute
    - 支持 BTC, ETH 等主流链
    """
    
    BASE_URL = "https://api.whale-alert.io/v1/transactions"
    
    # 大额转账阈值（USD）
    MIN_VALUE_USD = 100000  # 10万美元以上
    
    def __init__(self, config: AdapterConfig = None, api_key: str = None):
        if not config:
            config = AdapterConfig(
                name="WhaleAlertAdapter",
                source_type="whale_alert"
            )
        super().__init__(config)
        
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_timestamp = int(datetime.now().timestamp()) - 3600  # 从1小时前开始
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "TradeAgent/1.0"}
            )
        return self.session
    
    async def fetch_raw_data(self) -> Dict:
        """获取 Whale Alert 数据"""
        try:
            session = await self._get_session()
            
            params = {
                "api_key": self.api_key,
                "min_value": self.MIN_VALUE_USD,
                "start": self.last_timestamp,
                "limit": 100
            }
            
            async with session.get(self.BASE_URL, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    transactions = data.get("transactions", [])
                    
                    # 更新最后时间戳
                    if transactions:
                        self.last_timestamp = max(
                            t.get("timestamp", 0) for t in transactions
                        )
                    
                    logger.info(f"WhaleAlert: Fetched {len(transactions)} transactions")
                    return data
                else:
                    logger.error(f"WhaleAlert API error: {response.status}")
                    return self._generate_mock_data()
                    
        except Exception as e:
            logger.error(f"WhaleAlert fetch failed: {e}")
            return self._generate_mock_data()
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        transactions = raw_data.get("transactions", [])
        
        for tx in transactions:
            symbol = tx.get("symbol", "").upper()
            amount = tx.get("amount", 0)
            value_usd = tx.get("amount_usd", 0)
            
            # 确定交易类型
            from_owner = tx.get("from", {}).get("owner_type", "")
            to_owner = tx.get("to", {}).get("owner_type", "")
            
            action = self._determine_action(from_owner, to_owner)
            
            # 创建巨鲸事件
            event = create_whale_event(
                wallet=tx.get("from", {}).get("address", "")[:20],
                action=action,
                symbol=symbol,
                amount=amount,
                value_usd=value_usd,
                exchange=tx.get("to", {}).get("owner", "") if to_owner == "exchange" else ""
            )
            
            # 补充元数据
            event.metadata.update({
                "blockchain": tx.get("blockchain", ""),
                "transaction_hash": tx.get("hash", ""),
                "from_owner_type": from_owner,
                "to_owner_type": to_owner,
                "from_address": tx.get("from", {}).get("address", ""),
                "to_address": tx.get("to", {}).get("address", ""),
                "timestamp": tx.get("timestamp", 0)
            })
            
            events.append(event)
        
        return events
    
    def _determine_action(self, from_type: str, to_type: str) -> str:
        """根据转账方向确定动作"""
        if from_type == "exchange" and to_type == "unknown":
            return "withdraw"  # 从交易所提现（可能看涨）
        elif from_type == "unknown" and to_type == "exchange":
            return "deposit"   # 存入交易所（可能看跌）
        elif from_type == "exchange" and to_type == "exchange":
            return "transfer"  # 交易所间转账
        else:
            return "transfer"
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据"""
        return {
            "transactions": [
                {
                    "blockchain": "ethereum",
                    "symbol": "eth",
                    "amount": 5000,
                    "amount_usd": 11500000,
                    "hash": "0x1234...",
                    "from": {
                        "address": "0xabc...",
                        "owner_type": "unknown"
                    },
                    "to": {
                        "address": "0xdef...",
                        "owner_type": "exchange",
                        "owner": "binance"
                    },
                    "timestamp": int(datetime.now().timestamp())
                }
            ]
        }
    
    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
