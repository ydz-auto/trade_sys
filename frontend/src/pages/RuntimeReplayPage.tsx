import { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Tag, Button, Slider, Select, Progress, Statistic, Badge, Tooltip, Spin, Empty, Timeline } from 'antd'
import {
  History,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Clock,
  Activity,
  Zap,
  Target,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Radio,
  ChevronRight,
  RefreshCw,
  Layers,
  BarChart3,
  DollarSign,
  Flame,
  Waves,
  Gauge,
} from 'lucide-react'
import {
  useRuntime,
  useRuntimeState,
} from '../services/runtime'
import { api } from '../services/api/client'
import clsx from 'clsx'
import { isMockMode } from '../config/mock'

interface MarketStateEvent {
  event_id: string
  timestamp: string
  layer: 'market'
  type: 'volatility_spike' | 'funding_extreme' | 'oi_collapse' | 'price_action' | 'liquidity_change'
  title: string
  description: string
  data: {
    symbol: string
    volatility?: number
    funding_rate?: number
    oi_change?: number
    price_change?: number
    liquidity?: number
  }
}

interface BehaviourEvent {
  event_id: string
  timestamp: string
  layer: 'behaviour'
  type: 'liquidation_cascade' | 'panic_selling' | 'whale_sweep' | 'imbalance_flip' | 'momentum_shift'
  title: string
  description: string
  data: {
    direction: 'bullish' | 'bearish'
    magnitude: number
    affected_symbols: string[]
    trigger: string
  }
}

interface FeatureEvent {
  event_id: string
  timestamp: string
  layer: 'feature'
  type: 'feature_change'
  title: string
  description: string
  data: {
    feature_name: string
    old_value: number
    new_value: number
    zscore: number
    contribution: number
  }
}

interface StrategyEvent {
  event_id: string
  timestamp: string
  layer: 'strategy'
  type: 'signal_triggered' | 'confidence_change' | 'position_update'
  title: string
  description: string
  data: {
    strategy_id: string
    strategy_name: string
    action: 'ENTER' | 'EXIT' | 'HOLD'
    confidence: number
    trigger_conditions: string[]
  }
}

interface ExecutionEvent {
  event_id: string
  timestamp: string
  layer: 'execution'
  type: 'order_created' | 'order_filled' | 'order_rejected' | 'position_opened' | 'position_closed'
  title: string
  description: string
  data: {
    order_id: string
    symbol: string
    side: 'buy' | 'sell'
    quantity: number
    price: number
    status: string
  }
}

interface RiskEvent {
  event_id: string
  timestamp: string
  layer: 'risk'
  type: 'risk_check' | 'limit_breach' | 'drawdown_alert'
  title: string
  description: string
  data: {
    risk_type: string
    current_value: number
    limit: number
    action_taken: string
  }
}

interface PnLEvent {
  event_id: string
  timestamp: string
  layer: 'pnl'
  type: 'pnl_update'
  title: string
  description: string
  data: {
    unrealized: number
    realized: number
    total: number
    pnl_pct: number
  }
}

type ReplayEvent = MarketStateEvent | BehaviourEvent | FeatureEvent | StrategyEvent | ExecutionEvent | RiskEvent | PnLEvent

interface ReplaySession {
  session_id: string
  start_time: string
  end_time: string
  symbol: string
  strategy: string
  events: ReplayEvent[]
  outcome: {
    pnl: number
    win: boolean
    duration_seconds: number
    max_drawdown: number
    sharpe: number
  }
}

const layerConfig = {
  market: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: BarChart3, label: '市场状态', order: 1 },
  behaviour: { color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', icon: Zap, label: '行为检测', order: 2 },
  feature: { color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30', icon: Activity, label: '特征变化', order: 3 },
  strategy: { color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: Target, label: '策略触发', order: 4 },
  execution: { color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', icon: Radio, label: '执行', order: 5 },
  risk: { color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertTriangle, label: '风险', order: 6 },
  pnl: { color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', icon: DollarSign, label: '盈亏', order: 7 },
}

const behaviourTypeConfig = {
  liquidation_cascade: { color: 'text-red-400', icon: Flame, label: '爆仓链' },
  panic_selling: { color: 'text-red-300', icon: AlertTriangle, label: '恐慌抛售' },
  whale_sweep: { color: 'text-purple-400', icon: Waves, label: '鲸鱼扫单' },
  imbalance_flip: { color: 'text-yellow-400', icon: Gauge, label: '失衡翻转' },
  momentum_shift: { color: 'text-blue-400', icon: TrendingUp, label: '动量转换' },
}

const mockSession: ReplaySession = {
  session_id: 'replay_001',
  start_time: '2024-01-15T14:00:00Z',
  end_time: '2024-01-15T14:30:00Z',
  symbol: 'BTCUSDT',
  strategy: 'Panic Reversal',
  events: [
    {
      event_id: 'e1',
      timestamp: '2024-01-15T14:01:00Z',
      layer: 'market',
      type: 'volatility_spike',
      title: 'BTC 波动率飙升',
      description: '15分钟波动率从 2.1% 升至 8.7%',
      data: { symbol: 'BTCUSDT', volatility: 8.7 },
    },
    {
      event_id: 'e2',
      timestamp: '2024-01-15T14:02:30Z',
      layer: 'market',
      type: 'funding_extreme',
      title: '资金费率极端',
      description: 'Funding Rate 达到 -0.05%，做空极度拥挤',
      data: { symbol: 'BTCUSDT', funding_rate: -0.05 },
    },
    {
      event_id: 'e3',
      timestamp: '2024-01-15T14:03:00Z',
      layer: 'market',
      type: 'oi_collapse',
      title: '持仓量崩塌',
      description: 'OI 在 2 分钟内下降 23%',
      data: { symbol: 'BTCUSDT', oi_change: -23 },
    },
    {
      event_id: 'e4',
      timestamp: '2024-01-15T14:03:30Z',
      layer: 'behaviour',
      type: 'liquidation_cascade',
      title: '爆仓链触发',
      description: '检测到多头爆仓连锁反应',
      data: { direction: 'bearish', magnitude: 0.85, affected_symbols: ['BTCUSDT', 'ETHUSDT'], trigger: 'price_drop' },
    },
    {
      event_id: 'e5',
      timestamp: '2024-01-15T14:04:00Z',
      layer: 'behaviour',
      type: 'panic_selling',
      title: '恐慌抛售',
      description: '市场情绪转为恐慌，卖出压力剧增',
      data: { direction: 'bearish', magnitude: 0.72, affected_symbols: ['BTCUSDT'], trigger: 'liquidation' },
    },
    {
      event_id: 'e6',
      timestamp: '2024-01-15T14:04:30Z',
      layer: 'behaviour',
      type: 'imbalance_flip',
      title: '订单失衡翻转',
      description: '买卖失衡从 -0.6 翻转至 +0.4',
      data: { direction: 'bullish', magnitude: 0.4, affected_symbols: ['BTCUSDT'], trigger: 'rebound' },
    },
    {
      event_id: 'e7',
      timestamp: '2024-01-15T14:05:00Z',
      layer: 'feature',
      type: 'feature_change',
      title: '情绪因子反转',
      description: 'Fear & Greed 从 28 升至 45',
      data: { feature_name: 'sentiment', old_value: 28, new_value: 45, zscore: 2.1, contribution: 0.25 },
    },
    {
      event_id: 'e8',
      timestamp: '2024-01-15T14:05:30Z',
      layer: 'strategy',
      type: 'signal_triggered',
      title: 'Panic Reversal 触发',
      description: '策略检测到恐慌反转信号',
      data: { strategy_id: 'panic_reversal', strategy_name: 'Panic Reversal', action: 'ENTER', confidence: 0.84, trigger_conditions: ['funding_extreme', 'liquidation_cascade', 'imbalance_flip'] },
    },
    {
      event_id: 'e9',
      timestamp: '2024-01-15T14:06:00Z',
      layer: 'execution',
      type: 'order_created',
      title: '创建入场订单',
      description: 'LIMIT BUY 0.5 BTC @ 42,150',
      data: { order_id: 'ord_001', symbol: 'BTCUSDT', side: 'buy', quantity: 0.5, price: 42150, status: 'pending' },
    },
    {
      event_id: 'e10',
      timestamp: '2024-01-15T14:06:30Z',
      layer: 'execution',
      type: 'order_filled',
      title: '订单成交',
      description: 'BUY 0.5 BTC @ 42,120 成交',
      data: { order_id: 'ord_001', symbol: 'BTCUSDT', side: 'buy', quantity: 0.5, price: 42120, status: 'filled' },
    },
    {
      event_id: 'e11',
      timestamp: '2024-01-15T14:10:00Z',
      layer: 'pnl',
      type: 'pnl_update',
      title: '盈亏更新',
      description: '未实现盈亏 +$520',
      data: { unrealized: 520, realized: 0, total: 520, pnl_pct: 2.47 },
    },
    {
      event_id: 'e12',
      timestamp: '2024-01-15T14:15:00Z',
      layer: 'pnl',
      type: 'pnl_update',
      title: '盈亏更新',
      description: '未实现盈亏 +$1,240',
      data: { unrealized: 1240, realized: 0, total: 1240, pnl_pct: 5.89 },
    },
    {
      event_id: 'e13',
      timestamp: '2024-01-15T14:20:00Z',
      layer: 'strategy',
      type: 'signal_triggered',
      title: '止盈信号触发',
      description: '达到目标盈亏，建议离场',
      data: { strategy_id: 'panic_reversal', strategy_name: 'Panic Reversal', action: 'EXIT', confidence: 0.91, trigger_conditions: ['target_reached', 'momentum_exhaustion'] },
    },
    {
      event_id: 'e14',
      timestamp: '2024-01-15T14:21:00Z',
      layer: 'execution',
      type: 'position_closed',
      title: '平仓完成',
      description: 'SELL 0.5 BTC @ 43,500',
      data: { order_id: 'ord_002', symbol: 'BTCUSDT', side: 'sell', quantity: 0.5, price: 43500, status: 'filled' },
    },
    {
      event_id: 'e15',
      timestamp: '2024-01-15T14:22:00Z',
      layer: 'pnl',
      type: 'pnl_update',
      title: '最终盈亏',
      description: '已实现盈亏 +$1,380',
      data: { unrealized: 0, realized: 1380, total: 1380, pnl_pct: 6.55 },
    },
  ],
  outcome: {
    pnl: 1380,
    win: true,
    duration_seconds: 1320,
    max_drawdown: 0.8,
    sharpe: 2.1,
  },
}

export function RuntimeReplayPage() {
  const { isConnected } = useRuntime()
  const replayState = useRuntimeState('replay')

  const [sessions, setSessions] = useState<ReplaySession[]>([])
  const [selectedSession, setSelectedSession] = useState<ReplaySession | null>(null)
  const [currentEventIndex, setCurrentEventIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [loading, setLoading] = useState(true)
  const [activeLayer, setActiveLayer] = useState<string | null>(null)
  const playIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    loadSessions()
  }, [])

  useEffect(() => {
    if (isPlaying && selectedSession) {
      playIntervalRef.current = setInterval(() => {
        setCurrentEventIndex((prev) => {
          if (prev >= selectedSession.events.length - 1) {
            setIsPlaying(false)
            return prev
          }
          return prev + 1
        })
      }, 1000 / playbackSpeed)
    } else {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current)
      }
    }
    return () => {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current)
      }
    }
  }, [isPlaying, playbackSpeed, selectedSession])

  const loadSessions = async () => {
    setLoading(true)
    if (isMockMode) {
      setSessions([mockSession])
      setSelectedSession(mockSession)
      setLoading(false)
      return
    }

    try {
      const res = await api.get('/replay/sessions')
      if (res.data && Array.isArray(res.data)) {
        setSessions(res.data)
        if (res.data.length > 0) {
          setSelectedSession(res.data[0])
        }
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePlayPause = () => setIsPlaying(!isPlaying)
  const handleStepForward = () => {
    if (selectedSession && currentEventIndex < selectedSession.events.length - 1) {
      setCurrentEventIndex(currentEventIndex + 1)
    }
  }
  const handleStepBack = () => {
    if (currentEventIndex > 0) setCurrentEventIndex(currentEventIndex - 1)
  }
  const handleReset = () => {
    setCurrentEventIndex(0)
    setIsPlaying(false)
  }

  const formatTime = (timestamp: string) => new Date(timestamp).toLocaleTimeString()
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分 ${secs}秒`
  }

  const getEventsByLayer = (layer: string) => {
    if (!selectedSession) return []
    return selectedSession.events.filter(e => e.layer === layer)
  }

  const getCurrentPnL = () => {
    if (!selectedSession) return { unrealized: 0, realized: 0, total: 0 }
    const pnlEvents = selectedSession.events.slice(0, currentEventIndex + 1).filter(e => e.layer === 'pnl') as PnLEvent[]
    if (pnlEvents.length === 0) return { unrealized: 0, realized: 0, total: 0 }
    return pnlEvents[pnlEvents.length - 1].data
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  const currentPnL = getCurrentPnL()
  const filteredEvents = activeLayer 
    ? selectedSession?.events.filter(e => e.layer === activeLayer) || []
    : selectedSession?.events || []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Runtime Replay</h1>
          <p className="text-text-secondary text-sm mt-1">
            市场事件 → 特征 → 行为 → 策略 → 执行 全链路回放
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedSession?.session_id}
            onChange={(v) => {
              const session = sessions.find((s) => s.session_id === v)
              setSelectedSession(session || null)
              setCurrentEventIndex(0)
              setIsPlaying(false)
            }}
            className="w-64"
            options={sessions.map((s) => ({
              value: s.session_id,
              label: `${s.symbol} - ${s.strategy} (${new Date(s.start_time).toLocaleDateString()})`,
            }))}
          />
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={loadSessions}>刷新</Button>
        </div>
      </div>

      {selectedSession && (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">品种 / 策略</span>}
                  value={`${selectedSession.symbol} / ${selectedSession.strategy}`}
                  valueStyle={{ color: 'var(--text-primary)', fontSize: '16px' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">最终盈亏</span>}
                  value={selectedSession.outcome.pnl}
                  precision={2}
                  prefix={selectedSession.outcome.pnl >= 0 ? '+$' : '-$'}
                  valueStyle={{
                    color: selectedSession.outcome.pnl >= 0 ? 'var(--bullish)' : 'var(--bearish)',
                    fontSize: '20px',
                  }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">最大回撤</span>}
                  value={selectedSession.outcome.max_drawdown}
                  precision={1}
                  suffix="%"
                  valueStyle={{ color: 'var(--warning)', fontSize: '20px' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">Sharpe</span>}
                  value={selectedSession.outcome.sharpe}
                  precision={2}
                  valueStyle={{ color: 'var(--primary)', fontSize: '20px' }}
                />
              </Card>
            </Col>
          </Row>

          <Card className="bg-surface border-border">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-text-secondary">
                  事件 {currentEventIndex + 1} / {selectedSession.events.length}
                </span>
                <span className="text-xs text-text-secondary">
                  {formatTime(selectedSession.events[currentEventIndex]?.timestamp || '')}
                </span>
              </div>
              <Slider
                value={currentEventIndex}
                max={selectedSession.events.length - 1}
                onChange={setCurrentEventIndex}
              />
            </div>

            <div className="flex items-center justify-center gap-4 mb-6">
              <Button icon={<SkipBack className="w-4 h-4" />} onClick={handleReset} />
              <Button icon={<ChevronRight className="w-4 h-4 rotate-180" />} onClick={handleStepBack} />
              <Button
                type="primary"
                size="large"
                icon={isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                onClick={handlePlayPause}
                className="w-16 h-16 rounded-full"
              />
              <Button icon={<ChevronRight className="w-4 h-4" />} onClick={handleStepForward} />
              <Select
                value={playbackSpeed}
                onChange={setPlaybackSpeed}
                className="w-20"
                options={[0.5, 1, 2, 4, 8].map((x) => ({ value: x, label: `${x}x` }))}
              />
            </div>

            <div className="flex gap-2 mb-4 overflow-x-auto">
              <Button 
                type={activeLayer === null ? 'primary' : 'default'} 
                size="small"
                onClick={() => setActiveLayer(null)}
              >
                全部
              </Button>
              {Object.entries(layerConfig).map(([layer, config]) => (
                <Button
                  key={layer}
                  type={activeLayer === layer ? 'primary' : 'default'}
                  size="small"
                  icon={<config.icon className="w-3 h-3" />}
                  onClick={() => setActiveLayer(activeLayer === layer ? null : layer)}
                >
                  {config.label}
                </Button>
              ))}
            </div>

            <Row gutter={[16, 16]}>
              <Col xs={24} lg={8}>
                <Card className="bg-background border-border h-full" title={<span className="text-xs font-medium">当前事件</span>}>
                  {selectedSession.events[currentEventIndex] && (() => {
                    const event = selectedSession.events[currentEventIndex]
                    const config = layerConfig[event.layer]
                    const Icon = config.icon
                    return (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <Tag className={clsx('text-xs border', config.color)}>
                            <Icon className="w-3 h-3 inline mr-1" />
                            {config.label}
                          </Tag>
                        </div>
                        <h4 className="text-sm font-medium text-text-primary">{event.title}</h4>
                        <p className="text-xs text-text-secondary">{event.description}</p>
                        <div className="pt-2 border-t border-border">
                          <div className="text-[10px] text-text-secondary mb-1">事件数据</div>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(event.data).map(([key, value]) => (
                              <Tag key={key} className="text-[10px] bg-border/50 text-text-secondary border-0">
                                {key}: {typeof value === 'number' ? value.toFixed(2) : String(value)}
                              </Tag>
                            ))}
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                </Card>
              </Col>

              <Col xs={24} lg={8}>
                <Card className="bg-background border-border h-full" title={<span className="text-xs font-medium">事件链</span>}>
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {selectedSession.events.slice(0, currentEventIndex + 1).map((event, i) => {
                      const config = layerConfig[event.layer]
                      const Icon = config.icon
                      return (
                        <div
                          key={event.event_id}
                          className={clsx(
                            'p-2 rounded-lg border transition-all cursor-pointer',
                            i === currentEventIndex
                              ? 'border-primary bg-primary/10'
                              : 'border-border bg-surface/50'
                          )}
                          onClick={() => setCurrentEventIndex(i)}
                        >
                          <div className="flex items-center gap-2">
                            <Icon className="w-3 h-3" style={{ color: `var(--${config.color.split(' ')[0].replace('bg-', '').replace('/20', '')})` }} />
                            <span className="text-[10px] text-text-secondary">{formatTime(event.timestamp)}</span>
                            <span className="text-xs text-text-primary truncate flex-1">{event.title}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </Card>
              </Col>

              <Col xs={24} lg={8}>
                <Card className="bg-background border-border h-full" title={<span className="text-xs font-medium">PnL 演变</span>}>
                  <div className="space-y-4">
                    <div>
                      <div className="text-xs text-text-secondary mb-1">未实现盈亏</div>
                      <div className={clsx('text-xl font-bold', currentPnL.unrealized >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {currentPnL.unrealized >= 0 ? '+' : ''}${currentPnL.unrealized.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-text-secondary mb-1">已实现盈亏</div>
                      <div className={clsx('text-xl font-bold', currentPnL.realized >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {currentPnL.realized >= 0 ? '+' : ''}${currentPnL.realized.toFixed(2)}
                      </div>
                    </div>
                    <div className="pt-2 border-t border-border">
                      <div className="text-xs text-text-secondary mb-1">总计</div>
                      <div className={clsx('text-2xl font-bold', currentPnL.total >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {currentPnL.total >= 0 ? '+' : ''}${currentPnL.total.toFixed(2)}
                      </div>
                    </div>
                  </div>
                </Card>
              </Col>
            </Row>
          </Card>

          <Row gutter={[16, 16]}>
            {Object.entries(layerConfig).map(([layer, config]) => {
              const layerEvents = getEventsByLayer(layer)
              const currentLayerEvents = layerEvents.filter(e => {
                const idx = selectedSession.events.findIndex(ev => ev.event_id === e.event_id)
                return idx <= currentEventIndex
              })
              const Icon = config.icon

              return (
                <Col xs={24} md={12} lg={Math.floor(24 / Object.keys(layerConfig).length) as any} key={layer}>
                  <Card 
                    className="bg-surface border-border h-full"
                    title={
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4" />
                        <span className="text-sm font-medium">{config.label}</span>
                        <Badge count={currentLayerEvents.length} className="ml-2" />
                      </div>
                    }
                  >
                    {currentLayerEvents.length === 0 ? (
                      <div className="py-4 text-center text-xs text-text-secondary">暂无事件</div>
                    ) : (
                      <div className="space-y-2">
                        {currentLayerEvents.slice(-3).map((event) => (
                          <div key={event.event_id} className="p-2 bg-background rounded-lg border border-border">
                            <div className="text-xs font-medium text-text-primary">{event.title}</div>
                            <div className="text-[10px] text-text-secondary mt-1">{event.description}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                </Col>
              )
            })}
          </Row>
        </>
      )}

      {!selectedSession && !loading && (
        <Card className="bg-surface border-border">
          <Empty description="暂无回放会话，请先运行策略" />
        </Card>
      )}
    </div>
  )
}
