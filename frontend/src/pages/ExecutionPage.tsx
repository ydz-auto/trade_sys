import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Table, Timeline, Badge, Spin } from 'antd'
import { CheckCircleOutlined, SyncOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { fetchOrders } from '../services/api/tradingApi'

interface Order {
  order_id: string
  symbol: string
  status: string
  filled_quantity: number
  created_at: string
  side?: string
  order_type?: string
  price?: number
}

export function ExecutionPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadOrders()
    const interval = setInterval(loadOrders, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadOrders = async () => {
    try {
      const data = await fetchOrders()
      setOrders(data)
    } catch (error) {
      console.error('Failed to load orders:', error)
    } finally {
      setLoading(false)
    }
  }

  const statusMap: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    filled: { color: 'green', icon: <CheckCircleOutlined />, text: '已成交' },
    pending: { color: 'orange', icon: <SyncOutlined />, text: '处理中' },
    cancelled: { color: 'red', icon: <CloseCircleOutlined />, text: '已取消' },
    new: { color: 'blue', icon: <SyncOutlined />, text: '新订单' },
    partially_filled: { color: 'orange', icon: <SyncOutlined />, text: '部分成交' },
  }

  const orderColumns = [
    {
      title: '订单ID',
      dataIndex: 'order_id',
      key: 'order_id',
      render: (id: string) => <span className="font-mono text-xs">{id}</span>,
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
      render: (side: string) => (
        <Tag color={side === 'BUY' ? 'green' : side === 'SELL' ? 'red' : 'default'}>
          {side || '-'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const s = statusMap[status.toLowerCase()] || statusMap.pending
        return (
          <Tag color={s.color} icon={s.icon}>
            {s.text}
          </Tag>
        )
      },
    },
    {
      title: '成交数量',
      dataIndex: 'filled_quantity',
      key: 'filled_quantity',
      render: (qty: number) => <span className="font-mono">{qty?.toFixed(4) || 0}</span>,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => <span className="text-[#94A3B8] text-xs">{time || '-'}</span>,
    },
  ]

  const filledCount = orders.filter(o => o.status?.toLowerCase() === 'filled').length
  const pendingCount = orders.filter(o => ['pending', 'new'].includes(o.status?.toLowerCase())).length
  const failedCount = orders.filter(o => o.status?.toLowerCase() === 'cancelled').length

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="执行追踪" className="!bg-[#1E293B] !border-[#334155]">
            {loading ? (
              <div className="flex justify-center p-8">
                <Spin />
              </div>
            ) : (
              <Table
                dataSource={orders}
                columns={orderColumns}
                pagination={false}
                rowKey="order_id"
                scroll={{ x: 800 }}
                locale={{ emptyText: '暂无订单数据' }}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="执行日志" className="!bg-[#1E293B] !border-[#334155]">
            <Timeline
              items={orders.slice(0, 4).map((order) => ({
                color: order.status?.toLowerCase() === 'filled' ? 'green' : 
                       order.status?.toLowerCase() === 'cancelled' ? 'red' : 'orange',
                children: (
                  <div>
                    <div className="font-medium">
                      {order.status?.toLowerCase() === 'filled' ? '订单已成交' : 
                       order.status?.toLowerCase() === 'cancelled' ? '订单已取消' : '订单处理中'}
                    </div>
                    <div className="text-xs text-[#94A3B8]">{order.symbol}</div>
                    <div className="text-xs text-[#94A3B8]">{order.created_at || '-'}</div>
                  </div>
                ),
              })) || []}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={8}>
          <Card title="执行统计" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">今日成交</span>
                <Badge status="success" text={<span className="text-[#10B981]">{filledCount} 笔</span>} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">待处理</span>
                <Badge status="processing" text={<span className="text-[#F97316]">{pendingCount} 笔</span>} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">失败</span>
                <Badge status="error" text={<span className="text-[#EF4444]">{failedCount} 笔</span>} />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="交易所状态" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">Binance</span>
                <Badge status="success" text={<span className="text-[#10B981]">正常</span>} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">OKX</span>
                <Badge status="success" text={<span className="text-[#10B981]">正常</span>} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">Bybit</span>
                <Badge status="warning" text={<span className="text-[#F97316]">延迟</span>} />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="重试机制" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">最大重试次数</span>
                <span className="font-mono">3</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">重试间隔</span>
                <span className="font-mono">5s</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">超时时间</span>
                <span className="font-mono">30s</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
