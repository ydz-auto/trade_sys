"""
Feature Lineage System - 特征血缘系统

核心问题：
当特征 A 依赖特征 B，特征 B 依赖特征 C 时，
如果特征 C 的计算逻辑改变，特征 A 和 B 都会受影响。
但没有记录这种依赖关系，导致难以追踪和审计。

解决方案：
1. 记录每个特征的依赖关系
2. 支持血缘追溯
3. 当依赖特征变化时，自动标记受影响的特征
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import hashlib

from infrastructure.logging import get_logger

logger = get_logger("domain.feature.infrastructure.feature_lineage")


class FeatureType(Enum):
    """特征类型"""
    RAW = "raw"                 # 原始数据
    DERIVED = "derived"         # 衍生特征
    AGGREGATED = "aggregated"   # 聚合特征
    CROSS_SYMBOL = "cross_symbol"  # 跨品种特征
    LABEL = "label"             # 标签


@dataclass
class FeatureNode:
    """特征节点"""
    feature_name: str
    feature_type: FeatureType
    
    description: str = ""
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    
    computation_hash: str = ""
    config_hash: str = ""
    
    source_file: str = ""
    source_function: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_type": self.feature_type.value,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "computation_hash": self.computation_hash,
            "config_hash": self.config_hash,
            "source_file": self.source_file,
            "source_function": self.source_function,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureNode':
        return cls(
            feature_name=data["feature_name"],
            feature_type=FeatureType(data["feature_type"]),
            description=data.get("description", ""),
            version=data.get("version", 1),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            modified_at=data.get("modified_at", datetime.utcnow().isoformat()),
            dependencies=set(data.get("dependencies", [])),
            dependents=set(data.get("dependents", [])),
            computation_hash=data.get("computation_hash", ""),
            config_hash=data.get("config_hash", ""),
            source_file=data.get("source_file", ""),
            source_function=data.get("source_function", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class LineageEdge:
    """血缘边"""
    source: str
    target: str
    relation: str  # "depends_on", "derived_from", "aggregated_from"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "created_at": self.created_at,
        }


class FeatureLineageSystem:
    """
    特征血缘系统
    
    核心功能：
    1. 记录特征依赖关系
    2. 支持血缘追溯
    3. 影响分析
    """
    
    def __init__(self):
        self._nodes: Dict[str, FeatureNode] = {}
        self._edges: List[LineageEdge] = []
        
        self._computation_registry: Dict[str, str] = {}
        self._change_log: List[Dict[str, Any]] = []
    
    def register_feature(
        self,
        feature_name: str,
        feature_type: FeatureType = FeatureType.DERIVED,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        source_file: str = "",
        source_function: str = "",
        computation_hash: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        注册特征
        
        Args:
            feature_name: 特征名称
            feature_type: 特征类型
            description: 描述
            dependencies: 依赖特征列表
            source_file: 源文件
            source_function: 源函数
            computation_hash: 计算逻辑哈希
            config: 配置
        """
        dependencies = dependencies or []
        config = config or {}
        
        config_hash = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()[:16] if config else ""
        
        is_new = feature_name not in self._nodes
        is_modified = False
        
        if not is_new:
            existing = self._nodes[feature_name]
            is_modified = (
                existing.computation_hash != computation_hash or
                existing.config_hash != config_hash or
                set(dependencies) != existing.dependencies
            )
        
        node = FeatureNode(
            feature_name=feature_name,
            feature_type=feature_type,
            description=description,
            version=1 if is_new else self._nodes[feature_name].version + (1 if is_modified else 0),
            dependencies=set(dependencies),
            source_file=source_file,
            source_function=source_function,
            computation_hash=computation_hash,
            config_hash=config_hash,
        )
        
        self._nodes[feature_name] = node
        
        for dep in dependencies:
            self._add_dependency(feature_name, dep)
        
        if is_modified:
            self._log_change(
                feature_name=feature_name,
                change_type="modified",
                details={
                    "old_version": self._nodes[feature_name].version - 1,
                    "new_version": node.version,
                }
            )
        
        logger.debug(f"Registered feature: {feature_name}, type={feature_type.value}")
    
    def _add_dependency(self, feature_name: str, dependency: str):
        """添加依赖关系"""
        if dependency not in self._nodes:
            self._nodes[dependency] = FeatureNode(
                feature_name=dependency,
                feature_type=FeatureType.RAW,
            )
        
        self._nodes[dependency].dependents.add(feature_name)
        
        self._edges.append(LineageEdge(
            source=feature_name,
            target=dependency,
            relation="depends_on",
        ))
    
    def get_feature(self, feature_name: str) -> Optional[FeatureNode]:
        """获取特征节点"""
        return self._nodes.get(feature_name)
    
    def get_dependencies(
        self,
        feature_name: str,
        recursive: bool = True,
    ) -> Set[str]:
        """
        获取依赖特征
        
        Args:
            feature_name: 特征名称
            recursive: 是否递归获取
        
        Returns:
            Set[str]: 依赖特征集合
        """
        node = self._nodes.get(feature_name)
        if node is None:
            return set()
        
        if not recursive:
            return node.dependencies.copy()
        
        all_deps = set()
        to_visit = list(node.dependencies)
        
        while to_visit:
            dep = to_visit.pop()
            if dep in all_deps:
                continue
            
            all_deps.add(dep)
            
            dep_node = self._nodes.get(dep)
            if dep_node:
                to_visit.extend(dep_node.dependencies - all_deps)
        
        return all_deps
    
    def get_dependents(
        self,
        feature_name: str,
        recursive: bool = True,
    ) -> Set[str]:
        """
        获取依赖此特征的特征
        
        Args:
            feature_name: 特征名称
            recursive: 是否递归获取
        
        Returns:
            Set[str]: 依赖此特征的特征集合
        """
        node = self._nodes.get(feature_name)
        if node is None:
            return set()
        
        if not recursive:
            return node.dependents.copy()
        
        all_dependents = set()
        to_visit = list(node.dependents)
        
        while to_visit:
            dep = to_visit.pop()
            if dep in all_dependents:
                continue
            
            all_dependents.add(dep)
            
            dep_node = self._nodes.get(dep)
            if dep_node:
                to_visit.extend(dep_node.dependents - all_dependents)
        
        return all_dependents
    
    def analyze_impact(
        self,
        changed_features: List[str],
    ) -> Dict[str, Any]:
        """
        分析影响范围
        
        Args:
            changed_features: 变更的特征列表
        
        Returns:
            Dict[str, Any]: 影响分析结果
        """
        all_affected: Set[str] = set()
        
        for feature in changed_features:
            dependents = self.get_dependents(feature, recursive=True)
            all_affected.update(dependents)
        
        return {
            "changed_features": changed_features,
            "affected_features": list(all_affected),
            "affected_count": len(all_affected),
            "impact_depth": self._compute_impact_depth(changed_features),
        }
    
    def _compute_impact_depth(self, changed_features: List[str]) -> Dict[str, int]:
        """计算影响深度"""
        depths: Dict[str, int] = {}
        
        for feature in changed_features:
            depths[feature] = 0
            dependents = self.get_dependents(feature, recursive=True)
            
            for dep in dependents:
                dep_depth = self._get_dependency_depth(dep)
                depths[dep] = dep_depth
        
        return depths
    
    def _get_dependency_depth(self, feature_name: str) -> int:
        """获取依赖深度"""
        node = self._nodes.get(feature_name)
        if node is None or not node.dependencies:
            return 0
        
        max_depth = 0
        for dep in node.dependencies:
            max_depth = max(max_depth, self._get_dependency_depth(dep) + 1)
        
        return max_depth
    
    def get_lineage_path(
        self,
        from_feature: str,
        to_feature: str,
    ) -> List[List[str]]:
        """
        获取血缘路径
        
        Args:
            from_feature: 起始特征
            to_feature: 目标特征
        
        Returns:
            List[List[str]]: 所有路径列表
        """
        paths = []
        
        def dfs(current: str, target: str, path: List[str], visited: Set[str]):
            if current == target:
                paths.append(path.copy())
                return
            
            if current in visited:
                return
            
            visited.add(current)
            node = self._nodes.get(current)
            
            if node:
                for dep in node.dependencies:
                    path.append(dep)
                    dfs(dep, target, path, visited)
                    path.pop()
            
            visited.remove(current)
        
        dfs(from_feature, to_feature, [from_feature], set())
        return paths
    
    def validate_lineage(self) -> List[Dict[str, Any]]:
        """验证血缘关系"""
        issues = []
        
        for name, node in self._nodes.items():
            for dep in node.dependencies:
                if dep not in self._nodes:
                    issues.append({
                        "type": "missing_dependency",
                        "feature": name,
                        "dependency": dep,
                        "message": f"Feature {name} depends on non-existent feature {dep}",
                    })
        
        visited = set()
        rec_stack = set()
        
        def has_cycle(feature: str) -> bool:
            visited.add(feature)
            rec_stack.add(feature)
            
            node = self._nodes.get(feature)
            if node:
                for dep in node.dependencies:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        issues.append({
                            "type": "circular_dependency",
                            "feature": feature,
                            "dependency": dep,
                            "message": f"Circular dependency detected: {feature} -> {dep}",
                        })
                        return True
            
            rec_stack.remove(feature)
            return False
        
        for feature in self._nodes:
            if feature not in visited:
                has_cycle(feature)
        
        return issues
    
    def _log_change(
        self,
        feature_name: str,
        change_type: str,
        details: Dict[str, Any],
    ):
        """记录变更"""
        self._change_log.append({
            "feature_name": feature_name,
            "change_type": change_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def export_lineage(self) -> Dict[str, Any]:
        """导出血缘关系"""
        return {
            "nodes": {name: node.to_dict() for name, node in self._nodes.items()},
            "edges": [edge.to_dict() for edge in self._edges],
            "exported_at": datetime.utcnow().isoformat(),
        }
    
    def import_lineage(self, data: Dict[str, Any]):
        """导入血缘关系"""
        for name, node_data in data.get("nodes", {}).items():
            self._nodes[name] = FeatureNode.from_dict(node_data)
        
        for edge_data in data.get("edges", []):
            self._edges.append(LineageEdge(
                source=edge_data["source"],
                target=edge_data["target"],
                relation=edge_data["relation"],
                created_at=edge_data.get("created_at", datetime.utcnow().isoformat()),
            ))
        
        logger.info(f"Imported lineage: {len(self._nodes)} nodes, {len(self._edges)} edges")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        for node in self._nodes.values():
            t = node.feature_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        
        return {
            "total_features": len(self._nodes),
            "total_edges": len(self._edges),
            "feature_types": type_counts,
            "change_log_count": len(self._change_log),
        }


_lineage_instances: Dict[str, FeatureLineageSystem] = {}


def get_feature_lineage(instance_id: str = "default") -> FeatureLineageSystem:
    """获取特征血缘系统实例"""
    if instance_id not in _lineage_instances:
        _lineage_instances[instance_id] = FeatureLineageSystem()
    return _lineage_instances[instance_id]


def register_feature_lineage(
    feature_name: str,
    feature_type: str = "derived",
    dependencies: Optional[List[str]] = None,
    **kwargs,
):
    """注册特征血缘的便捷函数"""
    lineage = get_feature_lineage()
    lineage.register_feature(
        feature_name=feature_name,
        feature_type=FeatureType(feature_type),
        dependencies=dependencies,
        **kwargs,
    )
