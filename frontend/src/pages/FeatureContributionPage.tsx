import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Select, Progress, Table, Tooltip, Spin } from 'antd'
import {
  BarChart3,
  Info,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Zap,
  Activity,
} from 'lucide-react'
import {
  useRuntime,
  useFeaturesState,
} from '../services/runtime'
import { api } from '../services/api/client'
import clsx from 'clsx'

interface FeatureContribution {
  feature_name: string
  display_name: string
  category: 'raw' | 'derived' | 'microstructure' | 'cross_market' | 'event'
  contribution: number
  direction: 'bullish' | 'bearish' | 'neutral'
  value: number
  zscore: number
  description: string
}

interface StrategyExplanation {
  strategy_id: string
  strategy_name: string
  symbol: string
  action: string
  confidence: number
  trigger_conditions: string[]
  feature_contributions: FeatureContribution[]
  suggested_rr: number
  suggested_leverage: number
}

const categoryColors: Record<string, string> = {
  raw: 'bg-primary/20 text-primary',
  derived: 'bg-accent/20 text-accent',
  microstructure: 'bg-warning/20 text-warning',
  cross_market: 'bg-bullish/20 text-bullish',
  event: 'bg-bearish/20 text-bearish',
}

const categoryLabels: Record<string, string> = {
  raw: '原始',
  derived: '衍生',
  microstructure: '微观',
  cross_market: '跨市场',
  event: '事件',
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
const STRATEGIES = ['Panic Reversal', 'Funding Trap', 'Short Squeeze', 'Liquidity Vacuum']

export function FeatureContributionPage() {
  const { isConnected } = useRuntime()
  const featuresState = useFeaturesState()

  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTCUSDT')
  const [selectedStrategy, setSelectedStrategy] = useState<string>('Panic Reversal')
  const [explanation, setExplanation] = useState<StrategyExplanation | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadExplanation()
  }, [selectedSymbol, selectedStrategy])

  const loadExplanation = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/strategy/explain?symbol=${selectedSymbol}&strategy=${selectedStrategy}`)
      if (res.data) {
        setExplanation(res.data)
      }
    } catch (error) {
      console.error('Failed to load explanation:', error)
    } finally {
      setLoading(false)
    }
  }

  const featureMetadata = featuresState?.metadata || []
  const featureValues = featuresState?.values?.[selectedSymbol] || []

  const columns = [
    {
      title: '特征',
      dataIndex: 'display_name',
      key: 'feature',
      render: (text: string, record: FeatureContribution) => (
        <div className="flex items-center gap-2">
          <Tag className={clsx('text-[10px] border-0', categoryColors[record.category])}>
            {categoryLabels[record.category]}
          </Tag>
          <span className="text-text-primary font-medium">{text}</span>
        </div>
      ),
    },
    {
      title: '贡献度',
      dataIndex: 'contribution',
      key: 'contribution',
      render: (value: number, record: FeatureContribution) => (
        <div className="flex items-center gap-2">
          <div className="w-24">
            <Progress
              percent={Math.abs(value) * 100}
              showInfo={false}
              size="small"
              strokeColor={record.direction === 'bullish' ? '#10B981' : record.direction === 'bearish' ? '#EF4444' : '#6B7280'}
            />
          </div>
          <span
            className={clsx(
              'text-sm font-medium',
              record.direction === 'bullish' ? 'text-bullish' : record.direction === 'bearish' ? 'text-bearish' : 'text-text-secondary'
            )}
          >
            {record.direction === 'bullish' ? '+' : record.direction === 'bearish' ? '-' : ''}
            {(value * 100).toFixed(0)}%
          </span>
        </div>
      ),
    },
    {
      title: '数值',
      dataIndex: 'value',
      key: 'value',
      render: (value: number) => (
        <span className="text-text-primary font-mono text-sm">{value.toFixed(2)}</span>
      ),
    },
    {
      title: 'Z分数',
      dataIndex: 'zscore',
      key: 'zscore',
      render: (value: number) => (
        <span
          className={clsx(
            'font-mono text-sm',
            Math.abs(value) > 2 ? 'text-accent font-bold' : 'text-text-secondary'
          )}
        >
          {value > 0 ? '+' : ''}{value.toFixed(2)}
        </span>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => (
        <Tooltip title={text}>
          <span className="text-xs text-text-secondary truncate block max-w-[200px]">{text}</span>
        </Tooltip>
      ),
    },
  ]

  if (loading && !featuresState) {
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
          <h1 className="text-2xl font-bold text-text-primary">特征贡献度</h1>
          <p className="text-text-secondary text-sm mt-1">策略触发原因解释 - 运行态可解释性</p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            className="w-32"
            options={SYMBOLS.map(s => ({ value: s, label: s }))}
          />
          <Select
            value={selectedStrategy}
            onChange={setSelectedStrategy}
            className="w-40"
            options={STRATEGIES.map(s => ({ value: s, label: s }))}
          />
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card className="bg-surface border-border h-full">
            <div className="text-center py-4">
              <div className="text-xs text-text-secondary mb-2">{explanation?.strategy_name}</div>
              <div className="flex items-center justify-center gap-2 mb-4">
                <Tag className="bg-bullish text-background text-lg px-4 py-1 border-0 font-bold">
                  {explanation?.action === 'ENTER' ? '入场' : explanation?.action === 'EXIT' ? '离场' : explanation?.action === 'HOLD' ? '持有' : explanation?.action}
                </Tag>
                <Tag className="bg-primary/20 text-primary border-0">{explanation?.symbol}</Tag>
              </div>
              <div className="text-4xl font-bold text-text-primary mb-1">
                {((explanation?.confidence || 0) * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-text-secondary">置信度</div>
            </div>

            <div className="border-t border-border pt-4 mt-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">建议盈亏比</span>
                <span className="text-lg font-bold text-bullish">{explanation?.suggested_rr}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">建议杠杆</span>
                <span className="text-lg font-bold text-text-primary">{explanation?.suggested_leverage}x</span>
              </div>
            </div>

            <div className="border-t border-border pt-4 mt-4">
              <div className="text-xs text-text-secondary mb-2">触发条件</div>
              <div className="space-y-1">
                {explanation?.trigger_conditions.map((cond, i) => (
                  <div key={i} className="text-xs text-bullish font-mono bg-bullish/10 px-2 py-1 rounded">
                    {cond}
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">特征贡献度</span>
              </div>
            }
          >
            <Table
              dataSource={explanation?.feature_contributions}
              columns={columns}
              rowKey="feature_name"
              pagination={false}
              size="small"
              className="feature-table"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">贡献度分解</span>
              </div>
            }
          >
            <Row gutter={[16, 16]}>
              {explanation?.feature_contributions.slice(0, 6).map((feature) => (
                <Col xs={24} sm={12} md={8} key={feature.feature_name}>
                  <div className="p-4 bg-background rounded-lg border border-border">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {feature.direction === 'bullish' ? (
                          <ArrowUpRight className="w-4 h-4 text-bullish" />
                        ) : feature.direction === 'bearish' ? (
                          <ArrowDownRight className="w-4 h-4 text-bearish" />
                        ) : (
                          <Minus className="w-4 h-4 text-text-secondary" />
                        )}
                        <span className="text-sm font-medium text-text-primary">{feature.display_name}</span>
                      </div>
                      <Tag className={clsx('text-[10px] border-0', categoryColors[feature.category])}>
                        {categoryLabels[feature.category]}
                      </Tag>
                    </div>
                    <div className="mb-2">
                      <Progress
                        percent={Math.abs(feature.contribution) * 100}
                        showInfo={false}
                        strokeColor={feature.direction === 'bullish' ? '#10B981' : feature.direction === 'bearish' ? '#EF4444' : '#6B7280'}
                        trailColor="var(--border)"
                      />
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-secondary">数值: {feature.value.toFixed(2)}</span>
                      <span className={clsx(Math.abs(feature.zscore) > 2 ? 'text-accent font-bold' : 'text-text-secondary')}>
                        Z: {feature.zscore > 0 ? '+' : ''}{feature.zscore.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card className="bg-surface border-border">
            <div className="flex items-center gap-2 mb-4">
              <Info className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">如何阅读</span>
            </div>
            <div className="space-y-2 text-xs text-text-secondary">
              <p><strong className="text-text-primary">贡献度 %</strong> - 该特征对策略信号的贡献程度</p>
              <p><strong className="text-text-primary">Z分数</strong> - 当前值偏离均值的程度（|z| &gt; 2 为显著）</p>
              <p><strong className="text-text-primary">方向</strong> - 特征对信号的影响方向</p>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card className="bg-surface border-border">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-4 h-4 text-accent" />
              <span className="text-sm font-medium">快捷操作</span>
            </div>
            <div className="flex gap-2">
              <Tag className="bg-bullish/20 text-bullish border-0 cursor-pointer hover:bg-bullish/30">
                跟随信号
              </Tag>
              <Tag className="bg-primary/20 text-primary border-0 cursor-pointer hover:bg-primary/30">
                查看历史
              </Tag>
              <Tag className="bg-warning/20 text-warning border-0 cursor-pointer hover:bg-warning/30">
                调整阈值
              </Tag>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
