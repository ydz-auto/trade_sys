import { Card, Row, Col, Tag, Table, Timeline, Badge } from 'antd'
import { CheckCircleOutlined, SyncOutlined, CloseCircleOutlined } from '@ant-design/icons'

export function ExecutionPage() {
  const orders = [
    {
      id: 'binance_123456',
      symbol: 'BTC/USDT',
      type: '市价开多',
      status: 'filled',
      filledPrice: 66500,
      filledQty: 0.18,
      time: '10:30:25',
    },
    {
      id: 'binance_123457',
      symbol: 'ETH/USDT',
      type: '限价开多',
      status: 'pending',
      filledPrice: 3800,
      filledQty: 0,
      time: '10:31:00',
    },
    {
      id: 'binance_123458',
      symbol: 'BTC/USDT',
      type: '止损触发',
      status: 'filled',
      filledPrice: 64000,
      filledQty: 0.18,
      time: '昨天 14:30:00',
    },
  ]

  const statusMap: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    filled: { color: 'green', icon: <CheckCircleOutlined />, text: '已成交' },
    pending: { color: 'orange', icon: <SyncOutlined />, text: '处理中' },
    cancelled: { color: 'red', icon: <CloseCircleOutlined />, text: '已取消' },
  }

  const orderColumns = [
    {
      title: '订单ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => <span className="font-mono text-xs">{id}</span>,
    },
    {
      title: '交易对',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const s = statusMap[status] || statusMap.pending
        return (
          <Tag color={s.color} icon={s.icon}>
            {s.text}
          </Tag>
        )
      },
    },
    {
      title: '成交价',
      dataIndex: 'filledPrice',
      key: 'filledPrice',
      render: (price: number) => <span className="font-mono">${price.toLocaleString()}</span>,
    },
    {
      title: '数量',
      dataIndex: 'filledQty',
      key: 'filledQty',
      render: (qty: number) => <span className="font-mono">{qty}</span>,
    },
    {
      title: '时间',
      dataIndex: 'time',
      key: 'time',
      render: (time: string) => <span className="text-[#94A3B8] text-xs">{time}</span>,
    },
  ]

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col span={16}>
          <Card title="执行追踪" className="!bg-[#1E293B] !border-[#334155]">
            <Table
              dataSource={orders}
              columns={orderColumns}
              pagination={false}
              rowKey="id"
            />
          </Card>
        </Col>

        <Col span={8}>
          <Card title="执行日志" className="!bg-[#1E293B] !border-[#334155]">
            <Timeline
              items={[
                {
                  color: 'green',
                  children: (
                    <div>
                      <div className="font-medium">订单已成交</div>
                      <div className="text-xs text-[#94A3B8]">BTC/USDT 市价开多 @ $66,500</div>
                      <div className="text-xs text-[#94A3B8]">10:30:25</div>
                    </div>
                  ),
                },
                {
                  color: 'orange',
                  children: (
                    <div>
                      <div className="font-medium">订单已提交</div>
                      <div className="text-xs text-[#94A3B8]">ETH/USDT 限价开多 @ $3,800</div>
                      <div className="text-xs text-[#94A3B8]">10:31:00</div>
                    </div>
                  ),
                },
                {
                  color: 'green',
                  children: (
                    <div>
                      <div className="font-medium">策略触发</div>
                      <div className="text-xs text-[#94A3B8]">BUY 信号确认，执行开仓</div>
                      <div className="text-xs text-[#94A3B8]">10:30:20</div>
                    </div>
                  ),
                },
                {
                  color: 'red',
                  children: (
                    <div>
                      <div className="font-medium">止损触发</div>
                      <div className="text-xs text-[#94A3B8]">BTC/USDT @ $64,000</div>
                      <div className="text-xs text-[#94A3B8]">昨天 14:30:00</div>
                    </div>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Card title="执行统计" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">今日成交</span>
                <Badge status="success" text={<span className="text-[#10B981]">12 笔</span>} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">待处理</span>
                <Badge status="processing" text={<span className="text-[#F97316]">2 笔</span>} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">失败</span>
                <Badge status="error" text={<span className="text-[#EF4444]">0 笔</span>} />
              </div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
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
        <Col span={8}>
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
