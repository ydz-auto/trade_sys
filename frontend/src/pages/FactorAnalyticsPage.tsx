import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Progress, Tabs, Typography, Tag, Space, Spin, Empty } from 'antd'
import { BarChartOutlined, LineChartOutlined, DotChartOutlined } from '@ant-design/icons'
import { api } from '../services/api/client'
import { isMockMode } from '../config/mock'

const { Title, Text } = Typography
const { TabPane } = Tabs

interface FactorData {
  factor: string
  shortName: string
  contribution: number
  weight: number
  correlation: number
  recentPnL: string
  volatility: number
  color: string
}

interface FactorMetrics {
  activeFactors: number
  totalContribution: number
  avgCorrelation: number
  riskAdjustedReturn: number
}

const mockFactorContributionData: FactorData[] = [
  {
    factor: '趋势因子',
    shortName: 'Trend',
    contribution: 2.3,
    weight: 0.3,
    correlation: 0.85,
    recentPnL: '+12.5%',
    volatility: 0.18,
    color: '#3B82F6',
  },
  {
    factor: '资金流因子',
    shortName: 'Flow',
    contribution: 1.8,
    weight: 0.25,
    correlation: 0.72,
    recentPnL: '+8.3%',
    volatility: 0.22,
    color: '#F59E0B',
  },
  {
    factor: '情绪因子',
    shortName: 'Sentiment',
    contribution: -0.5,
    weight: 0.2,
    correlation: 0.68,
    recentPnL: '-2.1%',
    volatility: 0.35,
    color: '#EC4899',
  },
  {
    factor: '宏观因子',
    shortName: 'Macro',
    contribution: 0.9,
    weight: 0.15,
    correlation: 0.55,
    recentPnL: '+5.2%',
    volatility: 0.12,
    color: '#10B981',
  },
]

const mockCorrelationMatrix = [
  [1.00, 0.45, 0.32, 0.18],
  [0.45, 1.00, 0.28, 0.35],
  [0.32, 0.28, 1.00, 0.15],
  [0.18, 0.35, 0.15, 1.00],
]

const mockMetrics: FactorMetrics = {
  activeFactors: 4,
  totalContribution: 4.5,
  avgCorrelation: 0.42,
  riskAdjustedReturn: 1.25,
}

export function FactorAnalyticsPage() {
  const [activeTab, setActiveTab] = useState('contribution')
  const [loading, setLoading] = useState(true)
  const [factorData, setFactorData] = useState<FactorData[]>([])
  const [correlationMatrix, setCorrelationMatrix] = useState<number[][]>([])
  const [metrics, setMetrics] = useState<FactorMetrics | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    if (isMockMode) {
      setFactorData(mockFactorContributionData)
      setCorrelationMatrix(mockCorrelationMatrix)
      setMetrics(mockMetrics)
      setLoading(false)
      return
    }

    try {
      const [factorsRes, correlationRes, metricsRes] = await Promise.all([
        api.get('/factor/contributions'),
        api.get('/factor/correlation'),
        api.get('/factor/metrics'),
      ])
      if (factorsRes.data && Array.isArray(factorsRes.data)) {
        setFactorData(factorsRes.data)
      }
      if (correlationRes.data && Array.isArray(correlationRes.data)) {
        setCorrelationMatrix(correlationRes.data)
      }
      if (metricsRes.data) {
        setMetrics(metricsRes.data)
      }
    } catch (error) {
      console.error('Failed to load factor data:', error)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: '因子',
      dataIndex: 'factor',
      key: 'factor',
      render: (text: string, record: FactorData) => (
        <Space>
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: 3,
              backgroundColor: record.color,
            }}
          />
          <Text strong>{text}</Text>
        </Space>
      ),
    },
    {
      title: '贡献',
      dataIndex: 'contribution',
      key: 'contribution',
      render: (value: number) => (
        <Text style={{ color: value >= 0 ? '#10B981' : '#EF4444' }}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
        </Text>
      ),
    },
    {
      title: '权重',
      dataIndex: 'weight',
      key: 'weight',
      render: (value: number) => `${(value * 100).toFixed(0)}%`,
    },
    {
      title: '相关性',
      dataIndex: 'correlation',
      key: 'correlation',
      render: (value: number) => (
        <Tag color={value > 0.7 ? 'green' : value > 0.5 ? 'blue' : 'orange'}>
          {value.toFixed(2)}
        </Tag>
      ),
    },
    {
      title: '近期盈亏',
      dataIndex: 'recentPnL',
      key: 'recentPnL',
      render: (value: string) => (
        <Text style={{ color: value.startsWith('+') ? '#10B981' : '#EF4444' }}>
          {value}
        </Text>
      ),
    },
    {
      title: '波动率',
      dataIndex: 'volatility',
      key: 'volatility',
      render: (value: number) => `${(value * 100).toFixed(1)}%`,
    },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  const activeFactors = metrics?.activeFactors ?? factorData.length
  const totalContribution = metrics?.totalContribution ?? factorData.reduce((sum, f) => sum + f.contribution, 0)
  const avgCorrelation = metrics?.avgCorrelation ?? 0.42
  const riskAdjustedReturn = metrics?.riskAdjustedReturn ?? 1.25

  return (
    <div className="space-y-4">
      <Title level={4}>📊 因子分析</Title>
      <Card.Meta
        title={<span style={{ fontSize: 16, fontWeight: 600 }}>因子分析系统</span>}
        description={
          <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            <p style={{ marginBottom: 4 }}>• 分析因子贡献、相关性、历史表现</p>
            <p style={{ marginBottom: 4 }}>• 帮助优化因子配置和权重分配</p>
            <p style={{ marginBottom: 0 }}>• 识别冗余因子，提高策略效率</p>
          </div>
        }
        style={{ marginBottom: 16 }}
      />

      <Row gutter={16}>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="活跃因子"
              value={activeFactors}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: '#3B82F6' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="总贡献"
              value={totalContribution}
              precision={1}
              prefix={totalContribution >= 0 ? '+' : ''}
              valueStyle={{ color: totalContribution >= 0 ? '#10B981' : '#EF4444' }}
              suffix="%"
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="平均相关性"
              value={avgCorrelation}
              precision={2}
              prefix={<DotChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="风险调整收益"
              value={riskAdjustedReturn}
              precision={2}
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
                <BarChartOutlined />
                因子贡献
              </span>
            }
            key="contribution"
          >
            {factorData.length === 0 ? (
              <Empty description="暂无因子数据" />
            ) : (
              <>
                <div className="mb-6">
                  <Title level={5}>因子贡献详情</Title>
                  <Table
                    dataSource={factorData}
                    columns={columns}
                    rowKey="factor"
                    pagination={false}
                  />
                </div>

                <div className="mt-6">
                  <Title level={5}>各因子贡献可视化</Title>
                  <div className="space-y-3">
                    {factorData.map((factor) => (
                      <div key={factor.factor}>
                        <div className="flex justify-between mb-1">
                          <Text strong>{factor.factor}</Text>
                          <Text
                            style={{
                              color: factor.contribution >= 0 ? '#10B981' : '#EF4444',
                            }}
                          >
                            {factor.contribution >= 0 ? '+' : ''}
                            {factor.contribution.toFixed(2)}
                          </Text>
                        </div>
                        <Progress
                          percent={Math.abs(factor.contribution * 40)}
                          strokeColor={factor.contribution >= 0 ? '#10B981' : '#EF4444'}
                          trailColor="#1E293B"
                          showInfo={false}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </TabPane>

          <TabPane
            tab={
              <span>
                <DotChartOutlined />
                相关性矩阵
              </span>
            }
            key="correlation"
          >
            {correlationMatrix.length === 0 ? (
              <Empty description="暂无相关性数据" />
            ) : (
              <>
                <div className="mb-4">
                  <Title level={5}>因子相关性分析</Title>
                  <Text type="secondary">
                    高相关性因子应该避免同时配置，以降低风险。
                  </Text>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-center border-collapse">
                    <thead>
                      <tr>
                        <th className="p-2 bg-gray-800 border border-gray-700"></th>
                        {factorData.map((factor, i) => (
                          <th
                            key={i}
                            className="p-2 bg-gray-800 border border-gray-700 text-sm"
                          >
                            {factor.shortName}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {correlationMatrix.map((row, i) => (
                        <tr key={i}>
                          <td className="p-2 bg-gray-800 border border-gray-700 font-semibold">
                            {factorData[i]?.shortName || ''}
                          </td>
                          {row.map((cell, j) => (
                            <td
                              key={j}
                              className="p-2 border border-gray-700"
                              style={{
                                backgroundColor:
                                  i === j
                                    ? '#3B82F6'
                                    : Math.abs(cell) > 0.7
                                    ? 'rgba(16, 184, 129, 0.3)'
                                    : Math.abs(cell) > 0.5
                                    ? 'rgba(245, 158, 11, 0.3)'
                                    : 'transparent',
                              }}
                            >
                              <Text
                                style={{
                                  color:
                                    i === j || Math.abs(cell) > 0.7
                                      ? 'white'
                                      : 'gray-400',
                                }}
                              >
                                {cell.toFixed(2)}
                              </Text>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </TabPane>

          <TabPane
            tab={
              <span>
                <LineChartOutlined />
                历史表现
              </span>
            }
            key="performance"
          >
            {factorData.length === 0 ? (
              <Empty description="暂无历史表现数据" />
            ) : (
              <div className="space-y-4">
                <Title level={5}>因子历史表现</Title>

                {factorData.map((factor) => (
                  <Card size="small" key={factor.factor}>
                    <div className="flex justify-between items-center mb-2">
                      <Text strong>{factor.factor}</Text>
                      <Tag color={factor.recentPnL.startsWith('+') ? 'green' : 'red'}>
                        {factor.recentPnL}
                      </Tag>
                    </div>
                    <div className="flex justify-between text-sm text-gray-500">
                      <span>波动率: {(factor.volatility * 100).toFixed(1)}%</span>
                      <span>权重: {(factor.weight * 100).toFixed(0)}%</span>
                    </div>
                    <div className="mt-2">
                      <Progress
                        percent={70 + factor.contribution * 20}
                        strokeColor={factor.color}
                        trailColor="#1E293B"
                        size="small"
                        showInfo={false}
                      />
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </TabPane>
        </Tabs>
      </Card>
    </div>
  )
}
