import { useQuery } from '@tanstack/react-query'
import { CalendarOff, ChevronLeft, ChevronRight, FileWarning, PencilLine } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { STATUS_TO_INCIDENT } from '../letters/api'
import { addDays, fmtMin, fmtTime, STATUSES, todayLocal, type Daily, type Status } from './api'
import { Filters } from './Filters'
import { emptyFilters, filterParams, type FilterState } from './filterState'
import { StatusBadge } from './StatusBadge'

const SIZE = 50
/** Kartochkalarda ko'rsatiladigan asosiy holatlar */
const HEADLINE: Status[] = ['present', 'late', 'absent', 'working', 'pending', 'off']

/** /attendance/daily: tanlangan kun bo'yicha hamma xodimning holati. */
export function DailyPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const can = useCan()
  const edit = can('attendance.edit')
  const issueLetter = can('letters.issue') || can('letters.manage')
  const [date, setDate] = useState(todayLocal())
  const [filters, setFilters] = useState<FilterState>(emptyFilters)
  const [status, setStatus] = useState<Status | ''>('')
  const [page, setPage] = useState(1)

  const params = new URLSearchParams({ date, page: String(page), size: String(SIZE) })
  filterParams(filters, params)
  if (status) params.set('status', status)
  const list = useQuery({
    queryKey: ['attendance', 'daily', params.toString()],
    queryFn: () => api<Daily>(`/api/v1/attendance/daily?${params}`),
    placeholderData: (prev) => prev,
  })
  const s = list.data?.summary
  const reset = (fn: () => void) => (fn(), setPage(1))

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('attendance.daily.title')} subtitle={t('attendance.daily.subtitle')} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {HEADLINE.map((k) => (
          <button key={k} onClick={() => reset(() => setStatus(status === k ? '' : k))} aria-pressed={status === k} className="text-left">
            <Card className={`p-4 transition-all duration-150 ${status === k ? 'shadow-[inset_0_0_0_1.5px_var(--primary)]' : 'hover:-translate-y-px hover:shadow-pop'}`}>
              <div className="text-xs text-muted">{t(`attendance.status.${k}`)}</div>
              <div className="mt-2 font-mono text-[26px] font-medium leading-none tracking-tight tabular-nums">{s?.[k] ?? '—'}</div>
            </Card>
          </button>
        ))}
      </div>

      <Card className="flex flex-wrap items-center gap-2 p-3">
        <div className="flex items-center gap-1">
          <Button variant="outline" className="size-9 px-0" aria-label={t('attendance.prevDay')} onClick={() => reset(() => setDate(addDays(date, -1)))}>
            <ChevronLeft className="size-4" />
          </Button>
          <Input type="date" value={date} onChange={(e) => e.target.value && reset(() => setDate(e.target.value))} className="w-36 px-2" aria-label={t('attendance.date')} />
          <Button variant="outline" className="size-9 px-0" aria-label={t('attendance.nextDay')} onClick={() => reset(() => setDate(addDays(date, 1)))}>
            <ChevronRight className="size-4" />
          </Button>
          <Button variant="ghost" className="px-2" onClick={() => reset(() => setDate(todayLocal()))}>
            {t('schedule.today')}
          </Button>
        </div>
        <Filters value={filters} onChange={(f) => reset(() => setFilters(f))} />
        <Select className="w-auto" value={status} onChange={(e) => reset(() => setStatus(e.target.value as Status | ''))} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          {STATUSES.map((k) => (
            <option key={k} value={k}>
              {t(`attendance.status.${k}`)}
            </option>
          ))}
        </Select>
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('employees.fullName')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('attendance.shift')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.in')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.out')}</th>
                <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('attendance.worked')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.isLoading && (
                <tr>
                  <td colSpan={7} className="px-5 py-2.5">
                    <Skeleton className="h-32" />
                  </td>
                </tr>
              )}
              {list.data?.items.map((r) => (
                <tr key={r.employee.id} data-href onClick={(ev) => !(ev.target as HTMLElement).closest('a,button,input') && navigate(`/attendance/employee/${r.employee.id}`)}>
                  <td className="px-5 py-2.5">
                    <Link to={`/schedule/employee/${r.employee.id}`} className="font-medium hover:text-primary hover:underline">
                      {r.employee.full_name}
                    </Link>
                  </td>
                  <td className="hidden px-5 py-2.5 text-muted md:table-cell">{r.shift ? `${r.shift.name} ${r.shift.start_time}–${r.shift.end_time}` : '—'}</td>
                  <td className="px-5 py-2.5 tabular-nums">
                    {fmtTime(r.record?.check_in_at)}
                    {r.record && r.record.late_minutes > 0 && <Badge className="ml-2" tone="warning">+{r.record.late_minutes}</Badge>}
                  </td>
                  <td className="px-5 py-2.5 tabular-nums">
                    {fmtTime(r.record?.check_out_at)}
                    {r.record && r.record.early_leave_minutes > 0 && <Badge className="ml-2" tone="warning">−{r.record.early_leave_minutes}</Badge>}
                  </td>
                  <td className="hidden px-5 py-2.5 tabular-nums sm:table-cell">{r.record?.check_out_at ? fmtMin(r.record.worked_minutes) : '—'}</td>
                  <td className="px-5 py-2.5">
                    <StatusBadge status={r.status} />
                    {r.record?.is_manual && <Badge className="ml-1.5">{t('attendance.manual')}</Badge>}
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {issueLetter && STATUS_TO_INCIDENT[r.status] && (
                      <Link to={`/letters/new?employee=${r.employee.id}&type=${STATUS_TO_INCIDENT[r.status]}&date=${date}`} title={t('letters.askExplanation')}>
                        <Button variant="ghost" className="h-8 px-2" aria-label={t('letters.askExplanation')}>
                          <FileWarning className="size-4" />
                        </Button>
                      </Link>
                    )}
                    {edit && (
                      <Link to={r.record ? `/attendance/records/${r.record.id}/edit` : `/attendance/records/new?employee=${r.employee.id}&date=${date}`}>
                        <Button variant="ghost" className="h-8 px-2" aria-label={t('common.edit')}>
                          <PencilLine className="size-4" />
                        </Button>
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
              {list.data && list.data.items.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <EmptyState icon={CalendarOff} title={t('attendance.emptyTitle')} hint={t('attendance.emptyHint')} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {list.data && (
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />
          </div>
        )}
      </Card>
      <p className="text-xs text-muted">{t('attendance.daily.note')}</p>
    </div>
  )
}
