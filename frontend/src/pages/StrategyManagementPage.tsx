import { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Table,
  Button,
  Tag,
  Space,
  Modal,
  Form,
  Select,
  Input,
  DatePicker,
  Switch,
  Spin,
  Alert,
  Statistic,
  Divider,
  Typography,
  message,
  Badge,
  Timeline,
  Progress,
  List,
} from 'antd'
import {
  PlusOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  StopOutlined,
  RocketOutlined,
  SettingOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { MenuProps } from 'antd'
import dayjs from 'dayjs'
import {
  StrategyPattern,
  BacktestConfig,
  BacktestResult,
  StrategyConfig,
  discoverStrategies,
  getActiveStrategies,
  getAllStrategyConfigs,
  getBacktestHistory,
  enableStrategy,
  disableStrategy,
  updateStrategyConfig,
} from '../services/api/strategyApi'
import { getAllSymbolConfigs } from '../services/api/featureMatrixApi'

const { Title, Text } = Typography
const { RangePicker } = DatePicker
const { Option } = Select
const { TextArea } = Input

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

type TabKey = 'discover' | 'active' | 'backtest' | 'config'

export function StrategyManagementPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('discover')
  const [loading, setLoading] = useState(false)

  // Discover strategies
  const [discoveredStrategies, setDiscoveredStrategies] = useState<StrategyPattern[]>([])
  const [discoverSymbol, setDiscoverSymbol] = useState('BTCUSDT')
  const [discovering, setDiscovering] = useState(false)

  // Active strategies
  const [activeStrategies, setActiveStrategies] = useState<StrategyPattern[]>([])

  // Backtest
  const [backtestHistory, setBacktestHistory] = useState<BacktestResult[]>([])
  const [backtestModalVisible, setBacktestModalVisible] = useState(false)
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([])
  const [backtestConfig, setBacktestConfig] = useState<BacktestConfig | null>(null)
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null)

  // Config
  const [strategyConfigs, setStrategyConfigs] = useState<Record<string, StrategyConfig[]>>({})

  useEffect(() => {
    loadData()
  }, [activeTab])

  const loadData = async () => {
    setLoading(true)
    try {
      switch (activeTab) {
        case 'discover':
          await loadDiscoveredStrategies()
          break
        case 'active':
          await loadActiveStrategies()
          break
        case 'backtest':
          await loadBacktestHistory()
          break
        case 'config':
          await loadStrategyConfigs()
          break
      }
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadDiscoveredStrategies = async () => {
    const data = await getActiveStrategies()
    setDiscoveredStrategies(data)
  }

  const loadActiveStrategies = async () => {
    const data = await getActiveStrategies()
    setActiveStrategies(data.filter(s => s.isEnabled))
  }

  const loadBacktestHistory = async () => {
    const data = await getBacktestHistory()
    setBacktestHistory(data)
  }

  const loadStrategyConfigs = async () => {
    const data = await getAllStrategyConfigs()
    setStrategyConfigs(data)
  }

  const handleDiscover = async () => {
    setDiscovering(true)
    try {
      message.loading('正在发现策略...')
      await discoverStrategies(discoverSymbol)
      message.success('策略发现完成')
      await loadDiscoveredStrategies()
    } catch (error) {
      message.error('策略发现失败')
      console.error(error)
    } finally {
      setDiscovering(false)
    }
  }

  const handleEnableStrategy = async (strategy: StrategyPattern) => {
    try {
      await enableStrategy(strategy.id, discoverSymbol)
      message.success(`策略 ${strategy.name} 已启用`)
      loadData()
    } catch (error) {
      message.error('启用策略失败')
    }
  }

  const handleDisableStrategy = async (strategy: StrategyPattern) => {
    try {
      await disableStrategy(strategy.id, discoverSymbol)
      message.warning(`策略 ${strategy.name} 已停用`)
      loadData()
    } catch (error) {
      message.error('停用策略失败')
    }
  }

  const handleStartBacktest = () => {
    setBacktestModalVisible(true)
  }

  const handleRunBacktest = async (values: any) => {
    setLoading(true)
    try {
      const config: BacktestConfig = {
        symbol: values.symbol,
        startDate: values.dateRange[0].format('YYYY-MM-DD'),
        endDate: values.dateRange[1].format('YYYY-MM-DD'),
        initialCapital: values.initialCapital || 100000,
        strategyIds: selectedStrategies,
      }
      setBacktestConfig(config)
      const result = await startBacktest(config)
      setBacktestResult(result)
      message.success('回测已启动')
      await loadBacktestHistory()
    } catch (error) {
      message.error('回测启动失败')
    } finally {
      setLoading(false)
      setBacktestModalVisible(false)
    }
  }

  const getStatusColor = (enabled: boolean) => (enabled ? 'success' : 'default')
  const getStatusText = (enabled: boolean) => (enabled ? '运行中' : '已停用')

  const tabMenuItems: MenuProps['items'] = [
    { key: 'discover', icon: <ExperimentOutlined />, label: '策略发现' },
    { key: 'active', icon: <ThunderboltOutlined />, label: '活跃策略' },
    { key: 'backtest', icon: <HistoryOutlined />, label: '回测管理' },
    { key: 'config', icon: <SettingOutlined />, label: '参数配置' },
  ]

  const strategyColumns: ColumnsType<StrategyPattern> = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <div>
          <Text strong>{text}</Text>
          <div className="text-xs text-gray-500">{record.description}</div>
        </div>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      render: (cat: string) => <Tag color="blue">{cat}</Tag>,
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      render: (val: number) => (
        <Progress percent={val * 100} size="small" format={() => `${(val * 100).toFixed(0)}%`} />
      ),
    },
    {
      title: '状态',
      dataIndex: 'isEnabled',
      key: 'isEnabled',
      render: (enabled: boolean) => (
        <Badge status={getStatusColor(enabled)} text={getStatusText(enabled)} />
      ),
    },
    {
      title: '绩效',
      key: 'performance',
      render: (_, record) =>
        record.performance ? (
          <Space direction="vertical" size="small">
            <Text type="success">胜率: {(record.performance.winRate * 100).toFixed(1)}%</Text>
            <Text type="secondary">夏普: {record.performance.sharpeRatio.toFixed(2)}</Text>
          </Space>
        ) : (
          <Text type="secondary">暂无数据</Text>
        ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          {record.isEnabled ? (
            <Button
              size="small"
              icon={<PauseCircleOutlined />}
              danger
              onClick={() => handleDisableStrategy(record)}
            >
              停用
            </Button>
          ) : (
            <Button
              size="small"
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => handleEnableStrategy(record)}
            >
              上线
            </Button>
          )}
          <Button size="small" icon={<BarChartOutlined />}>
            回测
          </Button>
        </Space>
      ),
    },
  ]

  const backtestColumns: ColumnsType<BacktestResult> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => <Text code className="text-xs">{id.slice(0, 8)}</Text>,
    },
    {
      title: '配置',
      key: 'config',
      render: (_, record) => (
        <Space direction="vertical" size="small">
          <Text>{record.config.symbol}</Text>
          <Text type="secondary" className="text-xs">
            {record.config.startDate} ~ {record.config.endDate}
          </Text>
        </Space>
      ),
    },
    {
      title: '总收益',
      dataIndex: ['performance', 'totalReturn'],
      key: 'totalReturn',
      render: (val: number) => (
        <Text type={val >= 0 ? 'success' : 'danger'}>
          {(val * 100).toFixed(2)}%
        </Text>
      ),
    },
    {
      title: '夏普比率',
      dataIndex: ['performance', 'sharpeRatio'],
      key: 'sharpeRatio',
      render: (val: number) => <Text>{val.toFixed(2)}</Text>,
    },
    {
      title: '胜率',
      dataIndex: ['performance', 'winRate'],
      key: 'winRate',
      render: (val: number) => (
        <Text>{(val * 100).toFixed(1)}%</Text>
      ),
    },
    {
      title: '交易次数',
      dataIndex: ['performance', 'totalTrades'],
      key: 'totalTrades',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          running: 'processing',
          completed: 'success',
          failed: 'error',
        }
        return <Badge status={colorMap[status] || 'default'} text={status} />
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<BarChartOutlined />}>
            查看
          </Button>
        </Space>
      ),
    },
  ]

  const renderDiscoverTab = () => (
    <div className="space-y-4">
      <Card>
        <Row gutter={16} align="middle">
          <Col xs={24} md={8}>
            <Space>
              <Select value={discoverSymbol} onChange={setDiscoverSymbol} style={{ width: 150 }}>
                {SYMBOLS.map(s => (
                  <Option key={s} value={s}>{s}</Option>
                ))}
              </Select>
              <Button
                type="primary"
                icon={<ExperimentOutlined />}
                onClick={handleDiscover}
                loading={discovering}
              >
                发现策略
              </Button>
            </Space>
          </Col>
          <Col xs={24} md={16}>
            <Text type="secondary">
              基于历史特征数据，自动扫描并发现有效的策略模式
            </Text>
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        <Table
          dataSource={discoveredStrategies}
          columns={strategyColumns}
          rowKey="id"
          locale={{ emptyText: '点击"发现策略"开始扫描' }}
        />
      </Spin>
    </div>
  )

  const renderActiveTab = () => (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="活跃策略"
              value={activeStrategies.length}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#10B981' }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="总交易次数"
              value={activeStrategies.reduce((sum, s) => sum + (s.performance?.winRate || 0), 0).toFixed(0)}
              prefix={<HistoryOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="平均胜率"
              value={
                activeStrategies.length
                  ? (
                      activeStrategies.reduce(
                        (sum, s) => sum + (s.performance?.winRate || 0),
                        0
                      ) / activeStrategies.length * 100
                    ).toFixed(1)
                  : 0
              }
              suffix="%"
              valueStyle={{ color: '#3B82F6' }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="平均夏普"
              value={
                activeStrategies.length
                  ? (
                      activeStrategies.reduce(
                        (sum, s) => sum + (s.performance?.sharpeRatio || 0),
                        0
                      ) / activeStrategies.length
                    ).toFixed(2)
                  : 0
              }
              valueStyle={{ color: '#F59E0B' }}
            />
          </Card>
        </Col>
      </Row>

      <Spin spinning={loading}>
        <Table
          dataSource={activeStrategies}
          columns={strategyColumns}
          rowKey="id"
          locale={{ emptyText: '暂无活跃策略' }}
        />
      </Spin>
    </div>
  )

  const renderBacktestTab = () => (
    <div className="space-y-4">
      <Card>
        <Row gutter={16} align="middle">
          <Col xs={24} md={16}>
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStartBacktest}
              >
                新建回测
              </Button>
            </Space>
          </Col>
          <Col xs={24} md={8}>
            <Text type="secondary">
              共 {backtestHistory.length} 个回测记录
            </Text>
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        <Table
          dataSource={backtestHistory}
          columns={backtestColumns}
          rowKey="id"
          locale={{ emptyText: '暂无回测记录' }}
        />
      </Spin>

      <Modal
        title="配置回测"
        open={backtestModalVisible}
        onCancel={() => setBacktestModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form layout="vertical" onFinish={handleRunBacktest}>
          <Form.Item
            label="交易对"
            name="symbol"
            rules={[{ required: true }]}
            initialValue="BTCUSDT"
          >
            <Select>
              {SYMBOLS.map(s => (
                <Option key={s} value={s}>{s}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="回测时间范围"
            name="dateRange"
            rules={[{ required: true }]}
            initialValue={[dayjs().subtract(30, 'day'), dayjs()]}
          >
            <RangePicker style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="初始资金"
            name="initialCapital"
            initialValue={100000}
          >
            <Input type="number" />
          </Form.Item>

          <Form.Item label="选择策略" name="strategies">
            <Select mode="multiple" placeholder="选择要回测的策略">
              {discoveredStrategies.map(s => (
                <Option key={s.id} value={s.id}>{s.name}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />}>
                开始回测
              </Button>
              <Button onClick={() => setBacktestModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {backtestResult && (
        <Card title="回测结果" className="mt-4">
          <Row gutter={16}>
            <Col xs={12} md={6}>
              <Statistic
                title="总收益"
                value={(backtestResult.performance.totalReturn * 100).toFixed(2)}
                suffix="%"
                valueStyle={{
                  color: backtestResult.performance.totalReturn >= 0 ? '#10B981' : '#EF4444',
                }}
              />
            </Col>
            <Col xs={12} md={6}>
              <Statistic
                title="夏普比率"
                value={backtestResult.performance.sharpeRatio.toFixed(2)}
              />
            </Col>
            <Col xs={12} md={6}>
              <Statistic
                title="胜率"
                value={(backtestResult.performance.winRate * 100).toFixed(1)}
                suffix="%"
              />
            </Col>
            <Col xs={12} md={6}>
              <Statistic
                title="最大回撤"
                value={(backtestResult.performance.maxDrawdown * 100).toFixed(2)}
                suffix="%"
                valueStyle={{ color: '#EF4444' }}
              />
            </Col>
          </Row>
        </Card>
      )}
    </div>
  )

  const renderConfigTab = () => (
    <div className="space-y-4">
      <Alert
        message="策略参数配置"
        description="为每个币种配置独立的策略参数，包括阈值、权重和优先级"
        type="info"
        showIcon
      />

      <Spin spinning={loading}>
        {SYMBOLS.map(symbol => (
          <Card key={symbol} title={`${symbol} 配置`} className="mb-4">
            <List
              dataSource={strategyConfigs[symbol] || []}
              renderItem={(config: StrategyConfig) => (
                <List.Item
                  actions={[
                    <Switch
                      checked={config.enabled}
                      onChange={(checked) => {
                        if (checked) {
                          enableStrategy(config.strategyId, symbol)
                        } else {
                          disableStrategy(config.strategyId, symbol)
                        }
                        loadStrategyConfigs()
                      }}
                    />,
                  ]}
                >
                  <List.Item.Meta
                    title={config.strategyId}
                    description={
                      <Space direction="vertical" size="small">
                        <Text type="secondary">
                          优先级: {config.priority}
                        </Text>
                        <div>
                          {Object.entries(config.parameters).map(([key, value]) => (
                            <Tag key={key} className="mr-1">
                              {key}: {value}
                            </Tag>
                          ))}
                        </div>
                      </Space>
                    }
                  />
                </List.Item>
              )}
              locale={{ emptyText: '暂无配置' }}
            />
          </Card>
        ))}
      </Spin>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <Title level={4} className="mb-0">
          策略管理中心
        </Title>
      </div>

      <Card>
        <Space className="mb-4">
          {tabMenuItems.map(item => (
            <Button
              key={item?.key}
              type={activeTab === item?.key ? 'primary' : 'default'}
              icon={item?.icon}
              onClick={() => setActiveTab(item?.key as TabKey)}
            >
              {item?.label}
            </Button>
          ))}
        </Space>

        <Divider className="my-4" />

        {activeTab === 'discover' && renderDiscoverTab()}
        {activeTab === 'active' && renderActiveTab()}
        {activeTab === 'backtest' && renderBacktestTab()}
        {activeTab === 'config' && renderConfigTab()}
      </Card>
    </div>
  )
}

export default StrategyManagementPage
