"""
Tests for ETFCollector
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collectors import ETFCollector, ETFFlowData, ETFFlowResult


class TestETFFlowData:
    def test_create_etf_flow_data(self, mock_etf_flow):
        from datetime import datetime
        data = ETFFlowData(
            symbol="BTC",
            net_flow=mock_etf_flow["netFlow"],
            inflow=mock_etf_flow["inflow"],
            outflow=mock_etf_flow["outflow"],
            aum=mock_etf_flow["aum"],
            source="farside",
            confidence=0.9
        )

        assert data.symbol == "BTC"
        assert data.net_flow == 150000000
        assert data.inflow == 150000000
        assert data.outflow == 0
        assert data.source == "farside"


class TestETFFlowResult:
    def test_create_fusion_result(self):
        from datetime import datetime
        result = ETFFlowResult(
            symbol="BTC",
            net_flow=150000000,
            inflow=150000000,
            outflow=0,
            aum=52000000000,
            sources_used=["farside", "sosovalue"],
            confidence=0.88,
            timestamp=datetime.now()
        )

        assert result.symbol == "BTC"
        assert result.net_flow == 150000000
        assert len(result.sources_used) == 2
        assert result.confidence == 0.88


class TestETFCollector:
    def test_init(self):
        with patch("collectors.etf_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_etf_symbols.return_value = ["BTC", "ETH"]
            collector = ETFCollector()

            assert "BTC" in collector.symbols or "ETH" in collector.symbols

    def test_create_mock_result(self):
        with patch("collectors.etf_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_etf_symbols.return_value = ["BTC"]
            collector = ETFCollector()

            result = collector._create_mock_result("BTC")

            assert result.symbol == "BTC"
            assert result.sources_used == ["mock"]
            assert result.confidence == 0.5

    def test_compare_sources(self):
        from datetime import datetime
        with patch("collectors.etf_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_etf_symbols.return_value = ["BTC"]
            collector = ETFCollector()

            result = ETFFlowResult(
                symbol="BTC",
                net_flow=150000000,
                inflow=150000000,
                outflow=0,
                aum=52000000000,
                sources_used=["farside", "sosovalue"],
                confidence=0.88,
                timestamp=datetime.now(),
                individual_flows={
                    "farside": ETFFlowData(
                        symbol="BTC", net_flow=155000000,
                        inflow=155000000, outflow=0, aum=52000000000,
                        source="farside", confidence=0.9
                    ),
                    "sosovalue": ETFFlowData(
                        symbol="BTC", net_flow=145000000,
                        inflow=145000000, outflow=0, aum=52000000000,
                        source="sosovalue", confidence=0.85
                    )
                }
            )
            collector.latest_results["BTC"] = result

            comparison = collector.compare_sources("BTC")

            assert "farside" in comparison
            assert "sosovalue" in comparison
            assert comparison["farside"]["net_flow"] == 155000000
