interface LiveIndicatorProps {
  className?: string
}

export function LiveIndicator({ className = '' }: LiveIndicatorProps) {
  return (
    <span className={`relative flex h-2 w-2 ${className}`}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-bullish opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-bullish"></span>
    </span>
  )
}
