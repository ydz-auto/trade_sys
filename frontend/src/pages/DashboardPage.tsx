import { useEffect } from 'react'
import { Card, Row, Col, Statistic, Progress, Tag, Badge, Table, Space, Avatar, Tooltip } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  DollarOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
  TwitterOutlined,
  YoutubeOutlined,
  SendOutlined,
} from '@ant-design/icons'
import { useTradingStore } from '../store/tradingStore'

const platformIcon: Record<string, React.ReactNode> = {
  Twitter: <TwitterOutlined />,
  YouTube: <YoutubeOutlined />,
  Telegram: <SendOutlined />,
}

export function DashboardPage() {
  const { prices, compositeScore, regime, risk, signal, factors, positions, dataSources, traders, socialPosts, setLastUpdate } =
    useTradingStore()

  useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(new Date())
    }, 1000)
    return () => clearInterval(interval)
  }, [setLastUpdate])

  const regimeTagColor: Record<string, string> = {
    RISK_OFF: 'red',
    RISK_ON: 'green',
    NEUTRAL: 'blue',
    TRANSITIONAL: 'orange',
    UNCERTAIN: 'default',
  }

  const signalTagColor: Record<string, string> = {
    BUY: 'green',
    SELL: 'red',
    HOLD: 'default',
  }

  const btcPrices = prices.filter(p => p.symbol === 'BTC/USDT')
  const ethPrices = prices.filter(p => p.symbol === 'ETH/USDT')

  const dataSourceColumns = [
    { title: '数据源', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string, record: any) => (
        <Space size="small">
          <Badge
            status={status === 'normal' ? 'success' : status === 'delayed' ? 'warning' : 'error'}
          />
          <span>
            {status === 'normal' ? '正常' : status === 'delayed' ? `延迟${record.delay}` : '异常'}
          </span>
        </Space>
      ),
    },
  ]

  return (
    <div className="p-6 bg-[#0F172A] min-h-screen">
      {/* 价格卡片 - 按平台分组 */}
      <Row gutter={[16, 16]} className="mb-4">
        <Col span={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">BTC/USDT 各平台价格</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2">
              {btcPrices.map((price) => (
                <div key={price.exchange} className="flex justify-between items-center bg-[#0F172A] rounded p-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[#F59E0B] font-bold">B</span>
                    <span className="text-sm text-[#94A3B8]">{price.exchange}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-[#F8FAFC]">${price.price.toLocaleString()}</span>
                    <span className={`text-xs ${price.change24h >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {price.change24h >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                      {Math.abs(price.change24h)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">ETH/USDT 各平台价格</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2">
              {ethPrices.map((price) => (
                <div key={price.exchange} className="flex justify-between items-center bg-[#0F172A] rounded p-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[#8B5CF6] font-bold">E</span>
                    <span className="text-sm text-[#94A3B8]">{price.exchange}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-[#F8FAFC]">${price.price.toLocaleString()}</span>
                    <span className={`text-xs ${price.change24h >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {price.change24h >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                      {Math.abs(price.change24h)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* 综合得分 + 市场状态 + 风险指数 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col span={8}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155] h-full">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">综合得分</span>}
              value={compositeScore}
              precision={2}
              prefix={compositeScore >= 0 ? '+' : ''}
              valueStyle={{
                color: compositeScore >= 0 ? '#10B981' : '#EF4444',
                fontSize: '1.5rem',
                fontWeight: 600,
              }}
              suffix={<span className="text-xs text-[#94A3B8] ml-1">85%</span>}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155] h-full">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">市场状态</span>}
              value={regime.state}
              prefix={<SafetyOutlined className="text-[#F97316]" />}
              valueStyle={{ color: '#F97316', fontSize: '1rem', fontWeight: 600 }}
            />
            <Tag color={regimeTagColor[regime.state] || 'default'} className="mt-2 text-xs">{regime.state}</Tag>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155] h-full">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">风险指数</span>}
              value={risk.total}
              prefix={<ExclamationCircleOutlined className="text-[#F97316]" />}
              valueStyle={{ color: '#F97316', fontSize: '1.5rem', fontWeight: 600 }}
            />
            <Progress
              percent={risk.total}
              showInfo={false}
              strokeColor="#F97316"
              trailColor="#334155"
              size="small"
              className="!mb-0 !mt-3"
            />
          </Card>
        </Col>
      </Row>

      {/* KOL交易员 + 社交媒体 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col span={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0] flex items-center gap-2">
              <UserOutlined className="text-[#EC4899]" /> KOL 交易员
            </span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {traders.map((trader, idx) => (
                <div key={idx} className="flex items-center justify-between bg-[#0F172A] rounded p-2">
                  <div className="flex items-center gap-2">
                    <Avatar size="small" icon={platformIcon[trader.platform]} className="bg-[#8B5CF6]" />
                    <div>
                      <div className="text-sm text-[#F8FAFC]">{trader.name}</div>
                      <div className="text-xs text-[#94A3B8]">{trader.platform} · {(trader.followers / 1000).toFixed(0)}K 粉丝</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Tag color={trader.recentPosition === 'LONG' ? 'green' : trader.recentPosition === 'SHORT' ? 'red' : 'default'} className="text-xs">
                      {trader.recentPosition} {trader.symbol}
                    </Tag>
                    <Tooltip title={`情绪 ${(trader.sentiment * 100).toFixed(0)}%`}>
                      <span className={`text-xs font-semibold ${trader.sentiment >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {(trader.sentiment * 100).toFixed(0)}%
                      </span>
                    </Tooltip>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0] flex items-center gap-2">
              <ThunderboltOutlined className="text-[#06B6D4]" /> 社交媒体
            </span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {socialPosts.map((post) => (
                <div key={post.id} className="bg-[#0F172A] rounded p-2">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[#94A3B8] text-xs">{post.time}</span>
                    <Tag color="blue" className="text-xs">{platformIcon[post.platform]}</Tag>
                    <span className="text-xs text-[#94A3B8]">{post.author}</span>
                    <Tag color={post.sentiment > 0 ? 'green' : 'red'} className="text-xs ml-auto">
                      {post.sentiment > 0 ? '+' : ''}{(post.sentiment * 100).toFixed(0)}%
                    </Tag>
                  </div>
                  <div className="text-xs text-[#E2E8F0] line-clamp-2">{post.content}</div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* ETF + 宏观 + 情绪 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col span={8}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm text-[#E2E8F0]">
                <DollarOutlined className="text-[#F59E0B]" />
                ETF资金流
              </span>
            }
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-[#94A3B8] text-xs">BTC ETF 今日净流入</span>
                <span className="text-[#10B981] font-semibold">+$150M</span>
              </div>
              <Progress
                percent={75}
                strokeColor="#10B981"
                trailColor="#334155"
                showInfo={false}
              />
              <div className="flex justify-between items-center text-xs">
                <span className="text-[#94A3B8]">7日趋势</span>
                <span className="text-[#10B981]">持续流入 ↑</span>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm text-[#E2E8F0]">
                <SafetyOutlined className="text-[#10B981]" />
                宏观数据
              </span>
            }
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <Row gutter={[8, 8]}>
              <Col span={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">黄金 (USD/oz)</div>
                  <div className="font-semibold text-[#F8FAFC]">$2,020</div>
                  <div className="text-[#10B981] text-xs">▲ +0.5%</div>
                </div>
              </Col>
              <Col span={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">原油 (USD/bbl)</div>
                  <div className="font-semibold text-[#F8FAFC]">$78.3</div>
                  <div className="text-[#EF4444] text-xs">▼ -0.3%</div>
                </div>
              </Col>
              <Col span={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">美元指数</div>
                  <div className="font-semibold text-[#F8FAFC]">104.2</div>
                  <div className="text-[#3B82F6] text-xs">▲ +0.1%</div>
                </div>
              </Col>
              <Col span={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">MSTR</div>
                  <div className="font-semibold text-[#F8FAFC]">$1,520</div>
                  <div className="text-[#10B981] text-xs">▲ +3.2%</div>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm text-[#E2E8F0]">
                <ThunderboltOutlined className="text-[#8B5CF6]" />
                情绪指数
              </span>
            }
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-3">
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-[#94A3B8] text-xs">恐慌贪婪指数</span>
                  <span className="text-[#10B981] text-xs font-semibold">72 [贪婪]</span>
                </div>
                <Progress
                  percent={72}
                  strokeColor={{ '0%': '#EF4444', '50%': '#F97316', '100%': '#10B981' }}
                  trailColor="#334155"
                  showInfo={false}
                />
              </div>
              <Row gutter={[8, 8]}>
                <Col span={12}>
                  <div className="bg-[#0F172A] rounded p-2 text-center">
                    <div className="text-[#94A3B8] text-xs">新闻情绪</div>
                    <div className="text-sm font-semibold text-[#10B981]">+0.35</div>
                  </div>
                </Col>
                <Col span={12}>
                  <div className="bg-[#0F172A] rounded p-2 text-center">
                    <div className="text-[#94A3B8] text-xs">社交情绪</div>
                    <div className="text-sm font-semibold text-[#10B981]">+0.52</div>
                  </div>
                </Col>
              </Row>
              <div className="text-center">
                <Tag color="green" className="text-xs">综合情绪: 偏多</Tag>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 因子 + 决策 + 仓位 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col span={8}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">因子详情</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <Row gutter={[8, 8]}>
              {factors.map((factor) => (
                <Col span={12} key={factor.type}>
                  <div className="bg-[#0F172A] rounded p-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-[#94A3B8] text-xs">{factor.name}</span>
                      <span className="text-[#94A3B8] text-xs">{factor.weight}%</span>
                    </div>
                    <div
                      className={`font-semibold text-lg ${
                        factor.value >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                      }`}
                    >
                      {factor.value >= 0 ? '+' : ''}
                      {factor.value.toFixed(2)}
                    </div>
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">决策信号</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="text-center mb-3">
              <Tag color={signalTagColor[signal.action] || 'default'} className="text-sm px-3 py-0.5">
                {signal.action} SIGNAL
              </Tag>
            </div>
            <Row gutter={[8, 8]} className="mb-3">
              <Col span={12}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs mb-1">置信度</div>
                  <div className="text-lg font-semibold text-[#F59E0B]">{signal.confidence}%</div>
                </div>
              </Col>
              <Col span={12}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs mb-1">风险等级</div>
                  <div
                    className={`text-lg font-semibold ${
                      signal.riskLevel === 'LOW'
                        ? 'text-[#10B981]'
                        : signal.riskLevel === 'MEDIUM'
                        ? 'text-[#F97316]'
                        : 'text-[#EF4444]'
                    }`}
                  >
                    {signal.riskLevel}
                  </div>
                </div>
              </Col>
            </Row>
            <div className="bg-[#0F172A] rounded p-3 text-xs text-[#94A3B8] text-center">
              {signal.reason}
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">仓位管理</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            {positions.map((pos) => (
              <div key={pos.symbol} className="bg-[#0F172A] rounded p-3 mb-2 last:mb-0">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium text-sm text-[#F8FAFC]">{pos.symbol}</span>
                  <Tag color={pos.side === 'LONG' ? 'green' : pos.side === 'SHORT' ? 'red' : 'default'} className="text-xs">
                    {pos.side}
                  </Tag>
                </div>
                {pos.side !== 'NONE' ? (
                  <Row gutter={[8, 8]}>
                    <Col span={8}>
                      <div className="text-[#94A3B8] text-xs">仓位</div>
                      <div className="text-sm text-[#F8FAFC]">{pos.size} BTC</div>
                    </Col>
                    <Col span={8}>
                      <div className="text-[#94A3B8] text-xs">杠杆</div>
                      <div className="text-sm text-[#F8FAFC]">{pos.leverage}x</div>
                    </Col>
                    <Col span={8}>
                      <div className="text-[#94A3B8] text-xs">浮盈</div>
                      <div className={`text-sm font-semibold ${pos.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {pos.pnl >= 0 ? '+' : ''}${pos.pnl}
                      </div>
                    </Col>
                  </Row>
                ) : (
                  <div className="text-[#94A3B8] text-xs">等待买入信号...</div>
                )}
              </div>
            ))}
          </Card>
        </Col>
      </Row>

      {/* 新闻 + 数据源状态 */}
      <Row gutter={[16, 16]} align="stretch">
        <Col span={16}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm text-[#E2E8F0]">
                <ClockCircleOutlined className="text-[#8B5CF6]" />
                新闻资讯
              </span>
            }
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2">
              <div className="bg-[#0F172A] rounded p-3 hover:bg-[#334155]/50 transition-colors cursor-pointer">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[#94A3B8] text-xs">10分钟前</span>
                  <Tag color="orange" className="text-xs">CoinDesk</Tag>
                  <Tag color="green" className="text-xs">+0.85</Tag>
                </div>
                <div className="text-sm text-[#F8FAFC]">BTC ETF净流入创历史新高，单日流入超10亿美元</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 hover:bg-[#334155]/50 transition-colors cursor-pointer">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[#94A3B8] text-xs">25分钟前</span>
                  <Tag color="orange" className="text-xs">金十数据</Tag>
                  <Tag color="red" className="text-xs">-0.15</Tag>
                </div>
                <div className="text-sm text-[#F8FAFC]">美联储宣布维持利率不变，符合市场预期</div>
              </div>
              <div className="bg-[#0F172A] rounded p-3 hover:bg-[#334155]/50 transition-colors cursor-pointer">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[#94A3B8] text-xs">32分钟前</span>
                  <Tag color="orange" className="text-xs">CoinTelegraph</Tag>
                  <Tag color="green" className="text-xs">+0.72</Tag>
                </div>
                <div className="text-sm text-[#F8FAFC]">以太坊ETF获批预期升温，ETH突破新高</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={
              <span className="flex items-center gap-2 text-sm text-[#E2E8F0]">
                <CheckCircleOutlined className="text-[#10B981]" />
                数据采集状态
              </span>
            }
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <Table
              dataSource={dataSources}
              columns={dataSourceColumns}
              pagination={false}
              size="small"
              className="!bg-transparent"
              rowKey="name"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
