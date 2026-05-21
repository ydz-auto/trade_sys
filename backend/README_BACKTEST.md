# 完整策略回测系统

## 📋 概述

本系统包含 39 个完整策略，每个策略都有上下文检查机制，自动适配不同的市场环境。

## 🚀 快速开始

### 1️⃣ 使用现有完整脚本（推荐）

系统已包含完整的回测脚本在 `scripts/backtest_full_all_strategies.py`：

```bash
cd backend
python scripts/backtest_full_all_strategies.py
```

这个脚本：
- 使用真实数据（需从数据湖加载
- 包含所有39个策略
- 上下文检查
- 完整的统计和报告
- 结果保存到 JSON

### 2️⃣ 使用多个交易对回测

我还创建了一个完整的脚本 `scripts/run_complete_backtest.py`，包含4个交易对的测试。

## 📊 策略列表

### 一、经典技术指标策略（6个）
1. `rsi_14` - RSI超买超卖
2. `macd_12_26_9` - MACD金叉死叉
3. `bollinger_bands` - 布林带突破
4. `ma_cross` - 均线交叉
5. `rsi_macd_combo` - RSI+MACD组合
6. `ema_cross` - EMA交叉

### 二、事件驱动策略（6个）
7. `panic_reversal` - 恐慌反弹
8. `long_liquidation_bounce` - 多头踩踏反弹
9. `volume_climax_fade` - 放量高潮衰竭
10. `weak_bounce_short` - 弱反弹做空
11. `fake_breakout_trap` - 假突破反杀
12. `short_squeeze_hunt` - 空头挤压

### 三、策略地图策略（6个）
13. `compression_breakout` - 压缩突破
14. `funding_reset` - 资金费率重置
15. `oi_flush` - OI洗盘
16. `weekend_liquidity_trap` - 周末流动性陷阱
17. `session_rotation` - 时段轮换
18. `macro_shock_recovery` - 宏观冲击恢复

### 四、创新策略（8个）
19. `leveraged_short_squeeze` - 杠杆空头挤压
20. `micro_range_ripples` - 微区间涟漪
21. `cascade_flip` - 级联翻转
22. `funding_exhaustion_trap` - 资金衰竭陷阱
23. `meme_mania_rotation` - Meme狂热轮换
24. `session_gap_exploit` - 时段跳空利用
25. `dead_cat_echo` - 死猫回声
26. `liquidity_vacuum_breakout` - 流动性真空突破

### 五、Playbook行为策略（7个）
27. `pb_panic_reversal` - 放宽版恐慌反弹
28. `pb_fake_breakout` - 放宽版假突破
29. `pb_oi_flush` - 放宽版OI洗盘
30. `pb_weekend_manipulation` - 周末操控
31. `pb_short_squeeze` - 放宽版空头挤压
32. `pb_volume_climax` - 放宽版放量高潮
33. `pb_liquidation_cascade` - 清盘级联

### 六、V2优化策略（6个）
34. `v2_volume_climax_fade` - V2放量高潮衰竭
35. `v2_weak_bounce_short` - V2弱反弹做空
36. `v2_fake_breakout_trap` - V2假突破反杀
37. `v2_weekend_trap` - V2周末陷阱
38. `v2_short_squeeze_hunt` - V2空头挤压
39. `v2_funding_reset` - V2资金费率重置

## 🔍 上下文检查机制

每个策略都有上下文检查，确保在合适的市场环境触发：

### 市场环境检测
- `panic_drop` - 恐慌下跌（4h > 8%）
- `slow_drop` - 缓慢下跌（4h > 2%）
- `bounce` - 反弹（4h > 2%）
- `normal` - 正常市场

### 策略-环境匹配
- 做多事件驱动策略只在下跌环境中更有效
- 做空策略在反弹/正常环境中更有效
- 突破策略在震荡/正常环境中更有效
- 趋势策略在震荡市中关闭

## 🛡️ 风险管理

- **初始资金**：$10,000
- **杠杆**：50x
- **固定止损**：15%（资金）
- **移动止盈**：60%~1000% + 15%回撤保护
- **持仓时限**：48小时
- **手续费**：0.05% + 0.02%滑点

## 📈 输出指标

- 每个策略独立统计
- 总收益、胜率、平均盈亏
- 最大回撤
- 平仓原因分布
- 策略排名

## 💾 结果保存

结果保存到：
- `data_lake/research/full_all_strategies_backtest.json`
- 包含所有交易详情
- 策略排名和统计

## 🎯 推荐工作流

1. 确保数据湖有数据：
```bash
python scripts/data_lake_download.py --binance-klines --symbols BTCUSDT ETHUSDT SOLUSDT ZECUSDT --years 2025
```

2. 生成特征：
```bash
python scripts/generate_features.py
```

3. 运行回测：
```bash
python scripts/backtest_full_all_strategies.py
```

4. 分析结果，选择表现最好的策略
