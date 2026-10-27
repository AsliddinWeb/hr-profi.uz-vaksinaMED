import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

/** Ma'lumot juftligi: kichik kulrang nom + qiymat. Bo'sh qiymat "—" bo'ladi. */
export function Info({ label, children, className }: { label: string; children?: ReactNode; className?: string }) {
  return (
    <div className={cn('min-w-0', className)}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 break-words text-[13px] font-medium">{children === null || children === undefined || children === '' || children === false ? <span className="font-normal text-muted">—</span> : children}</dd>
    </div>
  )
}

/** Ma'lumot juftliklari to'ri (responsive ustunlar). */
export function InfoGrid({ children, cols = 3, className }: { children: ReactNode; cols?: 2 | 3 | 4; className?: string }) {
  return <dl className={cn('grid gap-x-6 gap-y-4', cols === 2 && 'sm:grid-cols-2', cols === 3 && 'sm:grid-cols-3', cols === 4 && 'grid-cols-2 lg:grid-cols-4', className)}>{children}</dl>
}
