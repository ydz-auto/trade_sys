import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Progress, Button, Select, Tabs, Badge, Tooltip, Empty, Spin, Statistic } from 'antd'
import {
  Radio,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Zap,
  Shield,
  Activity,
  ChevronRight,
  RefreshCw,
} from 'lucide-react'
import {
  useRuntime,
  useSignalsState,
  useRiskState,
  usePnLState,
} from '../services/runtime'
import { api } from '../services/api/client'
import clsx from 'clsx'

interface StrategyRuntime {
  strategy_id: string
  name: string
  symbol: string
  state: 'ACTIVE' | 'PAUSED' | 'ERROR'
  last_signal: string
  signals_today: number
  win_rate: number
  pnl: number
}

const signalStateConfig = {
  ENTER: {
    color: 'bg-bullish text-background',
    icon: ArrowUpRight,
    label: '入场',
    description: '建议入场',
  },
  HOLD: {
    color: 'bg-warning text-background',
    icon: Minus,
    label: '持有',
    description: '持有观望',
  },
  EXIT: {
    color: 'bg-bearish text-background',
    icon: ArrowDownRight,
    label: '离场',
    description: '建议离场',
  },
  NONE: {
    color: 'bg-neutral text-background',
    icon: Minus,
    label: '无信号',
    description: '无信号',
  },
}

const executionStateConfig = {
  pending: { color: 'text-warning', icon: Clock, label: '待执行' },
  executed: { color: 'text-bullish', icon: CheckCircle, label: '已执行' },
  rejected: { color: 'text-bearish', icon: XCircle, label: '已拒绝' },
  expired: { color: 'text-text-secondary', icon: AlertTriangle, label: '已过期' },
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']

export function RuntimeSignalsPage() {
  const { isConnected } = useRuntime()
  const signalsState = useSignalsState()
  const riskState = useRiskState()
  const pnlState = usePnLState()

  const [runtimes, setRuntimes] = useState<StrategyRuntime[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string>('ALL')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    loadRuntimes()
    const interval = setInterval(loadRuntimes, 3000)
    return () => clearInterval(interval)
  }, [])

  const loadRuntimes = async () => {
    try {
      const runtimesRes = await api.get('/execution/state')
      if (runtimesRes.data && Array.isArray(runtimesRes.data)) {
        setRuntimes(runtimesRes.data)
      }
    } catch (error) {
      console.error('Failed to load runtimes:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const handleRefresh = () => {
    setRefreshing(true)
    loadRuntimes()
  }

  const signals = signalsState?.history || []
  const signalsSummary = signalsState?.summary

  const filteredSignals = selectedSymbol === 'ALL' 
    ? signals 
    : signals.filter(s => s.symbol === selectedSymbol)

  if (loading && !signalsState) {
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
          <h1 className="text-2xl font-bold text-text-primary">运行态信号</h1>
          <p className="text-text-secondary text-sm mt-1">策略运行态信号监控</p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            className="w-32"
            options={[
              { value: 'ALL', label: '全部品种' },
              ...SYMBOLS.map(s => ({ value: s, label: s })),
            ]}
          />
          <Button
            icon={<RefreshCw className={clsx('w-4 h-4', refreshing && 'animate-spin')} />}
            onClick={handleRefresh}
            loading={refreshing}
          >
            刷新
          </Button>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">活跃信号</span>}
              value={signalsSummary?.total || 0}
              prefix={<Radio className="w-4 h-4 text-primary" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">入场信号</span>}
              value={signalsSummary?.long || 0}
              prefix={<TrendingUp className="w-4 h-4 text-bullish" />}
              valueStyle={{ color: 'var(--bullish)' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">平均置信度</span>}
              value={signalsSummary?.avgConfidence ? (signalsSummary.avgConfidence * 100).toFixed(0) : 0}
              suffix="%"
              prefix={<Target className="w-4 h-4 text-accent" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">实时信号</span>
              </div>
            }
          >
            <div className="space-y-3">
              {filteredSignals.length === 0 ? (
                <Empty description="暂无信号" />
              ) : (
                filteredSignals.map((signal) => {
                  const config = signalStateConfig[signal.action] || signalStateConfig.NONE
                  const Icon = config.icon
                  return (
                    <div
                      key={signal.signalId}
                      className="p-4 bg-background rounded-lg border border-border hover:border-primary/30 transition-all"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center', config.color)}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-text-primary">{signal.strategyId}</span>
                              <Tag className="text-[10px] bg-primary/10 text-primary border-0">{signal.symbol}</Tag>
                            </div>
                            <div className="text-xs text-text-secondary mt-0.5">{signal.reason}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-text-primary">
                            {(signal.confidence * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-text-secondary">置信度</div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-3 border-t border-border">
                        <div className="flex items-center gap-4 text-xs">
                          <div>
                            <span className="text-text-secondary">时间:</span>{' '}
                            <span className="text-text-primary">{new Date(signal.timestamp).toLocaleTimeString()}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {signal.action === 'BUY' && (
                            <Button type="primary" size="small" icon={<Zap className="w-3 h-3" />}>
                              跟随
                            </Button>
                          )}
                          <Button size="small">详情</Button>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">策略运行态</span>
              </div>
            }
          >
            <div className="space-y-2">
              {runtimes.map((runtime) => (
                <div
                  key={runtime.strategy_id}
                  className="flex items-center justify-between p-3 bg-background rounded-lg border border-border"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={clsx(
                        'w-2 h-2 rounded-full',
                        runtime.state === 'ACTIVE' ? 'bg-bullish' : runtime.state === 'PAUSED' ? 'bg-warning' : 'bg-bearish'
                      )}
                    />
                    <div>
                      <div className="text-sm font-medium text-text-primary">{runtime.name}</div>
                      <div className="text-xs text-text-secondary">{runtime.symbol}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className={clsx('text-sm font-medium', runtime.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {runtime.pnl >= 0 ? '+' : ''}{runtime.pnl.toFixed(2)}%
                      </div>
                      <div className="text-xs text-text-secondary">胜率 {(runtime.win_rate * 100).toFixed(0)}%</div>
                    </div>
                    <Tag className={clsx('text-[10px] border-0', signalStateConfig[runtime.last_signal as keyof typeof signalStateConfig]?.color || 'bg-neutral/20')}>
                      {signalStateConfig[runtime.last_signal as keyof typeof signalStateConfig]?.label || runtime.last_signal}
                    </Tag>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card
            className="bg-surface border-border mt-4"
            title={
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-warning" />
                <span className="text-sm font-medium">风险检查</span>
              </div>
            }
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">仓位限制</span>
                <span className="text-bullish">✓ 正常</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">杠杆上限</span>
                <span className="text-bullish">✓ 正常</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">回撤</span>
                <span className={clsx(riskState?.score && riskState.score > 0.1 ? 'text-warning' : 'text-bullish')}>
                  {riskState?.score ? `⚠ ${(riskState.score * 100).toFixed(1)}%` : '✓ 正常'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">相关性</span>
                <span className="text-bullish">✓ 低</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
