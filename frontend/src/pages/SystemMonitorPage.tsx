import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Progress, Statistic, Table, Timeline, Badge, Typography } from 'antd'
import {
  CloudServerOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  SafetyOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'

const { Text } = Typography

interface ServiceStatus {
  name: string
  status: 'healthy' | 'degraded' | 'down'
  latency: number
  lastCheck: string
  uptime: string
}

interface CircuitBreaker {
  name: string
  state: 'closed' | 'open' | 'half-open'
  failureCount: number
  successCount: number
}

interface SystemMetric {
  name: string
  value: number | string
  unit?: string
  status: 'good' | 'warning' | 'error'
  icon?: React.ReactNode
}

const serviceStatusData: ServiceStatus[] = [
  { name: 'API Server', status: 'healthy', latency: 42, lastCheck: '刚刚', uptime: '99.8%' },
  { name: 'Data Service', status: 'healthy', latency: 68, lastCheck: '30秒前', uptime: '99.5%' },
  { name: 'Execution Service', status: 'healthy', latency: 120, lastCheck: '1分钟前', uptime: '99.2%' },
  { name: 'WebSocket Server', status: 'degraded', latency: 250, lastCheck: '2分钟前', uptime: '98.7%' },
  { name: 'Redis', status: 'healthy', latency: 2, lastCheck: '刚刚', uptime: '99.9%' },
  { name: 'PostgreSQL', status: 'healthy', latency: 8, lastCheck: '刚刚', uptime: '99.9%' },
]

const circuitBreakers: CircuitBreaker[] = [
  { name: 'Binance API', state: 'closed', failureCount: 0, successCount: 1247 },
  { name: 'News RSS', state: 'closed', failureCount: 1, successCount: 856 },
  { name: 'Fear & Greed', state: 'half-open', failureCount: 3, successCount: 120 },
  { name: 'Social API', state: 'open', failureCount: 12, successCount: 0 },
]

const riskEventLog = [
  { color: 'red', children: (
    <div>
      <div className="font-medium">熔断触发: Social API</div>
      <div className="text-xs text-[#94A3B8]">连续12次请求失败 - 暂停5分钟</div>
      <div className="text-xs text-[#94A3B8]">09:35:20</div>
    </div>
  )},
  { color: 'orange', children: (
    <div>
      <div className="font-medium">降级: WebSocket延迟上升</div>
      <div className="text-xs text-[#94A3B8]">从80ms增加到250ms，回退到轮询</div>
      <div className="text-xs text-[#94A3B8]">09:30:15</div>
    </div>
  )},
  { color: 'green', children: (
    <div>
      <div className="font-medium">服务恢复: Data Service</div>
      <div className="text-xs text-[#94A3B8]">重启完成，数据同步正常</div>
      <div className="text-xs text-[#94A3B8]">09:25:00</div>
    </div>
  )},
  { color: 'blue', children: (
    <div>
      <div className="font-medium">定期检查: 全服务健康</div>
      <div className="text-xs text-[#94A3B8]">所有服务响应时间在阈值内</div>
      <div className="text-xs text-[#94A3B8]">09:00:00</div>
    </div>
  )},
]

const systemMetrics: SystemMetric[] = [
  { name: 'WebSocket连接数', value: 1284, unit: '', status: 'good', icon: <ThunderboltOutlined /> },
  { name: 'Redis延迟', value: 2, unit: 'ms', status: 'good', icon: <ClockCircleOutlined /> },
  { name: 'API请求/秒', value: 847, unit: 'rps', status: 'good', icon: <ApiOutlined /> },
  { name: '错误率', value: 0.2, unit: '%', status: 'warning', icon: <WarningOutlined /> },
]

export function SystemMonitorPage() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const serviceColumns = [
    { title: '服务', dataIndex: 'name', key: 'name', render: (name: string) => <Text className="font-medium">{name}</Text> },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'healthy' ? 'green' : status === 'degraded' ? 'orange' : 'red'
        const icon = status === 'healthy' ? <CheckCircleOutlined /> : status === 'degraded' ? <WarningOutlined /> : <CloseCircleOutlined />
        return (
          <Tag color={color} icon={icon}>
            {status === 'healthy' ? '正常' : status === 'degraded' ? '降级' : '异常'}
          </Tag>
        )
      },
    },
    { title: '延迟', dataIndex: 'latency', key: 'latency', render: (lat: number) => <span className="font-mono text-[#94A3B8]">{lat}ms</span> },
    { title: '可用性', dataIndex: 'uptime', key: 'uptime', render: (uptime: string) => <span className="font-mono text-[#10B981]">{uptime}</span> },
  ]

  const circuitColumns = [
    { title: '熔断器', dataIndex: 'name', key: 'name', render: (name: string) => <Text className="font-medium">{name}</Text> },
    {
      title: '状态',
      dataIndex: 'state',
      key: 'state',
      render: (state: string) => {
        const color = state === 'closed' ? 'green' : state === 'half-open' ? 'orange' : 'red'
        return (
          <Tag color={color}>
            {state === 'closed' ? '关闭（正常）' : state === 'half-open' ? '半开放（恢复中）' : '开放（熔断）'}
          </Tag>
        )
      },
    },
    { title: '失败', dataIndex: 'failureCount', key: 'failureCount', render: (cnt: number) => <span className="font-mono text-[#EF4444]">{cnt}</span> },
    { title: '成功', dataIndex: 'successCount', key: 'successCount', render: (cnt: number) => <span className="font-mono text-[#10B981]">{cnt}</span> },
  ]

  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {systemMetrics.map((metric, idx) => (
          <Col xs={12} md={6} key={idx}>
            <Card className="!bg-[#1E293B] !border-[#334155]">
              <Statistic
                title={<span className="text-[#94A3B8] text-xs flex items-center gap-1">{metric.icon} {metric.name}</span>}
                value={metric.value}
                suffix={metric.unit}
                valueStyle={{
                  color: metric.status === 'good' ? '#10B981' : metric.status === 'warning' ? '#F97316' : '#EF4444',
                  fontSize: '1.25rem',
                  fontWeight: 600,
                }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={14}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm">
                <CloudServerOutlined className="text-[#3B82F6]" />
                服务健康状态
              </span>
            }
            className="!bg-[#1E293B] !border-[#334155]"
          >
            <Table
              dataSource={serviceStatusData}
              columns={serviceColumns}
              pagination={false}
              rowKey="name"
              size="small"
            />
          </Card>
        </Col>

        <Col xs={24} md={10}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm">
                <SafetyOutlined className="text-[#8B5CF6]" />
                熔断器状态
              </span>
            }
            className="!bg-[#1E293B] !border-[#334155]"
          >
            <Table
              dataSource={circuitBreakers}
              columns={circuitColumns}
              pagination={false}
              rowKey="name"
              size="small"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm">
                <ClockCircleOutlined className="text-[#F59E0B]" />
                系统事件日志
              </span>
            }
            className="!bg-[#1E293B] !border-[#334155]"
          >
            <Timeline items={riskEventLog} />
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm">
                <ApiOutlined className="text-[#10B981]" />
                API 限制状态
              </span>
            }
            className="!bg-[#1E293B] !border-[#334155]"
          >
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-[#94A3B8]">Binance API</span>
                  <span className="text-xs font-mono text-[#10B981]">78% 剩余</span>
                </div>
                <Progress percent={22} strokeColor="#10B981" trailColor="#334155" size="small" showInfo={false} />
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-[#94A3B8]">News API</span>
                  <span className="text-xs font-mono text-[#F59E0B]">45% 剩余</span>
                </div>
                <Progress percent={55} strokeColor="#F59E0B" trailColor="#334155" size="small" showInfo={false} />
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-[#94A3B8]">Fear & Greed API</span>
                  <span className="text-xs font-mono text-[#EF4444]">12% 剩余</span>
                </div>
                <Progress percent={88} strokeColor="#EF4444" trailColor="#334155" size="small" showInfo={false} />
              </div>
              <div className="bg-[#0F172A] rounded p-3 mt-4">
                <div className="text-xs text-[#94A3B8] mb-1">重置倒计时</div>
                <div className="font-mono text-lg text-[#F8FAFC]">00:24:35</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
