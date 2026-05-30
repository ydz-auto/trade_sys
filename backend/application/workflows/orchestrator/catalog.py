from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import os

from domain.trading_mode import TradingMode
from runtime.kernel.runtime_context import RuntimeType


RuntimeFactory = Callable[[], object]


@dataclass(frozen=True)
class RuntimeSpec:
    runtime_type: RuntimeType
    runtime_id: str
    factory: RuntimeFactory
    dependencies: Tuple[RuntimeType, ...] = ()
    priority: int = 0
    optional: bool = False
    modes: Tuple[TradingMode, ...] = ()


def _feature_runtime() -> object:
    from engines.context.market_context_builder import MarketContextBuilder

    return MarketContextBuilder()


def _signal_runtime() -> object:
    from runtime.components.strategy_runner import StrategyRunner

    return StrategyRunner()


def _ingestion_runtime() -> object:
    from runtime.components.ingestion_runner import IngestionRunner

    return IngestionRunner()


def _execution_runtime() -> object:
    from runtime.components.execution_runner import ExecutionRunner

    return ExecutionRunner()


def _portfolio_runtime() -> object:
    raise NotImplementedError("portfolio_runtime has been removed")


def _projection_runtime() -> object:
    raise NotImplementedError("projection_runtime has been removed")


def _regime_runtime() -> object:
    raise NotImplementedError("regime_runtime has been removed")


def _correlation_runtime() -> object:
    raise NotImplementedError("correlation_runtime has been removed")


def _narrative_runtime() -> object:
    from engines.narrative.narrative_engine import NarrativeEngine

    return NarrativeEngine()


def _replay_runtime() -> object:
    from runtime.replay_runtime.runtime import TimeCausalReplayRuntime

    return TimeCausalReplayRuntime()


RUNTIME_SPECS: Dict[RuntimeType, RuntimeSpec] = {
    RuntimeType.INGESTION: RuntimeSpec(
        runtime_type=RuntimeType.INGESTION,
        runtime_id="ingestion_runtime",
        factory=_ingestion_runtime,
        priority=90,
        modes=(TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.FEATURE: RuntimeSpec(
        runtime_type=RuntimeType.FEATURE,
        runtime_id="feature_runtime",
        factory=_feature_runtime,
        dependencies=(RuntimeType.INGESTION,),
        priority=80,
        modes=(TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.SIGNAL: RuntimeSpec(
        runtime_type=RuntimeType.SIGNAL,
        runtime_id="signal_runtime",
        factory=_signal_runtime,
        dependencies=(RuntimeType.FEATURE,),
        priority=60,
        modes=(TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.EXECUTION: RuntimeSpec(
        runtime_type=RuntimeType.EXECUTION,
        runtime_id="execution_runtime",
        factory=_execution_runtime,
        dependencies=(RuntimeType.SIGNAL,),
        priority=50,
        modes=(TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.PORTFOLIO: RuntimeSpec(
        runtime_type=RuntimeType.PORTFOLIO,
        runtime_id="portfolio_runtime",
        factory=_portfolio_runtime,
        dependencies=(RuntimeType.EXECUTION,),
        priority=40,
        modes=(TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.PROJECTION: RuntimeSpec(
        runtime_type=RuntimeType.PROJECTION,
        runtime_id="projection_runtime",
        factory=_projection_runtime,
        dependencies=(RuntimeType.SIGNAL, RuntimeType.EXECUTION, RuntimeType.PORTFOLIO),
        priority=20,
        modes=(TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.REGIME: RuntimeSpec(
        runtime_type=RuntimeType.REGIME,
        runtime_id="regime_runtime",
        factory=_regime_runtime,
        dependencies=(RuntimeType.FEATURE,),
        priority=45,
        optional=True,
        modes=(TradingMode.PAPER, TradingMode.LIVE),
    ),
    RuntimeType.CORRELATION: RuntimeSpec(
        runtime_type=RuntimeType.CORRELATION,
        runtime_id="correlation_runtime",
        factory=_correlation_runtime,
        dependencies=(RuntimeType.FEATURE,),
        priority=35,
        optional=True,
        modes=(),
    ),
    RuntimeType.NARRATIVE: RuntimeSpec(
        runtime_type=RuntimeType.NARRATIVE,
        runtime_id="narrative_runtime",
        factory=_narrative_runtime,
        dependencies=(RuntimeType.INGESTION,),
        priority=30,
        optional=True,
        modes=(TradingMode.LIVE,),
    ),
    RuntimeType.REPLAY: RuntimeSpec(
        runtime_type=RuntimeType.REPLAY,
        runtime_id="replay_runtime",
        factory=_replay_runtime,
        priority=100,
        modes=(TradingMode.BACKTEST,),
    ),
}


def get_runtime_spec(runtime_type: RuntimeType) -> Optional[RuntimeSpec]:
    return RUNTIME_SPECS.get(runtime_type)


def iter_runtime_specs(runtime_types: Iterable[RuntimeType]) -> Iterable[RuntimeSpec]:
    for runtime_type in runtime_types:
        spec = get_runtime_spec(runtime_type)
        if spec:
            yield spec


def _parse_runtime_type_list(value: str) -> List[RuntimeType]:
    runtime_types: List[RuntimeType] = []
    for raw_name in value.split(","):
        name = raw_name.strip().lower()
        if not name:
            continue
        try:
            runtime_types.append(RuntimeType(name))
        except ValueError:
            continue
    return runtime_types


def get_mode_runtime_types(mode: TradingMode) -> List[RuntimeType]:
    override = (
        os.environ.get(f"{mode.value.upper()}_RUNTIMES")
        or os.environ.get("ORCHESTRATOR_RUNTIMES")
    )
    if override:
        runtime_types = _parse_runtime_type_list(override)
        if runtime_types:
            return runtime_types

    return [
        spec.runtime_type
        for spec in sorted(RUNTIME_SPECS.values(), key=lambda item: item.priority, reverse=True)
        if mode in spec.modes
    ]


def get_catalog_dependencies() -> Dict[RuntimeType, Sequence[RuntimeType]]:
    return {
        runtime_type: spec.dependencies
        for runtime_type, spec in RUNTIME_SPECS.items()
    }
