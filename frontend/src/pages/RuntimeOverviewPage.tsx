import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Progress, Statistic, Badge, Tooltip, Empty, Spin } from 'antd'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Shield,
  Zap,
  Target,
  Activity,
  Radio,
  Brain,
  Clock,
  ChevronRight,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from 'lucide-react'
import {
  useRuntime,
  useMarketState,
  useSignalsState,
  useRiskState,
  usePnLState,
  useAIState,
} from '../services/runtime'
import { api } from '../services/api/client'
import clsx from 'clsx'
import { isMockMode } from '../config/mock'

interface RuntimeStats {
  state: string
  governor_stats: {
    events_processed: number
    errors: number
    uptime_seconds: number
  }
  degradation_stats: {
    current_mode: string
    load_metrics: {
      cpu_percent: number
      memory_percent: number
      event_rate: number
    }
  }
}

interface ActiveStrategy {
  id: string
  strategy_id: string
  symbol: string
  enabled: boolean
  enabled_at: string
}

const regimeColors: Record<string, string> = {
  TRENDING_UP: 'bg-bullish/20 text-bullish border-bullish/30',
  TRENDING_DOWN: 'bg-bearish/20 text-bearish border-bearish/30',
  RANGING: 'bg-warning/20 text-warning border-warning/30',
  HIGH_VOLATILITY: 'bg-accent/20 text-accent border-accent/30',
  PANIC: 'bg-bearish/30 text-bearish border-bearish/50',
}

const regimeLabels: Record<string, string> = {
  TRENDING_UP: '上涨趋势',
  TRENDING_DOWN: '下跌趋势',
  RANGING: '震荡',
  HIGH_VOLATILITY: '高波动',
  PANIC: '恐慌',
}

const signalStateColors: Record<string, string> = {
  ENTER: 'bg-bullish text-background',
  HOLD: 'bg-warning text-background',
  EXIT: 'bg-bearish text-background',
  NONE: 'bg-neutral text-background',
}

const signalLabels: Record<string, string> = {
  ENTER: '入场',
  HOLD: '持有',
  EXIT: '离场',
  NONE: '无信号',
}

export function RuntimeOverviewPage() {
  const { isConnected, isLive, isPaper } = useRuntime()
  const marketState = useMarketState()
  const signalsState = useSignalsState()
  const riskState = useRiskState()
  const pnlState = usePnLState()
  const aiState = useAIState()

  const [runtimeStats, setRuntimeStats] = useState<RuntimeStats | null>(null)
  const [activeStrategies, setActiveStrategies] = useState<ActiveStrategy[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadRuntimeStats()
    const interval = setInterval(loadRuntimeStats, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadRuntimeStats = async () => {
    try {
      const [runtimeRes, strategiesRes] = await Promise.all([
        api.get('/runtime/stats'),
        api.get('/strategy/active'),
      ])
      setRuntimeStats(runtimeRes.data)
      setActiveStrategies(strategiesRes.data || [])
    } catch (error) {
      console.error('Failed to load runtime stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时 ${minutes}分钟`
  }

  const prices = marketState?.prices || {}
  const btcPrice = prices['BTCUSDT']
  const ethPrice = prices['ETHUSDT']
  const signals = signalsState?.history?.slice(0, 5) || []
  const latestInsight = aiState?.latestInsight

  if (loading && !marketState) {
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
          <h1 className="text-2xl font-bold text-text-primary">运行态总览</h1>
          <p className="text-text-secondary text-sm mt-1">系统运行态总览</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            status={isConnected ? 'success' : 'error'}
            text={isConnected ? '运行中' : '已离线'}
          />
          <Tag color={isLive ? 'green' : isPaper ? 'orange' : 'default'}>
            {isLive ? '实盘' : isPaper ? '模拟' : '回测'}
          </Tag>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="bg-surface border-border h-full">
            <div className="flex items-center justify-between">
              <Statistic
                title={<span className="text-text-secondary text-xs">活跃策略</span>}
                value={activeStrategies.length}
                prefix={<Radio className="w-4 h-4 text-primary" />}
                valueStyle={{ color: 'var(--text-primary)', fontSize: '28px' }}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              {activeStrategies.slice(0, 3).map((s) => (
                <Tag key={s.id} className="text-[10px] bg-primary/10 text-primary border-0">
                  {s.symbol}
                </Tag>
              ))}
              {activeStrategies.length > 3 && (
                <Tag className="text-[10px] bg-border text-text-secondary border-0">
                  +{activeStrategies.length - 3}
                </Tag>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card className="bg-surface border-border h-full">
            <Statistic
              title={<span className="text-text-secondary text-xs">已处理事件</span>}
              value={runtimeStats?.governor_stats.events_processed || 0}
              prefix={<Activity className="w-4 h-4 text-accent" />}
              valueStyle={{ color: 'var(--text-primary)', fontSize: '28px' }}
            />
            <div className="mt-3 text-xs text-text-secondary">
              运行时间: {formatUptime(runtimeStats?.governor_stats.uptime_seconds || 0)}
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card className="bg-surface border-border h-full">
            <div className="flex items-center justify-between mb-2">
              <span className="text-text-secondary text-xs">CPU 使用率</span>
              <span className="text-text-primary text-sm font-medium">
                {runtimeStats?.degradation_stats.load_metrics.cpu_percent.toFixed(1) || 0}%
              </span>
            </div>
            <Progress
              percent={runtimeStats?.degradation_stats.load_metrics.cpu_percent || 0}
              showInfo={false}
              strokeColor={{
                '0%': '#10B981',
                '50%': '#F59E0B',
                '100%': '#EF4444',
              }}
              trailColor="var(--border)"
            />
            <div className="flex items-center justify-between mt-3">
              <span className="text-text-secondary text-xs">内存</span>
              <span className="text-text-primary text-sm">
                {runtimeStats?.degradation_stats.load_metrics.memory_percent.toFixed(1) || 0}%
              </span>
            </div>
            <Progress
              percent={runtimeStats?.degradation_stats.load_metrics.memory_percent || 0}
              showInfo={false}
              size="small"
              strokeColor="var(--primary)"
              trailColor="var(--border)"
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card className="bg-surface border-border h-full">
            <div className="flex items-center justify-between">
              <span className="text-text-secondary text-xs">系统模式</span>
              <Tag
                className={clsx(
                  'text-[10px] font-medium',
                  runtimeStats?.degradation_stats.current_mode === 'normal'
                    ? 'bg-bullish/20 text-bullish'
                    : 'bg-warning/20 text-warning'
                )}
              >
                {runtimeStats?.degradation_stats.current_mode === 'normal' ? '正常' : '降级'}
              </Tag>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">事件速率</span>
                <span className="text-text-primary">
                  {runtimeStats?.degradation_stats.load_metrics.event_rate.toFixed(1) || 0}/秒
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">错误数</span>
                <span
                  className={clsx(
                    runtimeStats?.governor_stats.errors
                      ? 'text-bearish'
                      : 'text-bullish'
                  )}
                >
                  {runtimeStats?.governor_stats.errors || 0}
                </span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border h-full"
            title={
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">活跃信号</span>
              </div>
            }
            extra={<a href="/signals" className="text-xs text-primary hover:underline">查看全部 →</a>}
          >
            {signals.length === 0 ? (
              <div className="py-8">
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={<span className="text-text-secondary text-xs">暂无活跃信号</span>}
                />
              </div>
            ) : (
              <div className="space-y-3">
                {signals.map((signal) => (
                  <div
                    key={signal.signalId}
                    className="flex items-center justify-between p-3 bg-background rounded-lg border border-border"
                  >
                    <div className="flex items-center gap-3">
                      <Tag className={clsx('text-[10px] font-medium border-0', signalStateColors[signal.action] || 'bg-neutral/20')}>
                        {signalLabels[signal.action] || signal.action}
                      </Tag>
                      <span className="text-sm text-text-primary font-medium">{signal.symbol}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Progress
                        type="circle"
                        percent={signal.confidence * 100}
                        size={32}
                        showInfo={false}
                        strokeColor="var(--primary)"
                      />
                      <span className="text-xs text-text-secondary">
                        {(signal.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border h-full"
            title={
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">市场状态</span>
              </div>
            }
            extra={<a href="/regime" className="text-xs text-primary hover:underline">详情 →</a>}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                <div>
                  <div className="text-xs text-text-secondary mb-1">BTCUSDT</div>
                  <Tag className={clsx('text-xs', btcPrice?.change24h && btcPrice.change24h > 0 ? regimeColors.TRENDING_UP : regimeColors.RANGING)}>
                    {btcPrice?.change24h && btcPrice.change24h > 0 ? regimeLabels.TRENDING_UP : regimeLabels.RANGING}
                  </Tag>
                </div>
                <div className="text-right">
                  <div className={clsx('text-lg font-bold', btcPrice?.change24h && btcPrice.change24h > 0 ? 'text-bullish' : 'text-bearish')}>
                    {btcPrice?.change24h ? `${btcPrice.change24h > 0 ? '+' : ''}${btcPrice.change24h.toFixed(2)}%` : '-'}
                  </div>
                  <div className="text-xs text-text-secondary">24小时</div>
                </div>
              </div>
              <div className="flex items-center justify-between p-4 bg-background rounded-lg border border-border">
                <div>
                  <div className="text-xs text-text-secondary mb-1">ETHUSDT</div>
                  <Tag className={clsx('text-xs', ethPrice?.change24h && ethPrice.change24h > 0 ? regimeColors.TRENDING_UP : regimeColors.RANGING)}>
                    {ethPrice?.change24h && ethPrice.change24h > 0 ? regimeLabels.TRENDING_UP : regimeLabels.RANGING}
                  </Tag>
                </div>
                <div className="text-right">
                  <div className={clsx('text-lg font-bold', ethPrice?.change24h && ethPrice.change24h > 0 ? 'text-bullish' : 'text-bearish')}>
                    {ethPrice?.change24h ? `${ethPrice.change24h > 0 ? '+' : ''}${ethPrice.change24h.toFixed(2)}%` : '-'}
                  </div>
                  <div className="text-xs text-text-secondary">24小时</div>
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">策略表现</span>
              </div>
            }
          >
            <div className="space-y-3">
              {activeStrategies.length === 0 ? (
                <div className="py-8 text-center text-text-secondary text-sm">
                  暂无活跃策略。 <a href="/strategy" className="text-primary">启用策略 →</a>
                </div>
              ) : (
                activeStrategies.map((strategy) => (
                  <div
                    key={strategy.id}
                    className="flex items-center justify-between p-3 bg-background rounded-lg border border-border hover:border-primary/30 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Zap className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-text-primary">
                          {strategy.strategy_id}
                        </div>
                        <div className="text-xs text-text-secondary">{strategy.symbol}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-sm font-medium text-bullish">
                          {pnlState?.performance?.winRate ? `+${(pnlState.performance.winRate * 100).toFixed(1)}%` : '-'}
                        </div>
                        <div className="text-xs text-text-secondary">胜率</div>
                      </div>
                      <Badge status="success" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            className="bg-surface border-border h-full"
            title={
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">AI 叙事</span>
              </div>
            }
            extra={<a href="/narrative" className="text-xs text-primary hover:underline">更多 →</a>}
          >
            {latestInsight ? (
              <div className="space-y-3">
                <div className="p-3 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-3 h-3 text-bullish" />
                    <span className="text-xs font-medium text-text-primary">{latestInsight.title}</span>
                  </div>
                  <div className="text-xs text-text-secondary">
                    {latestInsight.content}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-secondary">置信度</span>
                  <span className="text-primary">{(latestInsight.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ) : isMockMode ? (
              <div className="space-y-3">
                <div className="p-3 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-3 h-3 text-bullish" />
                    <span className="text-xs font-medium text-text-primary">ETF 资金流</span>
                  </div>
                  <div className="text-xs text-text-secondary">
                    检测到强劲的机构买入压力
                  </div>
                </div>
                <div className="p-3 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-3 h-3 text-warning" />
                    <span className="text-xs font-medium text-text-primary">宏观风险</span>
                  </div>
                  <div className="text-xs text-text-secondary">
                    美联储政策不确定性上升
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8">
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={<span className="text-text-secondary text-xs">暂无 AI 洞察</span>}
                />
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
