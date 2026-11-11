import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { addDays, mondayOf, todayLocal } from '../attendance/api'
import { monthRange, shiftMonth } from '../schedule/api'
import { Dist, Kpi } from '../tasks/AnalyticsPage'
import { PRIORITIES, STATUSES, type Analytics } from './api'

type Preset = 'week' | 'month' | 'lastMonth' | 'custom'

function presetRange(p: Exclude<Preset, 'custom'>) {
  const today = todayLocal()
  if (p === 'week') return { start: mondayOf(today), end: addDays(mondayOf(today), 6) }
  if (p === 'month') return monthRange(today.slice(0, 7))
  return monthRange(shiftMonth(today.slice(0, 7), -1))
}

type Row = Analytics['by_category'][number]

/** /helpdesk/analytics: ticket oqimi, SLA, javob va hal qilish tezligi. */
export function AnalyticsPage() {
  const { t } = useTranslation()
  const [preset, setPreset] = useState<Preset>('month')
  const [custom, setCustom] = useState(presetRange('month'))
  const range = preset === 'custom' ? custom : presetRange(preset)
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 <= 92
  const params = new URLSearchParams({ start: range.start, end: range.end })
  const q = useQuery({ queryKey: ['helpdesk', 'analytics', params.toString()], queryFn: () => api<Analytics>(`/api/v1/helpdesk/analytics?${params}`), enabled: valid, placeholderData: (p) => p })
  const d = q.data
  const k = d?.kpis
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`)
  const hours = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v} ${t('tasks.analytics.hours')}`)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('helpdesk.analytics.title')} subtitle={t('helpdesk.analytics.subtitle')} backTo="/helpdesk" backLabel={t('helpdesk.title')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex flex-wrap rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group" aria-label={t('attendance.dash.period')}>
          {(['week', 'month', 'lastMonth', 'custom'] as const).map((p) => (
            <button key={p} onClick={() => setPreset(p)} aria-pressed={preset === p} className={preset === p ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`attendance.dash.presets.${p}`)}
            </button>
          ))}
        </div>
        {preset === 'custom' && (
          <div className="flex items-center gap-2">
            <Input type="date" value={custom.start} onChange={(e) => e.target.value && setCustom({ ...custom, start: e.target.value })} className="w-40" aria-label={t('schedule.apply.from')} />
            <span className="text-muted">–</span>
            <Input type="date" value={custom.end} min={custom.start} onChange={(e) => e.target.value && setCustom({ ...custom, end: e.target.value })} className="w-40" aria-label={t('schedule.apply.to')} />
          </div>
        )}
      </Card>
      {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid')}</p>}
      {!d || !k ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi tint="lilac" label={t('tasks.analytics.created')} value={String(k.created)} />
            <Kpi tint="mint" label={t('helpdesk.analytics.resolved')} value={String(k.resolved)} />
            <Kpi label={t('tasks.analytics.open')} value={String(k.open)} hint={t('helpdesk.analytics.unassignedHint', { count: k.unassigned })} />
            <Kpi tint="rose" label={t('tasks.analytics.overdue')} value={String(k.overdue)} />
            <Kpi label={t('helpdesk.analytics.slaRate')} value={pct(k.sla_rate)} hint={t('helpdesk.analytics.slaHint')} />
            <Kpi label={t('helpdesk.analytics.reopenRate')} value={pct(k.reopen_rate)} />
            <Kpi label={t('helpdesk.analytics.avgResponse')} value={k.avg_response_minutes === null ? '—' : `${k.avg_response_minutes} ${t('helpdesk.analytics.min')}`} />
            <Kpi label={t('helpdesk.analytics.avgResolution')} value={hours(k.avg_resolution_hours)} hint={k.avg_rating === null ? undefined : `${t('helpdesk.rating')}: ${k.avg_rating} / 5`} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Dist title={t('tasks.analytics.byStatus')} rows={STATUSES.map((s) => [t(`helpdesk.status.${s}`), d.by_status[s]])} />
            <Dist title={t('helpdesk.analytics.byPriority')} rows={PRIORITIES.map((p) => [t(`tasks.priority.${p}`), d.by_priority[p]])} />
          </div>
          <Breakdown title={t('helpdesk.analytics.byCategory')} first={t('helpdesk.category')} rows={d.by_category} hours={hours} none={t('helpdesk.noCategory')} />
          <Breakdown title={t('helpdesk.analytics.byExecutor')} first={t('helpdesk.assignee')} rows={d.by_executor} hours={hours} none="—" />
        </>
      )}
    </div>
  )
}

function Breakdown({ title, first, rows, hours, none }: { title: string; first: string; rows: Row[]; hours: (v: number | null) => string; none: string }) {
  const { t } = useTranslation()
  return (
    <Card className="overflow-hidden">
      <h2 className="px-5 pt-5 text-[13px] text-muted">{title}</h2>
      <div className="overflow-x-auto">
        <table className="mt-3 w-full text-left text-sm">
          <thead className="border-y border-border text-xs text-muted">
            <tr>
              <th className="px-5 py-2.5 font-medium">{first}</th>
              <th className="px-5 py-2.5 text-right font-medium">{t('tasks.analytics.created')}</th>
              <th className="px-5 py-2.5 text-right font-medium">{t('helpdesk.analytics.resolved')}</th>
              <th className="px-5 py-2.5 text-right font-medium">{t('tasks.analytics.open')}</th>
              <th className="px-5 py-2.5 text-right font-medium">{t('tasks.analytics.overdue')}</th>
              <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('tasks.analytics.avg')}</th>
              <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('helpdesk.rating')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border tabular-nums">
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="px-5 py-2.5 font-medium">{r.name ?? none}</td>
                <td className="px-5 py-2.5 text-right">{r.created}</td>
                <td className="px-5 py-2.5 text-right">{r.done}</td>
                <td className="px-5 py-2.5 text-right">{r.open}</td>
                <td className={'px-5 py-2.5 text-right ' + (r.overdue ? 'font-semibold text-danger' : '')}>{r.overdue}</td>
                <td className="hidden px-5 py-2.5 text-right text-muted sm:table-cell">{hours(r.avg_hours)}</td>
                <td className="hidden px-5 py-2.5 text-right text-muted sm:table-cell">{r.rating ?? '—'}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-muted">
                  {t('common.empty')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
