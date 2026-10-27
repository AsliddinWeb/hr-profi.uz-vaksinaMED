import { useQuery } from '@tanstack/react-query'
import { AlarmClock, CalendarCheck2, FileDown, Hourglass, Percent, UserX } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { Delta, Gauge, KpiCard, LineChart, SegmentBar } from '../../components/charts'
import { pp, rel } from '../../lib/delta'
import { api } from '../../lib/api'
import { monthRange, shiftMonth } from '../schedule/api'
import { addDays, fmtMin, mondayOf, pct, STATUSES, todayLocal, type Dashboard, type GroupRow } from './api'
import { Filters } from './Filters'
import { emptyFilters, filterParams, type FilterState } from './filterState'

type Preset = 'today' | 'week' | 'month' | 'lastMonth' | 'custom'

function presetRange(p: Exclude<Preset, 'custom'>): { start: string; end: string } {
  const today = todayLocal()
  if (p === 'today') return { start: today, end: today }
  if (p === 'week') return { start: mondayOf(today), end: addDays(mondayOf(today), 6) }
  if (p === 'month') return monthRange(today.slice(0, 7))
  return monthRange(shiftMonth(today.slice(0, 7), -1))
}

/** /attendance/dashboard: davomat tahlili. Raqamlar tabel bilan bir manbadan hisoblanadi. */
export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const [preset, setPreset] = useState<Preset>('month')
  const [custom, setCustom] = useState(presetRange('month'))
  const [filters, setFilters] = useState<FilterState>(emptyFilters)
  const range = preset === 'custom' ? custom : presetRange(preset)
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 < 62

  const params = new URLSearchParams({ start: range.start, end: range.end })
  filterParams(filters, params)
  const q = useQuery({ queryKey: ['attendance', 'dashboard', params.toString()], queryFn: () => api<Dashboard>(`/api/v1/attendance/dashboard?${params}`), enabled: valid, placeholderData: (p) => p })
  const d = q.data
  const k = d?.kpis
  const pk = d?.previous?.kpis
  const past = (d?.trend ?? []).filter((x) => x.date <= todayLocal()) // kelajak kunlar grafikda 0 ga tushmasin

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('attendance.dash.title')}
        subtitle={t('attendance.dash.subtitle')}
        actions={
          <a href={`/api/v1/attendance/dashboard/pdf?${params}&lang=${i18n.language === 'ru' ? 'ru' : 'uz'}`} download aria-disabled={!valid}>
            <Button variant="outline" disabled={!valid}>
              <FileDown className="size-4" />
              {t('attendance.dash.pdf')}
            </Button>
          </a>
        }
      />

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex flex-wrap rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group" aria-label={t('attendance.dash.period')}>
          {(['today', 'week', 'month', 'lastMonth', 'custom'] as const).map((p) => (
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
        <Filters value={filters} onChange={setFilters} />
      </Card>
      {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid')}</p>}

      {!d || !k ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
            <KpiCard icon={Percent} color="var(--c-blue)" label={t('attendance.dash.rate')} value={pct(k.rate)} delta={<Delta value={pp(k.rate, pk?.rate)} suffix=" pp" />} hint={t('attendance.dash.rateHint')} />
            <KpiCard icon={CalendarCheck2} color="var(--c-green)" label={t('attendance.dash.attended')} value={String(k.attended)} delta={<Delta value={rel(k.attended, pk?.attended)} />} hint={t('attendance.dash.employeesN', { count: k.employees })} />
            <KpiCard icon={UserX} color="var(--c-rose)" label={t('attendance.dash.absent')} value={String(k.absent)} delta={<Delta value={rel(k.absent, pk?.absent)} goodWhen="down" />} />
            <KpiCard icon={AlarmClock} color="var(--c-amber)" label={t('attendance.dash.late')} value={String(k.late_count)} delta={<Delta value={rel(k.late_count, pk?.late_count)} goodWhen="down" />} hint={t('attendance.dash.lateMin', { m: k.late_minutes })} />
            <KpiCard icon={Percent} color="var(--c-teal)" label={t('attendance.dash.punctuality')} value={pct(k.punctuality)} delta={<Delta value={pp(k.punctuality, pk?.punctuality)} suffix=" pp" />} />
            <KpiCard icon={Hourglass} color="var(--c-violet)" label={t('attendance.dash.hours')} value={fmtMin(k.worked_minutes)} delta={<Delta value={rel(k.worked_minutes, pk?.worked_minutes)} />} hint={k.no_checkout ? t('attendance.dash.noCheckout', { count: k.no_checkout }) : undefined} />
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <Card className="p-5 lg:col-span-2">
              <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
                <div>
                  <h2 className="text-[13px] text-muted">{t('attendance.dash.trend')}</h2>
                  <p className="mt-1 text-xs text-muted">{t('attendance.dash.trendNote')}</p>
                </div>
                <div className="flex gap-8">
                  <BigNumber color="var(--chart-ok)" label={t('attendance.dash.attended')} value={k.attended} delta={<Delta value={rel(k.attended, pk?.attended)} />} />
                  <BigNumber color="var(--chart-muted)" label={t('attendance.dash.absent')} value={k.absent} delta={<Delta value={rel(k.absent, pk?.absent)} goodWhen="down" />} />
                </div>
              </div>
              <LineChart
                label={t('attendance.dash.trendLabel')}
                labels={past.map((x) => x.date)}
                series={[
                  { key: 'absent', label: t('attendance.dash.absentLabel'), color: 'var(--chart-muted)', muted: true, values: past.map((x) => x.absent) },
                  { key: 'attended', label: t('attendance.dash.attended'), color: 'var(--chart-ok)', values: past.map((x) => x.attended) },
                ]}
              />
            </Card>
            <Card className="flex flex-col p-5">
              <h2 className="text-[13px] text-muted">{t('attendance.dash.rate')}</h2>
              <div className="my-auto py-4">
                <Gauge value={k.rate} display={pct(k.rate)} caption={t('attendance.dash.rateHint')} label={t('attendance.dash.rate')} />
              </div>
              <div className="flex items-center justify-between border-t border-border pt-3 text-xs">
                <span className="text-muted">{t('attendance.dash.employees')}</span>
                <span className="font-mono tabular-nums">{k.employees}</span>
              </div>
            </Card>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Breakdown title={t('attendance.dash.byDept')} rows={d.by_department} none={t('attendance.dash.none')} />
            <Breakdown title={t('attendance.dash.byBranch')} rows={d.by_branch} none={t('attendance.dash.none')} />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <TopList title={t('attendance.dash.topLate')} empty={t('common.empty')}>
              {d.top_late.map((p) => (
                <Row key={p.employee.id} id={p.employee.id} name={p.employee.full_name} value={t('attendance.dash.lateRow', { n: p.late_count, m: p.late_minutes })} />
              ))}
            </TopList>
            <TopList title={t('attendance.dash.topAbsent')} empty={t('common.empty')}>
              {d.top_absent.map((p) => (
                <Row key={p.employee.id} id={p.employee.id} name={p.employee.full_name} value={t('attendance.dash.absentRow', { count: p.absent })} />
              ))}
            </TopList>
          </div>

          <Card className="p-5">
            <h2 className="text-[13px] text-muted">{t('attendance.dash.statuses')}</h2>
            <div className="mt-4">
              <SegmentBar items={STATUSES.filter((s) => d.statuses[s]).map((s) => ({ key: s, label: t(`attendance.status.${s}`), value: d.statuses[s] ?? 0, color: STATUS_COLOR[s] }))} />
            </div>
            <p className="mt-3 text-xs text-muted">{t('attendance.dash.note')}</p>
          </Card>
        </>
      )}
    </div>
  )
}

const STATUS_COLOR: Record<string, string> = {
  present: 'var(--chart-ok)', unscheduled: 'var(--chart-ok)', late: 'var(--chart-late)', early: 'var(--chart-late)', late_early: 'var(--chart-late)', incomplete: 'var(--chart-late)',
  absent: 'var(--chart-absent)', leave: 'var(--info)', working: 'var(--info)', holiday: 'var(--chart-muted)', off: 'var(--chart-muted)', no_checkout: 'var(--warning)',
  pending: 'var(--border-strong)', exempt: 'var(--border-strong)', no_shift: 'var(--border-strong)', future: 'var(--border-strong)',
}

function BigNumber({ label, value, color, delta }: { label: string; value: number; color: string; delta?: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-muted">
        <span className="size-1.5 rounded-full" style={{ background: color }} />
        {label}
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="font-mono text-[28px] font-medium leading-none tracking-tight tabular-nums">{value}</span>
        {delta}
      </div>
    </div>
  )
}

function Breakdown({ title, rows, none }: { title: string; rows: GroupRow[]; none: string }) {
  const { t } = useTranslation()
  return (
    <Card className="p-5">
      <h2 className="text-[13px] text-muted">{title}</h2>
      <ul className="mt-4 flex flex-col gap-3.5">
        {rows.map((r) => (
          <li key={r.id ?? 'none'}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-sm">
              <span className="min-w-0 font-medium">{r.name ?? none}</span>
              <span className="shrink-0 tabular-nums text-muted">
                {pct(r.rate)} · {t('attendance.dash.absentShort', { count: r.absent })} · {t('attendance.dash.lateShort', { count: r.late_count })}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3" role="img" aria-label={`${r.name ?? none}: ${pct(r.rate)}`}>
              <div className="h-full rounded-full" style={{ width: `${(r.rate ?? 0) * 100}%`, background: 'var(--chart-ok)' }} />
            </div>
          </li>
        ))}
        {rows.length === 0 && <li className="text-sm text-muted">{t('common.empty')}</li>}
      </ul>
    </Card>
  )
}

function TopList({ title, children, empty }: { title: string; children: React.ReactNode[]; empty: string }) {
  return (
    <Card className="p-5">
      <h2 className="text-[13px] text-muted">{title}</h2>
      <ol className="mt-3 divide-y divide-border text-[13px]">{children.length ? children : <li className="py-2 text-muted">{empty}</li>}</ol>
    </Card>
  )
}

function Row({ id, name, value }: { id: number; name: string; value: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <Link to={`/attendance/employee/${id}`} className="truncate font-medium hover:text-primary hover:underline">
        {name}
      </Link>
      <span className="shrink-0 tabular-nums text-muted">{value}</span>
    </li>
  )
}
