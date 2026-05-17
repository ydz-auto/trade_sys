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
 */

import { useEffect, useRef, useCallback } from 'react'
import { useTimeline } from '../hooks/useRealtime'
import { useTimelineHistory } from '../hooks/useTimelineHistory'

interface EventTimelineProps {
  maxHeight?: string
  symbol?: string
  showFilters?: boolean
  enableInfiniteScroll?: boolean
}

const severityColors: Record<string, string> = {
  info: 'text-blue-400',
  success: 'text-green-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
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
  maxHeight = '600px',
  symbol,
  enableInfiniteScroll = true,
}: EventTimelineProps) {
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

  const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
    const [target] = entries
    if (target.isIntersecting && hasMore && !loading) {
      loadMore()
    }
  }, [hasMore, loading, loadMore])

  useEffect(() => {
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
  }, [handleObserver])

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Event Timeline</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">
            {allEvents.length} events
          </span>
          {enableInfiniteScroll && (
            <button
              onClick={refresh}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              Refresh
            </button>
          )}
        </div>
      </div>

      <div 
        className="space-y-2 overflow-y-auto"
        style={{ maxHeight }}
      >
        {allEvents.length === 0 && !loading ? (
          <div className="text-gray-500 text-center py-8">
            No events yet. Waiting for runtime activity...
          </div>
        ) : (
          <>
            {allEvents.map((event) => (
              <div
                key={event.event_id}
                className="flex items-start gap-3 p-2 rounded hover:bg-gray-800 transition-colors"
              >
                <span className="text-lg">
                  {eventTypeIcons[event.event_type] || '📌'}
                </span>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 font-mono">
                      {event.display_time || event.timestamp.split('T')[1]?.split('.')[0] || event.timestamp}
                    </span>
                    <span className="text-xs text-gray-600">
                      {event.symbol}
                    </span>
                  </div>
                  
                  <p className={`text-sm ${severityColors[event.severity] || 'text-gray-300'}`}>
                    {event.title}
                  </p>
                  
                  {event.description && (
                    <p className="text-xs text-gray-500 truncate">
                      {event.description}
                    </p>
                  )}
                </div>
              </div>
            ))}

            {enableInfiniteScroll && (
              <div ref={loadMoreRef} className="py-4 text-center">
                {loading && (
                  <div className="text-gray-400 text-sm">
                    Loading more events...
                  </div>
                )}
                {!hasMore && allEvents.length > 0 && (
                  <div className="text-gray-500 text-sm">
                    No more events
                  </div>
                )}
                {error && (
                  <div className="text-red-400 text-sm">
                    {error}
                    <button 
                      onClick={loadMore}
                      className="ml-2 text-blue-400 hover:text-blue-300"
                    >
                      Retry
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
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
