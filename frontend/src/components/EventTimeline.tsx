/**
 * Event Timeline Component - 事件时间线
 * 
 * 显示 Runtime 事件流：
 *   09:31 ETF inflow detected
 *   09:32 4H bullish regime confirmed
 *   09:33 Funding normalized
 *   09:34 LONG signal generated
 *   09:35 Risk approved
 *   09:35 Order executed
 */

import { useTimeline } from '../hooks/useRealtime'

interface EventTimelineProps {
  maxHeight?: string
  symbol?: string
  showFilters?: boolean
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
}

export function EventTimeline({ 
  maxHeight = '600px',
  symbol,
}: EventTimelineProps) {
  const events = useTimeline(100)
  
  const filteredEvents = symbol 
    ? events.filter(e => e.symbol === symbol)
    : events

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Event Timeline</h2>
        <span className="text-sm text-gray-400">
          {filteredEvents.length} events
        </span>
      </div>

      <div 
        className="space-y-2 overflow-y-auto"
        style={{ maxHeight }}
      >
        {filteredEvents.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            No events yet. Waiting for runtime activity...
          </div>
        ) : (
          filteredEvents.map((event) => (
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
          ))
        )}
      </div>
    </div>
  )
}

export default EventTimeline
