import { useEffect, useState } from 'react'
import { Card, Table, Tag, Badge, Tooltip, Space, Typography, Spin, Alert } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { fetchPricesFromAllSources, fetchPriceComparison, fetchPriceSourcesStatus } from '../services/api/tradingApi'
import type { PriceData, PriceComparison, PriceSourceStatus } from '../types'

const { Text, Title } = Typography

interface MultiSourcePriceCardProps {
  symbol?: string
  refreshInterval?: number // 刷新间隔（毫秒）
}

export function MultiSourcePriceCard({ symbol = 'BTC', refreshInterval = 5000 }: MultiSourcePriceCardProps) {
  const [prices, setPrices] = useState<PriceData[]>([])
  const [comparison, setComparison] = useState<PriceComparison | null>(null)
  const [sourceStatus, setSourceStatus] = useState<Record<string, PriceSourceStatus>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // 并行获取所有数据
      const [pricesData, comparisonData, statusData] = await Promise.all([
        fetchPricesFromAllSources(symbol),
        fetchPriceComparison(symbol),
        fetchPriceSourcesStatus()
      ])
      
      setPrices(pricesData.filter(p => p.symbol.includes(symbol)))
      setComparison(comparisonData)
      setSourceStatus(statusData)
      setLastUpdate(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    
    // 定时刷新
    const interval = setInterval(fetchData, refreshInterval)
    return () => clearInterval(interval)
  }, [symbol, refreshInterval])

  // 表格列定义
  const columns = [
    {
      title: '交易所',
      dataIndex: 'exchange',
      key: 'exchange',
      render: (exchange: string) => (
        <Space>
          <Badge 
            status={sourceStatus[exchange]?.status?.available ? 'success' : 'error'} 
          />
          <Text strong style={{ textTransform: 'capitalize' }}>{exchange}</Text>
        </Space>
      )
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (price: number, record: PriceData) => (
        <Space direction="vertical" size={0}>
          <Text strong style={{ fontSize: 16, color: comparison?.bestBid === record.exchange ? '#52c41a' : comparison?.bestAsk === record.exchange ? '#f5222d' : undefined }}>
            ${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </Text>
          {comparison?.bestBid === record.exchange && (
            <Tag color="success">最高</Tag>
          )}
          {comparison?.bestAsk === record.exchange && (
            <Tag color="error">最低</Tag>
          )}
        </Space>
      ),
      sorter: (a: PriceData, b: PriceData) => a.price - b.price
    },
    {
      title: '24h变化',
      dataIndex: 'change24h',
      key: 'change24h',
      render: (change: number) => (
        <Space>
          {change >= 0 ? <ArrowUpOutlined style={{ color: '#52c41a' }} /> : <ArrowDownOutlined style={{ color: '#f5222d' }} />}
          <Text style={{ color: change >= 0 ? '#52c41a' : '#f5222d' }}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </Text>
        </Space>
      )
    },
    {
      title: '延迟',
      key: 'latency',
      render: (_: any, record: PriceData) => {
        const latency = sourceStatus[record.exchange]?.status?.latencyMs || 0
        return (
          <Tooltip title="API响应时间">
            <Tag color={latency < 500 ? 'success' : latency < 1000 ? 'warning' : 'error'}>
              {latency.toFixed(0)}ms
            </Tag>
          </Tooltip>
        )
      }
    },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: PriceData) => {
        const breaker = sourceStatus[record.exchange]?.circuitBreaker
        if (!breaker) return <Tag>未知</Tag>
        
        const statusMap = {
          'closed': { color: 'success', icon: <CheckCircleOutlined />, text: '正常' },
          'open': { color: 'error', icon: <CloseCircleOutlined />, text: '熔断' },
          'half-open': { color: 'warning', icon: <SyncOutlined spin />, text: '恢复中' }
        }
        
        const status = statusMap[breaker.state] || statusMap['closed']
        return (
          <Tag icon={status.icon} color={status.color}>
            {status.text}
          </Tag>
        )
      }
    }
  ]

  if (loading && prices.length === 0) {
    return (
      <Card title={`${symbol}/USDT 多交易所价格`}>
        <Spin tip="加载中...">
          <div style={{ height: 200 }} />
        </Spin>
      </Card>
    )
  }

  return (
    <Card
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>{symbol}/USDT 多交易所价格</Title>
          <Badge count={prices.length} style={{ backgroundColor: '#1890ff' }} />
        </Space>
      }
      extra={
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            最后更新: {lastUpdate.toLocaleTimeString()}
          </Text>
          <SyncOutlined 
            spin={loading} 
            onClick={fetchData} 
            style={{ cursor: 'pointer', color: '#1890ff' }}
          />
        </Space>
      }
    >
      {error && (
        <Alert
          message="获取数据失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          closable
        />
      )}

      {comparison && (
        <Space style={{ marginBottom: 16 }} wrap>
          <Tooltip title="最高与最低价格的百分比差异">
            <Tag color="blue">
              价差: {comparison.priceSpread.toFixed(4)}%
            </Tag>
          </Tooltip>
          {comparison.bestBid && (
            <Tag color="success">
              最佳卖出: {comparison.bestBid}
            </Tag>
          )}
          {comparison.bestAsk && (
            <Tag color="error">
              最佳买入: {comparison.bestAsk}
            </Tag>
          )}
        </Space>
      )}

      <Table
        dataSource={prices}
        columns={columns}
        rowKey="exchange"
        pagination={false}
        size="small"
        loading={loading}
      />

      <div style={{ marginTop: 16, padding: 12, backgroundColor: '#f6ffed', borderRadius: 4 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Text strong>💡 提示</Text>
            <Text>• 最高价格（绿色）适合卖出，最低价格（红色）适合买入</Text>
            <Text>• 价差小于0.1%为正常范围，大于0.5%可能存在套利机会</Text>
            <Text>• 熔断状态表示该数据源暂时不可用，系统会自动切换到备用源</Text>
          </Space>
        </Text>
      </div>
    </Card>
  )
}
