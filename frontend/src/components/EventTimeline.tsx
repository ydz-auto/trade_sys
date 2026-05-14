import { useState, useEffect, useRef } from 'react'
import { Badge, Card, Typography } from 'antd'
import { ClockCircleOutlined, ThunderboltOutlined, RiseOutlined, FireOutlined, WarningOutlined, CheckCircleOutlined } from '@ant-design/icons'

const { Text } = Typography

export interface SystemEvent {
  id: string
  timestamp: number
  type: 'signal' | 'price' | 'risk' | 'system' | 'news' | 'execution'
  level: 'info' | 'warning' | 'error' | 'success'
  title: string
  description?: string
  metadata?: Record<string, any>
}

const EVENT_ICONS: Record<SystemEvent['type'], React.ReactNode> = {
  signal: <ThunderboltOutlined />,
  price: <RiseOutlined />,
  risk: <WarningOutlined />,
  system: <CheckCircleOutlined />,
  news: <FireOutlined />,
  execution: <CheckCircleOutlined />,
}

const EVENT_COLORS: Record<SystemEvent['level'], string> = {
  info: '#3B82F6',
  warning: '#F59E0B',
  error: '#EF4444',
  success: '#10B981',
}

// 模拟事件生成器 - 实际项目中应该从WebSocket或API获取
const generateMockEvent = (): SystemEvent => {
  const eventTypes: SystemEvent['type'][] = ['price', 'signal', 'risk', 'system', 'news', 'execution']
  const levels: SystemEvent['level'][] = ['info', 'warning', 'error', 'success']
  const type = eventTypes[Math.floor(Math.random() * eventTypes.length)]
  const level = levels[Math.floor(Math.random() * levels.length)]

  const events = {
    price: ['BTC突破79k', 'ETH上涨3%', 'SOL突破95'],
    signal: ['LONG信号触发', 'HOLD模式', 'SELL警告'],
    risk: ['波动率上升', '持仓风险降低', '市场流动性'],
    system: ['API连接正常', '数据同步中', '服务健康'],
    news: ['ETF流入120M', '新监管消息', '机构增持'],
    execution: ['订单已成交', '开仓成功', '部分成交'],
  }

  return {
    id: Date.now().toString(),
    timestamp: Date.now(),
    type,
    level,
    title: events[type][Math.floor(Math.random() * events[type].length)],
    description: `实时更新 ${new Date().toLocaleTimeString()}`,
  }
}

export function EventTimeline() {
  const [events, setEvents] = useState<SystemEvent[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const [isPaused, setIsPaused] = useState(false)

  // 初始化事件
  useEffect(() => {
    const initialEvents: SystemEvent[] = [
      { id: '1', timestamp: Date.now() - 60000, type: 'price', level: 'success', title: 'BTC价格突破79,400', description: '24h +2.3%' },
      { id: '2', timestamp: Date.now() - 45000, type: 'system', level: 'info', title: '数据源连接正常', description: 'Binance API延迟42ms' },
      { id: '3', timestamp: Date.now() - 30000, type: 'news', level: 'info', title: 'Cointelegraph: ETF资金流入120M', description: '机构持续增持BTC' },
      { id: '4', timestamp: Date.now() - 15000, type: 'signal', level: 'warning', title: 'AI置信度下降', description: '因子分歧，降低仓位' },
      { id: '5', timestamp: Date.now(), type: 'risk', level: 'success', title: '风险指数: Medium', description: '系统处于可控状态' },
    ]
    setEvents(initialEvents)
  }, [])

  // 模拟实时事件流
  useEffect(() => {
    if (isPaused) return

    const interval = setInterval(() => {
      if (Math.random() > 0.7) { // 30%概率生成新事件
        const newEvent = generateMockEvent()
        setEvents(prev => [newEvent, ...prev].slice(0, 50))
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [isPaused])

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current && !isPaused) {
      scrollRef.current.scrollTop = 0
    }
  }, [events, isPaused])

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <Card 
      size="small"
      style={{ 
        backgroundColor: '#1E293B', 
        borderTop: '1px solid #334155',
        borderRadius: 0,
      }}
      bodyStyle={{ padding: '12px 16px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Badge status="processing" />
          <Text strong style={{ color: '#F8FAFC' }}>Event Stream</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>| 实时事件流</Text>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {events.length} events · {isPaused ? 'Paused' : 'Live'}
          </Text>
        </div>
      </div>

      <div
        ref={scrollRef}
        style={{
          height: 140,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column-reverse',
          gap: 8,
          scrollbarWidth: 'thin',
          scrollbarColor: '#334155 #1E293B',
        }}
      >
        {events.map((event, index) => (
          <div
            key={event.id}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
              padding: '6px 8px',
              borderRadius: 6,
              backgroundColor: index === 0 ? 'rgba(245, 158, 11, 0.1)' : 'transparent',
              transition: 'background-color 0.3s',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 24,
                height: 24,
                borderRadius: 4,
                backgroundColor: `${EVENT_COLORS[event.level]}20`,
                color: EVENT_COLORS[event.level],
                flexShrink: 0,
              }}
            >
              {EVENT_ICONS[event.type]}
            </div>
            
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ color: '#F8FAFC', fontSize: 13 }}>
                  {event.title}
                </Text>
                {index === 0 && (
                  <Badge status="processing" text={<Text type="secondary" style={{ fontSize: 11 }}>New</Text>} />
                )}
              </div>
              {event.description && (
                <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                  {event.description}
                </Text>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
              <ClockCircleOutlined style={{ color: '#6B7280', fontSize: 11 }} />
              <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>
                {formatTime(event.timestamp)}
              </Text>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
