import { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Tag, Button, Slider, Select, Timeline, Progress, Statistic, Badge, Tooltip, Spin } from 'antd'
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
  Settings,
} from 'lucide-react'
import {
  useRuntime,
  useRuntimeState,
} from '../services/runtime'
import { api } from '../services/api/client'
import clsx from 'clsx'

interface ReplayEvent {
  event_id: string
  timestamp: string
  event_type: 'feature' | 'behaviour' | 'signal' | 'execution' | 'risk'
  symbol: string
  title: string
  description: string
  data: Record<string, any>
  impact: 'bullish' | 'bearish' | 'neutral'
}

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
  }
}

const eventTypeConfig = {
  feature: { color: 'bg-primary/20 text-primary', icon: Activity, label: '特征' },
  behaviour: { color: 'bg-accent/20 text-accent', icon: Zap, label: '行为' },
  signal: { color: 'bg-bullish/20 text-bullish', icon: Radio, label: '信号' },
  execution: { color: 'bg-warning/20 text-warning', icon: Target, label: '执行' },
  risk: { color: 'bg-bearish/20 text-bearish', icon: AlertTriangle, label: '风险' },
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

export function RuntimeReplayPage() {
  const { isConnected } = useRuntime()
  const replayState = useRuntimeState('replay')

  const [sessions, setSessions] = useState<ReplaySession[]>([])
  const [selectedSession, setSelectedSession] = useState<ReplaySession | null>(null)
  const [currentEventIndex, setCurrentEventIndex] = useState(replayState?.currentIndex || 0)
  const [isPlaying, setIsPlaying] = useState(replayState?.isPlaying || false)
  const [playbackSpeed, setPlaybackSpeed] = useState(replayState?.playbackSpeed || 1)
  const [loading, setLoading] = useState(true)
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

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying)
  }

  const handleStepForward = () => {
    if (selectedSession && currentEventIndex < selectedSession.events.length - 1) {
      setCurrentEventIndex(currentEventIndex + 1)
    }
  }

  const handleStepBack = () => {
    if (currentEventIndex > 0) {
      setCurrentEventIndex(currentEventIndex - 1)
    }
  }

  const handleReset = () => {
    setCurrentEventIndex(0)
    setIsPlaying(false)
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分 ${secs}秒`
  }

  if (loading && !replayState) {
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
          <h1 className="text-2xl font-bold text-text-primary">运行态回放</h1>
          <p className="text-text-secondary text-sm mt-1">重放市场事件 → 特征 → 信号 → 执行 全链路</p>
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
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={loadSessions}>
            刷新
          </Button>
        </div>
      </div>

      {selectedSession && (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">品种</span>}
                  value={selectedSession.symbol}
                  valueStyle={{ color: 'var(--text-primary)', fontSize: '20px' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">策略</span>}
                  value={selectedSession.strategy}
                  valueStyle={{ color: 'var(--text-primary)', fontSize: '20px' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={6}>
              <Card className="bg-surface border-border">
                <Statistic
                  title={<span className="text-text-secondary text-xs">结果</span>}
                  value={selectedSession.outcome.pnl}
                  precision={2}
                  prefix={selectedSession.outcome.pnl >= 0 ? '+' : ''}
                  suffix=" USDT"
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
                  title={<span className="text-text-secondary text-xs">持续时间</span>}
                  value={formatDuration(selectedSession.outcome.duration_seconds)}
                  valueStyle={{ color: 'var(--text-primary)', fontSize: '20px' }}
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
                tooltip={{ formatter: (v) => selectedSession.events[v || 0]?.title }}
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
                options={[0.5, 1, 2, 4].map((x) => ({ value: x, label: `${x}x` }))}
              />
            </div>

            <Row gutter={[16, 16]}>
              <Col xs={24} lg={12}>
                <div className="p-4 bg-background rounded-lg border border-border">
                  <div className="text-xs text-text-secondary mb-2">当前事件</div>
                  {selectedSession.events[currentEventIndex] && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Tag
                          className={clsx(
                            'text-xs border-0',
                            eventTypeConfig[selectedSession.events[currentEventIndex].event_type].color
                          )}
                        >
                          {eventTypeConfig[selectedSession.events[currentEventIndex].event_type].label}
                        </Tag>
                        <span className="font-medium text-text-primary">
                          {selectedSession.events[currentEventIndex].title}
                        </span>
                      </div>
                      <div className="text-sm text-text-secondary mb-3">
                        {selectedSession.events[currentEventIndex].description}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(selectedSession.events[currentEventIndex].data).map(([key, value]) => (
                          <Tag key={key} className="text-[10px] bg-border text-text-secondary border-0">
                            {key}: {typeof value === 'number' ? value.toFixed(2) : String(value)}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Col>
              <Col xs={24} lg={12}>
                <div className="p-4 bg-background rounded-lg border border-border h-[200px] overflow-y-auto">
                  <div className="text-xs text-text-secondary mb-2">事件时间线</div>
                  <Timeline
                    items={selectedSession.events.slice(0, currentEventIndex + 1).map((event, i) => ({
                      color: i === currentEventIndex ? 'var(--primary)' : 'var(--border)',
                      children: (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-text-secondary">{formatTime(event.timestamp)}</span>
                          <span className="text-xs text-text-primary">{event.title}</span>
                        </div>
                      ),
                    }))}
                  />
                </div>
              </Col>
            </Row>
          </Card>

          <Card className="bg-surface border-border" title={<span className="text-sm font-medium">完整事件链</span>}>
            <div className="flex gap-2 overflow-x-auto pb-2">
              {selectedSession.events.map((event, i) => {
                const config = eventTypeConfig[event.event_type]
                const Icon = config.icon
                return (
                  <Tooltip key={event.event_id} title={event.description}>
                    <div
                      className={clsx(
                        'flex-shrink-0 p-3 rounded-lg border transition-all cursor-pointer',
                        i === currentEventIndex
                          ? 'border-primary bg-primary/10'
                          : i < currentEventIndex
                          ? 'border-border bg-background opacity-60'
                          : 'border-border bg-background opacity-30'
                      )}
                      onClick={() => setCurrentEventIndex(i)}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-3 h-3" />
                        <span className="text-[10px] text-text-secondary">{formatTime(event.timestamp)}</span>
                      </div>
                      <div className="text-xs font-medium text-text-primary truncate max-w-[100px]">{event.title}</div>
                    </div>
                  </Tooltip>
                )
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
