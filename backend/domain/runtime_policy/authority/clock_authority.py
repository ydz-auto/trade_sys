from enum import Enum
from datetime import datetime
from typing import Optional

from infrastructure.logging import get_logger

logger = get_logger("runtime.authority.clock")


class ClockMode(Enum):
    LIVE = "live"
    REPLAY = "replay"
    FROZEN = "frozen"


class ClockAuthority:

    def __init__(self, mode: ClockMode = ClockMode.LIVE):
        self._mode = mode
        self._replay_time_ms: Optional[int] = None
        self._frozen_time_ms: Optional[int] = None
        self._last_time_ms: Optional[int] = None

        logger.info(f"ClockAuthority initialized in {mode.value} mode")

    @property
    def mode(self) -> ClockMode:
        return self._mode

    def now_ms(self) -> int:
        if self._mode == ClockMode.LIVE:
            return int(datetime.utcnow().timestamp() * 1000)

        elif self._mode == ClockMode.REPLAY:
            if self._replay_time_ms is None:
                raise ValueError("Clock in REPLAY mode but no time set")
            return self._replay_time_ms

        elif self._mode == ClockMode.FROZEN:
            if self._frozen_time_ms is None:
                raise ValueError("Clock in FROZEN mode but not frozen")
            return self._frozen_time_ms

        else:
            raise ValueError(f"Unknown clock mode: {self._mode}")

    def advance_to(self, target_ms: int) -> None:
        if self._mode != ClockMode.REPLAY:
            raise ValueError(f"advance_to() only allowed in REPLAY mode, current: {self._mode}")

        if self._replay_time_ms is not None and target_ms < self._replay_time_ms:
            raise ValueError(
                f"Time cannot go backwards: {target_ms} < {self._replay_time_ms}"
            )

        self._replay_time_ms = target_ms
        self._last_time_ms = target_ms

        logger.debug(f"Clock advanced to {target_ms}")

    def freeze(self) -> None:
        if self._mode == ClockMode.FROZEN:
            return

        self._frozen_time_ms = self.now_ms()
        self._mode = ClockMode.FROZEN

        logger.info(f"Clock frozen at {self._frozen_time_ms}")

    def unfreeze(self) -> None:
        if self._mode != ClockMode.FROZEN:
            return

        self._frozen_time_ms = None
        self._mode = ClockMode.LIVE

        logger.info("Clock unfrozen")

    def switch_to_replay_mode(self, start_time_ms: int) -> None:
        self._mode = ClockMode.REPLAY
        self._replay_time_ms = start_time_ms
        self._last_time_ms = start_time_ms

        logger.info(f"Clock switched to REPLAY mode, start time: {start_time_ms}")

    def switch_to_live_mode(self) -> None:
        self._mode = ClockMode.LIVE
        self._replay_time_ms = None

        logger.info("Clock switched to LIVE mode")

    def __repr__(self) -> str:
        return f"ClockAuthority(mode={self._mode}, time={self.now_ms() if self._last_time_ms else 'uninitialized'})"
