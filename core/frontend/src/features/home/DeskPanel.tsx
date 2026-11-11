import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'

type DeskCard = { key: string; to: string; value: number; tone: 'neutral' | 'info' | 'warning' | 'danger' }
type Desk = { mine: DeskCard[]; all: DeskCard[] }

const TONE = { neutral: 'text-text', info: 'text-primary', warning: 'text-warning', danger: 'text-danger' } as const

/** Resepshin paneli: xodimning o'z ishlari va (ruxsati bo'lsa) butun kompaniya bo'yicha umumiy nazorat. */
export function DeskPanel() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['home', 'desk'], queryFn: () => api<Desk>('/api/v1/home/desk'), refetchInterval: 60_000 })
  if (q.isLoading) return <Skeleton className="h-28" />
  if (!q.data || (!q.data.mine.length && !q.data.all.length)) return null
  const block = (title: string, cards: DeskCard[]) =>
    cards.length > 0 && (
      <section className="flex flex-col gap-2.5">
        <h2 className="text-[13px] font-semibold uppercase tracking-wider text-muted">{title}</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {cards.map((c) => (
            <Link key={c.key} to={c.to}>
              <Card className="h-full p-4 transition-all duration-150 hover:-translate-y-px hover:shadow-pop">
                <div className="text-xs text-muted">{t(`desk.${c.key}`)}</div>
                <div className={clsx('mt-2 font-mono text-[26px] font-medium leading-none tabular-nums', c.value ? TONE[c.tone] : 'text-muted')}>{c.value}</div>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    )
  return (
    <div className="flex flex-col gap-5">
      {block(t('desk.mine'), q.data.mine)}
      {block(t('desk.all'), q.data.all)}
    </div>
  )
}
