/**
 * useTimelineHistory Hook - Timeline历史数据加载
 * 
 * 支持分页加载历史事件数据
 */

import { useState, useEffect, useCallback } from 'react'

interface TimelineEvent {
  event_id: string
  event_type: string
  symbol: string
  timestamp: string
  display_time?: string
  title: string
  description: string
  severity: string
}

interface TimelineResponse {
  events: TimelineEvent[]
  count: number
}

export function useTimelineHistory(symbol?: string, pageSize: number = 50) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [page, setPage] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const fetchEvents = useCallback(async (pageNum: number, append: boolean = false) => {
    if (loading) return

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        limit: String(pageSize),
      })
      
      if (symbol) {
        params.append('symbol', symbol)
      }

      const response = await fetch(`/api/v1/projection/timeline?${params}`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data: TimelineResponse = await response.json()
      
      if (append) {
        setEvents(prev => {
          const existingIds = new Set(prev.map(e => e.event_id))
          const newEvents = data.events.filter(e => !existingIds.has(e.event_id))
          return [...prev, ...newEvents]
        })
      } else {
        setEvents(data.events)
      }
      
      setHasMore(data.events.length === pageSize)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch events')
      console.error('Failed to fetch timeline events:', err)
    } finally {
      setLoading(false)
    }
  }, [symbol, pageSize, loading])

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      const nextPage = page + 1
      setPage(nextPage)
      fetchEvents(nextPage, true)
    }
  }, [loading, hasMore, page, fetchEvents])

  const refresh = useCallback(() => {
    setPage(0)
    setHasMore(true)
    fetchEvents(0, false)
  }, [fetchEvents])

  useEffect(() => {
    fetchEvents(0, false)
  }, [symbol])

  return {
    events,
    loading,
    hasMore,
    error,
    loadMore,
    refresh,
  }
}
