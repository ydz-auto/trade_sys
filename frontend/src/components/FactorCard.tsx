import { TrendingUp, Activity, Globe, Users, Clock } from 'lucide-react'
import clsx from 'clsx'
import type { Factor } from '../types'

const iconMap = {
  trend: TrendingUp,
  flow: Activity,
  sentiment: Users,
  macro: Globe,
  behavioral: Users,
  historical: Clock,
}

const colorMap: Record<string, string> = {
  primary: 'text-primary bg-primary/20',
  neutral: 'text-neutral bg-neutral/20',
  accent: 'text-accent bg-accent/20',
  bullish: 'text-bullish bg-bullish/20',
  warning: 'text-warning bg-warning/20',
  'text-secondary': 'text-text-secondary bg-text-secondary/20',
}

interface FactorCardProps {
  factor: Factor
  onClick?: () => void
}

export function FactorCard({ factor, onClick }: FactorCardProps) {
  const Icon = iconMap[factor.type] || iconMap.trend
  const colorClass = factor.color ? colorMap[factor.color] : colorMap.primary
  const isPositive = factor.value >= 0

  return (
    <div
      onClick={onClick}
      className={clsx(
        'bg-surface/50 border border-border rounded-xl p-4 cursor-pointer transition-all duration-200',
        'hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 hover:-translate-y-0.5'
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', colorClass)}>
            <Icon className="w-4 h-4" />
          </div>
          <span className="font-heading text-sm text-text-primary">{factor.name}</span>
        </div>
        <span className="text-xs text-text-secondary">{(factor.weight * 100).toFixed(0)}%</span>
      </div>

      <div className="flex items-end gap-3">
        <span
          className={clsx(
            'text-3xl font-heading font-bold',
            isPositive ? 'text-bullish' : 'text-bearish'
          )}
        >
          {isPositive ? '+' : ''}
          {factor.value.toFixed(2)}
        </span>
        <span className="text-sm text-text-secondary mb-1">conf: {(factor.confidence * 100).toFixed(0)}%</span>
      </div>

      <div className="mt-3 h-10 bg-background/50 rounded flex items-center px-2">
        <MiniSparkline positive={isPositive} />
      </div>
    </div>
  )
}

function MiniSparkline({ positive }: { positive: boolean }) {
  const points = positive
    ? '0,15 15,14 30,12 45,10 60,8 75,9 90,5 100,5'
    : '0,8 15,10 30,12 45,11 60,13 75,14 90,15 100,15'

  return (
    <svg className="w-full h-full" viewBox="0 0 100 20" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={positive ? '#10B981' : '#EF4444'}
        strokeWidth="1.5"
        points={points}
      />
    </svg>
  )
}
