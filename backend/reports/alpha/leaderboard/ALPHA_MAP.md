# Per-Asset Alpha Map

研究范式从 **Strategy-centric** → **Alpha-centric**

## Dominant Alpha Summary

| Symbol | Dominant Alpha | Best IS PF | Best OOS PF | IS Pass | OOS Pass |
|--------|----------------|------------|-------------|---------|----------|
| BTCUSDT | drawdown_dip_buying | 1.72 | N/A | 3 | 0 |
| ETCUSDT | drawdown_dip_buying | 6.57 | 3.70 | 5 | 3 |
| SOLUSDT | drawdown_dip_buying | 2.02 | 1.79 | 3 | 2 |
| ZECUSDT | drawdown_dip_buying | 5.28 | 1.76 | 5 | 4 |

## Key Insights

1. **Universal Alpha 很少**：多数 Alpha 是 asset-specific
2. **ETC 对 Funding Squeeze 极其敏感**
3. **SOL 的 Ret Reversal OOS 最稳**
4. **BTC 的均值回归较弱**

## Research Factory Pipeline

```
Feature IC
  → Conditional IC
    → Fee Sensitivity
      → Multi-Symbol
        → Walk-forward
          → Alpha Registry
            → Leaderboard
```
