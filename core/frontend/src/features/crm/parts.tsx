import { Star } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { cn } from '../../lib/cn'
import { STATE_TONE, type ActState } from './api'

/** Faoliyat holati belgisi: «Kechikdi 7 kun» / «Bugun» / «Reja». */
export function ActivityChip({ a, className }: { a: ActState | null | undefined; className?: string }) {
  const { t } = useTranslation()
  if (!a) return <span className={cn('rounded-full bg-surface-3 px-2 py-0.5 text-[11px] text-muted', className)}>{t('crm.act.none')}</span>
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums', STATE_TONE[a.state], className)}>
      {a.state === 'overdue' ? t('crm.act.overdue', { n: a.days }) : a.state === 'today' ? t('crm.act.today') : t('crm.act.planned')}
    </span>
  )
}

/** Ustuvorlik: 0..3 yulduz. `onChange` berilsa bosib o'zgartiriladi. */
export function Stars({ value, onChange }: { value: number; onChange?: (v: number) => void }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center" aria-label={t('crm.field.priority')}>
      {[1, 2, 3].map((i) => {
        const on = i <= value
        const icon = <Star className={cn('size-3.5', on ? 'fill-(--amber) text-(--amber)' : 'text-border-strong')} />
        return onChange ? (
          <button key={i} type="button" onClick={() => onChange(value === i ? i - 1 : i)} className="p-0.5" aria-pressed={on} aria-label={`${i}`}>
            {icon}
          </button>
        ) : (
          <span key={i} className="p-px">
            {icon}
          </span>
        )
      })}
    </span>
  )
}
