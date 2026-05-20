import { useState, useEffect } from 'react'
import { Card, Radio, Button, Modal, Tag, Spin, Empty, Progress, Divider, Alert } from 'antd'
import {
  Gauge,
  Zap,
  Shield,
  AlertTriangle,
  CheckCircle,
  History,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'
import { api } from '../services/api/client'
import { isMockMode } from '../config/mock'
import clsx from 'clsx'

interface ModeInfo {
  mode: string
  config: {
    market_data_source: string
    order_execution: string
    risk_engine: string
    portfolio_isolated: boolean
    require_confirmation: boolean
    color: string
    warning: string | null
  }
  is_current: boolean
  portfolio: {
    balance: Record<string, number>
    positions: Record<string, unknown>
  }
}

interface ModeStatus {
  mode: string
  state: string
  previous_mode: string | null
  config: {
    market_data_source: string
    order_execution: string
    risk_engine: string
    color: string
    warning: string | null
  }
  is_safe_to_trade: [boolean, string]
}

const mockModes: ModeInfo[] = [
  {
    mode: 'backtest',
    config: {
      market_data_source: 'historical',
      order_execution: 'simulated',
      risk_engine: 'simulated',
      portfolio_isolated: true,
      require_confirmation: false,
      color: '#3B82F6',
      warning: null,
    },
    is_current: false,
    portfolio: { balance: { USDT: 100000 }, positions: {} },
  },
  {
    mode: 'paper',
    config: {
      market_data_source: 'real',
      order_execution: 'simulated',
      risk_engine: 'real',
      portfolio_isolated: true,
      require_confirmation: false,
      color: '#F59E0B',
      warning: 'Paper Trading: 真实行情 + 模拟下单',
    },
    is_current: true,
    portfolio: { balance: { USDT: 98542.50 }, positions: { BTCUSDT: {} } },
  },
  {
    mode: 'live',
    config: {
      market_data_source: 'real',
      order_execution: 'real',
      risk_engine: 'real',
      portfolio_isolated: true,
      require_confirmation: true,
      color: '#EF4444',
      warning: '⚠️ LIVE MODE: 真实交易，请谨慎操作！',
    },
    is_current: false,
    portfolio: { balance: {}, positions: {} },
  },
]

const modeIcons: Record<string, React.ReactNode> = {
  backtest: <History className="w-5 h-5" />,
  paper: <Shield className="w-5 h-5" />,
  live: <Zap className="w-5 h-5" />,
}

const modeLabels: Record<string, string> = {
  backtest: 'Backtest',
  paper: 'Paper Trading',
  live: 'Live Trading',
}

export function TradingModePage() {
  const [loading, setLoading] = useState(true)
  const [modes, setModes] = useState<ModeInfo[]>([])
  const [status, setStatus] = useState<ModeStatus | null>(null)
  const [selectedMode, setSelectedMode] = useState<string | null>(null)
  const [transitioning, setTransitioning] = useState(false)
  const [confirmModalVisible, setConfirmModalVisible] = useState(false)
  const [stats, setStats] = useState<Record<string, unknown>>({})

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [modesRes, statusRes, statsRes] = await Promise.all([
        api.get('/trading-mode/modes'),
        api.get('/trading-mode'),
        api.get('/trading-mode/stats'),
      ])

      if (isMockMode) {
        setModes(mockModes)
        setStatus({
          mode: 'paper',
          state: 'active',
          previous_mode: null,
          config: mockModes[1].config,
          is_safe_to_trade: [true, 'PAPER mode - simulated trading'],
        })
        setStats({ total_transitions: 0, failed_transitions: 0 })
      } else {
        if (modesRes.modes) setModes(modesRes.modes)
        if (statusRes) setStatus(statusRes)
        if (statsRes) setStats(statsRes)
      }
    } catch (error) {
      console.error('Failed to load trading mode data:', error)
      if (isMockMode) {
        setModes(mockModes)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleModeSelect = (mode: string) => {
    setSelectedMode(mode)
    const targetMode = modes.find(m => m.mode === mode)
    if (targetMode?.config.require_confirmation) {
      setConfirmModalVisible(true)
    }
  }

  const handleTransition = async (confirmed: boolean = false) => {
    if (!selectedMode) return

    setTransitioning(true)
    try {
      const result = await api.post('/trading-mode/transition', {
        target_mode: selectedMode,
        reason: 'Manual transition from UI',
        confirmed,
      })

      if (result.success) {
        await loadData()
        setConfirmModalVisible(false)
      } else if (result.requires_confirmation) {
        setConfirmModalVisible(true)
      }
    } catch (error) {
      console.error('Failed to transition:', error)
    } finally {
      setTransitioning(false)
    }
  }

  const currentMode = status?.mode || 'paper'

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Gauge className="w-6 h-6 text-primary" />
            Trading Mode
          </h1>
          <p className="text-text-secondary text-sm mt-1">
            Runtime Level 模式管理 - 控制整个系统的执行行为
          </p>
        </div>
        <Button
          icon={<RefreshCw className="w-4 h-4" />}
          onClick={loadData}
        >
          刷新
        </Button>
      </div>

      <Card className="bg-surface border-border">
        <div className="mb-4">
          <div className="text-sm text-text-secondary mb-2">当前模式</div>
          <div className="flex items-center gap-4">
            <div
              className={clsx(
                'px-4 py-2 rounded-lg font-bold text-lg flex items-center gap-2',
                currentMode === 'backtest' && 'bg-blue-500/20 text-blue-400',
                currentMode === 'paper' && 'bg-warning/20 text-warning',
                currentMode === 'live' && 'bg-bearish/20 text-bearish',
              )}
            >
              {modeIcons[currentMode]}
              {modeLabels[currentMode]}
            </div>
            {status?.config.warning && (
              <Alert
                type={currentMode === 'live' ? 'error' : 'warning'}
                message={status.config.warning}
                showIcon
                className="flex-1"
              />
            )}
          </div>
        </div>

        <Divider />

        <div className="mb-4">
          <div className="text-sm text-text-secondary mb-3">模式配置</div>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 bg-background rounded-lg border border-border">
              <div className="text-xs text-text-tertiary mb-1">市场数据</div>
              <div className="text-sm font-medium text-text-primary">
                {status?.config.market_data_source === 'real' ? '真实行情' : '历史数据'}
              </div>
            </div>
            <div className="p-3 bg-background rounded-lg border border-border">
              <div className="text-xs text-text-tertiary mb-1">订单执行</div>
              <div className="text-sm font-medium text-text-primary">
                {status?.config.order_execution === 'real' ? '真实下单' : '模拟下单'}
              </div>
            </div>
            <div className="p-3 bg-background rounded-lg border border-border">
              <div className="text-xs text-text-tertiary mb-1">风控引擎</div>
              <div className="text-sm font-medium text-text-primary">
                {status?.config.risk_engine === 'real' ? '真实风控' : '模拟风控'}
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card className="bg-surface border-border" title={<span className="text-sm font-medium">切换模式</span>}>
        {modes.length === 0 ? (
          <Empty description="暂无模式数据" />
        ) : (
          <div className="space-y-4">
            <Radio.Group
              value={selectedMode || currentMode}
              onChange={(e) => handleModeSelect(e.target.value)}
              className="w-full"
            >
              <div className="grid grid-cols-3 gap-4">
                {modes.map((mode) => (
                  <div
                    key={mode.mode}
                    className={clsx(
                      'p-4 rounded-lg border-2 cursor-pointer transition-all',
                      (selectedMode === mode.mode || mode.is_current)
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50',
                    )}
                    onClick={() => handleModeSelect(mode.mode)}
                  >
                    <Radio value={mode.mode} className="hidden" />
                    <div className="flex items-center gap-2 mb-2">
                      <div style={{ color: mode.config.color }}>
                        {modeIcons[mode.mode]}
                      </div>
                      <span className="font-medium text-text-primary">
                        {modeLabels[mode.mode]}
                      </span>
                      {mode.is_current && (
                        <Tag color="green" className="ml-auto">当前</Tag>
                      )}
                    </div>
                    <div className="text-xs text-text-secondary space-y-1">
                      <div>市场: {mode.config.market_data_source}</div>
                      <div>执行: {mode.config.order_execution}</div>
                      <div>风控: {mode.config.risk_engine}</div>
                    </div>
                    {mode.config.warning && (
                      <div className="mt-2 text-xs text-warning">
                        {mode.config.warning}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Radio.Group>

            {selectedMode && selectedMode !== currentMode && (
              <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                <div className="flex items-center gap-2">
                  <ArrowRight className="w-4 h-4 text-primary" />
                  <span className="text-sm">
                    切换到 <strong>{modeLabels[selectedMode]}</strong> 模式
                  </span>
                </div>
                <Button
                  type="primary"
                  onClick={() => handleTransition(false)}
                  loading={transitioning}
                  danger={selectedMode === 'live'}
                >
                  {modes.find(m => m.mode === selectedMode)?.config.require_confirmation
                    ? '确认切换'
                    : '切换'}
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      <Card className="bg-surface border-border" title={<span className="text-sm font-medium">Portfolio 隔离</span>}>
        <div className="grid grid-cols-3 gap-4">
          {modes.map((mode) => {
            const balance = mode.portfolio.balance
            const balanceValue = Object.entries(balance).reduce(
              (sum, [_, val]) => sum + (typeof val === 'number' ? val : 0),
              0
            )
            return (
              <div key={mode.mode} className="p-3 bg-background rounded-lg border border-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-tertiary">{modeLabels[mode.mode]}</span>
                  {mode.is_current && <CheckCircle className="w-4 h-4 text-bullish" />}
                </div>
                <div className="text-lg font-bold text-text-primary">
                  ${balanceValue.toLocaleString()}
                </div>
                <div className="text-xs text-text-secondary">
                  {Object.keys(mode.portfolio.positions).length} 持仓
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <Card className="bg-surface border-border" title={<span className="text-sm font-medium">安全检查</span>}>
        <div className="flex items-center gap-4">
          {status?.is_safe_to_trade[0] ? (
            <>
              <CheckCircle className="w-6 h-6 text-bullish" />
              <div>
                <div className="text-sm font-medium text-bullish">系统安全</div>
                <div className="text-xs text-text-secondary">{status.is_safe_to_trade[1]}</div>
              </div>
            </>
          ) : (
            <>
              <AlertTriangle className="w-6 h-6 text-warning" />
              <div>
                <div className="text-sm font-medium text-warning">需要检查</div>
                <div className="text-xs text-text-secondary">{status?.is_safe_to_trade[1]}</div>
              </div>
            </>
          )}
        </div>
      </Card>

      <Modal
        title="确认切换到 LIVE 模式"
        open={confirmModalVisible}
        onCancel={() => setConfirmModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setConfirmModalVisible(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            danger
            loading={transitioning}
            onClick={() => handleTransition(true)}
          >
            确认切换到 LIVE
          </Button>,
        ]}
      >
        <Alert
          type="error"
          message="⚠️ 警告"
          description="切换到 LIVE 模式将启用真实交易！系统将连接真实交易所并执行真实订单。请确保您已充分测试策略并了解相关风险。"
          showIcon
          className="mb-4"
        />
        <div className="text-sm text-text-secondary">
          <p>切换后：</p>
          <ul className="list-disc list-inside mt-2 space-y-1">
            <li>市场数据: 真实行情</li>
            <li>订单执行: 真实下单</li>
            <li>风控引擎: 真实风控</li>
            <li>Portfolio: 独立隔离</li>
          </ul>
        </div>
      </Modal>
    </div>
  )
}
