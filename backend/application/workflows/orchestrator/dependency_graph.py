from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from runtime.kernel.runtime_context import RuntimeType
from application.workflows.orchestrator.catalog import RUNTIME_SPECS
from infrastructure.logging import get_logger

logger = get_logger("runtime.dependency")


@dataclass
class DependencyNode:
    runtime_type: RuntimeType
    dependencies: Set[RuntimeType] = field(default_factory=set)
    dependents: Set[RuntimeType] = field(default_factory=set)
    priority: int = 0
    optional: bool = False


class DependencyError(Exception):
    pass


class CircularDependencyError(DependencyError):
    pass


class RuntimeDependencyGraph:
    _instance: Optional['RuntimeDependencyGraph'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True

        self._nodes: Dict[RuntimeType, DependencyNode] = {}

        self._setup_default_dependencies()

        self._startup_cache: Optional[List[RuntimeType]] = None
        self._shutdown_cache: Optional[List[RuntimeType]] = None

        logger.info("RuntimeDependencyGraph initialized")

    def _setup_default_dependencies(self) -> None:
        for spec in RUNTIME_SPECS.values():
            self._nodes[spec.runtime_type] = DependencyNode(
                runtime_type=spec.runtime_type,
                dependencies=set(spec.dependencies),
                priority=spec.priority,
                optional=spec.optional,
            )

        self._rebuild_dependents()

    def _rebuild_dependents(self) -> None:
        for node in self._nodes.values():
            node.dependents.clear()

        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in self._nodes:
                    self._nodes[dep].dependents.add(node.runtime_type)

    def register(
        self,
        runtime_type: RuntimeType,
        dependencies: Optional[Set[RuntimeType]] = None,
        priority: int = 0,
        optional: bool = False,
    ) -> None:
        node = DependencyNode(
            runtime_type=runtime_type,
            dependencies=dependencies or set(),
            priority=priority,
            optional=optional,
        )

        self._nodes[runtime_type] = node
        self._rebuild_dependents()

        self._startup_cache = None
        self._shutdown_cache = None

        logger.info(f"Registered runtime dependency: {runtime_type.value} -> {[d.value for d in node.dependencies]}")

    def add_dependency(self, runtime_type: RuntimeType, depends_on: RuntimeType) -> None:
        if runtime_type not in self._nodes:
            self._nodes[runtime_type] = DependencyNode(runtime_type=runtime_type)

        self._nodes[runtime_type].dependencies.add(depends_on)
        self._rebuild_dependents()

        self._startup_cache = None
        self._shutdown_cache = None

    def remove_dependency(self, runtime_type: RuntimeType, depends_on: RuntimeType) -> None:
        if runtime_type in self._nodes:
            self._nodes[runtime_type].dependencies.discard(depends_on)
            self._rebuild_dependents()

            self._startup_cache = None
            self._shutdown_cache = None

    def detect_cycle(self) -> Optional[List[RuntimeType]]:
        visited: Set[RuntimeType] = set()
        rec_stack: Set[RuntimeType] = set()
        path: List[RuntimeType] = []

        def dfs(node_type: RuntimeType) -> Optional[List[RuntimeType]]:
            visited.add(node_type)
            rec_stack.add(node_type)
            path.append(node_type)

            node = self._nodes.get(node_type)
            if node:
                for dep in node.dependencies:
                    if dep not in visited:
                        result = dfs(dep)
                        if result:
                            return result
                    elif dep in rec_stack:
                        cycle_start = path.index(dep)
                        return path[cycle_start:] + [dep]

            path.pop()
            rec_stack.discard(node_type)
            return None

        for node_type in self._nodes:
            if node_type not in visited:
                cycle = dfs(node_type)
                if cycle:
                    return cycle

        return None

    def get_startup_order(self, runtimes: Optional[Set[RuntimeType]] = None) -> List[RuntimeType]:
        if self._startup_cache and runtimes is None:
            return self._startup_cache

        cycle = self.detect_cycle()
        if cycle:
            raise CircularDependencyError(f"Circular dependency detected: {' -> '.join(r.value for r in cycle)}")

        target_runtimes = runtimes or set(self._nodes.keys())

        in_degree: Dict[RuntimeType, int] = defaultdict(int)
        for rt in target_runtimes:
            if rt in self._nodes:
                for dep in self._nodes[rt].dependencies:
                    if dep in target_runtimes:
                        in_degree[rt] += 1

        queue = sorted(
            [rt for rt in target_runtimes if in_degree[rt] == 0],
            key=lambda r: self._nodes.get(r, DependencyNode(r)).priority,
            reverse=True,
        )

        result = []
        while queue:
            current = queue.pop(0)
            result.append(current)

            for dependent in self._nodes.get(current, DependencyNode(current)).dependents:
                if dependent in target_runtimes:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
                        queue.sort(
                            key=lambda r: self._nodes.get(r, DependencyNode(r)).priority,
                            reverse=True,
                        )

        if runtimes is None:
            self._startup_cache = result

        return result

    def get_shutdown_order(self, runtimes: Optional[Set[RuntimeType]] = None) -> List[RuntimeType]:
        startup_order = self.get_startup_order(runtimes)
        return list(reversed(startup_order))

    def get_dependencies(self, runtime_type: RuntimeType, recursive: bool = False) -> Set[RuntimeType]:
        if runtime_type not in self._nodes:
            return set()

        direct_deps = self._nodes[runtime_type].dependencies.copy()

        if not recursive:
            return direct_deps

        all_deps = direct_deps.copy()
        for dep in direct_deps:
            all_deps.update(self.get_dependencies(dep, recursive=True))

        return all_deps

    def get_dependents(self, runtime_type: RuntimeType, recursive: bool = False) -> Set[RuntimeType]:
        if runtime_type not in self._nodes:
            return set()

        direct_dependents = self._nodes[runtime_type].dependents.copy()

        if not recursive:
            return direct_dependents

        all_dependents = direct_dependents.copy()
        for dep in direct_dependents:
            all_dependents.update(self.get_dependents(dep, recursive=True))

        return all_dependents

    def can_start(
        self,
        runtime_type: RuntimeType,
        started: Set[RuntimeType],
        target_runtimes: Optional[Set[RuntimeType]] = None,
    ) -> Tuple[bool, List[RuntimeType]]:
        if runtime_type not in self._nodes:
            return True, []

        node = self._nodes[runtime_type]
        missing = []

        for dep in node.dependencies:
            if target_runtimes is not None and dep not in target_runtimes:
                continue
            if dep not in started and not self._nodes.get(dep, DependencyNode(dep)).optional:
                missing.append(dep)

        return len(missing) == 0, missing

    def get_node(self, runtime_type: RuntimeType) -> Optional[DependencyNode]:
        return self._nodes.get(runtime_type)

    def get_graph(self) -> Dict[str, Any]:
        return {
            rt.value: {
                "dependencies": [d.value for d in node.dependencies],
                "dependents": [d.value for d in node.dependents],
                "priority": node.priority,
                "optional": node.optional,
            }
            for rt, node in self._nodes.items()
        }

    def visualize(self) -> str:
        lines = ["Runtime Dependency Graph:"]
        startup_order = self.get_startup_order()

        for i, rt in enumerate(startup_order):
            node = self._nodes.get(rt)
            deps = [d.value for d in node.dependencies] if node else []
            indent = "  " * i
            lines.append(f"{indent}{'└─' if i > 0 else ''}{rt.value} (priority={node.priority if node else 0})")
            if deps:
                lines.append(f"{indent}   deps: {deps}")

        return "\n".join(lines)


def get_dependency_graph() -> RuntimeDependencyGraph:
    return RuntimeDependencyGraph()
