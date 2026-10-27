import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { addDays, todayLocal } from '../attendance/api'
import { Kpi } from '../tasks/AnalyticsPage'
import { hm, type Control, type WhRow } from './api'

/** /warehouse/:id/control: nazorat hisoboti: xodimlar soati, minimumdan kam kunlar va kunlik yetishmovchilik. */
export function ControlPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -13), end: today })
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 + 1 <= 42
  const w = useQuery({ queryKey: ['warehouse', 'one', id], queryFn: () => api<WhRow>(`/api/v1/warehouse/${id}`), retry: false })
  const q = useQuery({ queryKey: ['warehouse', 'control', id, range.start, range.end], queryFn: () => api<Control>(`/api/v1/warehouse/${id}/control?start=${range.start}&end=${range.end}`), enabled: valid, placeholderData: (p) => p })
  if (w.error instanceof ApiError && w.error.status === 404) return <NotFound />
  const d = q.data
  const th = 'px-5 py-2.5 font-medium'
  const td = 'px-5 py-2.5'
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('warehouse.controlReport')} subtitle={w.data?.name} backTo={`/warehouse/${id}`} backLabel={w.data?.name ?? t('warehouse.title')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Input type="date" className="w-40" value={range.start} max={range.end} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" className="w-40" value={range.end} min={range.start} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} aria-label={t('schedule.apply.to')} />
        <span className="text-xs text-muted">{t('warehouse.max42')}</span>
      </Card>
      {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid')}</p>}
      {!d ? (
        <Skeleton className="h-72" />
      ) : d.no_shift ? (
        <p className="text-center text-muted">{t('warehouse.noShift')}</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi tint="lilac" label={t('warehouse.report.hours')} value={String(d.totals.worked_hours)} />
            <Kpi tint="sand" label={t('warehouse.report.belowMin')} value={String(d.totals.below_min)} hint={t('warehouse.report.minHint', { hours: d.totals.min_work_minutes / 60 })} />
            <Kpi tint="rose" label={t('warehouse.report.absent')} value={String(d.totals.absent)} />
            <Kpi tint={d.totals.gap_days ? 'rose' : 'mint'} label={t('warehouse.report.gap')} value={hm(d.totals.gap_minutes)} hint={t('warehouse.report.gapDays', { count: d.totals.gap_days })} />
          </div>
          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 text-[15px] font-medium">{t('warehouse.report.byEmployee')}</h2>
            <div className="overflow-x-auto">
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-y border-border text-xs text-muted">
                  <tr>
                    <th className={th}>{t('payroll.line.employee')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.days')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.hours')}</th>
                    <th className={th + ' hidden text-right sm:table-cell'}>{t('warehouse.report.avg')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.belowMin')}</th>
                    <th className={th + ' hidden text-right md:table-cell'}>{t('warehouse.report.absent')}</th>
                    <th className={th + ' hidden text-right md:table-cell'}>{t('warehouse.report.noCheckout')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.employees.map((e) => (
                    <tr key={e.employee.id}>
                      <td className={td + ' font-medium'}>{e.employee.name}</td>
                      <td className={td + ' text-right'}>
                        {e.days}/{e.scheduled}
                      </td>
                      <td className={td + ' text-right'}>{hm(e.worked_minutes)}</td>
                      <td className={td + ' hidden text-right text-muted sm:table-cell'}>{hm(e.avg_minutes)}</td>
                      <td className={td + ' text-right ' + (e.below_min ? 'font-semibold text-warning' : 'text-muted')}>{e.below_min}</td>
                      <td className={td + ' hidden text-right md:table-cell ' + (e.absent ? 'font-semibold text-danger' : 'text-muted')}>{e.absent}</td>
                      <td className={td + ' hidden text-right md:table-cell ' + (e.no_checkout ? 'font-semibold text-warning' : 'text-muted')}>{e.no_checkout}</td>
                    </tr>
                  ))}
                  {d.employees.length === 0 && (
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
          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 text-[15px] font-medium">{t('warehouse.report.byDay')}</h2>
            <div className="overflow-x-auto">
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-y border-border text-xs text-muted">
                  <tr>
                    <th className={th}>{t('logistics.reports.date')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.staffIn')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.peak')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.lowest')}</th>
                    <th className={th + ' text-right'}>{t('warehouse.report.gap')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.days.map((x) => (
                    <tr key={x.date}>
                      <td className={td}>{formatDate(x.date, i18n.language)}</td>
                      <td className={td + ' text-right'}>{x.staff_in}</td>
                      <td className={td + ' text-right'}>{x.peak}</td>
                      <td className={td + ' text-right'}>{x.lowest}</td>
                      <td className={td + ' text-right ' + (x.gap_minutes ? 'font-semibold text-danger' : 'text-success')}>{x.gap_minutes ? hm(x.gap_minutes) : '0'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
