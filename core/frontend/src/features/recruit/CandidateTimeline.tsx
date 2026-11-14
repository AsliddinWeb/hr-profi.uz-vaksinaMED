import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { fmtMoney } from '../../lib/money'

type Item = { kind: string; at: string; action: string; actor: string | null; data: Record<string, unknown> }
type Timeline = { items: Item[]; total: number; counts: Record<string, number> }

const KINDS = ['application', 'call', 'interview', 'stage', 'background', 'offer', 'hire', 'candidate'] as const
const DOT: Record<string, string> = {
  candidate: 'bg-slate-400',
  application: 'bg-emerald-500',
  call: 'bg-sky-500',
  interview: 'bg-violet-500',
  stage: 'bg-teal-500',
  background: 'bg-amber-500',
  offer: 'bg-fuchsia-500',
  hire: 'bg-success',
}
const BAD = new Set(['no_show', 'offer_declined', 'rejected'])

/** Nomzod profili: barcha hodisalar (arizalar, qo'ng'iroqlar, intervyu, keldi/kelmadi, tekshiruv, offer, ishga qabul) bitta lentada. */
export function CandidateTimeline({ id }: { id: number }) {
  const { t, i18n } = useTranslation()
  const [kind, setKind] = useState('')
  const q = useQuery({ queryKey: ['recruit', 'candidate', id, 'timeline'], queryFn: () => api<Timeline>(`/api/v1/recruit/candidates/${id}/timeline`) })
  const items = (q.data?.items ?? []).filter((x) => !kind || x.kind === kind)
  const counts = q.data?.counts ?? {}
  const st = (s: unknown) => (typeof s === 'string' ? t(`recruit.stage.${s}`) : '—')

  const detail = (x: Item) => {
    const d = x.data
    const parts: string[] = []
    if (typeof d.vacancy === 'string') parts.push(d.vacancy)
    if (d.from_stage || d.to_stage) parts.push(`${st(d.from_stage)} → ${st(d.to_stage)}`)
    if (typeof d.outcome === 'string') parts.push(t(`ana.call.${d.outcome}`, { defaultValue: d.outcome }))
    if (typeof d.callback_date === 'string') parts.push(`${t('ctl.callback')}: ${d.callback_date}`)
    if (typeof d.salary === 'number') parts.push(fmtMoney(d.salary))
    if (typeof d.decision === 'string') parts.push(d.decision)
    if (typeof d.place === 'string' && d.place) parts.push(d.place)
    if (typeof d.hard === 'number' || typeof d.soft === 'number') parts.push(`Hard ${d.hard ?? '—'} · Soft ${d.soft ?? '—'}`)
    for (const k of ['note', 'reason', 'reply'] as const) if (typeof d[k] === 'string' && d[k]) parts.push(String(d[k]))
    return parts.join(' · ')
  }

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div>
        <h2 className="font-semibold">{t('ctl.title')}</h2>
        <p className="text-xs text-muted">{t('ctl.hint')}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {['', ...KINDS].map((k) => (
          <button
            key={k || 'all'}
            type="button"
            onClick={() => setKind(k)}
            className={clsx('rounded-full border px-3 py-1 text-xs', kind === k ? 'border-primary bg-primary text-white' : 'border-border hover:bg-surface-2')}
          >
            {k ? t(`ctl.kind.${k}`) : t('vhist.all')} <span className="opacity-70">{k ? (counts[k] ?? 0) : (q.data?.total ?? 0)}</span>
          </button>
        ))}
      </div>
      {!q.data ? (
        <Skeleton className="h-32" />
      ) : items.length === 0 ? (
        <EmptyState title={t('ana.empty')} />
      ) : (
        <ol className="relative flex flex-col gap-3 border-l border-border pl-5">
          {items.map((x, i) => {
            const aid = typeof x.data.application_id === 'number' ? x.data.application_id : null
            const title = t(`ctl.a.${x.action}`, { defaultValue: t(`recruit.event.${x.action}`, { defaultValue: x.action, from: st(x.data.from_stage), to: st(x.data.to_stage) }) })
            return (
              <li key={`${x.kind}-${x.at}-${i}`} className="relative text-sm">
                <span className={clsx('absolute -left-[26px] top-1.5 size-2.5 rounded-full ring-4 ring-surface', BAD.has(x.action) ? 'bg-danger' : (DOT[x.kind] ?? 'bg-muted'))} />
                <div className="flex flex-wrap items-baseline gap-x-2">
                  {aid ? (
                    <Link to={`/recruit/applications/${aid}`} className={clsx('font-medium hover:underline', BAD.has(x.action) && 'text-danger')}>
                      {title}
                    </Link>
                  ) : (
                    <span className="font-medium">{title}</span>
                  )}
                  <span className="text-xs text-muted">
                    {formatDateTime(x.at, i18n.language)}
                    {x.actor ? ` · ${x.actor}` : ''}
                  </span>
                </div>
                {detail(x) && <div className="text-xs text-muted">{detail(x)}</div>}
              </li>
            )
          })}
        </ol>
      )}
    </Card>
  )
}
