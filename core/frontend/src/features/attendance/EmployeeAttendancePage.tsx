import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { useCan } from '../auth/useAuth'
import { currentMonth, monthRange, shiftMonth } from '../schedule/api'
import { fmtMin, fmtTime, todayLocal, type AttRecord } from './api'

/** /attendance/employee/:id: bitta xodimning oylik keldi/ketdi yozuvlari. */
export function EmployeeAttendancePage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const edit = useCan()('attendance.edit')
  const [month, setMonth] = useState(currentMonth())
  const { start, end } = monthRange(month)
  const data = useQuery({
    queryKey: ['attendance', 'employee', id, month],
    queryFn: () => api<{ employee: { id: number; full_name: string }; items: AttRecord[] }>(`/api/v1/attendance/employees/${id}/records?start=${start}&end=${end}`),
    retry: false,
  })
  if (data.error instanceof ApiError && data.error.status === 404) return <NotFound />
  const items = data.data?.items ?? []
  const total = items.reduce((s, r) => s + r.worked_minutes, 0)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={data.data?.employee.full_name ?? t('attendance.title')}
        subtitle={t('attendance.employee.subtitle')}
        backTo="/attendance/timesheet"
        backLabel={t('attendance.timesheet.title')}
        actions={
          edit && (
            <Link to={`/attendance/records/new?employee=${id}&date=${todayLocal()}`}>
              <Button>
                <Plus className="size-4" />
                {t('attendance.record.add')}
              </Button>
            </Link>
          )
        }
      />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.prevMonth')} onClick={() => setMonth(shiftMonth(month, -1))}>
          <ChevronLeft className="size-4" />
        </Button>
        <div className="min-w-40 text-center font-semibold">{`${t(`schedule.months.${Number(month.slice(5)) - 1}`)} ${month.slice(0, 4)}`}</div>
        <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.nextMonth')} onClick={() => setMonth(shiftMonth(month, 1))}>
          <ChevronRight className="size-4" />
        </Button>
        <div className="ml-auto flex gap-2">
          <Badge>{t('attendance.employee.days', { count: items.length })}</Badge>
          <Badge tone="success">{t('attendance.employee.hours', { h: fmtMin(total) })}</Badge>
        </div>
      </Card>
      <Card className="overflow-hidden">
        {data.isLoading ? (
          <Skeleton className="m-4 h-40" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.date')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.in')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.out')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.worked')}</th>
                  <th className="px-5 py-2.5 font-medium" />
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <tr key={r.id}>
                    <td className="px-5 py-2.5 tabular-nums">{formatDate(r.work_date, i18n.language)}</td>
                    <td className="px-5 py-2.5 tabular-nums">{fmtTime(r.check_in_at)}</td>
                    <td className="px-5 py-2.5 tabular-nums">{fmtTime(r.check_out_at)}</td>
                    <td className="px-5 py-2.5 tabular-nums">{r.check_out_at ? fmtMin(r.worked_minutes) : '—'}</td>
                    <td className="px-5 py-2.5">
                      <div className="flex flex-wrap gap-1.5">
                        {r.late_minutes > 0 && <Badge tone="warning">{t('attendance.my.late', { m: r.late_minutes })}</Badge>}
                        {r.early_leave_minutes > 0 && <Badge tone="warning">{t('attendance.my.early', { m: r.early_leave_minutes })}</Badge>}
                        {r.is_manual && <Badge>{t('attendance.manual')}</Badge>}
                      </div>
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      {edit && (
                        <Link to={`/attendance/records/${r.id}/edit`}>
                          <Button variant="ghost" className="h-8 px-2">
                            {t('common.edit')}
                          </Button>
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
