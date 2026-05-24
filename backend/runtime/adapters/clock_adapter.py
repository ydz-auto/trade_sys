"""
Clock Adapter - Bridge between runtime kernel and infrastructure clock.

Kernel code should use this adapter instead of importing
infrastructure.utilities.runtime_clock directly.
"""
import time as _time
from typing import Callable, Optional


_now_ms_fn: Optional[Callable[[], int]] = None
_clock_class = None


def set_clock_functions(now_ms_fn: Callable[[], int] = None, clock_class=None):
    """Inject infrastructure clock functions.

    Call this at application startup:
        from infrastructure.utilities.runtime_clock import now_ms, RuntimeClock
        from runtime.adapters.clock_adapter import set_clock_functions
        set_clock_functions(now_ms, RuntimeClock)
    """
    global _now_ms_fn, _clock_class
    _now_ms_fn = now_ms_fn
    _clock_class = clock_class


def now_ms() -> int:
    """Get current time in milliseconds.

    If infrastructure clock is available, use it.
    Otherwise fall back to time.time().
    """
    if _now_ms_fn is not None:
        return _now_ms_fn()
    return int(_time.time() * 1000)


def get_clock_class():
    """Get the RuntimeClock class if available, else None."""
    return _clock_class
