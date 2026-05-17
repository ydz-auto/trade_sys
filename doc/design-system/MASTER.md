# TradeAgent 完整交易系统 - 设计规范

## Overview

TradeAgent 是一个专业级加密货币交易信号系统，支持 BTC/ETH 现货和合约交易。系统采用模块化架构，包含从数据采集到执行反馈的完整闭环。

---

## 系统架构总览

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           TradeAgent 交易系统架构                                │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  [数据层]                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 市场行情 │ ETF资金 │ 宏观商品 │ 新闻资讯 │ 社交媒体 │ KOL数据 │ 链上数据 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      ↓                                           │
│  [特征层] → 收益率 / 动量 / 波动率 / 资金流 / 情绪分数                            │
│                                      ↓                                           │
│  [因子层] → 趋势因子 / 资金流因子 / 情绪因子 / 宏观因子 / 行为因子 / 历史因子      │
│                                      ↓                                           │
│  [Regime引擎] → TRENDING / RANGE / PANIC / EUPHORIA / RISK_OFF / UNCERTAIN     │
│                                      ↓                                           │
│  [风险引擎] → 波动风险 / 资金流风险 / 情绪风险 / 宏观风险 / 组合风险               │
│                                      ↓                                           │
│  [决策引擎] → BUY / SELL / HOLD 信号                                           │
│                                      ↓                                           │
│  [仓位引擎] → 仓位大小 / 杠杆倍数 / 止损止盈                                     │
│                                      ↓                                           │
│  [执行层] → 订单管理 / 交易所对接 / 状态追踪                                     │
│                                      ↓                                           │
│  [反馈闭环] → PnL反馈 / 风险反馈 / 信号反馈 / Regime反馈                         │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 页面清单

| 页面 | 路由 | 功能 |
|------|------|------|
| **数据大盘** | `/` | 实时行情、ETF、宏观、新闻、社交媒体、情绪指数 |
| **特征预览** | `/features` | 特征计算结果预览 |
| **因子面板** | `/factors` | 6个因子得分、雷达图、趋势图 |
| **Regime状态** | `/regime` | 市场状态检测、置信度、驱动因素 |
| **风险引擎** | `/risk` | 风险指数分解、风控规则 |
| **决策信号** | `/decision` | BUY/SELL/HOLD信号、置信度 |
| **仓位管理** | `/positions` | 当前仓位、浮盈浮亏、止损止盈 |
| **执行追踪** | `/execution` | 订单状态、重试机制、执行日志 |
| **反馈闭环** | `/feedback` | PnL统计、胜率、连续亏损、暴露倍数 |
| **历史分析** | `/history` | 历史回测、策略表现 |
| **权重配置** | `/weights` | 因子权重调整 |

---

## 颜色系统

| Role | Hex | Usage |
|------|-----|-------|
| Primary | `#F59E0B` | 主色调、因子卡片、标题 |
| Secondary | `#FBBF24` | 辅助强调 |
| Accent | `#8B5CF6` | CTA按钮、情绪分析 |
| Background | `#0F172A` | 主背景 (OLED友好) |
| Surface | `#1E293B` | 卡片/面板背景 |
| Border | `#334155` | 分割线、边框 |
| Text Primary | `#F8FAFC` | 主要文字 |
| Text Secondary | `#94A3B8` | 次要文字、标签 |
| Bullish | `#10B981` | 上涨、正向因子、做多 |
| Bearish | `#EF4444` | 下跌、负向因子、做空 |
| Warning | `#F97316` | 警告状态、中等风险 |
| Neutral | `#3B82F6` | 中性状态 |

---

## 组件设计

### 1. 状态徽章 (StatusBadge)

| State | Background | Text | Border |
|-------|------------|------|--------|
| 做多 (LONG) | `bg-bullish/20` | `text-bullish` | `border-bullish/30` |
| 做空 (SHORT) | `bg-bearish/20` | `text-bearish` | `border-bearish/30` |
| 无仓位 | `bg-border/50` | `text-text-secondary` | - |
| 风险-低 | `bg-bullish/20` | `text-bullish` | - |
| 风险-中 | `bg-warning/20` | `text-warning` | - |
| 风险-高 | `bg-bearish/20` | `text-bearish` | - |

### 2. 实时指示器 (LiveIndicator)

```html
<span class="relative flex h-2 w-2">
  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-bullish opacity-75"></span>
  <span class="relative inline-flex rounded-full h-2 w-2 bg-bullish"></span>
</span>
```

### 3. 因子卡片 (FactorCard)

- 默认: `bg-surface/50 border border-border`
- 悬停: `border-primary/50 shadow-lg shadow-primary/10 translate-y-[-2px]`
- 正值: `text-bullish`
- 负值: `text-bearish`

### 4. 风险条 (RiskBar)

```html
<div class="h-1.5 bg-border/50 rounded-full overflow-hidden">
  <div class="h-full rounded-full" style="width: 58%"></div>
</div>
<!-- 0-30: bullish, 30-60: warning, 60-100: bearish -->
```

### 5. 信号徽章 (SignalBadge)

| Signal | Style |
|--------|-------|
| BUY | `bg-bullish/20 border-bullish/30 text-bullish` |
| SELL | `bg-bearish/20 border-bearish/30 text-bearish` |
| HOLD | `bg-border/50 text-text-secondary` |

---

## 数据源状态指示

| Status | Indicator | Color |
|--------|-----------|-------|
| 正常 | `w-1.5 h-1.5 rounded-full bg-bullish` | #10B981 |
| 延迟 | `w-1.5 h-1.5 rounded-full bg-warning` | #F97316 |
| 异常 | `w-1.5 h-1.5 rounded-full bg-bearish` | #EF4444 |

---

## 响应式断点

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop XL | 1440px+ | 4列网格 |
| Desktop | 1024px-1439px | 3-4列网格 |
| Tablet | 768px-1023px | 2列网格 |
| Mobile | <768px | 单列堆叠 |

---

## 导航结构

```
数据层
├── 数据大盘 (实时监控)
└── 特征预览

分析层
├── 因子面板
├── Regime状态
└── 风险引擎

决策层
├── 决策信号
├── 仓位管理
└── 执行追踪

反馈层
├── 反馈闭环
└── 历史分析
```

---

## 字体系统

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

--font-heading: 'Fira Code', monospace;
--font-body: 'Fira Sans', sans-serif;
```

---

## 技术栈

| Category | Technology |
|----------|------------|
| Framework | React 18 + TypeScript |
| Styling | Tailwind CSS |
| Charts | Chart.js / ApexCharts |
| State | Zustand / Redux Toolkit |
| Real-time | WebSocket |
| Icons | Heroicons / Lucide |
| Build | Vite |

---

## 交互规范

### 动画时长
- 悬停过渡: `transition-colors duration-200`
- 数据更新: `transition-all duration-300`
- 页面切换: `transition-opacity duration-150`

### 禁止事项
- ❌ 使用 emoji 作为图标
- ❌ 无过渡的即时状态切换
- ❌ 可交互元素无悬停反馈
- ❌ 装饰性持续动画
- ❌ 低于 4.5:1 的文字对比度
