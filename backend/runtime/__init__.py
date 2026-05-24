"""
Runtime - Deterministic Event-Sourced Trading Runtime OS

Architecture:
    API
      ↓
    APPLICATION (CQRS / Workflow)
      ↓
    RUNTIME KERNEL
      ↓
    RUNTIMES (concrete business runtimes)
      ↓
    COMPUTE ENGINES
      ↓
    PURE DOMAIN
      ↓
    INFRASTRUCTURE

Structure:
    runtime/
    ├── kernel/          # System control plane (lifecycle, state machine, orchestration)
    ├── contracts/       # Stable protocols and event contracts
    ├── adapters/        # Bridges to infrastructure/domain/engines
    └── pipeline/        # Pipeline orchestration (to be refactored later)

    runtimes/            # Concrete runtime implementations
    ├── ingestion_runtime/
    ├── feature_runtime/
    ├── signal_runtime/
    ├── execution_runtime/
    ├── portfolio_runtime/
    ├── replay_runtime/
    ├── projection_runtime/
    ├── correlation_runtime/
    ├── narrative_runtime/
    ├── regime_runtime/
    ├── verification_runtime/
    └── trading_mode_manager.py
"""
