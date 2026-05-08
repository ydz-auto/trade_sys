import { useState } from 'react'
import { useTradingStore } from '../../store/tradingStore'
import type { SystemMode } from '../../types'

const modeConfig: Record<SystemMode, { bg: string; border: string; text: string; color: string }> = {
  BACKTEST: { bg: 'bg-neutral/20', border: 'border-neutral/30', text: 'NEUTRAL 回测', color: 'neutral' },
  SIMULATION: { bg: 'bg-warning/20', border: 'border-warning/30', text: 'SIMULATION 模拟', color: 'warning' },
  LIVE: { bg: 'bg-bullish/20', border: 'border-bullish/30', text: 'LIVE 实盘', color: 'bullish' },
}

interface HeaderProps {
  title: string
  subtitle?: string
}

export function Header({ title, subtitle }: HeaderProps) {
  const { mode, setMode, lastUpdate } = useTradingStore()
  const [showConfirm, setShowConfirm] = useState(false)

  const handleModeChange = (newMode: SystemMode) => {
    if (newMode === 'LIVE' && mode !== 'LIVE') {
      setShowConfirm(true)
      return
    }
    setMode(newMode)
  }

  const confirmLive = () => {
    setMode('LIVE')
    setShowConfirm(false)
  }

  const config = modeConfig[mode]

  return (
    <>
      <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-50">
        <div className="flex items-center gap-4">
          <h1 className="font-heading text-lg">{title}</h1>
          {subtitle && <span className="text-text-secondary text-sm">{subtitle}</span>}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1 bg-background rounded-lg p-1">
            {(['BACKTEST', 'SIMULATION', 'LIVE'] as SystemMode[]).map((m) => (
              <button
                key={m}
                onClick={() => handleModeChange(m)}
                className={clsx(
                  'px-3 py-1 text-xs rounded-md transition-colors cursor-pointer',
                  mode === m
                    ? `bg-${modeConfig[m].color}/20 text-${modeConfig[m].color} border border-${modeConfig[m].color}/30 font-medium`
                    : 'bg-border/50 text-text-secondary hover:bg-border'
                )}
              >
                {m === 'BACKTEST' ? '回测' : m === 'SIMULATION' ? '模拟' : '实盘'}
              </button>
            ))}
          </div>

          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${config.bg} ${config.border}`}>
            <span className={`w-2 h-2 rounded-full bg-${config.color}`}></span>
            <span className={`text-xs font-medium text-${config.color}`}>{config.text}</span>
          </div>

          <div className="text-xs text-text-secondary">
            最后更新: {lastUpdate.toLocaleTimeString('zh-CN', { hour12: false })}
          </div>

          <button className="p-2 hover:bg-border/50 rounded-lg cursor-pointer transition-colors">
            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </header>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-surface border border-border rounded-xl p-6 max-w-md">
            <h3 className="font-heading text-lg mb-4 text-bearish">⚠️ 确认切换到实盘模式</h3>
            <p className="text-text-secondary mb-6">
              切换到实盘模式将使用真实资金进行交易。请确保您已了解相关风险。
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 py-2 bg-border/50 text-text-secondary rounded-lg hover:bg-border cursor-pointer transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmLive}
                className="flex-1 py-2 bg-bullish text-white rounded-lg hover:bg-bullish/80 cursor-pointer transition-colors font-medium"
              >
                确认实盘
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function clsx(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
