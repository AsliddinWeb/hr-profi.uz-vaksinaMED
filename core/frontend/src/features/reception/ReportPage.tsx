import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { BarChart } from '../../components/charts'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { addDays, mondayOf, todayLocal } from '../attendance/api'
import { monthRange, shiftMonth } from '../schedule/api'
import { Dist, Kpi } from '../tasks/AnalyticsPage'
import { PURPOSES, type Report } from './api'

type Preset = 'week' | 'month' | 'lastMonth' | 'custom'

function presetRange(p: Exclude<Preset, 'custom'>) {
  const today = todayLocal()
  if (p === 'week') return { start: mondayOf(today), end: addDays(mondayOf(today), 6) }
  if (p === 'month') return monthRange(today.slice(0, 7))
  return monthRange(shiftMonth(today.slice(0, 7), -1))
}

/** /reception/report: mehmonlar oqimi (kunlar bo'yicha), maqsadlar, eng ko'p mehmon qabul qilganlar. */
export function ReportPage() {
  const { t } = useTranslation()
  const [preset, setPreset] = useState<Preset>('month')
  const [custom, setCustom] = useState(presetRange('month'))
  const range = preset === 'custom' ? custom : presetRange(preset)
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 <= 92
  const params = new URLSearchParams({ start: range.start, end: range.end })
  const q = useQuery({ queryKey: ['reception', 'report', params.toString()], queryFn: () => api<Report>(`/api/v1/reception/report?${params}`), enabled: valid, placeholderData: (p) => p })
  const d = q.data

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('reception.report.title')} subtitle={t('reception.report.subtitle')} backTo="/reception" backLabel={t('reception.title')} />
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
      {!d ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi tint="lilac" label={t('reception.report.total')} value={String(d.total)} />
            <Kpi tint="mint" label={t('reception.sum.inside')} value={String(d.inside_now)} />
            <Kpi tint="rose" label={t('reception.report.noShow')} value={String(d.no_show)} />
            <Kpi label={t('reception.report.avg')} value={d.avg_minutes === null ? '—' : `${d.avg_minutes} ${t('helpdesk.analytics.min')}`} />
          </div>
          <Card className="p-5">
            <h2 className="text-[13px] text-muted">{t('reception.report.byDay')}</h2>
            <BarChart label={t('reception.report.byDay')} labels={d.trend.map((x) => x.date)} values={d.trend.map((x) => x.count)} name={t('reception.report.total')} />
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Dist title={t('reception.report.byPurpose')} rows={PURPOSES.map((p) => [t(`reception.purpose.${p}`), d.by_purpose[p]])} />
            <Dist title={t('reception.report.topHosts')} rows={d.top_hosts.map((h) => [h.name ?? '—', h.count])} />
          </div>
        </>
      )}
    </div>
  )
}
