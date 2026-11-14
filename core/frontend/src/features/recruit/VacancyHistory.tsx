import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

type Item = { kind: string; at: string; action: string; actor: string | null; data: Record<string, unknown> }
type History = { items: Item[]; total: number; counts: Record<string, number> }

const KINDS = ['request', 'announcement', 'vacancy', 'channel', 'link', 'application', 'stage', 'call'] as const
const DOT: Record<string, string> = {
  request: 'bg-violet-500',
  announcement: 'bg-fuchsia-500',
  vacancy: 'bg-primary',
  channel: 'bg-amber-500',
  link: 'bg-sky-500',
  application: 'bg-emerald-500',
  stage: 'bg-teal-500',
  call: 'bg-slate-400',
}

/** Vakansiyaning o'zgarmas tarixi (TZ): zayavka, e'lon, tahrirlar (eski → yangi), kanallar, havolalar, arizalar, bosqichlar, qo'ng'iroqlar. */
export function VacancyHistory({ id }: { id: number }) {
  const { t, i18n } = useTranslation()
  const [kind, setKind] = useState('')
  const q = useQuery({ queryKey: ['recruit', 'vacancy', id, 'history', kind], queryFn: () => api<History>(`/api/v1/recruit/vacancies/${id}/history${kind ? `?kind=${kind}` : ''}`), placeholderData: (p) => p })
  const all = useQuery({ queryKey: ['recruit', 'vacancy', id, 'history', ''], queryFn: () => api<History>(`/api/v1/recruit/vacancies/${id}/history`) })
  const counts = all.data?.counts ?? {}
  const total = all.data?.total ?? 0

  const detail = (x: Item) => {
    const d = x.data
    const parts: string[] = []
    if (typeof d.candidate === 'string') parts.push(d.candidate)
    if (d.from_stage || d.to_stage) parts.push(`${d.from_stage ? t(`recruit.stage.${d.from_stage}`) : '—'} → ${d.to_stage ? t(`recruit.stage.${d.to_stage}`) : '—'}`)
    if (typeof d.status === 'string') parts.push(t(`recruit.vacancy.status.${d.status}`))
    if (typeof d.channel === 'string') parts.push(t(`ana.src.${d.channel}`, { defaultValue: d.channel }))
    if (typeof d.outcome === 'string') parts.push(t(`ana.call.${d.outcome}`, { defaultValue: d.outcome }))
    if (typeof d.title === 'string' && !d.changes) parts.push(d.title)
    if (typeof d.note === 'string' && d.note) parts.push(d.note)
    if (typeof d.reason === 'string' && d.reason) parts.push(d.reason)
    return parts.join(' · ')
  }

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium">{t('vhist.title')}</div>
          <div className="text-xs text-muted">{t('vhist.hint')}</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {['', ...KINDS].map((k) => (
          <button
            key={k || 'all'}
            type="button"
            onClick={() => setKind(k)}
            className={clsx('rounded-full border px-3 py-1 text-xs', kind === k ? 'border-primary bg-primary text-white' : 'border-border hover:bg-surface-2')}
          >
            {k ? t(`vhist.kind.${k}`) : t('vhist.all')} <span className="opacity-70">{k ? (counts[k] ?? 0) : total}</span>
          </button>
        ))}
      </div>
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : q.data.items.length === 0 ? (
        <EmptyState title={t('ana.empty')} />
      ) : (
        <ol className="relative flex flex-col gap-3 border-l border-border pl-5">
          {q.data.items.map((x, i) => {
            const changes = (x.data.changes ?? null) as Record<string, [string | null, string | null]> | null
            return (
              <li key={`${x.kind}-${x.at}-${i}`} className="relative text-sm">
                <span className={clsx('absolute -left-[26px] top-1.5 size-2.5 rounded-full ring-4 ring-surface', DOT[x.kind] ?? 'bg-muted')} />
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-medium">{t(`vhist.a.${x.action}`, { defaultValue: t(`recruit.event.${x.action}`, { defaultValue: x.action, from: x.data.from_stage ? t(`recruit.stage.${x.data.from_stage}`) : '—', to: x.data.to_stage ? t(`recruit.stage.${x.data.to_stage}`) : '—' }) })}</span>
                  <span className="text-xs text-muted">
                    {formatDateTime(x.at, i18n.language)}
                    {x.actor ? ` · ${x.actor}` : ''}
                  </span>
                </div>
                {detail(x) && <div className="text-xs text-muted">{detail(x)}</div>}
                {changes && Object.keys(changes).length > 0 && (
                  <ul className="mt-1 flex flex-col gap-0.5 rounded-lg bg-surface-2 p-2 text-xs">
                    {Object.entries(changes).map(([f, [a, b]]) => (
                      <li key={f}>
                        <span className="text-muted">{t(`vhist.f.${f}`, { defaultValue: f })}:</span> <s className="text-danger/80">{a ?? '—'}</s> → <b>{b ?? '—'}</b>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            )
          })}
        </ol>
      )}
      {q.data && q.data.total > q.data.items.length && <div className="text-xs text-muted">{t('vhist.more', { n: q.data.total - q.data.items.length })}</div>}
    </Card>
  )
}
