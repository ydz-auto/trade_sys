import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Table, Button, Select, DatePicker, InputNumber, Form, Modal, Progress, Statistic, Badge, Tabs, Spin, Empty, message } from 'antd'
import {
  History,
  Play,
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  LineChart,
  Target,
  Clock,
  DollarSign,
  Percent,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Download,
  Settings,
} from 'lucide-react'
import { api } from '../services/api/client'
import clsx from 'clsx'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

interface BacktestConfig {
  symbol: string
  start_date: string
  end_date: string
  initial_capital: number
  strategies: string[]
  leverage: number
  fee_rate: number
}

interface BacktestResult {
  id: string
  config: BacktestConfig
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  started_at: string
  completed_at?: string
  performance: {
    total_return: number
    annualized_return: number
    sharpe_ratio: number
    max_drawdown: number
    win_rate: number
    total_trades: number
    profit_factor: number
    avg_trade_duration: number
  }
  equity_curve: { date: string; value: number }[]
  drawdown_curve: { date: string; drawdown: number }[]
  trades: BacktestTrade[]
}

interface BacktestTrade {
  id: string
  symbol: string
  side: 'LONG' | 'SHORT'
  entry_time: string
  exit_time: string
  entry_price: number
  exit_price: number
  quantity: number
  pnl: number
  pnl_percent: number
  reason: string
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']
const STRATEGIES = ['Panic Reversal', 'Funding Trap', 'Short Squeeze', 'Liquidity Vacuum']

export function BacktestingPage() {
  const [results, setResults] = useState<BacktestResult[]>([])
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [configModalVisible, setConfigModalVisible] = useState(false)
  const [runningBacktest, setRunningBacktest] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    loadResults()
  }, [])

  const loadResults = async () => {
    setLoading(true)
    try {
      const res = await api.get('/backtest/results')
      if (res.data) setResults(res.data)
    } catch (error) {
      console.error('Failed to load backtest results:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRunBacktest = async (values: any) => {
    setRunningBacktest(true)
    try {
      const config: BacktestConfig = {
        symbol: values.symbol,
        start_date: values.dateRange[0].format('YYYY-MM-DD'),
        end_date: values.dateRange[1].format('YYYY-MM-DD'),
        initial_capital: values.initial_capital,
        strategies: values.strategies,
        leverage: values.leverage,
        fee_rate: values.fee_rate || 0.0004,
      }
      const res = await api.post('/backtest/run', config)
      message.success('回测已启动')
      setConfigModalVisible(false)
      loadResults()
    } catch (error) {
      message.error('回测启动失败')
    } finally {
      setRunningBacktest(false)
    }
  }

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时 ${minutes}分钟`
  }

  const resultColumns = [
    {
      title: '回测ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (id: string) => <span className="font-mono text-xs text-text-secondary">{id.slice(0, 8)}</span>,
    },
    {
      title: '品种',
      dataIndex: ['config', 'symbol'],
      key: 'symbol',
      width: 100,
    },
    {
      title: '时间范围',
      key: 'range',
      width: 200,
      render: (_: unknown, record: BacktestResult) => (
        <span className="text-xs">
          {record.config.start_date} ~ {record.config.end_date}
        </span>
      ),
    },
    {
      title: '总收益',
      dataIndex: ['performance', 'total_return'],
      key: 'total_return',
      width: 100,
      render: (val: number) => (
        <span className={clsx('font-bold', val >= 0 ? 'text-bullish' : 'text-bearish')}>
          {(val * 100).toFixed(2)}%
        </span>
      ),
    },
    {
      title: '夏普比率',
      dataIndex: ['performance', 'sharpe_ratio'],
      key: 'sharpe_ratio',
      width: 80,
      render: (val: number) => <span className="font-mono">{val.toFixed(2)}</span>,
    },
    {
      title: '最大回撤',
      dataIndex: ['performance', 'max_drawdown'],
      key: 'max_drawdown',
      width: 100,
      render: (val: number) => <span className="font-mono text-bearish">{(val * 100).toFixed(2)}%</span>,
    },
    {
      title: '胜率',
      dataIndex: ['performance', 'win_rate'],
      key: 'win_rate',
      width: 80,
      render: (val: number) => <span className="font-mono">{(val * 100).toFixed(1)}%</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string, record: BacktestResult) => {
        if (status === 'running') {
          return (
            <div className="flex items-center gap-2">
              <Progress percent={record.progress} size="small" showInfo={false} className="w-16" />
              <span className="text-xs text-warning">{record.progress}%</span>
            </div>
          )
        }
        return (
          <Tag
            className={clsx(
              'text-xs border-0',
              status === 'completed'
                ? 'bg-bullish/20 text-bullish'
                : status === 'failed'
                ? 'bg-bearish/20 text-bearish'
                : 'bg-neutral/20 text-neutral'
            )}
          >
            {status === 'completed' ? '已完成' : status === 'failed' ? '失败' : '待运行'}
          </Tag>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: BacktestResult) => (
        <div className="flex gap-2">
          <Button size="small" onClick={() => setSelectedResult(record)}>
            详情
          </Button>
          {record.status === 'completed' && (
            <Button size="small" icon={<Download className="w-3 h-3" />}>
              导出
            </Button>
          )}
        </div>
      ),
    },
  ]

  const tradeColumns = [
    {
      title: '时间',
      dataIndex: 'entry_time',
      key: 'entry_time',
      width: 150,
      render: (t: string) => new Date(t).toLocaleString(),
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
      title: '入场价',
      dataIndex: 'entry_price',
      key: 'entry_price',
      width: 100,
      render: (p: number) => `$${p.toLocaleString()}`,
    },
    {
      title: '出场价',
      dataIndex: 'exit_price',
      key: 'exit_price',
      width: 100,
      render: (p: number) => `$${p.toLocaleString()}`,
    },
    {
      title: '盈亏',
      dataIndex: 'pnl',
      key: 'pnl',
      width: 100,
      render: (pnl: number) => (
        <span className={clsx('font-bold', pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
          {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
        </span>
      ),
    },
    {
      title: '盈亏%',
      dataIndex: 'pnl_percent',
      key: 'pnl_percent',
      width: 80,
      render: (pct: number) => (
        <span className={clsx(pct >= 0 ? 'text-bullish' : 'text-bearish')}>
          {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
        </span>
      ),
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
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
          <h1 className="text-2xl font-bold text-text-primary">历史回测</h1>
          <p className="text-text-secondary text-sm mt-1">策略回测、收益曲线、回撤分析</p>
        </div>
        <div className="flex items-center gap-3">
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={loadResults}>
            刷新
          </Button>
          <Button type="primary" icon={<Play className="w-4 h-4" />} onClick={() => setConfigModalVisible(true)}>
            新建回测
          </Button>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">总回测次数</span>}
              value={results.length}
              prefix={<History className="w-4 h-4 text-primary" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">平均收益</span>}
              value={
                results.length > 0
                  ? ((results.reduce((a, r) => a + (r.performance?.total_return || 0), 0) / results.length) * 100).toFixed(1)
                  : 0
              }
              suffix="%"
              prefix={<TrendingUp className="w-4 h-4 text-bullish" />}
              valueStyle={{ color: 'var(--bullish)' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">平均夏普</span>}
              value={
                results.length > 0
                  ? (results.reduce((a, r) => a + (r.performance?.sharpe_ratio || 0), 0) / results.length).toFixed(2)
                  : 0
              }
              prefix={<Activity className="w-4 h-4 text-accent" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="bg-surface border-border">
            <Statistic
              title={<span className="text-text-secondary text-xs">平均胜率</span>}
              value={
                results.length > 0
                  ? ((results.reduce((a, r) => a + (r.performance?.win_rate || 0), 0) / results.length) * 100).toFixed(1)
                  : 0
              }
              suffix="%"
              prefix={<Target className="w-4 h-4 text-warning" />}
              valueStyle={{ color: 'var(--text-primary)' }}
            />
          </Card>
        </Col>
      </Row>

      <Card className="bg-surface border-border" title={<span className="text-sm font-medium">回测记录</span>}>
        <Table
          dataSource={results}
          columns={resultColumns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无回测记录" /> }}
        />
      </Card>

      {selectedResult && (
        <Card
          className="bg-surface border-border"
          title={
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">回测详情 - {selectedResult.id.slice(0, 8)}</span>
              <Button size="small" onClick={() => setSelectedResult(null)}>
                关闭
              </Button>
            </div>
          }
        >
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <div className="p-4 bg-background rounded-lg border border-border">
                <div className="text-xs text-text-secondary mb-2">收益指标</div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">总收益</span>
                    <span className={clsx('font-bold', selectedResult.performance.total_return >= 0 ? 'text-bullish' : 'text-bearish')}>
                      {(selectedResult.performance.total_return * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">年化收益</span>
                    <span className="font-mono text-text-primary">
                      {(selectedResult.performance.annualized_return * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">夏普比率</span>
                    <span className="font-mono text-text-primary">{selectedResult.performance.sharpe_ratio.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </Col>
            <Col xs={24} md={8}>
              <div className="p-4 bg-background rounded-lg border border-border">
                <div className="text-xs text-text-secondary mb-2">风险指标</div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">最大回撤</span>
                    <span className="font-mono text-bearish">
                      {(selectedResult.performance.max_drawdown * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">盈亏比</span>
                    <span className="font-mono text-text-primary">{selectedResult.performance.profit_factor.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">平均持仓</span>
                    <span className="font-mono text-text-primary">
                      {formatDuration(selectedResult.performance.avg_trade_duration)}
                    </span>
                  </div>
                </div>
              </div>
            </Col>
            <Col xs={24} md={8}>
              <div className="p-4 bg-background rounded-lg border border-border">
                <div className="text-xs text-text-secondary mb-2">交易统计</div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">总交易数</span>
                    <span className="font-mono text-text-primary">{selectedResult.performance.total_trades}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">胜率</span>
                    <span className="font-mono text-bullish">{(selectedResult.performance.win_rate * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-text-secondary">初始资金</span>
                    <span className="font-mono text-text-primary">
                      ${selectedResult.config.initial_capital.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </Col>
          </Row>

          <div className="mt-6">
            <div className="text-sm font-medium mb-3">交易记录</div>
            <Table
              dataSource={selectedResult.trades}
              columns={tradeColumns}
              rowKey="id"
              pagination={{ pageSize: 10 }}
              size="small"
              scroll={{ x: 1000 }}
            />
          </div>
        </Card>
      )}

      <Modal
        title="配置回测"
        open={configModalVisible}
        onCancel={() => setConfigModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleRunBacktest} initialValues={{ initial_capital: 100000, leverage: 1, fee_rate: 0.0004 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="symbol" label="交易对" rules={[{ required: true }]}>
                <Select placeholder="选择交易对">
                  {SYMBOLS.map((s) => (
                    <Select.Option key={s} value={s}>
                      {s}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="strategies" label="策略" rules={[{ required: true }]}>
                <Select mode="multiple" placeholder="选择策略">
                  {STRATEGIES.map((s) => (
                    <Select.Option key={s} value={s}>
                      {s}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="dateRange" label="回测时间范围" rules={[{ required: true }]} initialValue={[dayjs().subtract(30, 'day'), dayjs()]}>
            <RangePicker style={{ width: '100%' }} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="initial_capital" label="初始资金">
                <InputNumber min={1000} max={10000000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="leverage" label="杠杆">
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="fee_rate" label="手续费率">
                <InputNumber min={0} max={0.01} step={0.0001} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <div className="flex gap-2">
              <Button type="primary" htmlType="submit" loading={runningBacktest} icon={<Play className="w-4 h-4" />}>
                开始回测
              </Button>
              <Button onClick={() => setConfigModalVisible(false)}>取消</Button>
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
