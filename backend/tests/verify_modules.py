"""
Verification Script - 模块验证脚本

在没有 pytest 的环境中手动验证模块功能。
"""

print("=" * 70)
print("Trading Intelligence OS - Module Verification")
print("=" * 70)

errors = []
successes = []

# 1. Test Signal Domain
print("\n1. Testing domain/signal/ module...")
try:
    from domain.signal.models import (
        Signal,
        SignalDirection,
        SignalConfidence,
        SignalStrength,
        SignalState,
        SignalType,
    )
    print("   ✓ Signal models imported successfully")
    
    # Create test signal
    signal = Signal(
        symbol="BTC/USDT",
        timeframe="1h",
        direction=SignalDirection.LONG,
        type=SignalType.TECHNICAL,
        confidence=SignalConfidence(value=0.8),
        strength=SignalStrength(magnitude=0.7),
    )
    print(f"   ✓ Signal created: {signal.signal_id}")
    
    # Activate signal
    signal.activate()
    assert signal.state == SignalState.ACTIVE
    print("   ✓ Signal activation works")
    
    successes.append("Signal models")
except Exception as e:
    errors.append(f"Signal models: {e}")
    print(f"   ✗ Error: {e}")

try:
    from domain.signal.fusion import VotingFusion, BlendingFusion
    print("   ✓ Fusion modules imported successfully")
    successes.append("Signal fusion")
except Exception as e:
    errors.append(f"Signal fusion: {e}")
    print(f"   ✗ Error: {e}")

try:
    from domain.signal.lifecycle import SignalDecay, SignalCooldown
    print("   ✓ Lifecycle modules imported successfully")
    successes.append("Signal lifecycle")
except Exception as e:
    errors.append(f"Signal lifecycle: {e}")
    print(f"   ✗ Error: {e}")

try:
    from domain.signal.registry import SignalRegistry, SignalQuery
    print("   ✓ Registry modules imported successfully")
    
    registry = SignalRegistry()
    print("   ✓ Signal registry created")
    successes.append("Signal registry")
except Exception as e:
    errors.append(f"Signal registry: {e}")
    print(f"   ✗ Error: {e}")

# 2. Test Execution Intelligence
print("\n2. Testing domain/execution/intelligence/ module...")
try:
    from domain.execution.intelligence import (
        SlippagePredictor,
        ImpactModel,
        LiquidityEstimator,
        ExecutionOptimizer,
    )
    print("   ✓ Intelligence modules imported successfully")
    
    # Test slippage predictor
    predictor = SlippagePredictor()
    prediction = predictor.predict(
        order_size=1.0,
        current_price=50000.0,
        spread_bps=10.0,
        volatility=0.02,
        orderbook_depth=100.0,
        avg_trade_size=10.0,
    )
    print(f"   ✓ Slippage prediction: {prediction.expected_slippage_bps:.2f} bps")
    
    # Test impact model
    impact_model = ImpactModel()
    impact = impact_model.calculate_impact(
        order_size=5.0,
        current_price=50000.0,
        orderbook_depth=100.0,
        volatility=0.02,
        avg_daily_volume=1000.0,
    )
    print(f"   ✓ Impact calculation: {impact.total_impact_bps:.2f} bps")
    
    # Test liquidity estimator
    estimator = LiquidityEstimator()
    liquidity = estimator.estimate(
        bid_price=50000.0,
        ask_price=50005.0,
        bid_depth=100.0,
        ask_depth=100.0,
        recent_volume=50.0,
        volatility=0.02,
    )
    print(f"   ✓ Liquidity estimate: {liquidity.rating.value}")
    
    # Test execution optimizer
    optimizer = ExecutionOptimizer()
    plan = optimizer.optimize(
        order_size=5.0,
        current_price=50000.0,
        side="buy",
        bid_price=50000.0,
        ask_price=50005.0,
        bid_depth=100.0,
        ask_depth=100.0,
        spread_bps=10.0,
        volatility=0.02,
        recent_volume=50.0,
        avg_daily_volume=1000.0,
        avg_trade_size=10.0,
    )
    print(f"   ✓ Execution optimization: {plan.strategy.value} strategy")
    print(f"     Expected cost: {plan.total_cost_bps:.2f} bps")
    
    successes.append("Execution intelligence")
except Exception as e:
    errors.append(f"Execution intelligence: {e}")
    print(f"   ✗ Error: {e}")

# 3. Test Portfolio Domain
print("\n3. Testing domain/portfolio/ module...")
try:
    from domain.portfolio import Portfolio, Position
    print("   ✓ Portfolio modules imported successfully")
    
    portfolio = Portfolio(
        portfolio_id="test_portfolio",
        initial_capital=100000.0,
        equity=100000.0,
    )
    print("   ✓ Portfolio created")
    
    position = Position(
        symbol="BTC/USDT",
        side="long",
        size=1.0,
        entry_price=50000.0,
        current_price=51000.0,
        unrealized_pnl=1000.0,
    )
    portfolio.update_position(position)
    print(f"   ✓ Position updated: {position.symbol}")
    
    exposure = portfolio.total_exposure
    print(f"   ✓ Exposure calculated: {exposure:.2f}")
    
    successes.append("Portfolio domain")
except Exception as e:
    errors.append(f"Portfolio domain: {e}")
    print(f"   ✗ Error: {e}")

# 4. Test Domain Analysis
print("\n4. Testing domain/analysis/ module...")
try:
    from domain.analysis import SignalDirection
    print("   ✓ Analysis module imported successfully")
    print(f"   ✓ SignalDirection: {SignalDirection.POSITIVE.value}")
    successes.append("Domain analysis")
except Exception as e:
    errors.append(f"Domain analysis: {e}")
    print(f"   ✗ Error: {e}")

# Summary
print("\n" + "=" * 70)
print("VERIFICATION SUMMARY")
print("=" * 70)

print(f"\n✅ Successful: {len(successes)} modules")
for module in successes:
    print(f"   - {module}")

if errors:
    print(f"\n❌ Failed: {len(errors)} modules")
    for error in errors:
        print(f"   - {error}")
else:
    print("\n🎉 All modules verified successfully!")

print("\n" + "=" * 70)
