"""Stateless compute and adapter engines.

Engines are allowed to perform pure compute and external IO, but they must not
own trading runtime state such as positions, pending orders, replay cursors, or
feature availability.
"""

__all__: list[str] = []
