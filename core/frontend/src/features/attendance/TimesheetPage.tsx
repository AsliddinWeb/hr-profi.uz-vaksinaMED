import { useQuery } from '@tanstack/react-query'
import { CalendarOff, ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { monthRange, shiftMonth } from '../schedule/api'
import { addDays, CODES, fmtMin, mondayOf, STATUSES, TONES, todayLocal, type Timesheet } from './api'
import { Filters } from './Filters'
import { emptyFilters, filterParams, type FilterState } from './filterState'

const SIZE = 30

type Mode = 'week' | 'month'

/** /attendance/timesheet: hafta yoki oy tabeli (xodimlar x kunlar) + jami ko'rsatkichlar va Excel eksport. */
export function TimesheetPage() {
  const { t } = useTranslation()
  const can = useCan()
  const [mode, setMode] = useState<Mode>('month')
  const [anchor, setAnchor] = useState(todayLocal())
  const [filters, setFilters] = useState<FilterState>(emptyFilters)
  const [page, setPage] = useState(1)

  const range = mode === 'week' ? { start: mondayOf(anchor), end: addDays(mondayOf(anchor), 6) } : monthRange(anchor.slice(0, 7))
  const params = new URLSearchParams({ start: range.start, end: range.end })
  filterParams(filters, params)
  const list = useQuery({
    queryKey: ['attendance', 'timesheet', params.toString(), page],
    queryFn: () => api<Timesheet>(`/api/v1/attendance/timesheet?${params}&page=${page}&size=${SIZE}`),
    placeholderData: (prev) => prev,
  })
  const move = (delta: number) => {
    setPage(1)
    setAnchor(mode === 'week' ? addDays(anchor, 7 * delta) : `${shiftMonth(anchor.slice(0, 7), delta)}-01`)
  }
  const data = list.data
  const title = mode === 'week' ? `${range.start.split('-').reverse().join('.')} – ${range.end.split('-').reverse().join('.')}` : `${t(`schedule.months.${Number(anchor.slice(5, 7)) - 1}`)} ${anchor.slice(0, 4)}`

  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
      <PageHeader
        title={t('attendance.timesheet.title')}
        subtitle={t('attendance.timesheet.subtitle')}
        actions={
          <a href={`/api/v1/attendance/timesheet/export?${params}`} download>
            <Button variant="outline">
              <Download className="size-4" />
              {t('attendance.timesheet.export')}
            </Button>
          </a>
        }
      />
      <Card className="flex flex-wrap items-center gap-2 p-3">
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
          {(['week', 'month'] as const).map((m) => (
            <button key={m} onClick={() => (setMode(m), setPage(1))} className={mode === m ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`attendance.timesheet.${m}`)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" className="size-9 px-0" aria-label={t('schedule.prevMonth')} onClick={() => move(-1)}>
            <ChevronLeft className="size-4" />
          </Button>
          <div className="min-w-40 px-2 text-center text-[13px] font-medium capitalize">{title}</div>
          <Button variant="outline" className="size-9 px-0" aria-label={t('schedule.nextMonth')} onClick={() => move(1)}>
            <ChevronRight className="size-4" />
          </Button>
          <Button variant="ghost" onClick={() => (setAnchor(todayLocal()), setPage(1))}>
            {t('schedule.today')}
          </Button>
        </div>
        <Filters value={filters} onChange={(f) => (setFilters(f), setPage(1))} />
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 min-w-52 border-b border-border bg-surface px-4 py-2 text-left text-xs font-medium text-muted">{t('employees.fullName')}</th>
                {data?.days.map((d) => (
                  <th key={d.date} title={d.holiday ?? undefined} className={'min-w-8 border-b border-border px-0.5 py-2 text-center text-xs font-medium ' + (d.holiday ? 'bg-danger/10 text-danger' : d.weekday >= 5 ? 'text-danger/80' : 'text-muted')}>
                    <div>{t(`schedule.wd.${d.weekday}`)}</div>
                    <div className="text-sm font-semibold tabular-nums text-text">{Number(d.date.slice(8))}</div>
                  </th>
                ))}
                {['days', 'absent', 'late', 'lateMin', 'earlyMin', 'hours'].map((k) => (
                  <th key={k} className="whitespace-nowrap border-b border-l border-border bg-surface-2 px-3 py-2 text-xs font-medium text-muted">
                    {t(`attendance.timesheet.cols.${k}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.isLoading && (
                <tr>
                  <td colSpan={40} className="px-4 py-3">
                    <Skeleton className="h-40" />
                  </td>
                </tr>
              )}
              {data?.rows.map((r) => (
                <tr key={r.employee.id} className="group">
                  <td className="sticky left-0 z-10 border-b border-border bg-surface px-4 py-1.5 group-hover:bg-surface-2">
                    <Link to={`/attendance/employee/${r.employee.id}`} className="block max-w-48 truncate font-medium hover:text-primary hover:underline">
                      {r.employee.full_name}
                    </Link>
                    <div className="max-w-48 truncate text-xs text-muted">{r.employee.position ?? '—'}</div>
                  </td>
                  {r.cells.map((c, i) => {
                    const cell = (
                      <span title={`${t(`attendance.status.${c.status}`)}${c.late ? ` · +${c.late}` : ''}`} className={`grid h-7 min-w-7 place-items-center rounded-md text-[11px] font-semibold ${TONES[c.status]}`}>
                        {CODES[c.status]}
                      </span>
                    )
                    return (
                      <td key={i} className="border-b border-border p-0.5 text-center group-hover:bg-surface-2">
                        {c.record_id && can('attendance.edit') ? <Link to={`/attendance/records/${c.record_id}/edit`}>{cell}</Link> : cell}
                      </td>
                    )
                  })}
                  <Totals t={r.totals} />
                </tr>
              ))}
              {data && data.rows.length === 0 && (
                <tr>
                  <td colSpan={40}>
                    <EmptyState icon={CalendarOff} title={t('attendance.emptyTitle')} hint={t('attendance.emptyHint')} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {data && (
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={data.total} onPage={setPage} />
          </div>
        )}
      </Card>

      <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted">
        {STATUSES.filter((s) => CODES[s]).map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5">
            <span className={`grid h-5 min-w-6 place-items-center rounded px-1 text-[10px] font-bold ${TONES[s]}`}>{CODES[s]}</span>
            {t(`attendance.status.${s}`)}
          </span>
        ))}
      </div>
    </div>
  )
}

function Totals({ t }: { t: Timesheet['rows'][number]['totals'] }) {
  const cell = 'border-b border-l border-border bg-surface-2/50 px-3 py-1.5 text-center tabular-nums'
  return (
    <>
      <td className={cell}>{t.worked_days}</td>
      <td className={cell + (t.absent ? ' font-semibold text-danger' : '')}>{t.absent}</td>
      <td className={cell}>{t.late_count}</td>
      <td className={cell}>{t.late_minutes}</td>
      <td className={cell}>{t.early_minutes}</td>
      <td className={cell}>{fmtMin(t.worked_minutes)}</td>
    </>
  )
}
