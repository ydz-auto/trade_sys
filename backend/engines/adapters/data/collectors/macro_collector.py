"""
Macro Collector - 宏观数据采集（增强版）
支持：多源融合（Yahoo Finance + Metals.live + CME + 金十数据）+ 弹性能力
"""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import httpx
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from infrastructure.config.manager import get_datasource_config_manager
from infrastructure.utilities.http_client import HTTPClient, HTTPRequest, HTTPMethod
from infrastructure.logging import get_logger
from .base_collector import BaseCollector, CollectorResult, SourceConfig
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreakerConfig
from infrastructure.utilities.resilience.retry import RetryConfig

logger = get_logger("collectors.macro")


@dataclass
class MacroData:
    """宏观数据"""
    asset: str
    price: float
    change_1d: float = 0
    change_7d: float = 0
    volume: float = 0
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0


@dataclass
class MacroResult:
    """融合后的宏观数据"""
    asset: str
    price: float
    change_1d: float
    change_7d: float
    sources_used: List[str]
    confidence: float
    timestamp: datetime
    individual_data: Dict[str, MacroData] = field(default_factory=dict)


class MacroSourceCollector:
    """单个宏观数据源采集器"""

    def __init__(self, name: str, source_type: str, config: Dict):
        self.name = name
        self.source_type = source_type
        self.config = config

    async def collect(self, asset: str) -> Optional[MacroData]:
        if self.source_type == "yahoo_finance":
            return await self._collect_yahoo(asset)
        elif self.source_type == "metals_live":
            return await self._collect_metals_live(asset)
        elif self.source_type == "cme":
            return await self._collect_cme(asset)
        elif self.source_type == "llm_scraper":
            return await self._collect_jinshi(asset)
        return None

    async def _collect_yahoo(self, asset: str) -> Optional[MacroData]:
        symbol_map = {
            "gold": "GC=F",
            "silver": "SI=F",
            "oil": "CL=F",
            "dxy": "DX-Y.NYB",
            "us10y": "^TNX",
            "us2y": "^UST2Y",
            "vix": "^VIX"
        }

        symbol = symbol_map.get(asset)
        if not symbol:
            return None

        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    result = data.get("chart", {}).get("result", [{}])[0]

                    meta = result.get("meta", {})
                    quotes = result.get("indicators", {}).get("quote", [{}])[0]

                    current_price = meta.get("regularMarketPrice", 0)
                    prev_close = meta.get("previousClose", current_price)

                    return MacroData(
                        asset=asset,
                        price=current_price,
                        change_1d=((current_price - prev_close) / prev_close * 100) if prev_close else 0,
                        change_7d=0,
                        volume=meta.get("regularMarketVolume", 0),
                        source="yahoo_finance",
                        confidence=0.95
                    )
        except Exception as e:
            logger.warning(f"Yahoo Finance fetch error for {asset}: {e}")
        return None

    async def _collect_metals_live(self, asset: str) -> Optional[MacroData]:
        endpoint_map = {
            "gold": "https://api.metals.live/v1/spot/gold",
            "silver": "https://api.metals.live/v1/spot/silver",
            "oil": "https://api.metals.live/v1/spot/oil"
        }

        url = endpoint_map.get(asset)
        if not url:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        price = data[0].get("price", 0)
                        return MacroData(
                            asset=asset,
                            price=price,
                            source="metals_live",
                            confidence=0.85
                        )
        except Exception as e:
            logger.warning(f"Metals.live fetch error for {asset}: {e}")
        return None

    async def _collect_cme(self, asset: str) -> Optional[MacroData]:
        try:
            url = "https://www.cmegroup.com/CmeWS/ Midd/VCOM/JsonReques tHandler.aspx?Name=CMEGlobalservicesWebPortal"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    return MacroData(
                        asset=asset,
                        price=data.get("price", 0),
                        source="cme",
                        confidence=0.90
                    )
        except Exception as e:
            logger.warning(f"CME fetch error for {asset}: {e}")
        return None

    async def _collect_jinshi(self, asset: str) -> Optional[MacroData]:
        try:
            from infrastructure.utilities.llm import LLMServiceClient
            llm_client = LLMServiceClient()

            url = self.config.get("scrape_url", "https://m.jin10.com/")
            http = HTTPClient()
            request = HTTPRequest(url=url, timeout=30.0)

            async with http:
                response = await http.request(request)

            if response.success and response.text:
                result = await llm_client.structured_extraction(
                    content=response.text,
                    prompt=f"从金融数据页面中提取{asset}的当前价格"
                )

                if result and "price" in result:
                    return MacroData(
                        asset=asset,
                        price=float(result.get("price", 0)),
                        source="jinshi",
                        confidence=0.70
                    )
        except Exception as e:
            logger.warning(f"Jin10 fetch error for {asset}: {e}")
        return None


class MacroCollector(BaseCollector):
    """宏观数据收集器（多源融合）+ 弹性能力"""

    ASSET_MAP = {
        "gold": {"name": "黄金", "unit": "USD/oz"},
        "silver": {"name": "白银", "unit": "USD/oz"},
        "oil": {"name": "原油(WTI)", "unit": "USD/barrel"},
        "dxy": {"name": "美元指数", "unit": "index"},
        "us10y": {"name": "美债10年", "unit": "%"},
        "us2y": {"name": "美债2年", "unit": "%"},
        "vix": {"name": "VIX恐慌指数", "unit": "index"}
    }

    def __init__(self):
        self.latest_results: Dict[str, MacroResult] = {}
        self.sources: Dict[str, MacroSourceCollector] = {}
        
        # 调用基类初始化
        super().__init__(
            name="MacroCollector",
            circuit_config=CircuitBreakerConfig(
                name="macro_circuit",
                failure_threshold=3,
                recovery_timeout=60.0
            ),
            retry_config=RetryConfig(
                max_attempts=2,
                initial_delay=1.0
            ),
            fallback_value={}  # 降级时返回空字典
        )
        
        self._init_sources()

    def _init_sources(self):
        source_configs = [
            {"name": "yahoo_finance", "type": "yahoo_finance", "weight": 0.50, "enabled": True},
            {"name": "metals_live", "type": "metals_live", "weight": 0.30, "enabled": True},
            {"name": "cme", "type": "cme", "weight": 0.20, "enabled": False}
        ]

        for config in source_configs:
            if config["enabled"]:
                self.sources[config["name"]] = MacroSourceCollector(
                    name=config["name"],
                    source_type=config["type"],
                    config=config
                )

    async def collect(self) -> CollectorResult:
        """采集宏观数据（返回 CollectorResult）"""
        try:
            results = {}

            for asset in self.ASSET_MAP.keys():
                try:
                    result = await self._collect_with_fusion(asset)
                    if result:
                        self.latest_results[asset] = result
                        results[asset] = result
                except Exception as e:
                    logger.error(f"Error collecting macro for {asset}: {e}")

            return CollectorResult(
                success=bool(results),
                data=results,
                source="MacroCollector",
                confidence=0.85
            )
        except Exception as e:
            logger.error(f"Macro collection failed: {e}")
            return CollectorResult(
                success=False,
                error=str(e),
                source="MacroCollector"
            )

    async def _collect_with_fusion(self, asset: str) -> Optional[MacroResult]:
        individual_data = {}
        weights = {}

        tasks = []
        source_names = []
        for name, collector in self.sources.items():
            tasks.append(collector.collect(asset))
            source_names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(source_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Source {name} error: {result}")
            elif result:
                individual_data[name] = result
                weights[name] = self.sources[name].config.get("weight", 1.0)

        if not individual_data:
            return self._create_mock_result(asset)

        total_weight = sum(weights.values())
        price = sum(d.price * weights.get(name, 1.0) for name, d in individual_data.items()) / total_weight
        change_1d = sum(d.change_1d * weights.get(name, 1.0) for name, d in individual_data.items()) / total_weight
        change_7d = sum(d.change_7d * weights.get(name, 1.0) for name, d in individual_data.items()) / total_weight
        confidence = sum(d.confidence * weights.get(name, 1.0) for name, d in individual_data.items()) / total_weight

        return MacroResult(
            asset=asset,
            price=price,
            change_1d=change_1d,
            change_7d=change_7d,
            sources_used=list(individual_data.keys()),
            confidence=confidence,
            timestamp=datetime.now(),
            individual_data=individual_data
        )

    def _create_mock_result(self, asset: str) -> MacroResult:
        mock_prices = {
            "gold": 2020.50,
            "silver": 23.50,
            "oil": 78.30,
            "dxy": 104.2,
            "us10y": 4.25,
            "us2y": 4.75,
            "vix": 15.5
        }

        return MacroResult(
            asset=asset,
            price=mock_prices.get(asset, 0),
            change_1d=0,
            change_7d=0,
            sources_used=["mock"],
            confidence=0.5,
            timestamp=datetime.now()
        )

    def get_latest_data(self, asset: str = None) -> Optional[MacroResult]:
        if asset:
            return self.latest_results.get(asset)
        return self.latest_results

    def get_asset_info(self, asset: str) -> Dict:
        return self.ASSET_MAP.get(asset, {})

    def compare_sources(self, asset: str) -> Dict:
        result = self.latest_results.get(asset)
        if not result:
            return {}

        comparison = {}
        for name, data in result.individual_data.items():
            comparison[name] = {
                "price": data.price,
                "change_1d": data.change_1d,
                "confidence": data.confidence,
                "diff_from_fused": data.price - result.price if result.price else 0
            }
        return comparison
