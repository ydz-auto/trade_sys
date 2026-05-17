import { useState, useEffect } from 'react'

interface TradingMode {
  mode: string
  name: string
  description: string
  warning: string | null
}

interface TradingModeInfo {
  mode: string
  description: string
  market_data_source: string
  order_execution: string
  show_warning: boolean
  config: Record<string, any>
}

const getModeColor = (mode: string) => {
  switch (mode) {
    case 'demo':
      return {
        bg: 'bg-blue-500/10',
        border: 'border-blue-500/30',
        text: 'text-blue-400',
        dot: 'bg-blue-500',
        badge: 'bg-blue-500/20',
      }
    case 'paper':
      return {
        bg: 'bg-amber-500/10',
        border: 'border-amber-500/30',
        text: 'text-amber-400',
        dot: 'bg-amber-500',
        badge: 'bg-amber-500/20',
      }
    case 'prod':
      return {
        bg: 'bg-rose-500/10',
        border: 'border-rose-500/30',
        text: 'text-rose-400',
        dot: 'bg-rose-500',
        badge: 'bg-rose-500/20',
      }
    default:
      return {
        bg: 'bg-gray-500/10',
        border: 'border-gray-500/30',
        text: 'text-gray-400',
        dot: 'bg-gray-500',
        badge: 'bg-gray-500/20',
      }
  }
}

const getModeLabel = (mode: string) => {
  switch (mode) {
    case 'demo':
      return 'Demo / 测试网'
    case 'paper':
      return 'Paper / 模拟'
    case 'prod':
      return 'Prod / 实盘'
    default:
      return mode.toUpperCase()
  }
}

export function TradingModeSwitcher() {
  const [currentMode, setCurrentMode] = useState<TradingModeInfo | null>(null)
  const [availableModes, setAvailableModes] = useState<TradingMode[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showConfirm, setShowConfirm] = useState<string | null>(null)

  // 获取当前模式
  const fetchCurrentMode = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/config/trading-mode')
      const data = await response.json()
      setCurrentMode(data)
    } catch (error) {
      console.error('Failed to fetch trading mode:', error)
    }
  }

  // 获取可用模式
  const fetchAvailableModes = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/config/trading-mode/options')
      const data = await response.json()
      setAvailableModes(data.options)
    } catch (error) {
      console.error('Failed to fetch trading mode options:', error)
    }
  }

  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchCurrentMode(), fetchAvailableModes()])
      setLoading(false)
    }
    init()
  }, [])

  const handleModeSelect = async (mode: string) => {
    if (mode === 'prod' && currentMode?.mode !== 'prod') {
      setShowConfirm(mode)
      return
    }

    await switchMode(mode)
  }

  const switchMode = async (mode: string) => {
    try {
      const response = await fetch('http://localhost:8000/api/config/trading-mode', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode }),
      })
      const data = await response.json()
      console.log('Mode switch response:', data)
      
      // 重新获取当前模式
      await fetchCurrentMode()
      setShowDropdown(false)
      setShowConfirm(null)
    } catch (error) {
      console.error('Failed to switch mode:', error)
    }
  }

  if (loading) {
    return (
      <div className="h-8 w-24 bg-gray-700/50 rounded animate-pulse"></div>
    )
  }

  if (!currentMode) {
    return null
  }

  const colors = getModeColor(currentMode.mode)

  return (
    <div className="relative">
      {/* 当前模式显示 */}
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${colors.bg} ${colors.border} border transition-all hover:opacity-80 cursor-pointer`}
      >
        <span className={`w-2 h-2 rounded-full ${colors.dot}`}></span>
        <span className={`text-xs font-medium ${colors.text}`}>
          {getModeLabel(currentMode.mode)}
        </span>
        <svg
          className={`w-3 h-3 ${colors.text} transition-transform ${showDropdown ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Paper Trading 警告条 */}
      {currentMode.mode === 'paper' && (
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 bg-amber-500/20 text-amber-300 text-xs px-3 py-1 rounded-full whitespace-nowrap border border-amber-500/30">
          📊 真实行情 + 本地撮合
        </div>
      )}

      {/* 下拉菜单 */}
      {showDropdown && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-surface border border-border rounded-xl shadow-xl z-50 overflow-hidden">
          <div className="p-3 border-b border-border/50">
            <h3 className="font-medium text-sm">选择交易模式</h3>
          </div>
          
          <div className="p-2">
            {availableModes.map((mode) => {
              const isActive = currentMode.mode === mode.mode
              const modeColors = getModeColor(mode.mode)
              
              return (
                <button
                  key={mode.mode}
                  onClick={() => handleModeSelect(mode.mode)}
                  className={`w-full text-left p-3 rounded-lg transition-all ${
                    isActive
                      ? `${modeColors.badge} border ${modeColors.border}`
                      : 'hover:bg-border/50'
                  } mb-1 last:mb-0 cursor-pointer`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`font-medium text-sm ${isActive ? modeColors.text : 'text-text'}`}>
                      {mode.name}
                    </span>
                    {isActive && (
                      <span className="text-xs text-green-400">当前</span>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary">{mode.description}</p>
                  {mode.warning && (
                    <p className={`text-xs mt-1 ${
                      mode.mode === 'prod' ? 'text-rose-400' : 'text-amber-400'
                    }`}>
                      ⚠️ {mode.warning}
                    </p>
                  )}
                </button>
              )
            })}
          </div>

          {/* 说明 */}
          <div className="p-3 border-t border-border/50 bg-background/50">
            <p className="text-xs text-text-secondary">
              💡 推荐：Paper Trading 模式用于策略验证
            </p>
          </div>
        </div>
      )}

      {/* 关闭下拉菜单的点击遮罩 */}
      {showDropdown && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setShowDropdown(false)}
        />
      )}

      {/* 实盘确认弹窗 */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100]">
          <div className="bg-surface border border-rose-500/30 rounded-xl p-6 max-w-md shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-rose-500/20 rounded-full flex items-center justify-center">
                <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="font-heading text-lg text-rose-400">⚠️ 确认切换到实盘模式</h3>
            </div>
            <p className="text-text-secondary mb-4">
              切换到实盘模式将使用真实资金进行交易。请确保：
            </p>
            <ul className="text-sm text-text-secondary mb-6 space-y-2">
              <li>• 您已了解所有相关风险</li>
              <li>• 您已经过充分的策略回测和模拟交易验证</li>
              <li>• 您的 API Key 配置正确</li>
            </ul>
            <p className="text-xs text-amber-400 mb-6">
              📝 提示：请先在 .env 文件中设置 MODE=prod 并重启服务
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(null)}
                className="flex-1 py-2 bg-border/50 text-text-secondary rounded-lg hover:bg-border cursor-pointer transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => switchMode(showConfirm)}
                className="flex-1 py-2 bg-rose-500 text-white rounded-lg hover:bg-rose-600 cursor-pointer transition-colors font-medium"
              >
                我已了解风险，确认
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
