import { NavLink } from 'react-router-dom'
import { useTradingStore } from '../../store/tradingStore'
import clsx from 'clsx'
import {
  LayoutDashboard,
  TrendingUp,
  Radio,
  Zap,
  History,
  Shield,
  Brain,
  Settings,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { useState } from 'react'

const modeConfig = {
  BACKTEST: { text: 'BACKTEST', bgClass: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  SIMULATION: { text: 'PAPER', bgClass: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
  LIVE: { text: 'LIVE', bgClass: 'bg-red-500/20 text-red-400 border-red-500/30' },
}

const navStructure = [
  {
    section: '首页',
    icon: LayoutDashboard,
    items: [
      { path: '/', label: 'Runtime 总览' },
    ],
  },
  {
    section: '市场',
    icon: TrendingUp,
    items: [
      { path: '/markets', label: '市场监控' },
      { path: '/regime', label: '市场状态' },
      { path: '/data-pipeline', label: '数据流监控' },
    ],
  },
  {
    section: '策略',
    icon: Radio,
    items: [
      { path: '/signals', label: '策略运行态', highlight: true },
      { path: '/feature-contribution', label: 'Feature 贡献' },
      { path: '/strategy', label: '策略管理' },
      { path: '/alpha', label: 'Alpha 生命周期' },
      { path: '/behaviour', label: '行为检测' },
    ],
  },
  {
    section: '交易',
    icon: Zap,
    items: [
      { path: '/trading', label: '实盘交易', highlight: true },
      { path: '/execution', label: '订单执行' },
      { path: '/positions', label: '持仓管理' },
    ],
  },
  {
    section: 'Replay',
    icon: History,
    items: [
      { path: '/replay', label: 'Runtime 回放', highlight: true },
      { path: '/backtest', label: 'Backtest' },
    ],
  },
  {
    section: '风险',
    icon: Shield,
    items: [
      { path: '/risk', label: '风险引擎', highlight: true },
      { path: '/risk-propagation', label: '风险传播' },
    ],
  },
  {
    section: 'AI',
    icon: Brain,
    items: [
      { path: '/narrative', label: 'Narrative' },
      { path: '/sentiment', label: 'Sentiment' },
      { path: '/events', label: 'Event Intelligence' },
    ],
  },
  {
    section: '系统',
    icon: Settings,
    items: [
      { path: '/control', label: 'Runtime 控制中心' },
      { path: '/trading-mode', label: '交易模式', highlight: true },
      { path: '/monitor', label: 'Runtime 监控' },
      { path: '/settings', label: '设置' },
    ],
  },
]

function NavSection({ section, icon: Icon, items }: { section: string; icon: React.ElementType; items: Array<{ path: string; label: string; highlight?: boolean }> }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-tertiary uppercase tracking-widest font-medium hover:text-text-secondary transition-colors"
      >
        <Icon className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">{section}</span>
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      
      {expanded && (
        <div className="space-y-0.5">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200',
                  'hover:bg-border/50',
                  isActive
                    ? 'bg-primary/10 text-primary border border-primary/20 font-medium'
                    : 'text-text-secondary hover:text-text-primary border border-transparent',
                  item.highlight && !isActive && 'text-text-primary/80'
                )
              }
            >
              <span className="truncate">{item.label}</span>
              {item.highlight && (
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

export function Sidebar() {
  const { mode, isConnected } = useTradingStore()

  return (
    <aside 
      style={{ position: 'fixed', left: 0, top: 0, bottom: 0, width: 220, zIndex: 50 }} 
      className="bg-surface border-r border-border flex flex-col"
    >
      <div className="h-14 flex items-center gap-2.5 px-3 border-b border-border">
        <div className="w-8 h-8 bg-gradient-to-br from-primary to-accent rounded-lg flex items-center justify-center shadow-lg shadow-primary/20">
          <Zap className="w-4 h-4 text-background" />
        </div>
        <div className="flex-1">
          <div className="font-heading font-bold text-sm tracking-tight">TradeAgent</div>
          <div className="text-[9px] text-text-tertiary tracking-wide">RUNTIME PLATFORM</div>
        </div>
      </div>

      <nav className="flex-1 p-2 overflow-y-auto scrollbar-hide">
        {navStructure.map((section) => (
          <NavSection key={section.section} {...section} />
        ))}
      </nav>

      <div className="p-2.5 border-t border-border bg-surface/50">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              {isConnected && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-bullish opacity-75"></span>
              )}
              <span
                className={clsx(
                  'relative inline-flex rounded-full h-2 w-2',
                  isConnected ? 'bg-bullish' : 'bg-bearish'
                )}
              ></span>
            </span>
            <span className="text-[10px] text-text-secondary">
              {isConnected ? 'Runtime Active' : 'Offline'}
            </span>
          </div>
          <span
            className={clsx(
              'px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wide border',
              modeConfig[mode].bgClass
            )}
          >
            {modeConfig[mode].text}
          </span>
        </div>
        <div className="text-[9px] text-text-tertiary">v2.2.0 Runtime System</div>
      </div>
    </aside>
  )
}
