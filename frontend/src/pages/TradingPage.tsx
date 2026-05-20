import { useState, useEffect } from 'react'
import { Card, Row, Col, Button, Tag, Table, Statistic, Space, Form, Input, Select, Alert, Typography } from 'antd'
import { 
  TrendingUpOutlined, 
  TrendingDownOutlined, 
  ShoppingCartOutlined, 
  WalletOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { useRuntime } from '../services/runtime'
import { SignalTradingPanel } from '../components/SignalTradingPanel'
import { getPositions, getOrderHistory, type Position, type Order } from '../services/api/executionApi'

const { Title, Text } = Typography
const { Option } = Select

export function TradingPage() {
  const { isLive } = useRuntime()
  
  const [positions, setPositions] = useState<Position[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [pos, ords] = await Promise.all([getPositions(), getOrderHistory()])
      setPositions(pos)
      setOrders(ords)
    } catch (error) {
      console.error('Failed to load trading data:', error)
    }
  }

  const totalPnL = positions.reduce((sum, p) => sum + p.unrealizedPnL, 0)
  const totalMargin = positions.reduce((sum, p) => sum + p.margin, 0)

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <Title level={4}>
          {isLive ? (
            <span className="flex items-center gap-2">
              <BarChartOutlined /> 实盘交易
              <Tag color="red">LIVE</Tag>
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <BarChartOutlined /> 模拟交易
              <Tag color="blue">SIMULATION</Tag>
            </span>
          )}
        </Title>
      </div>

      <Alert
        message="交易说明"
        description="前端仅作为交易触发入口，所有订单需经过后端 Execution Runtime 执行。系统会自动进行风控校验和仓位约束。"
        type="info"
        showIcon
      />

      <SignalTradingPanel />

      <Card title="账户概览">
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Statistic
              title="持仓数量"
              value={positions.length}
              suffix="个"
              prefix={<WalletOutlined />}
              valueStyle={{ color: '#3B82F6' }}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title="占用保证金"
              value={totalMargin}
              prefix="$"
              precision={2}
              valueStyle={{ color: '#F59E0B' }}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title="未实现盈亏"
              value={totalPnL}
              prefix="$"
              precision={2}
              valueStyle={{ color: totalPnL >= 0 ? '#10B981' : '#EF4444' }}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title="盈亏比例"
              value={totalMargin > 0 ? (totalPnL / totalMargin * 100).toFixed(2) : 0}
              suffix="%"
              valueStyle={{ color: totalPnL >= 0 ? '#10B981' : '#EF4444' }}
            />
          </Col>
        </Row>
      </Card>

      <Card title="当前持仓">
        {positions.length === 0 ? (
          <Alert message="暂无持仓" type="info" />
        ) : (
          <Table
            dataSource={positions}
            columns={[
              {
                title: '交易对',
                dataIndex: 'symbol',
                key: 'symbol',
              },
              {
                title: '方向',
                dataIndex: 'side',
                key: 'side',
                render: (side: string) => (
                  <Tag color={side === 'LONG' ? 'green' : 'red'}>
                    {side === 'LONG' ? <><TrendingUpOutlined /> 多</> : <><TrendingDownOutlined /> 空</>}
                  </Tag>
                ),
              },
              {
                title: '数量',
                dataIndex: 'quantity',
                key: 'quantity',
              },
              {
                title: '杠杆',
                dataIndex: 'leverage',
                key: 'leverage',
                render: (lev: number) => `${lev}x`,
              },
              {
                title: '开仓价',
                dataIndex: 'entryPrice',
                key: 'entryPrice',
                render: (p: number) => `$${p.toFixed(2)}`,
              },
              {
                title: '当前价',
                dataIndex: 'markPrice',
                key: 'markPrice',
                render: (p?: number) => p ? `$${p.toFixed(2)}` : '-',
              },
              {
                title: '未实现盈亏',
                key: 'unrealizedPnL',
                render: (_, record: Position) => (
                  <Text className={record.unrealizedPnL >= 0 ? 'text-green-500' : 'text-red-500'}>
                    {record.unrealizedPnL >= 0 ? '+' : ''}${record.unrealizedPnL.toFixed(2)}
                  </Text>
                ),
              },
              {
                title: '强平价',
                dataIndex: 'liquidationPrice',
                key: 'liquidationPrice',
                render: (p?: number) => p ? <Text type="danger">${p.toFixed(2)}</Text> : '-',
              },
              {
                title: '操作',
                key: 'actions',
                render: () => (
                  <Space>
                    <Button size="small" type="primary">平仓</Button>
                    <Button size="small">调整SL/TP</Button>
                  </Space>
                ),
              },
            ]}
            rowKey="id"
          />
        )}
      </Card>

      <Card title="订单历史">
        {orders.length === 0 ? (
          <Alert message="暂无订单" type="info" />
        ) : (
          <Table
            dataSource={orders.slice(0, 20)}
            columns={[
              {
                title: '订单ID',
                dataIndex: 'id',
                key: 'id',
                render: (id: string) => <Text code className="text-xs">{id.slice(0, 8)}</Text>,
              },
              {
                title: '交易对',
                dataIndex: 'symbol',
                key: 'symbol',
              },
              {
                title: '方向',
                dataIndex: 'side',
                key: 'side',
                render: (s: string) => (
                  <Tag color={s === 'BUY' ? 'green' : 'red'}>{s}</Tag>
                ),
              },
              {
                title: '类型',
                dataIndex: 'type',
                key: 'type',
              },
              {
                title: '数量',
                dataIndex: 'quantity',
                key: 'quantity',
              },
              {
                title: '价格',
                dataIndex: 'price',
                key: 'price',
                render: (p?: number) => p ? `$${p.toFixed(2)}` : '-',
              },
              {
                title: '成交均价',
                dataIndex: 'avgFillPrice',
                key: 'avgFillPrice',
                render: (p?: number) => p ? `$${p.toFixed(2)}` : '-',
              },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                render: (status: string) => {
                  const colorMap: Record<string, string> = {
                    FILLED: 'green',
                    PARTIAL_FILL: 'yellow',
                    PENDING: 'blue',
                    CANCELLED: 'gray',
                    REJECTED: 'red',
                  }
                  return <Tag color={colorMap[status] || 'default'}>{status}</Tag>
                },
              },
              {
                title: '时间',
                dataIndex: 'createdAt',
                key: 'createdAt',
                render: (t: string) => new Date(t).toLocaleString(),
              },
            ]}
            rowKey="id"
          />
        )}
      </Card>
    </div>
  )
}

export default TradingPage
