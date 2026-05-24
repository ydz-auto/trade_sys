import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Table, Progress, Statistic, Badge, Timeline, Spin, Alert, Tooltip } from 'antd'
import {
  Activity,
  Wifi,
  WifiOff,
  Clock,
  Database,
  Zap,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Server,
  ArrowDownRight,
  ArrowUpRight,
} from 'lucide-react'
import { api } from '../services/api/client'
import clsx from 'clsx'

interface WebSocketStatus {
  name: string
  url: string
  status: 'connected' | 'disconnected' | 'reconnecting'
  latency: number
  last_message: string
  messages_per_second: number
  reconnect_count: number
}

interface FeaturePipeline {
  name: string
  status: 'healthy' | 'degraded' | 'down'
  latency_ms: number
  throughput: number
  error_rate: number
  last_update: string
  queue_size: number
}

interface DataQuality {
  symbol: string
  completeness: number
  latency_p50: number
  latency_p99: number
  drop_rate: number
  last_gap: string
}

interface PipelineEvent {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error'
  component: string
  message: string
}

export function DataPipelinePage() {
  const [wsStatus, setWsStatus] = useState<WebSocketStatus[]>([])
  const [pipelines, setPipelines] = useState<FeaturePipeline[]>([])
  const [dataQuality, setDataQuality] = useState<DataQuality[]>([])
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 3000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [wsRes, pipelineRes, qualityRes, eventsRes] = await Promise.all([
        api.get('/pipeline/websocket'),
        api.get('/pipeline/features'),
        api.get('/pipeline/quality'),
        api.get('/pipeline/events'),
      ])
      if (wsRes.data) setWsStatus(wsRes.data)
      if (pipelineRes.data) setPipelines(pipelineRes.data)
      if (qualityRes.data) setDataQuality(qualityRes.data)
      if (eventsRes.data) setEvents(eventsRes.data)
    } catch (error) {
      console.error('Failed to load pipeline data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-bullish" />
      case 'disconnected':
      case 'down':
        return <XCircle className="w-4 h-4 text-bearish" />
      case 'reconnecting':
      case 'degraded':
        return <AlertTriangle className="w-4 h-4 text-warning" />
      default:
        return <Activity className="w-4 h-4 text-text-secondary" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
      case 'healthy':
        return 'success'
      case 'disconnected':
      case 'down':
        return 'error'
      case 'reconnecting':
      case 'degraded':
        return 'warning'
      default:
        return 'default'
    }
  }

  const wsColumns = [
    {
      title: 'WebSocket',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: WebSocketStatus) => (
        <div className="flex items-center gap-2">
          {record.status === 'connected' ? (
            <Wifi className="w-4 h-4 text-bullish" />
          ) : (
            <WifiOff className="w-4 h-4 text-bearish" />
          )}
          <span className="font-medium text-text-primary">{name}</span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag
          className={clsx(
            'text-xs border-0',
            status === 'connected'
              ? 'bg-bullish/20 text-bullish'
              : status === 'disconnected'
              ? 'bg-bearish/20 text-bearish'
              : 'bg-warning/20 text-warning'
          )}
        >
          {status === 'connected' ? '已连接' : status === 'disconnected' ? '已断开' : '重连中'}
        </Tag>
      ),
    },
    {
      title: '延迟',
      dataIndex: 'latency',
      key: 'latency',
      render: (lat: number) => (
        <span className={clsx('font-mono', lat < 100 ? 'text-bullish' : lat < 300 ? 'text-warning' : 'text-bearish')}>
          {lat}ms
        </span>
      ),
    },
    {
      title: '消息/秒',
      dataIndex: 'messages_per_second',
      key: 'messages_per_second',
      render: (mps: number) => <span className="font-mono text-text-primary">{mps}</span>,
    },
    {
      title: '重连次数',
      dataIndex: 'reconnect_count',
      key: 'reconnect_count',
      render: (count: number) => (
        <span className={clsx('font-mono', count > 5 ? 'text-bearish' : 'text-text-primary')}>{count}</span>
      ),
    },
    {
      title: '最后消息',
      dataIndex: 'last_message',
      key: 'last_message',
      render: (t: string) => <span className="text-xs text-text-secondary">{t}</span>,
    },
  ]

  const pipelineColumns = [
    {
      title: 'Pipeline',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: FeaturePipeline) => (
        <div className="flex items-center gap-2">
          {getStatusIcon(record.status)}
          <span className="font-medium text-text-primary">{name}</span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag
          className={clsx(
            'text-xs border-0',
            status === 'healthy'
              ? 'bg-bullish/20 text-bullish'
              : status === 'down'
              ? 'bg-bearish/20 text-bearish'
              : 'bg-warning/20 text-warning'
          )}
        >
          {status === 'healthy' ? '正常' : status === 'down' ? '异常' : '降级'}
        </Tag>
      ),
    },
    {
      title: '延迟',
      dataIndex: 'latency_ms',
      key: 'latency_ms',
      render: (lat: number) => (
        <span className={clsx('font-mono', lat < 50 ? 'text-bullish' : lat < 100 ? 'text-warning' : 'text-bearish')}>
          {lat}ms
        </span>
      ),
    },
    {
      title: '吞吐量',
      dataIndex: 'throughput',
      key: 'throughput',
      render: (t: number) => <span className="font-mono text-text-primary">{t}/s</span>,
    },
    {
      title: '错误率',
      dataIndex: 'error_rate',
      key: 'error_rate',
      render: (rate: number) => (
        <span className={clsx('font-mono', rate < 1 ? 'text-bullish' : rate < 5 ? 'text-warning' : 'text-bearish')}>
          {rate.toFixed(2)}%
        </span>
      ),
    },
    {
      title: '队列',
      dataIndex: 'queue_size',
      key: 'queue_size',
      render: (size: number) => (
        <span className={clsx('font-mono', size < 100 ? 'text-text-primary' : 'text-warning')}>{size}</span>
      ),
    },
  ]

  const qualityColumns = [
    {
      title: '品种',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (s: string) => <span className="font-medium text-text-primary">{s}</span>,
    },
    {
      title: '完整性',
      dataIndex: 'completeness',
      key: 'completeness',
      render: (val: number) => (
        <div className="flex items-center gap-2">
          <Progress
            percent={val * 100}
            showInfo={false}
            size="small"
            className="w-20"
            strokeColor={val > 0.99 ? '#10B981' : val > 0.95 ? '#F59E0B' : '#EF4444'}
          />
          <span className={clsx('text-xs', val > 0.99 ? 'text-bullish' : val > 0.95 ? 'text-warning' : 'text-bearish')}>
            {(val * 100).toFixed(2)}%
          </span>
        </div>
      ),
    },
    {
      title: 'P50延迟',
      dataIndex: 'latency_p50',
      key: 'latency_p50',
      render: (lat: number) => <span className="font-mono text-text-primary">{lat}ms</span>,
    },
    {
      title: 'P99延迟',
      dataIndex: 'latency_p99',
      key: 'latency_p99',
      render: (lat: number) => (
        <span className={clsx('font-mono', lat < 200 ? 'text-bullish' : lat < 500 ? 'text-warning' : 'text-bearish')}>
          {lat}ms
        </span>
      ),
    },
    {
      title: '丢包率',
      dataIndex: 'drop_rate',
      key: 'drop_rate',
      render: (rate: number) => (
        <span className={clsx('font-mono', rate < 0.01 ? 'text-bullish' : rate < 0.1 ? 'text-warning' : 'text-bearish')}>
          {(rate * 100).toFixed(3)}%
        </span>
      ),
    },
    {
      title: '最近缺口',
      dataIndex: 'last_gap',
      key: 'last_gap',
      render: (t: string) => <span className="text-xs text-text-secondary">{t || '无'}</span>,
    },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  const healthyCount = pipelines.filter((p) => p.status === 'healthy').length
  const connectedCount = wsStatus.filter((w) => w.status === 'connected').length

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">数据管道监控</h1>
          <p className="text-text-secondary text-sm mt-1">WebSocket状态、Feature提取延迟、数据质量监控</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge status="success" text={<span className="text-xs text-text-secondary">实时监控</span>} />
          <button
            onClick={loadData}
            className="p-2 rounded-lg bg-surface border border-border hover:border-primary/30 transition-colors"
          >
            <RefreshCw className="w-4 h-4 text-text-secondary" />
          </button>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">WebSocket 连接</span>}
              value={connectedCount}
              suffix={`/ ${wsStatus.length}`}
              prefix={<Wifi className="w-4 h-4 text-primary" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">健康 Pipeline</span>}
              value={healthyCount}
              suffix={`/ ${pipelines.length}`}
              prefix={<Activity className="w-4 h-4 text-bullish" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">平均延迟</span>}
              value={pipelines.length > 0 ? (pipelines.reduce((a, p) => a + p.latency_ms, 0) / pipelines.length).toFixed(0) : 0}
              suffix="ms"
              prefix={<Clock className="w-4 h-4 text-accent" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">总吞吐量</span>}
              value={pipelines.reduce((a, p) => a + p.throughput, 0)}
              suffix="/s"
              prefix={<Zap className="w-4 h-4 text-warning" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Wifi className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">WebSocket 状态</span>
              </div>
            }
          >
            <Table
              dataSource={wsStatus}
              columns={wsColumns}
              rowKey="name"
              pagination={false}
              size="small"
              locale={{ emptyText: '暂无 WebSocket 连接' }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">Feature Pipeline</span>
              </div>
            }
          >
            <Table
              dataSource={pipelines}
              columns={pipelineColumns}
              rowKey="name"
              pagination={false}
              size="small"
              locale={{ emptyText: '暂无 Pipeline 数据' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        className="bg-surface border-border"
        title={
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-warning" />
            <span className="text-sm font-medium">数据质量监控</span>
          </div>
        }
      >
        <Table
          dataSource={dataQuality}
          columns={qualityColumns}
          rowKey="symbol"
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无数据质量信息' }}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">管道事件</span>
                <Badge count={events.filter((e) => e.level === 'error').length} className="ml-2" />
              </div>
            }
          >
            <Timeline
              items={events.slice(0, 10).map((event) => ({
                color: event.level === 'error' ? 'red' : event.level === 'warning' ? 'orange' : 'green',
                children: (
                  <div>
                    <div className="flex items-center gap-2">
                      <Tag className="text-[10px] border-0 bg-primary/10 text-primary">{event.component}</Tag>
                      <span className="text-xs text-text-secondary">{event.timestamp}</span>
                    </div>
                    <div className="text-sm text-text-primary mt-1">{event.message}</div>
                  </div>
                ),
              }))}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">系统资源</span>
              </div>
            }
          >
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-secondary">CPU 使用率</span>
                  <span className="text-xs font-mono text-text-primary">45%</span>
                </div>
                <Progress percent={45} showInfo={false} strokeColor="#3B82F6" trailColor="var(--border)" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-secondary">内存使用</span>
                  <span className="text-xs font-mono text-text-primary">62%</span>
                </div>
                <Progress percent={62} showInfo={false} strokeColor="#10B981" trailColor="var(--border)" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-secondary">网络带宽</span>
                  <span className="text-xs font-mono text-text-primary">28%</span>
                </div>
                <Progress percent={28} showInfo={false} strokeColor="#F59E0B" trailColor="var(--border)" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-secondary">Redis 连接池</span>
                  <span className="text-xs font-mono text-text-primary">15/50</span>
                </div>
                <Progress percent={30} showInfo={false} strokeColor="#8B5CF6" trailColor="var(--border)" />
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
