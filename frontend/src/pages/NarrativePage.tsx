import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Progress, Statistic, Badge, Timeline, Select, Button, Spin, Empty } from 'antd'
import {
  Sparkles,
  Brain,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock,
  Activity,
  Newspaper,
  Twitter,
  Globe,
  Zap,
  ChevronRight,
  RefreshCw,
} from 'lucide-react'
import {
  useRuntime,
  useAIState,
} from '../services/runtime'
import { api } from '../services/api/client'
import clsx from 'clsx'

interface Narrative {
  narrative_id: string
  title: string
  category: 'macro' | 'sector' | 'event' | 'technical'
  sentiment: 'bullish' | 'bearish' | 'neutral'
  confidence: number
  impact_score: number
  sources: string[]
  keywords: string[]
  summary: string
  created_at: string
  expires_at: string
}

interface SentimentData {
  overall: number
  news: number
  social: number
  derivatives: number
  trend: 'rising' | 'falling' | 'stable'
}

interface EventIntelligence {
  event_id: string
  title: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  category: string
  description: string
  affected_symbols: string[]
  timestamp: string
  action_required: boolean
}

const categoryConfig = {
  macro: { color: 'bg-primary/20 text-primary', icon: Globe, label: '宏观' },
  sector: { color: 'bg-accent/20 text-accent', icon: Activity, label: '板块' },
  event: { color: 'bg-warning/20 text-warning', icon: Zap, label: '事件' },
  technical: { color: 'bg-bullish/20 text-bullish', icon: TrendingUp, label: '技术' },
}

const severityConfig = {
  critical: { color: 'bg-bearish text-background', icon: AlertTriangle },
  high: { color: 'bg-warning text-background', icon: AlertTriangle },
  medium: { color: 'bg-primary/20 text-primary', icon: Activity },
  low: { color: 'bg-border text-text-secondary', icon: Clock },
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

export function NarrativePage() {
  const { isConnected } = useRuntime()
  const aiState = useAIState()

  const [narratives, setNarratives] = useState<Narrative[]>([])
  const [sentiment, setSentiment] = useState<SentimentData | null>(null)
  const [events, setEvents] = useState<EventIntelligence[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTCUSDT')
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'narrative' | 'sentiment' | 'events'>('narrative')

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [selectedSymbol])

  const loadData = async () => {
    setLoading(true)
    try {
      const [narrativesRes, sentimentRes, eventsRes] = await Promise.all([
        api.get(`/ai/narratives?symbol=${selectedSymbol}`),
        api.get(`/ai/sentiment?symbol=${selectedSymbol}`),
        api.get(`/ai/events?symbol=${selectedSymbol}`),
      ])
      if (narrativesRes.data && Array.isArray(narrativesRes.data)) {
        setNarratives(narrativesRes.data)
      }
      if (sentimentRes.data) {
        setSentiment(sentimentRes.data)
      }
      if (eventsRes.data && Array.isArray(eventsRes.data)) {
        setEvents(eventsRes.data)
      }
    } catch (error) {
      console.error('Failed to load AI data:', error)
    } finally {
      setLoading(false)
    }
  }

  const latestInsight = aiState?.latestInsight
  const recentInsights = aiState?.recentInsights || []

  if (loading && !aiState) {
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
          <h1 className="text-2xl font-bold text-text-primary">AI 智能分析</h1>
          <p className="text-text-secondary text-sm mt-1">叙事分析、情绪监控、事件智能</p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            className="w-32"
            options={SYMBOLS.map((s) => ({ value: s, label: s }))}
          />
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={loadData}>
            刷新
          </Button>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        {(['narrative', 'sentiment', 'events'] as const).map((tab) => (
          <Button
            key={tab}
            type={activeTab === tab ? 'primary' : 'default'}
            onClick={() => setActiveTab(tab)}
            icon={
              tab === 'narrative' ? (
                <Sparkles className="w-4 h-4" />
              ) : tab === 'sentiment' ? (
                <Brain className="w-4 h-4" />
              ) : (
                <MessageSquare className="w-4 h-4" />
              )
            }
          >
            {tab === 'narrative' ? '叙事分析' : tab === 'sentiment' ? '情绪监控' : '事件智能'}
          </Button>
        ))}
      </div>

      {activeTab === 'narrative' && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <div className="space-y-4">
              {latestInsight && (
                <Card className="bg-surface border-border border-primary/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-primary" />
                    <span className="text-xs text-primary font-medium">最新洞察</span>
                  </div>
                  <h3 className="text-lg font-medium text-text-primary mb-2">{latestInsight.title}</h3>
                  <p className="text-sm text-text-secondary mb-3">{latestInsight.content}</p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {latestInsight.relatedSymbols.map((s) => (
                        <Tag key={s} className="text-[10px] bg-primary/10 text-primary border-0">
                          {s}
                        </Tag>
                      ))}
                    </div>
                    <span className="text-xs text-text-secondary">
                      置信度: {(latestInsight.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </Card>
              )}
              {narratives.map((narrative) => {
                const config = categoryConfig[narrative.category]
                const Icon = config.icon
                return (
                  <Card key={narrative.narrative_id} className="bg-surface border-border">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Tag className={clsx('text-[10px] border-0', config.color)}>
                          <Icon className="w-3 h-3 inline mr-1" />
                          {config.label}
                        </Tag>
                        <Tag
                          className={clsx(
                            'text-[10px] border-0',
                            narrative.sentiment === 'bullish'
                              ? 'bg-bullish/20 text-bullish'
                              : narrative.sentiment === 'bearish'
                              ? 'bg-bearish/20 text-bearish'
                              : 'bg-neutral/20 text-neutral'
                          )}
                        >
                          {narrative.sentiment === 'bullish' ? '看涨' : narrative.sentiment === 'bearish' ? '看跌' : '中性'}
                        </Tag>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-text-primary">
                          {(narrative.confidence * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-text-secondary">置信度</div>
                      </div>
                    </div>

                    <h3 className="text-lg font-medium text-text-primary mb-2">{narrative.title}</h3>
                    <p className="text-sm text-text-secondary mb-3">{narrative.summary}</p>

                    <div className="flex items-center gap-2 mb-3">
                      {narrative.keywords.map((kw) => (
                        <Tag key={kw} className="text-[10px] bg-border text-text-secondary border-0">
                          {kw}
                        </Tag>
                      ))}
                    </div>

                    <div className="flex items-center justify-between pt-3 border-t border-border">
                      <div className="flex items-center gap-2">
                        <Newspaper className="w-3 h-3 text-text-secondary" />
                        <span className="text-xs text-text-secondary">
                          来源: {narrative.sources.join(', ')}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Progress
                          percent={narrative.impact_score * 100}
                          showInfo={false}
                          size="small"
                          className="w-16"
                          strokeColor="var(--primary)"
                        />
                        <span className="text-xs text-text-secondary">影响度</span>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          </Col>

          <Col xs={24} lg={8}>
            <Card className="bg-surface border-border" title={<span className="text-sm font-medium">叙事汇总</span>}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">看涨</span>
                  <span className="text-sm font-medium text-bullish">
                    {narratives.filter((n) => n.sentiment === 'bullish').length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">看跌</span>
                  <span className="text-sm font-medium text-bearish">
                    {narratives.filter((n) => n.sentiment === 'bearish').length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">中性</span>
                  <span className="text-sm font-medium text-neutral">
                    {narratives.filter((n) => n.sentiment === 'neutral').length}
                  </span>
                </div>
              </div>
            </Card>

            <Card className="bg-surface border-border mt-4" title={<span className="text-sm font-medium">AI 模型状态</span>}>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">运行状态</span>
                  <span className={clsx('text-xs', aiState?.modelStatus?.isRunning ? 'text-bullish' : 'text-text-secondary')}>
                    {aiState?.modelStatus?.isRunning ? '运行中' : '空闲'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">版本</span>
                  <span className="text-xs text-text-primary">{aiState?.modelStatus?.version || '-'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">最近洞察</span>
                  <span className="text-xs text-text-primary">{recentInsights.length}</span>
                </div>
              </div>
            </Card>
          </Col>
        </Row>
      )}

      {activeTab === 'sentiment' && sentiment && (
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} lg={6}>
            <Card className="bg-surface border-border h-full">
              <Statistic
                title={<span className="text-text-secondary text-xs">整体情绪</span>}
                value={(sentiment.overall * 100).toFixed(0)}
                suffix="%"
                prefix={
                  sentiment.trend === 'rising' ? (
                    <TrendingUp className="w-4 h-4 text-bullish" />
                  ) : sentiment.trend === 'falling' ? (
                    <TrendingDown className="w-4 h-4 text-bearish" />
                  ) : (
                    <Activity className="w-4 h-4 text-neutral" />
                  )
                }
                valueStyle={{
                  color: sentiment.overall > 0.6 ? 'var(--bullish)' : sentiment.overall < 0.4 ? 'var(--bearish)' : 'var(--neutral)',
                  fontSize: '28px',
                }}
              />
              <div className="mt-2 text-xs text-text-secondary">
                {sentiment.trend === 'rising' ? '上升' : sentiment.trend === 'falling' ? '下降' : '稳定'}
              </div>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card className="bg-surface border-border h-full">
              <div className="flex items-center gap-2 mb-2">
                <Newspaper className="w-4 h-4 text-primary" />
                <span className="text-xs text-text-secondary">新闻情绪</span>
              </div>
              <Progress
                percent={sentiment.news * 100}
                strokeColor={sentiment.news > 0.6 ? '#10B981' : sentiment.news < 0.4 ? '#EF4444' : '#6B7280'}
              />
              <div className="text-lg font-bold text-text-primary mt-2">{(sentiment.news * 100).toFixed(0)}%</div>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card className="bg-surface border-border h-full">
              <div className="flex items-center gap-2 mb-2">
                <Twitter className="w-4 h-4 text-accent" />
                <span className="text-xs text-text-secondary">社交媒体情绪</span>
              </div>
              <Progress
                percent={sentiment.social * 100}
                strokeColor={sentiment.social > 0.6 ? '#10B981' : sentiment.social < 0.4 ? '#EF4444' : '#6B7280'}
              />
              <div className="text-lg font-bold text-text-primary mt-2">{(sentiment.social * 100).toFixed(0)}%</div>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card className="bg-surface border-border h-full">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-warning" />
                <span className="text-xs text-text-secondary">衍生品情绪</span>
              </div>
              <Progress
                percent={sentiment.derivatives * 100}
                strokeColor={sentiment.derivatives > 0.6 ? '#10B981' : sentiment.derivatives < 0.4 ? '#EF4444' : '#6B7280'}
              />
              <div className="text-lg font-bold text-text-primary mt-2">{(sentiment.derivatives * 100).toFixed(0)}%</div>
            </Card>
          </Col>
        </Row>
      )}

      {activeTab === 'events' && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card className="bg-surface border-border" title={<span className="text-sm font-medium">事件智能</span>}>
              <div className="space-y-3">
                {events.map((event) => {
                  const config = severityConfig[event.severity]
                  const Icon = config.icon
                  return (
                    <div
                      key={event.event_id}
                      className={clsx(
                        'p-4 rounded-lg border',
                        event.action_required ? 'border-warning/50 bg-warning/5' : 'border-border bg-background'
                      )}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Tag className={clsx('text-[10px] border-0', config.color)}>
                            <Icon className="w-3 h-3 inline mr-1" />
                            {event.severity === 'critical' ? '严重' : event.severity === 'high' ? '高' : event.severity === 'medium' ? '中' : '低'}
                          </Tag>
                          <span className="font-medium text-text-primary">{event.title}</span>
                        </div>
                        {event.action_required && (
                          <Badge status="warning" text={<span className="text-xs text-warning">需要操作</span>} />
                        )}
                      </div>
                      <p className="text-sm text-text-secondary mb-2">{event.description}</p>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {event.affected_symbols.map((s) => (
                            <Tag key={s} className="text-[10px] bg-primary/10 text-primary border-0">
                              {s}
                            </Tag>
                          ))}
                        </div>
                        <span className="text-xs text-text-secondary">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card className="bg-surface border-border" title={<span className="text-sm font-medium">事件汇总</span>}>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">严重</span>
                  <span className="text-sm font-medium text-bearish">
                    {events.filter((e) => e.severity === 'critical').length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">高</span>
                  <span className="text-sm font-medium text-warning">
                    {events.filter((e) => e.severity === 'high').length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">中</span>
                  <span className="text-sm font-medium text-primary">
                    {events.filter((e) => e.severity === 'medium').length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">需要操作</span>
                  <span className="text-sm font-medium text-warning">
                    {events.filter((e) => e.action_required).length}
                  </span>
                </div>
              </div>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
