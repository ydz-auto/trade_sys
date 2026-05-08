# TradeAgent Dashboard

前端项目，基于 React + TypeScript + Vite + Tailwind CSS

## 技术栈

- **框架**: React 18 + TypeScript
- **路由**: React Router DOM v6
- **状态管理**: Zustand
- **样式**: Tailwind CSS
- **图表**: Chart.js + react-chartjs-2
- **图标**: Lucide React
- **构建**: Vite

## 项目结构

```
frontend/
├── src/
│   ├── components/       # 通用组件
│   │   ├── layout/       # 布局组件
│   │   ├── FactorCard.tsx
│   │   ├── StatusBadge.tsx
│   │   └── LiveIndicator.tsx
│   ├── pages/           # 页面组件
│   │   ├── DashboardPage.tsx
│   │   └── WeightConfigPage.tsx
│   ├── store/           # 状态管理
│   │   └── tradingStore.ts
│   ├── types/           # TypeScript 类型
│   │   └── index.ts
│   ├── App.tsx          # 根组件
│   ├── main.tsx         # 入口文件
│   └── index.css         # 全局样式
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 页面列表

| 路由 | 页面 | 状态 |
|------|------|------|
| `/` | 数据大盘 | ✅ 完成 |
| `/factors` | 因子面板 | ✅ 完成 |
| `/weights` | 权重配置 | ✅ 完成 |
| `/versions` | 版本历史 | ✅ 完成 |
| `/regime` | Regime状态 | 🚧 开发中 |
| `/risk` | 风险引擎 | 🚧 开发中 |
| `/decision` | 决策信号 | 🚧 开发中 |
| `/control` | 控制中心 | 🚧 开发中 |
| `/positions` | 仓位管理 | 🚧 开发中 |
| `/execution` | 执行追踪 | 🚧 开发中 |

## 设计规范

参见 [design-system/MASTER.md](../../design-system/MASTER.md)
