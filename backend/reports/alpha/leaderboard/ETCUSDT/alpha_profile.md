# ETCUSDT Alpha Profile

## Summary

- **Dominant Alpha**: drawdown_ret5_combo
- **IS Pass**: 1
- **IS Warning**: 10
- **Tier A**: 1
- **Tier B**: 6

## Best In-Sample

- **Alpha**: drawdown_dip_buying
- **PF**: 6.57

## Best Walk-Forward

- **Alpha**: drawdown_ret5_combo
- **WF Sharpe**: 5.592

## Tier A Candidates

| Alpha | PF | Sharpe | WF Passed | Stab Passed |
|-------|----|--------|-----------|-------------|
| trend_filter_long | 1.81 | 3.06 | True | True |

## Tier B Candidates

| Alpha | PF | Sharpe | WF Passed | Stab Passed |
|-------|----|--------|-----------|-------------|
| ret_5_reversal | 1.52 | 2.27 | True | False |
| funding_extreme_reversal | 1.42 | 2.56 | True | False |
| drawdown_dip_buying | 6.57 | 9.46 | True | False |
| drawdown_ret5_combo | 1.33 | 2.07 | True | False |
| parabolic_blowoff | 1.53 | 1.20 | True | False |
| funding_trap_short | 3.94 | 8.46 | False | False |

