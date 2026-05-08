import clsx from 'clsx'

type BadgeVariant = 'success' | 'danger' | 'warning' | 'info' | 'neutral' | 'default'

interface StatusBadgeProps {
  variant: BadgeVariant
  children: React.ReactNode
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  success: 'bg-bullish/20 text-bullish border-bullish/30',
  danger: 'bg-bearish/20 text-bearish border-bearish/30',
  warning: 'bg-warning/20 text-warning border-warning/30',
  info: 'bg-neutral/20 text-neutral border-neutral/30',
  neutral: 'bg-border/50 text-text-secondary',
  default: 'bg-surface border-border text-text-secondary',
}

export function StatusBadge({ variant, children, className }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border',
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  )
}
