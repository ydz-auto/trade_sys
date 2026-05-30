from enum import Enum
from typing import Dict, Any, Optional, Callable
import random
from dataclasses import dataclass

from runtime.kernel.runtime_container import (
    RuntimeKernel,
    RawEvent,
)
from domain.risk.guards import GuardViolation
import logging

logger = logging.getLogger(__name__)


class FailureMode(Enum):
    EVENT_DELAY = "event_delay"
    OUT_OF_ORDER = "out_of_order"
    DUPLICATE_EVENT = "duplicate_event"
    MISSING_EVENT = "missing_event"
    PARTIAL_CANDLE = "partial_candle"
    CLOCK_DRIFT = "clock_drift"
    TIMESTAMP_TAMPERING = "timestamp_tampering"


@dataclass
class FailureTestResult:
    mode: FailureMode
    was_intercepted: bool
    exception_type: Optional[str]
    exception_message: Optional[str]
    step: int
    success: bool


class FailureInjector:
    def __init__(
        self,
        kernel: RuntimeKernel,
    ):
        self._kernel = kernel
        self._results: list[FailureTestResult] = []
        self._event_counter = 0

    @property
    def results(self) -> list[FailureTestResult]:
        return self._results

    def inject_event_delay(
        self,
        raw_event: RawEvent,
        delay_ms: Optional[int] = None,
    ) -> RawEvent:
        if delay_ms is None:
            delay_ms = random.randint(100, 1000)

        logger.info(
            f"Injecting EVENT_DELAY: extra {delay_ms}ms, "
            f"event_time={raw_event.event_time_ms}"
        )

        modified_payload = raw_event.payload.copy()
        modified_payload["injected_delay_ms"] = delay_ms
        modified_payload["injected_mode"] = "EVENT_DELAY"

        return RawEvent(
            event_type=raw_event.event_type,
            symbol=raw_event.symbol,
            exchange=raw_event.exchange,
            event_time_ms=raw_event.event_time_ms,
            payload=modified_payload,
        )

    def inject_out_of_order(
        self,
        raw_event: RawEvent,
        past_offset_ms: Optional[int] = None,
    ) -> RawEvent:
        if past_offset_ms is None:
            past_offset_ms = random.randint(100, 500)

        logger.info(
            f"Injecting OUT_OF_ORDER: past offset {past_offset_ms}ms, "
            f"original_time={raw_event.event_time_ms}"
        )

        modified_payload = raw_event.payload.copy()
        modified_payload["injected_offset_ms"] = past_offset_ms
        modified_payload["injected_mode"] = "OUT_OF_ORDER"

        return RawEvent(
            event_type=raw_event.event_type,
            symbol=raw_event.symbol,
            exchange=raw_event.exchange,
            event_time_ms=raw_event.event_time_ms - past_offset_ms,
            payload=modified_payload,
        )

    def inject_duplicate(
        self,
        base_event: RawEvent,
        duplicate_id_suffix: str = "_duplicate",
    ) -> RawEvent:
        logger.info(
            f"Injecting DUPLICATE_EVENT: for event_type={base_event.event_type}"
        )

        modified_payload = base_event.payload.copy()
        modified_payload["injected_mode"] = "DUPLICATE_EVENT"
        modified_payload["is_duplicate"] = True

        return RawEvent(
            event_type=base_event.event_type,
            symbol=base_event.symbol,
            exchange=base_event.exchange,
            event_time_ms=base_event.event_time_ms,
            payload=modified_payload,
        )

    def inject_partial_candle(
        self,
        raw_event: RawEvent,
    ) -> RawEvent:
        logger.info(
            f"Injecting PARTIAL_CANDLE: event_type={raw_event.event_type}"
        )

        modified_payload = raw_event.payload.copy()
        modified_payload["injected_mode"] = "PARTIAL_CANDLE"
        modified_payload["is_complete"] = False

        return RawEvent(
            event_type=raw_event.event_type,
            symbol=raw_event.symbol,
            exchange=raw_event.exchange,
            event_time_ms=raw_event.event_time_ms,
            payload=modified_payload,
        )

    def inject_timestamp_tampering(
        self,
        raw_event: RawEvent,
    ) -> RawEvent:
        logger.info(
            f"Injecting TIMESTAMP_TAMPERING: event_type={raw_event.event_type}"
        )

        modified_payload = raw_event.payload.copy()
        modified_payload["injected_mode"] = "TIMESTAMP_TAMPERING"
        modified_payload["tampered"] = True

        return RawEvent(
            event_type=raw_event.event_type,
            symbol=raw_event.symbol,
            exchange=raw_event.exchange,
            event_time_ms=raw_event.event_time_ms,
            payload=modified_payload,
        )

    def run_all_failure_tests(
        self,
        base_events: list[RawEvent],
    ) -> Dict[str, Any]:
        self._results = []
        self._kernel.reset()

        logger.info("=" * 80)
        logger.info("Starting all failure mode tests")
        logger.info("=" * 80)

        logger.info("\n--- Baseline - Processing normal events")
        baseline_ok = self._run_baseline_test(base_events)

        logger.info("\n--- Testing EVENT_DELAY")
        self._test_single_mode(
            FailureMode.EVENT_DELAY,
            base_events,
            self.inject_event_delay,
        )

        logger.info("\n--- Testing OUT_OF_ORDER")
        self._test_single_mode(
            FailureMode.OUT_OF_ORDER,
            base_events,
            self.inject_out_of_order,
        )

        logger.info("\n--- Testing PARTIAL_CANDLE")
        self._test_single_mode(
            FailureMode.PARTIAL_CANDLE,
            base_events,
            self.inject_partial_candle,
        )

        summary = self._generate_summary()

        logger.info("\n" + "=" * 80)
        logger.info("Failure test summary")
        logger.info("=" * 80)
        logger.info(f"Total tests: {summary['total_tests']}")
        logger.info(f"Passed: {summary['passed']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info("=" * 80)

        return summary

    def _run_baseline_test(
        self,
        events: list[RawEvent],
    ) -> bool:
        success = True
        try:
            for event in events:
                ok, _ = self._kernel.handle(event)
                if not ok:
                    success = False
            return success
        except Exception as e:
            logger.error(f"Baseline test failed: {e}")
            return False

    def _test_single_mode(
        self,
        mode: FailureMode,
        base_events: list[RawEvent],
        injector_func: Callable[[RawEvent], RawEvent],
    ):
        self._kernel.reset()

        intercepted_count = 0
        total_count = 0

        if not base_events:
            return

        base_event = base_events[0]

        try:
            injected_event = injector_func(base_event)

            ok, _ = self._kernel.handle(injected_event)

            result = FailureTestResult(
                mode=mode,
                was_intercepted=(not ok),
                exception_type=None,
                exception_message=None,
                step=self._event_counter,
                success=(not ok),
            )

            self._results.append(result)

            if result.success:
                logger.info(f"✓ {mode.value} test passed (intercepted as expected)")
            else:
                logger.error(f"✗ {mode.value} test failed (not intercepted)")

        except GuardViolation as e:
            result = FailureTestResult(
                mode=mode,
                was_intercepted=True,
                exception_type="GuardViolation",
                exception_message=str(e),
                step=self._event_counter,
                success=True,
            )
            self._results.append(result)
            logger.info(f"✓ {mode.value} test passed (intercepted by Guard: {e}")

        except Exception as e:
            result = FailureTestResult(
                mode=mode,
                was_intercepted=False,
                exception_type=type(e).__name__,
                exception_message=str(e),
                step=self._event_counter,
                success=False,
            )
            self._results.append(result)
            logger.error(f"✗ {mode.value} test failed (unexpected exception: {e}")

    def _generate_summary(self) -> Dict[str, Any]:
        total = len(self._results)
        passed = sum(1 for r in self._results if r.success)
        failed = total - passed

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total) * 100 if total > 0 else 0.0,
            "results": [
                {
                    "mode": r.mode.value,
                    "success": r.success,
                    "intercepted": r.was_intercepted,
                }
                for r in self._results
            ],
        }

    def get_detailed_report(self) -> str:
        lines = []
        lines.append("=" * 80)
        lines.append("DETAILED FAILURE TEST REPORT")
        lines.append("=" * 80)
        for result in self._results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            lines.append(f"\n{status} - {result.mode.value}")
            if result.exception_message:
                lines.append(f"  Exception: {result.exception_type}")
                lines.append(f"  Message: {result.exception_message}")
        lines.append("=" * 80)
        return "\n".join(lines)
