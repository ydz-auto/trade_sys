import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Table, Progress, Statistic, Badge, Tabs, Spin, Tooltip } from 'antd'
import {
  LineChart,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  BarChart3,
  Zap,
  AlertTriangle,
  RefreshCw,
  Clock,
} from 'lucide-react'
import { api } from '../services/api/client'
import clsx from 'clsx'

interface MarketData {
  symbol: string
  price: number
  change_24h: number
  volume_24h: number
  high_24h: number
  low_24h: number
}

interface FundingRate {
  symbol: string
  rate: number
  next_funding: string
  trend: 'rising' | 'falling' | 'stable'
}

interface OpenInterest {
  symbol: string
  oi: number
  oi_change_24h: number
  notional: number
}

interface Liquidation {
  id: string
  symbol: string
  side: 'LONG' | 'SHORT'
  price: number
  quantity: number
  value: number
  timestamp: string
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']

export function MarketMonitorPage() {
  const [marketData, setMarketData] = useState<MarketData[]>([])
  const [fundingRates, setFundingRates] = useState<FundingRate[]>([])
  const [openInterest, setOpenInterest] = useState<OpenInterest[]>([])
  const [liquidations, setLiquidations] = useState<Liquidation[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [marketRes, fundingRes, oiRes, liqRes] = await Promise.all([
        api.get('/market/tickers'),
        api.get('/market/funding'),
        api.get('/market/oi'),
        api.get('/market/liquidations'),
      ])
      if (marketRes.data) setMarketData(marketRes.data)
      if (fundingRes.data) setFundingRates(fundingRes.data)
      if (oiRes.data) setOpenInterest(oiRes.data)
      if (liqRes.data) setLiquidations(liqRes.data)
    } catch (error) {
      console.error('Failed to load market data:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number, decimals = 2) => {
    if (num >= 1e9) return (num / 1e9).toFixed(decimals) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(decimals) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(decimals) + 'K'
    return num.toFixed(decimals)
  }

  const getFundingColor = (rate: number) => {
    if (rate > 0.01) return 'text-bearish'
    if (rate < -0.01) return 'text-bullish'
    return 'text-text-secondary'
  }

  const liquidationColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 100,
      render: (t: string) => new Date(t).toLocaleTimeString(),
    },
    {
      title: '品种',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 100,
    },
    {
      title: '方向',
      dataIndex: 'side',
      key: 'side',
      width: 80,
      render: (side: string) => (
        <Tag className={clsx('text-xs border-0', side === 'LONG' ? 'bg-bullish/20 text-bullish' : 'bg-bearish/20 text-bearish')}>
          {side === 'LONG' ? '多' : '空'}
        </Tag>
      ),
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (p: number) => `$${p.toLocaleString()}`,
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 80,
      render: (q: number) => q.toFixed(4),
    },
    {
      title: '价值',
      dataIndex: 'value',
      key: 'value',
      width: 100,
      render: (v: number) => `$${formatNumber(v)}`,
    },
  ]

  if (loading) {
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
          <h1 className="text-2xl font-bold text-text-primary">市场监控</h1>
          <p className="text-text-secondary text-sm mt-1">实时行情、资金费率、持仓量、清算监控</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge status="success" text={<span className="text-xs text-text-secondary">实时更新</span>} />
          <button
            onClick={loadData}
            className="p-2 rounded-lg bg-surface border border-border hover:border-primary/30 transition-colors"
          >
            <RefreshCw className="w-4 h-4 text-text-secondary" />
          </button>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        {SYMBOLS.map((symbol) => {
          const data = marketData.find((d) => d.symbol === symbol) || {
            symbol,
            price: 0,
            change_24h: 0,
            volume_24h: 0,
            high_24h: 0,
            low_24h: 0,
          }
          const funding = fundingRates.find((f) => f.symbol === symbol) || {
            symbol,
            rate: 0,
            next_funding: '-',
            trend: 'stable',
          }
          const oi = openInterest.find((o) => o.symbol === symbol) || {
            symbol,
            oi: 0,
            oi_change_24h: 0,
            notional: 0,
          }

          return (
            <Col xs={24} sm={12} lg={6} key={symbol}>
              <Card className="bg-surface border-border h-full">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-lg text-text-primary">{symbol}</span>
                  <Tag
                    className={clsx(
                      'text-xs border-0',
                      data.change_24h >= 0 ? 'bg-bullish/20 text-bullish' : 'bg-bearish/20 text-bearish'
                    )}
                  >
                    {data.change_24h >= 0 ? '+' : ''}{data.change_24h.toFixed(2)}%
                  </Tag>
                </div>

                <div className="text-2xl font-bold text-text-primary mb-3">
                  ${data.price ? data.price.toLocaleString() : '-'}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                  <div>
                    <span className="text-text-secondary">24h高</span>
                    <div className="text-text-primary font-mono">${data.high_24h?.toLocaleString() || '-'}</div>
                  </div>
                  <div>
                    <span className="text-text-secondary">24h低</span>
                    <div className="text-text-primary font-mono">${data.low_24h?.toLocaleString() || '-'}</div>
                  </div>
                </div>

                <div className="border-t border-border pt-3 mt-3 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary flex items-center gap-1">
                      <DollarSign className="w-3 h-3" /> 资金费率
                    </span>
                    <span className={clsx('font-mono font-medium', getFundingColor(funding.rate))}>
                      {(funding.rate * 100).toFixed(4)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary flex items-center gap-1">
                      <BarChart3 className="w-3 h-3" /> 持仓量
                    </span>
                    <span className={clsx('font-mono', oi.oi_change_24h >= 0 ? 'text-bullish' : 'text-bearish')}>
                      ${formatNumber(oi.notional)} ({oi.oi_change_24h >= 0 ? '+' : ''}{oi.oi_change_24h.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-secondary flex items-center gap-1">
                      <Activity className="w-3 h-3" /> 24h成交量
                    </span>
                    <span className="font-mono text-text-primary">${formatNumber(data.volume_24h)}</span>
                  </div>
                </div>
              </Card>
            </Col>
          )
        })}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border h-full"
            title={
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">资金费率监控</span>
              </div>
            }
          >
            <div className="space-y-3">
              {fundingRates.map((funding) => (
                <div key={funding.symbol} className="flex items-center justify-between p-3 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-text-primary">{funding.symbol}</span>
                    <Tag
                      className={clsx(
                        'text-[10px] border-0',
                        funding.trend === 'rising'
                          ? 'bg-bearish/20 text-bearish'
                          : funding.trend === 'falling'
                          ? 'bg-bullish/20 text-bullish'
                          : 'bg-neutral/20 text-neutral'
                      )}
                    >
                      {funding.trend === 'rising' ? '上升' : funding.trend === 'falling' ? '下降' : '稳定'}
                    </Tag>
                  </div>
                  <div className="text-right">
                    <div className={clsx('text-lg font-bold', getFundingColor(funding.rate))}>
                      {(funding.rate * 100).toFixed(4)}%
                    </div>
                    <div className="text-xs text-text-secondary">下次: {funding.next_funding}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            className="bg-surface border-border h-full"
            title={
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium">持仓量变化</span>
              </div>
            }
          >
            <div className="space-y-3">
              {openInterest.map((oi) => (
                <div key={oi.symbol} className="p-3 bg-background rounded-lg border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-text-primary">{oi.symbol}</span>
                    <span
                      className={clsx(
                        'text-sm font-bold',
                        oi.oi_change_24h >= 0 ? 'text-bullish' : 'text-bearish'
                      )}
                    >
                      {oi.oi_change_24h >= 0 ? '+' : ''}{oi.oi_change_24h.toFixed(2)}%
                    </span>
                  </div>
                  <Progress
                    percent={Math.min(Math.abs(oi.oi_change_24h) * 5, 100)}
                    showInfo={false}
                    strokeColor={oi.oi_change_24h >= 0 ? '#10B981' : '#EF4444'}
                    trailColor="var(--border)"
                  />
                  <div className="text-xs text-text-secondary mt-1">
                    名义价值: ${formatNumber(oi.notional)}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Card
        className="bg-surface border-border"
        title={
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-warning" />
            <span className="text-sm font-medium">清算事件</span>
            <Badge count={liquidations.length} className="ml-2" />
          </div>
        }
        extra={
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <Clock className="w-3 h-3" />
            <span>最近 1 小时</span>
          </div>
        }
      >
        <Table
          dataSource={liquidations}
          columns={liquidationColumns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          size="small"
          locale={{ emptyText: '暂无清算事件' }}
        />
      </Card>
    </div>
  )
}
