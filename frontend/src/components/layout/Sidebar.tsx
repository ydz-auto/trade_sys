import { useTradingStore } from '../../store/tradingStore'
import clsx from 'clsx'

const modeConfig = {
  BACKTEST: { color: 'neutral', text: 'NEUTRAL 回测' },
  SIMULATION: { color: 'warning', text: 'SIMULATION 模拟' },
  LIVE: { color: 'bullish', text: 'LIVE 实盘' },
}

const navItems = [
  { section: '监控层', items: [
    { path: '/', label: '数据大盘', icon: 'ChartBar' },
    { path: '/factors', label: '因子面板', icon: 'TrendingUp' },
  ]},
  { section: '策略层', items: [
    { path: '/regime', label: 'Regime状态', icon: 'Shield' },
    { path: '/risk', label: '风险引擎', icon: 'AlertTriangle' },
    { path: '/decision', label: '决策信号', icon: 'ClipboardList' },
  ]},
  { section: '配置层', items: [
    { path: '/weights', label: '权重配置', icon: 'Sliders' },
    { path: '/versions', label: '版本历史', icon: 'History' },
    { path: '/control', label: '控制中心', icon: 'MessageSquare' },
  ]},
  { section: '执行层', items: [
    { path: '/positions', label: '仓位管理', icon: 'Box' },
    { path: '/execution', label: '执行追踪', icon: 'Zap' },
  ]},
]

export function Sidebar() {
  const { mode, isConnected } = useTradingStore()

  return (
    <aside className="w-56 bg-surface border-r border-border flex flex-col flex-shrink-0">
      <div className="h-16 flex items-center gap-3 px-4 border-b border-border">
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
          <svg className="w-5 h-5 text-background" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </div>
        <div>
          <span className="font-heading font-bold text-sm">TradeAgent</span>
          <span className="block text-xs text-text-secondary">Trading System</span>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-4 overflow-y-auto scrollbar-hide">
        {navItems.map((section) => (
          <div key={section.section}>
            <div className="text-xs text-text-secondary uppercase tracking-wider px-3 py-2">
              {section.section}
            </div>
            {section.items.map((item) => (
              <a
                key={item.path}
                href={item.path}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg border border-transparent',
                  'text-text-secondary hover:bg-border/50 hover:text-text-primary transition-colors'
                )}
              >
                <span className="text-sm">{item.label}</span>
              </a>
            ))}
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-2 mb-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-bullish opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-bullish"></span>
          </span>
          <span className="text-xs text-text-secondary">
            {isConnected ? '系统正常' : '系统异常'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'px-1.5 py-0.5 rounded text-xs',
              modeConfig[mode].color === 'bullish' && 'bg-bullish/20 text-bullish',
              modeConfig[mode].color === 'warning' && 'bg-warning/20 text-warning',
              modeConfig[mode].color === 'neutral' && 'bg-neutral/20 text-neutral'
            )}
          >
            {modeConfig[mode].text}
          </span>
        </div>
        <div className="text-xs text-text-secondary mt-1">版本: v2.1.0</div>
      </div>
    </aside>
  )
}
