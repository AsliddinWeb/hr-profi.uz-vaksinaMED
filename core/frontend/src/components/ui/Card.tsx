import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

/** `tint` eski API (gradient kartalar) uchun saqlangan: endi hamma karta tekis oq sirt. */
export type Tint = 'rose' | 'lilac' | 'mint' | 'sand'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  tint?: Tint
}

export function Card({ tint: _tint, className, ...rest }: CardProps) {
  return <div className={cn('rounded-card bg-surface shadow-card', className)} {...rest} />
}
