import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Progress, Statistic, Badge, Select, Button, Spin, Empty, Tooltip } from 'antd'
import {
  Sparkles,
  Brain,
  TrendingUp,
  TrendingDown,
  Activity,
  Globe,
  Zap,
  RefreshCw,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Radio,
  Target,
} from 'lucide-react'
import { api } from '../services/api/client'
import clsx from 'clsx'
import { isMockMode } from '../config/mock'

interface Narrative {
  narrative_id: string
  name: string
  type: 'sector_rotation' | 'macro_theme' | 'event_driven' | 'technical_pattern'
  strength: 'HIGH' | 'MEDIUM' | 'LOW'
  velocity: 'FAST' | 'MODERATE' | 'SLOW' | 'REVERSING'
  confidence: number
  affected_symbols: string[]
  flow: NarrativeFlowStep[]
  started_at: string
  last_updated: string
  status: 'active' | 'fading' | 'emerging'
}

interface NarrativeFlowStep {
  step: number
  description: string
  metric: string
  value: string
  direction: 'up' | 'down' | 'neutral'
}

interface NarrativeRotation {
  from_narrative: string
  to_narrative: string
  probability: number
  estimated_time: string
}

interface NarrativeHeatmap {
  narrative: string
  strength: number
  trend: 'rising' | 'falling' | 'stable'
}

const strengthConfig = {
  HIGH: { color: 'bg-bullish/20 text-bullish border-bullish/30', barColor: '#10B981', label: '强' },
  MEDIUM: { color: 'bg-warning/20 text-warning border-warning/30', barColor: '#F59E0B', label: '中' },
  LOW: { color: 'bg-neutral/20 text-neutral border-neutral/30', barColor: '#6B7280', label: '弱' },
}

const velocityConfig = {
  FAST: { color: 'text-bullish', icon: TrendingUp, label: '快速' },
  MODERATE: { color: 'text-warning', icon: Activity, label: '中等' },
  SLOW: { color: 'text-neutral', icon: Minus, label: '缓慢' },
  REVERSING: { color: 'text-bearish', icon: TrendingDown, label: '反转' },
}

const statusConfig = {
  active: { color: 'bg-bullish text-background', label: '活跃' },
  fading: { color: 'bg-warning text-background', label: '消退' },
  emerging: { color: 'bg-primary text-background', label: '新兴' },
}

const mockNarratives: Narrative[] = [
  {
    narrative_id: 'n1',
    name: 'AI Rotation',
    type: 'sector_rotation',
    strength: 'HIGH',
    velocity: 'FAST',
    confidence: 0.81,
    affected_symbols: ['FETUSDT', 'WLDUSDT', 'AGIXUSDT', 'RNDRUSDT'],
    flow: [
      { step: 1, description: 'AI 叙事启动', metric: '推特讨论量', value: '+340%', direction: 'up' },
      { step: 2, description: '资金流入 AI 币', metric: '净流入', value: '$52M', direction: 'up' },
      { step: 3, description: 'FET/WLD/AGIX 联动', metric: '相关性', value: '0.87', direction: 'up' },
      { step: 4, description: 'OI 增长', metric: 'OI 变化', value: '+45%', direction: 'up' },
      { step: 5, description: 'Funding 升高', metric: 'Funding', value: '+0.03%', direction: 'up' },
    ],
    started_at: '2024-01-15T08:00:00Z',
    last_updated: '2024-01-15T14:30:00Z',
    status: 'active',
  },
  {
    narrative_id: 'n2',
    name: 'ETF Momentum',
    type: 'macro_theme',
    strength: 'MEDIUM',
    velocity: 'MODERATE',
    confidence: 0.68,
    affected_symbols: ['BTCUSDT', 'ETHUSDT'],
    flow: [
      { step: 1, description: 'ETF 申请进展', metric: '新闻热度', value: 'HIGH', direction: 'up' },
      { step: 2, description: '机构资金流入', metric: 'ETF 净流入', value: '+$120M', direction: 'up' },
      { step: 3, description: 'BTC 强势', metric: 'BTC.D', value: '+2.1%', direction: 'up' },
    ],
    started_at: '2024-01-14T00:00:00Z',
    last_updated: '2024-01-15T14:00:00Z',
    status: 'active',
  },
  {
    narrative_id: 'n3',
    name: 'Risk-Off Macro',
    type: 'macro_theme',
    strength: 'LOW',
    velocity: 'SLOW',
    confidence: 0.45,
    affected_symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
    flow: [
      { step: 1, description: '美联储鹰派信号', metric: '利率预期', value: '+25bp', direction: 'up' },
      { step: 2, description: '风险资产承压', metric: 'SPX', value: '-1.2%', direction: 'down' },
    ],
    started_at: '2024-01-15T10:00:00Z',
    last_updated: '2024-01-15T12:00:00Z',
    status: 'fading',
  },
]

const mockHeatmap: NarrativeHeatmap[] = [
  { narrative: 'AI', strength: 0.85, trend: 'rising' },
  { narrative: 'MEME', strength: 0.62, trend: 'falling' },
  { narrative: 'RWA', strength: 0.45, trend: 'stable' },
  { narrative: 'L2', strength: 0.38, trend: 'rising' },
  { narrative: 'Gaming', strength: 0.28, trend: 'stable' },
  { narrative: 'DeFi', strength: 0.22, trend: 'falling' },
]

const mockRotations: NarrativeRotation[] = [
  { from_narrative: 'MEME', to_narrative: 'AI', probability: 0.72, estimated_time: '2-3天' },
  { from_narrative: 'DeFi', to_narrative: 'RWA', probability: 0.58, estimated_time: '1-2周' },
]

export function NarrativePage() {
  const [loading, setLoading] = useState(true)
  const [narratives, setNarratives] = useState<Narrative[]>([])
  const [heatmap, setHeatmap] = useState<NarrativeHeatmap[]>([])
  const [rotations, setRotations] = useState<NarrativeRotation[]>([])
  const [selectedNarrative, setSelectedNarrative] = useState<Narrative | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    setLoading(true)
    if (isMockMode) {
      setNarratives(mockNarratives)
      setHeatmap(mockHeatmap)
      setRotations(mockRotations)
      if (mockNarratives.length > 0) {
        setSelectedNarrative(mockNarratives[0])
      }
      setLoading(false)
      return
    }

    try {
      const [narrativesRes, heatmapRes, rotationsRes] = await Promise.all([
        api.get('/narrative/current'),
        api.get('/narrative/heatmap'),
        api.get('/narrative/rotations'),
      ])
      if (narrativesRes.data && Array.isArray(narrativesRes.data)) {
        setNarratives(narrativesRes.data)
        if (narrativesRes.data.length > 0) {
          setSelectedNarrative(narrativesRes.data[0])
        }
      }
      if (heatmapRes.data && Array.isArray(heatmapRes.data)) {
        setHeatmap(heatmapRes.data)
      }
      if (rotationsRes.data && Array.isArray(rotationsRes.data)) {
        setRotations(rotationsRes.data)
      }
    } catch (error) {
      console.error('Failed to load narrative data:', error)
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

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">叙事分析</h1>
          <p className="text-text-secondary text-sm mt-1">市场叙事分析 - 当前市场正在相信什么故事</p>
        </div>
        <Button icon={<RefreshCw className="w-4 h-4" />} onClick={loadData}>刷新</Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card className="bg-surface border-border" title={<span className="text-sm font-medium">当前叙事</span>}>
            {narratives.length === 0 ? (
              <Empty description="暂无活跃叙事" />
            ) : (
              <div className="space-y-4">
                {narratives.map((narrative) => {
                  const strengthCfg = strengthConfig[narrative.strength]
                  const velocityCfg = velocityConfig[narrative.velocity]
                  const statusCfg = statusConfig[narrative.status]
                  const VelocityIcon = velocityCfg.icon

                  return (
                    <div
                      key={narrative.narrative_id}
                      className={clsx(
                        'p-4 rounded-lg border transition-all cursor-pointer',
                        selectedNarrative?.narrative_id === narrative.narrative_id
                          ? 'border-primary bg-primary/5'
                          : 'border-border bg-background hover:border-primary/30'
                      )}
                      onClick={() => setSelectedNarrative(narrative)}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="text-lg font-bold text-text-primary">{narrative.name}</div>
                          <Tag className={clsx('text-[10px] border-0', statusCfg.color)}>
                            {statusCfg.label}
                          </Tag>
                        </div>
                        <div className="flex items-center gap-2">
                          <Tag className={clsx('text-[10px] border', strengthCfg.color)}>
                            强度: {strengthCfg.label}
                          </Tag>
                          <Tag className={clsx('text-[10px]', velocityCfg.color)}>
                            <VelocityIcon className="w-3 h-3 inline mr-1" />
                            {velocityCfg.label}
                          </Tag>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 mb-3">
                        <div className="flex-1">
                          <div className="text-xs text-text-secondary mb-1">置信度</div>
                          <Progress
                            percent={narrative.confidence * 100}
                            showInfo={false}
                            size="small"
                            strokeColor={strengthCfg.barColor}
                          />
                          <div className="text-sm font-medium text-text-primary mt-1">
                            {(narrative.confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                        <div className="flex-1">
                          <div className="text-xs text-text-secondary mb-1">影响品种</div>
                          <div className="flex flex-wrap gap-1">
                            {narrative.affected_symbols.slice(0, 4).map((s) => (
                              <Tag key={s} className="text-[10px] bg-primary/10 text-primary border-0">
                                {s.replace('USDT', '')}
                              </Tag>
                            ))}
                          </div>
                        </div>
                      </div>

                      {selectedNarrative?.narrative_id === narrative.narrative_id && narrative.flow.length > 0 && (
                        <div className="pt-3 border-t border-border">
                          <div className="text-xs text-text-secondary mb-2">Narrative Flow</div>
                          <div className="space-y-2">
                            {narrative.flow.map((step, i) => (
                              <div key={step.step} className="flex items-center gap-2">
                                <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs text-primary">
                                  {step.step}
                                </div>
                                <div className="flex-1">
                                  <span className="text-xs text-text-primary">{step.description}</span>
                                </div>
                                <div className="text-xs text-text-secondary">{step.metric}:</div>
                                <div className={clsx(
                                  'text-xs font-medium',
                                  step.direction === 'up' ? 'text-bullish' : step.direction === 'down' ? 'text-bearish' : 'text-text-secondary'
                                )}>
                                  {step.value}
                                </div>
                                {i < narrative.flow.length - 1 && (
                                  <div className="text-text-secondary">↓</div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card className="bg-surface border-border" title={<span className="text-sm font-medium">叙事热度图</span>}>
            <div className="space-y-3">
              {heatmap.map((item) => (
                <div key={item.narrative} className="flex items-center gap-3">
                  <div className="w-16 text-sm text-text-primary">{item.narrative}</div>
                  <div className="flex-1">
                    <div className="h-6 bg-border/30 rounded overflow-hidden">
                      <div
                        className={clsx(
                          'h-full transition-all',
                          item.trend === 'rising' ? 'bg-bullish' : item.trend === 'falling' ? 'bg-bearish' : 'bg-neutral'
                        )}
                        style={{ width: `${item.strength * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="w-12 text-right">
                    <span className={clsx(
                      'text-sm font-medium',
                      item.trend === 'rising' ? 'text-bullish' : item.trend === 'falling' ? 'text-bearish' : 'text-text-secondary'
                    )}>
                      {(item.strength * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="bg-surface border-border mt-4" title={<span className="text-sm font-medium">叙事轮动</span>}>
            {rotations.length === 0 ? (
              <div className="py-4 text-center text-xs text-text-secondary">暂无轮动预测</div>
            ) : (
              <div className="space-y-3">
                {rotations.map((rotation, i) => (
                  <div key={i} className="p-3 bg-background rounded-lg border border-border">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Tag className="bg-bearish/20 text-bearish border-0">{rotation.from_narrative}</Tag>
                        <ArrowUpRight className="w-4 h-4 text-primary" />
                        <Tag className="bg-bullish/20 text-bullish border-0">{rotation.to_narrative}</Tag>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-secondary">概率</span>
                      <span className="text-primary font-medium">{(rotation.probability * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center justify-between text-xs mt-1">
                      <span className="text-text-secondary">预计时间</span>
                      <span className="text-text-primary">{rotation.estimated_time}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="bg-surface border-border mt-4" title={<span className="text-sm font-medium">叙事影响</span>}>
            {selectedNarrative && (
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-text-secondary mb-1">叙事</div>
                  <div className="text-sm font-medium text-text-primary">{selectedNarrative.name}</div>
                </div>
                <div>
                  <div className="text-xs text-text-secondary mb-1">影响品种</div>
                  <div className="flex flex-wrap gap-1">
                    {selectedNarrative.affected_symbols.map((s) => (
                      <Tag key={s} className="text-[10px] bg-primary/10 text-primary border-0">{s}</Tag>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-secondary mb-1">联动性</div>
                  <div className="text-lg font-bold text-primary">
                    {selectedNarrative.confidence.toFixed(2)}
                  </div>
                </div>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
