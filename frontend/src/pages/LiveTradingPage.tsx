import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Button, InputNumber, Select, Switch, Progress, Statistic, Badge, Modal, message, Spin } from 'antd'
import {
  Target,
  Zap,
  Shield,
  AlertTriangle,
  Clock,
  DollarSign,
  Settings,
  RefreshCw,
} from 'lucide-react'
import {
  useRuntime,
  useSignalsState,
  usePnLState,
  useRiskState,
} from '../services/runtime'
import { api } from '../services/api/client'
import type { Position } from '../../types'
import clsx from 'clsx'
import { isMockMode } from '../config/mock'

interface TradingSignal {
  signal_id: string
  strategy_name: string
  symbol: string
  action: 'ENTER' | 'EXIT'
  confidence: number
  price: number
  suggested_sl: number
  suggested_tp: number
  suggested_rr: number
  suggested_leverage: number
  features: Record<string, number>
  expires_at: string
}

interface TradingConfig {
  auto_follow: boolean
  max_position_size: number
  max_leverage: number
  default_sl_percent: number
  default_tp_percent: number
  risk_per_trade: number
}

export function LiveTradingPage() {
  const { isConnected, isLive, isPaper } = useRuntime()
  const signalsState = useSignalsState()
  const pnlState = usePnLState()
  const riskState = useRiskState()

  const [signals, setSignals] = useState<TradingSignal[]>([])
  const [positions, setPositions] = useState<Position[]>([])
  const [accountBalance, setAccountBalance] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [config, setConfig] = useState<TradingConfig>({
    auto_follow: false,
    max_position_size: 1000,
    max_leverage: 10,
    default_sl_percent: 2,
    default_tp_percent: 6,
    risk_per_trade: 1,
  })
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null)
  const [tradeModalVisible, setTradeModalVisible] = useState(false)
  const [tradeSize, setTradeSize] = useState(0.01)
  const [tradeLeverage, setTradeLeverage] = useState(5)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [signalsRes, positionsRes, accountRes] = await Promise.all([
        api.get('/execution/signals'),
        api.get('/execution/positions'),
        api.get('/account/balance'),
      ])
      if (signalsRes.data && Array.isArray(signalsRes.data)) {
        setSignals(signalsRes.data)
      }
      if (positionsRes.data && Array.isArray(positionsRes.data)) {
        setPositions(positionsRes.data)
      }
      if (accountRes.data?.balance !== undefined) {
        setAccountBalance(accountRes.data.balance)
      }
    } catch (error) {
      console.error('Failed to load trading data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFollowSignal = (signal: TradingSignal) => {
    setSelectedSignal(signal)
    setTradeLeverage(signal.suggested_leverage)
    setTradeModalVisible(true)
  }

  const handleExecuteTrade = async () => {
    if (!selectedSignal) return
    
    try {
      await api.post('/execution/orders', {
        symbol: selectedSignal.symbol,
        side: selectedSignal.action === 'ENTER' ? 'buy' : 'sell',
        quantity: tradeSize,
        leverage: tradeLeverage,
        order_type: 'market',
      })
      message.success('订单执行成功！')
      setTradeModalVisible(false)
      loadData()
    } catch (error) {
      message.error('订单执行失败')
    }
  }

  const formatTimeLeft = (expiresAt: string) => {
    const diff = new Date(expiresAt).getTime() - Date.now()
    const minutes = Math.floor(diff / 60000)
    const seconds = Math.floor((diff % 60000) / 1000)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const totalPnL = pnlState?.total?.total || 0
  const unrealizedPnL = pnlState?.total?.unrealized || 0
  const performance = pnlState?.performance
  const riskScore = riskState?.score || 0

  if (loading && !signalsState) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">跟随交易</h1>
          <p className="text-text-secondary text-sm mt-1">跟随策略信号一键交易</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">自动跟随</span>
            <Switch
              checked={config.auto_follow}
              onChange={(checked) => setConfig({ ...config, auto_follow: checked })}
            />
          </div>
          <Button icon={<Settings className="w-4 h-4" />}>设置</Button>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">账户余额</span>}
              value={accountBalance ?? (isMockMode ? 10452.50 : 0)}
              precision={2}
              prefix={<DollarSign className="w-4 h-4 text-bullish" />}
              valueStyle={{ color: 'var(--text-primary)', fontSize: '24px' }}
            />
            <div className={clsx('mt-2 text-xs', totalPnL >= 0 ? 'text-bullish' : 'text-bearish')}>
              今日 {totalPnL >= 0 ? '+' : ''}{(totalPnL * 100).toFixed(2)}%
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">持仓数量</span>}
              value={positions.length}
              prefix={<Target className="w-4 h-4 text-primary" />}
              valueStyle={{ color: 'var(--text-primary)', fontSize: '24px' }}
            />
            <div className="text-xs text-text-secondary">
              未实现盈亏: {unrealizedPnL >= 0 ? '+' : ''}${unrealizedPnL.toFixed(2)}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">风险占用</span>}
              value={(riskScore * 100).toFixed(1)}
              suffix="%"
              prefix={<Shield className="w-4 h-4 text-warning" />}
              valueStyle={{ color: 'var(--text-primary)', fontSize: '24px' }}
            />
            <Progress percent={riskScore * 100} showInfo={false} size="small" strokeColor="var(--warning)" />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">活跃信号</span>
                <Badge count={signals.length} className="ml-2" />
              </div>
            }
            extra={<Button size="small" icon={<RefreshCw className="w-3 h-3" />} onClick={loadData} />}
          >
            <div className="space-y-4">
              {signals.length === 0 ? (
                <div className="py-8 text-center text-text-secondary">
                  暂无活跃信号，等待策略触发...
                </div>
              ) : (
                signals.map((signal) => (
                  <div
                    key={signal.signal_id}
                    className="p-4 bg-background rounded-lg border border-border hover:border-primary/30 transition-all"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Tag className={clsx('text-xs font-bold border-0', signal.action === 'ENTER' ? 'bg-bullish text-background' : 'bg-bearish text-background')}>
                            {signal.action === 'ENTER' ? '入场' : '离场'}
                          </Tag>
                          <span className="font-medium text-text-primary">{signal.strategy_name}</span>
                          <Tag className="text-[10px] bg-primary/10 text-primary border-0">{signal.symbol}</Tag>
                        </div>
                        <div className="text-xs text-text-secondary">
                          价格: ${signal.price.toLocaleString()}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-bullish">
                          {(signal.confidence * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-text-secondary">置信度</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-3 text-xs">
                      <div>
                        <span className="text-text-secondary">止损:</span>
                        <span className="text-bearish ml-1">${signal.suggested_sl.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">止盈:</span>
                        <span className="text-bullish ml-1">${signal.suggested_tp.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">盈亏比:</span>
                        <span className="text-primary ml-1">{signal.suggested_rr}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-3 border-t border-border">
                      <div className="flex items-center gap-2 text-xs text-text-secondary">
                        <Clock className="w-3 h-3" />
                        <span>剩余 {formatTimeLeft(signal.expires_at)}</span>
                      </div>
                      <Button
                        type="primary"
                        icon={<Target className="w-3 h-3" />}
                        onClick={() => handleFollowSignal(signal)}
                      >
                        跟随
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            className="bg-surface border-border"
            title={
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">当前持仓</span>
              </div>
            }
          >
            {positions.length === 0 ? (
              <div className="py-8 text-center text-text-secondary">
                暂无持仓
              </div>
            ) : (
              <div className="space-y-3">
                {positions.map((position) => (
                  <div
                    key={position.symbol}
                    className="p-4 bg-background rounded-lg border border-border"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Tag className={clsx('text-xs border-0', position.side === 'LONG' ? 'bg-bullish/20 text-bullish' : 'bg-bearish/20 text-bearish')}>
                          {position.side === 'LONG' ? '多' : '空'}
                        </Tag>
                        <span className="font-medium text-text-primary">{position.symbol}</span>
                      </div>
                      <div className={clsx('text-sm font-bold', position.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {position.pnl >= 0 ? '+' : ''}{position.pnlPct?.toFixed(2) || '0.00'}%
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-text-secondary">仓位:</span>{' '}
                        <span className="text-text-primary">{position.size}</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">杠杆:</span>{' '}
                        <span className="text-text-primary">{position.leverage || 1}x</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">开仓价:</span>{' '}
                        <span className="text-text-primary">${position.entryPrice?.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">盈亏:</span>{' '}
                        <span className={position.pnl >= 0 ? 'text-bullish' : 'text-bearish'}>
                          {position.pnl >= 0 ? '+' : ''}${position.pnl.toFixed(2)}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button size="small" danger>平仓</Button>
                      <Button size="small">修改止损止盈</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="bg-surface border-border mt-4" title={<span className="text-sm font-medium">风险设置</span>}>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-secondary">最大仓位</span>
                <span className="text-xs text-text-primary">${config.max_position_size}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-secondary">最大杠杆</span>
                <span className="text-xs text-text-primary">{config.max_leverage}x</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-secondary">单笔风险</span>
                <span className="text-xs text-text-primary">{config.risk_per_trade}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-secondary">默认止损</span>
                <span className="text-xs text-bearish">{config.default_sl_percent}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-secondary">默认止盈</span>
                <span className="text-xs text-bullish">{config.default_tp_percent}%</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Modal
        title={`跟随信号 - ${selectedSignal?.symbol}`}
        open={tradeModalVisible}
        onCancel={() => setTradeModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setTradeModalVisible(false)}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={handleExecuteTrade}>
            执行交易
          </Button>,
        ]}
      >
        {selectedSignal && (
          <div className="space-y-4">
            <div className="p-4 bg-background rounded-lg border border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-secondary">策略</span>
                <span className="text-sm font-medium text-text-primary">{selectedSignal.strategy_name}</span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-secondary">操作</span>
                <Tag className={selectedSignal.action === 'ENTER' ? 'bg-bullish text-background' : 'bg-bearish text-background'}>
                  {selectedSignal.action === 'ENTER' ? '入场' : '离场'}
                </Tag>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-secondary">入场价格</span>
                <span className="text-sm font-medium text-text-primary">${selectedSignal.price.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-secondary">止损</span>
                <span className="text-sm text-bearish">${selectedSignal.suggested_sl.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">止盈</span>
                <span className="text-sm text-bullish">${selectedSignal.suggested_tp.toLocaleString()}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs text-text-secondary mb-1">数量 (BTC)</label>
              <InputNumber
                value={tradeSize}
                onChange={(v) => setTradeSize(v || 0.01)}
                min={0.001}
                max={1}
                step={0.01}
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-xs text-text-secondary mb-1">杠杆</label>
              <Select
                value={tradeLeverage}
                onChange={setTradeLeverage}
                className="w-full"
                options={[1, 2, 3, 5, 8, 10, 15, 20].map((x) => ({ value: x, label: `${x}x` }))}
              />
            </div>

            <div className="p-3 bg-warning/10 rounded-lg border border-warning/30">
              <div className="flex items-center gap-2 text-warning text-xs">
                <AlertTriangle className="w-4 h-4" />
                <span>交易有风险，请谨慎操作。</span>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
