"""
Example: Testing the Resilience Infrastructure
This file demonstrates the Circuit Breaker, Retry, and Fallback mechanisms
"""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryPolicy,
    RetryConfig,
    FallbackChain,
    PrimaryFallback,
    StaticValueFallback,
    FallbackResult,
    create_default_chain,
    get_circuit_breaker
)
from infrastructure.logging import get_logger

logger = get_logger("example.resilience")


async def unstable_function(fail_rate=0.7):
    """Function that fails often for testing"""
    if random.random() < fail_rate:
        logger.warning("Simulated failure!")
        raise Exception("Random failure")
    return "Success!"


async def test_circuit_breaker():
    """Test circuit breaker"""
    print("\n" + "="*60)
    print("Testing Circuit Breaker")
    print("="*60)
    
    config = CircuitBreakerConfig(
        name="test_circuit",
        failure_threshold=3,
        recovery_timeout=2.0,
        half_open_max_calls=2,
        success_threshold=2
    )
    
    breaker = CircuitBreaker(config)
    
    print(f"Initial state: {breaker.state}")
    
    # Test 1: Normal operation (fail)
    for i in range(5):
        try:
            result = await breaker.execute(unstable_function, fail_rate=1.0)
            print(f"Attempt {i+1}: {result}")
        except Exception as e:
            print(f"Attempt {i+1}: {str(e)[:50]}")
            print(f"  State: {breaker.state}, Failures: {breaker._failure_count}")
    
    print(f"\nAfter failures: State={breaker.state}")
    
    # Wait for recovery timeout
    print("\nWaiting for recovery timeout (2.5s)...")
    await asyncio.sleep(2.5)
    
    print(f"After timeout: State={breaker.state}")
    
    # Test recovery
    print("\nTesting recovery...")
    for i in range(3):
        try:
            result = await breaker.execute(unstable_function, fail_rate=0.0)
            print(f"Attempt {i+1}: {result}")
            print(f"  State: {breaker.state}, Successes: {breaker._success_count}")
        except Exception as e:
            print(f"Attempt {i+1}: {str(e)[:50]}")
    
    stats = breaker.get_stats()
    print(f"\nFinal stats: {stats}")


async def test_retry():
    """Test retry policy"""
    print("\n" + "="*60)
    print("Testing Retry Policy")
    print("="*60)
    
    config = RetryConfig(
        max_attempts=4,
        initial_delay=0.2,
        max_delay=1.0,
        backoff_multiplier=2.0,
        jitter=True
    )
    
    policy = RetryPolicy(config)
    
    # Test with decreasing fail rate
    attempt = 0
    def decreasing_fail():
        nonlocal attempt
        attempt += 1
        return unstable_function(fail_rate=0.6)
    
    try:
        result = await policy.execute(decreasing_fail)
        print(f"Retry success! Result: {result}")
    except Exception as e:
        print(f"Retry failed after {config.max_attempts} attempts: {e}")


async def test_fallback():
    """Test fallback chain"""
    print("\n" + "="*60)
    print("Testing Fallback Chain")
    print("="*60)
    
    # Create fallback chain
    chain = FallbackChain()
    chain.add_strategy(PrimaryFallback())
    chain.add_strategy(StaticValueFallback("Fallback Value"))
    
    # Test with failing primary
    print("Testing with failing primary function...")
    result = await chain.execute(lambda: unstable_function(fail_rate=1.0))
    print(f"Result: success={result.success}, data={result.data}, strategy={result.strategy_used}")
    
    # Test with working primary
    print("\nTesting with working primary function...")
    result = await chain.execute(lambda: unstable_function(fail_rate=0.0))
    print(f"Result: success={result.success}, data={result.data}, strategy={result.strategy_used}")
    
    # Test with create_default_chain
    print("\nTesting create_default_chain...")
    default_chain = create_default_chain(
        primary_name="test",
        static_value="Default Fallback",
        alternate_func=lambda: "Alternate Result"
    )
    result = await default_chain.execute(lambda: unstable_function(fail_rate=1.0))
    print(f"Result: success={result.success}, data={result.data}, strategy={result.strategy_used}")


async def test_combined():
    """Test combined usage: circuit breaker + retry + fallback"""
    print("\n" + "="*60)
    print("Testing Combined Usage")
    print("="*60)
    
    # Get or create circuit breaker
    breaker = get_circuit_breaker(
        "combined_test",
        CircuitBreakerConfig(
            name="combined_test",
            failure_threshold=2,
            recovery_timeout=5.0
        )
    )
    
    # Create retry policy
    retry_policy = RetryPolicy(RetryConfig(max_attempts=2))
    
    # Create fallback chain
    fallback = create_default_chain("combined", static_value="Final Safety Net")
    
    async def wrapped_operation():
        # First: retry
        async def with_retry():
            return await retry_policy.execute(lambda: unstable_function(fail_rate=0.8))
        
        # Then: circuit breaker
        result = await breaker.execute(with_retry)
        return result
    
    try:
        result = await wrapped_operation()
        print(f"Success! Result: {result}")
    except Exception as e:
        print(f"Operation failed after all retries and circuit breaker: {e}")
        # Use fallback
        fallback_result = await fallback.execute(lambda: unstable_function(fail_rate=1.0))
        print(f"Fallback result: {fallback_result.data}")


async def main():
    await test_circuit_breaker()
    await test_retry()
    await test_fallback()
    await test_combined()


if __name__ == "__main__":
    asyncio.run(main())
