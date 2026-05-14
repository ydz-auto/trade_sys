import { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Slider, Button, Space, Typography, Tag, Table, Statistic, Alert } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, StepBackwardOutlined, StepForwardOutlined, ReloadOutlined } from '@ant-design/icons'

const { Text, Title } = Typography

interface ReplaySnapshot {
  id: string
  timestamp: number
  datetime: string
  prices: any[]
  factors: any[]
  signal: any
  regime: any
  risk: any
}

export function ReplaySystem() {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [snapshots, setSnapshots] = useState<ReplaySnapshot[]>([])
  const [currentSnapshot, setCurrentSnapshot] = useState<ReplaySnapshot | null>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  // 生成模拟快照数据
  useEffect(() => {
    generateMockSnapshots()
  }, [])

  // 播放控制
  useEffect(() => {
    if (isPlaying && snapshots.length > 0) {
      timerRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          const nextIndex = prev + 1
          if (nextIndex >= snapshots.length) {
            setIsPlaying(false)
            return prev
          }
          return nextIndex
        })
      }, 1000 / speed)
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [isPlaying, speed, snapshots.length])

  // 更新当前快照
  useEffect(() => {
    if (snapshots[currentIndex]) {
      setCurrentSnapshot(snapshots[currentIndex])
    }
  }, [currentIndex, snapshots])

  const generateMockSnapshots = () => {
    const mockSnapshots: ReplaySnapshot[] = []
    const now = Date.now()
    
    for (let i = 0; i < 60; i++) {
      const timestamp = now - (60 - i) * 60000
      mockSnapshots.push({
        id: `snap_${timestamp}`,
        timestamp,
        datetime: new Date(timestamp).toISOString(),
        prices: [
          { symbol: 'BTC', price: 68000 + Math.sin(i / 10) * 1000, change24h: Math.random() * 6 - 3 },
          { symbol: 'ETH', price: 3500 + Math.sin(i / 8) * 100, change24h: Math.random() * 8 - 4 },
          { symbol: 'SOL', price: 140 + Math.sin(i / 6) * 10, change24h: Math.random() * 10 - 5 },
        ],
        factors: [
          { type: 'trend', name: '趋势因子', value: Math.sin(i / 5), weight: 0.3 },
          { type: 'flow', name: '资金流', value: Math.cos(i / 4), weight: 0.25 },
        ],
        signal: {
          action: i % 15 < 5 ? 'BUY' : i % 15 < 10 ? 'SELL' : 'HOLD',
          confidence: 50 + Math.random() * 40,
        },
        regime: {
          state: i % 20 < 10 ? 'RISK_ON' : 'RISK_OFF',
          volatility: 20 + Math.random() * 30,
        },
        risk: {
          total: 30 + Math.random() * 50,
          level: 'medium',
        },
      })
    }
    
    setSnapshots(mockSnapshots)
    setCurrentSnapshot(mockSnapshots[0])
  }

  const togglePlay = () => {
    setIsPlaying(!isPlaying)
  }

  const stepBack = () => {
    setCurrentIndex(prev => Math.max(0, prev - 1))
  }

  const stepForward = () => {
    setCurrentIndex(prev => Math.min(snapshots.length - 1, prev + 1))
  }

  const handleSlider = (value: number) => {
    setCurrentIndex(value)
  }

  const formatDateTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString()
  }

  const getActionColor = (action: string) => {
    return action === 'BUY' ? 'green' : action === 'SELL' ? 'red' : 'default'
  }

  return (
    <div className="space-y-4">
      <Title level={4}>⏪ 回测系统</Title>
      <Alert
        message="系统回放系统让您可以回到任意时间点查看历史市场状态和系统决策。"
        type="info"
        showIcon
      />
      
      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="回放控制">
            <div className="mb-4">
              <div className="flex justify-between mb-2">
                <Text type="secondary">
                  {currentSnapshot ? formatDateTime(currentSnapshot.timestamp) : '未选择'}
                </Text>
                <Space>
                  <Text type="secondary">速度: </Text>
                  <Button size="small" onClick={() => setSpeed(0.5)}>0.5x</Button>
                  <Button size="small" onClick={() => setSpeed(1)}>1x</Button>
                  <Button size="small" onClick={() => setSpeed(2)}>2x</Button>
                  <Button size="small" onClick={() => setSpeed(5)}>5x</Button>
                </Space>
              </div>
              
              <Slider
                min={0}
                max={snapshots.length - 1}
                value={currentIndex}
                onChange={handleSlider}
                tooltip={{ formatter: (value) => snapshots[value] && formatDateTime(snapshots[value].timestamp) }}
              />
              
              <div className="flex justify-center mt-4">
                <Space>
                  <Button icon={<StepBackwardOutlined />} onClick={stepBack} />
                  <Button
                    icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                    type="primary"
                    onClick={togglePlay}
                  >
                    {isPlaying ? '暂停' : '播放'}
                  </Button>
                  <Button icon={<StepForwardOutlined />} onClick={stepForward} />
                  <Button icon={<ReloadOutlined />} onClick={generateMockSnapshots}>重置</Button>
                </Space>
              </div>
            </div>
          </Card>

          {currentSnapshot && (
            <Card title="历史快照" className="mt-4">
              <Row gutter={16}>
                <Col xs={12} md={6}>
                  <Statistic
                    title="BTC价格"
                    value={currentSnapshot.prices[0]?.price || 0}
                    precision={2}
                    prefix="$"
                    valueStyle={{ color: currentSnapshot.prices[0]?.change24h >= 0 ? '#10B981' : '#EF4444' }}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    24h: {currentSnapshot.prices[0]?.change24h?.toFixed(2)}%
                  </div>
                </Col>
                <Col xs={12} md={6}>
                  <Statistic
                    title="ETH价格"
                    value={currentSnapshot.prices[1]?.price || 0}
                    precision={2}
                    prefix="$"
                    valueStyle={{ color: currentSnapshot.prices[1]?.change24h >= 0 ? '#10B981' : '#EF4444' }}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    24h: {currentSnapshot.prices[1]?.change24h?.toFixed(2)}%
                  </div>
                </Col>
                <Col xs={12} md={6}>
                  <Statistic
                    title="信号"
                    value={0}
                    formatter={() => <Tag color={getActionColor(currentSnapshot.signal?.action || 'HOLD')}>
                      {currentSnapshot.signal?.action}
                    </Tag>
                  }
                  <div className="text-xs text-gray-500 mt-1">
                    置信度: {currentSnapshot.signal?.confidence?.toFixed(0)}%
                  </div>
                </Col>
                <Col xs={12} md={6}>
                  <Statistic
                    title="风险"
                    value={currentSnapshot.risk?.total || 0}
                    precision={0}
                    valueStyle={{ color: currentSnapshot.risk?.level === 'low' ? '#10B981' : currentSnapshot.risk?.level === 'medium' ? '#F59E0B' : '#EF4444' }}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    状态: {currentSnapshot.regime?.state}
                  </div>
                </Col>
              </Row>

              <div className="mt-4">
                <Text strong className="block mb-2">因子状态:</Text>
                <div className="flex gap-2">
                  {currentSnapshot.factors.map((factor, index) => (
                    <Tag key={index} color={factor.value >= 0 ? 'green' : 'red'}>
                      {factor.name}: {factor.value.toFixed(2)}
                    </Tag>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </Col>

        <Col xs={24} md={8}>
          <Card title="历史快照列表">
            <Table
              dataSource={snapshots}
              columns={[
                {
                  title: '时间',
                  dataIndex: 'datetime',
                  key: 'datetime',
                  render: (dt) => new Date(dt).toLocaleTimeString(),
                },
                {
                  title: '信号',
                  dataIndex: 'signal',
                  key: 'signal',
                  render: (s) => <Tag color={getActionColor(s?.action)}>{s?.action}</Tag>,
                },
                {
                  title: 'Regime',
                  dataIndex: 'regime',
                  key: 'regime',
                  render: (r) => <Tag color={r?.state === 'RISK_ON' ? 'green' : 'orange'}>{r?.state}</Tag>,
                },
                {
                  title: '风险',
                  dataIndex: 'risk',
                  key: 'risk',
                  render: (r) => r?.total?.toFixed(0),
                },
              ]}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 5 }}
              onRow={(record) => ({
                onClick: () => {
                  const index = snapshots.findIndex(s => s.id === record.id)
                  if (index !== -1) {
                    setCurrentIndex(index)
                  }
                },
              })}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
