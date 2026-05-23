"""
Domain Logging Facade

domain 层日志门面。domain 代码只依赖此模块，不直接依赖 infrastructure.logging。

用法：
    from domain.logging import get_logger
    logger = get_logger("domain.feature")
"""

from typing import Optional


def get_logger(name: str):
    from infrastructure.logging import get_logger as _infrastructure_get_logger
    return _infrastructure_get_logger(name)
