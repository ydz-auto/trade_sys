"""
Alpha Reporting Module

报告模块

模块：
- leaderboard.py    Leaderboard 类
- per_symbol.py     generate_from_pipeline_result / load_from_csv
- paper_config.py   AlphaTradingConfig / generate_paper_trading_configs
- status.py         状态报告函数
- readiness.py      Production Readiness 分级
"""

from research.alpha.reporting.leaderboard import Leaderboard

from research.alpha.reporting.per_symbol import (
    generate_from_pipeline_result,
    load_from_csv as load_per_symbol_from_csv,
)

from research.alpha.reporting.paper_config import (
    AlphaTradingConfig,
    generate_paper_trading_configs,
)

from research.alpha.reporting.readiness import (
    MINIMUM_TRADES,
    READINESS_ICONS,
    classify_production_readiness,
    generate_paper_trading_config,
)

__all__ = [
    "Leaderboard",
    "generate_from_pipeline_result",
    "load_per_symbol_from_csv",
    "AlphaTradingConfig",
    "generate_paper_trading_configs",
    "MINIMUM_TRADES",
    "READINESS_ICONS",
    "classify_production_readiness",
    "generate_paper_trading_config",
]
