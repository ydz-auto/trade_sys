"""
ETF Collector - ETF资金流数据采集（增强版）
支持：多源融合（Farside + SoSoValue + CoinGlass + LLM爬虫）
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import httpx
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config import get_datasource_config_manager
from shared.http_client import HTTPClient, HTTPRequest, HTTPMethod
from shared.llm_client import LLMServiceClient
from infrastructure.logging import get_logger

logger = get_logger("collectors.etf")


@dataclass
class ETFFlowData:
    """ETF流量数据"""
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    aum: float
    nav: float = 0
    shares: float = 0
    price: float = 0
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0


@dataclass
class ETFFlowResult:
    """融合后的ETF结果"""
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    aum: float
    sources_used: List[str]
    confidence: float
    timestamp: datetime
    individual_flows: Dict[str, ETFFlowData] = field(default_factory=dict)


class ETFSourceCollector:
    """单个ETF数据源采集器"""

    def __init__(self, name: str, source_type: str, config: Dict):
        self.name = name
        self.source_type = source_type
        self.config = config
        self.enabled = config.get("enabled", True)

    async def collect(self, symbol: str) -> Optional[ETFFlowData]:
        if self.source_type == "farside":
            return await self._collect_farside(symbol)
        elif self.source_type == "sosovalue":
            return await self._collect_sosovalue(symbol)
        elif self.source_type == "coinglass":
            return await self._collect_coinglass(symbol)
        elif self.source_type == "llm_scraper":
            return await self._collect_llm(symbol)
        return None

    async def _collect_farside(self, symbol: str) -> Optional[ETFFlowData]:
        try:
            api_url = "https://api.farside.io/etf/flow"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(api_url, params={"symbol": symbol})

                if response.status_code == 200:
                    data = response.json()
                    return ETFFlowData(
                        symbol=symbol,
                        net_flow=data.get("netFlow", 0),
                        inflow=data.get("inflow", 0),
                        outflow=data.get("outflow", 0),
                        aum=data.get("aum", 0),
                        source="farside",
                        confidence=0.9
                    )
        except Exception as e:
            logger.warning(f"Farside fetch error: {e}")
        return None

    async def _collect_sosovalue(self, symbol: str) -> Optional[ETFFlowData]:
        try:
            api_url = f"https://api.sosovalue.com/etf/bitcoin/flow"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(api_url, params={"symbol": symbol})

                if response.status_code == 200:
                    data = response.json()
                    return ETFFlowData(
                        symbol=symbol,
                        net_flow=data.get("net_flow", 0),
                        inflow=data.get("in_flow", 0),
                        outflow=data.get("out_flow", 0),
                        aum=data.get("aum", 0),
                        source="sosovalue",
                        confidence=0.85
                    )
        except Exception as e:
            logger.warning(f"SoSoValue fetch error: {e}")
        return None

    async def _collect_coinglass(self, symbol: str) -> Optional[ETFFlowData]:
        try:
            api_url = "https://open-api-v4.coinglass.com/api/etf/bitcoin/flow-history"
            api_key = self.config.get("api_key", "")

            headers = {"accept": "application/json", "x-api-key": api_key} if api_key else {}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(api_url, headers=headers, params={"symbol": symbol})

                if response.status_code == 200:
                    data = response.json()
                    if data.get("data"):
                        item = data["data"][0]
                        return ETFFlowData(
                            symbol=symbol,
                            net_flow=item.get("netFlow", 0),
                            inflow=item.get("inFlow", 0),
                            outflow=item.get("outFlow", 0),
                            aum=item.get("aum", 0),
                            source="coinglass",
                            confidence=0.80
                        )
        except Exception as e:
            logger.warning(f"CoinGlass fetch error: {e}")
        return None

    async def _collect_llm(self, symbol: str) -> Optional[ETFFlowData]:
        try:
            llm_client = LLMServiceClient()
            url = self.config.get("scrape_url", "https://farside.co.in/bitcoin-etf-flow")

            from shared.llm_client import HTTPClient, HTTPRequest, HTTPMethod
            http = HTTPClient()
            request = HTTPRequest(url=url, timeout=30.0)

            async with http:
                response = await http.request(request)

            if response.success and response.text:
                result = await llm_client.structured_extraction(
                    content=response.text,
                    prompt=f"从比特币ETF资金流数据中提取今日{symbol}的净流入(inflow)、流出(outflow)、净流量(net_flow)"
                )

                if result and "net_flow" in result:
                    return ETFFlowData(
                        symbol=symbol,
                        net_flow=float(result.get("net_flow", 0)),
                        inflow=float(result.get("inflow", 0)),
                        outflow=float(result.get("outflow", 0)),
                        aum=float(result.get("aum", 0)),
                        source="llm_scraper",
                        confidence=0.75
                    )
        except Exception as e:
            logger.warning(f"LLM scraper fetch error: {e}")
        return None


class ETFCollector:
    """ETF收集器（多源融合）"""

    ETF_SYMBOL_MAP = {
        "BTC": ["IBIT", "FBTC", "ARKB", "BBTC"],
        "ETH": ["ETHA", "FETH", "ETHW"]
    }

    def __init__(self):
        self.latest_results: Dict[str, ETFFlowResult] = {}
        self.sources: Dict[str, ETFSourceCollector] = {}
        self._init_sources()

    def _init_sources(self):
        ds_config = get_datasource_config_manager()
        self.symbols = ds_config.get_etf_symbols()

        source_configs = [
            {
                "name": "farside",
                "type": "farside",
                "enabled": True,
                "weight": 0.45
            },
            {
                "name": "sosovalue",
                "type": "sosovalue",
                "enabled": True,
                "weight": 0.30
            },
            {
                "name": "coinglass",
                "type": "coinglass",
                "enabled": True,
                "weight": 0.25
            }
        ]

        for config in source_configs:
            if config["enabled"]:
                self.sources[config["name"]] = ETFSourceCollector(
                    name=config["name"],
                    source_type=config["type"],
                    config=config
                )

    async def collect(self) -> Dict[str, ETFFlowResult]:
        results = {}

        for symbol in self.symbols:
            try:
                result = await self._collect_with_fusion(symbol)
                if result:
                    self.latest_results[symbol] = result
                    results[symbol] = result
            except Exception as e:
                logger.error(f"Error collecting ETF for {symbol}: {e}")

        return results

    async def _collect_with_fusion(self, symbol: str) -> Optional[ETFFlowResult]:
        individual_flows = {}
        weights = {}

        tasks = []
        source_names = []
        for name, collector in self.sources.items():
            tasks.append(collector.collect(symbol))
            source_names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(source_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Source {name} error: {result}")
            elif result:
                individual_flows[name] = result
                weights[name] = self.sources[name].config.get("weight", 1.0)

        if not individual_flows:
            return self._create_mock_result(symbol)

        total_weight = sum(weights.values())
        net_flow = sum(f.net_flow * weights.get(name, 1.0) for name, f in individual_flows.items()) / total_weight
        inflow = sum(f.inflow * weights.get(name, 1.0) for name, f in individual_flows.items()) / total_weight
        outflow = sum(f.outflow * weights.get(name, 1.0) for name, f in individual_flows.items()) / total_weight
        aum = sum(f.aum * weights.get(name, 1.0) for name, f in individual_flows.items()) / total_weight

        avg_confidence = sum(f.confidence * weights.get(name, 1.0) for name, f in individual_flows.items()) / total_weight

        return ETFFlowResult(
            symbol=symbol,
            net_flow=net_flow,
            inflow=inflow,
            outflow=outflow,
            aum=aum,
            sources_used=list(individual_flows.keys()),
            confidence=avg_confidence,
            timestamp=datetime.now(),
            individual_flows=individual_flows
        )

    def _create_mock_result(self, symbol: str) -> ETFFlowResult:
        mock_data = {
            "BTC": {"net_flow": 150000000, "inflow": 150000000, "outflow": 0, "aum": 52000000000},
            "ETH": {"net_flow": 40000000, "inflow": 45000000, "outflow": 5000000, "aum": 8500000000}
        }
        data = mock_data.get(symbol, {"net_flow": 0, "inflow": 0, "outflow": 0, "aum": 0})

        return ETFFlowResult(
            symbol=symbol,
            net_flow=data["net_flow"],
            inflow=data["inflow"],
            outflow=data["outflow"],
            aum=data["aum"],
            sources_used=["mock"],
            confidence=0.5,
            timestamp=datetime.now()
        )

    def get_latest_flow(self, symbol: str) -> Optional[ETFFlowResult]:
        return self.latest_results.get(symbol)

    def get_flow_by_source(self, symbol: str, source: str) -> Optional[ETFFlowData]:
        result = self.latest_results.get(symbol)
        if result and source in result.individual_flows:
            return result.individual_flows[source]
        return None

    def compare_sources(self, symbol: str) -> Dict:
        result = self.latest_results.get(symbol)
        if not result:
            return {}

        comparison = {}
        for name, flow in result.individual_flows.items():
            comparison[name] = {
                "net_flow": flow.net_flow,
                "inflow": flow.inflow,
                "outflow": flow.outflow,
                "confidence": flow.confidence,
                "diff_from_fused": flow.net_flow - result.net_flow if result.net_flow else 0
            }
        return comparison
