import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'violet'
}

const tones = {
  neutral: 'bg-surface-3 text-muted',
  success: 'bg-success/12 text-success',
  warning: 'bg-warning/14 text-warning',
  danger: 'bg-danger/12 text-danger',
  info: 'bg-info/12 text-info',
  violet: 'bg-(--violet)/12 text-(--violet)',
}

export function Badge({ tone = 'neutral', className, ...rest }: BadgeProps) {
  return <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium', tones[tone], className)} {...rest} />
}
