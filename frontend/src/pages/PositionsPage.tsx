import { useState } from 'react'
import { Card, Row, Col, Tag, Table, Button, message, Modal } from 'antd'
import { useTradingStore } from '../store/tradingStore'
import { closePosition } from '../services/api/tradingApi'

export function PositionsPage() {
  const { positions, prices } = useTradingStore()
  const [loading, setLoading] = useState<string | null>(null)
  const [confirmModal, setConfirmModal] = useState<{ visible: boolean; position?: typeof positions[0] }>({ visible: false })

  const handleClosePosition = async (position: typeof positions[0]) => {
    setConfirmModal({ visible: true, position })
  }

  const confirmClosePosition = async () => {
    if (!confirmModal.position) return
    
    setLoading(confirmModal.position.symbol)
    try {
      const result = await closePosition(confirmModal.position.symbol)
      if (result.success) {
        message.success(`平仓成功: ${confirmModal.position.symbol}`)
      } else {
        message.error(`平仓失败: ${result.error || '未知错误'}`)
      }
    } catch (error) {
      message.error('平仓请求失败')
    } finally {
      setLoading(null)
      setConfirmModal({ visible: false })
    }
  }

  const getCurrentPrice = (symbol: string) => {
    const baseSymbol = symbol.split('/')[0]
    const price = prices.find(p => p.symbol === baseSymbol || p.symbol === symbol)
    return price?.price || 0
  }

  const columns = [
    {
      title: '交易对',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (symbol: string) => <span className="font-medium">{symbol}</span>,
    },
    {
      title: '方向',
      dataIndex: 'side',
      key: 'side',
      render: (side: string) => (
        <Tag color={side === 'LONG' ? 'green' : side === 'SHORT' ? 'red' : 'default'}>
          {side}
        </Tag>
      ),
    },
    {
      title: '仓位',
      dataIndex: 'size',
      key: 'size',
      render: (size: number, record: typeof positions[0]) => (
        <span className="font-mono">{size} {record.symbol.split('/')[0]}</span>
      ),
    },
    {
      title: '杠杆',
      dataIndex: 'leverage',
      key: 'leverage',
      render: (leverage: number) => <span className="font-mono">{leverage}x</span>,
    },
    {
      title: '入场价',
      dataIndex: 'entryPrice',
      key: 'entryPrice',
      render: (price: number) => <span className="font-mono">${price?.toLocaleString() || '-'}</span>,
    },
    {
      title: '当前价',
      key: 'currentPrice',
      render: (_: unknown, record: typeof positions[0]) => {
        const currentPrice = getCurrentPrice(record.symbol)
        return <span className="font-mono text-[#94A3B8]">${currentPrice?.toLocaleString() || '-'}</span>
      },
    },
    {
      title: '浮盈',
      dataIndex: 'pnl',
      key: 'pnl',
      render: (pnl: number) => (
        <span className={`font-mono font-bold ${pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
          {pnl >= 0 ? '+' : ''}${pnl}
        </span>
      ),
    },
    {
      title: '止损',
      dataIndex: 'stopLoss',
      key: 'stopLoss',
      render: (sl: number) => <span className="font-mono text-[#94A3B8]">${sl?.toLocaleString() || '-'}</span>,
    },
    {
      title: '止盈',
      dataIndex: 'takeProfit',
      key: 'takeProfit',
      render: (tp: number) => <span className="font-mono text-[#94A3B8]">${tp?.toLocaleString() || '-'}</span>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: typeof positions[0]) => (
        <Button 
          size="small" 
          danger={record.side !== 'NONE'}
          loading={loading === record.symbol}
          onClick={() => record.side !== 'NONE' ? handleClosePosition(record) : null}
        >
          {record.side === 'NONE' ? '开仓' : '平仓'}
        </Button>
      ),
    },
  ]

  const totalPnl = positions.reduce((sum, p) => sum + p.pnl, 0)
  const openPositions = positions.filter(p => p.side !== 'NONE')

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={24}>
          <Card
            title="仓位管理"
            extra={
              <div className="flex gap-2">
                <Tag color="green">总仓位: 18%</Tag>
                <Tag color="blue">可用: 82%</Tag>
              </div>
            }
            className="!bg-[#1E293B] !border-[#334155]"
          >
            <Table
              dataSource={positions}
              columns={columns}
              pagination={false}
              rowKey="symbol"
              scroll={{ x: 1200 }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="持仓统计" className="!bg-[#1E293B] !border-[#334155]">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">总浮盈</div>
                <div className={`font-mono text-lg ${totalPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                  {totalPnl >= 0 ? '+' : ''}${totalPnl}
                </div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">保证金</div>
                <div className="font-mono text-lg">$3,345</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">强平价</div>
                <div className="font-mono text-lg text-[#EF4444]">$58,200</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">收益率</div>
                <div className="font-mono text-lg text-[#10B981]">+3.9%</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="风险限制" className="!bg-[#1E293B] !border-[#334155]">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">最大仓位</div>
                <div className="font-mono text-lg">30%</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">最大杠杆</div>
                <div className="font-mono text-lg">3x</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">总持仓数</div>
                <div className="font-mono text-lg">{openPositions.length}</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 text-center">
                <div className="text-[#94A3B8] text-xs mb-1">风险敞口</div>
                <div className="font-mono text-lg">18%</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Modal
        title="确认平仓"
        open={confirmModal.visible}
        onOk={confirmClosePosition}
        onCancel={() => setConfirmModal({ visible: false })}
        okText="确认平仓"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <p>确定要平仓 <strong>{confirmModal.position?.symbol}</strong> 吗？</p>
        <p>当前仓位: {confirmModal.position?.size} | 浮盈: ${confirmModal.position?.pnl}</p>
      </Modal>
    </div>
  )
}
