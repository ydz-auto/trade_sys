# Runtime Adapters
#
# Adapters that bridge runtime kernel to infrastructure/domain/engines.
# Kernel should never import infrastructure directly - it goes through adapters.
#
# Adapters:
#   logging_adapter.py   - wraps infrastructure.logging
#   clock_adapter.py     - wraps infrastructure.utilities.runtime_clock
#   config_adapter.py    - wraps infrastructure.config
#   storage_adapter.py   - wraps infrastructure.storage/persistence
#   messaging_adapter.py - wraps infrastructure.messaging

