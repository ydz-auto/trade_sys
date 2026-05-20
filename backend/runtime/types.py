"""
Runtime Core Types - Runtime 核心类型定义

避免循环导入的共享类型定义
"""
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


class RuntimeType(str, Enum):
    MARKET = "market"
    INGESTION = "ingestion"
    FEATURE = "feature"
    BEHAVIOUR = "behaviour"
    SIGNAL = "signal"
    EXECUTION = "execution"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    PROJECTION = "projection"
    REPLAY = "replay"
    NARRATIVE = "narrative"
    MONITORING = "monitoring"


class RuntimeState(str, Enum):
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RECOVERING = "recovering"
