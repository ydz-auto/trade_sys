import { NavLink } from 'react-router-dom'
import { useTradingStore } from '../../store/tradingStore'
import clsx from 'clsx'
import {
  LayoutDashboard,
  LineChart,
  Shield,
  Database,
  Radio,
  BarChart3,
  Settings,
  Zap,
  Target,
  History,
  AlertTriangle,
  Brain,
  MessageSquare,
  Activity,
  TrendingUp,
  Boxes,
  Cpu,
  Network,
  Sparkles,
} from 'lucide-react'

const modeConfig = {
  BACKTEST: { color: 'neutral', text: 'NEUTRAL 回测' },
  SIMULATION: { color: 'warning', text: 'SIMULATION 模拟' },
  LIVE: { color: 'bullish', text: 'LIVE 实盘' },
}

const navStructure = [
  {
    section: '总览',
    items: [
      { path: '/', label: '运行态总览', icon: LayoutDashboard },
    ],
  },
  {
    section: '市场',
    items: [
      { path: '/markets', label: '市场监控', icon: LineChart },
      { path: '/regime', label: '市场状态', icon: Shield },
      { path: '/data-pipeline', label: '数据管道', icon: Database },
    ],
  },
  {
    section: '策略',
    items: [
      { path: '/signals', label: '运行态信号', icon: Radio },
      { path: '/feature-contribution', label: '特征贡献度', icon: BarChart3 },
      { path: '/strategy', label: '策略管理', icon: Settings },
      { path: '/alpha', label: 'Alpha生命周期', icon: TrendingUp },
    ],
  },
  {
    section: '交易',
    items: [
      { path: '/execution', label: '执行管理', icon: Zap },
      { path: '/positions', label: '持仓管理', icon: Boxes },
      { path: '/trading', label: '跟随交易', icon: Target },
    ],
  },
  {
    section: '回放',
    items: [
      { path: '/replay', label: '运行态回放', icon: History },
      { path: '/backtest', label: '历史回测', icon: Activity },
    ],
  },
  {
    section: '风险',
    items: [
      { path: '/risk', label: '风险引擎', icon: AlertTriangle },
      { path: '/risk-propagation', label: '风险传导', icon: Network },
    ],
  },
  {
    section: '智能分析',
    items: [
      { path: '/narrative', label: '叙事分析', icon: Sparkles },
      { path: '/sentiment', label: '情绪监控', icon: Brain },
      { path: '/events', label: '事件智能', icon: MessageSquare },
    ],
  },
  {
    section: '系统',
    items: [
      { path: '/control', label: '控制中心', icon: Cpu },
      { path: '/monitor', label: '系统监控', icon: Activity },
      { path: '/settings', label: '系统设置', icon: Settings },
    ],
  },
]

export function Sidebar() {
  const { mode, isConnected } = useTradingStore()

  return (
    <aside style={{ position: 'fixed', left: 0, top: 0, bottom: 0, width: 240, zIndex: 50 }} className="bg-surface border-r border-border flex flex-col">
      <div className="h-16 flex items-center gap-3 px-4 border-b border-border">
        <div className="w-9 h-9 bg-gradient-to-br from-primary to-accent rounded-lg flex items-center justify-center shadow-lg shadow-primary/20">
          <Zap className="w-5 h-5 text-background" />
        </div>
        <div>
          <span className="font-heading font-bold text-sm tracking-tight">TradeAgent</span>
          <span className="block text-[10px] text-text-secondary tracking-wide">RUNTIME TERMINAL</span>
        </div>
      </div>

      <nav className="flex-1 p-2 space-y-1 overflow-y-auto scrollbar-hide">
        {navStructure.map((section) => (
          <div key={section.section} className="mb-3">
            <div className="text-[10px] text-text-tertiary uppercase tracking-widest px-3 py-1.5 font-medium">
              {section.section}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-200',
                      'hover:bg-border/50',
                      isActive
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'text-text-secondary hover:text-text-primary border border-transparent'
                    )
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="p-3 border-t border-border bg-surface/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
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
            <span className="text-xs text-text-secondary">
              {isConnected ? '系统正常' : '系统异常'}
            </span>
          </div>
          <span
            className={clsx(
              'px-2 py-0.5 rounded text-[10px] font-medium tracking-wide',
              modeConfig[mode].color === 'bullish' && 'bg-bullish/20 text-bullish',
              modeConfig[mode].color === 'warning' && 'bg-warning/20 text-warning',
              modeConfig[mode].color === 'neutral' && 'bg-neutral/20 text-neutral'
            )}
          >
            {modeConfig[mode].text.split(' ')[0]}
          </span>
        </div>
        <div className="text-[10px] text-text-tertiary">v2.1.0 Runtime</div>
      </div>
    </aside>
  )
}
