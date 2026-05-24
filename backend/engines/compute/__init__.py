"""Pure compute engines.

Subdirectories:
  risk/        Risk engine and checkers
  signal/      Signal fusion and scoring
  feature/     Feature calculation and matrix management
  strategy/    Strategy definitions, discovery, and registry
  aggregation/ Candle aggregation and event grouping
  correlation/ Correlation computation and service
  scoring/     LLM-based scoring
  models/      Data models (candle, orderbook, trade)
  schemas/     Signal schemas

Move calculations here only after their mutable state has been removed
or explicitly owned by a runtime.
"""

__all__: list[str] = []
