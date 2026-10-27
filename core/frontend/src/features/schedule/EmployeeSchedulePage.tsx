import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { cellView } from './cellView'
import { currentMonth, shiftMonth, type EmployeeMonth, type Shift } from './api'

/** /schedule/employee/:id?month=YYYY-MM: bitta xodimning oylik taqvimi, kunlarni tanlab o'zgartirish. */
export function EmployeeSchedulePage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const month = params.get('month') && /^\d{4}-\d{2}$/.test(params.get('month')!) ? params.get('month')! : currentMonth()
  const edit = useCan()('schedule.edit')
  const qc = useQueryClient()
  const toast = useToast()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [shiftId, setShiftId] = useState('')

  const data = useQuery({
    queryKey: ['schedule', 'employee', id, month],
    queryFn: () => api<EmployeeMonth>(`/api/v1/schedule/employees/${id}?month=${month}`),
    retry: false,
  })
  const shifts = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })

  const apply = useMutation({
    mutationFn: (body: { mode: 'shift' | 'off' | 'clear'; shift_id?: number }) => send('POST', `/api/v1/schedule/employees/${id}/days`, { dates: [...selected].sort(), ...body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      setSelected(new Set())
    },
  })

  const go = (delta: number) => {
    setSelected(new Set())
    setParams({ month: shiftMonth(month, delta) })
  }
  if (data.error instanceof ApiError && data.error.status === 404) return <NotFound />

  const [y, m] = month.split('-').map(Number) as [number, number]
  const days = data.data?.days ?? []
  const lead = days.length ? days[0]!.weekday : 0
  const dismissed = data.data?.employee.status !== 'active'
  const toggle = (date: string) =>
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(date)) next.delete(date)
      else next.add(date)
      return next
    })
  const active = (shifts.data ?? []).filter((s) => s.is_active)
  const worked = days.filter((d) => d.working).length
  const holidays = days.filter((d) => d.reason === 'holiday').length

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={data.data?.employee.full_name ?? t('schedule.title')}
        subtitle={data.data?.group ? t('schedule.employeeGroup', { group: data.data.group.name }) : t('schedule.noGroup')}
        backTo={`/schedule?month=${month}`}
        backLabel={t('schedule.title')}
        actions={
          <Link to={`/employees/${id}`}>
            <Button variant="outline">{t('employees.toCard')}</Button>
          </Link>
        }
      />

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Button variant="outline" className="size-10 px-0" onClick={() => go(-1)} aria-label={t('schedule.prevMonth')}>
          <ChevronLeft className="size-4" />
        </Button>
        <div className="min-w-40 text-center font-semibold capitalize">{i18n.language === 'ru' ? new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1)) : `${t(`schedule.months.${m - 1}`)} ${y}`}</div>
        <Button variant="outline" className="size-10 px-0" onClick={() => go(1)} aria-label={t('schedule.nextMonth')}>
          <ChevronRight className="size-4" />
        </Button>
        <div className="ml-auto flex gap-2">
          <Badge tone="success">{t('schedule.workDaysCount', { count: worked })}</Badge>
          {holidays > 0 && <Badge tone="danger">{t('schedule.holidaysCount', { count: holidays })}</Badge>}
        </div>
      </Card>

      <Card className="p-4 sm:p-6">
        {data.isLoading ? (
          <Skeleton className="h-96" />
        ) : (
          <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
            {[0, 1, 2, 3, 4, 5, 6].map((d) => (
              <div key={d} className={'pb-1 text-center text-xs font-medium ' + (d >= 5 ? 'text-danger/80' : 'text-muted')}>
                {t(`schedule.wd.${d}`)}
              </div>
            ))}
            {Array.from({ length: lead }).map((_, i) => (
              <div key={`lead${i}`} />
            ))}
            {days.map((d) => {
              const v = cellView(d, data.data!.shifts, t)
              const on = selected.has(d.date)
              return (
                <button
                  key={d.date}
                  type="button"
                  disabled={!edit || dismissed}
                  onClick={() => toggle(d.date)}
                  title={v.title}
                  aria-pressed={on}
                  className={
                    'flex min-h-16 flex-col items-start justify-between rounded-control border p-1.5 text-left transition-colors sm:min-h-20 sm:p-2 ' +
                    (on ? 'border-primary bg-primary/10' : 'border-border hover:bg-surface-2') +
                    (d.holiday && d.reason === 'holiday' ? ' bg-danger/5' : '')
                  }
                >
                  <span className="text-xs font-semibold tabular-nums">{Number(d.date.slice(8))}</span>
                  <span
                    className={
                      'w-full truncate rounded px-1 py-0.5 text-center text-[11px] font-bold ' +
                      (v.kind === 'shift' ? 'text-white' : v.kind === 'holiday' ? 'bg-danger/15 text-danger' : 'bg-surface-2 text-muted') +
                      (d.explicit ? ' ring-2 ring-primary/50' : '')
                    }
                    style={v.color ? { background: v.color } : undefined}
                  >
                    {v.kind === 'shift' ? `${v.label} ${data.data!.shifts[String(d.shift_id)]?.start_time ?? ''}` : v.kind === 'holiday' ? (d.holiday ?? v.label) : v.label}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </Card>

      {edit && !dismissed && (
        <Card className="sticky bottom-2 z-10 flex flex-wrap items-center gap-3 border border-primary/30 p-4">
          <span className="text-sm font-medium">{selected.size ? t('schedule.daysSelected', { count: selected.size }) : t('schedule.pickDays')}</span>
          <Select className="w-auto" value={shiftId} onChange={(e) => setShiftId(e.target.value)} aria-label={t('schedule.shifts.title')}>
            <option value="">{t('schedule.chooseShift')}</option>
            {active.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.start_time}–{s.end_time}
              </option>
            ))}
          </Select>
          <Button disabled={!selected.size || !shiftId || apply.isPending} onClick={() => apply.mutate({ mode: 'shift', shift_id: Number(shiftId) })}>
            {t('schedule.setShift')}
          </Button>
          <Button variant="outline" disabled={!selected.size || apply.isPending} onClick={() => apply.mutate({ mode: 'off' })}>
            {t('schedule.setOff')}
          </Button>
          <Button variant="ghost" disabled={!selected.size || apply.isPending} onClick={() => apply.mutate({ mode: 'clear' })}>
            <Undo2 className="size-4" />
            {t('schedule.resetToGroup')}
          </Button>
          {selected.size > 0 && (
            <Button variant="ghost" onClick={() => setSelected(new Set())}>
              {t('common.clear')}
            </Button>
          )}
          {apply.isError && (
            <p role="alert" className="w-full text-sm text-danger">
              {errorText(t, apply.error)}
            </p>
          )}
        </Card>
      )}
      {dismissed && data.data && <p className="text-sm text-muted">{t('schedule.dismissedNote')}</p>}
    </div>
  )
}
