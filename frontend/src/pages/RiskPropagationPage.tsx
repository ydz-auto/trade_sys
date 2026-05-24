import { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Timeline,
  Tag,
  Typography,
  Progress,
  List,
  Alert,
  Statistic,
  Tabs,
  Space,
  Spin,
  Empty,
} from 'antd'
import {
  WarningOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  DollarOutlined,
  ClockCircleOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import { api } from '../services/api/client'
import { isMockMode } from '../config/mock'

const { Title, Text } = Typography
const { TabPane } = Tabs

interface RiskEvent {
  id: number
  timestamp: string
  level: 'error' | 'warning' | 'info' | 'success'
  event: string
  component: string
  message: string
  impact: string
}

interface ComponentHealth {
  name: string
  status: 'healthy' | 'warning' | 'critical'
  latency: number
  errorRate: number
  lastCheck: string
}

interface RiskPathway {
  source: string
  target: string
  severity: number
  description: string
}

const mockRiskEvents: RiskEvent[] = [
  {
    id: 1,
    timestamp: '09:35:12',
    level: 'error',
    event: '熔断触发',
    component: 'Social API',
    message: '社交媒体API连接断开',
    impact: '情绪因子暂时不可用',
  },
  {
    id: 2,
    timestamp: '09:32:45',
    level: 'warning',
    event: '风险上升',
    component: 'Factor Engine',
    message: '因子置信度下降',
    impact: '降低仓位规模',
  },
  {
    id: 3,
    timestamp: '09:30:18',
    level: 'info',
    event: '波动率上升',
    component: 'Market Data',
    message: 'BTC波动率超过25%',
    impact: '收紧止损',
  },
  {
    id: 4,
    timestamp: '09:28:05',
    level: 'success',
    event: '系统恢复',
    component: 'WebSocket',
    message: '实时价格重连成功',
    impact: '正常交易恢复',
  },
]

const mockComponentHealth: ComponentHealth[] = [
  {
    name: 'Binance API',
    status: 'healthy',
    latency: 85,
    errorRate: 0.1,
    lastCheck: '5秒前',
  },
  {
    name: 'News Feed',
    status: 'warning',
    latency: 320,
    errorRate: 2.5,
    lastCheck: '10秒前',
  },
  {
    name: 'Fear & Greed',
    status: 'healthy',
    latency: 120,
    errorRate: 0,
    lastCheck: '15秒前',
  },
  {
    name: 'Social Media',
    status: 'critical',
    latency: 0,
    errorRate: 100,
    lastCheck: '30秒前',
  },
]

const mockRiskPathways: RiskPathway[] = [
  {
    source: '数据源异常',
    target: '因子计算',
    severity: 0.8,
    description: '社交媒体API延迟导致情绪因子过期',
  },
  {
    source: '因子计算',
    target: '信号生成',
    severity: 0.6,
    description: '缺少情绪因子导致信号置信度下降',
  },
  {
    source: '信号生成',
    target: '仓位管理',
    severity: 0.4,
    description: '置信度降低导致开仓规模减少50%',
  },
]

export function RiskPropagationPage() {
  const [activeTab, setActiveTab] = useState('timeline')
  const [loading, setLoading] = useState(true)
  const [riskEvents, setRiskEvents] = useState<RiskEvent[]>([])
  const [componentHealth, setComponentHealth] = useState<ComponentHealth[]>([])
  const [riskPathways, setRiskPathways] = useState<RiskPathway[]>([])
  const [riskMetrics, setRiskMetrics] = useState<{
    activeEvents: number
    healthyComponents: number
    totalComponents: number
    avgLatency: number
    riskExposure: number
  } | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    if (isMockMode) {
      setRiskEvents(mockRiskEvents)
      setComponentHealth(mockComponentHealth)
      setRiskPathways(mockRiskPathways)
      setRiskMetrics({
        activeEvents: 2,
        healthyComponents: 2,
        totalComponents: 4,
        avgLatency: 131,
        riskExposure: 32,
      })
      setLoading(false)
      return
    }

    try {
      const [eventsRes, healthRes, pathwaysRes, metricsRes] = await Promise.all([
        api.get('/risk/events'),
        api.get('/risk/components'),
        api.get('/risk/pathways'),
        api.get('/risk/metrics'),
      ])
      if (eventsRes.data && Array.isArray(eventsRes.data)) {
        setRiskEvents(eventsRes.data)
      }
      if (healthRes.data && Array.isArray(healthRes.data)) {
        setComponentHealth(healthRes.data)
      }
      if (pathwaysRes.data && Array.isArray(pathwaysRes.data)) {
        setRiskPathways(pathwaysRes.data)
      }
      if (metricsRes.data) {
        setRiskMetrics(metricsRes.data)
      }
    } catch (error) {
      console.error('Failed to load risk data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'green'
      case 'warning':
        return 'orange'
      case 'critical':
        return 'red'
      default:
        return 'default'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <SafetyOutlined />
      case 'warning':
        return <WarningOutlined />
      case 'critical':
        return <ThunderboltOutlined />
      default:
        return <ClockCircleOutlined />
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  const activeEvents = riskMetrics?.activeEvents ?? riskEvents.filter(e => e.level === 'error' || e.level === 'warning').length
  const healthyComponents = riskMetrics?.healthyComponents ?? componentHealth.filter(c => c.status === 'healthy').length
  const totalComponents = riskMetrics?.totalComponents ?? componentHealth.length
  const avgLatency = riskMetrics?.avgLatency ?? Math.round(componentHealth.reduce((sum, c) => sum + c.latency, 0) / componentHealth.length)
  const riskExposure = riskMetrics?.riskExposure ?? 32

  return (
    <div className="space-y-4">
      <Title level={4}>⚠️ 风险传播链</Title>
      <Card.Meta
        title={<span style={{ fontSize: 16, fontWeight: 600 }}>风险传播监控系统</span>}
        description={
          <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            <p style={{ marginBottom: 4 }}>• 追踪风险从数据源到仓位的传播路径</p>
            <p style={{ marginBottom: 4 }}>• 提供完整的风险可视化和影响分析</p>
            <p style={{ marginBottom: 0 }}>• 自动触发风险缓解措施和告警通知</p>
          </div>
        }
        style={{ marginBottom: 16 }}
      />

      <Row gutter={16}>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="活跃风险事件"
              value={activeEvents}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#EF4444' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="健康组件"
              value={healthyComponents}
              suffix={`/${totalComponents}`}
              prefix={<SafetyOutlined />}
              valueStyle={{ color: '#10B981' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="平均延迟"
              value={avgLatency}
              suffix="ms"
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#3B82F6' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="风险敞口"
              value={riskExposure}
              suffix="%"
              prefix={<DollarOutlined />}
              valueStyle={{ color: '#F59E0B' }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane
            tab={
              <span>
                <ClockCircleOutlined />
                事件时间线
              </span>
            }
            key="timeline"
          >
            {riskEvents.length === 0 ? (
              <Empty description="暂无风险事件" />
            ) : (
              <Timeline
                mode="left"
                items={riskEvents.map((event) => ({
                  color: event.level === 'error' ? 'red' : event.level === 'warning' ? 'orange' : 'green',
                  children: (
                    <div>
                      <div className="flex justify-between">
                        <Text strong style={{ fontSize: 14 }}>
                          {event.event}
                        </Text>
                        <Tag color={getStatusColor(event.level === 'error' ? 'critical' : event.level)}>
                          {event.component}
                        </Tag>
                      </div>
                      <Text type="secondary" className="block mt-1">
                        {event.message}
                      </Text>
                      <Text type="secondary" className="text-xs block mt-1">
                        影响: {event.impact}
                      </Text>
                      <Text type="secondary" className="text-xs block">
                        {event.timestamp}
                      </Text>
                    </div>
                  ),
                }))}
              />
            )}
          </TabPane>

          <TabPane
            tab={
              <span>
                <SafetyOutlined />
                组件状态
              </span>
            }
            key="components"
          >
            {componentHealth.length === 0 ? (
              <Empty description="暂无组件状态" />
            ) : (
              <List
                itemLayout="horizontal"
                dataSource={componentHealth}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={
                        <div
                          style={{
                            fontSize: 24,
                            color:
                              item.status === 'healthy'
                                ? '#10B981'
                                : item.status === 'warning'
                                ? '#F59E0B'
                                : '#EF4444',
                          }}
                        >
                          {getStatusIcon(item.status)}
                        </div>
                      }
                      title={
                        <Space>
                          <Text strong>{item.name}</Text>
                          <Tag color={getStatusColor(item.status)}>
                            {item.status === 'healthy' ? '正常' : item.status === 'warning' ? '警告' : '严重'}
                          </Tag>
                        </Space>
                      }
                      description={
                        <div className="mt-2 space-y-2">
                          <div className="flex justify-between text-sm">
                            <Text type="secondary">延迟: {item.latency}ms</Text>
                            <Text type="secondary">错误率: {item.errorRate}%</Text>
                          </div>
                          <Progress
                            percent={item.status === 'healthy' ? 95 : item.status === 'warning' ? 60 : 20}
                            strokeColor={
                              item.status === 'healthy' ? '#10B981' : item.status === 'warning' ? '#F59E0B' : '#EF4444'
                            }
                            trailColor="#1E293B"
                            size="small"
                          />
                          <Text type="secondary" className="text-xs">
                            最后检查: {item.lastCheck}
                          </Text>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </TabPane>

          <TabPane
            tab={
              <span>
                <LinkOutlined />
                传播路径
              </span>
            }
            key="pathways"
          >
            {riskPathways.length === 0 ? (
              <Empty description="暂无风险传播路径" />
            ) : (
              <div className="space-y-6">
                {riskPathways.map((pathway, index) => (
                  <Card size="small" key={index}>
                    <div className="flex items-center gap-4">
                      <div className="flex-1">
                        <Tag color="blue">{pathway.source}</Tag>
                      </div>
                      <ThunderboltOutlined style={{ color: '#F59E0B', fontSize: 20 }} />
                      <div className="flex-1">
                        <Tag color="orange">{pathway.target}</Tag>
                      </div>
                      <div className="w-24">
                        <Progress
                          percent={pathway.severity * 100}
                          strokeColor="#EF4444"
                          trailColor="#1E293B"
                          size="small"
                          format={(percent) => `${(percent || 0) / 10}x`}
                        />
                      </div>
                    </div>
                    <div className="mt-3 text-sm text-gray-400">
                      {pathway.description}
                    </div>
                  </Card>
                ))}

                {activeEvents > 0 && (
                  <Alert
                    message="风险缓解措施已激活"
                    description="系统已自动降低仓位50%，并禁用低置信度因子。"
                    type="success"
                    showIcon
                  />
                )}
              </div>
            )}
          </TabPane>
        </Tabs>
      </Card>
    </div>
  )
}
