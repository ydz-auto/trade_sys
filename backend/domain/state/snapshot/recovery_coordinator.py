from typing import Dict, Any, List, Optional

import logging
from domain.state.snapshot.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)

RECOVERY_ORDER = [
    "kernel",
    "ingestion",
    "feature",
    "signal",
    "execution",
    "portfolio",
    "replay",
    "projection",
    "correlation",
    "regime",
    "narrative",
]


class RecoveryCoordinator:

    def __init__(self):
        self._checkpoint_manager = CheckpointManager()
        self._results: Dict[str, Dict[str, Any]] = {}

    async def recover_all(
        self,
        runtimes: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        self._results = {}

        for runtime_name in RECOVERY_ORDER:
            runtime = runtimes.get(runtime_name)
            if runtime is None:
                logger.info(f"Skipping {runtime_name}: not provided")
                continue

            try:
                checkpoint = await self._checkpoint_manager.load_checkpoint(runtime_name)

                if checkpoint is None:
                    logger.info(f"No checkpoint for {runtime_name}, skipping recovery")
                    self._results[runtime_name] = {
                        "recovered": False,
                        "reason": "no_checkpoint",
                    }
                    continue

                await runtime.recover(checkpoint)

                health = await runtime.health()
                healthy = health.get("healthy", False)

                self._results[runtime_name] = {
                    "recovered": True,
                    "healthy": healthy,
                    "checkpoint_id": checkpoint.get("metadata", {}).get("checkpoint_id"),
                }

                if not healthy:
                    logger.warning(
                        f"Runtime {runtime_name} recovered but unhealthy: {health}"
                    )
                else:
                    logger.info(f"Runtime {runtime_name} recovered and healthy")

            except Exception as e:
                logger.error(f"Failed to recover {runtime_name}: {e}")
                self._results[runtime_name] = {
                    "recovered": False,
                    "error": str(e),
                }

        return self._results

    def get_results(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._results)
