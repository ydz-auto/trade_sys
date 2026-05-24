import { useState } from 'react'
import { Card, Row, Col, Slider, Table, Tag, Button, Tabs, Progress, Statistic } from 'antd'
import { SaveOutlined, ReloadOutlined, ThunderboltOutlined, RiseOutlined, LineChartOutlined } from '@ant-design/icons'
import { useTradingStore } from '../store/tradingStore'

const factorIcons: Record<string, React.ReactNode> = {
  trend: <RiseOutlined />,
  flow: <ThunderboltOutlined />,
  sentiment: <LineChartOutlined />,
  macro: <ThunderboltOutlined />,
  behavioral: <LineChartOutlined />,
  historical: <RiseOutlined />,
}

const factorColors: Record<string, string> = {
  trend: '#3B82F6',
  flow: '#F59E0B',
  sentiment: '#EC4899',
  macro: '#10B981',
  behavioral: '#8B5CF6',
  historical: '#6B7280',
}

export function WeightConfigPage() {
  const { factors, updateFactorWeight, weightVersions, currentVersion } = useTradingStore()
  const [localWeights, setLocalWeights] = useState<Record<string, number>>(
    Object.fromEntries(factors.map((f) => [f.type, f.weight]))
  )

  const total = Object.values(localWeights).reduce((a, b) => a + b, 0)

  const handleWeightChange = (type: string, value: number) => {
    setLocalWeights((prev) => ({ ...prev, [type]: value }))
  }

  const handleApply = () => {
    Object.entries(localWeights).forEach(([type, weight]) => {
      updateFactorWeight(type as any, weight)
    })
  }

  const handleReset = () => {
    setLocalWeights(Object.fromEntries(factors.map((f) => [f.type, f.weight])))
  }

  const currentProduction = weightVersions.find((v) => v.status === 'production')

  const versionColumns = [
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      render: (version: string) => (
        <span className={version === currentVersion ? 'text-[#F59E0B] font-mono' : 'font-mono'}>
          {version}
          {version === currentVersion && <span className="text-xs text-[#94A3B8] ml-1">(当前)</span>}
        </span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag
          color={
            status === 'production' ? 'green' : status === 'testing' ? 'orange' : 'default'
          }
        >
          {status === 'production' ? '生产' : status === 'testing' ? '测试' : '归档'}
        </Tag>
      ),
    },
    {
      title: '权重快照',
      key: 'weights',
      render: (_: any, record: any) => (
        <span className="font-mono text-xs">
          T:{record.weights.trend} F:{record.weights.flow} S:{record.weights.sentiment} M:
          {record.weights.macro} B:{record.weights.behavioral} H:{record.weights.historical}
        </span>
      ),
    },
    {
      title: 'Sharpe',
      dataIndex: 'sharpe',
      key: 'sharpe',
      render: (sharpe: number) => (
        <span className={sharpe >= 1.5 ? 'text-[#10B981]' : sharpe >= 1.0 ? 'text-[#F97316]' : 'text-[#EF4444]'}>
          {sharpe}
        </span>
      ),
    },
    {
      title: '胜率',
      dataIndex: 'winRate',
      key: 'winRate',
      render: (winRate: number) => `${winRate}%`,
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
    },
    {
      title: '创建者',
      dataIndex: 'createdBy',
      key: 'createdBy',
      render: (createdBy: string) => (
        <Tag
          color={
            createdBy === 'LLM优化'
              ? 'purple'
              : createdBy === '手动调整'
              ? 'orange'
              : createdBy === 'A/B测试'
              ? 'blue'
              : 'default'
          }
        >
          {createdBy}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Button type="link" size="small">
          {record.version === currentVersion
            ? '对比'
            : record.status === 'archived'
            ? '回滚'
            : '部署'}
        </Button>
      ),
    },
  ]

  const totalWeight = factors.reduce((sum, f) => sum + f.weight, 0)
  const avgConfidence = factors.reduce((sum, f) => sum + f.confidence, 0) / factors.length
  const totalContribution = factors.reduce((sum, f) => sum + Math.abs((f.weight / 100) * f.value), 0)

  const renderFactorMonitor = () => (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">因子数量</span>}
              value={factors.length}
              valueStyle={{ color: '#F8FAFC', fontSize: '1.5rem', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">总权重</span>}
              value={totalWeight}
              suffix="%"
              valueStyle={{ color: totalWeight === 100 ? '#10B981' : '#EF4444', fontSize: '1.5rem', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">平均置信度</span>}
              value={avgConfidence}
              precision={1}
              suffix="%"
              valueStyle={{ color: '#F59E0B', fontSize: '1.5rem', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic
              title={<span className="text-[#94A3B8] text-xs">综合得分</span>}
              value={(avgConfidence * totalWeight / 100).toFixed(2)}
              suffix="分"
              valueStyle={{ color: '#10B981', fontSize: '1.5rem', fontWeight: 600 }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {factors.map((factor) => {
          const contribution = (factor.weight / 100) * factor.value
          const contributionPercent = totalContribution > 0 ? (Math.abs(contribution) / totalContribution) * 100 : 0
          return (
            <Col xs={24} md={8} key={factor.type}>
              <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${factorColors[factor.type]}20`, color: factorColors[factor.type] }}
                    >
                      {factorIcons[factor.type]}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-[#F8FAFC]">{factor.name}</div>
                      <div className="text-xs text-[#94A3B8]">{factor.nameEn}</div>
                    </div>
                  </div>
                  <Tag color={factor.value >= 0 ? 'green' : 'red'}>
                    {factor.value >= 0 ? '+' : ''}{factor.value.toFixed(2)}
                  </Tag>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-[#94A3B8]">权重</span>
                    <span className="text-[#F8FAFC]">{factor.weight}%</span>
                  </div>
                  <Progress percent={factor.weight} showInfo={false} strokeColor={factorColors[factor.type]} trailColor="#334155" size="small" />

                  <div className="flex justify-between text-xs">
                    <span className="text-[#94A3B8]">置信度</span>
                    <span className="text-[#F8FAFC]">{factor.confidence}%</span>
                  </div>
                  <Progress percent={factor.confidence} showInfo={false} strokeColor={factorColors[factor.type]} trailColor="#334155" size="small" />

                  <div className="flex justify-between text-xs">
                    <span className="text-[#94A3B8]">贡献度</span>
                    <span className={contribution >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                      {contribution >= 0 ? '+' : ''}{contribution.toFixed(4)} ({contributionPercent.toFixed(1)}%)
                    </span>
                  </div>
                  <Progress percent={contributionPercent} showInfo={false} strokeColor={contribution >= 0 ? '#10B981' : '#EF4444'} trailColor="#334155" size="small" />
                </div>
              </Card>
            </Col>
          )
        })}
      </Row>

      <Card title={<span className="text-sm text-[#E2E8F0]">因子贡献度分布</span>} size="small" className="!bg-[#1E293B] !border-[#334155]">
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <div className="space-y-3">
              {factors.map((factor) => {
                const contribution = (factor.weight / 100) * factor.value
                return (
                  <div key={factor.type}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[#94A3B8]">{factor.name}</span>
                      <span className={contribution >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                        {contribution >= 0 ? '+' : ''}{contribution.toFixed(4)}
                      </span>
                    </div>
                    <Progress percent={Math.abs(contribution / totalContribution * 100) || 0} showInfo={false} strokeColor={contribution >= 0 ? '#10B981' : '#EF4444'} trailColor="#334155" size="small" />
                  </div>
                )
              })}
            </div>
          </Col>
          <Col xs={24} md={12}>
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="text-xs text-[#94A3B8] mb-2">正向贡献</div>
                <div className="text-2xl font-bold text-[#10B981]">
                  +{factors.filter(f => (f.weight / 100) * f.value > 0).length}
                </div>
                <div className="text-xs text-[#94A3B8] mt-2">负向贡献</div>
                <div className="text-2xl font-bold text-[#EF4444]">
                  -{factors.filter(f => (f.weight / 100) * f.value < 0).length}
                </div>
              </div>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  )

  const tabItems = [
    {
      key: 'monitor',
      label: '因子监控',
      children: renderFactorMonitor(),
    },
    {
      key: 'weights',
      label: '权重配置',
      children: (
        <Row gutter={16}>
          <Col xs={24} md={16}>
            <Card
              title={
                <span>
                  当前因子权重 ({currentVersion}) -{' '}
                  <span className="text-xs text-[#94A3B8]">Sharpe: {currentProduction?.sharpe}</span>
                </span>
              }
              extra={<Tag color="green">生产中</Tag>}
              className="!bg-[#1E293B] !border-[#334155]"
            >
              <Row gutter={[16, 16]}>
                {factors.map((factor) => (
                  <Col xs={24} md={12} key={factor.type}>
                    <div className="bg-[#0F172A] rounded-lg p-4">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{factor.name}</span>
                          <Tag>{factor.nameEn}</Tag>
                        </div>
                        <span className="font-mono text-[#F59E0B] text-lg">
                          {localWeights[factor.type]}%
                        </span>
                      </div>
                      <Slider
                        value={localWeights[factor.type]}
                        onChange={(value) => handleWeightChange(factor.type, value)}
                        min={0}
                        max={100}
                        trackStyle={{ backgroundColor: '#F59E0B' }}
                        handleStyle={{ borderColor: '#F59E0B', backgroundColor: '#F59E0B' }}
                      />
                      <Progress
                        percent={localWeights[factor.type]}
                        showInfo={false}
                        strokeColor="#F59E0B"
                        trailColor="#334155"
                        size="small"
                      />
                    </div>
                  </Col>
                ))}
              </Row>

              <div className="flex flex-col md:flex-row items-center justify-between mt-6 pt-4 border-t border-[#334155] gap-4">
                <div className="text-sm text-[#94A3B8]">
                  总计:{' '}
                  <span className={`font-mono ${total === 100 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                    {total}%
                  </span>{' '}
                  (应为100%)
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button icon={<ReloadOutlined />} onClick={handleReset}>
                    重置
                  </Button>
                  <Button>保存到新版本</Button>
                  <Button type="primary" icon={<SaveOutlined />} onClick={handleApply}>
                    应用修改
                  </Button>
                </div>
              </div>
            </Card>
          </Col>

          <Col xs={24} md={8}>
            <Card
              title={
                <span className="flex items-center gap-2">
                  <ThunderboltOutlined className="text-[#8B5CF6]" />
                  LLM 权重建议
                  <Tag color="purple" className="ml-auto">MiniMax</Tag>
                </span>
              }
              className="!bg-[#1E293B] !border-[#334155]"
            >
              <div className="space-y-4">
                <div className="bg-[#0F172A] rounded p-3">
                  <div className="text-xs text-[#94A3B8] mb-2">基于近期市场分析:</div>
                  <div className="text-sm">
                    当前 <Tag color="red" className="text-xs">RISK_OFF</Tag> 市场环境下，建议:
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-[#94A3B8]">提高趋势因子</span>
                    <span className="font-mono text-[#F59E0B]">30% → 35%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#94A3B8]">降低情绪因子</span>
                    <span className="font-mono text-[#F59E0B]">20% → 15%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#94A3B8]">增加宏观因子</span>
                    <span className="font-mono text-[#F59E0B]">15% → 20%</span>
                  </div>
                </div>

                <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded p-3">
                  <div className="text-xs text-[#F59E0B] mb-1">LLM 分析理由:</div>
                  <div className="text-xs text-[#94A3B8]">
                    市场恐慌时，情绪因子容易产生误判。增加趋势和宏观因子权重可提高稳定性。
                  </div>
                </div>

                <Button type="primary" block className="bg-[#8B5CF6] border-[#8B5CF6]">
                  应用 LLM 建议
                </Button>
                <Button block>查看完整分析报告</Button>
              </div>
            </Card>
          </Col>
        </Row>
      ),
    },
    {
      key: 'versions',
      label: '版本历史',
      children: (
        <Card title="版本历史" className="!bg-[#1E293B] !border-[#334155]">
          <Table
            dataSource={weightVersions}
            columns={versionColumns}
            pagination={false}
            rowKey="version"
            scroll={{ x: 600 }}
          />
        </Card>
      ),
    },
    { key: 'strategy', label: '策略迭代', children: <div>策略迭代内容</div> },
    { key: 'control', label: '控制中心', children: <div>控制中心内容</div> },
  ]

  return (
    <div className="space-y-4">
      <Tabs items={tabItems} defaultActiveKey="monitor" />
    </div>
  )
}
