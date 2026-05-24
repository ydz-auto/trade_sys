import { useEffect } from 'react'
import { Card, Row, Col, Statistic, Progress, Tag, Badge, Table, Space, Avatar, Tooltip, Empty } from 'antd'
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
import { AISummaryBar } from '../components/AISummaryBar'

const platformIcon: Record<string, React.ReactNode> = {
  Twitter: <TwitterOutlined />,
  YouTube: <YoutubeOutlined />,
  Telegram: <SendOutlined />,
}

function formatTimeAgo(timestamp: number): string {
  // 处理秒级时间戳（后端返回的是Unix timestamp）
  const ts = timestamp > 9999999999 ? timestamp : timestamp * 1000
  const now = Date.now()
  const diff = now - ts
  const minutes = Math.floor(diff / 60000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  
  const days = Math.floor(hours / 24)
  return `${days}天前`
}

export function DashboardPage() {
  const { prices, compositeScore, regime, risk, signal, factors, positions, dataSources, traders, socialPosts, news, fearGreed, macro, etf, setLastUpdate } =
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

  const btcPrices = prices.filter(p => p.symbol === 'BTC' || p.symbol === 'BTC/USDT')
  const ethPrices = prices.filter(p => p.symbol === 'ETH' || p.symbol === 'ETH/USDT')

  const dataSourceColumns = [
    { title: '数据源', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string, record: any) => (
        <Space size="small">
          <Badge
            status={status === 'connected' || status === 'normal' ? 'success' : status === 'delayed' ? 'warning' : 'error'}
          />
          <span>
            {status === 'connected' || status === 'normal' ? '正常' : status === 'delayed' ? `延迟${record.delay || ''}` : '异常'}
          </span>
        </Space>
      ),
    },
  ]

  return (
    <div className="p-4 md:p-6 bg-[#0F172A] min-h-screen">
      <AISummaryBar />
      {/* 价格卡片 - 按平台分组 */}
      <Row gutter={[16, 16]} className="mb-4">
        <Col xs={24} md={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">BTC/USDT 各平台价格</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2">
              {btcPrices.length > 0 ? btcPrices.map((price) => (
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
              )) : (
                <Empty description="暂无价格数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">ETH/USDT 各平台价格</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2">
              {ethPrices.length > 0 ? ethPrices.map((price) => (
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
              )) : (
                <Empty description="暂无价格数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </Card>
        </Col>
      </Row>

      {/* 综合得分 + 市场状态 + 风险指数 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col xs={24} md={8}>
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
        <Col xs={24} md={8}>
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
        <Col xs={24} md={8}>
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
        <Col xs={24} md={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0] flex items-center gap-2">
              <UserOutlined className="text-[#EC4899]" /> KOL 交易员
            </span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {traders.length > 0 ? traders.map((trader, idx) => (
                <div key={idx} className="flex items-center justify-between bg-[#0F172A] rounded p-2">
                  <div className="flex items-center gap-2">
                    <Avatar size="small" icon={<UserOutlined />} className="bg-[#8B5CF6]" />
                    <div>
                      <div className="text-sm text-[#F8FAFC]">{trader.name}</div>
                      <div className="text-xs text-[#94A3B8]">
                        {trader.platform || 'Unknown'}
                        {trader.followers && trader.followers > 0 && ` · ${(trader.followers / 1000).toFixed(0)}K 粉丝`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {trader.recentPosition && (
                      <Tag color={trader.recentPosition === 'LONG' ? 'green' : trader.recentPosition === 'SHORT' ? 'red' : 'default'} className="text-xs">
                        {trader.recentPosition} {trader.symbol}
                      </Tag>
                    )}
                    {trader.sentiment !== undefined && (
                      <Tooltip title={`情绪 ${(trader.sentiment * 100).toFixed(0)}%`}>
                        <span className={`text-xs font-semibold ${trader.sentiment >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                          {(trader.sentiment * 100).toFixed(0)}%
                        </span>
                      </Tooltip>
                    )}
                    {trader.winRate !== undefined && trader.winRate > 0 && (
                      <Tag color="blue" className="text-xs">
                        胜率 {(trader.winRate * 100).toFixed(0)}%
                      </Tag>
                    )}
                  </div>
                </div>
              )) : (
                <Empty description="暂无KOL数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card
            title={<span className="text-sm text-[#E2E8F0] flex items-center gap-2">
              <ThunderboltOutlined className="text-[#06B6D4]" /> 社交媒体
            </span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {socialPosts.length > 0 ? socialPosts.map((post) => (
                <div key={post.id} className="bg-[#0F172A] rounded p-2">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[#94A3B8] text-xs">{post.time || post.timestamp}</span>
                    <Tag color="blue" className="text-xs">{platformIcon[post.platform as keyof typeof platformIcon] || post.platform}</Tag>
                    <span className="text-xs text-[#94A3B8]">{post.author}</span>
                    {typeof post.sentiment === 'number' ? (
                      <Tag color={post.sentiment > 0 ? 'green' : 'red'} className="text-xs ml-auto">
                        {post.sentiment > 0 ? '+' : ''}{(post.sentiment * 100).toFixed(0)}%
                      </Tag>
                    ) : (
                      <Tag color={post.sentiment === 'bullish' ? 'green' : post.sentiment === 'bearish' ? 'red' : 'default'} className="text-xs ml-auto">
                        {post.sentiment}
                      </Tag>
                    )}
                  </div>
                  <div className="text-xs text-[#E2E8F0] line-clamp-2">{post.content}</div>
                </div>
              )) : (
                <Empty description="暂无社交媒体数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </Card>
        </Col>
      </Row>

      {/* ETF + 宏观 + 情绪 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col xs={24} md={8}>
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
                <span className={`font-semibold ${etf && etf.net_flow >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                  {etf ? `${etf.net_flow >= 0 ? '+' : ''}$${Math.abs(etf.net_flow).toFixed(0)}M` : '+$150M'}
                </span>
              </div>
              <Progress
                percent={etf ? Math.min(100, Math.max(0, (etf.net_flow + 200) / 4)) : 75}
                strokeColor={etf && etf.net_flow >= 0 ? "#10B981" : "#EF4444"}
                trailColor="#334155"
                showInfo={false}
              />
              <div className="flex justify-between items-center text-xs">
                <span className="text-[#94A3B8]">7日趋势</span>
                <span className={etf && etf.net_flow >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                  {etf && etf.net_flow >= 0 ? '持续流入 ↑' : '持续流出 ↓'}
                </span>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
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
              <Col xs={12} md={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">黄金 (USD/oz)</div>
                  <div className="font-semibold text-[#F8FAFC]">
                    ${macro?.gold?.price?.toFixed(0) || '2,020'}
                  </div>
                  <div className={`text-xs ${(macro?.gold?.change ?? 0) >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                    {(macro?.gold?.change ?? 0) >= 0 ? '▲' : '▼'} {macro?.gold?.change?.toFixed(1) || '+0.5'}%
                  </div>
                </div>
              </Col>
              <Col xs={12} md={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">原油 (USD/bbl)</div>
                  <div className="font-semibold text-[#F8FAFC]">
                    ${macro?.oil?.price?.toFixed(1) || '78.3'}
                  </div>
                  <div className={`text-xs ${(macro?.oil?.change ?? 0) >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                    {(macro?.oil?.change ?? 0) >= 0 ? '▲' : '▼'} {macro?.oil?.change?.toFixed(1) || '-0.3'}%
                  </div>
                </div>
              </Col>
              <Col xs={12} md={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">美元指数</div>
                  <div className="font-semibold text-[#F8FAFC]">
                    {macro?.usd_index?.value?.toFixed(1) || '104.2'}
                  </div>
                  <div className={`text-xs ${(macro?.usd_index?.change ?? 0) >= 0 ? 'text-[#3B82F6]' : 'text-[#EF4444]'}`}>
                    {(macro?.usd_index?.change ?? 0) >= 0 ? '▲' : '▼'} {macro?.usd_index?.change?.toFixed(1) || '+0.1'}%
                  </div>
                </div>
              </Col>
              <Col xs={12} md={12}>
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-[#94A3B8] text-xs mb-1">MSTR</div>
                  <div className="font-semibold text-[#F8FAFC]">$1,520</div>
                  <div className="text-[#10B981] text-xs">▲ +3.2%</div>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={8}>
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
                  <span className={`text-xs font-semibold ${fearGreed && fearGreed.value >= 50 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                    {fearGreed ? `${fearGreed.value} [${fearGreed.classification}]` : '72 [贪婪]'}
                  </span>
                </div>
                <Progress
                  percent={fearGreed?.value || 72}
                  strokeColor={{ '0%': '#EF4444', '50%': '#F97316', '100%': '#10B981' }}
                  trailColor="#334155"
                  showInfo={false}
                />
              </div>
              <Row gutter={[8, 8]}>
                <Col xs={12} md={12}>
                  <div className="bg-[#0F172A] rounded p-2 text-center">
                    <div className="text-[#94A3B8] text-xs">新闻情绪</div>
                    <div className={`text-sm font-semibold ${risk.components.sentiment >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {risk.components.sentiment >= 0 ? '+' : ''}{risk.components.sentiment.toFixed(2)}
                    </div>
                  </div>
                </Col>
                <Col xs={12} md={12}>
                  <div className="bg-[#0F172A] rounded p-2 text-center">
                    <div className="text-[#94A3B8] text-xs">社交情绪</div>
                    <div className={`text-sm font-semibold ${risk.components.flow >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {risk.components.flow >= 0 ? '+' : ''}{risk.components.flow.toFixed(2)}
                    </div>
                  </div>
                </Col>
              </Row>
              <div className="text-center">
                <Tag color={fearGreed && fearGreed.value >= 50 ? 'green' : 'red'} className="text-xs">
                  综合情绪: {fearGreed ? (fearGreed.value >= 50 ? '偏多' : '偏空') : '偏多'}
                </Tag>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 因子 + 决策 + 仓位 */}
      <Row gutter={[16, 16]} className="mb-4" align="stretch">
        <Col xs={24} md={8}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">因子详情</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            <Row gutter={[8, 8]}>
              {factors.length > 0 ? factors.map((factor) => (
                <Col xs={12} md={12} key={factor.type}>
                  <div className="bg-[#0F172A] rounded p-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-[#94A3B8] text-xs">{factor.name}</span>
                      <span className="text-[#94A3B8] text-xs">{factor.weight.toFixed(0)}%</span>
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
              )) : (
                <Col span={24}>
                  <Empty description="暂无因子数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                </Col>
              )}
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={8}>
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
              <Col xs={12} md={12}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs mb-1">置信度</div>
                  <div className="text-lg font-semibold text-[#F59E0B]">{signal.confidence}%</div>
                </div>
              </Col>
              <Col xs={12} md={12}>
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
        <Col xs={24} md={8}>
          <Card
            title={<span className="text-sm text-[#E2E8F0]">仓位管理</span>}
            size="small"
            className="!bg-[#1E293B] !border-[#334155] h-full"
          >
            {positions.length > 0 ? positions.map((pos) => (
              <div key={pos.symbol} className={`bg-[#0F172A] rounded p-3 mb-2 last:mb-0 ${pos.riskLevel === 'DANGER' || pos.riskLevel === 'CRITICAL' ? 'ring-2 ring-[#EF4444]' : ''}`}>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium text-sm text-[#F8FAFC]">{pos.symbol}</span>
                  <div className="flex items-center gap-2">
                    <Tag color={pos.riskLevel === 'SAFE' ? 'green' : pos.riskLevel === 'CAUTION' ? 'blue' : pos.riskLevel === 'WARNING' ? 'orange' : 'red'} className="text-xs">
                      {pos.riskLevel || 'SAFE'}
                    </Tag>
                    <Tag color={pos.side === 'LONG' ? 'green' : pos.side === 'SHORT' ? 'red' : 'default'} className="text-xs">
                      {pos.side}
                    </Tag>
                  </div>
                </div>
                {pos.side !== 'NONE' ? (
                  <div className="space-y-2">
                    <Row gutter={[8, 8]}>
                      <Col xs={8} md={8}>
                        <div className="text-[#94A3B8] text-xs">开仓价</div>
                        <div className="text-sm text-[#F8FAFC]">${pos.entryPrice?.toLocaleString() || '-'}</div>
                      </Col>
                      <Col xs={8} md={8}>
                        <div className="text-[#94A3B8] text-xs">当前价</div>
                        <div className="text-sm text-[#F8FAFC]">${pos.currentPrice?.toLocaleString() || '-'}</div>
                      </Col>
                      <Col xs={8} md={8}>
                        <div className="text-[#94A3B8] text-xs">杠杆</div>
                        <div className={`text-sm font-semibold ${(pos.leverage || 1) > 5 ? 'text-[#F97316]' : 'text-[#F8FAFC]'}`}>
                          {pos.leverage || 1}x
                        </div>
                      </Col>
                    </Row>
                    {pos.liquidationPrice !== undefined && pos.liquidationPrice > 0 && (
                      <Row gutter={[8, 8]}>
                        <Col xs={12} md={12}>
                          <div className="text-[#94A3B8] text-xs">爆仓价</div>
                          <div className={`text-sm font-semibold ${pos.liquidationDistancePct !== undefined && pos.liquidationDistancePct < 10 ? 'text-[#EF4444]' : 'text-[#F8FAFC]'}`}>
                            ${pos.liquidationPrice.toLocaleString()}
                          </div>
                        </Col>
                        <Col xs={12} md={12}>
                          <div className="text-[#94A3B8] text-xs">距爆仓</div>
                          <div className={`text-sm font-semibold ${
                            pos.liquidationDistancePct !== undefined 
                              ? pos.liquidationDistancePct < 5 ? 'text-[#EF4444]' 
                              : pos.liquidationDistancePct < 10 ? 'text-[#F97316]' 
                              : 'text-[#10B981]'
                              : 'text-[#F8FAFC]'
                          }`}>
                            {pos.liquidationDistancePct !== undefined ? `${pos.liquidationDistancePct.toFixed(1)}%` : '-'}
                          </div>
                        </Col>
                      </Row>
                    )}
                    <Row gutter={[8, 8]}>
                      <Col xs={8} md={8}>
                        <div className="text-[#94A3B8] text-xs">仓位</div>
                        <div className="text-sm text-[#F8FAFC]">{pos.size}</div>
                      </Col>
                      <Col xs={8} md={8}>
                        <div className="text-[#94A3B8] text-xs">保证金</div>
                        <div className="text-sm text-[#F8FAFC]">{pos.margin !== undefined ? `$${pos.margin.toFixed(0)}` : '-'}</div>
                      </Col>
                      <Col xs={8} md={8}>
                        <div className="text-[#94A3B8] text-xs">浮盈</div>
                        <div className={`text-sm font-semibold ${pos.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                          {pos.pnl >= 0 ? '+' : ''}{Math.abs(pos.pnl) > 1000 || pos.pnl < -1000 ? `$${(pos.pnl / 1000).toFixed(1)}K` : `$${pos.pnl.toFixed(0)}`}
                        </div>
                      </Col>
                    </Row>
                    {(pos.stopLoss !== undefined || pos.takeProfit !== undefined) && (
                      <Row gutter={[8, 8]}>
                        <Col xs={12} md={12}>
                          <div className="text-[#94A3B8] text-xs">止损</div>
                          <div className="text-sm text-[#EF4444]">{pos.stopLoss ? `$${pos.stopLoss.toLocaleString()}` : '-'}</div>
                        </Col>
                        <Col xs={12} md={12}>
                          <div className="text-[#94A3B8] text-xs">止盈</div>
                          <div className="text-sm text-[#10B981]">{pos.takeProfit ? `$${pos.takeProfit.toLocaleString()}` : '-'}</div>
                        </Col>
                      </Row>
                    )}
                    {pos.fundingRate !== undefined && (
                      <Row gutter={[8, 8]}>
                        <Col xs={12} md={12}>
                          <div className="text-[#94A3B8] text-xs">资金费率</div>
                          <div className={`text-sm font-semibold ${pos.fundingRate >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                            {pos.fundingRate >= 0 ? '+' : ''}{(pos.fundingRate * 100).toFixed(4)}%
                          </div>
                        </Col>
                        <Col xs={12} md={12}>
                          <div className="text-[#94A3B8] text-xs">预估资金费</div>
                          <div className={`text-sm ${pos.fundingFeeEstimate !== undefined && pos.fundingFeeEstimate >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                            {pos.fundingFeeEstimate !== undefined ? `$${pos.fundingFeeEstimate.toFixed(2)}` : '-'}
                          </div>
                        </Col>
                      </Row>
                    )}
                    {pos.riskLevel === 'DANGER' && (
                      <div className="mt-2 p-2 bg-[#EF4444]/20 rounded text-xs text-[#EF4444] text-center">
                        ⚠️ 爆仓风险极高，请及时处理！
                      </div>
                    )}
                    {pos.riskLevel === 'WARNING' && (
                      <div className="mt-2 p-2 bg-[#F97316]/20 rounded text-xs text-[#F97316] text-center">
                        ⚠️ 距爆仓较近，注意风险
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-[#94A3B8] text-xs">等待买入信号...</div>
                )}
              </div>
            )) : (
              <Empty description="暂无仓位数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>

      {/* 新闻 + 数据源状态 */}
      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} md={16}>
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
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {news.length > 0 ? news.slice(0, 10).map((item) => (
                <div 
                  key={item.id} 
                  className="bg-[#0F172A] rounded p-3 hover:bg-[#334155]/50 transition-colors cursor-pointer"
                  onClick={() => item.url && window.open(item.url, '_blank')}
                >
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-[#94A3B8] text-xs">{formatTimeAgo(item.published)}</span>
                    <Tag color="orange" className="text-xs">{item.source}</Tag>
                    <Tag 
                      color={item.sentiment_score >= 0 ? 'green' : 'red'} 
                      className="text-xs"
                    >
                      {item.sentiment_score >= 0 ? '+' : ''}{item.sentiment_score.toFixed(2)}
                    </Tag>
                  </div>
                  <div className="text-sm text-[#F8FAFC]">{item.title}</div>
                  {item.content && item.content !== item.title && (
                    <div className="text-xs text-[#94A3B8] mt-1 line-clamp-2">{item.content}</div>
                  )}
                </div>
              )) : (
                <Empty description="暂无新闻数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
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
              scroll={{ x: 300 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
