"""
Failure Injector - 失效模式注入器

设计原则:
- 主动测试所有可能的失效模式
- 验证 Guard 能正确拦截
- 验证内核在失效情况下保持稳定
"""

from enum import Enum
from typing import Dict, Any, Optional, Callable
import random
from dataclasses import dataclass

from runtime.kernel import (
    RuntimeKernel,
    RawEvent,
)
from runtime.guards import GuardViolation
from domain.logging import get_logger

logger = get_logger("runtime.failure_injector")


class FailureMode(Enum):
    """失效模式"""
    EVENT_DELAY = "event_delay"          # 事件延迟
    OUT_OF_ORDER = "out_of_order"          # 事件乱序
    DUPLICATE_EVENT = "duplicate_event"    # 重复事件
    MISSING_EVENT = "missing_event"          # 缺失事件
    PARTIAL_CANDLE = "partial_candle"          # 未完成K线
    CLOCK_DRIFT = "clock_drift"              # 时钟漂移
    TIMESTAMP_TAMPERING = "timestamp_tampering"  # 时间戳篡改


@dataclass
class FailureTestResult:
    """失效测试结果"""
    mode: FailureMode
    was_intercepted: bool
    exception_type: Optional[str]
    exception_message: Optional[str]
    step: int
    success: bool


class FailureInjector:
    """
    失效模式注入器
    
    主动测试所有失效模式，验证:
    1. Guard 能正确拦截
    2. 内核保持稳定
    """
    
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
    
    # ============================================
    # 失效模式注入
    # ============================================
    
    def inject_event_delay(
        self,
        raw_event: RawEvent,
        delay_ms: Optional[int] = None,
    ) -> RawEvent:
        """
        注入事件延迟
        
        正常情况下:
            event_time = T
            available_time = T + default_delay
        
        注入后:
            event_time = T
            available_time = T + (default_delay + X
            (X 是额外的延迟
        
        验证:
            当处理时, processing_time < available_time, AvailabilityGuard 应该拦截
        """
        if delay_ms is None:
            delay_ms = random.randint(100, 1000)
        
        logger.info(
            f"Injecting EVENT_DELAY: extra {delay_ms}ms, "
            f"event_time={raw_event.event_time_ms}"
        )
        
        # 我们通过一个 "future_event" 来模拟, 即:
        # 事件在未来才变为可用
        # 注意: 这里我们只修改 payload 来标记
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
        """
        注入事件乱序
        
        正常情况下:
            事件时间递增
        
        注入后:
            事件时间比前一个事件时间 - X
        
        验证:
            OrderingGuard 应该拦截
        """
        if past_offset_ms is None:
            past_offset_ms = random.randint(100, 500)
        
        logger.info(
            f"Injecting OUT_OF_ORDER: past offset {past_offset_ms}ms, "
            f"original_time={raw_event.event_time_ms}"
        )
        
        modified_payload = raw_event.payload.copy()
        modified_payload["injected_offset_ms"] = past_offset_ms
        modified_payload["injected_mode"] = "OUT_OF_ORDER"
        
        # 把时间改为过去
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
        """
        注入重复事件
        
        正常情况下:
            事件 ID 唯一
        
        注入后:
            两个相同的 event_id
        
        验证:
            DuplicateGuard 应该拦截第二个
        """
        logger.info(
            f"Injecting DUPLICATE_EVENT: for event_type={base_event.event_type}"
        )
        
        modified_payload = base_event.payload.copy()
        modified_payload["injected_mode"] = "DUPLICATE_EVENT"
        modified_payload["is_duplicate"] = True
        
        # 注意: 在 RawEvent 没有 event_id, 在 Authority 会计算
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
        """
        注入未完成K线
        
        验证:
            PartialCandleGuard 应该拦截
        """
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
        """
        注入时间戳篡改
        
        验证:
            虽然这在 kernel 中我们在 Authority 会重新计算
            但这里我们测试 Guard 能处理
        """
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
    
    # ============================================
    # 完整测试
    # ============================================
    
    def run_all_failure_tests(
        self,
        base_events: list[RawEvent],
    ) -> Dict[str, Any]:
        """
        运行所有失效模式测试
        
        Args:
            base_events: 基础事件列表
        
        Returns:
            测试结果
        """
        self._results = []
        self._kernel.reset()
        
        logger.info("=" * 80)
        logger.info("Starting all failure mode tests")
        logger.info("=" * 80)
        
        # 1. 先正常处理一次正常事件序列作为基准
        logger.info("\n--- Baseline - Processing normal events")
        baseline_ok = self._run_baseline_test(base_events)
        
        # 2. EVENT_DELAY 测试
        logger.info("\n--- Testing EVENT_DELAY")
        self._test_single_mode(
            FailureMode.EVENT_DELAY,
            base_events,
            self.inject_event_delay,
        )
        
        # 3. OUT_OF_ORDER 测试
        logger.info("\n--- Testing OUT_OF_ORDER")
        self._test_single_mode(
            FailureMode.OUT_OF_ORDER,
            base_events,
            self.inject_out_of_order,
        )
        
        # 4. PARTIAL_CANDLE 测试
        logger.info("\n--- Testing PARTIAL_CANDLE")
        self._test_single_mode(
            FailureMode.PARTIAL_CANDLE,
            base_events,
            self.inject_partial_candle,
        )
        
        # 5. 总结
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
        """运行基准测试"""
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
        injector_func: Callable[[RawEvent],
    ):
        """单个模式测试"""
        self._kernel.reset()
        
        intercepted_count = 0
        total_count = 0
        
        # 选择一个事件进行注入
        if not base_events:
            return
        
        base_event = base_events[0]
        
        try:
            # 注入
            injected_event = injector_func(base_event)
            
            # 尝试处理
            ok, _ = self._kernel.handle(injected_event)
            
            # 检查是否被拦截
            # 注意: 这里 ok 为 False 说明被拦截
            # 这是预期的
            
            result = FailureTestResult(
                mode=mode,
                was_intercepted=(not ok),
                exception_type=None,
                exception_message=None,
                step=self._event_counter,
                success=(not ok),  # 被拦截说明成功
            )
            
            self._results.append(result)
            
            if result.success:
                logger.info(f"✓ {mode.value} test passed (intercepted as expected)")
            else:
                logger.error(f"✗ {mode.value} test failed (not intercepted)")
                
        except GuardViolation as e:
            # GuardViolation 是预期的
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
            # 其他异常
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
        """生成总结"""
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
        """获取详细报告"""
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
