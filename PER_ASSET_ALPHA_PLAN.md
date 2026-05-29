# Per-Asset Alpha Plan

## Overview
This document outlines the actionable plan for deploying alpha strategies per crypto assets based on the current state of research.

## Current State Summary
- Project: Crypto Quantitative Trading System
- Assets: BTCUSDT, ETCUSDT, SOLUSDT, ZECUSDT
- Completed: Initial alpha validation (walk-forward & stability skipped)
- Pipeline: Complete validation pipeline available

## Action Plan

### Phase 1: Generate Per-Asset Alpha Validation
**Goal**: Re-run the validation pipeline with walk-forward and parameter stability tests enabled for all active alphas.

**Steps**:
1. Run alpha pipeline with `skip_walk_forward=False` and `skip_stability=False`
2. Generate per-symbol leaderboard with complete validation
3. Generate paper trading configuration

**Command**:
```bash
cd e:\00_crypto\00_code\backend
python -m research.alpha.pipeline --strategy all --symbols BTCUSDT,ETCUSDT,SOLUSDT,ZECUSDT --timeframes 1h --days 365
```

### Phase 2: Per-Symbol Alpha Selection
Based on current partial results, here are the top candidates per symbol:

#### ETCUSDT
- drawdown_dip_buying: PF=6.57, Sharpe=9.46 (Tier A)
- trend_filter_long: PF=1.81, Sharpe=3.06 (Tier A)
- funding_extreme_reversal: PF=1.42, Sharpe=2.56 (Tier A)
- ret_5_reversal: PF=1.52, Sharpe=2.27 (Tier A)

#### SOLUSDT
- drawdown_dip_buying: PF=2.02, Sharpe=4.16 (Tier A)
- volatility_panic_reversal: PF=2.00, Sharpe=3.68 (Tier A)
- drawdown_ret5_combo: PF=1.26, Sharpe=1.75 (Tier B)

#### ZECUSDT
- drawdown_dip_buying: PF=5.28, Sharpe=9.86 (Tier A)
- ret_10_reversal: PF=1.99, Sharpe=4.21 (Tier A)
- trend_filter_long: PF=1.92, Sharpe=4.04 (Tier A)
- ret_3_reversal: PF=1.93, Sharpe=3.66 (Tier A)
- drawdown_ret5_combo: PF=1.84, Sharpe=4.47 (Tier A)

#### BTCUSDT
- drawdown_dip_buying: PF=1.72, Sharpe=3.02 (Tier A)
- ret_5_reversal: PF=1.21, Sharpe=1.08 (Tier B)
- volatility_panic_reversal: PF=1.14, Sharpe=1.39 (Tier B)

### Phase 3: Paper Trading Configuration
Generate paper trading configs for Tier A and Tier B candidates that pass walk-forward and stability tests.

## Notes
- BTC needs more aggressive thresholds and panic regime only
- Most alphas are asset-specific, avoid cross-asset parameters
- Focus on short alphas as next phase
