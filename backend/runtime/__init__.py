# Runtimes - Concrete runtime implementations
#
# Each subdirectory is an independent runtime that implements
# runtime.contracts.runtime_protocol.RuntimeProtocol.
#
# Runtimes import from:
#   runtime.kernel.*      (lifecycle, state machine, orchestration)
#   runtime.contracts.*   (stable protocols)
#   runtime.adapters.*    (infrastructure/domain/engines adapters)
#
# Runtimes should NOT import from each other directly.

