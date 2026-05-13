"""
Factor Registry - 因子注册表

功能：
1. 因子注册与管理
2. 因子版本控制
3. 因子依赖追踪
4. 因子血缘分析

这是 Alpha Production System 的核心基础设施。
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseManager

logger = get_logger("research.factor.registry")


class FactorType(str, Enum):
    """因子类型"""
    RAW = "raw"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    ONCHAIN = "onchain"
    MACRO = "macro"
    COMPOSITE = "composite"
    ML = "ml"


class FactorStatus(str, Enum):
    """因子状态"""
    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


@dataclass
class FactorMetadata:
    """因子元数据"""
    factor_id: str
    name: str
    version: str
    
    factor_type: FactorType
    status: FactorStatus
    
    description: str
    
    author: str
    created_at: datetime
    updated_at: datetime
    
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    metrics: Dict[str, float] = field(default_factory=dict)
    
    parent_factor_id: Optional[str] = None
    
    source_code_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "version": self.version,
            "factor_type": self.factor_type.value,
            "status": self.status.value,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "parent_factor_id": self.parent_factor_id,
            "source_code_hash": self.source_code_hash,
        }
    
    def compute_hash(self) -> str:
        data = {
            "name": self.name,
            "version": self.version,
            "factor_type": self.factor_type.value,
            "parameters": self.parameters,
            "dependencies": sorted(self.dependencies),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class FactorDependency:
    """因子依赖"""
    factor_id: str
    version: str
    dependency_type: str
    
    required: bool = True
    optional_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorEvaluation:
    """因子评估结果"""
    evaluation_id: str
    factor_id: str
    version: str
    timestamp: datetime
    ic: float
    rank_ic: float
    ir: float
    sharpe: float
    max_drawdown: float
    turnover: float
    decay: float
    stability: float
    sample_count: int
    period_start: datetime
    period_end: datetime
    regime_sensitivity: Dict[str, float] = field(default_factory=dict)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "factor_id": self.factor_id,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "ic": self.ic,
            "rank_ic": self.rank_ic,
            "ir": self.ir,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "turnover": self.turnover,
            "decay": self.decay,
            "stability": self.stability,
            "regime_sensitivity": self.regime_sensitivity,
            "sample_count": self.sample_count,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metadata": self.metadata,
        }


class FactorRegistry:
    """因子注册表
    
    管理因子的注册、版本、依赖和评估
    """
    
    def __init__(self):
        self.clickhouse: Optional[ClickHouseManager] = None
        
        self._factors: Dict[str, Dict[str, FactorMetadata]] = {}
        self._dependencies: Dict[str, List[FactorDependency]] = {}
        self._evaluations: Dict[str, List[FactorEvaluation]] = {}
        
        self._factor_implementations: Dict[str, Callable] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化"""
        if self._initialized:
            return
        
        self.clickhouse = ClickHouseManager()
        await self._ensure_tables()
        
        self._initialized = True
        logger.info("FactorRegistry initialized")
    
    async def _ensure_tables(self) -> None:
        """确保表存在"""
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS factor_registry (
                factor_id String,
                name String,
                version String,
                factor_type String,
                status String,
                description String,
                author String,
                created_at DateTime,
                updated_at DateTime,
                tags Array(String),
                dependencies Array(String),
                parameters String,
                metrics String,
                parent_factor_id Nullable(String),
                source_code_hash Nullable(String)
            ) ENGINE = MergeTree()
            ORDER BY (name, version)
            TTL toDateTime(updated_at) + INTERVAL 365 DAY
        """
        
        evaluation_table_sql = """
            CREATE TABLE IF NOT EXISTS factor_evaluations (
                evaluation_id String,
                factor_id String,
                version String,
                timestamp DateTime,
                ic Float64,
                rank_ic Float64,
                ir Float64,
                sharpe Float64,
                max_drawdown Float64,
                turnover Float64,
                decay Float64,
                stability Float64,
                regime_sensitivity String,
                sample_count UInt32,
                period_start DateTime,
                period_end DateTime,
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (factor_id, version, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 365 DAY
        """
        
        try:
            await self.clickhouse.execute(create_table_sql)
            await self.clickhouse.execute(evaluation_table_sql)
        except Exception as e:
            logger.warning(f"Table creation warning: {e}")
    
    async def register_factor(
        self,
        name: str,
        factor_type: FactorType,
        description: str,
        author: str,
        parameters: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        parent_factor_id: Optional[str] = None,
    ) -> FactorMetadata:
        """注册新因子"""
        if not self._initialized:
            await self.initialize()
        
        if name not in self._factors:
            self._factors[name] = {}
        
        version = self._get_next_version(name)
        
        factor_id = f"{name}_{version}"
        
        metadata = FactorMetadata(
            factor_id=factor_id,
            name=name,
            version=version,
            factor_type=factor_type,
            status=FactorStatus.EXPERIMENTAL,
            description=description,
            author=author,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tags=tags or [],
            dependencies=dependencies or [],
            parameters=parameters or {},
            parent_factor_id=parent_factor_id,
        )
        
        metadata.source_code_hash = metadata.compute_hash()
        
        self._factors[name][version] = metadata
        
        await self._persist_factor(metadata)
        
        logger.info(f"Factor registered: {factor_id}")
        return metadata
    
    async def update_factor(
        self,
        factor_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        status: Optional[FactorStatus] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[FactorMetadata]:
        """更新因子"""
        parts = factor_id.rsplit("_", 1)
        if len(parts) != 2:
            return None
        
        name, version = parts
        
        if name not in self._factors or version not in self._factors[name]:
            return None
        
        metadata = self._factors[name][version]
        
        if parameters:
            metadata.parameters.update(parameters)
        
        if status:
            metadata.status = status
        
        if metrics:
            metadata.metrics.update(metrics)
        
        metadata.updated_at = datetime.utcnow()
        metadata.source_code_hash = metadata.compute_hash()
        
        await self._persist_factor(metadata)
        
        logger.info(f"Factor updated: {factor_id}")
        return metadata
    
    async def register_evaluation(
        self,
        factor_id: str,
        ic: float,
        rank_ic: float,
        ir: float,
        sharpe: float,
        max_drawdown: float,
        turnover: float,
        decay: float,
        stability: float,
        regime_sensitivity: Optional[Dict[str, float]] = None,
        sample_count: int = 0,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FactorEvaluation:
        """注册因子评估"""
        if not self._initialized:
            await self.initialize()
        
        parts = factor_id.rsplit("_", 1)
        name, version = parts[0], parts[1] if len(parts) > 1 else "v1"
        
        evaluation_id = f"eval_{uuid.uuid4().hex[:12]}"
        
        evaluation = FactorEvaluation(
            evaluation_id=evaluation_id,
            factor_id=factor_id,
            version=version,
            timestamp=datetime.utcnow(),
            ic=ic,
            rank_ic=rank_ic,
            ir=ir,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            turnover=turnover,
            decay=decay,
            stability=stability,
            regime_sensitivity=regime_sensitivity or {},
            sample_count=sample_count,
            period_start=period_start or datetime.utcnow(),
            period_end=period_end or datetime.utcnow(),
            metadata=metadata or {},
        )
        
        if factor_id not in self._evaluations:
            self._evaluations[factor_id] = []
        
        self._evaluations[factor_id].append(evaluation)
        
        await self._persist_evaluation(evaluation)
        
        logger.info(f"Factor evaluation registered: {evaluation_id} (IC={ic:.4f}, IR={ir:.4f})")
        return evaluation
    
    def get_factor(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[FactorMetadata]:
        """获取因子"""
        if name not in self._factors:
            return None
        
        if version:
            return self._factors[name].get(version)
        
        versions = sorted(
            self._factors[name].keys(),
            key=lambda v: self._parse_version(v),
            reverse=True,
        )
        return self._factors[name].get(versions[0]) if versions else None
    
    def get_all_factors(
        self,
        status: Optional[FactorStatus] = None,
        factor_type: Optional[FactorType] = None,
        tags: Optional[List[str]] = None,
    ) -> List[FactorMetadata]:
        """获取所有因子"""
        results = []
        
        for name_versions in self._factors.values():
            for metadata in name_versions.values():
                if status and metadata.status != status:
                    continue
                if factor_type and metadata.factor_type != factor_type:
                    continue
                if tags and not any(t in metadata.tags for t in tags):
                    continue
                results.append(metadata)
        
        return sorted(results, key=lambda m: m.updated_at, reverse=True)
    
    def get_latest_version(self, name: str) -> Optional[str]:
        """获取最新版本"""
        if name not in self._factors:
            return None
        
        versions = sorted(
            self._factors[name].keys(),
            key=lambda v: self._parse_version(v),
            reverse=True,
        )
        return versions[0] if versions else None
    
    def _get_next_version(self, name: str) -> str:
        """获取下一个版本号"""
        if name not in self._factors or not self._factors[name]:
            return "v1"
        
        latest = self.get_latest_version(name)
        if not latest:
            return "v1"
        
        parts = latest.lstrip("v")
        try:
            num = int(parts) + 1
            return f"v{num}"
        except ValueError:
            return "v1"
    
    def _parse_version(self, version: str) -> int:
        """解析版本号"""
        parts = version.lstrip("v")
        try:
            return int(parts)
        except ValueError:
            return 0
    
    def get_evaluations(
        self,
        factor_id: str,
        limit: int = 10,
    ) -> List[FactorEvaluation]:
        """获取因子评估历史"""
        if factor_id not in self._evaluations:
            return []
        
        evaluations = sorted(
            self._evaluations[factor_id],
            key=lambda e: e.timestamp,
            reverse=True,
        )
        return evaluations[:limit]
    
    def get_latest_evaluation(
        self,
        factor_id: str,
    ) -> Optional[FactorEvaluation]:
        """获取最新评估"""
        evaluations = self.get_evaluations(factor_id, limit=1)
        return evaluations[0] if evaluations else None
    
    def get_factor_lineage(
        self,
        factor_id: str,
    ) -> List[FactorMetadata]:
        """获取因子血缘"""
        lineage = []
        visited = set()
        
        current_id = factor_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            
            parts = current_id.rsplit("_", 1)
            if len(parts) != 2:
                break
            
            name, version = parts
            factor = self.get_factor(name, version)
            
            if factor:
                lineage.append(factor)
                current_id = factor.parent_factor_id
            else:
                break
        
        return lineage
    
    def get_factor_dependencies(
        self,
        factor_id: str,
    ) -> List[FactorDependency]:
        """获取因子依赖"""
        return self._dependencies.get(factor_id, [])
    
    def register_dependency(
        self,
        factor_id: str,
        dependency: FactorDependency,
    ) -> None:
        """注册因子依赖"""
        if factor_id not in self._dependencies:
            self._dependencies[factor_id] = []
        self._dependencies[factor_id].append(dependency)
    
    def search_factors(
        self,
        query: str,
        limit: int = 20,
    ) -> List[FactorMetadata]:
        """搜索因子"""
        query_lower = query.lower()
        results = []
        
        for name_versions in self._factors.values():
            for metadata in name_versions.values():
                if (query_lower in metadata.name.lower() or
                    query_lower in metadata.description.lower() or
                    any(query_lower in tag.lower() for tag in metadata.tags)):
                    results.append(metadata)
        
        return sorted(results, key=lambda m: m.updated_at, reverse=True)[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_factors = sum(len(v) for v in self._factors.values())
        by_type = {}
        by_status = {}
        total_evaluations = sum(len(e) for e in self._evaluations.values())
        
        for name_versions in self._factors.values():
            for m in name_versions.values():
                by_type[m.factor_type.value] = by_type.get(m.factor_type.value, 0) + 1
                by_status[m.status.value] = by_status.get(m.status.value, 0) + 1
        
        return {
            "total_factors": total_factors,
            "by_type": by_type,
            "by_status": by_status,
            "total_evaluations": total_evaluations,
            "unique_factor_names": len(self._factors),
        }
    
    async def _persist_factor(self, metadata: FactorMetadata) -> None:
        """持久化因子"""
        try:
            data = metadata.to_dict()
            data["parameters"] = json.dumps(data["parameters"])
            data["metrics"] = json.dumps(data["metrics"])
            
            await self.clickhouse.insert("factor_registry", [data])
        except Exception as e:
            logger.warning(f"Factor persistence warning: {e}")
    
    async def _persist_evaluation(self, evaluation: FactorEvaluation) -> None:
        """持久化评估"""
        try:
            data = evaluation.to_dict()
            data["regime_sensitivity"] = json.dumps(data["regime_sensitivity"])
            data["metadata"] = json.dumps(data["metadata"])
            
            await self.clickhouse.insert("factor_evaluations", [data])
        except Exception as e:
            logger.warning(f"Evaluation persistence warning: {e}")
    
    def register_implementation(
        self,
        name: str,
        implementation: Callable,
    ) -> None:
        """注册因子实现"""
        self._factor_implementations[name] = implementation
        logger.info(f"Factor implementation registered: {name}")
    
    def get_implementation(self, name: str) -> Optional[Callable]:
        """获取因子实现"""
        return self._factor_implementations.get(name)


_factor_registry: Optional[FactorRegistry] = None


async def get_factor_registry() -> FactorRegistry:
    """获取因子注册表实例"""
    global _factor_registry
    if _factor_registry is None:
        _factor_registry = FactorRegistry()
        await _factor_registry.initialize()
    return _factor_registry
