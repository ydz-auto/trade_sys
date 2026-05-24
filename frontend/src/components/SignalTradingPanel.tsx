import { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Button,
  Tag,
  Table,
  Statistic,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tooltip,
  Alert,
  Spin,
} from 'antd'
import {
  ShoppingCartOutlined,
  CheckCircleOutlined,
  XOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import { TrendingUp, TrendingDown, Zap } from 'lucide-react'
import { useRuntime, useSignalsState, usePnLState, useRuntimeStatus } from '../services/runtime'
import {
  executeSignal,
  getPositions,
  getOpenOrders,
  type SignalAction,
  type Position,
  type Order,
  type ExchangeType,
} from '../services/api/executionApi'
import type { FeatureValue } from '../types'

const { Option } = Select
const { TextArea } = Input

const EXCHANGES: { value: ExchangeType; label: string }[] = [
  { value: 'binance', label: 'Binance' },
  { value: 'okx', label: 'OKX' },
]

export function SignalTradingPanel() {
  const { isLive, isPaper } = useRuntime()
  const signalsState = useSignalsState()
  const pnlState = usePnLState()
  const runtimeStatus = useRuntimeStatus()
  
  const [positions, setPositions] = useState<Position[]>([])
  const [openOrders, setOpenOrders] = useState<Order[]>([])
  const [signalModalVisible, setSignalModalVisible] = useState(false)
  const [selectedSignal, setSelectedSignal] = useState<SignalsState['latest'][string][number] | null>(null)
  const [selectedExchange, setSelectedExchange] = useState<ExchangeType>('binance')
  const [loading, setLoading] = useState(false)
  const [tradeMessage, setTradeMessage] = useState('')

  useEffect(() => {
    loadPositionsAndOrders()
  }, [])

  useEffect(() => {
    // 监听信号变化，自动刷新
    if (signalsState) {
      loadPositionsAndOrders()
    }
  }, [signalsState])

  const loadPositionsAndOrders = async () => {
    try {
      const [pos, orders] = await Promise.all([getPositions(), getOpenOrders()])
      setPositions(pos)
      setOpenOrders(orders)
    } catch (error) {
      console.error('Failed to load positions/orders:', error)
    }
  }

  const handleExecuteSignal = async (signal: SignalsState['latest'][string][number]) => {
    setSelectedSignal(signal)
    setSignalModalVisible(true)
  }

  const handleConfirmTrade = async (values: any) => {
    if (!selectedSignal) return
    
    setLoading(true)
    try {
      const action: SignalAction = {
        signalId: selectedSignal.signalId,
        strategyId: selectedSignal.strategyId,
        symbol: selectedSignal.symbol,
        exchange: values.exchange || selectedExchange,
        action: selectedSignal.action === 'BUY' ? 'OPEN_LONG' : selectedSignal.action === 'SELL' ? 'OPEN_SHORT' : 'CLOSE',
        leverage: values.leverage || 1,
        confidence: selectedSignal.confidence,
      }

      if (values.stopLoss) {
        action.stopLoss = parseFloat(values.stopLoss)
      }

      if (values.takeProfit) {
        action.takeProfit = parseFloat(values.takeProfit)
      }

      await executeSignal(action)
      setTradeMessage(`订单已提交 [${values.exchange || selectedExchange}]: ${selectedSignal.action} ${selectedSignal.symbol}`)
      setSignalModalVisible(false)
      await loadPositionsAndOrders()
    } catch (error) {
      setTradeMessage('订单提交失败，请检查风控设置')
    } finally {
      setLoading(false)
    }
  }

  const getActionIcon = (action: string) => {
    if (action === 'BUY') return <TrendingUp className="text-green-500" size={16} />
    if (action === 'SELL') return <TrendingDown className="text-red-500" size={16} />
    return <ExclamationCircleOutlined className="text-gray-500" />
  }

  const getActionColor = (action: string) => {
    if (action === 'BUY') return 'green'
    if (action === 'SELL') return 'red'
    return 'default'
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'FILLED':
        return <CheckCircleOutlined className="text-green-500" />
      case 'CANCELLED':
      case 'REJECTED':
        return <XOutlined className="text-red-500" />
      case 'PENDING':
      case 'ACKED':
      case 'PARTIAL_FILL':
        return <ClockCircleOutlined className="text-yellow-500" />
      default:
        return null
    }
  }

  const getRuntimeTag = () => {
    if (isLive) return <Tag color="red">实盘交易</Tag>
    if (isPaper) return <Tag color="blue">模拟交易</Tag>
    return <Tag color="gray">回测模式</Tag>
  }

  const latestSignals = signalsState?.latest 
    ? Object.values(signalsState.latest).flat().slice(0, 5)
    : []

  return (
    <div className="space-y-4">
      {tradeMessage && (
        <Alert
          message={tradeMessage}
          type={tradeMessage.includes('失败') ? 'error' : 'success'}
          showIcon
          onClose={() => setTradeMessage('')}
        />
      )}

      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="最新策略信号" extra={getRuntimeTag()}>
            {latestSignals.length === 0 ? (
              <Alert message="暂无信号" type="info" />
            ) : (
              <Table
                dataSource={latestSignals}
                columns={[
                  {
                    title: '时间',
                    dataIndex: 'timestamp',
                    key: 'timestamp',
                    render: (t: string) => new Date(t).toLocaleTimeString(),
                  },
                  {
                    title: '交易对',
                    dataIndex: 'symbol',
                    key: 'symbol',
                  },
                  {
                    title: '信号',
                    dataIndex: 'action',
                    key: 'action',
                    render: (action: string) => (
                      <Tag color={getActionColor(action)} icon={getActionIcon(action)}>
                        {action}
                      </Tag>
                    ),
                  },
                  {
                    title: '置信度',
                    dataIndex: 'confidence',
                    key: 'confidence',
                    render: (c: number) => `${c}%`,
                  },
                  {
                    title: '策略',
                    dataIndex: 'strategyId',
                    key: 'strategyId',
                    render: (id: string) => <span className="text-xs text-gray-500">{id}</span>,
                  },
                  {
                    title: '操作',
                    key: 'actions',
                    render: (_, record) => (
                      <Button
                        type="primary"
                        icon={<Zap size={14} />}
                        size="small"
                        onClick={() => handleExecuteSignal(record)}
                      >
                        跟随信号
                      </Button>
                    ),
                  },
                ]}
                rowKey="signalId"
                size="small"
              />
            )}
          </Card>

          <Card title="当前仓位">
            {positions.length === 0 ? (
              <Alert message="暂无持仓" type="info" />
            ) : (
              <div className="space-y-3">
                {positions.map(pos => (
                  <div
                    key={pos.id}
                    className="flex items-center justify-between p-3 bg-gray-800 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <Tag color={pos.side === 'LONG' ? 'green' : 'red'}>
                        {pos.side}
                      </Tag>
                      <div>
                        <div className="font-medium">{pos.symbol}</div>
                        <div className="text-xs text-gray-500">
                          持仓量: {pos.quantity} | 杠杆: {pos.leverage}x
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={pos.unrealizedPnL >= 0 ? 'text-green-500' : 'text-red-500'}>
                        {pos.unrealizedPnL >= 0 ? '+' : ''}{pos.unrealizedPnL.toFixed(2)} USDT
                      </div>
                      <div className="text-xs text-gray-500">
                        开仓价: {pos.entryPrice}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="账户概览">
            <Row gutter={12}>
              <Col span={12}>
                <Statistic
                  title="持仓数量"
                  value={positions.length}
                  suffix="个"
                  valueStyle={{ color: '#3B82F6' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="挂单数量"
                  value={openOrders.length}
                  suffix="个"
                  valueStyle={{ color: '#F59E0B' }}
                />
              </Col>
              <Col span={24}>
                <Statistic
                  title="未实现盈亏"
                  value={pnlState?.positions.reduce((sum, p) => sum + p.unrealizedPnL, 0) || 0}
                  prefix="$"
                  precision={2}
                  valueStyle={{
                    color: (pnlState?.positions.reduce((sum, p) => sum + p.unrealizedPnL, 0) || 0) >= 0 ? '#10B981' : '#EF4444',
                  }}
                />
              </Col>
            </Row>
          </Card>

          <Card title="挂单列表">
            {openOrders.length === 0 ? (
              <Alert message="暂无挂单" type="info" />
            ) : (
              <Table
                dataSource={openOrders}
                columns={[
                  {
                    title: '状态',
                    dataIndex: 'status',
                    key: 'status',
                    render: (status: string) => getStatusIcon(status),
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
                    render: (s: string) => <Tag color={s === 'BUY' ? 'green' : 'red'}>{s}</Tag>,
                  },
                  {
                    title: '价格',
                    dataIndex: 'price',
                    key: 'price',
                    render: (p: number) => `$${p}`,
                  },
                ]}
                rowKey="id"
                size="small"
                pagination={false}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title={`跟随信号: ${selectedSignal?.action} ${selectedSignal?.symbol}`}
        open={signalModalVisible}
        onCancel={() => setSignalModalVisible(false)}
        footer={null}
        width={500}
      >
        <Spin spinning={loading}>
          {selectedSignal && (
            <>
              <Alert
                message={`策略: ${selectedSignal.strategyId}`}
                description={`置信度: ${selectedSignal.confidence}%`}
                type="info"
                showIcon
                className="mb-4"
              />

              <Form layout="vertical" onFinish={handleConfirmTrade}>
                <Form.Item
                  label="交易所"
                  name="exchange"
                  initialValue={selectedExchange}
                  rules={[{ required: true }]}
                >
                  <Select>
                    {EXCHANGES.map(exchange => (
                      <Option key={exchange.value} value={exchange.value}>
                        {exchange.label}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>

                <Form.Item
                  label="杠杆倍数"
                  name="leverage"
                  initialValue={10}
                  rules={[{ required: true }]}
                >
                  <Select>
                    <Option value={1}>1x</Option>
                    <Option value={5}>5x</Option>
                    <Option value={10}>10x</Option>
                    <Option value={20}>20x</Option>
                    <Option value={50}>50x</Option>
                  </Select>
                </Form.Item>

                <Form.Item label="止损价格 (可选)">
                  <Input name="stopLoss" placeholder="输入止损价格" />
                </Form.Item>

                <Form.Item label="止盈价格 (可选)">
                  <Input name="takeProfit" placeholder="输入止盈价格" />
                </Form.Item>

                <Form.Item>
                  <TextArea
                    rows={3}
                    placeholder="备注（可选）"
                    name="notes"
                  />
                </Form.Item>

                <Form.Item>
                  <Space>
                    <Button type="primary" htmlType="submit" icon={<ShoppingCartOutlined />} danger={isLive}>
                      {isLive ? '⚠️ 实盘下单' : isPaper ? '模拟下单' : '回测下单'}
                    </Button>
                    <Button onClick={() => setSignalModalVisible(false)}>取消</Button>
                  </Space>
                </Form.Item>
              </Form>
            </>
          )}
        </Spin>
      </Modal>
    </div>
  )
}

type SignalsState = {
  latest: Record<string, Array<{
    signalId: string
    strategyId: string
    symbol: string
    action: string
    confidence: number
    timestamp: string
    reason: string
  }>>
  history: Array<{
    signalId: string
    strategyId: string
    symbol: string
    action: string
    confidence: number
    timestamp: string
    reason: string
  }>
  summary: {
    total: number
    long: number
    short: number
    hold: number
    avgConfidence: number
  }
}
