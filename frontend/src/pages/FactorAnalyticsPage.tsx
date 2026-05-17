import { useState } from 'react'
import { Card, Row, Col, Statistic, Table, Progress, Tabs, Typography, Tag, Space, Alert } from 'antd'
import { BarChartOutlined, LineChartOutlined, DotChartOutlined } from '@ant-design/icons'

const { Title, Text } = Typography
const { TabPane } = Tabs

// 模拟因子数据
const factorContributionData = [
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

// 因子相关性矩阵
const correlationMatrix = [
  [1.00, 0.45, 0.32, 0.18],
  [0.45, 1.00, 0.28, 0.35],
  [0.32, 0.28, 1.00, 0.15],
  [0.18, 0.35, 0.15, 1.00],
]

export function FactorAnalyticsPage() {
  const [activeTab, setActiveTab] = useState('contribution')

  const columns = [
    {
      title: '因子',
      dataIndex: 'factor',
      key: 'factor',
      render: (text: string, record: any) => (
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

  return (
    <div className="space-y-4">
      <Title level={4}>📊 因子分析</Title>
      <Alert
        message="因子分析系统"
        description="分析因子贡献、相关性、历史表现，帮助优化因子配置。"
        type="info"
        showIcon
      />

      {/* 关键统计概览 */}
      <Row gutter={16}>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="活跃因子"
              value={4}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: '#3B82F6' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="总贡献"
              value={4.5}
              precision={1}
              prefix="+"
              valueStyle={{ color: '#10B981' }}
              suffix="%"
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="平均相关性"
              value={0.42}
              precision={2}
              prefix={<DotChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="风险调整收益"
              value={1.25}
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
            <div className="mb-6">
              <Title level={5}>因子贡献详情</Title>
              <Table
                dataSource={factorContributionData}
                columns={columns}
                rowKey="factor"
                pagination={false}
              />
            </div>

            <div className="mt-6">
              <Title level={5}>各因子贡献可视化</Title>
              <div className="space-y-3">
                {factorContributionData.map((factor) => (
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
                    {factorContributionData.map((factor, i) => (
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
                        {factorContributionData[i].shortName}
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
            <div className="space-y-4">
              <Title level={5}>因子历史表现</Title>

              {factorContributionData.map((factor) => (
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
          </TabPane>
        </Tabs>
      </Card>
    </div>
  )
}
