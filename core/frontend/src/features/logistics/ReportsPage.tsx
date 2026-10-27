import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { addDays, todayLocal } from '../attendance/api'
import { Kpi } from '../tasks/AnalyticsPage'
import { LogisticsTabs } from './LogisticsTabs'
import { num, stageTone, type FuelReport } from './api'

type Tab = 'fuel' | 'trips' | 'days' | 'expiry'
interface TripsRep {
  items: { driver: { id: number; name: string | null }; completed: number; cancelled: number; open: number; km: number }[]
}
interface DaysRep {
  items: { driver: { id: number; name: string | null }; date: string; first: string; last: string; hours: number; points: number; trips: number; km: number }[]
}
interface ExpiryRep {
  items: { type: string; kind: string; subject: string | null; link: string; expires_at: string; days_left: number }[]
}

/** /logistics/reports: yoqilg'i hisobi, reyslar, GPS ish kuni va muddatlar. */
export function ReportsPage() {
  const { t, i18n } = useTranslation()
  const [tab, setTab] = useState<Tab>('fuel')
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -29), end: today })
  const qs = `start=${range.start}&end=${range.end}`
  const valid = range.end >= range.start
  const fuel = useQuery({ queryKey: ['logistics', 'rep-fuel', qs], queryFn: () => api<FuelReport>(`/api/v1/logistics/reports/fuel?${qs}`), enabled: tab === 'fuel' && valid })
  const trips = useQuery({ queryKey: ['logistics', 'rep-trips', qs], queryFn: () => api<TripsRep>(`/api/v1/logistics/reports/trips?${qs}`), enabled: tab === 'trips' && valid })
  const days = useQuery({ queryKey: ['logistics', 'rep-days', qs], queryFn: () => api<DaysRep>(`/api/v1/logistics/reports/driver-days?${qs}`), enabled: tab === 'days' && valid })
  const expiry = useQuery({ queryKey: ['logistics', 'rep-expiry'], queryFn: () => api<ExpiryRep>('/api/v1/logistics/reports/expiry?days=60'), enabled: tab === 'expiry' })
  const th = 'px-5 py-2.5 font-medium'
  const td = 'px-5 py-2.5'
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={t('logistics.title')} subtitle={t('logistics.subtitle')} />
      <LogisticsTabs />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex flex-wrap rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
          {(['fuel', 'trips', 'days', 'expiry'] as const).map((k) => (
            <button key={k} onClick={() => setTab(k)} aria-pressed={tab === k} className={tab === k ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`logistics.reports.${k}`)}
            </button>
          ))}
        </div>
        {tab !== 'expiry' && (
          <>
            <Input type="date" className="w-40" value={range.start} max={range.end} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} aria-label={t('schedule.apply.from')} />
            <span className="text-muted">–</span>
            <Input type="date" className="w-40" value={range.end} min={range.start} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} aria-label={t('schedule.apply.to')} />
          </>
        )}
        {tab === 'fuel' && (
          <a href={`/api/v1/logistics/reports/fuel/export?${qs}`} download className="ml-auto">
            <Button variant="outline">
              <Download className="size-4" />
              Excel
            </Button>
          </a>
        )}
      </Card>

      {tab === 'fuel' &&
        (!fuel.data ? (
          <Skeleton className="h-48" />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Kpi label={t('logistics.reports.km')} value={num(fuel.data.totals.km, 1)} hint={t('logistics.reports.tripsN', { count: fuel.data.totals.trips })} />
              <Kpi tint="lilac" label={t('logistics.reports.norm')} value={`${num(fuel.data.totals.norm_liters, 1)} l`} />
              <Kpi tint="sand" label={t('logistics.reports.filled')} value={`${num(fuel.data.totals.liters, 1)} l`} hint={`${num(fuel.data.totals.cost)} so'm`} />
              <Kpi tint={fuel.data.totals.variance > 0 ? 'rose' : 'mint'} label={t('logistics.reports.variance')} value={`${fuel.data.totals.variance > 0 ? '+' : ''}${num(fuel.data.totals.variance, 1)} l`} />
            </div>
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border text-xs text-muted">
                    <tr>
                      <th className={th}>{t('logistics.trip.vehicle')}</th>
                      <th className={th + ' text-right'}>km</th>
                      <th className={th + ' text-right'}>{t('logistics.reports.norm')}</th>
                      <th className={th + ' text-right'}>{t('logistics.reports.filled')}</th>
                      <th className={th + ' text-right'}>{t('logistics.reports.variance')}</th>
                      <th className={th + ' hidden text-right md:table-cell'}>l/100 km</th>
                      <th className={th + ' hidden text-right md:table-cell'}>{t('logistics.fuel.total')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border tabular-nums">
                    {fuel.data.items.map((r) => (
                      <tr key={r.vehicle.id}>
                        <td className={td + ' font-medium'}>
                          {r.vehicle.plate}
                          <div className="text-xs font-normal text-muted">
                            {r.vehicle.name} · {r.norm_per_100} l/100
                          </div>
                        </td>
                        <td className={td + ' text-right'}>{num(r.km, 1)}</td>
                        <td className={td + ' text-right'}>{num(r.norm_liters, 1)}</td>
                        <td className={td + ' text-right'}>{num(r.liters, 1)}</td>
                        <td className={td + ' text-right font-medium ' + (r.variance > 0 ? 'text-danger' : 'text-success')}>
                          {r.variance > 0 ? '+' : ''}
                          {num(r.variance, 1)}
                        </td>
                        <td className={td + ' hidden text-right md:table-cell'}>{r.actual_per_100 ?? '—'}</td>
                        <td className={td + ' hidden text-right md:table-cell'}>{num(r.cost)}</td>
                      </tr>
                    ))}
                    {fuel.data.items.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-5 py-10 text-center text-muted">
                          {t('common.empty')}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        ))}

      {tab === 'trips' &&
        (!trips.data ? (
          <Skeleton className="h-48" />
        ) : (
          <Card className="overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className={th}>{t('logistics.trip.driver')}</th>
                  <th className={th + ' text-right'}>{t('logistics.trip.status.completed')}</th>
                  <th className={th + ' text-right'}>{t('logistics.trip.status.cancelled')}</th>
                  <th className={th + ' text-right'}>km</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {trips.data.items.map((r) => (
                  <tr key={r.driver.id}>
                    <td className={td + ' font-medium'}>{r.driver.name}</td>
                    <td className={td + ' text-right'}>{r.completed}</td>
                    <td className={td + ' text-right'}>{r.cancelled}</td>
                    <td className={td + ' text-right'}>{num(r.km, 1)}</td>
                  </tr>
                ))}
                {trips.data.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>
        ))}

      {tab === 'days' &&
        (!days.data ? (
          <Skeleton className="h-48" />
        ) : (
          <Card className="overflow-hidden">
            <p className="px-5 pt-4 text-xs text-muted">{t('logistics.reports.daysHint')}</p>
            <div className="overflow-x-auto">
              <table className="mt-2 w-full text-left text-sm">
                <thead className="border-y border-border text-xs text-muted">
                  <tr>
                    <th className={th}>{t('logistics.trip.driver')}</th>
                    <th className={th}>{t('logistics.reports.date')}</th>
                    <th className={th}>{t('logistics.reports.first')}</th>
                    <th className={th}>{t('logistics.reports.last')}</th>
                    <th className={th + ' text-right'}>{t('logistics.reports.hours')}</th>
                    <th className={th + ' text-right'}>km</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {days.data.items.map((r) => (
                    <tr key={`${r.driver.id}-${r.date}`}>
                      <td className={td + ' font-medium'}>{r.driver.name}</td>
                      <td className={td}>{formatDate(r.date, i18n.language)}</td>
                      <td className={td + ' text-muted'}>{formatDateTime(r.first, i18n.language).slice(-5)}</td>
                      <td className={td + ' text-muted'}>{formatDateTime(r.last, i18n.language).slice(-5)}</td>
                      <td className={td + ' text-right'}>{r.hours}</td>
                      <td className={td + ' text-right'}>{num(r.km, 1)}</td>
                    </tr>
                  ))}
                  {days.data.items.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-5 py-10 text-center text-muted">
                        {t('common.empty')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        ))}

      {tab === 'expiry' &&
        (!expiry.data ? (
          <Skeleton className="h-48" />
        ) : (
          <Card className="divide-y divide-border p-0">
            {expiry.data.items.map((r, i) => (
              <Link key={i} to={r.link} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5 text-sm hover:bg-surface-2">
                <span>
                  <span className="font-medium">{r.subject}</span> <span className="text-muted">{r.type === 'license' ? t('logistics.driver.license') : t(`logistics.docKind.${r.kind}`)}</span>
                </span>
                <span className="flex items-center gap-2 tabular-nums">
                  {formatDate(r.expires_at, i18n.language)}
                  <Badge tone={stageTone(r.days_left < 0 ? 3 : r.days_left <= 7 ? 2 : 1)}>{r.days_left < 0 ? t('logistics.doc.expired', { days: -r.days_left }) : t('logistics.doc.daysLeft', { days: r.days_left })}</Badge>
                </span>
              </Link>
            ))}
            {expiry.data.items.length === 0 && <p className="px-5 py-10 text-center text-sm text-muted">{t('logistics.reports.noExpiry')}</p>}
          </Card>
        ))}
    </div>
  )
}
