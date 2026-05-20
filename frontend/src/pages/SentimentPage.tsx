import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Progress, Statistic, Select, Button, Spin, Empty, Timeline } from 'antd'
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  RefreshCw,
  Minus,
  Gauge,
  Radio,
  DollarSign,
  Flame,
  MessageSquare,
  Newspaper,
  Twitter,
} from 'lucide-react'
import { api } from '../services/api/client'
import clsx from 'clsx'
import { isMockMode } from '../config/mock'

interface SentimentSource {
  source: 'twitter' | 'telegram' | 'news' | 'funding' | 'liquidation' | 'reddit'
  sentiment: number
  velocity: number
  volume: number
  trend: 'rising' | 'falling' | 'stable'
}

interface SentimentState {
  symbol: string
  overall_sentiment: 'EXTREME_GREED' | 'GREED' | 'NEUTRAL' | 'FEAR' | 'EXTREME_FEAR'
  sentiment_score: number
  fear_greed_index: number
  social_velocity: 'HIGH' | 'MODERATE' | 'LOW'
  panic_index: number
  euphoria_index: number
  sources: SentimentSource[]
  history: SentimentHistoryPoint[]
  last_updated: string
}

interface SentimentHistoryPoint {
  timestamp: string
  sentiment: number
  fear_greed: number
}

interface SentimentSignal {
  signal_id: string
  type: 'long_opportunity' | 'short_opportunity' | 'panic_reversal' | 'euphoria_warning'
  description: string
  confidence: number
  triggers: string[]
  symbol: string
}

const sentimentConfig = {
  EXTREME_GREED: { color: 'bg-green-500 text-white', label: '极度贪婪', position: 100 },
  GREED: { color: 'bg-green-400 text-white', label: '贪婪', position: 75 },
  NEUTRAL: { color: 'bg-gray-400 text-white', label: '中性', position: 50 },
  FEAR: { color: 'bg-orange-400 text-white', label: '恐惧', position: 25 },
  EXTREME_FEAR: { color: 'bg-red-500 text-white', label: '极度恐惧', position: 0 },
}

const velocityConfig = {
  HIGH: { color: 'text-bullish', icon: TrendingUp, label: '高' },
  MODERATE: { color: 'text-warning', icon: Activity, label: '中' },
  LOW: { color: 'text-neutral', icon: Minus, label: '低' },
}

const sourceConfig = {
  twitter: { color: 'bg-blue-500/20 text-blue-400', icon: Twitter, label: 'Twitter/X' },
  telegram: { color: 'bg-cyan-500/20 text-cyan-400', icon: MessageSquare, label: 'Telegram' },
  news: { color: 'bg-purple-500/20 text-purple-400', icon: Newspaper, label: '新闻' },
  funding: { color: 'bg-orange-500/20 text-orange-400', icon: DollarSign, label: 'Funding' },
  liquidation: { color: 'bg-red-500/20 text-red-400', icon: Flame, label: '爆仓' },
  reddit: { color: 'bg-orange-400/20 text-orange-300', icon: MessageSquare, label: 'Reddit' },
}

const signalConfig = {
  long_opportunity: { color: 'bg-bullish/20 text-bullish border-bullish/30', icon: TrendingUp, label: '做多机会' },
  short_opportunity: { color: 'bg-bearish/20 text-bearish border-bearish/30', icon: TrendingDown, label: '做空机会' },
  panic_reversal: { color: 'bg-primary/20 text-primary border-primary/30', icon: AlertTriangle, label: '恐慌反转' },
  euphoria_warning: { color: 'bg-warning/20 text-warning border-warning/30', icon: Gauge, label: '贪婪预警' },
}

const mockSentiment: SentimentState = {
  symbol: 'BTCUSDT',
  overall_sentiment: 'GREED',
  sentiment_score: 0.72,
  fear_greed_index: 81,
  social_velocity: 'HIGH',
  panic_index: 0.15,
  euphoria_index: 0.68,
  sources: [
    { source: 'twitter', sentiment: 0.78, velocity: 0.85, volume: 125000, trend: 'rising' },
    { source: 'telegram', sentiment: 0.65, velocity: 0.42, volume: 45000, trend: 'stable' },
    { source: 'news', sentiment: 0.72, velocity: 0.55, volume: 3200, trend: 'rising' },
    { source: 'funding', sentiment: 0.58, velocity: 0.32, volume: 1, trend: 'falling' },
    { source: 'liquidation', sentiment: 0.25, velocity: 0.15, volume: 85000000, trend: 'stable' },
    { source: 'reddit', sentiment: 0.70, velocity: 0.48, volume: 28000, trend: 'rising' },
  ],
  history: [
    { timestamp: '2024-01-15T10:00:00Z', sentiment: 0.45, fear_greed: 52 },
    { timestamp: '2024-01-15T11:00:00Z', sentiment: 0.52, fear_greed: 58 },
    { timestamp: '2024-01-15T12:00:00Z', sentiment: 0.58, fear_greed: 65 },
    { timestamp: '2024-01-15T13:00:00Z', sentiment: 0.65, fear_greed: 72 },
    { timestamp: '2024-01-15T14:00:00Z', sentiment: 0.72, fear_greed: 81 },
  ],
  last_updated: '2024-01-15T14:30:00Z',
}

const mockSignals: SentimentSignal[] = [
  {
    signal_id: 's1',
    type: 'short_opportunity',
    description: '情绪过热 + Funding 极端 + OI 扩张',
    confidence: 0.75,
    triggers: ['euphoria_high', 'funding_extreme', 'oi_expansion'],
    symbol: 'BTCUSDT',
  },
  {
    signal_id: 's2',
    type: 'panic_reversal',
    description: '恐慌情绪 + 爆仓链',
    confidence: 0.68,
    triggers: ['panic_detected', 'liquidation_cascade'],
    symbol: 'ETHUSDT',
  },
]

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']

export function SentimentPage() {
  const [loading, setLoading] = useState(true)
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTCUSDT')
  const [sentiment, setSentiment] = useState<SentimentState | null>(null)
  const [signals, setSignals] = useState<SentimentSignal[]>([])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [selectedSymbol])

  const loadData = async () => {
    setLoading(true)
    if (isMockMode) {
      setSentiment(mockSentiment)
      setSignals(mockSignals)
      setLoading(false)
      return
    }

    try {
      const [sentimentRes, signalsRes] = await Promise.all([
        api.get(`/sentiment/current?symbol=${selectedSymbol}`),
        api.get(`/sentiment/signals?symbol=${selectedSymbol}`),
      ])
      if (sentimentRes.data) {
        setSentiment(sentimentRes.data)
      }
      if (signalsRes.data && Array.isArray(signalsRes.data)) {
        setSignals(signalsRes.data)
      }
    } catch (error) {
      console.error('Failed to load sentiment data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  const sentimentCfg = sentiment ? sentimentConfig[sentiment.overall_sentiment] : sentimentConfig.NEUTRAL
  const velocityCfg = sentiment ? velocityConfig[sentiment.social_velocity] : velocityConfig.LOW
  const VelocityIcon = velocityCfg.icon

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">市场情绪</h1>
          <p className="text-text-secondary text-sm mt-1">市场情绪分析 - 市场现在情绪如何</p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            className="w-32"
            options={SYMBOLS.map((s) => ({ value: s, label: s }))}
          />
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={loadData}>刷新</Button>
        </div>
      </div>

      {sentiment && (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={6}>
              <Card className="bg-surface border-border h-full">
                <div className="text-center">
                  <div className="text-xs text-text-secondary mb-2">整体情绪</div>
                  <Tag className={clsx('text-lg px-4 py-2 border-0', sentimentCfg.color)}>
                    {sentimentCfg.label}
                  </Tag>
                  <div className="mt-3">
                    <div className={clsx(
                      'text-3xl font-bold',
                      sentiment.sentiment_score > 0.6 ? 'text-bullish' : sentiment.sentiment_score < 0.4 ? 'text-bearish' : 'text-neutral'
                    )}>
                      {sentiment.sentiment_score > 0.5 ? '+' : ''}{((sentiment.sentiment_score - 0.5) * 2).toFixed(2)}
                    </div>
                    <div className="text-xs text-text-secondary mt-1">情绪得分</div>
                  </div>
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <Card className="bg-surface border-border h-full">
                <div className="text-center">
                  <div className="text-xs text-text-secondary mb-2">Fear & Greed Index</div>
                  <div className="relative w-32 h-16 mx-auto">
                    <div className="absolute inset-0 rounded-full overflow-hidden" style={{ background: 'linear-gradient(to right, #EF4444, #F59E0B, #10B981)' }}>
                      <div className="absolute inset-0 bg-surface" style={{ clipPath: `inset(0 0 0 ${sentiment.fear_greed_index}%)` }} />
                    </div>
                    <div 
                      className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full border-2 border-text-primary shadow-lg"
                      style={{ left: `${sentiment.fear_greed_index}%`, transform: 'translateX(-50%) translateY(-50%)' }}
                    />
                  </div>
                  <div className="text-3xl font-bold text-text-primary mt-2">
                    {sentiment.fear_greed_index}
                  </div>
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <Card className="bg-surface border-border h-full">
                <div className="text-center">
                  <div className="text-xs text-text-secondary mb-2">社交活跃度</div>
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <VelocityIcon className={clsx('w-5 h-5', velocityCfg.color)} />
                    <Tag className={clsx('text-sm border-0', velocityCfg.color === 'text-bullish' ? 'bg-bullish/20 text-bullish' : velocityCfg.color === 'text-warning' ? 'bg-warning/20 text-warning' : 'bg-neutral/20 text-neutral')}>
                      {velocityCfg.label}
                    </Tag>
                  </div>
                  <div className="text-xs text-text-secondary mt-4">情绪变化速度往往比价格还领先</div>
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <Card className="bg-surface border-border h-full">
                <div className="space-y-4">
                  <div>
                    <div className="text-xs text-text-secondary mb-1">恐慌指数</div>
                    <Progress
                      percent={sentiment.panic_index * 100}
                      showInfo={false}
                      size="small"
                      strokeColor="#EF4444"
                    />
                    <div className="text-sm font-medium text-bearish mt-1">
                      {(sentiment.panic_index * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-secondary mb-1">贪婪指数</div>
                    <Progress
                      percent={sentiment.euphoria_index * 100}
                      showInfo={false}
                      size="small"
                      strokeColor="#10B981"
                    />
                    <div className="text-sm font-medium text-bullish mt-1">
                      {(sentiment.euphoria_index * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={16}>
              <Card className="bg-surface border-border" title={<span className="text-sm font-medium">情绪来源分析</span>}>
                <Row gutter={[16, 16]}>
                  {sentiment.sources.map((source) => {
                    const cfg = sourceConfig[source.source]
                    const Icon = cfg.icon
                    return (
                      <Col xs={24} sm={12} md={8} key={source.source}>
                        <div className="p-3 bg-background rounded-lg border border-border">
                          <div className="flex items-center gap-2 mb-3">
                            <Icon className="w-4 h-4" />
                            <span className="text-sm font-medium text-text-primary">{cfg.label}</span>
                            <Tag className={clsx(
                              'text-[10px] border-0 ml-auto',
                              source.trend === 'rising' ? 'bg-bullish/20 text-bullish' : source.trend === 'falling' ? 'bg-bearish/20 text-bearish' : 'bg-neutral/20 text-neutral'
                            )}>
                              {source.trend === 'rising' ? '↑' : source.trend === 'falling' ? '↓' : '→'}
                            </Tag>
                          </div>
                          <div className="space-y-2">
                            <div>
                              <div className="text-[10px] text-text-secondary">情绪值</div>
                              <Progress
                                percent={source.sentiment * 100}
                                showInfo={false}
                                size="small"
                                strokeColor={source.sentiment > 0.6 ? '#10B981' : source.sentiment < 0.4 ? '#EF4444' : '#6B7280'}
                              />
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-text-secondary">速度</span>
                              <span className="text-text-primary">{(source.velocity * 100).toFixed(0)}%</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-text-secondary">量</span>
                              <span className="text-text-primary">
                                {source.volume > 1000000 ? `${(source.volume / 1000000).toFixed(1)}M` : source.volume > 1000 ? `${(source.volume / 1000).toFixed(1)}K` : source.volume}
                              </span>
                            </div>
                          </div>
                        </div>
                      </Col>
                    )
                  })}
                </Row>
              </Card>
            </Col>

            <Col xs={24} lg={8}>
              <Card className="bg-surface border-border" title={<span className="text-sm font-medium">情绪 + 行为 联动信号</span>}>
                {signals.length === 0 ? (
                  <div className="py-8 text-center text-xs text-text-secondary">暂无联动信号</div>
                ) : (
                  <div className="space-y-3">
                    {signals.map((signal) => {
                      const cfg = signalConfig[signal.type]
                      const Icon = cfg.icon
                      return (
                        <div key={signal.signal_id} className="p-3 bg-background rounded-lg border border-border">
                          <div className="flex items-center gap-2 mb-2">
                            <Icon className="w-4 h-4" />
                            <Tag className={clsx('text-[10px] border', cfg.color)}>
                              {cfg.label}
                            </Tag>
                          </div>
                          <div className="text-xs text-text-primary mb-2">{signal.description}</div>
                          <div className="flex items-center justify-between">
                            <div className="flex flex-wrap gap-1">
                              {signal.triggers.slice(0, 2).map((t) => (
                                <Tag key={t} className="text-[10px] bg-border/50 text-text-secondary border-0">
                                  {t}
                                </Tag>
                              ))}
                            </div>
                            <span className="text-xs text-primary font-medium">
                              {(signal.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </Card>

              <Card className="bg-surface border-border mt-4" title={<span className="text-sm font-medium">情绪演变</span>}>
                {sentiment.history.length === 0 ? (
                  <div className="py-4 text-center text-xs text-text-secondary">暂无历史数据</div>
                ) : (
                  <div className="space-y-2">
                    {sentiment.history.map((point, i) => {
                      const isLast = i === sentiment.history.length - 1
                      return (
                        <div key={point.timestamp} className="flex items-center gap-3">
                          <div className="w-16 text-[10px] text-text-secondary">
                            {new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                          <div className="flex-1">
                            <Progress
                              percent={point.fear_greed}
                              showInfo={false}
                              size="small"
                              strokeColor={point.fear_greed > 70 ? '#10B981' : point.fear_greed < 30 ? '#EF4444' : '#F59E0B'}
                            />
                          </div>
                          <div className={clsx(
                            'w-8 text-right text-xs font-medium',
                            point.fear_greed > 70 ? 'text-bullish' : point.fear_greed < 30 ? 'text-bearish' : 'text-warning'
                          )}>
                            {point.fear_greed}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}

      {!sentiment && !loading && (
        <Card className="bg-surface border-border">
          <Empty description="暂无情绪数据" />
        </Card>
      )}
    </div>
  )
}
