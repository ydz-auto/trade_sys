/**
 * Event Timeline Component - 事件时间线
 * 
 * 显示 Runtime 事件流，支持滚动加载分页：
 *   09:31 ETF inflow detected
 *   09:32 4H bullish regime confirmed
 *   09:33 Funding normalized
 *   09:34 LONG signal generated
 *   09:35 Risk approved
 *   09:35 Order executed
 * 
 * 支持折叠/展开模式：
 *   - 折叠时：单行滚动显示最新事件
 *   - 展开时：完整列表显示
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { Card, Tag, Button, Empty, Spin, Space, Typography } from 'antd'
import { ReloadOutlined, ClockCircleOutlined, UpOutlined, DownOutlined, ExpandOutlined, CompressOutlined } from '@ant-design/icons'
import { useTimeline } from '../hooks/useRealtime'
import { useTimelineHistory } from '../hooks/useTimelineHistory'

const { Text } = Typography

interface EventTimelineProps {
  maxHeight?: string
  symbol?: string
  showFilters?: boolean
  enableInfiniteScroll?: boolean
  collapsible?: boolean
  defaultCollapsed?: boolean
}

const severityColors: Record<string, string> = {
  info: '#3B82F6',
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
}

const eventTypeIcons: Record<string, string> = {
  raw_data: '📰',
  event: '⚡',
  signal: '📊',
  decision: '🎯',
  risk_checked: '🛡️',
  order: '📝',
  fill: '💰',
  pnl: '📈',
  news: '📰',
  odaily_raw: '📰',
}

export function EventTimeline({ 
  maxHeight = '400px',
  symbol,
  enableInfiniteScroll = true,
  collapsible = true,
  defaultCollapsed = true,
}: EventTimelineProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  const [currentEventIndex, setCurrentEventIndex] = useState(0)
  
  const realtimeEvents = useTimeline(100)
  const { 
    events: historyEvents, 
    loading, 
    hasMore, 
    error,
    loadMore,
    refresh 
  } = useTimelineHistory(symbol, 50)
  
  const observerRef = useRef<IntersectionObserver | null>(null)
  const loadMoreRef = useRef<HTMLDivElement | null>(null)

  const filteredRealtimeEvents = symbol 
    ? realtimeEvents.filter(e => e.symbol === symbol)
    : realtimeEvents

  const allEvents = enableInfiniteScroll 
    ? mergeEvents(filteredRealtimeEvents, historyEvents)
    : filteredRealtimeEvents

  const currentEvent = allEvents[currentEventIndex]

  useEffect(() => {
    if (collapsed && allEvents.length > 0) {
      const interval = setInterval(() => {
        setCurrentEventIndex(prev => (prev + 1) % allEvents.length)
      }, 3000)
      return () => clearInterval(interval)
    }
  }, [collapsed, allEvents.length])

  const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
    const [target] = entries
    if (target.isIntersecting && hasMore && !loading) {
      loadMore()
    }
  }, [hasMore, loading, loadMore])

  useEffect(() => {
    if (collapsed) return
    
    const option = {
      root: null,
      rootMargin: '20px',
      threshold: 0,
    }

    observerRef.current = new IntersectionObserver(handleObserver, option)

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current)
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect()
      }
    }
  }, [handleObserver, collapsed])

  const toggleCollapse = () => {
    setCollapsed(!collapsed)
    if (!collapsed) {
      setCurrentEventIndex(0)
    }
  }

  const renderCollapsedView = () => (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '8px 16px',
        cursor: 'pointer',
      }}
      onClick={toggleCollapse}
    >
      <span style={{ fontSize: '18px', lineHeight: 1 }}>
        {currentEvent ? (eventTypeIcons[currentEvent.event_type] || '📌') : '📌'}
      </span>
      
      <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Text style={{ fontSize: '12px', color: '#64748B', fontFamily: 'monospace' }}>
            {currentEvent?.display_time || currentEvent?.timestamp?.split('T')[1]?.split('.')[0] || '--:--:--'}
          </Text>
          {currentEvent?.symbol && (
            <Tag style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}>
              {currentEvent.symbol}
            </Tag>
          )}
        </div>
        
        <Text 
          style={{ 
            fontSize: '13px',
            color: currentEvent ? (severityColors[currentEvent.severity] || '#E2E8F0') : '#64748B',
            display: 'block',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {currentEvent?.title || '暂无事件，等待运行态活动...'}
        </Text>
      </div>

      <Space>
        <Tag color="blue">{allEvents.length}</Tag>
        <Button 
          type="text" 
          size="small" 
          icon={<ExpandOutlined />}
          onClick={(e) => {
            e.stopPropagation()
            toggleCollapse()
          }}
        />
      </Space>
    </div>
  )

  const renderExpandedView = () => (
    <>
      {allEvents.length === 0 && !loading ? (
        <Empty 
          description="暂无事件" 
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ padding: '20px 0' }}
        />
      ) : (
        <>
          {allEvents.map((event) => (
            <div
              key={event.event_id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '8px 16px',
                borderBottom: '1px solid #1E293B',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#1E293B'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent'
              }}
            >
              <span style={{ fontSize: '18px', lineHeight: 1 }}>
                {eventTypeIcons[event.event_type] || '📌'}
              </span>
              
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <Text style={{ fontSize: '12px', color: '#64748B', fontFamily: 'monospace' }}>
                    {event.display_time || event.timestamp.split('T')[1]?.split('.')[0] || event.timestamp}
                  </Text>
                  {event.symbol && (
                    <Tag style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}>
                      {event.symbol}
                    </Tag>
                  )}
                  {event.event_type && (
                    <Tag 
                      style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}
                      color="default"
                    >
                      {event.event_type}
                    </Tag>
                  )}
                </div>
                
                <Text 
                  style={{ 
                    fontSize: '13px',
                    color: severityColors[event.severity] || '#E2E8F0',
                    display: 'block',
                  }}
                >
                  {event.title}
                </Text>
                
                {event.description && (
                  <Text 
                    style={{ 
                      fontSize: '12px', 
                      color: '#64748B',
                      display: 'block',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {event.description}
                  </Text>
                )}
              </div>
            </div>
          ))}

          {enableInfiniteScroll && (
            <div ref={loadMoreRef} style={{ padding: '16px', textAlign: 'center' }}>
              {loading && (
                <Spin size="small" />
              )}
              {!hasMore && allEvents.length > 0 && (
                <Text style={{ fontSize: '12px', color: '#64748B' }}>
                  没有更多事件了
                </Text>
              )}
              {error && (
                <div>
                  <Text style={{ fontSize: '12px', color: '#EF4444' }}>
                    {error}
                  </Text>
                  <Button 
                    type="link" 
                    size="small"
                    onClick={loadMore}
                  >
                    重试
                  </Button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </>
  )

  return (
    <Card
      size="small"
      title={
        <Space onClick={collapsible ? toggleCollapse : undefined} style={{ cursor: collapsible ? 'pointer' : 'default' }}>
          <ClockCircleOutlined />
          <span>事件时间线</span>
          {collapsed && <Tag color="blue">{allEvents.length}</Tag>}
        </Space>
      }
      extra={
        <Space>
          <Button 
            type="text" 
            size="small" 
            icon={<ReloadOutlined />} 
            onClick={refresh}
          />
          {collapsible && (
            <Button 
              type="text" 
              size="small" 
              icon={collapsed ? <ExpandOutlined /> : <CompressOutlined />}
              onClick={toggleCollapse}
            />
          )}
        </Space>
      }
      styles={{
        body: { 
          padding: collapsed ? 0 : '8px 0', 
          maxHeight: collapsed ? 'auto' : maxHeight, 
          overflowY: collapsed ? 'visible' : 'auto' 
        }
      }}
    >
      {collapsed ? renderCollapsedView() : renderExpandedView()}
    </Card>
  )
}

function mergeEvents(realtimeEvents: any[], historyEvents: any[]): any[] {
  const eventMap = new Map<string, any>()
  
  historyEvents.forEach(event => {
    eventMap.set(event.event_id, event)
  })
  
  realtimeEvents.forEach(event => {
    if (!eventMap.has(event.event_id)) {
      eventMap.set(event.event_id, event)
    }
  })
  
  return Array.from(eventMap.values()).sort((a, b) => 
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  )
}

export default EventTimeline
