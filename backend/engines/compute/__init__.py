"""Pure compute engines.

Subdirectories:
  risk/        Risk engine and checkers
  signal/      Signal fusion and scoring
  feature/     Feature calculation and matrix management
  strategy/    Legacy strategy definitions (deprecated)
  strategy_v2/ Strategy V2 - MarketContext based strategies
  context/     MarketContext builder and validators
  aggregation/ Candle aggregation and event grouping
  correlation/ Correlation computation and service
  scoring/     LLM-based scoring
  models/      Data models (candle, orderbook, trade)
  schemas/     Signal schemas

Move calculations here only after their mutable state has been removed
or explicitly owned by a runtime.
"""

__all__: list[str] = []
