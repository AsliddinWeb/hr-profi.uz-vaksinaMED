import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { addDays, todayLocal } from '../attendance/api'
import { Dist, Kpi } from '../tasks/AnalyticsPage'
import { RecruitTabs } from './RecruitTabs'
import { STAGES, type Summary } from './api'

/** /recruit/summary: voronka, manbalar va ishga olish tezligi. */
export function SummaryPage() {
  const { t } = useTranslation()
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -89), end: today })
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 <= 400
  const q = useQuery({ queryKey: ['recruit', 'summary', range.start, range.end], queryFn: () => api<Summary>(`/api/v1/recruit/summary?start=${range.start}&end=${range.end}`), enabled: valid, placeholderData: (p) => p })
  const d = q.data
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('recruit.title')} subtitle={t('recruit.subtitle')} />
      <RecruitTabs />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Input type="date" value={range.start} max={range.end} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} className="w-40" aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" value={range.end} min={range.start} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} className="w-40" aria-label={t('schedule.apply.to')} />
      </Card>
      {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid')}</p>}
      {!d ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Kpi tint="lilac" label={t('recruit.summary.applied')} value={String(d.applied)} />
            <Kpi tint="mint" label={t('recruit.summary.hired')} value={String(d.hired)} />
            <Kpi tint="rose" label={t('recruit.summary.rejected')} value={String(d.rejected)} />
            <Kpi label={t('recruit.summary.openVacancies')} value={String(d.open_vacancies)} />
            <Kpi label={t('recruit.summary.avgDays')} value={d.avg_days_to_hire === null ? '—' : `${d.avg_days_to_hire} ${t('recruit.summary.days')}`} />
          </div>
          <div className="grid gap-5 md:grid-cols-2">
            <Dist title={t('recruit.summary.funnel')} rows={STAGES.map((s) => [t(`recruit.stage.${s}`), d.stages[s]])} />
            <Dist title={t('recruit.summary.sources')} rows={d.sources.map((s) => [`${s.source ? t(`recruit.source.${s.source}`) : '—'} (${s.hired})`, s.applied])} />
          </div>
        </>
      )}
    </div>
  )
}
