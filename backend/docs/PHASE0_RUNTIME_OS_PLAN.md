# Phase 0 Runtime OS Plan

This project already has a runtime-oriented shape. The next step is convergence,
not a disruptive directory rewrite.

## Goals

- deterministic event flow
- replay/live parity
- single ownership for mutable trading state
- runtime-safe imports
- gradual migration from service-shaped modules to stateless engines

## Implemented Phase 0

1. Runtime Protocol
   - `runtime/contracts/runtime_protocol.py`
   - Common `start/stop/on_event/snapshot/recover/health` control surface.

2. Ownership Registry
   - `runtime/authority/ownership_registry.py`
   - Maps authoritative mutable state to exactly one runtime.

3. Canonical Event Adapter
   - `runtime/contracts/event_adapter.py`
   - Converts transport `BaseEvent` into canonical immutable domain events.

4. Import Guard
   - `runtime/guards/import_guard.py`
   - Static import boundary checks for the most important forbidden directions.

5. Engines Migration Boundary
   - `engines/`
   - New home for stateless compute and external IO adapters.

## Dependency Policy

Allowed high-level flow:

```text
api -> application -> runtime -> engines -> domain -> infrastructure
```

Forbidden high-risk imports:

- `domain -> runtime`
- `domain -> services`
- `domain -> infrastructure`
- `engines -> runtime`
- `engines -> application`
- `infrastructure -> runtime`
- `api -> runtime/services/infrastructure`

The current guard is intentionally strict for new code. Existing violations
should be retired incrementally with focused migrations.

## Next Migration Order

1. Move stateful aggregation code behind `feature_runtime`.
2. Extract pure calculators from `services/aggregation_service` into `engines/compute`.
3. Replace application direct runtime singleton access with registry/workflow ports.
4. Retire the 25 currently detected legacy import-boundary violations.
5. Turn import guard from focused tests into a CI architecture test after existing exceptions are removed.
